"""Execute the complete original INT1C and its real CRT speaker calls under controlled Unicorn inputs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import unicorn
from unicorn import x86_const as x86

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--memory-reads', choices=['none', 'restricted'], default='restricted')
args = parser.parse_args()
root, out = args.root.resolve(), args.out.resolve()
assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
out.mkdir()
sha = lambda raw: hashlib.sha256(raw).hexdigest()
raw = (root / 'LEZAC.EXE').read_bytes()
assert sha(raw) == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
assert unicorn.__version__ == '2.1.4'
header = struct.unpack_from('<14H', raw)
image = bytearray(raw[header[4] * 16:])
for index in range(header[3]):
    offset, segment = struct.unpack_from('<HH', raw, header[12] + index * 4)
    at = segment * 16 + offset
    struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
original_irq = raw[0x770 + 0x0fbe:0x770 + 0x1091]
assert sha(original_irq) == '8505700f9f878bc49cb2ae0a62d2bd2c5ae9ca2849b8581bcc7cf95f6e06aecc'
registers = {name: getattr(x86, 'UC_X86_REG_' + name.upper()) for name in
             'ax bx cx dx si di bp cs ds es ss sp ip'.split()}
registers['flags'] = x86.UC_X86_REG_EFLAGS
initial = dict(ax=0x1234, bx=0x2345, cx=0x3456, dx=0x4567, si=0x5678, di=0x6789, bp=0x789a,
               cs=0x1000, ds=0x4321, es=0x5432, ss=0x8000, sp=0xfe00, ip=0x0fbe, flags=0x402)
data = 0x1aa20
bank = (root / 'PROEFS.SON').read_bytes()
assert sha(bank) == 'b5bc702a27ac85554cc76a62fced07567921b07d5c16f2027a62fbc956df701d'
assert len(bank) == 782
bank = bank[2:]
cases = []
for port in (0, 1, 2, 3, 0xf0, 0xff):
    cases.extend([(f'idle-p{port}', 0, 0, 17, 5, 3, port),
                  (f'gate-p{port}', 1, 0, 4, 5, 9, port),
                  (f'wait-p{port}', 1, 0, 2, 5, 9, port),
                  (f'direct-p{port}', 1, 0xea7e, 17, 5, 3, port),
                  (f'direct-terminal-p{port}', 1, 0xea61, 17, 5, 3, port)])
for index in range(130):
    cases.append((f'bank-{index}', 1, index, 0, 9, 1, index % 4))
cases.extend([('period-zero-wrap', 1, 0, 255, 0, 0, 0), ('period-zero-wait', 1, 0, 254, 255, 0, 3),
              ('step-before-gate', 1, 0, 0, 1, 1, 0), ('direct-maximum', 1, 65535, 255, 255, 0, 3)])
results = []
current = None
try:
    for name, active, cursor, accumulator, gate, period, port in cases:
        cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
        cpu.mem_map(0, 1024**2)
        cpu.mem_write(0x10000, bytes(image))
        cpu.mem_write(0x30000, bank)
        cpu.mem_write(0x8fdb0, bytes((index * 37 + 11) & 255 for index in range(112)))
        cpu.mem_write(0x8fe00, struct.pack('<HHH', 0x100, 0x9000, 0x7246))
        cpu.mem_write(data + 0x78c0, struct.pack('<H', cursor))
        cpu.mem_write(data + 0x79a0, bytes([accumulator, gate, period]))
        cpu.mem_write(data + 0x79c0, struct.pack('<HHB', 0, 0x3000, active))
        for key, value in initial.items():
            cpu.reg_write(registers[key], value)
        current = dict(name=name, active=active, cursor=cursor, accumulator=accumulator,
            gate=gate, period=period, port61=port, snapshots=[], io=[], writes=[], reads=[])
        state = dict(dispatch=0, defined=0x700, port=port)

        def snapshot():
            return dict(dispatch=state['dispatch'], defined=state['defined'],
                registers={key: cpu.reg_read(register) for key, register in registers.items()},
                stack=bytes(cpu.mem_read(0x8fdb0, 112)).hex(),
                globals=(bytes(cpu.mem_read(data + 0x78c0, 2)) + bytes(cpu.mem_read(data + 0x79a0, 3)) +
                         bytes(cpu.mem_read(data + 0x79c0, 5))).hex(),
                io_count=len(current['io']), write_count=sum(event['size'] for event in current['writes']),
                read_count=sum(event['size'] for event in current['reads']))

        def instruction(cpu, address, size, user):
            if address == 0x90100:
                current['snapshots'].append(snapshot())
                cpu.emu_stop()
                return
            if not (0x10fbe <= address < 0x11091 or 0x18769 <= address < 0x1879d):
                raise ValueError('Original execution escaped: ' + hex(address))
            current['snapshots'].append(snapshot())
            state['dispatch'] += 1
            ip = address - (0x10000 if address < 0x18000 else 0x184a0)
            if address < 0x18000 and ip in (0xfcf,0xfd9,0xfe4,0xfed,0xff2,0x100e,0x1021,0x1027,0x1029,0x1036,0x107c):
                state['defined'] |= 0x8d5
            if address < 0x18000 and ip in (0x1007, 0x1014):
                state['defined'] |= 0x8d4
            if address < 0x18000 and ip in (0x101b, 0x101f):
                state['defined'] = (state['defined'] | 0x8c5) & ~0x10
            if address >= 0x18000 and ip == 0x2d5:
                state['defined'] |= 0x8d5
            if address >= 0x18000 and ip == 0x2d9:
                state['defined'] &= ~0x8d5
            if address >= 0x18000 and ip in (0x2df, 0x2e3, 0x2f8):
                state['defined'] = (state['defined'] | 0x8c5) & ~0x10
            if address == 0x11090:
                state['defined'] |= 0x7fd7

        def read_port(cpu, port, size, user):
            assert port == 0x61 and size == 1
            current['io'].append(dict(direction='in', port=port, value=state['port'], dispatch=state['dispatch']))
            return state['port']

        def write_port(cpu, port, size, value, user):
            assert port in (0x61, 0x43, 0x42) and size == 1
            current['io'].append(dict(direction='out', port=port, value=value, dispatch=state['dispatch']))
            if port == 0x61:
                state['port'] = value

        def write_memory(cpu, access, address, size, value, user):
            assert (0x8fdb0 <= address and address + size <= 0x8fe20) or (
                address in (data + 0x78c0, data + 0x79a0, data + 0x79a1, data + 0x79a2, data + 0x79c4))
            current['writes'].append(dict(address=address, size=size, value=value, dispatch=state['dispatch']))

        def read_memory(cpu, access, address, size, value, user):
            current['reads'].append(dict(address=address, size=size,
                value=int.from_bytes(cpu.mem_read(address, size), 'little'), dispatch=state['dispatch']))

        def interrupt(*args):
            raise ValueError('Unexpected interrupt; real CRT calls must execute')

        cpu.hook_add(unicorn.UC_HOOK_CODE, instruction)
        cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, write_memory)
        if args.memory_reads == 'restricted':
            # Global read hooks alter Unicorn 2.1.4 far returns. Do not hook the control stack.
            cpu.hook_add(unicorn.UC_HOOK_MEM_READ, read_memory, None, data + 0x78c0, data + 0x79c4)
            cpu.hook_add(unicorn.UC_HOOK_MEM_READ, read_memory, None, 0x30000, 0x30000 + len(bank) - 1)
        cpu.hook_add(unicorn.UC_HOOK_INTR, interrupt)
        cpu.hook_add(unicorn.UC_HOOK_INSN, read_port, None, 1, 0, x86.UC_X86_INS_IN)
        cpu.hook_add(unicorn.UC_HOOK_INSN, write_port, None, 1, 0, x86.UC_X86_INS_OUT)
        cpu.emu_start(0x10fbe, 0x90101, count=1000)
        assert current['snapshots'][-1]['registers']['cs'] == 0x9000
        assert current['snapshots'][-1]['registers']['ip'] == 0x100
        assert current['snapshots'][-1]['registers']['sp'] == 0xfe06
        assert bytes(cpu.mem_read(0x10000, 43552)) == image[:43552]
        current['dispatches'] = state['dispatch']
        results.append(current)
    report = dict(schema='lezac-original-timer-instructions-v1', unicorn=unicorn.__version__,
        original_executable_sha256=sha(raw), bank_sha256=sha(bank),
        routine_sha256=sha(original_irq), speaker_sha256=sha(raw[0x770+0x8769:0x770+0x879d]),
        producer_sha256=sha(Path(__file__).read_bytes()), original_calls_stubbed=False,
        original_instruction_patches=0, original_code_bytes_verified=43552,
        inputs_seeded=True, io_ports_scripted=True, bios_wrapper_executed=False,
        memory_read_provider=args.memory_reads, stack_reads_hooked=False,
        natural_timing=False, whole_game_parity=False, initial_registers=initial, cases=results)
    raw_report = (json.dumps(report, separators=(',', ':')) + '\n').encode()
    assert len(raw_report) < 8 * 1024**2
    (out / 'original.json.gz').write_bytes(gzip.compress(raw_report, mtime=0))
    print(json.dumps(dict(cases=len(results), snapshots=sum(len(case['snapshots']) for case in results),
        distinct_instructions=len({(snapshot['registers']['cs'], snapshot['registers']['ip']) for case in results
            for snapshot in case['snapshots'][:-1]}), bytes=len(raw_report), status='passed')), flush=True)
except BaseException as error:
    (out / 'failure.json').write_text(json.dumps(dict(error=repr(error), current=current), indent=2) + '\n')
    raise
