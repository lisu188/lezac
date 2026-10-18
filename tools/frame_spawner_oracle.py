"""Execute unchanged original post-render spawner instructions on controlled inputs."""
import argparse
import gzip
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT

from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha


def profiles():
    result = []
    for seed in (0, 0xffffffff, 0x80000000, 0x12345678):
        for count in (0, 1, 2, 8):
            for gate in range(9):
                result.append((count, 29 if gate == 6 else 30 if gate == 7 else 0,
                               32 if gate == 8 else 2, gate, 0x200, seed))
    for visual in (0, 31, 33, 255):
        result.append((2, 0, visual, 0, 0x200, 0x87654321))
    result.extend([(1, 0, 2, 0, 0x4000, 0), (1, 0, 2, 0, 0x3de0, 1),
                   (255, 30, 32, 1, 0x200, 0xffffffff)])
    return result


def inputs(index, profile):
    count, actors, visuals, gate, floor, seed = profile
    result = []
    def put(address, raw):
        result.append((address, raw))
    def data(offset, raw):
        put(0x1aa20 + offset, raw)
    for offset, size in ((0x1bae, 31 * 38), (0xc21e, 33 * 8), (0x74a8, (count + 1) * 30)):
        data(offset, bytes((i * 37 + index * 19 + 5) & 255 for i in range(size)))
    put(0x73d00, bytes((i * 29 + index * 7 + 11) & 255 for i in range(0x308)))
    for source in range(1, count + 1):
        row = bytearray(30)
        struct.pack_into('<HH', row, 0, (96 + source * 8) & 65535, (120 + source * 8) & 65535)
        row[8:12] = bytes((1, 7, 5, (source + index) % 8 + 1))
        for offset, base, span in ((12, 0xfffe, 0), (16, 0x7fff, 1), (20, 0x8000, 0xffff)):
            struct.pack_into('<HH', row, offset, base, span if index % 2 else (span + 7) & 65535)
        row[24:30] = bytes((250, 255 if index % 2 else 0, 4, 1, index & 255, 3))
        if gate == 1: row[27] = 2
        if gate == 2: row[27] = 0
        if gate == 3: row[10] = 0
        if gate == 4: row[9] = 0
        if gate == 5: row[8] = 2
        data(0x74a8 + source * 30, bytes(row))
    data(0x79a6, bytes((count,)))
    data(0x208d, bytes((actors,)))
    data(0xc496, bytes((visuals,)))
    data(0x1afa, struct.pack('<H', floor))
    data(0x1afe, struct.pack('<I', seed))
    data(0x2072, b'\x5a\xa5')
    data(0x2082, b'\x34\x12')
    for offset in (0x79e8, 0x79e9, 0x79ae, 0x79af):
        data(offset, bytes((0x80 + index % 128,)))
    # Descriptor bytes are controlled inputs, not extracted original RAM.
    data(0xc322, bytes((i * 7 + index * 11 + 3) & 255 for i in range(368)))
    return result


