"""Original-backed ordinary Level 4 support-column production replay."""
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
import natural_level4_third_objective as third

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level4_support_column'
EVIDENCE = ROOT / 'docs/recovery/evidence/natural_level4_support_column_20261008'
FIRST, LAST, ENTRY, PLACEMENT = 8905, 11740, 9422, 11466
MANIFEST_SHA256 = '9e4d5bcfe2f11620e060bec1032a3a60e15dec949eaf55b33af9b30057eeeee1'
ROUTE_SHA256 = 'df39d4ac769d61e0073f1382ddca883e5572e7dfca48a7f4e6868d79557183b2'
CLAIMS = first.CLAIMS
require = fidelity.require


def manifest():
    path = EVIDENCE / 'manifest.json'
    require(fidelity.sha256(path) == MANIFEST_SHA256, 'untrusted Level 4 support-column manifest')
    result = fidelity.strict_json(path.read_text())
    require(result['schema'] == 'lezac-native-level4-support-column-evidence-v1' and
            result['expected_bytes_source'] == 'original_only' and result['closed_native_sessions'] is True and
            result['all_raw_members_independently_retained'] is True and
            result['snapshot_coherence_differences'] == result['normalized_bytes'] == 0,
            'Level 4 support-column evidence scope differs')
    return result


def check_route(path):
    require(fidelity.sha256(path) == ROUTE_SHA256, 'Level 4 support-column route fingerprint differs')
    settings, events = fidelity.read_route(path)
    prior_settings, prior = third.check_route(third.FIXTURE / 'route.txt')
    require(settings == {**prior_settings, 'ticks': LAST} and
            {tick: rows for tick, rows in events.items() if tick < third.LAST} == prior,
            'Level 4 third-objective route prefix differs')
    return settings, events


def keys():
    return third.keys() + [('level4', tick, phase) for tick in range(third.LAST + 1, LAST + 1)
                           for phase in ('present', 'post_update')]


def validate(rows, header):
    require(len(rows) == 4702 and rows[0] == header and
            rows[-1] == dict(kind='complete', frames=2380, boundaries=4700, patches_restored=True),
            'Level 4 support-column reference contract differs')
    require(header['schema'] == 'lezac-natural-level4-support-column-v1' and
            header['frames'] == 2380 and header['boundaries'] == 4700 and header['raw_ds_boundaries'] == 7018 and
            header['completed_levels'] == [1, 2, 3] and header['entered_level'] == 4 and
            header['cpp_expectations_used'] is False and header['state_injections'] is False and
            header['prior_manifest_sha256'] == third.MANIFEST_SHA256 and
            header['repeated_prior_boundaries'] == 4060 and header['added_boundaries'] == 640 and
            all(header[key] is value for key, value in CLAIMS.items()), 'Level 4 support-column claim differs')
    prior_header = third.manifest()['reference_header']
    third.validate([prior_header, *rows[1:4061],
                    dict(kind='complete', frames=2060, boundaries=4060, patches_restored=True)], prior_header)
    for key, row in zip(keys()[4060:], rows[4061:-1]):
        section, tick, phase = key
        require(set(row) == {'kind', 'section', 'index', 'phase', 'projection', 'rgb_sha256'} and
                row['kind'] == 'boundary' and (row['section'], row['index'], row['phase']) == key,
                'Level 4 support-column reference order differs')
        require(set(row['projection']) == {'mapped', 'lifecycle', 'monsters', 'markers', 'terrain'},
                'Level 4 support-column projection scope differs')
        mapped = row['projection']['mapped']
        player = mapped['players'][0]
        medium = 4 if tick > PLACEMENT or (tick == PLACEMENT and phase == 'post_update') else 5
        require(mapped['level'] == 4 and mapped['frame'] == tick - 1623 and
                mapped['progress'] == [3, 244] and mapped['score'] == 51190 and
                player['energy'] == 22 and player['reserve'] == 0 and
                player['inventory'] == [200, medium, 0, 0, 1], 'native support-column gameplay differs')
        require((row['rgb_sha256'] is None) == (phase == 'post_update'), 'support-column RGB phase differs')
        if row['rgb_sha256'] is not None:
            require(len(row['rgb_sha256']) == 64 and len(bytes.fromhex(row['rgb_sha256'])) == 32,
                    'invalid support-column RGB fingerprint')
    final = rows[-2]['projection']['mapped']
    require(final['players'][0]['xy'] == [255.0, 360.0] and
            final['players'][0]['velocity'] == [0, 0] and final['players'][0]['fractions'] == [47, 126] and
            final['rng'] == 2528869611, 'native support-column endpoint differs')


def fixture(root=FIXTURE):
    evidence = manifest()
    blobs = {name: gzip.decompress((EVIDENCE / (name + '.gz')).read_bytes())
             for name in evidence['producer_pins']}
    first.check_producers(blobs, evidence['producer_pins'])
    coherence = fidelity.strict_json(blobs['native-coherence-v1.json'].decode())
    require(coherence['boundaries'] == 7018 and coherence['differing_byte_observations'] == coherence['normalized_bytes'] == 0 and
            coherence['raw_sha256'] == evidence['raw_native_sha256'] and
            coherence['journal_sha256'] == evidence['raw_native_journal_sha256'], 'native support-column coherence differs')
    prepared = fidelity.strict_json(blobs['column-reference-preparation-v3.json'].decode())
    require(prepared['expected_bytes_source'] == 'original_only' and not prepared['cpp_outputs_read_for_expected_bytes'] and
            all(row['original_identity_terminal'] for row in prepared['native_processes_closed'].values()),
            'native support-column preparation/closure differs')
    retained = fidelity.strict_json(blobs['support-and-repaired-reward-retention-complete.json'].decode())['retention']
    require(retained == prepared['native_retention'] and all(retained[key] for key in
            ('all_notes_tree_anchors_verified', 'all_member_readback_verified', 'whole_archive_byte_readback_verified')),
            'native support-column retention incomplete')
    for name, digest in evidence['fixture_pins'].items():
        require(fidelity.sha256(root / name) == digest, 'Level 4 support-column fixture fingerprint differs: ' + name)
    check_route(root / 'route.txt')
    rows = handoff.load(root / 'reference.jsonl.gz')
    validate(rows, evidence['reference_header'])
    require(rows[1:4061] == third.fixture()[1:-1], 'trusted third-objective reference prefix differs')
    require(rows[0]['assets'] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS},
            'Level 4 support-column shipped assets differ')
    return rows


