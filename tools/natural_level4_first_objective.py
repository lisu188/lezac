"""Original-backed ordinary Level 4 first-objective production replay."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

import level1_fidelity as fidelity
import level1_handoff as handoff
import level1_original as original
import natural_campaign as campaign
import natural_level3_handoff as recovered

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level4_first_objective'
EVIDENCE = ROOT / 'docs/recovery/evidence/natural_level4_first_objective_20261007'
FIRST, LAST, ENTRY, OBJECTIVE = 8905, 9760, 9422, 9680
MANIFEST_SHA256 = '3d368a8c4513bf9fb2773f6b75d910f95b599dd63d9a81af8df4ccc0442c2352'
ROUTE_SHA256 = 'a58ae584bf24044d7b437e0e0f54a1a5b91fb35c4f31b3fb346a0ae12a1c132a'
CLAIMS = dict(full_prefix_cpp_comparison_claim=False, full_actor_clock_sound_byte_parity=False,
    level4_completion_claim=False, original_fidelity_claim=False, port_functionally_complete=False)
require = fidelity.require


def manifest():
    path = EVIDENCE / 'manifest.json'
    require(fidelity.sha256(path) == MANIFEST_SHA256, 'untrusted Level 4 evidence manifest')
    result = fidelity.strict_json(path.read_text())
    require(result['schema'] == 'lezac-native-level4-first-objective-evidence-v1' and
            result['expected_bytes_source'] == 'original_only' and result['closed_native_sessions'] is True and
            result['all_raw_members_independently_retained'] is True and
            result['snapshot_coherence_differences'] == result['normalized_bytes'] == 0,
            'Level 4 native evidence scope differs')
    return result


def check_producers(blobs, expected):
    require(set(blobs) == set(expected), 'Level 4 producer inventory differs')
    for name, digest in expected.items():
        require(hashlib.sha256(blobs[name]).hexdigest() == digest, 'untrusted Level 4 producer: ' + name)


def check_route(path):
    require(fidelity.sha256(path) == ROUTE_SHA256, 'Level 4 route fingerprint differs')
    settings, events = fidelity.read_route(path)
    prefix_settings, prefix = recovered.check_route(recovered.FIXTURE / 'route.txt')
    require(settings == {**prefix_settings, 'ticks': LAST} and
            {tick: rows for tick, rows in events.items() if tick < 9450} == prefix,
            'Level 4 ordinary handoff prefix differs')
    return settings, events


def keys():
    return [('gate', FIRST, phase) for phase in ('present', 'post_update')] + \
        [('result', index, 'result') for index in range(76, 134)] + \
        [('ack', 9301, 'present'), ('intro', 9421, 'present')] + \
        [('level4', tick, phase) for tick in range(ENTRY, LAST + 1) for phase in ('present', 'post_update')]


def validate(rows, header):
    require(len(rows) == 742 and rows[0] == header and
            rows[-1] == dict(kind='complete', frames=400, boundaries=740, patches_restored=True),
            'Level 4 reference contract differs')
    require(header['frames'] == 400 and header['boundaries'] == 740 and header['raw_ds_boundaries'] == 1078 and
            header['completed_levels'] == [1, 2, 3] and header['entered_level'] == 4 and
            header['cpp_expectations_used'] is False and header['state_injections'] is False and
            all(header[key] is value for key, value in CLAIMS.items()), 'Level 4 reference claim differs')
    indexed = {}
    for key, row in zip(keys(), rows[1:-1]):
        section, index, phase = key
        require(set(row) == {'kind', 'section', 'index', 'phase', 'projection', 'rgb_sha256'} and
                row['kind'] == 'boundary' and (row['section'], row['index'], row['phase']) == key,
                'Level 4 reference order differs')
        fields = {'mapped', 'lifecycle'}
        if section not in ('ack', 'intro'):
            fields |= {'monsters', 'markers'}
            if key != ('gate', FIRST, 'present'):
                fields.add('terrain')
        mapped = row['projection']['mapped']
        require(set(row['projection']) == fields and mapped['level'] == (4 if section in ('intro', 'level4') else 3) and
                mapped['frame'] == (index - 1623 if section == 'level4' else 7798) and
                (row['rgb_sha256'] is None) == (phase == 'post_update'), 'Level 4 projection scope differs')
        if row['rgb_sha256'] is not None:
            require(len(row['rgb_sha256']) == 64 and len(bytes.fromhex(row['rgb_sha256'])) == 32,
                    'invalid native RGB fingerprint')
        if section == 'level4':
            collected = int(index > OBJECTIVE or (index == OBJECTIVE and phase == 'post_update'))
            require(mapped['progress'][0] == collected, 'native first-objective timing differs')
        indexed[key] = mapped
    pickup = indexed['level4', OBJECTIVE, 'post_update']
    require(pickup['progress'] == [1, 29] and pickup['score'] == 47590 and
            pickup['players'][0]['xy'] == [603.0, 400.0] and pickup['players'][0]['energy'] == 42 and
            pickup['players'][0]['reserve'] == 0 and pickup['players'][0]['inventory'] == [200, 9, 0, 0, 1],
            'native first-objective state differs')
    final = indexed['level4', LAST, 'post_update']
    require(final['progress'] == [1, 105] and final['score'] == 47590 and final['rng'] == 4160656211 and
            final['players'][0]['xy'] == [603.0, 400.0] and final['players'][0]['energy'] == 38 and
            final['players'][0]['reserve'] == 0 and final['players'][0]['inventory'] == [200, 9, 0, 0, 1],
            'native Level 4 endpoint differs')


def fixture(root=FIXTURE):
    evidence = manifest()
    blobs = {name: gzip.decompress((EVIDENCE / (name + '.gz')).read_bytes())
             for name in evidence['producer_pins']}
    check_producers(blobs, evidence['producer_pins'])
    coherence = fidelity.strict_json(blobs['native-coherence-v1.json'].decode())
    require(coherence['boundaries'] == 1078 and coherence['differing_byte_observations'] == coherence['normalized_bytes'] == 0 and
            coherence['raw_sha256'] == evidence['raw_native_sha256'] and
            coherence['journal_sha256'] == evidence['raw_native_journal_sha256'], 'native coherence audit differs')
    closed = fidelity.strict_json(blobs['closed-controls-retention-complete.json'].decode())
    require(closed['retention']['all_notes_tree_anchors_verified'] and closed['raw_dependency']['all_member_readback_verified'],
            'native closed-control retention differs')
    for name, digest in evidence['fixture_pins'].items():
        require(fidelity.sha256(root / name) == digest, 'Level 4 fixture fingerprint differs: ' + name)
    check_route(root / 'route.txt')
    rows = handoff.load(root / 'reference.jsonl.gz')
    validate(rows, evidence['reference_header'])
    require(rows[0]['assets'] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS},
            'Level 4 shipped assets differ')
    return rows


def compare(cpp):
    report = recovered.compare(cpp, fixture(), last=LAST, route_validator=check_route, expected_frames=400)
    return {**report, 'first_objective_tick': OBJECTIVE, 'level4_frames': 339,
            'raw_coherent_boundaries': 1078, **CLAIMS}


def replay(exe, out):
    out.mkdir(parents=True, exist_ok=True)
    cpp = out.resolve() / ('run-' + uuid.uuid4().hex)
    assets = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
    command = [str(exe.resolve()), '--replay-level1-scout', str(FIXTURE / 'route.txt'), str(cpp), str(FIRST),
               '--original-intro-wait', '--result-reels']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=550,
        env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                 LEZAC_LOAD_JSON_ASSETS='0', LEZAC_LOAD_ORIGINAL_ASSETS='1'))
    require(cpp.is_dir(), 'C++ Level 4 replay produced no evidence')
    for name, data in (('stdout.txt', result.stdout), ('stderr.txt', result.stderr)):
        (cpp / name).write_text(data, encoding='utf-8')
    (cpp / 'command.json').write_bytes(original.json_bytes(dict(command=command, source=fidelity.source_version(ROOT),
        executable_sha256=fidelity.sha256(exe), assets=assets, audio='dummy', video='dummy', state_injections=False,
        replay_reader_sha256=fidelity.sha256(Path(__file__)), **CLAIMS)))
    require(result.returncode == 0, 'C++ Level 4 replay failed: ' + result.stderr.strip())
    shutil.copyfile(FIXTURE / 'route.txt', cpp / 'route.txt')
    require(assets == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, 'Level 4 replay changed shipped assets')
    report = compare(cpp)
    (cpp / 'comparison.json').write_bytes(original.json_bytes(report))
    return report


def guard():
    rows, evidence = fixture(), manifest()
    pickup_index = 1 + keys().index(('level4', OBJECTIVE, 'post_update'))
    edits = [lambda r: r.pop(1), lambda r: r.insert(1, copy.deepcopy(r[1])),
        lambda r: r[-1].__setitem__('patches_restored', False),
        lambda r: r[1].__setitem__('rgb_sha256', None), lambda r: r[1].__setitem__('index', FIRST - 1),
        lambda r: r[-2]['projection']['mapped'].__setitem__('score', 0),
        lambda r: r[pickup_index]['projection']['mapped']['players'][0].__setitem__('energy', 0),
        lambda r: r[pickup_index]['projection']['mapped']['progress'].__setitem__(0, 0),
        lambda r: r[-2]['projection'].__setitem__('extra', 1)]
    edits += [lambda r, key=key: r[0].__setitem__(key, True) for key in (*CLAIMS, 'state_injections', 'cpp_expectations_used')]
    rejected = 0
    for edit in edits:
        changed = copy.deepcopy(rows)
        edit(changed)
        require(changed != rows, 'vacuous Level 4 reference mutation')
        try:
            validate(changed, evidence['reference_header'])
        except fidelity.EvidenceError:
            rejected += 1
        else:
            raise fidelity.EvidenceError('Level 4 reference mutation accepted')
    blobs = {name: gzip.decompress((EVIDENCE / (name + '.gz')).read_bytes()) for name in evidence['producer_pins']}
    for name in blobs:
        changed = {**blobs, name: blobs[name] + b' '}
        try:
            check_producers(changed, evidence['producer_pins'])
        except fidelity.EvidenceError:
            pass
        else:
            raise fidelity.EvidenceError('Level 4 producer mutation accepted')
    with tempfile.TemporaryDirectory(prefix='lezac-level4-guard-') as temporary:
        root = Path(temporary)
        for name in ('route.txt', 'guard-input.json'):
            shutil.copyfile(FIXTURE / name, root / name)
        raw = (FIXTURE / 'reference.jsonl.gz').read_bytes()
        for changed in (raw[:-1], raw + b'\0', bytes([raw[0] ^ 1]) + raw[1:]):
            (root / 'reference.jsonl.gz').write_bytes(changed)
            try:
                fixture(root)
            except fidelity.EvidenceError:
                rejected += 1
            else:
                raise fidelity.EvidenceError('Level 4 fixture byte mutation accepted')
    typed = campaign.guard_projection(fidelity.strict_json((FIXTURE / 'guard-input.json').read_text()),
                                     rows[-2]['projection']['mapped'])
    return dict(status='guarded', mutations_rejected=rejected, producer_mutations_rejected=len(blobs),
                typed_field_mutations_rejected=typed, **CLAIMS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('replay', 'compare', 'guard'))
    for name in ('exe', 'out', 'cpp'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if args.command == 'replay':
        require(args.exe is not None and args.out is not None, 'Level 4 executable/output required')
        report = replay(args.exe, args.out)
    elif args.command == 'compare':
        require(args.cpp is not None, 'Level 4 C++ evidence required')
        report = compare(args.cpp)
    else:
        report = guard()
    print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
