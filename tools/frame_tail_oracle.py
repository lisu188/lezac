"""Controlled original frame-tail observations, not a C++ or natural-route proof."""
from collections import Counter
import argparse
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import struct
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--unicorn-path', type=Path)
args = parser.parse_args()
ROOT = args.root.resolve(strict=True)
OUT = args.out.resolve()
sys.path.insert(0,str(ROOT / 'tools'))
if args.unicorn_path:
    sys.path.insert(0,str(args.unicorn_path.resolve(strict=True)))
import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha
from actor_steering_oracle import encode_trace

if not OUT.is_relative_to(Path('/dev/shm')):
    raise ValueError('Use RAM-only scout output')
DATA = 0x1aa20
STOPS = {0x17903: 'next_frame', 0x18298: 'completion_handoff',
    0x182b9: 'escape_handoff', 0x192e2: 'runtime_error',
    0x18224: 'view_change_handoff', 0x1825e: 'view_change_handoff'}
FIELDS = (0x2098, 0x209a, 0x209c, 0x79cb, 0x2082, 0xc49c)

def require(yes, message):
    if not yes:
        raise ValueError(message)

capacity = os.statvfs('/dev/shm')
require(capacity.f_bavail * capacity.f_frsize - 64 * 1048576 >=
    capacity.f_blocks * capacity.f_frsize / 10, 'RAM capacity guard')
require(unicorn.__version__ == '2.1.4' and
    not any(k in os.environ for k in ('LD_PRELOAD', 'LIBUNICORN_PATH')), 'Unicorn profile')
library = Path(uclib._name).resolve(strict=True)
require(sha(library.read_bytes()) == LIB_SHA and any(line.endswith(str(library))
    for line in Path('/proc/self/maps').read_text().splitlines()), 'Unicorn mapping')
raw = (ROOT / 'LEZAC.EXE').read_bytes()
require(sha(raw) == EXE_SHA, 'Canonical original differs')
mz = struct.unpack_from('<14H', raw)
image = bytearray(raw[mz[4] * 16:])
for i in range(mz[3]):
    offset, segment = struct.unpack_from('<HH', raw, mz[12] + i * 4)
    at = segment * 16 + offset
    struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
OUT.mkdir(exist_ok=False)
SOURCES = ('frame_tail_oracle.py','frame_camera_oracle.py','actor_steering_oracle.py')
sources = {name:sha((ROOT/'tools'/name).read_bytes()) for name in SOURCES}
require(sources['frame_tail_oracle.py']==sha(Path(__file__).read_bytes()), 'Executed producer source differs')
coverage = Counter()
rows = []
profiles = [dict(duration=d, palette=p, key=k, complete=c, seed=s, tick=t,
    countdown=0, tile=None, fragment=0, floor=0x200, flags=0x202)
    for d,p,k,c,s,t in itertools.product(
        (0,1,2,3,255,32768,65535), (0,1,3), (0,0x73,0x1b), (False,True),
        (1,0xffffffff), (0,1,4,5,65535))]
profiles += [dict(duration=d, palette=0, key=0, complete=True, seed=s, tick=5,
    countdown=c, tile=tile, fragment=f, floor=floor, flags=flags)
    for d,c,tile,s,f,flags,floor in itertools.product(
        (0,3), (1,2,255), (0,1,102,115), (1,0xffffffff),
        (0,0x3fff,0x4000,0x7fff,0x8000,0xffff), (0x202,0x602), (0x200,0xffff))]
profiles += [dict(duration=d, palette=0, key=0, complete=True, seed=s, tick=5,
    countdown=1, tile=0, fragment=1, floor=0x200, flags=flags, excluded=excluded)
    for d,s,flags,excluded in itertools.product(
        (0,3), (1,0xffffffff), (0x202,0x602), range(103,113))]
profiles += [dict(duration=0, palette=0, key=key, complete=False, seed=1, tick=1,
    countdown=0, tile=None, fragment=0, floor=0x200, flags=flags, view=view, players=players)
    for key,view,players,flags in itertools.product(
        (0x65,0x72), (20,21,22,39,40,41), (0,1,2), (0x202,0x602))]
profiles += [dict(duration=0, palette=0, key=0x73, complete=False, seed=1, tick=tick,
    countdown=0, tile=None, fragment=0, floor=0x200, flags=flags, toggle=toggle)
    for toggle,flags,tick in itertools.product((0,1,255), (0x202,0x602), (1,5))]
