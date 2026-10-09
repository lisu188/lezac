"""Compare production reward paths with complete pinned original CPU tables."""
import argparse
from datetime import datetime, timezone
import gzip
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import traceback

from check_transient_storage_original import require, sha

STATE_BYTES = 1585
OPERATIONS = 4982
ORIGINAL_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
FIXTURES = {
    'requests': ('098ef3d5b15a7819f9ea98f4e3ccbb75530ee671d55cc4e5eb268f1a81abe456',
                 '8a68fc46f6457f784423eca69a70978081102bffd836b09cc58b1b18cc452338'),
    'expected': ('6797216835dad9113684141b1395fc55010d036b4333d0d7575b0e23f2a69ef4',
                 'b503b8304a767b08a0d5af3471c537f66c4393283d909afd7b7632cdfa58ba44'),
}


def decode_fixture(packed, compressed_sha, raw_sha, limit=8 * 1024**2):
    require(len(packed) < 256 * 1024, 'compressed reward fixture exceeds limit')
    require(sha(packed) == compressed_sha, 'compressed reward fixture hash mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(limit + 1)
        require(len(raw) <= limit, 'decompressed reward fixture exceeds limit')
    require(sha(raw) == raw_sha, 'decompressed reward fixture hash mismatch')
    return raw


def difference(actual, expected):
    if actual == expected:
        return None
    offset = next((at for at, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]), min(len(actual), len(expected)))
    at = (offset - 12) % STATE_BYTES if offset >= 12 else None
    return dict(output_offset=offset, operation=(offset - 12) // STATE_BYTES + 1 if at is not None else None,
        state_offset=at, area='header' if at is None else 'actors' if at < 1178 else 'visuals' if at < 1442 else 'links' if at < 1570 else 'scalars',
        actual=actual[offset] if offset < len(actual) else None, expected=expected[offset] if offset < len(expected) else None,
        actual_bytes=len(actual), expected_bytes=len(expected))


def check_routing(source, models):
    def body(start, end):
        at = source.index(start)
        return source[at:source.index(end, at)]

    update = body('    void updateBonusDrops(', '    void applyPendingBonus(')
    for token in ('advanceBonusDrop(', 'conversionBackup(drop.actorOrder)', 'logicTick_, touching, pendingBonuses_',
                  'updateTimedActorMotion(x, y, vx, vy, fracX, fracY, scanActorEdges(x, y))',
                  'actorSlots_.setSpriteDescriptor(drop.actorOrder, descriptor);',
                  'actorSlots_.writeTransient(drop.actorOrder, step.conversion, false, {});',
                  'actorSlots_.writeReward(drop.actorOrder, drop, step.animationAdvanced, descriptor);'):
        require(token in update, 'missing reward production routing: ' + token)
    require(update.index('actorSlots_.setSpriteDescriptor') < update.index('actorSlots_.writeTransient') < update.index('transientActors_.push_back'),
            'reward conversion bypasses physical write-before-publish')
    require('case SharedActorKind::Reward: updateBonusDrops(std::numeric_limits<size_t>::max(), entry.order); break;' in source,
            'reward bypasses ordered production dispatch')
    diagnostic = body('    void debugRewardStorageOriginal(', '    void debugCorpseRewardAnimationMode(')
    require('legacyActorSeedsEnabled_ = false;' in diagnostic and 'updateOrderedActors(0);' in diagnostic,
            'reward diagnostic does not exercise bound production pass')
    require(diagnostic.count('restoreForFixture') == 1, 'reward diagnostic rebuilds physical state after seed')
    require('reward pass changed fixture terrain' in diagnostic, 'reward diagnostic omits terrain preservation')
    require('app.debugRewardStorageOriginal(argv[2], argv[3]);' in source and '--debug-reward-storage-original' in source,
            'missing reward App command')
    helper = models[models.index('inline BonusDropStep advanceBonusDrop('):models.index('struct State2VisualCursor')]
    require(helper.index('drop.animation.advance(backup)') < helper.index('for (size_t player'), 'reward animation is not first')
    require(helper.index('motion(x, y, drop.vx8') < helper.index('drop.timer ='), 'reward timer precedes motion')


