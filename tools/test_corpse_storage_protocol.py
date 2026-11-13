"""Reject malformed corpse fixture requests through the compiled helper or App."""
import argparse
import gzip
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

HEADER = 12 + 1980 + 3960 + 368
STATE = 1593


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--production-app', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    request = gzip.decompress((args.root / 'tests/fixtures/corpse_storage/requests.bin.gz').read_bytes())
    golden = gzip.decompress((args.root / 'tests/fixtures/corpse_storage/expected.bin.gz').read_bytes())
    header = request[:8] + struct.pack('<I', 1) + request[12:HEADER]
    seed = request[HEADER + 1:HEADER + 1 + STATE]
    valid = header + b'S' + seed
    tests = dict(empty=b'', short_magic=valid[:7], wrong_magic=b'BROKEN01' + valid[8:], short_count=valid[:11],
        zero_count=valid[:8] + bytes(4), excessive_count=valid[:8] + struct.pack('<I', 100001),
        short_header=valid[:HEADER - 1], short_seed=valid[:-1], trailing_byte=valid + b'!',
        unknown_command=header + b'X', update_before_seed=header + b'U\x00\x00',
        missing_next_operation=valid[:8] + struct.pack('<I', 2) + valid[12:],
        short_update=valid[:8] + struct.pack('<I', 2) + valid[12:] + b'U\x00')
    for label, offset, value in (
        ('actor_count', 1570, 31), ('empty_pool', 1570, 0), ('visual_count', 1571, 4),
        ('link_count_mismatch', 1572, 1), ('player2_visual', 1, 2), ('pending_bonus', 1579, 8),
        ('alive_gate', 1583, 1), ('sound_active_flag', 1592, 2),
        ('kind', 38, 0x12), ('behavior', 38 + 21, 5),
        ('reserved_visual', 38 + 1, 1), ('outside_visual', 38 + 1, 33),
        ('active_cursor', 38 + 22, 92), ('active_first', 38 + 23, 0), ('active_last', 38 + 24, 92),
        ('active_mode', 38 + 27, 4), ('active_step', 38 + 28, 0),
        ('backup_cursor', 38 + 29, 92), ('backup_mode', 38 + 34, 4), ('backup_step', 38 + 35, 0)):
        changed = bytearray(seed); changed[offset] = value
        tests[label] = header + b'S' + changed
    linked = bytearray(seed); linked[1442 + 15] = linked[1572] = 1
    tests['unsupported_active_links'] = header + b'S' + linked
    duplicate = bytearray(seed)
    duplicate[1570], duplicate[1571] = 2, 4
    duplicate[76:114] = duplicate[38:76]
    tests['duplicate_visual_reference'] = header + b'S' + duplicate
    second = bytearray(duplicate); second[77] = 3
    tests['two_corpses'] = header + b'S' + second
    args.out.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='corpse-protocol-app-' if args.production_app else 'corpse-protocol-helper-', dir=args.out))
    report = dict(passed=False, production_app=args.production_app, rejected=[], commands=[], seeded=True, natural_route=False, whole_game_claim=False)
    try:
        for label, raw in [('valid_seed', valid), *tests.items()]:
            request_path, actual_path = directory / (label + '.request.bin'), directory / (label + '.actual.bin')
            request_path.write_bytes(raw)
            command = [str(args.exe.resolve())] + (['--debug-corpse-storage-original'] if args.production_app else [])
            command += [str(request_path), str(actual_path)]
            result = subprocess.run(command, capture_output=True, timeout=30,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1'))
            (directory / (label + '.stdout')).write_bytes(result.stdout)
            (directory / (label + '.stderr')).write_bytes(result.stderr)
            report['commands'].append(dict(label=label, args=command, returncode=result.returncode))
            if label == 'valid_seed':
                assert result.returncode == 0
                assert actual_path.read_bytes() == b'LZCO0001' + struct.pack('<I', 1) + golden[12:12 + STATE]
            else:
                assert result.returncode != 0, 'malformed request accepted: ' + label
                report['rejected'].append(label)
        report['passed'] = True
    finally:
        (directory / 'protocol.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print('corpse_storage_protocol=ok rejected=%d production_app=%d report=%s' %
          (len(tests), args.production_app, directory / 'protocol.json'))


if __name__ == '__main__':
    main()
