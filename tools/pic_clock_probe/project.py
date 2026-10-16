"""Create bounded local CPU and PIC projections from a completed original capture."""
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
from check_interruptible_dos_time_fixture import projection

HEX = {'opcode', 'stack', 'vector_stub', 'globals', 'bank'}
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def project(capture, out):
    capture = capture.resolve(strict=True)
    out = out.resolve()
    assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
    recipe = json.loads((capture / 'report.json').read_bytes())
    raw = (capture / 'guest-dos-time.csv').read_bytes()
    assert 0 < len(raw) < 8 * 1024**2 and raw.endswith(b'\nend\n')
    assert recipe['passed'] is True and recipe['target_completed'] is True
    assert recipe['canonical_assets_unchanged'] is True and recipe['child_exit_code'] == 0
    assert recipe['trace_bytes'] == len(raw) and recipe['trace_sha256'] == sha(raw)
    assert recipe['producer_sha256'] == sha((capture / 'producer.py').read_bytes())
    assert recipe['input_route_sha256'] == sha((capture / 'input-route.py').read_bytes())
    assert recipe['process_memory_writes'] == recipe['injected_instructions'] == recipe['process_pauses'] == 0
    assert recipe['clock_or_irq_state_seeded'] is False and recipe['gameplay_state_seeded'] is False
    assert recipe['host_build']['guest_instruction_patches'] == 0
    assert recipe['host_build']['cpu_source_unchanged'] is True
    sample_proofs = []
    for sample in recipe['samples']:
        compressed = (capture / (sample['name'] + '.ram.gz')).read_bytes()
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            ram = stream.read(1048577)
        assert len(ram) == 1048576
        assert sample['ram_sha256'] == sha(ram) and sample['ram_gzip_sha256'] == sha(compressed)
        assert sample['code_bytes_verified'] == 43552 and sample['code_differences'] == 0
        png = (capture / (sample['name'] + '.png')).read_bytes()
        assert sample['png_sha256'] == sha(png)
        sample_proofs.append(dict(name=sample['name'], ram_sha256=sha(ram), png_sha256=sha(png)))
    cpu, clock, cases = projections(raw, recipe)
    out.mkdir()
    (out / 'cpu.bin').write_bytes(cpu)
    (out / 'clock.bin').write_bytes(clock)
    report = dict(schema='lezac-original-coupled-dos-pic-projection-v1', capture=str(capture),
        source_trace_terminal=True, source_capture_passed=True, raw_samples_verified=sample_proofs,
        calls=[case['call'] for case in cases], states=sum(len(case['states']) for case in cases),
        observed_irq_boundaries=sum(len(case['deliveries']) for case in cases),
        trace_sha256=sha(raw), cpu_sha256=sha(cpu), clock_sha256=sha(clock),
        raw_memory_published=False, later_irq_states_to_be_used_only_as_expected_outputs=True)
    (out / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


def projections(raw, recipe):
    rows = []
    for item in csv.DictReader(raw[:-4].decode('ascii').splitlines()):
        assert None not in item and all(type(value) is str for value in item.values())
        row = {key: value if key in ('kind', 'queue') else bytes.fromhex(value) if key in HEX else int(value)
               for key, value in item.items()}
        assert row['queue_overflow'] == 0 and row['cycle_max'] == 6000 and row['id_toggle'] == 0x200000
        rows.append(row)
    assert rows[0]['kind'] == 'identified'
    cases = []
    for entry in (row for row in rows if row['kind'] == 'callback_enter' and row['windowed'] == 1):
        group = [row for row in rows if row['call'] == entry['call']]
        assert group[0] is entry and group[-1]['kind'] == 'returned'
        assert not any(row['kind'] not in ('callback_enter', 'instruction', 'service_before',
                                          'service_after', 'returned') for row in group)
        states = [dict(row) for row in group if row['kind'] in ('instruction', 'returned')]
        assert 326 <= len(states) <= 4097 and states[0]['dispatch'] == entry['dispatch']
        assert all(b['dispatch'] == a['dispatch'] + 1 for a, b in zip(states, states[1:]))
        assert sum(row['cs'] == entry['vector_cs'] and entry['vector_ip'] <= row['ip'] < entry['vector_ip'] + 15
                   for row in states[:-1]) == 325
        assert (states[-1]['cs'], states[-1]['ip'], states[-1]['sp']) == (
            entry['return_cs'], entry['return_ip'], (entry['sp'] + 6) & 65535)
        assert len(entry['bank']) == 780 and entry['psp'] == recipe['code_segment'] - 16
        deliveries = [i for i, row in enumerate(states) if row['cs'] == 0xf000 and row['ip'] == 0xfea5]
        events = []
        for i, row in enumerate(states):
            row['io_count'] = len(events)
            assert row['stack_base'] == entry['stack_base'] and row['stack_ss'] == entry['ss']
            assert len(row['stack']) == 128 and len(row['globals']) == 10
            assert row['defined_flags'] == (0x207fd7 if row['kind'] == 'returned' else 0x700)
            if i + 1 == len(states):
                continue
            op = row['opcode']
            if op[0] in (0xe4, 0xe6):
                assert op[1] in ((0x61,) if op[0] == 0xe4 else (0x20, 0x61, 0x42, 0x43))
                events.append((op[0] == 0xe6, op[1], row['ax'] & 255 if op[0] == 0xe6 else states[i + 1]['ax'] & 255))
        offset, segment = struct.unpack_from('<HH', entry['globals'], 5)
        cases.append(dict(game=recipe['code_segment'], base=entry['vector_ip'], psp=entry['psp'],
            ss=entry['ss'], sp=entry['sp'], stack_base=entry['stack_base'], stack_length=128,
            bank_segment=segment, bank_offset=offset, bank=entry['bank'],
            vector_ip=entry['int1c_ip'], vector_cs=entry['int1c_cs'], legacy=False,
            states=states, deliveries=deliveries, io=events, call=entry['call']))
    assert 1 <= len(cases) <= 8 and sum(len(case['deliveries']) for case in cases) > 0
    clock = bytearray(b'LZPCLK01' + struct.pack('<I', len(cases)))
    for case in cases:
        clock.extend(struct.pack('<I', len(case['states'])))
        for row in case['states']:
            assert row['clock'] == row['pic_ticks'] * 6000 + 6000 - row['cpu_left'] - row['cpu_cycles']
            op = row['opcode']
            io_kind = 1 if op[0] == 0xe4 else 2 if op[0] == 0xe6 else 0
            clock.extend(struct.pack('<3qQI2H', row['cpu_cycles'], row['cpu_left'], row['io_delay_removed'],
                row['pic_ticks'], row['flags'], row['cs'], row['ip']))
            clock.extend(struct.pack('<BHB2B', io_kind, op[1] if io_kind else 0, row['ax'] & 255, op[0], op[1]))
            clock.extend(struct.pack('<4H4B', row['active_lines'], row['masked_lines'], row['inservice_lines'],
                row['pic_pending'], row['pic_active'], row['irq0_vector'], row['pic_special'], row['pic_auto_eoi']))
            queue = [item.split(':') for item in row['queue'].split(';') if item]
            assert len(queue) <= 64
            clock.extend(struct.pack('<IQIBBH', row['pit0_delay_bits'], row['pit0_start_bits'], row['pit0_count'],
                row['pit0_mode'], row['pit0_update'], len(queue)))
            for index, kind, value in queue:
                assert int(kind) in (1, 2)
                clock.extend(struct.pack('<IBQ', int(index, 16), int(kind), int(value)))
    cpu = projection(cases)
    return cpu, bytes(clock), cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    project(args.capture, args.out)