projection = bytearray(b'LZTAIL01' + struct.pack('<I', len(profiles)))
report = dict(status='running', schema='lezac-controlled-frame-tail-v1',
    source_sha256=sources, asset_sha256={'LEZAC.EXE':EXE_SHA}, rows=rows,
    unicorn_version=unicorn.__version__, unicorn_library_sha256=LIB_SHA,
    actual_library_mapping_verified=True, host_hardware_io=False,
    hardware_inputs=0, emulated_output_ports=[0x3c8,0x3c9],
    original_code_bytes_verified=43552, instruction_patches=0, calls_stubbed=0,
    later_state_injected=False, interrupts_delivered=0, natural_route=False,
    production_app_comparison=False, natural_capture=False, full_frame_claim=False,
    raw_memory_published=False)
engine = None
initial = None
profile = None
try:
    for index, profile in enumerate(profiles):
        duration,palette,key,complete,seed,tick = (profile[k] for k in
            ('duration','palette','key','complete','seed','tick'))
        initial = bytearray(1048576)
        initial[0x10000:0x10000 + len(image)] = image
        seeds = []
        def put(address, value):
            value = bytes(value)
            initial[address:address + len(value)] = value
            seeds.append((address, value))
        def word(offset, value):
            put(DATA + offset, struct.pack('<H', value))
        def byte(offset, value):
            put(DATA + offset, bytes((value,)))
        word(0x2076, 0)
        word(0x207e, 199)
        word(0x2080, 0)
        word(0x2098, 0xa55a)
        word(0x209a, duration)
        word(0x209c, 0 if duration == 0 else 1)
        word(0x78c2, tick)
        word(0x1afa, profile['floor'])
        put(DATA + 0x1afe, struct.pack('<I', seed))
        byte(0x79cb, palette)
        byte(0x2058, key)
        byte(0x79c5, int(complete))
        byte(0x79c6, int(complete))
        byte(0x79b2, profile['countdown'])
        byte(0x79b7, 1)
        byte(0x79ad, 20)
        for field,offset in (('excluded',0x79b4),('players',0x79b8),('toggle',0xc49c)):
            if field in profile:
                byte(offset,profile[field])
        if 'view' in profile:
            word(0xc1ea,profile['view'])
        for slot in range(1, 4):
            byte(0x79cd + slot, slot + 10)
            for component in range(1, 4):
                byte(0x79ce + slot * 3 + component, 20)
                byte(0x79d8 + slot * 3 + component, 20 if slot == 3 else 24)
        if profile['tile'] is not None:
            word(0xc204,60)
            word(0xc206,33)
            word(0xc1e0,0)
            word(0xc1e2,0x4000)
            word(0x6612,0)
            word(0x6614,0x5000)
            word(0x78c4,profile['fragment'])
            put(0x40000,bytes((profile['tile'],))*1980)
            put(0x50000,struct.pack('<H',0x1234)*1980)
        sp = 0x3fe4
        put(0x70000 + sp - 128, bytes((index * 7 + i * 29 + 11) & 255 for i in range(160)))
        reconstructed = bytearray(1048576)
        reconstructed[0x10000:0x10000 + len(image)] = image
        for address, value in seeds:
            reconstructed[address:address + len(value)] = value
        require(reconstructed == initial, 'Initial seeds do not reconstruct complete RAM')
        entry = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x3ffe,
            0x1000, 0x1aa2, 0x40, 0x7000, sp, 0x806a, profile['flags'])
        endpoints = []
        writes = []
        visits = Counter()
        trace = hashlib.sha256()
        trace_rows = []
        for observed in (True, False):
            engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
            engine.mem_map(0, 1048576)
            engine.mem_write(0, bytes(initial))
            for reg, value in zip(REGS, entry):
                engine.reg_write(reg, value)
            ports = []
            def stop(uc, address, size, user):
                if address in STOPS:
                    uc.emu_stop()
                    return True
                return False
            def code(uc, address, size, user):
                if stop(uc, address, size, user):
                    return
                visits[hex(address)] += 1
                registers = tuple(uc.reg_read(reg) for reg in REGS)
                trace.update(struct.pack('<13HI', *registers))
                trace_rows.append(registers)
            def write(uc, access, address, size, value, user):
                require(size in (1, 2, 4) and address + size <= 1048576, 'Write extent')
                writes.append((address, size, value & ((1 << (size * 8)) - 1)))
            def port_out(uc, port, size, value, user):
                require(port in (0x3c8, 0x3c9) and size == 1, 'Unexpected original output')
                ports.append((port, size, value))
            def forbidden(*unused):
                raise ValueError('Original tail attempted an input or CPU interrupt')
            engine.hook_add(unicorn.UC_HOOK_INTR, forbidden)
            engine.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, UC_X86_INS_IN)
            engine.hook_add(unicorn.UC_HOOK_INSN, port_out, None, 1, 0, UC_X86_INS_OUT)
            if observed:
                engine.hook_add(unicorn.UC_HOOK_CODE, code)
                engine.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
            else:
                for address in STOPS:
                    engine.hook_add(unicorn.UC_HOOK_CODE, stop, None, address, address)
            engine.emu_start(0x1806a, 0, count=500000)
            registers = tuple(engine.reg_read(reg) for reg in REGS)
            endpoint = registers[7] * 16 + registers[12]
            memory = bytes(engine.mem_read(0, 1048576))
            require(endpoint in STOPS, 'Tail did not reach a declared boundary')
            require(memory[0x10000:DATA] == initial[0x10000:DATA], 'Original code changed')
            endpoints.append((registers, memory, ports))
        require(endpoints[0] == endpoints[1], 'Observer changed RAM, registers or DAC output')
        registers, memory, ports = endpoints[0]
        rebuilt = bytearray(initial)
        for address, size, value in writes:
            rebuilt[address:address + size] = value.to_bytes(size, 'little')
        require(rebuilt == memory, 'Ordered writes do not reconstruct full RAM')
        boundary = STOPS[registers[7] * 16 + registers[12]]
        require(registers[10] == entry[10], 'Borrowed SS changed')
        if boundary!='runtime_error':
            require(all(registers[n] == entry[n] for n in (6,11)), 'Borrowed SP/BP changed')
        trace_rows.append(registers)
        projection.extend(struct.pack('<IB13HI13HI', index, tuple(STOPS.values()).index(boundary),
            *entry, *registers))
        projection.extend(struct.pack('<I', len(seeds)))
        for address, value in seeds:
            projection.extend(struct.pack('<II', address, len(value)) + value)
        encode_trace(projection, trace_rows)
        projection.extend(struct.pack('<I', len(writes)))
        for item in writes:
            projection.extend(struct.pack('<IBI', *item))
        projection.extend(struct.pack('<I', len(ports)))
        for item in ports:
            projection.extend(struct.pack('<HBI', *item))
        require(len(projection) <= 64 * 1048576, 'Projection exceeds RAM reserve')
        coverage.update(cases=1, instructions=sum(visits.values()), writes=len(writes),
            dac_writes=len(ports))
        coverage[boundary] += 1
        rows.append(dict(index=index, profile=profile, entry=list(entry), endpoint=list(registers),
            boundary=boundary, trace_sha256=trace.hexdigest(),
            initial_ram_sha256=sha(initial), final_ram_sha256=sha(memory),
            fields={hex(offset): struct.unpack_from('<H', memory, DATA + offset)[0] for offset in FIELDS},
            seed=struct.unpack_from('<I', memory, DATA + 0x1afe)[0],
            visits=dict(visits), ports=[list(port) for port in ports], writes=len(writes)))
        if index % 50 == 0:
            print('frame_tail_scout_cases=' + str(index + 1), flush=True)
        del engine
        engine = None
    require(all(sha((ROOT/'tools'/name).read_bytes())==expected for name,expected in sources.items()) and
        sha((ROOT/'LEZAC.EXE').read_bytes())==EXE_SHA and sha(library.read_bytes())==LIB_SHA and
        any(line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()),
        'Original tail capture inputs changed')
    report.update(status='passed', coverage=dict(coverage),
        observer_control='register-write-trace-versus-stop-only-code-hooks',
        complete_memory_observer_control=True, ordered_writes_reconstruct_memory=True)
    packed = gzip.compress(projection, mtime=0)
    (OUT / 'oracle.bin.gz').write_bytes(packed)
    report.update(projection_bytes=len(projection), projection_sha256=sha(projection),
        compressed_bytes=len(packed), compressed_sha256=sha(packed),
        complete_initial_seed_reconstruction=True)
except Exception as error:
    report.update(status='failed', error=str(error), profile=profile)
    if initial is not None:
        (OUT / 'failed-initial.bin').write_bytes(initial)
    if engine is not None:
        (OUT / 'failed-current.bin').write_bytes(engine.mem_read(0, 1048576))
        report['failed_registers'] = [engine.reg_read(reg) for reg in REGS]
    raise
finally:
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(status=report['status'], coverage=report.get('coverage'))))
