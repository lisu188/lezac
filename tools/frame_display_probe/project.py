"""Project completed original DOS-to-foreground windows without injecting later state."""
import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct

HEX = {'opcode', 'stack', 'vector_stub', 'globals', 'bank', 'frame_globals', 'display_globals'}
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def projections(raw, recipe):
    assert 0 < len(raw) < 8 * 1024**2 and raw.endswith(b'\nend\n')
    rows = []
    for item in csv.DictReader(raw[:-4].decode('ascii').splitlines()):
        assert None not in item and all(type(value) is str for value in item.values())
        row = {key: value if key in ('kind', 'queue') else bytes.fromhex(value) if key in HEX else int(value)
               for key, value in item.items()}
        assert row['queue_overflow'] == 0 and row['cycle_max'] == 6000 and row['id_toggle'] == 0x200000
        rows.append(row)
    assert rows[0]['kind'] == 'identified'
    cases = []
    for entry in (row for row in rows if row['kind'] == 'callback_enter' and row['windowed'] == 1
                  and row['return_ip'] == 0x791e):
        assert entry['return_cs'] == recipe['code_segment']
        group = [row for row in rows if row['call'] == entry['call']]
        assert group[0] is entry and group[-1]['kind'] == 'frame_display_return'
        assert all(row['kind'] in ('callback_enter', 'instruction', 'service_before', 'service_after',
                                   'returned', 'frame_display_return') for row in group)
        # DOS-return metadata duplicates the following pre-decode boundary.
        states = [dict(row) for row in group if row['kind'] in ('instruction', 'frame_display_return')]
        assert 355 <= len(states) <= 4097 and states[0]['dispatch'] == entry['dispatch']
        assert all(b['dispatch'] == a['dispatch'] + 1 for a, b in zip(states, states[1:]))
        assert sum(row['cs'] == entry['vector_cs'] and entry['vector_ip'] <= row['ip'] < entry['vector_ip'] + 15
                   for row in states[:-1]) == 325
        assert sum(row['cs'] == recipe['code_segment'] and 0x791e <= row['ip'] < 0x7966 for row in states) == 29
        assert (states[-1]['cs'], states[-1]['ip'], states[-1]['sp']) == (
            entry['return_cs'], 0x799a, (entry['sp'] + 6) & 65535)
        assert len(entry['bank']) == 780 and entry['psp'] == recipe['code_segment'] - 16
        events = []
        for index, row in enumerate(states):
            row['io_count'] = len(events)
            assert row['stack_base'] == entry['stack_base'] and row['stack_ss'] == entry['ss']
            assert len(row['stack']) == 128 and len(row['globals']) == 10 and len(row['frame_globals']) == 11 and len(row['display_globals']) == 5
            assert row['defined_flags'] == 0x700
            if index + 1 == len(states):
                continue
            op = row['opcode']
            if op[0] in (0xe4, 0xe6):
                assert op[1] in ((0x61,) if op[0] == 0xe4 else (0x20, 0x61, 0x42, 0x43))
                events.append((op[0] == 0xe6, op[1], row['ax'] & 255 if op[0] == 0xe6 else states[index + 1]['ax'] & 255))
        offset, segment = struct.unpack_from('<HH', entry['globals'], 5)
        deliveries = [index for index, row in enumerate(states) if row['cs'] == 0xf000 and row['ip'] == 0xfea5]
        cases.append(dict(entry=entry, states=states, events=events, offset=offset, segment=segment,
                          deliveries=deliveries, call=entry['call']))
    assert 1 <= len(cases) <= 8
    cpu = bytearray(b'LZFDSP01' + struct.pack('<I', len(cases)))
    clock = bytearray(b'LZPCLK01' + struct.pack('<I', len(cases)))
    registers = 'ax bx cx dx si di bp cs ds es ss sp ip'.split()
    for case in cases:
        entry, states, events, deliveries = (case[key] for key in ('entry', 'states', 'events', 'deliveries'))
        cpu.extend(struct.pack('<12HB3I', recipe['code_segment'], entry['vector_ip'], entry['psp'], entry['ss'], entry['sp'],
            entry['stack_base'], 128, case['segment'], case['offset'], len(entry['bank']), entry['int1c_ip'], entry['int1c_cs'],
            0, len(states), len(events), len(deliveries)))
        for index in deliveries:
            cpu.extend(struct.pack('<I', index))
        cpu.extend(entry['bank'])
        clock.extend(struct.pack('<I', len(states)))
        for row in states:
            cpu.extend(struct.pack('<13H4I2BI', *[row[key] for key in registers], row['flags'], row['defined_flags'],
                row['bios_ticks'], row['psp_stack'], row['motor'], row['drive'], row['io_count']))
            cpu.extend(row['stack'] + row['globals'] + row['frame_globals'] + row['display_globals'])
            assert row['clock'] == row['pic_ticks'] * 6000 + 6000 - row['cpu_left'] - row['cpu_cycles']
            op = row['opcode']
            kind = 1 if op[0] == 0xe4 else 2 if op[0] == 0xe6 else 0
            clock.extend(struct.pack('<3qQI2H', row['cpu_cycles'], row['cpu_left'], row['io_delay_removed'],
                row['pic_ticks'], row['flags'], row['cs'], row['ip']))
            clock.extend(struct.pack('<BHB2B', kind, op[1] if kind else 0, row['ax'] & 255, op[0], op[1]))
            clock.extend(struct.pack('<4H4B', row['active_lines'], row['masked_lines'], row['inservice_lines'], row['pic_pending'],
                row['pic_active'], row['irq0_vector'], row['pic_special'], row['pic_auto_eoi']))
            queue = [item.split(':') for item in row['queue'].split(';') if item]
            assert len(queue) <= 64
            clock.extend(struct.pack('<IQIBBH', row['pit0_delay_bits'], row['pit0_start_bits'], row['pit0_count'],
                row['pit0_mode'], row['pit0_update'], len(queue)))
            for index, kind, value in queue:
                assert int(kind) in (1, 2)
                clock.extend(struct.pack('<IBQ', int(index, 16), int(kind), int(value)))
        for event in events:
            cpu.extend(struct.pack('<BHB', *event))
    return bytes(cpu), bytes(clock), cases


