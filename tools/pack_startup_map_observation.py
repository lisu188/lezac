"""Pack retained unmodified-original RAM observations into a bounded fixture."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

REPORT_SHA = 'bb2dfd2a2c3e8b1ff9adb970b92c5a5bf3c204ac7bbf919ddf8e637c83773585'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    if sys.flags.optimize:
        raise RuntimeError('optimized Python is unsupported for original fixture packing')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    metadata = args.out.with_suffix('').with_suffix('.json')
    assert not args.out.exists() and not metadata.exists()
    raw = (args.capture / 'report.json').read_bytes()
    assert sha(raw) == REPORT_SHA
    report = json.loads(raw)
    assert report['passed'] and report['process_memory_writes'] == report['injected_instructions'] == 0
    assert not report['gameplay_state_seeded'] and not report['clock_rng_or_heap_seeded']
    assert sha((args.capture / 'producer.py').read_bytes()) == report['source_sha256']
    selected = [report['samples'][0], *report['samples'][2:]]
    assert [sample['name'] for sample in selected] == ['menu-first', 'level1-intro',
                                                     'level1-running-first', 'level1-running-second']
    packed = bytearray(b'LZSM0001' + struct.pack('<I', len(selected)))
    for sample in selected:
        ram = gzip.decompress((args.capture / sample['ram_file']).read_bytes())
        assert len(ram) == 1048576 and sha(ram) == sample['raw_ram_sha256']
        packed += ram
    value = dict(format='lezac-startup-map-observation-v1', original_report_sha256=REPORT_SHA,
        original_producer_sha256=report['source_sha256'], original_exe_sha256=report['executable_sha256'],
        levels_sha256=report['assets']['LIVELS.SCH']['sha256'], samples=selected,
        natural_original_startup_observed=True, memory_writes=0, instruction_patches=0,
        gameplay_state_seeded=False, clock_rng_or_heap_seeded=False,
        frame_aligned=False, natural_reload_history_proven=False, whole_game_complete=False)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(gzip.compress(bytes(packed), mtime=0))
    metadata.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    print(json.dumps(dict(passed=True, ram_images=4, fixture_bytes=args.out.stat().st_size,
        binary_sha256=sha(args.out.read_bytes()), metadata_sha256=sha(metadata.read_bytes()))), flush=True)


if __name__ == '__main__':
    main()
