"""Compare marker production paths with complete, pinned original CPU tables."""
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

from check_transient_storage_original import difference, require, sha

STATE_BYTES = 1575
OPERATIONS = 1008
ORIGINAL_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
FIXTURES = {
    'requests': ('1588b806e9cb2419400279857f2048914039f83c8e5067f3627b576c597fc660',
                 'd5dcdcd77111a5d5339b3e5428b1cad2bec14a956f1736e3e7dff786478852aa'),
    'expected': ('9bc418f2a06b7c8a9e88c6a849f92751021a9b2809fea9bcf5622e3e4498ba39',
                 'c058adcf9b7a4657fb1574b1f97198100cc62570d4f57c5ab50919df6912fe85'),
}


def decode_fixture(packed, compressed_sha, raw_sha, limit=2 * 1024**2):
    require(len(packed) < 256 * 1024, 'compressed marker fixture exceeds limit')
    require(sha(packed) == compressed_sha, 'compressed marker fixture hash mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(limit + 1)
        require(len(raw) <= limit, 'decompressed marker fixture exceeds limit')
    require(sha(raw) == raw_sha, 'decompressed marker fixture hash mismatch')
    return raw


def check_routing(source):
    def body(start, end):
        return source[source.index(start):source.index(end, source.index(start))]

    def ordered(text, *tokens):
        position = 0
        for token in tokens:
            at = text.find(token, position)
            require(at >= 0, 'missing marker routing token: ' + token)
            position = at + len(token)

    launch = body('    bool activateLaunchPad(', '    void spawnLaunchPadMarker(')
    ordered(launch, 'requestLaunchPadSound();', 'spawnLaunchPadMarker(static_cast<int>(player.x), localY);')
    launch_spawn = body('    void spawnLaunchPadMarker(', '    void spawnPortalMarker(')
    ordered(launch_spawn, 'marker.actorOrder = allocateActor(', 'if (!marker.actorOrder) return;',
            'actorSlots_.disableAnimation(marker.actorOrder);',
            'marker.animation = actorSlots_.activeAnimation(marker.actorOrder);', 'launchPadMarkers_.push_back(marker);')
    portal_spawn = body('    void spawnPortalMarker(', '    void updateLaunchPadMarkers(')
    ordered(portal_spawn, 'marker.animation = ActorAnimation::initialize(', 'marker.actorOrder = allocateActor(',
            'if (!marker.actorOrder) return;', 'actorSlots_.setActiveAnimation(marker.actorOrder, marker.animation);',
            'launchPadMarkers_.push_back(marker);')
    portal = body('    bool activatePortal(', '    void updatePortalsAndTriggers(')
    ordered(portal, 'portalDownConsumed_.fill(true);', 'requestPortalTeleportSound();', 'spawnPortalMarker(x, y);')
    for text in (launch, launch_spawn, portal, portal_spawn):
        require('sharedActorCount()' not in text, 'marker bypasses physical allocation refusal')
    update = body('    void updateLaunchPadMarkers(', '    // One banner line')
    ordered(update, 'advanceLaunchPadMarker(', 'actorSlots_.writeMarker(marker.actorOrder, marker, advanced, descriptor);',
            'retireActor(marker.actorOrder)')
    require(update.count('(!onlyOrder || marker.actorOrder == onlyOrder) && marker.timer == 0') == 2,
            'marker retires records that have not received their ordered update')
    require('case SharedActorKind::Marker: updateLaunchPadMarkers(entry.order); break;' in source,
            'marker is not routed through ordered production dispatch')
    diagnostic = body('    void debugMarkerStorageOriginal(', '    void debugProductionActorLifecycle(')
    ordered(diagnostic, 'legacyActorSeedsEnabled_ = false;', 'actorSlots_.restoreForFixture(state, orders);',
            'updateOrderedActors(0);', 'spawnLaunchPadMarker(position.x, position.y);',
            'spawnPortalMarker(position.x, position.y);')
    require(diagnostic.count('restoreForFixture') == 1, 'marker diagnostic rebuilds state after seed')
    require('--debug-marker-storage-original' in source and 'app.debugMarkerStorageOriginal(argv[2], argv[3]);' in source,
            'marker diagnostic has no App command route')


def check(root, exe, out, production_app):
    root, exe, out = root.resolve(), exe.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='marker-app-' if production_app else 'marker-helper-', dir=out))
    report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), production_app=production_app,
        compiled_helper=not production_app, operations=OPERATIONS, compared_bytes=OPERATIONS * STATE_BYTES,
        seeded=True, natural_route=False, whole_game_claim=False, masks_applied=False, audio='dummy',
        constructor_tails_only=True, input_gate_and_sound_prefix_executed=False, directory=str(directory), fixtures={})
    try:
        require(sha((root / 'LEZAC.EXE').read_bytes()) == ORIGINAL_SHA, 'original executable hash mismatch')
        check_routing((root / 'src/app/app.cpp').read_text(encoding='utf-8'))
        report['executable_sha256_before'] = sha(exe.read_bytes())
        for label, (packed_sha, raw_sha) in FIXTURES.items():
            packed = (root / 'tests/fixtures/marker_storage' / (label + '.bin.gz')).read_bytes()
            (directory / (label + '.bin.gz')).write_bytes(packed)
            raw = decode_fixture(packed, packed_sha, raw_sha)
            (directory / (label + '.bin')).write_bytes(raw)
            report['fixtures'][label] = dict(compressed_sha256=sha(packed), raw_sha256=sha(raw), bytes=len(raw))
        request = (directory / 'requests.bin').read_bytes()
        expected = (directory / 'expected.bin').read_bytes()
        require(request[:12] == b'LZMW0001' + struct.pack('<I', OPERATIONS), 'invalid marker request header')
        require(expected[:12] == b'LZMO0001' + struct.pack('<I', OPERATIONS), 'invalid marker output header')
        require(len(expected) == 12 + OPERATIONS * STATE_BYTES, 'invalid marker output extent')
        args = [str(exe)] + (['--debug-marker-storage-original'] if production_app else [])
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
        require(result.returncode == 0, 'marker executable failed')
        marker = (b'marker_storage_original_app=ok operations=1008 seeds=44 updates=644 launches=160 portals=160 '
                  b'legacy_adoptions=0 legacy_retirements=0 seeded=1 natural_route=0 whole_game_claim=0') if production_app \
            else b'marker_storage_probe=ok operations=1008'
        require(marker in stdout.splitlines(), 'missing marker execution marker')
        actual = (directory / 'actual.bin').read_bytes()
        report.update(actual_sha256=sha(actual), first_difference=difference(actual, expected))
        require(report['first_difference'] is None, 'marker physical table differs from original')
        report['executable_sha256_after'] = sha(exe.read_bytes())
        require(report['executable_sha256_before'] == report['executable_sha256_after'], 'executable changed during comparison')
        report['passed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    report_path = directory / 'comparison.json'
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report, report_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--production-app', action='store_true')
    args = parser.parse_args()
    report, path = check(args.root, args.exe, args.out, args.production_app)
    if not report['passed']:
        print('marker_storage_original=failed report=' + str(path))
        print(report['error'])
        return 1
    print('marker_storage_original=ok operations=1008 compared_bytes=1587600 production_app=%d '
          'masks=0 seeded=1 natural_route=0 whole_game_claim=0 report=%s' % (args.production_app, path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
