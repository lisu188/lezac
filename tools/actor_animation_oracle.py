"""Unchanged actor-animation instructions on controlled far records, not gameplay."""
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


def profiles():
    result = []
    backup = (9,8,12,1,2,1,255)
    def add(active, segment=0x1aa2, offset=0x1bd4, visual=2, floor=0x200, sp=0x3fde, error=0):
        result.append((segment,offset,visual,floor,sp,len(result)%2,error,tuple(active),backup))
    for mode in range(256):
        add((6,3,6,0,0,mode,1))
    for counter in range(256):
        add((6,3,6,counter,128,3,1),segment=0x5000)
    for step in range(256):
        add((5,3,6,0,0,2,step))
    for segment in (0x1aa2,0x5000):
        for offset in (0,0x1b88,0x1bae,0x1bd4,0xffe7,0xffe8,0xffe9,0xffea,0xfff0,0xffff):
            for visual in (0,1,31,32,127,255):
                add((6,3,6,0,0,3,1),segment,offset,visual)
    for mode in (1,2,3,255):
        for current in (0,1,127,128,254,255):
            for step in (0,1,127,128,255):
                add((current,3,6,0,0,mode,step))
    for floor,sp in ((0x4000,0x3fde),(0x200,0x210),(0x3da3,0x3fde)):
        add((6,3,6,0,0,3,1),floor=floor,sp=sp,error=1)
    return result


def memory(index,profile,image):
    segment,offset,visual,floor,sp,df,error,active,backup = profile
    initial = bytearray(1048576)
    initial[0x10000:0x10000+len(image)] = image
    stack = 0x70000+sp-128
    initial[stack:stack+144] = bytes((i*29+index*7+11)&255 for i in range(144))
    struct.pack_into('<H',initial,0x1aa20+0x1afa,floor)
    for i in range(256):
        struct.pack_into('<H',initial,0x1aa20+0xc324+i*4,(i*197+index*13+0x5a)&65535)
        struct.pack_into('<H',initial,0x1aa20+0xc224+i*8,(i*117+index*23+0xa55a)&65535)
    for i in range(38):
        initial[segment*16+((offset+i)&65535)] = (i*11+index*7+19)&255
    initial[segment*16+((offset+1)&65535)] = visual
    for i,value in enumerate(active+backup):
        initial[segment*16+((offset+0x16+i)&65535)] = value
    struct.pack_into('<3H',initial,0x70000+sp,0x7ee4,offset,segment)
    values = (0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x3ffe,
        0x1000,0x1aa2,0x40,0x7000,sp,0x6053,0x602 if df else 0x202)
    return initial,values,stack


