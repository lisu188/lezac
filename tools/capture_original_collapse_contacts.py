"""Capture full original 3BB2/3D46 helper outputs with optional Unicorn 2.1.4."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
VALUES = (-128, -127, -49, -1, 0, 1, 49, 127)
WEIGHTS = (1, 2, 18, 128, 254, 255)


def signed(value):
    return value if value < 128 else value - 256


def flagged_cases():
    for weight in WEIGHTS:
        for own in VALUES:
            yield 'no_contact', own, weight, []
            for kind in ('collapse', 'debris'):
                for target_weight in ((1, 2, 8, 18, 128, 254, 255) if kind == 'collapse' else (1,)):
                    for value in VALUES:
                        yield 'single_' + kind, own, weight, [(kind, target_weight, value)]
    for count in (2, 3, 5, 10, 30):
        for variant in range(64):
            seed = 0x12345678 + variant
            targets = []
            for index in range(count):
                seed = (seed * 0x08088405 + 1) & 0xFFFFFFFF
                kind = 'debris' if (variant + index) % 3 == 0 else 'collapse'
                weight = 1 if kind == 'debris' else WEIGHTS[(seed >> 8) % 6]
                targets.append((kind, weight, signed((seed >> 16) & 255)))
            yield 'mixed_' + str(count), signed(variant * 37 & 255), WEIGHTS[variant % 6], targets


def allocation_targets(profile):
    new = lambda n: [(32 + i, 0x4001 + i, 0x31 + i) for i in range(n)]
    collapse, debris = (2, 0x8001, 0x55), (3, 0xC0C8, 0x55)
    if profile == 'new_single':
        return new(1)
    if profile == 'new_two':
        return new(2)
    if profile == 'new_thirty':
        return new(30)
    if profile == 'existing_then_new':
        return [collapse, debris] + new(2)
    if profile == 'new_then_existing':
        return new(2) + [collapse, debris]
    return [collapse] + new(14) + [debris] + new(28)[14:]


def cases():
    for name, own, weight, targets in flagged_cases():
        for reverse in (0, 1):
            debris, collapse, contacts = [], [], []
            for kind, target_weight, value in targets:
                is_collapse = kind == 'collapse'
                pool = collapse if is_collapse else debris
                slot = len(pool) + (1 if is_collapse else 200)
                key = (0x8000 if is_collapse else 0xC000) + slot
                raw = bytearray([0x55] * (15 if is_collapse else 11))
                struct.pack_into('<H', raw, 4 if is_collapse else 2, key)
                raw[(7 if reverse else 6) if is_collapse else (5 if reverse else 4)] = value & 255
                if is_collapse:
                    raw[14] = target_weight
                pool.append(bytes(raw))
                contacts.append((0, key))
            yield name, own, weight, reverse, debris, collapse, bytes(256), bytes(128), contacts
    for profile in ('new_single', 'new_two', 'new_thirty', 'existing_then_new',
                    'new_then_existing', 'existing_mixed_thirty'):
        targets = allocation_targets(profile)
        for bound in (200, 1598, 1599, 1600):
            debris = []
            for slot in range(200, bound + 1):
                raw = bytearray([0x55] * 11)
                struct.pack_into('<HH', raw, 0, 3, 0xC000 + slot)
                raw[4], raw[5] = 207, 49
                debris.append(bytes(raw))
            raw = bytearray([0x55] * 15)
            struct.pack_into('<H', raw, 4, 0x8001)
            raw[6], raw[7], raw[14] = 127, 128, 254
            words, tiles = bytearray(256), bytearray(128)
            for cell, word, glyph in targets:
                struct.pack_into('<H', words, 2 * cell, word)
                tiles[cell] = glyph
            for weight in WEIGHTS:
                for own in VALUES:
                    for reverse in (0, 1):
                        yield ('allocate_' + profile, own, weight, reverse, debris, [bytes(raw)],
                               bytes(words), bytes(tiles), [(cell, word) for cell, word, _ in targets])


def request(case):
    _, own, weight, reverse, debris, collapse, words, tiles, contacts = case
    return (struct.pack('<bBBHHB', own, weight, reverse, len(debris), len(collapse), len(contacts))
            + b''.join(debris) + b''.join(collapse) + words + tiles
            + b''.join(struct.pack('<HH', cell, word) for cell, word in contacts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path)
    args = parser.parse_args()
    if args.unicorn_path:
        sys.path.insert(0, str(args.unicorn_path))
    import unicorn
    from unicorn.x86_const import (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_SS,
                                  UC_X86_REG_SP, UC_X86_REG_IP, UC_X86_REG_EFLAGS,
                                  UC_X86_INS_IN, UC_X86_INS_OUT)
    if unicorn.__version__ != '2.1.4':
        raise ValueError('capture requires the verified Unicorn 2.1.4 executor')
    raw = args.exe.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXE_SHA:
        raise ValueError('original executable differs')
    header = struct.unpack_from('<14H', raw)
    if header[0] != 0x5A4D or header[3] != 468 or header[4] * 16 != 0x770:
        raise ValueError('original MZ layout differs')
    image = bytearray(raw[0x770:])
    for index in range(header[3]):
        offset, segment = struct.unpack_from('<HH', raw, header[12] + 4 * index)
        address = 16 * segment + offset
        struct.pack_into('<H', image, address, (struct.unpack_from('<H', image, address)[0] + 0x1000) & 65535)
    cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
    cpu.mem_map(0, 1024 * 1024)
    cpu.mem_write(0x10000, bytes(image))
    data = 0x1AA20
    cpu.mem_write(data + 0x1AFA, bytes(2))
    cpu.mem_write(data + 0x6612, struct.pack('<HH', 0, 0x5000))
    cpu.mem_write(data + 0xC1E0, struct.pack('<HH', 0, 0x4000))
    cpu.mem_write(data + 0xC204, struct.pack('<H', 64))
    entries = {0x10000 + offset: name for name, offset in
               [('forward', 0x3BB2), ('reverse', 0x3D46), ('seeder', 0x370E),
                ('forward_matcher', 0x3A7E), ('reverse_matcher', 0x3B18),
                ('stack_check', 0x920 * 16 + 0x4DF), ('long_divider', 0x920 * 16 + 0x945)]}
    counts = {name: 0 for name in entries.values()}
    steps = [0]

    def observe(cpu, address, size, _):
        steps[0] += 1
        if address in entries:
            counts[entries[address]] += 1

    def unexpected(*args):
        raise RuntimeError('unexpected original interrupt or hardware I/O')

    cpu.hook_add(unicorn.UC_HOOK_CODE, observe)
    cpu.hook_add(unicorn.UC_HOOK_INTR, unexpected)
    cpu.hook_add(unicorn.UC_HOOK_INSN, unexpected, None, 1, 0, UC_X86_INS_IN)
    cpu.hook_add(unicorn.UC_HOOK_INSN, unexpected, None, 1, 0, UC_X86_INS_OUT)
    groups, minimum, maximum, total, failures, partial = {}, 200000, 0, 0, 0, 0
    input_hash, output_hash = hashlib.sha256(), hashlib.sha256()
    with args.out.open('xb') as destination, gzip.GzipFile(fileobj=destination, mode='wb', mtime=0, filename='') as fixture:
        fixture.write(b'LZCF0001' + struct.pack('<I', 9184))
        for case in cases():
            name, own, weight, reverse, debris, collapse, words, tiles, contacts = case
            cpu.mem_write(data + 0x2093, bytes(0x6611 - 0x2093))
            cpu.mem_write(data + 0x292B, b''.join(debris) or b'\0')
            cpu.mem_write(data + 0x6620, b''.join(collapse) or b'\0')
            cpu.mem_write(data + 0x2076, struct.pack('<HH', 0, len(contacts)))
            cpu.mem_write(data + 0x207E, struct.pack('<HH', 199 + len(debris), len(collapse)))
            cpu.mem_write(data + 0x78D2, bytes((own & 255,)))
            cpu.mem_write(data + 0x79C8, b'\x7f')
            cpu.mem_write(0x50000, words)
            cpu.mem_write(0x40000, tiles)
            for index, (cell, word) in enumerate(contacts, 1):
                cpu.mem_write(data + 0x655C + 2 * index, struct.pack('<H', word))
                cpu.mem_write(data + 0x6598 + 2 * index, struct.pack('<H', 2 * cell))
                cpu.mem_write(data + 0x65D4 + 2 * index, b'\xcc\xcc')
            for register, value in ((UC_X86_REG_CS, 0x1000), (UC_X86_REG_DS, 0x1AA2),
                                    (UC_X86_REG_SS, 0x8000), (UC_X86_REG_SP, 0xFF00),
                                    (UC_X86_REG_EFLAGS, 0x202)):
                cpu.reg_write(register, value)
            cpu.mem_write(0x8FF00, struct.pack('<HHHH', 0xFF00, 0x78D2, 0x1AA2, weight))
            steps[0] = 0
            cpu.emu_start(0x10000 + (0x3D46 if reverse else 0x3BB2), 0x1FF00, count=200000)
            if (cpu.reg_read(UC_X86_REG_CS), cpu.reg_read(UC_X86_REG_IP), cpu.reg_read(UC_X86_REG_SP)) != (0x1000, 0xFF00, 0xFF08):
                raise RuntimeError('original contact helper did not return normally')
            debris_after, collapse_after = struct.unpack('<HH', cpu.mem_read(data + 0x207E, 4))
            debris_after -= 199
            if not (0 <= debris_after <= 1401 and 0 <= collapse_after <= 30):
                raise ValueError('original returned invalid pool dimensions')
            result = (bytes(cpu.mem_read(data + 0x78D2, 1)) + struct.pack('<HH', debris_after, collapse_after)
                      + bytes(cpu.mem_read(data + 0x292B, 11 * debris_after))
                      + bytes(cpu.mem_read(data + 0x6620, 15 * collapse_after))
                      + bytes(cpu.mem_read(0x50000, 256)) + bytes(cpu.mem_read(0x40000, 128)))
            incoming = request(case)
            fixture.write(struct.pack('<II', len(incoming), len(result)) + incoming + result)
            input_hash.update(incoming)
            output_hash.update(result)
            total += 1
            groups[name] = groups.get(name, 0) + 1
            minimum, maximum = min(minimum, steps[0]), max(maximum, steps[0])
            if name.startswith('allocate_') and cpu.mem_read(data + 0x79C8, 1)[0] == 0:
                failures += 1
                partial += debris_after > len(debris)
    if total != 9184 or failures != 1248 or partial != 672:
        raise ValueError('original capture matrix differs')
    windows = []
    for start, end in ((0x370E, 0x3A53), (0x3A7E, 0x3EDA),
                       (0x920 * 16 + 0x4DF, 0x920 * 16 + 0x512),
                       (0x920 * 16 + 0x945, 0x920 * 16 + 0x9CC)):
        windows.append(dict(start=start, end=end, sha256=hashlib.sha256(raw[0x770 + start:0x770 + end]).hexdigest()))
    metadata = dict(schema='lezac.collapse-contact-original.v1', cases=total, groups=groups,
                    original_exe_sha256=EXE_SHA, mz_relocations=468, instruction_windows=windows,
                    input_sha256=input_hash.hexdigest(), output_sha256=output_hash.hexdigest(),
                    fixture_sha256=hashlib.sha256(args.out.read_bytes()).hexdigest(),
                    generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    executor='Unicorn 2.1.4', instruction_budget=200000,
                    minimum_instructions=minimum, maximum_instructions=maximum,
                    executed_entry_counts=counts, allocation_failure_cases=failures,
                    partial_allocation_failure_cases=partial, original_calls_stubbed=False,
                    original_instructions_patched=False, return_boundaries_verified=True,
                    compiled_cpp_comparison=False, full_collapse_update=False, natural_gameplay=False,
                    audio='dummy', original_fidelity_claim=False, whole_game_complete=False)
    with args.metadata.open('x') as output:
        json.dump(metadata, output, indent=2, sort_keys=True)
        output.write('\n')
    print(json.dumps(dict(cases=total, fixture_bytes=args.out.stat().st_size,
                         output_sha256=output_hash.hexdigest(), compiled_cpp_comparison=False)))


if __name__ == '__main__':
    main()
