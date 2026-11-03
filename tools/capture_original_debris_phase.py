"""Controlled original clock-block output feeding complete debris-updater calls."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import sys

import capture_original_debris_wrap as wrap
import check_original_debris_update as legacy

TICKS = tuple(sorted(set(wrap.TICKS) | {28, 29, 30, 31, 58, 59, 60}))
SLOTS = wrap.SLOTS
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def capture(unicorn_path):
    if unicorn_path:
        sys.path.insert(0, str(unicorn_path))
    import unicorn
    raw = (legacy.ROOT / 'LEZAC.EXE').read_bytes()
    executor = wrap.OriginalUpdater(raw)
    for incoming, expected in list(legacy.records(legacy.metadata()))[:18]:
        if executor.execute(incoming)[0] != expected:
            raise ValueError('Original debris native cross-check differs')
    active, boundary, counter_steps = [False], [None], [0]

    def observe(cpu, address, size, unused):
        if not active[0]:
            return
        counter_steps[0] += 1
        if address in (0x17919, 0x179df):
            boundary[0] = address
            cpu.emu_stop()

    executor.cpu.hook_add(unicorn.UC_HOOK_CODE, observe)
    cases, increment_paths, max_steps = [], {}, 0
    late_phase_differences = 0
    for before in TICKS:
        cpu, x86 = executor.cpu, executor.x86
        cpu.mem_write(0x1aa20 + 0x78c2, struct.pack('<H', before))
        for register, value in ((x86.UC_X86_REG_CS, 0x1000), (x86.UC_X86_REG_DS, 0x1aa2),
                (x86.UC_X86_REG_SS, 0x8000), (x86.UC_X86_REG_SP, 0xff00), (x86.UC_X86_REG_EFLAGS, 0x202)):
            cpu.reg_write(register, value)
        active[0], boundary[0], counter_steps[0] = True, None, 0
        cpu.emu_start(0x17903, 0x20000, count=100)
        active[0] = False
        if boundary[0] not in (0x17919, 0x179df):
            raise ValueError('Original counter block did not reach a declared boundary')
        after = struct.unpack('<H', bytes(cpu.mem_read(0x1aa20 + 0x78c2, 2)))[0]
        if after != (before + 1) & 65535 or bytes(cpu.mem_read(0x10000, len(executor.code))) != executor.code:
            raise ValueError('Original counter result or code preservation differs')
        increment_paths[hex(boundary[0] - 0x10000)] = increment_paths.get(hex(boundary[0] - 0x10000), 0) + 1
        for slot in SLOTS:
            result, steps = executor.execute(wrap.request(after, slot))
            cases.append((wrap.request(before, slot), struct.pack('<H', after) + result))
            max_steps = max(max_steps, steps)
            late_phase_differences += (((before + slot) & 65535) % 6 > 2) != (((after + slot) & 65535) % 6 > 2)
    decoded = b'LZPF0001' + struct.pack('<I', len(cases)) + b''.join(
        struct.pack('<II', len(incoming), len(expected)) + incoming + expected for incoming, expected in cases)
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb', filename='', mtime=0) as destination:
        destination.write(decoded)
    compressed = buffer.getvalue()
    meta = dict(schema='lezac.original-debris-phase.v1', cases=len(cases), ticks=TICKS, slots=SLOTS,
        original_exe_bytes=len(raw), original_exe_sha256=sha(raw), executor='Unicorn 2.1.4',
        generator_sha256=sha(Path(__file__).read_bytes()), wrap_generator_sha256=sha(Path(wrap.__file__).read_bytes()),
        legacy_metadata_sha256=sha(legacy.META.read_bytes()), fixture_sha256=sha(compressed),
        decoded_bytes=len(decoded), decoded_sha256=sha(decoded), native_crosschecks=18,
        counter_block_hex=raw[0x770 + 0x7903:0x770 + 0x7919].hex(),
        counter_exit_paths=increment_paths, maximum_debris_instructions=max_steps,
        late_counter_phase_counterexamples=late_phase_differences,
        counter_value_transferred_between_separate_controlled_calls=True,
        intervening_original_frame_work_executed=False, original_calls_stubbed=False,
        original_instructions_patched=False, code_preserved_after_every_case=True,
        natural_gameplay=False, full_guest_ram_exports=0, whole_game_fidelity_claim=False,
        sound_state_compared=False, original_return_boundaries_verified=True)
    return compressed, meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unicorn-path', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    args = parser.parse_args()
    wrap.validate_destinations(args.out, args.metadata)
    compressed, meta = capture(args.unicorn_path)
    with args.out.open('xb') as destination:
        destination.write(compressed)
    with args.metadata.open('x', encoding='ascii') as destination:
        json.dump(meta, destination, indent=2, sort_keys=True)
        destination.write('\n')
    print(json.dumps(dict(cases=meta['cases'], fixture_bytes=len(compressed),
        late_phase_counterexamples=meta['late_counter_phase_counterexamples'], counter_paths=meta['counter_exit_paths'])))


if __name__ == '__main__':
    main()