def generate(root,out):
    if unicorn.__version__ != '2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported Unicorn loader profile')
    library = Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes()) != LIB_SHA or not any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual original-CPU library mapping differs')
    sources = {name:sha((root/'tools'/name).read_bytes()) for name in
        ('actor_animation_oracle.py','frame_camera_oracle.py')}
    exe = (root/'LEZAC.EXE').read_bytes()
    if sha(exe) != EXE_SHA:
        raise ValueError('Original executable differs')
    mz = struct.unpack_from('<14H',exe)
    image = bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment = struct.unpack_from('<HH',exe,mz[12]+i*4)
        at = segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out = out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only output directory')
    out.mkdir()
    cases = profiles()
    output = bytearray(b'LZANIM01'+struct.pack('<I',len(cases)))
    coverage,states,write_count,rep_stops,copies = set(),0,0,0,0
    try:
        for index,profile in enumerate(cases):
            initial,values,stack = memory(index,profile,image)
            cursor_addresses = {profile[0]*16+((profile[1]+0x16+i)&65535) for i in range(7)}
            visual_address = 0x1aa20+0xc224+profile[2]*8
            trace,writes,endpoints = [],[],[]
            until = 0x192e2 if profile[6] else 0x1615a
            zero_stops = [0]
            for observed in (True,False):
                engine = unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                engine.mem_map(0,1048576)
                engine.mem_write(0,bytes(initial))
                for reg,value in zip(REGS,values):
                    engine.reg_write(reg,value)
                def external(*unused):
                    raise ValueError('Actor animation crossed an interrupt or I/O')
                def code(uc,address,size,user):
                    row = tuple(uc.reg_read(reg) for reg in REGS)
                    cs,ip = row[7],row[12]
                    if not (cs == 0x1000 and 0x6053 <= ip < 0x615a or cs == 0x1920 and
                            (0x4df <= ip < 0x4f7 or 0x90e <= ip < 0x926)):
                        raise ValueError('Actor animation left declared original instructions')
                    coverage.add((cs,ip))
                    if cs == 0x1920 and ip == 0x91f and row[2] == 0 and trace and trace[-1][7:8]+trace[-1][12:13] == (cs,ip):
                        zero_stops[0] += 1
                    else:
                        trace.append(row)
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (stack <= address and address+size <= stack+144 or
                            size == 1 and address in cursor_addresses or size == 2 and address == visual_address):
                        raise ValueError('Actor animation wrote outside stack/cursor/descriptor owners')
                    writes.append((address,size,value&((1<<(size*8))-1)))
                engine.hook_add(unicorn.UC_HOOK_INTR,external)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                engine.emu_start(0x16053,until,count=10000)
                registers = tuple(engine.reg_read(reg) for reg in REGS)
                final = bytes(engine.mem_read(0,1048576))
                if registers[7]*16+registers[12] != until or final[0x10000:0x1aa20] != initial[0x10000:0x1aa20]:
                    raise ValueError('Actor animation endpoint or unchanged code differs')
                endpoints.append((registers,final))
            if endpoints[0] != endpoints[1]:
                raise ValueError('Observer changed complete memory/registers')
            registers,final = endpoints[0]
            reconstructed = bytearray(initial)
            for address,size,value in writes:
                reconstructed[address:address+size] = value.to_bytes(size,'little')
            if reconstructed != final:
                raise ValueError('Ordered writes do not reconstruct complete final memory')
            trace.append(registers)
            states += len(trace); write_count += len(writes); rep_stops += zero_stops[0]
            copies += sum(row[7] == 0x1920 and row[12] == 0x91f for row in trace)
            output.extend(struct.pack('<I7H14B',index,*profile[:7],*profile[7],*profile[8]))
            output.extend(struct.pack('<13HI13HI',*values,*registers))
            output.extend(struct.pack('<I',len(trace)))
            for row in trace:
                output.extend(struct.pack('<13HI',*row))
            output.extend(struct.pack('<I',len(writes)))
            for row in writes:
                output.extend(struct.pack('<IBH',*row))
        if sha((root/'LEZAC.EXE').read_bytes()) != EXE_SHA or sha(library.read_bytes()) != LIB_SHA or any(
                sha((root/'tools'/name).read_bytes()) != digest for name,digest in sources.items()):
            raise ValueError('Original producer inputs changed during execution')
        raw = bytes(output)
        compressed = gzip.compress(raw,mtime=0)
        (out/'oracle.bin.gz').write_bytes(compressed)
        manifest = dict(schema='lezac-controlled-actor-animation-v1',executable_sha256=EXE_SHA,sources=sources,
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            cases=len(cases),register_states=states,writes=write_count,runtime_errors=3,
            executed_instructions=[list(row) for row in sorted(coverage)],string_bytes=copies,
            unicorn_rep_zero_stops_removed=rep_stops,projection_bytes=len(raw),projection_sha256=sha(raw),
            compressed_bytes=len(compressed),compressed_sha256=sha(compressed),original_code_bytes_verified=43552,
            complete_memory_observer_control=True,ordered_writes_reconstruct_full_memory=True,
            instruction_patches=0,calls_stubbed=0,interrupts_delivered=0,hardware_io=0,
            controlled_initial_memory=True,natural_capture=False,production_app_comparison=False,
            raw_memory_published=False,full_frame_claim=False,whole_game_parity=False,
            trace_arithmetic_flags_compared=False,endpoint_all_flags_compared=True)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(cases),states=states,writes=write_count,
            bytes=len(raw),compressed=len(compressed),sha256=sha(raw))))
    except Exception as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,error=str(error)))+'\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    generate(args.repo.resolve(),args.out)
