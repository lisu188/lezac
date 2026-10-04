"""Verify original behavior-2 writeback provenance and real C++ replay."""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tarfile
import tempfile

import capture_original_timed_writeback as producer
from check_monster_writeback_fixture import require
from check_flyer_contact_fixture import retained_file
from level1_fidelity import safe_file, strict_json

ROOT = Path(__file__).resolve().parent.parent
COUNT, ROW_SIZE = 1184, 80
SIZE = 64 + COUNT * ROW_SIZE
FIXTURE_SHA = 'a92403df344368bb2975fd570d25dbb37dd4bc9d7ae755905cb9a8ae4b8bccb2'
ARCHIVE_SHA = '2b249ee5799ccdc1984ac729201d7785b285be5da9eee8d16fbb03f8918b21f8'
INPUT, MOTION = struct.Struct('<HBBBBhhhhBBHBB'), struct.Struct('<hhhhBBI')


def header():
    windows = b''.join(struct.pack('<HH', at, len(raw)) + raw for at, raw in sorted(producer.WINDOWS.items()))
    return (b'LZTWv1\0\0' + struct.pack('<HHHH', COUNT, ROW_SIZE, 0x701C, 0x777F) +
            bytes.fromhex(producer.flyers.base.EXE_SHA) + hashlib.sha256(windows).digest()[:16])


def edge_mask(case):
    return sum(bit for bit in (1, 2, 4, 8) if case['edge_mask'] & bit and
               1 <= case['glyph'] <= (0x52 if bit == 8 else 0x4C))


def input_bytes(case):
    return INPUT.pack(case['index'], case['kind'], case['glyph'], case['edge_mask'], 11,
                      case['x'], case['y'], case['vx'], case['vy'], 165, 90, case['frame'],
                      edge_mask(case), case['profile'])


def validate(data, exe):
    require(len(data) == SIZE and hashlib.sha256(data).hexdigest() == FIXTURE_SHA, 'timed writeback fixture extent/hash differs')
    require(data[:64] == header() and hashlib.sha256(exe).hexdigest() == producer.flyers.base.EXE_SHA,
            'timed writeback header/original differs')
    for at, raw in producer.WINDOWS.items():
        require(exe[0x770 + at:0x770 + at + len(raw)] == raw, 'original timed writeback window differs')
    for index, case in enumerate(producer.CASES):
        at = 64 + index * ROW_SIZE
        require(data[at:at + INPUT.size] == input_bytes(case), 'timed writeback input coverage/order differs')
        x, y, vx, vy, fx, fy, rng = MOTION.unpack_from(data, at + 20)
        actor, visual = data[at + 34:at + 72], data[at + 72:at + 80]
        expected = bytearray(producer.seed_actor(case))
        expected[2] = 11 - (case['frame'] & 1)
        struct.pack_into('<hhHH', expected, 6, vx, vy, fx, fy)
        descriptor = bytes.fromhex('110aa82d' if case['kind'] == 12 else '0808fc36')
        require(actor == expected and visual == struct.pack('<hh', x, y) + descriptor and rng == 0x12345678,
                'timed actor/visual/timer/RNG writeback differs')


