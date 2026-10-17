"""Project original full-pacing CPU states; observed IRQ boundaries are external inputs."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct

from .trace import inspect_trace, rows

ROOT = Path(__file__).resolve().parents[2]
REGISTERS = 'ax bx cx dx si di bp cs ds es ss sp ip'.split()
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def projections(path, recipe):
    checked = inspect_trace(path)
    assert checked['validated_target_completed'] and checked['pacing_windows'] == recipe['pacing_windows']
    for field in ('trace_end_marker', 'trace_uncompressed_bytes', 'trace_uncompressed_sha256'):
        assert checked[field] == recipe[field]
    cases = []
    output = bytearray(b'LZFPAC01' + struct.pack('<I', len(checked['pacing_windows'])))
    metadata = {}
    entry = previous = None
    packed = bytearray()
    events, deliveries = [], []
    count = 0
    for item in rows(path, metadata):
        kind = item['kind']
        if kind == 'identified':
            continue
        if kind == 'pacing_enter':
            assert entry is None
            entry = item
            packed, events, deliveries, count, previous = bytearray(), [], [], 0, None
            assert int(entry['return_cs']) == int(entry['cs']) == recipe['code_segment']
            assert int(entry['psp']) == recipe['code_segment'] - 16
            assert int(entry['vector_cs']) == 0xf000 and int(entry['return_ip']) == 0x79e8
            continue
        assert entry and int(item['call']) == int(entry['call'])
        r = {key: int(item[key]) for key in REGISTERS}
        if previous:
            op = bytes.fromhex(previous['opcode'])
            if op[0] in (0xe4, 0xe6):
                assert op[1] in ((0x61,) if op[0] == 0xe4 else (0x20, 0x61, 0x42, 0x43))
                events.append((op[0] == 0xe6, op[1], int(previous['ax']) & 255 if op[0] == 0xe6 else r['ax'] & 255))
        assert int(item['defined_flags']) == 0x700
        assert item['stack_base'] == entry['stack_base'] and int(item['stack_ss']) == int(entry['ss'])
        assert r['ss'] == int(entry['ss'])
        assert int(item['clock']) == int(item['pic_ticks']) * 6000 + 6000 - int(item['cpu_left']) - int(item['cpu_cycles'])
        if (r['cs'], r['ip']) == (0xf000, 0xfea5):
            deliveries.append(count)
        packed.extend(struct.pack('<13H4I2BI', *[r[key] for key in REGISTERS], int(item['flags']), int(item['defined_flags']),
            int(item['bios_ticks']), int(item['psp_stack']), int(item['motor']), int(item['drive']), len(events)))
        for key in ('stack', 'globals', 'frame_globals', 'display_globals', 'pacing_globals'):
            packed.extend(bytes.fromhex(item[key]))
        count += 1
        if kind == 'pacing_return':
            assert 16 <= count <= 250001 and r['sp'] == int(entry['sp'])
            assert (r['cs'], r['ip']) == (recipe['code_segment'], 0x79e8)
            assert bool(deliveries) == (item['target_completed'] == '1')
            offset, segment = struct.unpack_from('<HH', bytes.fromhex(entry['globals']), 5)
            bank = bytes.fromhex(entry['bank'])
            output.extend(struct.pack('<12HB3I', recipe['code_segment'], int(entry['vector_ip']), int(entry['psp']), int(entry['ss']),
                int(entry['sp']), int(entry['stack_base']), 128, segment, offset, len(bank), int(entry['int1c_ip']), int(entry['int1c_cs']),
                0, count, len(events), len(deliveries)))
            for index in deliveries:
                output.extend(struct.pack('<I', index))
            output.extend(bank + packed)
            for event in events:
                output.extend(struct.pack('<BHB', *event))
            cases.append(dict(window=int(entry['call']), states=count, observed_irq_boundaries=deliveries, io_events=len(events)))
            entry = None
        previous = item
    assert entry is None and metadata == {key: checked[key] for key in metadata}
    assert len(cases) == len(checked['pacing_windows'])
    return bytes(output), cases


def project(capture, out, executable):
    capture = capture.resolve(strict=True)
    out = out.resolve()
    assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
    recipe = json.loads((capture / 'report.json').read_bytes())
    trace = capture / 'guest-pacing.csv.gz'
    assert recipe['status'] == 'observed' and recipe['passed'] is True and recipe['target_completed'] is True
    assert recipe['validated_target_completed'] is True and recipe['canonical_assets_unchanged'] is True and recipe['child_exit_code'] == 0
    compressed = trace.read_bytes()
    assert recipe['trace_bytes'] == len(compressed) and recipe['trace_sha256'] == sha(compressed)
    for field, name in [('producer_sha256','producer.py'), ('input_route_sha256','input-route.py'),
                        ('capture_contract_sha256','capture-contract.py')]:
        assert recipe[field] == sha((capture / name).read_bytes())
    assert recipe['trace_parser_sha256'] == sha(Path(__file__).with_name('trace.py').read_bytes())
    assert recipe['callback_boundary_probe'] is False
    assert recipe['process_memory_writes'] == recipe['injected_instructions'] == recipe['process_pauses'] == 0
    assert recipe['clock_or_irq_state_seeded'] is False and recipe['gameplay_state_seeded'] is False
    assert recipe['host_build']['guest_instruction_patches'] == 0 and recipe['host_build']['cpu_source_unchanged'] is True
    for field, name in [('probe_sha256','lezac_work_probe.h'), ('patch_sha256','dos_time_hook.patch'),
                        ('clock_patch_sha256','clock_hook.patch'), ('clock_api_sha256','lezac_clock_observation.h')]:
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
    proofs = []
    for sample in recipe['samples']:
        assert Path(sample['name']).name == sample['name']
        raw = (capture / (sample['name'] + '.ram.gz')).read_bytes()
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            ram = stream.read(1048577)
        assert len(ram) == 1048576 and sha(ram) == sample['ram_sha256'] and sha(raw) == sample['ram_gzip_sha256']
        start = recipe['code_segment'] * 16
        assert ram[start:start+43552] == expected[:43552]
        assert sample['code_bytes_verified'] == 43552 and sample['code_differences'] == 0
        png = (capture / (sample['name'] + '.png')).read_bytes()
        assert sha(png) == sample['png_sha256']
        proofs.append(dict(name=sample['name'], ram_sha256=sha(ram), png_sha256=sha(png), code_bytes_verified=43552))
    cpu, cases = projections(trace, recipe)
    out.mkdir()
    (out / 'cpu.bin').write_bytes(cpu)
    record = dict(cases=cases, states=sum(case['states'] for case in cases), raw_samples_verified=proofs,
        cpu_sha256=sha(cpu), trace_sha256=sha(compressed), original_capture_target_completed=True,
        observed_irq_boundaries_are_external_inputs=True, irq_eligibility_predicted=False,
        later_cpu_flags_or_memory_injected=False, whole_game_parity=False,
        legacy_trace_clock_label_inaccurate=True, actual_callback_boundary_probe=False)
    (out / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--exe', type=Path, required=True)
    args = parser.parse_args()
    project(args.capture, args.out, args.exe)
