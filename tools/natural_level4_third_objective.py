"""Original-backed ordinary Level 4 third objective and return-portal replay."""
from __future__ import annotations

import argparse
import copy
import gzip
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
import natural_level4_first_objective as first
import natural_level4_portal as portal

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level4_third_objective'
EVIDENCE = ROOT / 'docs/recovery/evidence/natural_level4_third_objective_20261007'
FIRST, LAST, ENTRY, PORTAL, OBJECTIVE = 8905, 11420, 9422, 11301, 11286
MANIFEST_SHA256 = '17a5f0d6d43e4805028d4afcc75ed44868c4a4b902a9b096b55b671e1379713d'
ROUTE_SHA256 = '00e22cf9842b7ae313f5efe966e948abea665cf42f51d5be1d14aed8195c4240'
CLAIMS = first.CLAIMS
require = fidelity.require


def manifest():
    path = EVIDENCE / 'manifest.json'
    require(fidelity.sha256(path) == MANIFEST_SHA256, 'untrusted Level 4 third-objective manifest')
    result = fidelity.strict_json(path.read_text())
    require(result['schema'] == 'lezac-native-level4-third-objective-evidence-v1' and
            result['expected_bytes_source'] == 'original_only' and result['closed_native_sessions'] is True and
            result['all_raw_members_independently_retained'] is True and
            result['snapshot_coherence_differences'] == result['normalized_bytes'] == 0,
            'Level 4 third-objective evidence scope differs')
    return result


def check_route(path):
    require(fidelity.sha256(path) == ROUTE_SHA256, 'Level 4 third-objective route fingerprint differs')
    settings, events = fidelity.read_route(path)
    prior_settings, prior = portal.check_route(portal.FIXTURE / 'route.txt')
    require(settings == {**prior_settings, 'ticks': LAST} and
            {tick: rows for tick, rows in events.items() if tick < portal.LAST} == prior,
            'Level 4 second-objective prefix differs')
    return settings, events


def keys():
    return [('gate', FIRST, phase) for phase in ('present', 'post_update')] + \
        [('result', index, 'result') for index in range(76, 134)] + \
        [('ack', 9301, 'present'), ('intro', 9421, 'present')] + \
        [('level4', tick, phase) for tick in range(ENTRY, LAST + 1) for phase in ('present', 'post_update')]


def validate(rows, header):
    require(len(rows) == 4062 and rows[0] == header and
            rows[-1] == dict(kind='complete', frames=2060, boundaries=4060, patches_restored=True),
            'Level 4 third-objective reference contract differs')
    require(header['frames'] == 2060 and header['boundaries'] == 4060 and header['raw_ds_boundaries'] == 6058 and
            header['completed_levels'] == [1, 2, 3] and header['entered_level'] == 4 and
            header['cpp_expectations_used'] is False and header['state_injections'] is False and
            all(header[key] is value for key, value in CLAIMS.items()), 'Level 4 third-objective claim differs')
    indexed = {}
    for key, row in zip(keys(), rows[1:-1]):
        section, index, phase = key
        require(set(row) == {'kind', 'section', 'index', 'phase', 'projection', 'rgb_sha256'} and
                row['kind'] == 'boundary' and (row['section'], row['index'], row['phase']) == key,
                'Level 4 third-objective reference order differs')
        fields = {'mapped', 'lifecycle'}
        if section not in ('ack', 'intro'):
            fields |= {'monsters', 'markers'}
            if key != ('gate', FIRST, 'present'):
                fields.add('terrain')
        mapped = row['projection']['mapped']
        require(set(row['projection']) == fields and mapped['level'] == (4 if section in ('intro', 'level4') else 3) and
                mapped['frame'] == (index - 1623 if section == 'level4' else 7798) and
                (row['rgb_sha256'] is None) == (phase == 'post_update'), 'Level 4 third-objective projection scope differs')
        if row['rgb_sha256'] is not None:
            require(len(row['rgb_sha256']) == 64 and len(bytes.fromhex(row['rgb_sha256'])) == 32,
                    'invalid native third-objective RGB fingerprint')
        if section == 'level4':
            collected = sum(int(index > tick or (index == tick and phase == 'post_update'))
                            for tick in (first.OBJECTIVE, portal.OBJECTIVE, OBJECTIVE))
            require(mapped['progress'][0] == collected, 'native Level 4 objective timing differs')
        indexed[key] = mapped
    for phase, xy, velocity, fractions in (
            ('present', [146.0, 400.0], [-790, 448], [55, 132]),
            ('post_update', [266.0, 344.0], [374, 0], [173, 132])):
        mapped = indexed['level4', PORTAL, phase]
        player = mapped['players'][0]
        require(player['xy'] == xy and player['velocity'] == velocity and player['fractions'] == fractions and
                player['energy'] == 22 and player['reserve'] == 0 and player['inventory'] == [200, 5, 0, 0, 1] and
                mapped['progress'] == [3, 230 if phase == 'present' else 237] and mapped['score'] == 51190,
                'native return-portal transition differs')
    before = indexed['level4', OBJECTIVE, 'present']
    require(before['progress'] == [2, 209] and before['score'] == 50190 and
            before['players'][0]['xy'] == [170.0, 405.0] and
            before['players'][0]['velocity'] == [-128, 1792] and
            before['players'][0]['fractions'] == [129, 132], 'native pre-pickup boundary differs')
    pickup = indexed['level4', OBJECTIVE, 'post_update']
    require(pickup['progress'] == [3, 230] and pickup['score'] == 51190 and
            pickup['players'][0]['xy'] == [170.0, 398.0] and pickup['players'][0]['energy'] == 22 and
            pickup['players'][0]['reserve'] == 0 and pickup['players'][0]['inventory'] == [200, 5, 0, 0, 1] and
            pickup['players'][0]['velocity'] == [-86, -448] and pickup['players'][0]['fractions'] == [43, 196],
            'native third-objective state differs')
    final = indexed['level4', LAST, 'post_update']
    require(final['progress'] == [3, 244] and final['score'] == 51190 and final['rng'] == 3120439081 and
            final['players'][0]['xy'] == [271.0, 360.0] and final['players'][0]['energy'] == 22 and
            final['players'][0]['reserve'] == 0 and final['players'][0]['inventory'] == [200, 5, 0, 0, 1],
            'native Level 4 third-objective endpoint differs')


