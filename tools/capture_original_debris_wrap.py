"""Optional Unicorn 2.1.4 capture of the original debris WORD-sum boundary."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import sys

import capture_original_debris_update as legacy
import check_original_debris_update as frozen

TICKS = (*range(6), *range(65327, 65338), *range(65530, 65536))
SLOTS = (*range(200, 208), 255, 256, 1599, 1600)
sha = lambda raw: hashlib.sha256(raw).hexdigest()


class OriginalUpdater:
    def __init__(self, raw):
        import unicorn
        from unicorn import x86_const as x86
        if unicorn.__version__ != '2.1.4' or len(raw) != 52384 or sha(raw) != legacy.EXE_SHA:
            raise ValueError('Original executable or Unicorn version differs')
        self.x86 = x86
        self.cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
        header = struct.unpack_from('<14H', raw)
        if header[3] != 468 or header[4] * 16 != 0x770:
            raise ValueError('Original MZ layout differs')
        image = bytearray(raw[0x770:])
        for index in range(header[3]):
            offset, segment = struct.unpack_from('<HH', raw, header[12] + 4 * index)
            address = 16 * segment + offset
            struct.pack_into('<H', image, address,
                (struct.unpack_from('<H', image, address)[0] + 0x1000) & 65535)
        self.cpu.mem_map(0, 1024**2)
        self.cpu.mem_write(0x10000, bytes(image))
        self.code = bytes(image[:0xaa20])
        self.initial = bytes(self.cpu.mem_read(0x1aa20, 65536))
        self.steps = 0

        def observe(cpu, address, size, data):
            self.steps += 1

        def unexpected(*args):
            raise RuntimeError('Unexpected original interrupt or hardware I/O')

        self.cpu.hook_add(unicorn.UC_HOOK_CODE, observe)
        self.cpu.hook_add(unicorn.UC_HOOK_INTR, unexpected)
        for instruction in (x86.UC_X86_INS_IN, x86.UC_X86_INS_OUT):
            self.cpu.hook_add(unicorn.UC_HOOK_INSN, unexpected, None, 1, 0, instruction)

    def execute(self, incoming):
        width, height, tick, rng, fragments, collapses = struct.unpack_from('<HHHIHH', incoming)
        cells = width * height
        if len(incoming) != 14 + cells * 3 + fragments * 11 + collapses * 15:
            raise ValueError('Original request extent differs')
        cpu, x86, data = self.cpu, self.x86, 0x1aa20
        cpu.mem_write(data, self.initial)
        cpu.mem_write(data + 0x1afa, bytes(2))
        cpu.mem_write(data + 0x1afe, struct.pack('<I', rng))
        cpu.mem_write(data + 0x2076, struct.pack('<6H', 0, 0, 0, 0x209e, 199 + fragments, collapses))
        cpu.mem_write(data + 0x2093, bytes(0x6611 - 0x2093))
        cpu.mem_write(data + 0x6620, bytes(250 * 15))
        start = 14 + cells * 3
        cpu.mem_write(data + 0x2093 + 2200, incoming[start:start + fragments * 11])
        if collapses:
            cpu.mem_write(data + 0x6620, incoming[start + fragments * 11:])
        cpu.mem_write(data + 0x6612, struct.pack('<HH', 0, 0x5000))
        cpu.mem_write(data + 0xc1e0, struct.pack('<HH', 0, 0x4000))
        cpu.mem_write(data + 0xc1fe, struct.pack('<H', 0x4000))
        cpu.mem_write(data + 0xc204, struct.pack('<H', width))
        cpu.mem_write(data + 0x78c2, struct.pack('<H', tick))
        cpu.mem_write(0x40000, bytes(65536))
        cpu.mem_write(0x50000, bytes(65536))
        cpu.mem_write(0x40000, incoming[14:14 + cells])
        cpu.mem_write(0x50000, incoming[14 + cells:start])
        for register, value in ((x86.UC_X86_REG_CS, 0x1000), (x86.UC_X86_REG_DS, 0x1aa2),
                (x86.UC_X86_REG_SS, 0x8000), (x86.UC_X86_REG_SP, 0xff00), (x86.UC_X86_REG_EFLAGS, 0x202)):
            cpu.reg_write(register, value)
        cpu.mem_write(0x8ff00, struct.pack('<H', 0xff00))
        self.steps = 0
        cpu.emu_start(0x145fa, 0x1ff00, count=1000000)
        terminal = tuple(cpu.reg_read(register) for register in
            (x86.UC_X86_REG_CS, x86.UC_X86_REG_IP, x86.UC_X86_REG_SP))
        if terminal != (0x1000, 0xff00, 0xff02) or bytes(cpu.mem_read(0x10000, len(self.code))) != self.code:
            raise ValueError('Original return boundary or code preservation differs')
        bound, count = struct.unpack('<HH', bytes(cpu.mem_read(data + 0x207e, 4)))
        if not 199 <= bound <= 1600 or count > 250:
            raise ValueError('Original live record bounds differ')
        result = bytes(cpu.mem_read(data + 0x1afe, 4)) + struct.pack('<HH', bound - 199, count)
        result += bytes(cpu.mem_read(0x40000, cells)) + bytes(cpu.mem_read(0x50000, cells * 2))
        result += bytes(cpu.mem_read(data + 0x2093 + 2200, (bound - 199) * 11))
        if count:
            result += bytes(cpu.mem_read(data + 0x6620, count * 15))
        return result, self.steps


def request(tick, slot):
    tiles, words = legacy.room()
    tiles[20], words[20] = 0x60, 0xc002
    tiles[136], words[136], tiles[152] = 0x70, 0xc001, 1
    records = [legacy.debris(20, 0xc002)] * (slot - 200)
    records.append(legacy.debris(136, 0xc001, vy=64, glyph=0x70))
    return (struct.pack('<HHHIHH', 16, 16, tick, 0x12345678, len(records), 0) +
        bytes(tiles) + struct.pack('<256H', *words) + b''.join(records))


def validate_destinations(output, metadata):
    if (output.resolve() == metadata.resolve() or output.exists() or metadata.exists() or
            output.is_symlink() or metadata.is_symlink()):
        raise ValueError('Use distinct, fresh capture destinations')
    if not output.parent.is_dir() or not metadata.parent.is_dir():
        raise ValueError('Capture destination parents must exist')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unicorn-path', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    args = parser.parse_args()
    if args.unicorn_path:
        sys.path.insert(0, str(args.unicorn_path))
    validate_destinations(args.out, args.metadata)
    original = (frozen.ROOT / 'LEZAC.EXE').read_bytes()
    prior = list(frozen.records(frozen.metadata()))
    executor = OriginalUpdater(original)
    for incoming, expected in prior[:18]:
        if executor.execute(incoming)[0] != expected:
            raise ValueError('Original executor failed a frozen native cross-check')
    cases, maximum, differences = [], 0, 0
    ih, oh = hashlib.sha256(), hashlib.sha256()
    for tick in TICKS:
        for slot in SLOTS:
            incoming = request(tick, slot)
            result, steps = executor.execute(incoming)
            expected_glyph = 0x76 if ((tick + slot) & 65535) % 6 > 2 else 0x70
            if result[8 + 3 * 256 + (slot - 200) * 11 + 9] != expected_glyph:
                raise ValueError('Executed original differs from its WORD predicate')
            differences += ((tick + slot) % 6 > 2) != (((tick + slot) & 65535) % 6 > 2)
            cases.append((incoming, result))
            ih.update(incoming)
            oh.update(result)
            maximum = max(maximum, steps)
    raw = b'LZDF0001' + struct.pack('<I', len(cases)) + b''.join(
        struct.pack('<II', len(incoming), len(result)) + incoming + result for incoming, result in cases)
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb', filename='', mtime=0) as destination:
        destination.write(raw)
    compressed = buffer.getvalue()
    metadata = dict(schema='lezac.original-debris-wrap.v1', cases=len(cases), ticks=TICKS, slots=SLOTS,
        executor='Unicorn 2.1.4', native_crosschecks=18, maximum_instructions=maximum,
        wide_sum_disagreements=differences, original_exe_bytes=len(original), original_exe_sha256=sha(original),
        generator_sha256=sha(Path(__file__).read_bytes()),
        legacy_metadata_sha256=sha(frozen.META.read_bytes()),
        instruction_offset=0x4afa, instruction_hex=original[0x770 + 0x4afa:0x770 + 0x4b0d].hex(),
        relocated_code_bytes=len(executor.code), relocated_code_sha256=sha(executor.code),
        input_sha256=ih.hexdigest(), output_sha256=oh.hexdigest(), fixture_sha256=sha(compressed),
        decoded_bytes=len(raw), decoded_sha256=sha(raw), original_calls_stubbed=False, original_instructions_patched=False,
        code_preserved_after_every_case=True, original_return_boundaries_verified=True,
        full_guest_ram_exports=0, natural_gameplay=False, sound_state_compared=False,
        spark_count_controlled_to_zero=True, whole_game_fidelity_claim=False)
    with args.out.open('xb') as destination:
        destination.write(compressed)
    with args.metadata.open('x', encoding='ascii') as destination:
        json.dump(metadata, destination, indent=2, sort_keys=True)
        destination.write('\n')
    print(json.dumps(dict(cases=len(cases), native_crosschecks=18,
        wide_sum_disagreements=differences, maximum_instructions=maximum, fixture_bytes=len(compressed))))


if __name__ == '__main__':
    main()
