"""Execute original pickup allocation, RNG and unconditional animation initialization."""
import argparse
import gzip
import hashlib
import io
import itertools
import json
from pathlib import Path
import struct

import unicorn
from unicorn.x86_const import (
    UC_X86_INS_IN, UC_X86_INS_OUT, UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS,
    UC_X86_REG_EFLAGS, UC_X86_REG_IP, UC_X86_REG_SP, UC_X86_REG_SS,
)

EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
NATIVE_SHA = '8604621c87c91e23bbe02f66cedfb312fd95b2c5a5cc429b0eca37872345f55e'
OUTPUT_SHA = 'a6e62f1397c08c90a4b1f88d45a66add2e883f5b8bc6ce8856c73cc5a55e09d1'
BOUNDARIES = ((0, 0), (1, 0), (29, 0), (29, 13), (29, 14), (30, 0), (30, 13), (30, 14))
PATTERNS = (bytes((71, 69, 79, 1, 2, 1, 1)), bytes((79, 69, 79, 250, 2, 2, 255)),
            bytes((0, 0, 0, 0, 0, 0, 1)))


def capture(root):
    raw = (root / 'LEZAC.EXE').read_bytes()
    native = (root / 'tests/fixtures/fracture_actor_original.txt').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXE_SHA and hashlib.sha256(native).hexdigest() == NATIVE_SHA
    assert unicorn.__version__ == '2.1.4'
    descriptors = bytes.fromhex(next(line.split('=', 1)[1] for line in native.decode().splitlines()
                                    if line.startswith('sprites descriptors=')))
    assert len(descriptors) == 368
    header = struct.unpack_from('<14H', raw)
    assert header[3] == 468 and header[4] * 16 == 0x770
    image = bytearray(raw[0x770:])
    for index in range(header[3]):
        offset, segment = struct.unpack_from('<HH', raw, header[12] + 4 * index)
        address = 16 * segment + offset
        struct.pack_into('<H', image, address,
                         (struct.unpack_from('<H', image, address)[0] + 0x1000) & 65535)
    cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
    cpu.mem_map(0, 1024**2)
    cpu.mem_write(0x10000, bytes(image))
    data = 0x1aa20
    initial = bytes(cpu.mem_read(data, 65536))
    entries = []

    def unexpected(*args):
        raise RuntimeError('unexpected original interrupt or hardware I/O')

    def observe(uc, address, size, user):
        if address in (0x12f9f, 0x106ab, 0x1a5a8): entries.append(address)

    cpu.hook_add(unicorn.UC_HOOK_INTR, unexpected)
    cpu.hook_add(unicorn.UC_HOOK_INSN, unexpected, None, 1, 0, UC_X86_INS_IN)
    cpu.hook_add(unicorn.UC_HOOK_INSN, unexpected, None, 1, 0, UC_X86_INS_OUT)
    cpu.hook_add(unicorn.UC_HOOK_CODE, observe)
    output, rows = bytearray(), []
    for count, pickups in BOUNDARIES:
        for category, pattern, seed, sprite in itertools.product(range(5), range(3),
                                                               (0x12345678, 0xffffffff), (80, 90)):
            cpu.mem_write(data, initial)
            cpu.mem_write(data + 0x1bae, bytes(31 * 38))
            cpu.mem_write(data + 0xc21e, bytes(33 * 8))
            cpu.mem_write(data + 0xc322, descriptors)
            cpu.mem_write(data + 0xc496, bytes((count + 3,)))
            cpu.mem_write(data + 0x208d, bytes((count, pickups)))
            cpu.mem_write(data + 0x2072, struct.pack('<H', sprite))
            cpu.mem_write(data + 0x1afe, struct.pack('<I', seed))
            cpu.mem_write(data + 0x78d2, bytes((254, 0, 254)))
            for index in range(count):
                actor = bytearray(38)
                actor[0] = 0x0a if index < pickups else 0x0b
                actor[1], actor[2], actor[21] = index + 3, 200, 5
                actor[22:29] = PATTERNS[pattern]
                if index == count - 1:
                    actor[0] = (11, 11, 1, 19, 13)[category]
                    actor[21] = (5, 5, 2, 2, 2)[category]
                    if category == 4: actor[22:29] = PATTERNS[2]
                cpu.mem_write(data + 0x1bae + (index + 1) * 38, bytes(actor))
            before = bytes(cpu.mem_read(data + 0x1bae + 38, count * 38))
            for register, value in ((UC_X86_REG_CS, 0x1000), (UC_X86_REG_DS, 0x1aa2),
                                    (UC_X86_REG_SS, 0x8000), (UC_X86_REG_BP, 0xff00),
                                    (UC_X86_REG_SP, 0xfe00), (UC_X86_REG_EFLAGS, 0x202)):
                cpu.reg_write(register, value)
            cpu.mem_write(0x8ff00 - 0x2c, struct.pack('<H', 184))
            cpu.mem_write(0x8ff00 - 0x2e, struct.pack('<H', 160))
            entries.clear()
            cpu.emu_start(0x16d81, 0x16e01, count=10000)
            assert (cpu.reg_read(UC_X86_REG_CS), cpu.reg_read(UC_X86_REG_IP),
                    cpu.reg_read(UC_X86_REG_SP), cpu.reg_read(UC_X86_REG_BP)) == (0x1000, 0x6e01, 0xfe00, 0xff00)
            after_count, after_pickups = bytes(cpu.mem_read(data + 0x208d, 2))
            attempted, admitted = pickups < 14, pickups < 14 and count < 30
            assert after_count == count + int(admitted) and after_pickups == pickups + int(admitted)
            assert entries == ([0x1a5a8, 0x12f9f, 0x106ab] if attempted else [])
            after = bytes(cpu.mem_read(data + 0x1bae + 38, after_count * 38))
            expected_existing = bytearray(before)
            if attempted and count == 30: expected_existing[-38 + 22:-38 + 29] = PATTERNS[2]
            assert after[:len(before)] == expected_existing
            rng = bytes(cpu.mem_read(data + 0x1afe, 4))
            if not attempted: assert rng == struct.pack('<I', seed)
            animations = b''.join(after[index * 38 + 22:index * 38 + 29] for index in range(after_count))
            record = bytes((after_count, after_pickups)) + rng + animations
            output.extend(record)
            rows.append(dict(count=count, pickups=pickups, category=category, pattern=pattern,
                             seed=seed, sprite=sprite, output_bytes=len(record)))
    assert len(rows) == 480 and hashlib.sha256(output).hexdigest() == OUTPUT_SHA
    return bytes(output), rows, raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    binary = args.out / 'pickup_post_init_original.bin.gz'
    metadata = args.out / 'pickup_post_init_original.json'
    if binary.exists() or metadata.exists(): raise RuntimeError('refusing to overwrite original evidence')
    output, rows, raw = capture(args.root.resolve())
    compressed = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=compressed, mtime=0) as archive: archive.write(output)
    report = dict(schema='lezac.original-pickup-post-init.v1', cases=480, original_exe_sha256=EXE_SHA,
        native_descriptor_fixture_sha256=NATIVE_SHA, generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        executor='Unicorn 2.1.4', entry_anchor='1000:6D81', exit_anchor='1000:6E01',
        entry_bytes_sha256=hashlib.sha256(raw[0x770 + 0x6d81:0x770 + 0x6e01]).hexdigest(),
        original_calls_stubbed=False, original_instructions_patched=False, hardware_io_permitted=False,
        complete_random_constructor_and_animation_helpers=True, boundary_registers_verified=True,
        admissions=240, full_pool_attempts=120, pickup_cap_skips=120,
        record_format='count BYTE, pickup-count BYTE, RNG DWORD, seven animation BYTEs per live actor in pool order',
        output_bytes=len(output), outputs_sha256=OUTPUT_SHA, compressed_sha256=hashlib.sha256(compressed.getvalue()).hexdigest(),
        categories=['effect', 'marker', 'monster', 'reward', 'static_bomb'], cases_in_order=rows,
        bomb_animation_implicit_static=True, full_actor_fields_compared=False,
        natural_full_pool_pickup_reachability_proven=False, visual_parity_claim=False,
        sound_parity_claim=False, whole_game_complete=False)
    args.out.mkdir(parents=True, exist_ok=True)
    binary.write_bytes(compressed.getvalue())
    metadata.write_bytes((json.dumps(report, indent=2, sort_keys=True) + '\n').encode())
    print(json.dumps(dict(cases=480, binary=str(binary), metadata=str(metadata),
        compressed_sha256=report['compressed_sha256'], metadata_sha256=hashlib.sha256(metadata.read_bytes()).hexdigest())))


if __name__ == '__main__': main()
