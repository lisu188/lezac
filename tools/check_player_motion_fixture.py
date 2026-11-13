"""Authenticate the frozen original complete player-motion projection."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/player_motion'
MANIFEST_SHA = 'f1abc2dba73cb264db2d8bd0c9f1aaa5640b4f4c1939b7fd35cee67abcab1ffc'
INPUTS = ('LEZAC.EXE', 'tools/actor_contact_oracle.py', 'tools/actor_motion_oracle.py',
    'tools/actor_precontact_oracle.py', 'tools/actor_steering_oracle.py', 'tools/ammo_hud_oracle.py',
    'tools/boss_links_oracle.py', 'tools/frame_actor_entry_oracle.py', 'tools/frame_camera_oracle.py',
    'tools/frame_spawner_oracle.py', 'tools/frame_waiting_oracle.py', 'tools/player_motion_oracle.py')
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(yes, message):
    if not yes:
        raise ValueError(message)


def read_fixture(root=ROOT, fixture=FIXTURE):
    raw = (fixture / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen player manifest differs')
    manifest = json.loads(raw)
    inputs = {**manifest['asset_sha256'],
        **{'tools/' + name: digest for name, digest in manifest['source_sha256'].items()}}
    require(set(inputs) == set(INPUTS), 'Player input catalog differs')
    for name, digest in inputs.items():
        require(sha((root / name).read_bytes()) == digest, 'Player input differs: ' + name)
    require(manifest['schema'] == 'lezac-controlled-player-motion-v1' and
        manifest['coverage'] == dict(cases=7028, register_states=3561155, ordered_writes=673658,
            actual_callers=24, original_player_instruction_sites=899, outcome_0=7024, outcome_1=4) and
        manifest['unicorn_version'] == '2.1.4' and
        manifest['unicorn_library_sha256'] ==
            'ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        manifest['actual_library_mapping_verified'] is True and
        manifest['complete_memory_observer_control'] is True and
        manifest['ordered_writes_reconstruct_memory'] is True and
        manifest['original_code_bytes_verified'] == 43552 and
        all(manifest[key] == 0 for key in
            ('instruction_patches', 'calls_stubbed', 'hardware_io', 'interrupts_delivered')) and
        all(manifest[key] is False for key in ('later_state_injected', 'production_app_comparison',
            'natural_capture', 'full_frame_claim', 'raw_memory_published')), 'Player proof domain differs')
    packed = (fixture / 'oracle.bin.gz').read_bytes()
    require(len(packed) == manifest['compressed_bytes'] and sha(packed) == manifest['compressed_sha256'],
        'Compressed player projection differs')
    size = manifest['projection_bytes']
    require(size == 49667615, 'Player projection reserve differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        decoded = stream.read(size + 1)
    require(len(decoded) == size and sha(decoded) == manifest['projection_sha256'],
        'Decoded player projection differs')
    return decoded


def run(root, fixture, out=None, report=None):
    protected = [root / name for name in INPUTS] + [
        fixture / 'manifest.json', fixture / 'oracle.bin.gz', Path(__file__).resolve()]
    for candidate in (out, report):
        if candidate:
            require(all(candidate.resolve() != path.resolve() and not
                (candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'Player output must not replace a protected input')
    if out and report:
        require(out.resolve() != report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)), 'Player report/export overlap')
    result = dict(status='failed', whole_game_parity=False)
    try:
        decoded = read_fixture(root, fixture)
        if out:
            if out.exists():
                require(out.stat().st_size == len(decoded) and out.read_bytes() == decoded,
                    'Existing player export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed', cases=7028, bytes=len(decoded), sha256=sha(decoded))
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        if report:
            report.write_text(json.dumps(result, sort_keys=True) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(ROOT, FIXTURE, args.out, args.report), sort_keys=True))
