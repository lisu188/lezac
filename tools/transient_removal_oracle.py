"""Execute unchanged 452A/458D removal calls on explicit controlled inputs."""
import argparse
from collections import Counter
import gzip
import itertools
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

DATA = 0x1aa20
LIMIT = 16 * 1024**2


def profiles():
    rows = []
    def add(kind, count, slot, **extra):
        row = dict(kind=kind, count=count, slot=slot, direction=0, base=0x209e,
                   sp=0x3fe4, ss=0x7000, parent=0x4000, cursor=205, floor=0x200,
                   family='matrix')
        row.update(extra)
        rows.append(row)
    for kind, counts in ((0, (0, 1, 2, 4, 16)), (1, (199, 200, 201, 205))):
        for count in counts:
            slots = sorted({0, 1, count-1, count, count+1, 65535})
            if kind:
                slots = sorted({198, 199, 200, count-1, count, count+1})
            for slot, direction, base in itertools.product(slots, (0, 1), (0x209e, 0xfff8)):
                add(kind, count, slot, direction=direction, base=base)
    for kind, sp, ss, floor in itertools.product((0, 1), (0, 1, 0x201, 0x3fe4, 65535),
                                                (0x7000, 0x1aa2), (0, 0x4000)):
        add(kind, 4 if not kind else 204, 2 if not kind else 201,
            sp=sp, ss=ss, floor=floor, family='stack_and_alias')
    for slot, cursor, parent in itertools.product((200, 201, 204, 205, 65535),
                                                 (0, 199, 200, 204, 32767, 32768, 65535),
                                                 (0, 0x4000, 65535)):
        add(1, 204, slot, cursor=cursor, parent=parent, family='parent_cursor')
    return rows


def make_case(index, row):
    patches = []
    def put(address, raw):
        if not 0 <= address <= address+len(raw) <= 1048576:
            raise ValueError('Removal seed exceeds memory')
        patches.append((address, raw))
    def word(segment, offset, value):
        put(segment*16+(offset & 65535), struct.pack('<H', value & 65535))
    pattern = bytes((i*29+index*7+11) & 255 for i in range(2600))
    first = min(len(pattern), 65536-row['base'])
    put(DATA+row['base'], pattern[:first])
    if first < len(pattern):
        put(DATA, pattern[first:])
    put(DATA+0x78d6, bytes((i*17+index*13+5) & 255 for i in range(256)))
    for offset, value in ((0x2076, row['count'] if row['kind'] == 0 else 0),
                          (0x207e, row['count'] if row['kind'] == 1 else 199),
                          (0x207c, row['base']), (0x1afa, row['floor'])):
        word(0x1aa2, offset, value)
    # Argument words may cross the 16-bit SP boundary independently.
    endpoint = 0x4929 if not row['kind'] else 0x4a3c if index % 2 else 0x4d34
    word(row['ss'], row['sp'], endpoint)
    word(row['ss'], row['sp']+2, row['parent'])
    word(row['ss'], row['sp']+4, row['slot'])
    word(row['ss'], row['parent']-2, row['cursor'])
    values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x4567,
              0x1000, 0x1aa2, 0x40, row['ss'], row['sp'],
              0x452a if not row['kind'] else 0x458d, 0x202 | row['direction']*0x400)
    return values, patches, endpoint


