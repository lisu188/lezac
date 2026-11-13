"""Authenticate the frozen original player post-return projection."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/player_post'
MANIFEST_SHA = 'bc8b93e1949fda472f00e7e0064046421fe09aff0da0811e64abc9ce627abed1'
PROJECTION_BYTES = 31367046
COVERAGE = dict(cases=3102, register_states=4177177, ordered_writes=373395,
    actual_player_calls=24, font_paths=434, life_loss_paths=502, score_format_paths=246,
    signed_divide_paths=902, vga_writes=243192, whole_actor_paths=50, whole_life_loss_paths=32,
    prefix_8044_skips=12, outcome_0=2422, outcome_1=600, outcome_2=80)
INPUTS = ('LEZAC.EXE', 'tools/actor_contact_oracle.py', 'tools/actor_motion_oracle.py',
    'tools/actor_precontact_oracle.py', 'tools/actor_steering_oracle.py', 'tools/ammo_hud_oracle.py',
    'tools/boss_links_oracle.py', 'tools/frame_actor_entry_oracle.py', 'tools/frame_camera_oracle.py',
    'tools/frame_spawner_oracle.py', 'tools/frame_waiting_oracle.py', 'tools/player_motion_oracle.py',
    'tools/nonplayer_loop_oracle.py', 'tools/actor_update_oracle.py', 'tools/player_post_oracle.py')
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(yes, message):
    if not yes:
        raise ValueError(message)


def read_fixture(root=ROOT, fixture=FIXTURE):
    raw = (fixture / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen player post manifest differs')
    manifest = json.loads(raw)
    inputs = {**manifest['asset_sha256'],
        **{'tools/' + name: digest for name, digest in manifest['source_sha256'].items()}}
    require(set(inputs) == set(INPUTS), 'Player post input catalog differs')
    for name, digest in inputs.items():
        require(sha((root / name).read_bytes()) == digest, 'Player post input differs: ' + name)
    require(manifest['schema'] == 'lezac-controlled-player-post-v1' and
        manifest['coverage'] == COVERAGE and manifest['unicorn_version'] == '2.1.4' and
        manifest['unicorn_library_sha256'] ==
            'ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        manifest['actual_library_mapping_verified'] is True and
        manifest['complete_memory_observer_control'] is True and
        manifest['observer_control'] == 'register-write-trace-versus-stop-only-hooks' and
        manifest['ordered_writes_reconstruct_memory'] is True and
        manifest['original_code_bytes_verified'] == 43552 and
        all(manifest[key] == 0 for key in
            ('instruction_patches', 'calls_stubbed', 'hardware_io', 'interrupts_delivered')) and
        all(manifest[key] is False for key in ('later_state_injected', 'production_app_comparison',
            'natural_capture', 'full_frame_claim', 'raw_memory_published')), 'Player post proof domain differs')
    packed = (fixture / 'oracle.bin.gz').read_bytes()
    require(len(packed) == manifest['compressed_bytes'] and sha(packed) == manifest['compressed_sha256'],
        'Compressed player post projection differs')
    require(manifest['projection_bytes'] == PROJECTION_BYTES, 'Player post projection reserve differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        decoded = stream.read(PROJECTION_BYTES + 1)
    require(len(decoded) == PROJECTION_BYTES and sha(decoded) == manifest['projection_sha256'],
        'Decoded player post projection differs')
    return decoded


def run(root, fixture, out=None, report=None):
    protected = [root / name for name in INPUTS] + [
        fixture / 'manifest.json', fixture / 'oracle.bin.gz', Path(__file__).resolve()]
    for candidate in (out, report):
        if candidate:
            require(all(candidate.resolve() != path.resolve() and not
                (candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'Player post output must not replace a protected input')
    if out and report:
        require(out.resolve() != report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)), 'Player post report/export overlap')
    result = dict(status='failed', whole_game_parity=False)
    try:
        decoded = read_fixture(root, fixture)
        if out:
            if out.exists():
                require(out.stat().st_size == len(decoded) and out.read_bytes() == decoded,
                    'Existing player post export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed', cases=COVERAGE['cases'], bytes=len(decoded), sha256=sha(decoded))
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