def check(root, exe, out, production_app):
    root, exe, out = root.resolve(), exe.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='reward-app-' if production_app else 'reward-helper-', dir=out))
    report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), production_app=production_app,
        compiled_helper=not production_app, operations=OPERATIONS, compared_bytes=OPERATIONS * STATE_BYTES,
        seeded=True, natural_route=False, whole_game_claim=False, full_raw_record_owner=False,
        masks_applied=False, audio='dummy', player_updates_executed=False, pending_bonus_application_executed=False,
        constructors_executed=False, rendered_pixels_claim=False, directory=str(directory), fixtures={})
    try:
        require(sha((root / 'LEZAC.EXE').read_bytes()) == ORIGINAL_SHA, 'original executable hash mismatch')
        check_routing((root / 'src/app/app.cpp').read_text(encoding='utf-8'),
                      (root / 'src/gameplay/actor_models.hpp').read_text(encoding='utf-8'))
        report['executable_sha256_before'] = sha(exe.read_bytes())
        streams = {}
        for label, (packed_sha, raw_sha) in FIXTURES.items():
            packed = (root / 'tests/fixtures/reward_storage' / (label + '.bin.gz')).read_bytes()
            raw = decode_fixture(packed, packed_sha, raw_sha)
            (directory / (label + '.bin.gz')).write_bytes(packed)
            if label == 'requests':
                (directory / 'requests.bin').write_bytes(raw)
            streams[label] = raw
            report['fixtures'][label] = dict(compressed_sha256=sha(packed), raw_sha256=sha(raw), bytes=len(raw))
        request, expected = streams['requests'], streams['expected']
        require(request[:12] == b'LZRW0001' + struct.pack('<I', OPERATIONS), 'invalid reward request header')
        require(expected[:12] == b'LZRO0001' + struct.pack('<I', OPERATIONS), 'invalid reward output header')
        require(len(expected) == 12 + OPERATIONS * STATE_BYTES, 'invalid reward output extent')
        args = [str(exe)] + (['--debug-reward-storage-original'] if production_app else [])
        args += [str(directory / 'requests.bin'), str(directory / 'actual.bin')]
        report['args'] = args
        try:
            result = subprocess.run(args, capture_output=True, timeout=30,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1'))
            stdout, stderr = result.stdout, result.stderr
            report['returncode'] = result.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.stdout or b'', error.stderr or b''
            report['timeout'] = True
            raise
        finally:
            if 'stdout' in locals():
                (directory / 'actual.stdout').write_bytes(stdout)
                (directory / 'actual.stderr').write_bytes(stderr)
                report.update(stdout_sha256=sha(stdout), stderr_sha256=sha(stderr))
        require(result.returncode == 0, 'reward executable failed')
        marker = (b'reward_storage_original_app=ok operations=4982 seeds=87 updates=4895 '
                  b'legacy_adoptions=0 legacy_retirements=0 seeded=1 natural_route=0 whole_game_claim=0') if production_app \
            else b'reward_storage_probe=ok operations=4982'
        require(marker in stdout.splitlines(), 'missing reward execution marker')
        actual = (directory / 'actual.bin').read_bytes()
        report.update(actual_sha256=sha(actual), first_difference=difference(actual, expected))
        require(report['first_difference'] is None, 'reward physical table differs from original')
        report['executable_sha256_after'] = sha(exe.read_bytes())
        require(report['executable_sha256_before'] == report['executable_sha256_after'], 'executable changed during comparison')
        report['passed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    path = directory / 'comparison.json'
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report, path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--production-app', action='store_true')
    args = parser.parse_args()
    report, path = check(args.root, args.exe, args.out, args.production_app)
    if not report['passed']:
        print('reward_storage_original=failed report=' + str(path))
        print(report['error'])
        return 1
    print('reward_storage_original=ok operations=4982 compared_bytes=7896470 production_app=%d '
          'masks=0 seeded=1 natural_route=0 whole_game_claim=0 report=%s' % (args.production_app, path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
