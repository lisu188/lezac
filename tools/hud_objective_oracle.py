"""Execute unchanged original objective callees on word-wrap and latch inputs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct

import unicorn
from frame_hud_probe.oracle import REGS, HUD
from check_frame_hud_fixture import read_fixture

PROFILES = [
    (0, 65535, 65534, 50, 0, 1, 0, 0),
    (32767, 65535, 65534, 50, 0, 1, 0, 0),
    (32768, 1, 0, 50, 0, 1, 0, 0),
    (65535, 32768, 32767, 50, 0, 1, 0, 0),
    (100, 0, 1, 100, 0, 1, 0, 0),
    (100, 1, 0, 101, 0, 1, 0, 0),
    (65535, 0, 1, 255, 0, 1, 0, 0),
    (10, 0, 1, 50, 0, 1, 1, 1),
    (0, 1, 0, 0, 1, 0, 0, 0),
    (32767, 32768, 32767, 255, 255, 254, 0, 0),
    (65535, 65535, 65534, 100, 99, 98, 0, 0),
    (1, 65535, 65534, 255, 254, 253, 0, 0),
    (32768, 0, 1, 0, 0, 1, 0, 0),
    (10, 0, 0, 50, 0, 0, 1, 1),
    (0, 0, 0, 0, 0, 0, 0, 0),
    (10, 0, 0, 50, 0, 1, 1, 0),
    (10, 0, 1, 50, 0, 0, 0, 1),
]
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def generate(executable, out):
    assert unicorn.__version__ == '2.1.4'
    out = out.resolve()
    assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
    raw = executable.read_bytes()
    assert sha(raw) == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    mz = struct.unpack_from('<14H', raw)
    image = bytearray(raw[0x770:])
    for i in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', raw, mz[12] + i * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
    font = read_fixture()[2][257:897]
    assert len(font) == 640

    def slices(memory):
        return memory[0x8fdb0:0x8fdb0 + 128] + b''.join(memory[0x1aa20 + at:0x1aa20 + at + size] for at, size in HUD)

    def pixels(memory):
        return bytes(memory[0xa0000 + (166 + block * 16 + row) * 320 + 159 + x]
                     for block in range(2) for row in range(8) for x in range(17))

    output = bytearray(b'LZHUDOR1' + struct.pack('<I', len(PROFILES)))
    cases = []
    for index, profile in enumerate(PROFILES):
        required, current, cached, destruction_required, destruction, previous_destruction, bonus_done, destruction_done = profile
        initial = bytearray(1048576)
        initial[0x10000:0x10000 + len(image)] = image
        for at, size in HUD:
            initial[0x1aa20 + at:0x1aa20 + at + size] = bytes(size)
        for at, value in [(0x2070, 40000), (0x2074, 120), (0x2086, required), (0x2088, current), (0x208a, cached)]:
            struct.pack_into('<H', initial, 0x1aa20 + at, value)
        for at, value in [(0x79b3, destruction_required), (0x79b5, destruction), (0x79b6, previous_destruction),
                          (0x79c5, bonus_done), (0x79c6, destruction_done)]:
            initial[0x1aa20 + at] = value
        initial[0x1aa20 + 0x1aae:0x1aa20 + 0x1ab5] = bytes([4, 8, 12, 99, 16, 20, 24])
        initial[0x1aa20 + 40000:0x1aa20 + 40640] = font
        initial[0x8fdb0:0x8fdb0 + 128] = bytes((index + i) & 255 for i in range(128))
        struct.pack_into('<2H', initial, 0x8fe00, 0x7a00, 0xcb0f)
        for block in range(2):
            for row in range(8):
                for x in range(17):
                    initial[0xa0000 + (166 + block * 16 + row) * 320 + 159 + x] = (index + row + x) & 255
        values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x9abc,
                  0x1000, 0x1aa2, 0xbeef, 0x8000, 0xfe00, 0x3184, 0x202)
        endpoints = []
        for observed in (True, False):
            engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
            engine.mem_map(0, 1048576)
            engine.mem_write(0, bytes(initial))
            for register, value in zip(REGS, values):
                engine.reg_write(register, value)
            def interrupt(*unused):
                raise RuntimeError('Original objective helper unexpectedly called an interrupt')
            engine.hook_add(unicorn.UC_HOOK_INTR, interrupt)
            if observed:
                engine.hook_add(unicorn.UC_HOOK_CODE, lambda *unused: None)
            engine.emu_start(0x13184, 0x17a00, count=100000)
            registers = [engine.reg_read(register) for register in REGS]
            memory = bytes(engine.mem_read(0, 1048576))
            assert registers[12] == 0x7a00 and memory[0x10000:0x10000 + 43552] == image[:43552]
            endpoints.append((registers, memory))
        assert endpoints[0] == endpoints[1]
        registers, memory = endpoints[0]
        output.extend(struct.pack('<B13HI', 0, *values) + slices(initial) + font + pixels(initial))
        output.extend(struct.pack('<13HI', *registers) + slices(memory) + pixels(memory))
        cases.append(dict(index=index, profile=list(profile), full_endpoint_flags=True, full_memory_control_identical=True))
    compressed = gzip.compress(output, mtime=0)
    record = dict(schema='lezac-original-hud-objective-boundaries-v1', cases=cases,
        producer_sha256=sha(Path(__file__).read_bytes()),
        shared_producer_sha256=sha(Path(__file__).with_name('frame_hud_probe').joinpath('oracle.py').read_bytes()),
        font_checker_sha256=sha(Path(__file__).with_name('check_frame_hud_fixture.py').read_bytes()),
        original_executable_sha256=sha(raw), font_sha256=sha(font), projection_sha256=sha(output),
        projection_bytes=len(output), compressed_sha256=sha(compressed), compressed_bytes=len(compressed),
        original_calls_stubbed=0, instruction_patches=0, source_code_bytes_verified=43552,
        raw_memory_published=False, natural_gameplay_claim=False, whole_frame_claim=False, unicorn=unicorn.__version__)
    out.mkdir()
    (out / 'oracle.bin.gz').write_bytes(compressed)
    (out / 'oracle.bin').write_bytes(output)
    (out / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    generate(args.exe, args.out)