def generate(root, out):
    if unicorn.__version__ != '2.1.4' or any(k in os.environ for k in ('LD_PRELOAD', 'LIBUNICORN_PATH')):
        raise ValueError('Unsupported removal oracle loader')
    library = Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes()) != LIB_SHA or not any(
            line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual removal oracle mapping differs')
    exe = (root/'LEZAC.EXE').read_bytes()
    if sha(exe) != EXE_SHA:
        raise ValueError('Canonical removal executable differs')
    sources = {name: sha((root/'tools'/name).read_bytes()) for name in
               ('transient_removal_oracle.py', 'frame_camera_oracle.py')}
    mz = struct.unpack_from('<14H', exe)
    image = bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12]+4*i)
        at = segment*16+offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0]+0x1000) & 65535)
    out = out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only removal output')
    out.mkdir()
    rows = profiles()
    output = bytearray(b'LZTRRM01'+struct.pack('<II', len(rows), len(exe))+exe)
    coverage = set()
    outcomes = [0, 0]
    states = writes_total = sparse_cases = 0
    index = -1
    try:
        for index, row in enumerate(rows):
            values, patches, endpoint = make_case(index, row)
            initial = bytearray(1048576)
            initial[0x10000:0x10000+len(image)] = image
            for address, raw in patches:
                initial[address:address+len(raw)] = raw
            trace, writes, results = [], [], []
            stop = None
            observed_states = 0
            for observed in (True, False):
                engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
                engine.mem_map(0, 1048576)
                engine.mem_write(0, bytes(initial))
                for register, value in zip(REGS, values):
                    engine.reg_write(register, value)
                def external(*unused):
                    raise ValueError('Removal crossed hardware I/O or interrupt')
                def code(uc, address, size, user):
                    nonlocal stop, observed_states
                    regs = tuple(uc.reg_read(register) for register in REGS)
                    if (regs[7], regs[12]) in ((0x1000, endpoint), (0x1920, 0xe2)):
                        stop = address
                        uc.emu_stop()
                        return
                    if not (regs[7] == 0x1000 and 0x452a <= regs[12] < 0x45fa or
                            regs[7] == 0x1920 and 0x4df <= regs[12] <= 0x4f4):
                        raise ValueError('Removal left declared code: '+str((regs[7], regs[12])))
                    observed_states += 1
                    if len(trace) < 10000:
                        trace.append(regs)
                    coverage.add((regs[7], regs[12]))
                def write(uc, access, address, size, value, user):
                    if size not in (1, 2) or not 0 <= address <= address+size <= 1048576:
                        raise ValueError('Removal write exceeds memory')
                    writes.append((address, size, value & ((1 << (size*8))-1)))
                engine.hook_add(unicorn.UC_HOOK_INTR, external)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE, code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
                engine.emu_start(values[7]*16+values[12], 0 if observed else stop, count=400000)
                regs = tuple(engine.reg_read(register) for register in REGS)
                final = bytes(engine.mem_read(0, 1048576))
                if stop is None or regs[7]*16+regs[12] != stop or final[0x10000:DATA] != image[:0xaa20]:
                    raise ValueError('Removal endpoint or original code changed: '+str((regs, stop, observed_states)))
                results.append((regs, final))
            if results[0] != results[1]:
                raise ValueError('Removal observer changed full memory/registers')
            regs, final = results[0]
            reconstructed = bytearray(initial)
            for address, size, value in writes:
                reconstructed[address:address+size] = value.to_bytes(size, 'little')
            if reconstructed != final:
                raise ValueError('Removal writes do not reconstruct memory')
            outcome = int(regs[7] == 0x1920)
            outcomes[outcome] += 1
            if observed_states > 10000:
                trace = [values]
                sparse_cases += 1
            trace.append(regs)
            output.extend(struct.pack('<III13HI13HI', index, row['kind'], outcome, *values, *regs))
            output.extend(struct.pack('<I', len(patches)))
            for address, raw in patches:
                output.extend(struct.pack('<II', address, len(raw))+raw)
            output.extend(struct.pack('<I', len(trace)))
            for column in range(14):
                output.extend(struct.pack('<'+('I' if column == 13 else 'H')*len(trace), *(r[column] for r in trace)))
            output.extend(struct.pack('<I', len(writes)))
            for entry in writes:
                output.extend(struct.pack('<IBH', *entry))
            if len(output) > LIMIT:
                raise ValueError('Removal compact projection exceeds 16 MiB')
            states += observed_states+1
            writes_total += len(writes)
        if sha((root/'LEZAC.EXE').read_bytes()) != EXE_SHA or any(
                sha((root/'tools'/name).read_bytes()) != value for name, value in sources.items()):
            raise ValueError('Removal inputs changed during generation')
        raw = bytes(output)
        packed = gzip.compress(raw, compresslevel=9, mtime=0)
        (out/'oracle.bin.gz').write_bytes(packed)
        manifest = dict(schema='lezac-controlled-transient-removal-v1', cases=len(rows),
            profile_families=dict(Counter(r['family'] for r in rows)), outcomes=outcomes,
            asset_sha256={'LEZAC.EXE': EXE_SHA}, source_sha256=sources,
            unicorn_version=unicorn.__version__, unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True, complete_memory_observer_control=True,
            ordered_writes_reconstruct_memory=True, instruction_patches=0, calls_stubbed=0,
            later_state_injected=False, controlled_initial_memory=True, natural_capture=False,
            interrupts_delivered=0, hardware_io=0, register_states=states, ordered_writes=writes_total,
            endpoint_only_long_cases=sparse_cases, long_case_trace_threshold=10000,
            executed_instructions=[list(r) for r in sorted(coverage)], projection_bytes=len(raw),
            projection_sha256=sha(raw), compressed_bytes=len(packed), compressed_sha256=sha(packed),
            raw_memory_published=False, actual_app_integration=False, full_frame_claim=False)
        (out/'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed', cases=len(rows), states=states, writes=writes_total,
                             outcomes=outcomes, raw_bytes=len(raw), compressed_bytes=len(packed))), flush=True)
    except BaseException as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed', case=index, error=repr(error)))+'\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    generate(args.repo.resolve(), args.out)