def project(capture, out, executable, allow_control=False):
    capture = capture.resolve(strict=True)
    out = out.resolve()
    assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
    recipe = json.loads((capture / 'report.json').read_bytes())
    raw = (capture / 'guest-dos-time.csv').read_bytes()
    completed_target = recipe['status'] == 'observed' and recipe['passed'] is True and recipe['target_completed'] is True
    assert completed_target or allow_control and recipe['status'] == 'failed' and recipe['passed'] is False and recipe['target_completed'] is False
    assert recipe['canonical_assets_unchanged'] is True and recipe['child_exit_code'] == 0
    assert recipe['trace_bytes'] == len(raw) and recipe['trace_sha256'] == sha(raw)
    for field, name in (('producer_sha256', 'producer.py'), ('input_route_sha256', 'input-route.py'),
                        ('capture_contract_sha256', 'capture-contract.py')):
        assert recipe[field] == sha((capture / name).read_bytes())
    assert recipe['process_memory_writes'] == recipe['injected_instructions'] == recipe['process_pauses'] == 0
    assert recipe['clock_or_irq_state_seeded'] is False and recipe['gameplay_state_seeded'] is False
    assert recipe['host_build']['guest_instruction_patches'] == 0 and recipe['host_build']['cpu_source_unchanged'] is True
    for field, name in (
        ('probe_sha256', 'lezac_work_probe.h'), ('patch_sha256', 'dos_time_hook.patch'),
        ('clock_patch_sha256', 'clock_hook.patch'), ('clock_api_sha256', 'lezac_clock_observation.h'),
    ):
        assert recipe['host_build'][field] == sha(Path(__file__).with_name(name).read_bytes())
    exe = executable.read_bytes()
    assert sha(exe) == recipe['executable_sha256'] == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    mz = struct.unpack_from('<14H', exe)
    assert mz[4] * 16 == 0x770
    expected = bytearray(exe[0x770:])
    for index in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + index * 4)
        address = segment * 16 + offset
        struct.pack_into('<H', expected, address, (struct.unpack_from('<H', expected, address)[0] + recipe['code_segment']) & 65535)
    sample_proofs = []
    for sample in recipe['samples']:
        assert Path(sample['name']).name == sample['name']
        compressed = (capture / (sample['name'] + '.ram.gz')).read_bytes()
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            ram = stream.read(1048577)
        assert len(ram) == 1048576
        assert sample['ram_sha256'] == sha(ram) and sample['ram_gzip_sha256'] == sha(compressed)
        assert sample['code_bytes_verified'] == 43552 and sample['code_differences'] == 0
        start = recipe['code_segment'] * 16
        assert ram[start:start + 43552] == expected[:43552]
        png = (capture / (sample['name'] + '.png')).read_bytes()
        assert sample['png_sha256'] == sha(png)
        sample_proofs.append(dict(name=sample['name'], ram_sha256=sha(ram), png_sha256=sha(png), code_bytes_verified=43552))
    cpu, clock, cases = projections(raw, recipe)
    assert not completed_target or sum(len(case['deliveries']) for case in cases) > 0
    out.mkdir()
    (out / 'cpu.bin').write_bytes(cpu)
    (out / 'clock.bin').write_bytes(clock)
    record = dict(source_capture_status=recipe['status'], source_trace_terminal=True, complete_target_capture_claim=completed_target,
        raw_samples_verified=sample_proofs, cases=len(cases), calls=[case['call'] for case in cases],
        states=sum(len(case['states']) for case in cases), observed_irq_boundaries=sum(len(case['deliveries']) for case in cases),
        trace_sha256=sha(raw), cpu_projection_sha256=sha(cpu), clock_projection_sha256=sha(clock),
        later_cpu_flags_or_irq_states_injected=False, raw_memory_published=False)
    (out / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--allow-control', action='store_true')
    args = parser.parse_args()
    project(args.capture, args.out, args.exe, args.allow_control)
