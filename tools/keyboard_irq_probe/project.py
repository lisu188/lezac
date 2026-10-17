"""Project only authenticated original IRQ1 states; later observations remain targets."""
import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from keyboard_irq_probe.trace import inspect_trace

REGISTERS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es', 'ss', 'sp', 'ip')
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def validate_opcodes(trace, executable, recipe):
    mz = struct.unpack_from('<14H', executable)
    image = bytearray(executable[0x770:])
    game = recipe['code_segment']
    for index in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', executable, mz[12] + index * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + game) & 65535)
    raw = gzip.decompress(trace.read_bytes())
    for row in csv.DictReader(io.StringIO(raw[:-4].decode('ascii'))):
        assert int(row['game']) == game and int(row['data']) == recipe['data_segment']
        if row['kind'] == 'irq_return':
            continue
        cs, ip, opcode = int(row['cs']), int(row['ip']), bytes.fromhex(row['opcode'])
        if cs == game:
            assert 0x1091 <= ip <= 0x1155 and opcode == image[ip:ip + 8]
        else:
            assert cs == 0xf000
            base = int(row['chain_ip']) if ip >= int(row['chain_ip']) else int(row['bios15_ip'])
            stub = bytes.fromhex(row['chain_stub'] if base == int(row['chain_ip']) else row['bios15_stub'])
            offset = ip - base
            assert 0 <= offset < len(stub) and opcode[:min(8, len(stub) - offset)] == stub[offset:offset + 8]


def projection(trace):
    details = inspect_trace(trace)
    assert details['validated_target_completed']
    raw = gzip.decompress(trace.read_bytes())
    rows = list(csv.DictReader(io.StringIO(raw[:-4].decode('ascii'))))
    output = bytearray(b'LZKIRQ01' + struct.pack('<I', len(details['irq_windows'])))
    cursor = 0
    for case in details['irq_windows']:
        states = rows[cursor:cursor + case['states']]
        cursor += case['states']
        entry = states[0]
        output.extend(struct.pack('<I8HIB', len(states), *[int(entry[name]) for name in
            ('stack_base', 'stack_ss', 'game', 'data', 'chain_ip', 'chain_cs', 'bios15_ip', 'bios15_cs')],
            int(entry['id_toggle']), int(entry['scan'])))
        for row in states:
            output.extend(struct.pack('<13HI', *[int(row[name]) for name in REGISTERS], int(row['flags'])))
            for name in ('stack', 'bios', 'held', 'opcode', 'hardware_buffer'):
                output.extend(bytes.fromhex(row[name]))
            output.extend(struct.pack('<13Q', *[int(value) for value in row['hardware'].split(';')]))
            output.extend(struct.pack('<5H', *[int(row[name]) for name in
                ('pic_active', 'pic_pending', 'active_lines', 'inservice_lines', 'masked_lines')]))
    assert cursor == len(rows)
    return bytes(output), details


def project(capture, root, out):
    assert out.resolve().is_relative_to(Path('/dev/shm')) and not out.exists()
    report_raw = (capture / 'report.json').read_bytes()
    report = json.loads(report_raw)
    assert report['schema'] == 'lezac-original-keyboard-irq-v1' and report['status'] == 'observed'
    assert report['passed'] and report['validated_target_completed'] and report['child_exit_code'] == 0
    assert report['canonical_assets_unchanged'] and report['keyboard_layout'] == 'none' and report['bios_observation_bytes'] == 152
    assert report['process_memory_writes'] == report['process_pauses'] == report['guest_instruction_patches'] == report['calls_stubbed'] == 0
    assert report['input_bytes_seeded'] is report['gameplay_state_seeded'] is False
    for name, digest in report['sources'].items():
        assert sha((root / name).read_bytes()) == sha((capture / 'source-tree' / name).read_bytes()) == digest
    for name, pin in report['assets'].items():
        raw = (root / name).read_bytes()
        assert len(raw) == pin['bytes'] and sha(raw) == pin['sha256']
    exe = (root / 'LEZAC.EXE').read_bytes()
    assert sha(exe) == report['executable_sha256'] == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    mz = struct.unpack_from('<14H', exe)
    image = bytearray(exe[0x770:])
    for index in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + index * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + report['code_segment']) & 65535)
    for sample in report['samples']:
        compressed = (capture / (sample['name'] + '.ram.gz')).read_bytes()
        ram = gzip.decompress(compressed)
        assert len(ram) == 1048576 and sha(ram) == sample['ram_sha256'] and sha(compressed) == sample['ram_gzip_sha256']
        at = report['code_segment'] * 16
        assert ram[at:at + 43552] == image[:43552]
        assert sha((capture / (sample['name'] + '.png')).read_bytes()) == sample['png_sha256']
    trace = capture / 'irq.csv.gz'
    assert sha(trace.read_bytes()) == report['trace_sha256']
    validate_opcodes(trace, exe, report)
    output, details = projection(trace)
    assert details['irq_windows'] == report['irq_windows']
    out.mkdir()
    (out / 'cpu.bin').write_bytes(output)
    record = dict(projection_sha256=sha(output), projection_bytes=len(output),
        recipe_sha256=sha(report_raw), trace_sha256=sha(trace.read_bytes()),
        cases=len(details['irq_windows']), states=details['states'],
        samples_verified=len(report['samples']), source_code_bytes_verified=43552,
        later_observations_injected=False, irq_eligibility_claim=False, whole_game_claim=False)
    (out / 'report.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    project(args.capture, args.repo, args.out)
