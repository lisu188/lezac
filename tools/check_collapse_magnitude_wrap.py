"""Check seeded original collapse updates at the wrapped magnitude boundary."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/collapse_magnitude_wrap_original.json.gz'
FIXTURE_SHA = '050cdf626e72b03f2d2030375bcb067518f35aedc9cd061552af0562046205c6'
EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
LIB_SHA = 'ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c'
PREVIOUS = (0, 1, 62, 63, 64, 65, 127, 255, 256, 32767, 32768, 32769, 65471, 65472, 65473, 65534, 65535)
OFFSETS = (0x555a, 0x555d, 0x5561, 0x5565, 0x5569, 0x556a, 0x556c, 0x556e,
           0x5571, 0x5576, 0x5578, 0x557b, 0x5581, 0x5586, 0x5589)
CLAIMS = dict(seeded=True, natural_route=False, full_frame_claim=False, whole_game_fidelity_claim=False)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(value):
    require(value['schema'] == 'lezac-collapse-magnitude-wrap-v1' and
            value['expected_bytes_source'] == 'original_only' and value['cpp_expectations_used'] is False,
            'collapse magnitude oracle scope differs')
    native = value['native_report']
    require(native['cases'] == 17 and native['exe_sha256'] == EXE_SHA and
            native['unicorn_version'] == '2.1.4' and native['library_sha256'] == LIB_SHA and
            native['initial_memory_controlled'] is True and native['natural_route'] is False and
            native['instruction_patches'] == native['calls_stubbed'] == native['full_guest_ram_exports'] == 0 and
            native['observer_control_passed'] is True and native['observer_control_full_memory_bytes'] == 1048576 and
            native['observer_control_registers'] == 14 and native['full_frame_claim'] is False and
            native['whole_game_fidelity_claim'] is False, 'collapse magnitude native producer differs')
    producers = value['producers']
    require(set(producers) == {'capture-collapse-wrap-t303.py', 'original_bomb_cpu.py', 'frame_camera_oracle.py',
                              'rea-level4-fracture-t303.py', 'rea_prefix_audit.py'}, 'collapse magnitude source domain differs')
    for name, source in producers.items():
        require(sha(source['text'].encode()) == source['sha256'], 'collapse magnitude frozen source differs: ' + name)
    require(native['producer_sha256'] == producers['capture-collapse-wrap-t303.py']['sha256'] and
            native['helper_sha256'] == producers['original_bomb_cpu.py']['sha256'] ==
                'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c',
            'collapse magnitude producer binding differs')
    require(set(value['assets']) == {'LEZAC.EXE', 'LIVELS.SCH', 'tests/fixtures/fracture_actor_original.txt'},
            'collapse magnitude asset domain differs')
    for name, pin in value['assets'].items():
        raw = (ROOT / name).read_bytes()
        require(len(raw) == pin['bytes'] and sha(raw) == pin['sha256'], 'collapse magnitude asset differs: ' + name)
    image = (ROOT / 'LEZAC.EXE').read_bytes()
    require(len(image) == 52384 and sha(image) == EXE_SHA, 'collapse magnitude original executable differs')
    rea, instructions = value['rea']['report'], value['rea']['byte_checks']
    require(rea['status'] == 'completed' and rea['target_preserved'] is True and rea['session_closed'] is True and
            rea['server_exit_code'] == 0 and rea['target_sha256'] == EXE_SHA and rea['rea_version'] == '6.7.0' and
            rea['provider']['id'] == 'ghidra' and rea['provider']['version'] == '12.1.4' and
            rea['source_sha256'] == producers['rea_prefix_audit.py']['sha256'], 'collapse magnitude REA closure differs')
    require(tuple(row['offset'] for row in instructions) == OFFSETS, 'collapse magnitude instruction extent differs')
    for row in instructions:
        code = bytes.fromhex(row['decoded']['bytes'])
        require(row['bytes_equal'] is True and code == image[0x770 + row['offset']:0x770 + row['offset'] + len(code)],
                'collapse magnitude instruction bytes differ')
    for offset, target in ((0x5586, 0x1165a), (0x5589, 0x14fda)):
        call = value['rea']['calls'][str(offset)]['result']['structuredContent']['normalized_result']
        require(call['status'] == 'direct' and [item['address'] for item in call['targets']] == [hex(target)],
                'collapse magnitude original call target differs')
    cases, records = value['cases'], native['records']
    require(tuple(row['previous'] for row in cases) == PREVIOUS and
            tuple(row['previous'] for row in records) == PREVIOUS, 'collapse magnitude case extent differs')
    inputs, outputs = [], []
    for case, record in zip(cases, records):
        incoming, expected = bytes.fromhex(case['input_hex']), bytes.fromhex(case['output_hex'])
        require(len(incoming) == 801 and struct.unpack_from('<HHHIHHHH', incoming) ==
                (16, 16, 0, 0x12345678, 0, 1, 0, 0x4000) and
                struct.unpack_from('<H', incoming, 18 + 768 + 10)[0] == case['previous'],
                'collapse magnitude input geometry differs')
        require(sha(incoming) == record['input_sha256'] and sha(expected) == record['output_sha256'],
                'collapse magnitude original case bytes differ')
        fragments, live, destroyed, next_word = struct.unpack_from('<4H', expected, 4)
        require(len(expected) == 12 + 768 + 11 * fragments + 15 * live and
                destroyed == record['destroyed'] and live == record['collapse_count'] and
                next_word == 0x4000 + destroyed and len(record['registers']) == 14 and
                len(bytes.fromhex(record['full_memory_sha256'])) == 32,
                'collapse magnitude original state extent differs')
        require((destroyed, live) == ((0, 1) if case['previous'] in (0, 1, 62, 63, 65473, 65534, 65535) else (2, 0)),
                'collapse magnitude original threshold differs')
        inputs.append(incoming)
        outputs.append(expected)
    incoming = b'LZCU0001' + struct.pack('<I', 17) + b''.join(inputs)
    expected = b''.join(outputs)
    require(sha(incoming) == native['input_sha256'] and sha(expected) == native['expected_sha256'],
            'collapse magnitude aggregate differs')
    return incoming, expected


def fixture():
    raw = FIXTURE.read_bytes()
    require(sha(raw) == FIXTURE_SHA, 'collapse magnitude fixture fingerprint differs')
    return validate(json.loads(gzip.decompress(raw)))


def compare(actual, expected):
    require(actual == expected, 'collapse magnitude App differs at byte ' + str(next(
        (index for index, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]), min(len(actual), len(expected)))))


def replay(exe, out):
    case = out.resolve() / ('run-' + uuid.uuid4().hex)
    case.mkdir(parents=True)
    report = dict(status='failed', **CLAIMS)
    try:
        incoming, expected = fixture()
        (case / 'input.bin').write_bytes(incoming)
        (case / 'expected.bin').write_bytes(expected)
        command = [str(exe.resolve()), '--debug-original-collapse-update', str(case / 'input.bin'), str(case / 'actual.bin')]
        report.update(command=command, executable_sha256=sha(exe.read_bytes()), reader_sha256=sha(Path(__file__).read_bytes()))
        try:
            child = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=90,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'))
        except subprocess.TimeoutExpired as error:
            (case / 'stdout.log').write_bytes(error.stdout or b'')
            (case / 'stderr.log').write_bytes(error.stderr or b'')
            report.update(timed_out=True, exit_code=None, owned_child_terminal=True)
            raise
        report.update(exit_code=child.returncode, owned_child_terminal=True)
        (case / 'stdout.log').write_bytes(child.stdout)
        (case / 'stderr.log').write_bytes(child.stderr)
        require(child.returncode == 0 and child.stdout.strip() == b'original_collapse_update=ok cases=17' and
                not child.stderr, 'collapse magnitude App diagnostic failed')
        compare((case / 'actual.bin').read_bytes(), expected)
        report.update(status='match', cases=17, compared_bytes=len(expected), expected_bytes_source='original_only')
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        (case / 'report.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.exe is None:
        _, expected = fixture()
        report = dict(status='fixture_verified', cases=17, expected_bytes=len(expected), **CLAIMS)
    else:
        require(args.out is not None, 'collapse magnitude output directory required')
        report = replay(args.exe, args.out)
    print(json.dumps(report, sort_keys=True, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
