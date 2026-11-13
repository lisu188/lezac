"""Execute the complete original constructor for every signed input on each axis."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct

import unicorn
from unicorn.x86_const import (
    UC_X86_INS_IN, UC_X86_INS_OUT, UC_X86_REG_CS, UC_X86_REG_DS,
    UC_X86_REG_EFLAGS, UC_X86_REG_IP, UC_X86_REG_SP, UC_X86_REG_SS,
)


EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
DESCRIPTOR_SHA = '8604621c87c91e23bbe02f66cedfb312fd95b2c5a5cc429b0eca37872345f55e'
CONSTRUCTOR_SHA = '189d417a54fa3c7eacec479279164257d6f6f6a8277b84927d08d0fb6324411c'
OUTPUT_SHA = '8d1cf2ab4126b1f9f67604ab763541d037aab549b6ba5aa2c7e91fe588890fe8'


def capture(root):
    raw = (root / 'LEZAC.EXE').read_bytes()
    native = (root / 'tests/fixtures/fracture_actor_original.txt').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXE_SHA
    assert hashlib.sha256(native).hexdigest() == DESCRIPTOR_SHA
    assert hashlib.sha256(raw[0x770 + 0x2f9f:0x770 + 0x30a3]).hexdigest() == CONSTRUCTOR_SHA
    assert unicorn.__version__ == '2.1.4'
    header = struct.unpack_from('<14H', raw)
    assert header[3] == 468 and header[4] * 16 == 0x770
    image = bytearray(raw[0x770:])
    for index in range(header[3]):
        offset, segment = struct.unpack_from('<HH', raw, header[12] + index * 4)
        address = segment * 16 + offset
        struct.pack_into('<H', image, address,
                         (struct.unpack_from('<H', image, address)[0] + 0x1000) & 65535)
    cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
    cpu.mem_map(0, 1024**2)
    cpu.mem_write(0x10000, bytes(image))
    descriptors = bytes.fromhex(next(line.split('=', 1)[1] for line in native.decode('ascii').splitlines()
                                    if line.startswith('sprites descriptors=')))
    assert len(descriptors) == 92 * 4
    data = 0x1aa20
    cpu.mem_write(data + 0xc322, descriptors)

    def unexpected(*args):
        raise RuntimeError('unexpected constructor hardware I/O or interrupt')

    cpu.hook_add(unicorn.UC_HOOK_INTR, unexpected)
    cpu.hook_add(unicorn.UC_HOOK_INSN, unexpected, None, 1, 0, UC_X86_INS_IN)
    cpu.hook_add(unicorn.UC_HOOK_INSN, unexpected, None, 1, 0, UC_X86_INS_OUT)
    output = bytearray()
    changed = 0
    for axis in range(2):
        for word in range(65536):
            vx, vy = (word, 0) if axis == 0 else (0, word)
            slot = data + 0x1bae + 38
            cpu.mem_write(slot, bytes(38))
            cpu.mem_write(data + 0x208d, b'\x00')
            cpu.mem_write(data + 0xc496, b'\x03')
            cpu.mem_write(data + 0x2072, b'\xff\xff')
            for register, value in (
                (UC_X86_REG_CS, 0x1000), (UC_X86_REG_DS, 0x1aa2),
                (UC_X86_REG_SS, 0x8000), (UC_X86_REG_SP, 0xff00), (UC_X86_REG_EFLAGS, 0x202),
            ):
                cpu.reg_write(register, value)
            cpu.mem_write(0x8ff00, struct.pack('<9H', 0xff00, 5, 8, 0x0b, 74, vy, vx, 160, 184))
            cpu.emu_start(0x12f9f, 0x1ff00, count=2000)
            assert (cpu.reg_read(UC_X86_REG_CS), cpu.reg_read(UC_X86_REG_IP),
                    cpu.reg_read(UC_X86_REG_SP)) == (0x1000, 0xff00, 0xff12)
            assert bytes(cpu.mem_read(data + 0x208d, 1)) == b'\x01'
            assert bytes(cpu.mem_read(data + 0x2072, 2)) == b'\x01\x00'
            actual = bytes(cpu.mem_read(slot + 6, 4))
            value = struct.unpack_from('<h', actual, axis * 2)[0]
            changed += value != (word if word < 32768 else word - 65536)
            output.extend(actual)
    assert len(output) == 524288 and changed == 122880
    assert hashlib.sha256(output).hexdigest() == OUTPUT_SHA
    return bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    binary = args.out / 'actor_constructor_velocity_original.bin.gz'
    metadata = args.out / 'actor_constructor_velocity_original.json'
    if binary.exists() or metadata.exists():
        raise RuntimeError('refusing to overwrite constructor evidence')
    raw = capture(args.root.resolve())
    compressed = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=compressed, mtime=0) as archive:
        archive.write(raw)
    report = dict(schema='lezac.original-actor-constructor-velocity.v1',
        original_exe_sha256=EXE_SHA, constructor_anchor='1000:2F9F..30A3',
        constructor_bytes_sha256=CONSTRUCTOR_SHA, native_descriptor_fixture_sha256=DESCRIPTOR_SHA,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), executor='Unicorn 2.1.4',
        original_instructions_patched=False, original_calls_stubbed=False, hardware_io_permitted=False,
        complete_constructor_executed=True, return_boundaries_verified=True,
        exhaustive_axis_cases=131072, signed_inputs_per_axis=65536, changed_velocity_cases=122880,
        ordering='axis X then Y; each axis uses WORD inputs 0..65535; other axis zero',
        record_format='two little-endian signed velocity WORDs from actor offsets +6 and +8',
        output_bytes=len(raw), outputs_sha256=hashlib.sha256(raw).hexdigest(),
        compressed_sha256=hashlib.sha256(compressed.getvalue()).hexdigest(),
        controlled_actor_kind=11, controlled_sprite=74, controlled_mode=5, controlled_timer=8,
        clean_first_slot=True, visual_cursor=3, natural_reachability_proven=False,
        all_actor_fields_compared=False, visual_parity_claim=False, sound_parity_claim=False,
        whole_game_complete=False)
    args.out.mkdir(parents=True, exist_ok=True)
    binary.write_bytes(compressed.getvalue())
    metadata.write_bytes((json.dumps(report, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    print(json.dumps(dict(binary=str(binary), metadata=str(metadata), cases=131072,
        compressed_sha256=report['compressed_sha256'],
        metadata_sha256=hashlib.sha256(metadata.read_bytes()).hexdigest())))


if __name__ == '__main__':
    main()