def fixture(root=FIXTURE):
    evidence = manifest()
    blobs = {name: gzip.decompress((EVIDENCE / (name + '.gz')).read_bytes())
             for name in evidence['producer_pins']}
    first.check_producers(blobs, evidence['producer_pins'])
    coherence = fidelity.strict_json(blobs['native-coherence-v1.json'].decode())
    require(coherence['boundaries'] == 6058 and coherence['differing_byte_observations'] == coherence['normalized_bytes'] == 0 and
            coherence['raw_sha256'] == evidence['raw_native_sha256'] and
            coherence['journal_sha256'] == evidence['raw_native_journal_sha256'], 'native third-objective coherence audit differs')
    closed = fidelity.strict_json(blobs['owned-services-closed-v1.json'].decode())
    require(closed['keeper_pidfd_terminal_verified'] and closed['capture_state']['MainPID'] == '0' and
            all(row['original_process_no_longer_live'] for row in closed['closed_processes']), 'native third-objective session not closed')
    retained = fidelity.strict_json(blobs['third-native-retention-complete.json'].decode())['retention']
    require(all(retained[key] for key in ('all_notes_tree_anchors_verified', 'all_member_readback_verified',
            'whole_archive_byte_readback_verified')), 'native third-objective retention incomplete')
    for name, digest in evidence['fixture_pins'].items():
        require(fidelity.sha256(root / name) == digest, 'Level 4 third-objective fixture fingerprint differs: ' + name)
    check_route(root / 'route.txt')
    rows = handoff.load(root / 'reference.jsonl.gz')
    validate(rows, evidence['reference_header'])
    require(rows[0]['assets'] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS},
            'Level 4 third-objective shipped assets differ')
    return rows


def compare(cpp):
    report = recovered.compare(cpp, fixture(), last=LAST, route_validator=check_route, expected_frames=2060)
    return {**report, 'return_portal_tick': PORTAL, 'third_objective_tick': OBJECTIVE,
            'level4_frames': 1999, 'raw_coherent_boundaries': 6058, **CLAIMS}