def capture_bytes(directory, producer_file, helper_file):
    report = strict_json((directory / 'capture.json').read_text(encoding='utf-8'))
    discovery = report['schema'] == 'lezac-timed-writeback-discovery-v1'
    require(report['schema'] in (producer.SCHEMA, 'lezac-timed-writeback-discovery-v1') and
            not (directory / 'failure.json').exists() and report['complete'] is True and
            report['case_count'] == len(report['cases']) == COUNT and report['kind_coverage'] == [12, 13] and
            report['profile_coverage'] == list(range(10)), 'native timed writeback failed/incomplete')
    require(report['producer_sha256'] == hashlib.sha256(producer_file.read_bytes()).hexdigest(), 'executed timed producer differs')
    helper_sha = (report['executed_discovery_helper_sha256'] if discovery else
                  report['support_dependencies_sha256']['capture_original_flyer_contacts.py'])
    require(helper_sha == hashlib.sha256(helper_file.read_bytes()).hexdigest(), 'executed timed helper differs')
    require(report['audio_driver'] == 'dummy' and report['owned_child_returncode'] is not None and
            report['hook_free_stack_preserved'] is True and report['selected_actor_parameter_guard'] is True and
            report['unseeded_bootstrap_ticks'] == 1 and report['seeded_case_boundaries'] is True and
            report['seeded_terrain'] is True and report['complete_coordinate_writeback_observed'] is True and
            report['observed_entry_exit'] == [0x701C, 0x777F] and report['hotspot_seed'] == 6 and
            report['timer_seed'] == 11 and report['shared_actor_profiles'] is True and
            all(report[key] is False for key in ('natural_constructor_claim', 'original_fidelity_claim',
                'natural_campaign_claim', 'pixel_parity_claim', 'full_actor_update_parity_claim')),
            'native timed writeback identity/closure/scope differs')
    require(discovery or report['animation_disabled'] is True, 'timed capture animation was not disabled')
    require(report['hooks'] == [[at, raw.hex()] for at, raw in producer.HOOKS] and
            report['instruction_windows'] == {str(at): raw.hex() for at, raw in producer.WINDOWS.items()},
            'timed native instruction windows differ')
    for name, digest in report['files'].items():
        require(hashlib.sha256(safe_file(directory, name).read_bytes()).hexdigest() == digest, 'timed native file differs')
    require(set(report['assets_sha256']) == set(producer.flyers.base.ASSETS), 'timed asset scope differs')
    for name, digest in report['assets_sha256'].items():
        require(hashlib.sha256(safe_file(ROOT, name).read_bytes()).hexdigest() == digest, 'timed source asset differs')
    for name, digest in (report['support_dependencies_sha256'] | report['dependency_sha256']).items():
        if name != 'capture_original_flyer_contacts.py':
            require(hashlib.sha256(safe_file(ROOT / 'tools', name).read_bytes()).hexdigest() == digest, 'timed dependency differs')
    require(strict_json((directory / 'restoration.json').read_text()) ==
            {'hooks_restored': True, 'scratch_restored': True, 'child_retained_stopped': True, 'installed_hooks': 3},
            'timed capture restoration differs')
    data = bytearray(header())
    for case, row in zip(producer.CASES, report['cases']):
        before, after = row['before'], row['after']
        require(row['seed'] == case and bytes.fromhex(row['seeded_actor_hex']) == producer.seed_actor(case), 'timed original seed differs')
        require([before[k] for k in ('x', 'y', 'vx', 'vy', 'frac_x', 'frac_y')] ==
                [case[k] for k in ('x', 'y', 'vx', 'vy', 'frac_x', 'frac_y')], 'timed initial motion differs')
        edges = [int(bool(edge_mask(case) & bit)) for bit in (1, 2, 4, 8)]
        require(before['edges'] == after['edges'] == edges and before['kind'] == after['kind'] == case['kind'] and
                before['behavior'] == after['behavior'] == 2 and before['rng'] == after['rng'] == 0x12345678 and
                before['frame'] == after['frame'] == case['frame'] and before['registers'][:2] == after['registers'][:2] and
                before['registers'][3:] == after['registers'][3:] and after['registers'][2] == after['registers'][1] and
                before['actor_pointer'] == after['actor_pointer'] == [0x1BD4, before['registers'][1]],
                'timed actor/frame/edges/stack identity differs')
        terrain = bytearray(1980)
        for x, y, glyph in case['tiles']:
            terrain[y * 60 + x] = glyph
        require(hashlib.sha256(terrain).hexdigest() == row['terrain_sha256'], 'timed seeded terrain differs')
        for phase in (before, after):
            raw = bytes.fromhex(phase['stack_hex'])
            require(len(raw) == 58 and len(phase['registers']) == 6 and
                    tuple(struct.unpack_from('<h', raw, 58 + at)[0] for at in (-44, -46, -12, -14)) ==
                    tuple(phase[key] for key in ('x', 'y', 'vx', 'vy')) and
                    [raw[42], raw[41]] == [phase['frac_x'], phase['frac_y']] and
                    [raw[58 + at] for at in (-35, -36, -34, -33)] == edges,
                    'timed decoded locals differ from raw stack')
        actor, visual = bytes.fromhex(row['writeback_actor_hex']), bytes.fromhex(row['writeback_visual_hex'])
        require(len(actor) == 38 and len(visual) == 8 and
                struct.unpack_from('<hh', visual) == (after['x'], after['y']) and
                struct.unpack_from('<hhHH', actor, 6) == (after['vx'], after['vy'], after['frac_x'], after['frac_y']),
                'timed actual actor/visual writeback differs')
        data += input_bytes(case) + MOTION.pack(*(after[k] for k in ('x', 'y', 'vx', 'vy', 'frac_x', 'frac_y', 'rng'))) + actor + visual
    result = bytes(data)
    validate(result, (ROOT / 'LEZAC.EXE').read_bytes())
    return result