def generate(root, out):
    if unicorn.__version__ != '2.1.4' or any(k in os.environ for k in ('LD_PRELOAD', 'LIBUNICORN_PATH')):
        raise ValueError('Unsupported Unicorn loader profile')
    library = Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes()) != LIB_SHA or not any(
            line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual Unicorn library mapping differs')
    exe = (root / 'LEZAC.EXE').read_bytes()
    if sha(exe) != EXE_SHA:
        raise ValueError('Original executable differs')
    mz = struct.unpack_from('<14H', exe)
    image = bytearray(exe[mz[4] * 16:])
    for i in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + i * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
    out = out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only output directory')
    out.mkdir()
    cases = profiles()
    output = bytearray(b'LZSPWN01' + struct.pack('<I', len(cases)))
    coverage, states, errors = set(), 0, 0
    try:
        for index, profile in enumerate(cases):
            initial = bytearray(1048576)
            initial[0x10000:0x10000 + len(image)] = image
            seeds = inputs(index, profile)
            for address, raw in seeds:
                initial[address:address + len(raw)] = raw
            values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x3ffe,
                      0x1000, 0x1aa2, 0x40, 0x7000, 0x3fe4, 0x7a57, 0x602 if index % 2 else 0x202)
            endpoints, trace, writes = [], [], []
            for observed in (True, False):
                engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
                engine.mem_map(0, 1048576)
                engine.mem_write(0, bytes(initial))
                for reg, value in zip(REGS, values):
                    engine.reg_write(reg, value)
                def external(*unused):
                    raise ValueError('Spawner crossed an unmodeled interrupt or I/O')
                def code(uc, address, size, user):
                    registers = tuple(uc.reg_read(reg) for reg in REGS)
                    if address in (0x17c3d, 0x192e2):
                        uc.emu_stop()
                        return
                    if observed:
                        trace.append(registers)
                        coverage.add((registers[7], registers[12]))
                def write(uc, access, address, size, value, user):
                    if size not in (1, 2) or not (0x1aa20 <= address < 0x2aa1f or 0x73d00 <= address < 0x74006):
                        raise ValueError('Spawner wrote outside controlled data/stack')
                    writes.append((address, size, value & ((1 << (size * 8)) - 1)))
                engine.hook_add(unicorn.UC_HOOK_INTR, external)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE, code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
                until = 0 if observed else endpoints[0][0][7] * 16 + endpoints[0][0][12]
                engine.emu_start(0x17a57, until, count=200000)
                registers = tuple(engine.reg_read(reg) for reg in REGS)
                final = bytes(engine.mem_read(0, 1048576))
                if (registers[7], registers[12]) not in ((0x1000, 0x7c3d), (0x1920, 0xe2)):
                    raise ValueError('Spawner did not reach its declared endpoint')
                if final[0x10000:0x1aa20] != image[:0xaa20]:
                    raise ValueError('Original code changed during execution')
                endpoints.append((registers, final))
            if endpoints[0] != endpoints[1]:
                raise ValueError('Spawner observation affected complete memory/registers')
            registers, final = endpoints[0]
            expected = bytearray(initial)
            for address, size, value in writes:
                expected[address:address + size] = value.to_bytes(size, 'little')
            if expected != final:
                raise ValueError('Observed writes do not reconstruct complete final memory')
            trace.append(registers)
            states += len(trace)
            error = int(registers[7] == 0x1920)
            errors += error
            output.extend(struct.pack('<II13HI13HI', index, error, *values, *registers))
            output.extend(struct.pack('<I', len(seeds)))
            for address, raw in seeds:
                output.extend(struct.pack('<II', address, len(raw)) + raw)
            output.extend(struct.pack('<I', len(trace)))
            for item in trace:
                output.extend(struct.pack('<13HI', *item))
            output.extend(struct.pack('<I', len(writes)))
            for address, size, value in writes:
                output.extend(struct.pack('<IBH', address, size, value))
        raw = bytes(output)
        compressed = gzip.compress(raw, mtime=0)
        (out / 'oracle.bin.gz').write_bytes(compressed)
        manifest = dict(schema='lezac-controlled-spawner-frame-v1', executable_sha256=EXE_SHA,
            producer_sha256=sha(Path(__file__).read_bytes()),
            shared_oracle_sha256=sha(Path(__file__).with_name('frame_camera_oracle.py').read_bytes()),
            unicorn_version=unicorn.__version__, unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True, cases=len(cases), register_states=states,
            runtime_errors=errors, executed_instructions=[list(pair) for pair in sorted(coverage)],
            projection_bytes=len(raw), projection_sha256=sha(raw), compressed_bytes=len(compressed),
            compressed_sha256=sha(compressed), controlled_initial_memory=True,
            full_memory_observer_control=True, raw_memory_published=False, natural_capture=False,
            full_frame_claim=False, work_clock_claim=False, trace_arithmetic_flags_compared=False,
            endpoint_all_flags_compared=True, instruction_patches=0, calls_stubbed=0,
            interrupts_delivered=0, hardware_io=0)
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        print(json.dumps(dict(status='passed', cases=len(cases), states=states, runtime_errors=errors,
                              bytes=len(raw), compressed=len(compressed), sha256=sha(raw))), flush=True)
    except Exception as error:
        (out / 'failed.json').write_text(json.dumps(dict(status='failed', case=index, error=str(error))) + '\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    generate(args.repo.resolve(), args.out)