def compare(cpp):
    report = recovered.compare(cpp, fixture(), last=LAST, route_validator=check_route, expected_frames=2380)
    return {**report, 'support_bomb_placement_tick': PLACEMENT, 'level4_frames': 2319,
            'raw_coherent_boundaries': 7018, **CLAIMS}


def replay(exe, out):
    out.mkdir(parents=True, exist_ok=True)
    cpp = out.resolve() / ('run-' + uuid.uuid4().hex)
    assets = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
    command = [str(exe.resolve()), '--replay-level1-scout', str(FIXTURE / 'route.txt'), str(cpp), str(FIRST),
               '--original-intro-wait', '--result-reels']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=550,
        env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                 LEZAC_LOAD_JSON_ASSETS='0', LEZAC_LOAD_ORIGINAL_ASSETS='1'))
    require(cpp.is_dir(), 'C++ support-column replay produced no evidence')
    for name, data in (('stdout.txt', result.stdout), ('stderr.txt', result.stderr)):
        (cpp / name).write_text(data, encoding='utf-8')
    (cpp / 'child-result.json').write_bytes(original.json_bytes(dict(exit_code=result.returncode)))
    (cpp / 'command.json').write_bytes(original.json_bytes(dict(command=command, source=fidelity.source_version(ROOT),
        executable_sha256=fidelity.sha256(exe), assets=assets, audio='dummy', video='dummy', state_injections=False,
        replay_reader_sha256=fidelity.sha256(Path(__file__)), **CLAIMS)))
    require(result.returncode == 0, 'C++ support-column replay failed: ' + result.stderr.strip())
    shutil.copyfile(FIXTURE / 'route.txt', cpp / 'route.txt')
    require(assets == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, 'support-column replay changed assets')
    report = compare(cpp)
    (cpp / 'comparison.json').write_bytes(original.json_bytes(report))
    return report


def guard():
    rows, evidence = fixture(), manifest()
    placement = 1 + keys().index(('level4', PLACEMENT, 'post_update'))
    edits = [lambda r: r.pop(1), lambda r: r.insert(1, copy.deepcopy(r[1])),
        lambda r: r[-1].__setitem__('patches_restored', False),
        lambda r: r[4061].__setitem__('rgb_sha256', None),
        lambda r: r[4061].__setitem__('index', third.LAST),
        lambda r: r[-2]['projection']['mapped'].__setitem__('score', 0),
        lambda r: r[-2]['projection']['mapped']['players'][0].__setitem__('energy', 0),
        lambda r: r[-2]['projection']['mapped']['progress'].__setitem__(0, 2),
        lambda r: r[-2]['projection'].__setitem__('extra', 1),
        lambda r: r[placement]['projection']['mapped']['players'][0]['inventory'].__setitem__(1, 5),
        lambda r: r[-2]['projection']['mapped']['players'][0]['xy'].__setitem__(0, 256.0),
        lambda r: r[-2]['projection']['mapped']['players'][0]['velocity'].__setitem__(0, 1),
        lambda r: r[-2]['projection']['mapped']['players'][0]['fractions'].__setitem__(0, 48),
        lambda r: r[0].__setitem__('completed_levels', [1, 2, 3, 4]),
        lambda r: r[0].__setitem__('raw_ds_boundaries', 6058),
        lambda r: r[0].__setitem__('repeated_prior_boundaries', 4059),
        lambda r: r[0].__setitem__('added_boundaries', 641)]
    edits += [lambda r, key=key: r[0].__setitem__(key, True) for key in (*CLAIMS, 'state_injections', 'cpp_expectations_used')]
    rejected = 0
    for edit in edits:
        changed = copy.deepcopy(rows)
        edit(changed)
        require(changed != rows, 'vacuous support-column mutation')
        try:
            validate(changed, evidence['reference_header'])
        except fidelity.EvidenceError:
            rejected += 1
        else:
            raise fidelity.EvidenceError('support-column reference mutation accepted')
    blobs = {name: gzip.decompress((EVIDENCE / (name + '.gz')).read_bytes()) for name in evidence['producer_pins']}
    for name in blobs:
        try:
            first.check_producers({**blobs, name: blobs[name] + b' '}, evidence['producer_pins'])
        except fidelity.EvidenceError:
            pass
        else:
            raise fidelity.EvidenceError('support-column producer mutation accepted')
    with tempfile.TemporaryDirectory(prefix='lezac-level4-support-column-guard-') as temporary:
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
                raise fidelity.EvidenceError('support-column fixture byte mutation accepted')
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
        require(args.exe is not None and args.out is not None, 'support-column executable/output required')
        report = replay(args.exe, args.out)
    elif args.command == 'compare':
        require(args.cpp is not None, 'support-column C++ evidence required')
        report = compare(args.cpp)
    else:
        report = guard()
    print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
