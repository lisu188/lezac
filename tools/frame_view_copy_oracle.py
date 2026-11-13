"""Controlled execution of unchanged 08AC:03C8; no natural frame/timing claim."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX,
    UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES,
    UC_X86_REG_SS, UC_X86_REG_SP, UC_X86_REG_IP, UC_X86_REG_EFLAGS, UC_X86_INS_IN, UC_X86_INS_OUT)

REGS = (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX, UC_X86_REG_SI, UC_X86_REG_DI,
    UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS, UC_X86_REG_SP,
    UC_X86_REG_IP, UC_X86_REG_EFLAGS)
PROFILES = ((320,160,0,0,8,1284,0x202), (320,160,7,7,8,1284,0x202),
    (160,160,0,0,8,1284,0x202), (160,160,7,7,8,1444,0x202),
    (320,9,1,0,65534,1284,0x202), (320,10,0,0,65535,1284,0x202),
    (160,12,3,1,65530,1444,0x202), (320,9,0,0,8,65534,0x202),
    (160,10,7,0,8,65535,0x202), (320,9,0,0,256,1284,0x602),
    (160,11,7,7,65534,1444,0x602), (168,32,14,7,8,1284,0x202))
EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
LIBRARY_SHA = 'ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def generate(root, out):
    if unicorn.__version__ != '2.1.4' or any(k in os.environ for k in ('LD_PRELOAD', 'LIBUNICORN_PATH')):
        raise ValueError('Unsupported Unicorn loader profile')
    library = Path(uclib._name).resolve(strict=True)
    mapped = [line for line in Path('/proc/self/maps').read_text().splitlines() if str(library) in line]
    if not mapped or any(line.endswith(' (deleted)') for line in mapped) or sha(library.read_bytes()) != LIBRARY_SHA:
        raise ValueError('Actual Unicorn library mapping differs')
    exe = (root / 'LEZAC.EXE').read_bytes()
    if sha(exe) != EXE_SHA:
        raise ValueError('Original executable differs')
    code = exe[0x95f8:0x9647]
    out = out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only output directory')
    out.mkdir()
    output = bytearray(b'LZVCOPY1' + struct.pack('<I', len(PROFILES)))
    cases = []
    try:
        for index, profile in enumerate(PROFILES):
            pitch, height, fine_x, fine_y, source, destination, flags = profile
            initial = bytearray(1048576)
            initial[0x50000:0x60002] = bytes((i * 17 + (i >> 6) * 3 + (i >> 16) * 97 + index + 1) & 255 for i in range(65538))
            initial[0xa0000:0xb0002] = bytes((i * 37 + (i >> 8) * 11 + (i >> 16) * 109 + (index + 1) * 13) & 255 for i in range(65538))
            initial[0x18e88:0x18ed7] = code
            for offset, value in ((0xc1ec,pitch),(0xc1ee,height),(0xc20a,fine_x),(0xc20c,fine_y),
                    (0xc214,source),(0xc1f4,destination),(0xc206,320-pitch),(0xc212,0x5000)):
                struct.pack_into('<H', initial, 0x1aa20 + offset, value)
            return_ip = 0x7a35 if index % 2 == 0 else 0x7a57
            struct.pack_into('<HH', initial, 0x73fe4, return_ip, 0x1000)
            values = (0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x3ffe,
                0x18ac,0x1aa2,0x40,0x7000,0x3fe4,0x3c8,flags)
            endpoints = []
            word_writes = [0]
            for observed in (True, False):
                engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
                engine.mem_map(0, len(initial))
                engine.mem_write(0, bytes(initial))
                for reg, value in zip(REGS, values):
                    engine.reg_write(reg, value)
                def external(*unused):
                    raise ValueError('Unexpected interrupt or port I/O')
                def write(uc, access, address, size, value, user):
                    if address == 0x73fe2 and size == 2:
                        return
                    if size != 2 or not 0xa0000 <= address <= 0xaffff:
                        raise ValueError('Original wrote outside controlled stack/VGA')
                    word_writes[0] += 1
                engine.hook_add(unicorn.UC_HOOK_INTR, external)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
                engine.emu_start(0x18e88, 0x10000 + return_ip, count=1000000)
                registers = tuple(engine.reg_read(reg) for reg in REGS)
                final = bytes(engine.mem_read(0, len(initial)))
                if registers[7] != 0x1000 or registers[12] != return_ip or final[0x18e88:0x18ed7] != code:
                    raise ValueError('Original endpoint/code differs')
                endpoints.append((registers, final))
            if endpoints[0] != endpoints[1] or word_writes[0] != (height - 8) * ((pitch - 8) // 2):
                raise ValueError('Observer control or original write count differs')
            registers, final = endpoints[0]
            output.extend(struct.pack('<9H13HI13HII', index,pitch,height,fine_x,fine_y,source,destination,flags,
                return_ip,*values,*registers,word_writes[0]))
            output.extend(final[0x73fe2:0x73fe8])
            output.extend(final[0xa0000:0xb0002])
            cases.append(dict(index=index,profile=list(profile),word_writes=word_writes[0],
                full_memory_observer_control=True,full_endpoint_registers=True))
        raw = bytes(output)
        compressed = gzip.compress(raw, mtime=0)
        (out / 'oracle.bin.gz').write_bytes(compressed)
        manifest = dict(schema='lezac-controlled-view-copy-v1',executable_sha256=EXE_SHA,
            instruction_file_range=[0x95f8,0x9647],instruction_sha256=sha(code),cases=cases,
            projection_bytes=len(raw),projection_sha256=sha(raw),compressed_bytes=len(compressed),
            compressed_sha256=sha(compressed),producer_sha256=sha(Path(__file__).read_bytes()),
            unicorn_version=unicorn.__version__,unicorn_library_sha256=sha(library.read_bytes()),
            actual_library_mapping_verified=True,controlled_initial_memory=True,
            natural_capture=False,interrupts=False,port_io=False,raw_memory_published=False,
            full_frame_claim=False,work_clock_claim=False)
        (out / 'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(cases),bytes=len(raw),sha256=sha(raw))))
    except Exception as error:
        (out / 'failed.json').write_text(json.dumps(dict(status='failed',error=str(error)))+'\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    generate(args.repo.resolve(),args.out)