def check_archive(data):
    path = ROOT / 'docs/recovery/evidence/timed_writeback_20261005/native-captures.tar.gz'
    require(path.stat().st_size == 1288451 and hashlib.sha256(path.read_bytes()).hexdigest() == ARCHIVE_SHA, 'timed retained archive differs')
    with tempfile.TemporaryDirectory(prefix='lezac-timed-writeback-archive-') as directory:
        temporary = Path(directory)
        with tarfile.open(path, 'r:gz') as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            require(len(names) == len(set(names)) == 60 and sum(member.size for member in members) == 16728115,
                    'timed retained archive extent differs')
            for member in members:
                require(member.isfile() and member.size >= 0, 'timed retained archive contains a non-file')
                target = retained_file(temporary, member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                content = archive.extractfile(member).read()
                require(len(content) == member.size, 'timed retained member truncated')
                target.write_bytes(content)
        manifest = strict_json((temporary / 'manifest.json').read_text())
        require(set(manifest) == set(names) - {'manifest.json'}, 'timed retained manifest scope differs')
        for name, item in manifest.items():
            content = retained_file(temporary, name).read_bytes()
            require(len(content) == item['bytes'] and hashlib.sha256(content).hexdigest() == item['sha256'], 'timed retained member differs')
        for label in ('discovery-a', 'discovery-b', 'production-a', 'production-b'):
            discovery = label.startswith('discovery-')
            source = temporary / ('discovery.py' if discovery else 'tools/capture_original_timed_writeback.py')
            helper = temporary / ('discovery-helper.py' if discovery else 'tools/capture_original_flyer_contacts.py')
            require(capture_bytes(temporary / label, source, helper) == data, 'retained timed native capture differs')
        negative, positive = [strict_json((temporary / f'{label}.json').read_text()) for label in ('negative', 'positive')]
        require(negative['returncode'] == 1 and {k: len(v) for k, v in negative['mismatches'].items()} ==
                {'helper': 180, 'caller': 150, 'timer': 0, 'visual': 136} and positive['returncode'] == 0 and
                'cases=1184 helper_updates=1184 caller_updates=1184' in positive['stdout'] and
                negative['audio'] == positive['audio'] == 'dummy', 'timed retained before/after replay differs')
        for values in negative['mismatches'].values():
            require(values == sorted(values) and all(0 <= value < COUNT for value in values), 'timed negative mismatch extent/order differs')
        require(len(set(negative['mismatches']['caller'])) == 145, 'timed negative unique caller coverage differs')
        wanted = 'fatal: timed actor writeback differs ' + ' '.join(key + '=' + ','.join(map(str, negative['mismatches'][key]))
                    for key in ('helper', 'caller', 'timer', 'visual'))
        require(negative['stderr'].strip() == wanted, 'timed negative real CLI stderr differs')
        for label, report in (('negative', negative), ('positive', positive)):
            require(hashlib.sha256((temporary / f'{label}-app.cpp').read_bytes()).hexdigest() == report['app_sha256'] and
                    report['fixture_sha256'] == FIXTURE_SHA, 'timed retained replay source/fixture differs')
    print('timed_writeback_retained_archive=ok captures=4 cases_each=1184 byte_verified=1 negative_preserved=1')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=ROOT / 'tests/fixtures/timed_actor_writeback_original.bin')
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--extract', nargs=2, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--producer-file', type=Path, default=ROOT / 'tools/capture_original_timed_writeback.py')
    parser.add_argument('--helper-file', type=Path, default=ROOT / 'tools/capture_original_flyer_contacts.py')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--replay-exe', type=Path)
    parser.add_argument('--archive', action='store_true')
    args = parser.parse_args()
    if args.extract:
        require(args.output is not None and not args.output.exists(), 'timed extraction needs a fresh output')
        first, second = [capture_bytes(p, args.producer_file, args.helper_file) for p in args.extract]
        require(first == second, 'independent complete timed writebacks differ')
        args.output.write_bytes(first)
        print(f'timed_writeback_extraction=ok cases={COUNT} bytes={SIZE} sha256={hashlib.sha256(first).hexdigest()} independent_runs=2')
        return
    data, exe = args.fixture.read_bytes(), (ROOT / 'LEZAC.EXE').read_bytes()
    validate(data, exe)
    if args.capture:
        require(capture_bytes(args.capture, args.producer_file, args.helper_file) == data, 'timed native capture does not reproduce fixture')
        print('timed_writeback_native_capture=ok cases=1184 fixture_byte_match=1 hooks_restored=1 child_closed=1 audio=dummy')
    elif args.self_test:
        for i in range(SIZE):
            changed = bytearray(data)
            changed[i] ^= 1
            try:
                validate(changed, exe)
            except ValueError:
                continue
            raise AssertionError(f'accepted timed writeback mutation {i}')
        for changed, original in ((data[:-1], exe), (data + b'\0', exe), (data, exe[:-1])):
            try:
                validate(changed, original)
            except ValueError:
                continue
            raise AssertionError('accepted malformed timed writeback fixture/original')
        print(f'timed_writeback_fixture_selftest=ok byte_mutations={SIZE} truncated=1 trailing=1 original_mutation=1')
    elif args.replay_exe:
        command = [str(args.replay_exe.resolve()), '--debug-timed-actor-writeback']
        env = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
        result = subprocess.run([*command, str(args.fixture.resolve())], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        require(result.returncode == 0 and 'cases=1184 helper_updates=1184 caller_updates=1184' in result.stdout, 'timed positive production replay failed')
        mutations = [data[:-1], data + b'\0']
        for at in (0, 8, 12, 16, 48, 64, 66, 67, 68, 69, 70, 78, 84, 98, 122, SIZE - 1):
            changed = bytearray(data)
            changed[at] ^= 1
            mutations.append(changed)
        with tempfile.TemporaryDirectory(prefix='lezac-timed-writeback-guard-') as directory:
            for i, changed in enumerate(mutations):
                path = Path(directory) / f'{i}.bin'
                path.write_bytes(changed)
                result = subprocess.run([*command, str(path)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
                require(result.returncode != 0 and 'timed actor writeback fixture bytes changed' in result.stderr and
                        'timed_actor_writeback=ok' not in result.stdout, f'accepted malformed timed writeback fixture {i}')
        print('timed_writeback_replay_guard=ok positive=1 rejected=18 audio=dummy')
    elif args.archive:
        check_archive(data)
    else:
        print('timed_writeback_fixture=ok cases=1184 bytes=94784 kinds=12,13 profiles=10 timer_parities=2 original_exit=0x777f')


if __name__ == '__main__':
    main()
