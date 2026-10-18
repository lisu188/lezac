"""Controlled original camera/raster/copy execution with independent camera arguments."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT
from frame_world_raster_inputs import ASSETS, assets
from frame_camera_oracle import REGS, LIB_SHA

sha = lambda raw: hashlib.sha256(raw).hexdigest()
SOURCES = ('standalone_camera_oracle.py', 'frame_world_raster_inputs.py', 'frame_camera_oracle.py')
DATA = 0x1aa20


def generate(root, out):
    library = Path(uclib._name).resolve(strict=True)
    if unicorn.__version__ != '2.1.4' or sha(library.read_bytes()) != LIB_SHA or any(
            key in os.environ for key in ('LD_PRELOAD', 'LIBUNICORN_PATH')):
        raise ValueError('Original CPU loader differs')
    if not any(line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual original CPU mapping differs')
    sources = {name: sha((root/'tools'/name).read_bytes()) for name in SOURCES}
    files, tiles, descriptors, sprites = assets(root)
    exe = files['LEZAC.EXE']
    mz = struct.unpack_from('<14H', exe)
    image = bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12]+i*4)
        at = segment*16+offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0]+0x1000)&65535)
    out = out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only output directory')
    out.mkdir()
    output = bytearray(b'LZSVIEW1'+struct.pack('<I', 24))
    metadata = []
    try:
        for background in (0, 1):
            for x, y, width, height in ((4,4,152,152), (164,4,152,152), (4,4,312,152)):
                for mode, camera_x in enumerate((104,136,168,136)):
                    index = len(metadata)
                    pitch = width+8
                    center = ((pitch//8-2)//2)*8
                    initial = bytearray(1048576)
                    initial[0x10000:0x10000+len(image)] = image
                    initial[DATA:DATA+65537] = bytes(65537)
                    initial[DATA+0x7f74:DATA+0x7f74+len(tiles)] = tiles
                    initial[DATA+0xa0aa:DATA+0xa0aa+len(tiles)] = bytes(0 if v else 255 for v in tiles)
                    initial[0x78008:0x78008+60000] = bytes([17])*60000
                    initial[0xd0000:0xd0000+len(sprites)] = sprites
                    initial[0xa0000:0xafa00] = bytes((i*11+(i>>8)*7+index)&255 for i in range(64000))
                    fields = ((0x1afa,0x200),(0x78bc,center),(0x78be,center//8),
                        (0x2094,(60-pitch//8)*8),(0x2096,96),(0x2098,0),(0x79f0,y*320+x),
                        (0xc1ea,pitch//8),(0xc1ec,pitch),(0xc1ee,160),(0xc1f6,320-pitch),
                        (0xc1f8,320),(0xc1fa,0xd000),(0xc1fe,0x4800),(0xc204,60),
                        (0xc206,320-pitch),(0xc208,0x7f74),(0xc212,0x6000),(0xc214,8),
                        (0xc498,8),(0xc49a,0x7800))
                    for offset, value in fields:
                        struct.pack_into('<H', initial, DATA+offset, value)
                    initial[DATA+0x79e6] = 1
                    initial[DATA+0xc496] = 2
                    initial[DATA+0xc49c] = background
                    for row, player_x in enumerate((104,136)):
                        sw, sh, source = descriptors[row]
                        struct.pack_into('<HHBBH', initial, DATA+0xc21e+row*8, player_x,168,sw,sh,source)
                    struct.pack_into('<3H', initial, 0x73fde, 0x7a25,168,camera_x)
                    values = (0,0,0,0,0,0,0x3ffe,0x1000,0x1aa2,0,0x7000,0x3fde,0x3587,0x202)
                    endpoints, writes = [], []
                    for observed in (True,False):
                        engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
                        engine.mem_map(0,1048576)
                        engine.mem_write(0,bytes(initial))
                        for register, value in zip(REGS,values):
                            engine.reg_write(register,value)
                        def external(*unused):
                            raise ValueError('Standalone camera crossed an interrupt or I/O')
                        def write(uc,access,address,size,value,user):
                            if size not in (1,2) or not (0x60000<=address and address+size<=0x70001 or
                                    0xa0000<=address and address+size<=0xb0001 or
                                    0x73f80<=address and address+size<=0x74000 or
                                    DATA+0xc1e8<=address and address+size<=DATA+0xc21e):
                                raise ValueError('Standalone camera wrote outside declared outputs')
                            writes.append((address,size,value&((1<<(size*8))-1)))
                        engine.hook_add(unicorn.UC_HOOK_INTR,external)
                        engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_IN)
                        engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_OUT)
                        if observed:
                            engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                        engine.emu_start(0x13587,0x17a57,count=4000000)
                        registers = tuple(engine.reg_read(register) for register in REGS)
                        final = bytes(engine.mem_read(0,1048576))
                        if (registers[7],registers[11],registers[12]) != (0x1000,0x3fe4,0x7a57):
                            raise ValueError('Original standalone camera endpoint differs')
                        if final[0x10000:DATA] != initial[0x10000:DATA]:
                            raise ValueError('Original code changed')
                        endpoints.append((registers,final))
                    if endpoints[0] != endpoints[1]:
                        raise ValueError('Observer changed complete memory/registers')
                    registers, final = endpoints[0]
                    replay = bytearray(initial)
                    for address,size,value in writes:
                        replay[address:address+size] = value.to_bytes(size,'little')
                    if replay != final or final[DATA+0xc21e:DATA+0xc22e] != initial[DATA+0xc21e:DATA+0xc22e]:
                        raise ValueError('Ordered writes or player visual ownership differ')
                    output.extend(struct.pack('<4H2B2H',x,y,width,height,background,mode,camera_x,168))
                    output.extend(final[0xa0000:0xafa00])
                    metadata.append(dict(index=index,background=background,camera_mode=mode,
                        rect=[x,y,width,height],camera=[camera_x,168],writes=len(writes),
                        initial_memory_sha256=sha(initial),final_memory_sha256=sha(final),
                        final_vga_sha256=sha(final[0xa0000:0xafa00]),endpoint_registers=list(registers)))
        if any(sha((root/name).read_bytes()) != digest for name,digest in ASSETS.items()) or any(
                sha((root/'tools'/name).read_bytes()) != digest for name,digest in sources.items()) or sha(library.read_bytes()) != LIB_SHA:
            raise ValueError('Producer inputs changed during capture')
        raw = bytes(output)
        compressed = gzip.compress(raw,mtime=0)
        (out/'oracle.bin.gz').write_bytes(compressed)
        manifest = dict(schema='lezac-controlled-standalone-camera-v1',assets=ASSETS,sources=sources,
            cases=metadata,unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True,full_memory_observer_control=True,
            ordered_writes_reconstruct_memory=True,player_visuals_unchanged=True,
            controlled_initial_state=True,natural_capture=False,raw_memory_published=False,
            original_calls_stubbed=0,instruction_patches=0,full_frame_claim=False,work_clock_claim=False,
            projection_bytes=len(raw),projection_sha256=sha(raw),compressed_bytes=len(compressed),compressed_sha256=sha(compressed))
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(metadata),bytes=len(raw),compressed=len(compressed),sha256=sha(raw))))
    except Exception as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=len(metadata),error=str(error)))+'\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    generate(args.repo.resolve(),args.out)
