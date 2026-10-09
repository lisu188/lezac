"""Compare corpse countdown/conversion production paths with pinned native tables."""
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

STATE_BYTES = 1593
OPERATIONS = 3252
ORIGINAL_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
FIXTURES = {
    'requests': ('6cf9b8f9521f2532937a78f99fbf90bc2e0e0a0030791acada433864fff3dc06',
                 '2f623d2a057425b71466c1b3fa75d5c6968a9f347a094c0fc034aa7b2a659790'),
    'expected': ('ad93b5c55116741e4af459464760697a545a3d646325c74f167e1f886bf0d801',
                 '5ecc7a2666dc2444261d5332bfbdc8ea162df13fa6a9c92c9b27d31b3408febc'),
}


def decode_fixture(packed, compressed_sha, raw_sha, limit=8 * 1024**2):
    require(len(packed) < 512 * 1024, 'compressed corpse fixture exceeds limit')
    require(sha(packed) == compressed_sha, 'compressed corpse fixture hash mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(limit + 1)
        require(len(raw) <= limit, 'decompressed corpse fixture exceeds limit')
    require(sha(raw) == raw_sha, 'decompressed corpse fixture hash mismatch')
    return raw


def difference(actual, expected):
    if actual == expected:
        return None
    offset = next((at for at, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]), min(len(actual), len(expected)))
    at = (offset - 12) % STATE_BYTES if offset >= 12 else None
    return dict(output_offset=offset, operation=(offset - 12) // STATE_BYTES + 1 if at is not None else None,
        state_offset=at, actual=actual[offset] if offset < len(actual) else None,
        expected=expected[offset] if offset < len(expected) else None,
        actual_bytes=len(actual), expected_bytes=len(expected))


def check_routing(source, models):
    def body(start, end):
        at = source.index(start)
        return source[at:source.index(end, at)]

    start = source.index('    void updateMonsters(')
    update = source[start:source.index('\n    void ', start + 1)]
    for token in ('advanceMonsterAnimation(monster)', 'advanceCorpseMotion(monster, timer, logicTick_',
                  'actorSlots_.actor(monster.actorOrder)', 'raw[0] == 0x0c ? raw[2]',
                  'actorSlots_.writeCorpse(monster.actorOrder, monster, timer, animationAdvanced,',
                  'finishMonsterDeathReward(monster)'):
        require(token in update, 'missing corpse production routing: ' + token)
    require(update.index('advanceMonsterAnimation') < update.index('advanceCorpseMotion') <
            update.index('actorSlots_.writeCorpse') < update.index('finishMonsterDeathReward'), 'corpse dispatch order differs')
    conversion = body('    void finishMonsterDeathReward(', '    void spawnExpiryParticles(')
    for token in ('corpseRewardRoll_ = static_cast<uint8_t>(randomRangeValue(0, 100))',
                  'randomRangeValue(0, 20)', 'requestSoundCursor(rewardSound, 4)', 'convertCorpseReward(',
                  'actorSlots_.convertCorpse(', 'bonusDrops_.push_back(conversion.reward)', 'spawnExpiryParticles('):
        require(token in conversion, 'missing corpse conversion routing: ' + token)
    require(conversion.index('actorSlots_.convertCorpse') < conversion.index('bonusDrops_.push_back') <
            conversion.index('spawnExpiryParticles'), 'corpse conversion is not written before publication/allocation')
    diagnostic = body('    void debugCorpseStorageOriginal(', '    void debugRewardStorageOriginal(')
    require('legacyActorSeedsEnabled_ = false;' in diagnostic and 'updateOrderedActors(0);' in diagnostic,
            'corpse diagnostic bypasses bound production pass')
    require(diagnostic.count('restoreForFixture') == 1, 'corpse diagnostic rebuilds physical state after seed')
    require('corpse pass changed fixture terrain' in diagnostic, 'corpse diagnostic omits terrain preservation')
    require('sound_.restoreLatchForFixture(seed.latch)' in diagnostic and 'corpseRewardRoll_, sound_' in diagnostic,
            'corpse diagnostic bypasses production sound latch')
    require('app.debugCorpseStorageOriginal(argv[2], argv[3]);' in source, 'missing corpse App command')
    helper = models[models.index('inline bool advanceCorpseMotion('):models.index('struct CorpseRewardConversion')]
    require(helper.index('motion(') < helper.index('timer =') < helper.index('const bool expired'), 'corpse timer order differs')
    require('timer == 0 || timer == 0xff' in helper, 'missing corpse timer sentinels')


def check(root, exe, out, production_app):
    root, exe, out = root.resolve(), exe.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='corpse-app-' if production_app else 'corpse-helper-', dir=out))
    report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), production_app=production_app,
        compiled_helper=not production_app, operations=OPERATIONS, cases=940, compared_bytes=OPERATIONS * STATE_BYTES,
        seeded=True, natural_route=False, whole_game_claim=False, masks_applied=False, audio='dummy',
        direct_reward_allocation_executed=False, natural_fatal_entry_executed=False, sound_interrupt_executed=False,
        rendered_pixels_claim=False, directory=str(directory), fixtures={})
    try:
        require(sha((root / 'LEZAC.EXE').read_bytes()) == ORIGINAL_SHA, 'original executable hash mismatch')
        check_routing((root / 'src/app/app.cpp').read_text(encoding='utf-8'),
                      (root / 'src/gameplay/actor_models.hpp').read_text(encoding='utf-8'))
        report['executable_sha256_before'] = sha(exe.read_bytes())
        streams = {}
        for label, (packed_sha, raw_sha) in FIXTURES.items():
            packed = (root / 'tests/fixtures/corpse_storage' / (label + '.bin.gz')).read_bytes()
            raw = decode_fixture(packed, packed_sha, raw_sha)
            (directory / (label + '.bin.gz')).write_bytes(packed)
            if label == 'requests':
                (directory / 'requests.bin').write_bytes(raw)
            streams[label] = raw
            report['fixtures'][label] = dict(compressed_sha256=sha(packed), raw_sha256=sha(raw), bytes=len(raw))
        request, expected = streams['requests'], streams['expected']
        require(request[:12] == b'LZRC0001' + struct.pack('<I', OPERATIONS), 'invalid corpse request header')
        require(expected[:12] == b'LZCO0001' + struct.pack('<I', OPERATIONS), 'invalid corpse output header')
        require(len(expected) == 12 + OPERATIONS * STATE_BYTES, 'invalid corpse output extent')
        args = [str(exe)] + (['--debug-corpse-storage-original'] if production_app else [])
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
        require(result.returncode == 0, 'corpse executable failed')
        marker = (b'corpse_storage_original_app=ok operations=3252 seeds=940 updates=2312 '
                  b'legacy_adoptions=0 legacy_retirements=0 seeded=1 natural_route=0 whole_game_claim=0') if production_app \
            else b'corpse_storage_probe=ok operations=3252'
        require(marker in stdout.splitlines(), 'missing corpse execution marker')
        actual = (directory / 'actual.bin').read_bytes()
        report.update(actual_sha256=sha(actual), first_difference=difference(actual, expected))
        require(report['first_difference'] is None, 'corpse physical table differs from original')
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
        print('corpse_storage_original=failed report=' + str(path))
        print(report['error'])
        return 1
    print('corpse_storage_original=ok operations=3252 compared_bytes=5180436 production_app=%d '
          'masks=0 seeded=1 natural_route=0 whole_game_claim=0 report=%s' % (args.production_app, path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
