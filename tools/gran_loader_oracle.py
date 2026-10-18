"""Unchanged GRAN loader with explicit read-only DOS file-service contracts."""
import argparse
import gzip
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT
from frame_camera_oracle import REGS, EXE_SHA, LIB_SHA, sha

DATA = 0x1aa20
STATE_BYTES = 31*38+33*8+8*16+5


def state(memory):
    return bytes(memory[DATA+0x1bae:DATA+0x1bae+31*38]+
        memory[DATA+0xc21e:DATA+0xc21e+33*8]+
        memory[DATA+0x79ea:DATA+0x79ea+8*16]+
        bytes((memory[DATA+0x208d],memory[DATA+0xc496],memory[DATA+0x79f9]))+
        memory[DATA+0x2072:DATA+0x2074])


def profiles():
    return [(actors,links,x&65535,y&65535) for actors in (0,1,23) for links in (0,1)
        for x,y in ((100,100),(-32768,32767),(32767,-32768),(-1,0))]


def initial_memory(index,profile,image,descriptors,pixels):
    actors,links,x,y = profile
    initial = bytearray(1048576)
    initial[0x10000:0x10000+len(image)] = image
    initial[0x73c00:0x74000] = bytes((i*29+index*7+11)&255 for i in range(1024))
    for offset,count,multiplier in ((0x1bae,31*38,13),(0xc21e,33*8,17),(0x79ea,8*16,23)):
        initial[DATA+offset:DATA+offset+count] = bytes((i*multiplier+index*7+19)&255 for i in range(count))
    for slot in range(actors+1):
        initial[DATA+0x1bae+slot*38+1] = slot+1
    initial[DATA+0x208d] = actors
    initial[DATA+0x79f9] = links
    initial[DATA+0xc496] = actors+2
    struct.pack_into('<H',initial,DATA+0x2072,0xa55a)
    struct.pack_into('<H',initial,DATA+0x1afa,0x200)
    struct.pack_into('<H',initial,DATA+0xc1fa,0xd000)
    for index,descriptor in enumerate(descriptors):
        initial[DATA+0xc326+index*4:DATA+0xc326+index*4+4] = descriptor
    initial[0xd0000:0xd0000+len(pixels)] = pixels
    struct.pack_into('<5H',initial,0x73fe4,0x2e9c,y,x,0x2ad3,0x1000)
    registers = (0,0,0,0,0,0,0x3ffe,0x1000,0x1aa2,0,0x7000,0x3fe4,0x8a5,0x202)
    return initial,registers


def execute(initial,registers,file,observed):
    engine = unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
    engine.mem_map(0,1048576)
    engine.mem_write(0,bytes(initial))
    for register,value in zip(REGS,registers):
        engine.reg_write(register,value)
    position,opened = 0,False
    calls,events,coverage = [],[],set()
    unknown_writes = set()
    def interrupt(uc,number,user):
        nonlocal position,opened
        r = tuple(uc.reg_read(reg) for reg in REGS)
        ax,bx,cx,dx = r[:4]
        if number != 0x21:
            raise ValueError('Unmodeled loader interrupt')
        record = dict(ax=ax,bx=bx,cx=cx,dx=dx,ds=r[8],cs=r[7],ip=r[12])
        if ax == 0x3d02 and not opened:
            name = bytes(uc.mem_read(r[8]*16+dx,128)).split(bytes([0]),1)[0]
            if name.lower() != b'gran.mst':
                raise ValueError('Original loader opened an unexpected file')
            opened = True
            uc.reg_write(REGS[0],5)
        elif ax >> 8 == 0x3f and bx == 5 and opened:
            raw = file[position:position+cx]
            if len(raw) != cx:
                raise ValueError('Original loader read beyond the canonical file')
            address = r[8]*16+dx
            if not (0x73c00 <= address and address+len(raw) <= 0x74000 or
                    DATA+0x1bae <= address and address+len(raw) <= DATA+0x1bae+31*38 or
                    DATA+0x79ea <= address and address+len(raw) <= DATA+0x79ea+8*16):
                raise ValueError('DOS file read left declared stack/actor/link owners')
            uc.mem_write(address,raw)
            if observed:
                events.append((address,raw,'dos-read'))
            position += len(raw)
            uc.reg_write(REGS[0],len(raw))
            record['returned'] = len(raw)
        else:
            raise ValueError('Unmodeled loader DOS service: '+str(record))
        uc.reg_write(REGS[13],r[13]&~1)
        calls.append(record)
    def code(uc,address,size,user):
        if not 0x10000 <= address < DATA or address+size > DATA:
            raise ValueError('Loader executed outside unchanged original code')
        row = (uc.reg_read(REGS[7]),uc.reg_read(REGS[12]))
        if row == (0x1920,0xe2):
            raise ValueError('Unexpected original loader runtime error')
        coverage.add(row)
    def write(uc,access,address,size,value,user):
        allowed = (0x73c00 <= address and address+size <= 0x74000 or
            DATA+0x1bae <= address and address+size <= DATA+0x1bae+31*38 or
            DATA+0xc21e <= address and address+size <= DATA+0xc21e+33*8 or
            DATA+0x79ea <= address and address+size <= DATA+0x79ea+8*16 or
            address in (DATA+0x208d,DATA+0xc496) or address == DATA+0x1afc and size == 2)
        if not allowed:
            raise ValueError('Original loader wrote outside declared owners: '+str((address,size)))
        if size not in (1,2,4):
            raise ValueError('Unexpected original loader write width')
        events.append((address,(value&((1<<(size*8))-1)).to_bytes(size,'little'),'guest'))
    def io(*unused):
        raise ValueError('Loader performed unmodeled hardware I/O')
    engine.hook_add(unicorn.UC_HOOK_INTR,interrupt)
    engine.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_IN)
    engine.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_OUT)
    if observed:
        engine.hook_add(unicorn.UC_HOOK_CODE,code)
        engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
    engine.emu_start(0x108a5,0x12e9c,count=2000000)
    final = bytes(engine.mem_read(0,1048576))
    end = tuple(engine.reg_read(reg) for reg in REGS)
    if (end[7],end[11],end[12]) != (0x1000,0x3fee,0x2e9c) or position != len(file) or not opened:
        raise ValueError('Original loader did not consume the file and return')
    if final[0x10000:DATA] != initial[0x10000:DATA]:
        raise ValueError('Original loader code changed')
    if observed:
        reconstructed = bytearray(initial)
        for address,raw,source in events:
            reconstructed[address:address+len(raw)] = raw
        if reconstructed != final:
            raise ValueError('Guest/DOS read writes do not reconstruct complete memory')
    return end,final,calls,events,coverage,unknown_writes


