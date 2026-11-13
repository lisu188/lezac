"""Reproduce the controlled original flame oracle with optional Unicorn 2.1.4.

No DOS, timer, audio device, instruction patching or call stubs are involved.
The output must be a new file; this tool never rewrites the committed fixture.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import struct

from check_flame_contact_word import GROUP_BYTES, ROOT, check_records, fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    data = fixture()
    output = args.out.resolve()
    if output.exists():
        raise ValueError('refusing to replace an existing original capture')
    if shutil.disk_usage(output.parent).free <= data['cases'] * 8 + 64 * 1024**2:
        raise ValueError('insufficient space for the controlled instruction records')

    from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, __version__
    from unicorn.x86_const import (UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS,
                                  UC_X86_REG_EFLAGS, UC_X86_REG_IP, UC_X86_REG_SP,
                                  UC_X86_REG_SS)

    raw = (ROOT / 'LEZAC.EXE').read_bytes()
    header = struct.unpack_from('<14H', raw)
    if header[0] != 0x5A4D or header[3] != 468 or header[4] * 16 != 0x770:
        raise ValueError('original MZ relocation header differs')
    image = bytearray(raw[header[4] * 16:])
    code_segment, data_segment, stack_segment = 0x1000, 0x1AA2, 0x8000
    for index in range(header[3]):
        offset, segment = struct.unpack_from('<HH', raw, header[12] + index * 4)
        address = segment * 16 + offset
        value = struct.unpack_from('<H', image, address)[0]
        struct.pack_into('<H', image, address, (value + code_segment) & 0xFFFF)
    if hashlib.sha256(image).hexdigest() != data['relocated_image_sha256']:
        raise ValueError('original relocated image differs')

    cpu = Uc(UC_ARCH_X86, UC_MODE_16)
    cpu.mem_map(0, 1024 * 1024)
    code_base, data_base = code_segment * 16, data_segment * 16
    locals_base = stack_segment * 16 + 0xF000
    cpu.mem_write(code_base, bytes(image))
    start, end = data['instruction_start'], data['instruction_end_exclusive']
    if bytes(cpu.mem_read(code_base + start, end - start)).hex() != data['instruction_hex']:
        raise ValueError('loaded original arithmetic window differs')
    for register, value in ((UC_X86_REG_CS, code_segment), (UC_X86_REG_DS, data_segment),
                            (UC_X86_REG_SS, stack_segment), (UC_X86_REG_BP, 0xF000),
                            (UC_X86_REG_SP, 0xEFF0), (UC_X86_REG_EFLAGS, 0x202)):
        cpu.reg_write(register, value)
    cpu.mem_write(locals_base - 2, struct.pack('<H', 1))

    digest = hashlib.sha256()
    with output.open('xb') as stream:
        for group in data['groups']:
            mass, weight = group['mass'], group['weight']
            cpu.mem_write(data_base + 0x78D6, bytes((mass,)))
            records = bytearray()
            for own_raw in range(256):
                own_y = (-own_raw) & 255
                cpu.mem_write(data_base + 0x78D2, bytes((own_raw, 0, own_y)))
                for incoming_raw in range(256):
                    incoming_y = (-incoming_raw) & 255
                    cpu.mem_write(locals_base - 0x11, bytes((weight, incoming_y, incoming_raw)))
                    cpu.emu_start(code_base + start, code_base + end, count=100)
                    if cpu.reg_read(UC_X86_REG_IP) != end:
                        raise ValueError('original arithmetic did not reach its end boundary')
                    result_y, result_x = cpu.mem_read(locals_base - 0x10, 2)
                    records.extend((own_raw, own_y, incoming_raw, incoming_y,
                                    mass, weight, result_x, result_y))
            if len(records) != GROUP_BYTES or hashlib.sha256(records).hexdigest() != group['records_sha256']:
                raise ValueError(f'original capture differs for mass={mass} weight={weight}')
            stream.write(records)
            digest.update(records)
            print(f'original_flame_group=ok mass={mass} weight={weight} cases=65536', flush=True)
    if digest.hexdigest() != data['records_sha256']:
        raise ValueError('original aggregate capture differs')
    check_records(output.read_bytes(), data)
    print(f'original_flame_capture=ok cases=1376256 groups=21 unicorn={__version__} '
          'instruction_patches=0 stubbed_calls=0 compiled_cpp=0 natural_gameplay=0')


if __name__ == '__main__':
    main()