def replay(exe, out):
    out.mkdir(parents=True, exist_ok=True)
    cpp = out.resolve() / ('run-' + uuid.uuid4().hex)
    assets = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
    command = [str(exe.resolve()), '--replay-level1-scout', str(FIXTURE / 'route.txt'), str(cpp), str(FIRST),
               '--original-intro-wait', '--result-reels']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=550,
        env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                 LEZAC_LOAD_JSON_ASSETS='0', LEZAC_LOAD_ORIGINAL_ASSETS='1'))
    require(cpp.is_dir(), 'C++ Level 4 third-objective replay produced no evidence')
    for name, data in (('stdout.txt', result.stdout), ('stderr.txt', result.stderr)):
        (cpp / name).write_text(data, encoding='utf-8')
    (cpp / 'child-result.json').write_bytes(original.json_bytes(dict(exit_code=result.returncode)))
    (cpp / 'command.json').write_bytes(original.json_bytes(dict(command=command, source=fidelity.source_version(ROOT),
        executable_sha256=fidelity.sha256(exe), assets=assets, audio='dummy', video='dummy', state_injections=False,
        replay_reader_sha256=fidelity.sha256(Path(__file__)), **CLAIMS)))
    require(result.returncode == 0, 'C++ Level 4 third-objective replay failed: ' + result.stderr.strip())
    shutil.copyfile(FIXTURE / 'route.txt', cpp / 'route.txt')
    require(assets == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, 'third-objective replay changed shipped assets')
    report = compare(cpp)
    (cpp / 'comparison.json').write_bytes(original.json_bytes(report))
    return report


def guard():
    rows, evidence = fixture(), manifest()
    pickup_index = 1 + keys().index(('level4', OBJECTIVE, 'post_update'))
    portal_index = 1 + keys().index(('level4', PORTAL, 'post_update'))
    edits = [lambda r: r.pop(1), lambda r: r.insert(1, copy.deepcopy(r[1])),
        lambda r: r[-1].__setitem__('patches_restored', False),
        lambda r: r[1].__setitem__('rgb_sha256', None), lambda r: r[1].__setitem__('index', FIRST - 1),
        lambda r: r[-2]['projection']['mapped'].__setitem__('score', 0),
        lambda r: r[pickup_index]['projection']['mapped']['players'][0].__setitem__('energy', 0),
        lambda r: r[pickup_index]['projection']['mapped']['progress'].__setitem__(0, 2),
        lambda r: r[-2]['projection'].__setitem__('extra', 1),
        lambda r: r[portal_index]['projection']['mapped']['players'][0]['xy'].__setitem__(0, 267.0),
        lambda r: r[portal_index]['projection']['mapped']['players'][0]['velocity'].__setitem__(0, 0),
        lambda r: r[portal_index]['projection']['mapped']['players'][0]['fractions'].__setitem__(0, 0),
        lambda r: r[0].__setitem__('completed_levels', [1, 2, 3, 4]),
        lambda r: r[1 + keys().index(('level4', OBJECTIVE, 'present'))]['projection']['mapped']['progress'].__setitem__(0, 3),
        lambda r: r[pickup_index]['projection']['mapped']['players'][0]['velocity'].__setitem__(1, 0),
        lambda r: r[pickup_index]['projection']['mapped']['players'][0]['fractions'].__setitem__(1, 0)]
    edits += [lambda r, key=key: r[0].__setitem__(key, True) for key in (*CLAIMS, 'state_injections', 'cpp_expectations_used')]
    rejected = 0
    for edit in edits:
        changed = copy.deepcopy(rows)
        edit(changed)
        require(changed != rows, 'vacuous Level 4 third-objective mutation')
        try:
            validate(changed, evidence['reference_header'])
        except fidelity.EvidenceError:
            rejected += 1
        else:
            raise fidelity.EvidenceError('Level 4 third-objective reference mutation accepted')
    blobs = {name: gzip.decompress((EVIDENCE / (name + '.gz')).read_bytes()) for name in evidence['producer_pins']}
    for name in blobs:
        try:
            first.check_producers({**blobs, name: blobs[name] + b' '}, evidence['producer_pins'])
        except fidelity.EvidenceError:
            pass
        else:
            raise fidelity.EvidenceError('Level 4 third-objective producer mutation accepted')
    with tempfile.TemporaryDirectory(prefix='lezac-level4-third-objective-guard-') as temporary:
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
                raise fidelity.EvidenceError('Level 4 third-objective fixture byte mutation accepted')
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
        require(args.exe is not None and args.out is not None, 'third-objective executable/output required')
        report = replay(args.exe, args.out)
    elif args.command == 'compare':
        require(args.cpp is not None, 'third-objective C++ evidence required')
        report = compare(args.cpp)
    else:
        report = guard()
    print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