def generate(root,out):
    if unicorn.__version__ != '2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported original-CPU loader profile')
    library = Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes()) != LIB_SHA or not any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual original-CPU mapping differs')
    assets = {name:sha((root/name).read_bytes()) for name in ('LEZAC.EXE','GRAN.MST','PROVA.SPR')}
    if assets['LEZAC.EXE'] != EXE_SHA:
        raise ValueError('Original executable differs')
    sources = {name:sha((root/'tools'/name).read_bytes()) for name in ('gran_loader_oracle.py','frame_camera_oracle.py')}
    exe = (root/'LEZAC.EXE').read_bytes()
    mz = struct.unpack_from('<14H',exe)
    image = bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment = struct.unpack_from('<HH',exe,mz[12]+i*4)
        at = segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    raw_sprites = (root/'PROVA.SPR').read_bytes()
    descriptors,pixels,at = [],bytearray(),1
    for index in range(raw_sprites[0]):
        width,height = raw_sprites[at:at+2]; at += 2
        descriptors.append(struct.pack('<BBH',width,height,len(pixels)))
        pixels.extend(raw_sprites[at:at+width*height]); at += width*height
    if at != len(raw_sprites) or len(pixels) >= 65536:
        raise ValueError('Canonical boss sprite bank differs')
    file = (root/'GRAN.MST').read_bytes()
    if len(file) != 399 or file[0] != 7:
        raise ValueError('Canonical GRAN shape differs')
    out = out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only output')
    out.mkdir()
    cases = profiles()
    output = bytearray(b'LZGRAN01'+struct.pack('<I',len(cases)))
    all_coverage,unknown = set(),set()
    metadata = []
    try:
        for index,profile in enumerate(cases):
            initial,registers = initial_memory(index,profile,image,descriptors,pixels)
            observed = execute(initial,registers,file,True)
            plain = execute(initial,registers,file,False)
            if observed[:3] != plain[:3]:
                raise ValueError('Loader observer changed complete memory/registers or DOS calls')
            end,final,calls,events,coverage,unknown_writes = observed
            all_coverage.update(coverage);unknown.update(unknown_writes)
            before,after = state(initial),state(final)
            if len(before) != STATE_BYTES or len(after) != STATE_BYTES:
                raise ValueError('Loader state projection size differs')
            if (final[DATA+0x208d],final[DATA+0xc496],final[DATA+0x79f9]) != (profile[0]+7,profile[0]+9,profile[1]+6):
                raise ValueError('Original loaded group counts differ')
            output.extend(struct.pack('<I4H',index,*profile))
            output.extend(before);output.extend(after)
            metadata.append(dict(index=index,profile=list(profile),dos_calls=calls,
                guest_writes=sum(row[2]=='guest' for row in events),dos_memory_writes=sum(row[2]=='dos-read' for row in events),
                initial_memory_sha256=sha(initial),final_memory_sha256=sha(final),endpoint_registers=list(end),
                initial_state_sha256=sha(before),final_state_sha256=sha(after)))
        for name,digest in assets.items():
            if sha((root/name).read_bytes()) != digest:
                raise ValueError('Loader asset changed during generation')
        if sha(library.read_bytes()) != LIB_SHA or any(sha((root/'tools'/name).read_bytes()) != digest for name,digest in sources.items()):
            raise ValueError('Loader producer changed during generation')
        raw = bytes(output)
        compressed = gzip.compress(raw,mtime=0)
        (out/'oracle.bin.gz').write_bytes(compressed)
        manifest = dict(schema='lezac-controlled-gran-loader-v1',assets=assets,sources=sources,cases=metadata,
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            executed_instructions=[list(row) for row in sorted(all_coverage)],unknown_guest_writes=[list(row) for row in sorted(unknown)],
            projection_bytes=len(raw),projection_sha256=sha(raw),compressed_bytes=len(compressed),compressed_sha256=sha(compressed),
            complete_memory_observer_control=True,guest_and_device_writes_reconstruct_full_memory=True,
            dos_file_services_modeled=True,dos_kernel_execution=False,guest_calls_stubbed=0,instruction_patches=0,
            original_code_bytes_verified=43552,natural_capture=False,whole_game_parity=False,raw_memory_published=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(cases),bytes=len(raw),compressed=len(compressed),
            unknown_guest_writes=manifest['unknown_guest_writes'],sha256=sha(raw))))
    except Exception as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,error=str(error)))+'\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    generate(args.repo.resolve(),args.out)
