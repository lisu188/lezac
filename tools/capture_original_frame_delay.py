"""Optional Unicorn 2.1.4 oracle for original counter and feedback blocks."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def capture(root, out):
    import unicorn
    from unicorn.x86_const import (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_SS,
        UC_X86_REG_SP, UC_X86_REG_IP, UC_X86_REG_EFLAGS)
    assert unicorn.__version__ == '2.1.4'
    raw = (root / 'LEZAC.EXE').read_bytes()
    sha = lambda data: hashlib.sha256(data).hexdigest()
    assert sha(raw) == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    header = struct.unpack_from('<14H', raw)
    assert header[3] == 468 and header[4] * 16 == 0x770
    image = bytearray(raw[0x770:])
    for index in range(header[3]):
        offset, segment = struct.unpack_from('<HH', raw, header[12] + index * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
    cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
    cpu.mem_map(0, 1024**2)
    cpu.mem_write(0x10000, bytes(image))
    for register, value in [(UC_X86_REG_CS, 0x1000), (UC_X86_REG_DS, 0x1aa2),
                            (UC_X86_REG_SS, 0x8000), (UC_X86_REG_SP, 0xfe00), (UC_X86_REG_EFLAGS, 0x202)]:
        cpu.reg_write(register, value)
    context = cpu.context_save()
    data = 0x1aa20
    def stop_clock(cpu, address, size, user):
        cpu.emu_stop()
    def write(cpu, access, address, size, value, user):
        if address < 0x10000 + 43552 and address + size > 0x10000:
            raise ValueError('Original code write is forbidden')
    cpu.hook_add(unicorn.UC_HOOK_CODE, stop_clock, None, 0x17919, 0x17919)
    cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
    bits = bytearray(8192)
    for prior in range(65536):
        cpu.context_restore(context)
        cpu.mem_write(data + 0x78c2, struct.pack('<H', prior))
        cpu.emu_start(0x17903, 0x179df, count=100)
        ip = cpu.reg_read(UC_X86_REG_IP)
        assert ip in (0x7919, 0x79df)
        assert struct.unpack('<H', cpu.mem_read(data + 0x78c2, 2))[0] == (prior + 1) & 65535
        if ip == 0x7919:
            bits[prior // 8] |= 1 << (prior % 8)

    def feedback(elapsed, delay, step):
        cpu.context_restore(context)
        for offset, value in [(0x2074, elapsed), (0x78cc, delay), (0x78ca, step)]:
            cpu.mem_write(data + offset, struct.pack('<H', value))
        for offset, value in [(0x79a4, 1), (0x79a8, 2), (0x79a9, 3),
                              (0x79aa, 4), (0x79ab, 5), (0x79ac, 6)]:
            cpu.mem_write(data + offset, bytes([value]))
        cpu.emu_start(0x1799a, 0x179df, count=100)
        assert cpu.reg_read(UC_X86_REG_IP) == 0x79df and cpu.reg_read(UC_X86_REG_SP) == 0xfe00
        assert [cpu.mem_read(data + offset, 1)[0] for offset in (0x79a4, 0x79a8, 0x79a9)] == [4, 5, 6]
        return struct.unpack('<H', cpu.mem_read(data + 0x78cc, 2))[0]
    results = b''.join(struct.pack('<H', feedback(elapsed, 16, 2)) for elapsed in range(65536))
    cases = [dict(elapsed=elapsed, delay=delay, step=step, result=feedback(elapsed, delay, step))
             for elapsed in (0, 119, 120, 125, 126, 32767, 32768, 65535)
             for delay in (0, 1, 2, 16, 65534, 65535) for step in (0, 1, 2, 200, 65535)]
    assert bytes(cpu.mem_read(0x10000, 43552)) == image[:43552]
    manifest = dict(schema=1, executable_sha256=sha(raw), producer_sha256=sha(Path(__file__).read_bytes()),
        unicorn=unicorn.__version__, counter_inputs=65536, elapsed_inputs=65536, feedback_cases=cases,
        counter_bits_sha256=sha(bits), delay_words_sha256=sha(results),
        counter_block_sha256=sha(image[0x7903:0x7919]), feedback_block_sha256=sha(image[0x799a:0x79df]),
        original_code_bytes_verified=43552, original_code_writes=0, instruction_patches=0,
        original_calls_stubbed=False, scope='two bounded instruction blocks, not a complete game loop',
        natural_clock_claim=False, synchronized_frame_parity=False, whole_game_parity=False)
    for name, contents in [('counter-bits.bin', bits), ('delay-words.bin', results),
                           ('oracle.json', (json.dumps(manifest, indent=2) + '\n').encode())]:
        (out / name).write_bytes(contents)
    print('original_frame_delay_capture=ok counter_inputs=65536 elapsed_inputs=65536 feedback_cases=240')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir()
    try:
        capture(args.root, args.out)
    except BaseException as error:
        (args.out / 'failure.json').write_text(json.dumps(dict(error=repr(error))) + '\n')
        raise
