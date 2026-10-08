"""Cross-check the complete original updater against retained native DOSBox traces."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback

NATIVE_FIXTURES = {
    'weapon1_jump.txt': '8966baa5f29f325daec1732d20ade643ac714abe785bfb56cca648b7428fbb7b',
    'weapon1_left.txt': '5d192cc4f3675199de7a3f07f880f36e35d43adf3ba3b37ae6d1f6b8945f3932',
    'weapon1_none.txt': '5bb24f63e522a50d8f96429c8414eb8cc89804816d00c74792d7873663c2c697',
    'weapon1_right.txt': '63dac31b6f203e0b88856ba90f73e0fdfbe086326a2a22448bee4700b2f3e09b',
    'weapon2_jump.txt': 'c091f3475539e6c4040a792b03cf8b41da9ea8d95988532ebcb9c67e0aeff4e0',
    'weapon2_left.txt': 'd80d3efe978f44993d83258651d056a20996b2bb30dea00b92c0c72249acb44f',
    'weapon2_none.txt': 'e18eb7707d91bbef56d573205d19b25cc4d162b1a1371db87786869c51cab579',
    'weapon2_right.txt': '1bd23469e35fafc8a13a71caa735972c4ee55ff64f0cfe50ac8e5ab2fe8ecdcf',
    'weapon3_jump.txt': 'b56c67caf85a35ddc903ee9e20d4ff41d91b0fe474d76c32028f77b360fd8607',
    'weapon3_left.txt': '1fe26160d93c16d9bd73af78686fa635fbf862fab3aa1667936fe374666419d2',
    'weapon3_none.txt': '7382795041c5e571de61ad99bcb6e495e78b29aca4fa82fd0c67fe0c27cd2ad9',
    'weapon3_right.txt': '0dd0f9b32c0a25cee8283cd1bf2cf7240c286462123b0e38c29a20f8f7600514',
    'weapon4_jump.txt': '83a3d899ec9977c7afebb8b9ba795432677d99119ab79a81e20b43a88347c76e',
    'weapon4_left.txt': '9d0c2d77730eff505a8d89ff1ceccbd2f9ce208738531ac90c3387f4d2484ace',
    'weapon4_none.txt': '5324b0601b5db5ceb95b546b7f13fd2c37206bc2c7a32a9f332653ba52b60742',
    'weapon4_right.txt': 'bd24fc426859e60797dcaa6b00fe0f0efc8ecc94321b7111adf3bdfcfcfd9eac',
}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def imported_helper_identity(module):
    path = Path(module.__file__).resolve(strict=True)
    return dict(helper_path=str(path), helper_sha256=sha(path.read_bytes()))


def fields(line):
    pairs = [token.split('=', 1) for token in line.split()[1:]]
    assert all(len(pair) == 2 for pair in pairs)
    assert len({pair[0] for pair in pairs}) == len(pairs), 'duplicate native trace field'
    return dict(pairs)


def read_native(root):
    folder = root / 'tests/fixtures/bomb_motion_original'
    if folder.exists():
        assert not ({path.name for path in folder.glob('*.txt')} - set(NATIVE_FIXTURES))
    result = []
    for name, expected in NATIVE_FIXTURES.items():
        path = folder / name
        blob = (path.read_bytes() if path.exists() else subprocess.check_output(
            ['git', '-C', str(root), 'show', 'HEAD:tests/fixtures/bomb_motion_original/' + name], timeout=30))
        canonical = blob.replace(b'\r\n', b'\n')
        assert sha(canonical) == expected, 'native trace hash mismatch: ' + name
        lines = canonical.decode('ascii').splitlines()
        seed = fields(next(line for line in lines if line.startswith('seed ')))
        ticks = [fields(line) for line in lines if line.startswith('tick ')]
        expiry = fields(next(line for line in lines if line.startswith('expiry ')))
        start = int(seed['frame'])
        assert len(bytes.fromhex(seed['raw'])) == 38 and len(bytes.fromhex(seed['visual'])) == 8
        assert len(ticks) == int(expiry['updates'])
        assert [int(row['frame']) for row in ticks] == list(range(start + 1, start + 1 + len(ticks)))
        assert int(ticks[-1]['frame']) == int(expiry['frame'])
        timer = bytes.fromhex(seed['raw'])[2]
        for index, tick in enumerate(ticks):
            raw = bytes.fromhex(tick['raw'])
            assert len(raw) == 38 and len(bytes.fromhex(tick['visual'])) == 8
            timer -= int(tick['frame']) & 1
            assert raw[2] == timer and (timer == 0) == (index + 1 == len(ticks))
        result.append((Path(name), canonical, blob))
    assert len(result) == 16
    assert sum(sum(line.startswith(b'tick ') for line in blob.splitlines()) for _, blob, _ in result) == 2304
    return result

def main():
    if sys.flags.optimize:
        raise RuntimeError('optimized Python is not supported by original bomb analysis')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path)
    parser.add_argument('--unicorn-path', type=Path)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    ROOT = args.root.resolve()
    if args.self_check:
        read_native(ROOT)
        compile(Path(__file__).with_name('original_bomb_cpu.py').read_text(encoding='utf-8'), 'original_bomb_cpu.py', 'exec')
        print('original_bomb_lifetime_self_check=ok native_traces=16 updates=2304 executor_required=0 live=0')
        raise SystemExit(0)
    if args.out is None:
        parser.error('--out is required unless --self-check is used')
    if args.unicorn_path:
        sys.path.insert(0, str(args.unicorn_path.resolve()))
    sys.path.insert(0, str(ROOT / 'tools'))
    import original_bomb_cpu
    from original_bomb_cpu import BombCPU, DESCRIPTOR_SHA, EXE_SHA, LEVELS_SHA
    from scan_livels_debris_sites import load_levels
    OUT = args.out.resolve()
    assert not OUT.exists()
    report = dict(passed=False, traces=[], checks=[], original_calls_stubbed=False,
        original_instructions_patched=False, hardware_io_permitted=False,
        new_native_capture=False, complete_campaign_claim=False, compiled_cpp_comparison=False)


    def compare(actual, expected, label):
        if actual != expected:
            offsets = [i for i, (left, right) in enumerate(zip(actual, expected)) if left != right]
            report['mismatch'] = dict(label=label, actual=actual.hex(), expected=expected.hex(), offsets=offsets)
            raise AssertionError(report['mismatch'])
        report['checks'].append(dict(label=label, bytes=len(actual), differing_bytes=0))


    try:
        report.update(imported_helper_identity(original_bomb_cpu))
        level = load_levels(ROOT / 'LIVELS.SCH')[0]
        assert (level['width'], level['height']) == (60, 33)
        cpu = BombCPU(ROOT)
        for path, blob, raw_blob in read_native(ROOT):
            report['active_trace'] = path.name
            lines = blob.decode('ascii').splitlines()
            capture = next(line for line in lines if line.startswith('capture='))
            weapon = int(dict(token.split('=', 1) for token in capture.split())['weapon'])
            seed = fields(next(line for line in lines if line.startswith('seed ')))
            native_actor = bytes.fromhex(seed['raw'])
            native_visual = bytes.fromhex(seed['visual'])
            assert len(native_actor) == 38 and len(native_visual) == 8
            values = [int(part) for part in seed['input'].split(',')]
            assert len(values) == 4
            actor, visual = cpu.reset(level, weapon, *values, visual_cursor=native_actor[1], slot=int(seed['slot']))
            compare(actor, native_actor, path.name + ':constructor:actor')
            compare(visual, native_visual, path.name + ':constructor:visual')
            ticks = [fields(line) for line in lines if line.startswith('tick ')]
            expiry = fields(next(line for line in lines if line.startswith('expiry ')))
            assert len(ticks) == int(expiry['updates'])
            start = int(seed['frame'])
            assert [int(row['frame']) for row in ticks] == list(range(start + 1, start + 1 + len(ticks)))
            instructions = 0
            for index, tick in enumerate(ticks):
                report['active_tick'] = int(tick['frame'])
                actor, visual = cpu.update(int(tick['frame']))
                compare(actor, bytes.fromhex(tick['raw']), path.name + ':' + tick['frame'] + ':actor')
                compare(visual, bytes.fromhex(tick['visual']), path.name + ':' + tick['frame'] + ':visual')
                instructions += cpu.instructions
                if index + 1 == len(ticks):
                    assert actor[2] == 0 and '0x175cb' in cpu.boundaries
                    assert int(tick['frame']) == int(expiry['frame'])
                else:
                    assert actor[2] > 0 and '0x175cb' not in cpu.boundaries
            report['traces'].append(dict(name=path.name, sha256=sha(blob), raw_sha256=sha(raw_blob),
                weapon=weapon, updates=len(ticks), instructions=instructions,
                constructor_full_actor_compared=True, full_pre_expiry_actor_compared=True,
                full_visual_compared=True, complete_updates_and_expiry_executed=True,
                original_helpers_entered=dict(cpu.entries)))
        assert sum(row['updates'] for row in report['traces']) == 2304
        report.update(passed=True, native_traces=16, native_updates=2304, original_exe_sha256=EXE_SHA,
            levels_sha256=LEVELS_SHA, descriptor_fixture_sha256=DESCRIPTOR_SHA,
            compared_bytes=sum(row['bytes'] for row in report['checks']),
            generator_sha256=sha(Path(__file__).read_bytes()),
            limitation='Native actors/visuals cross-checked through pre-expiry; post-explosion maps and effects are not captured in these fixtures.')
        print(json.dumps(dict(passed=True, traces=16, updates=2304,
            compared_bytes=report['compared_bytes'], report=str(OUT))), flush=True)
    except BaseException:
        report['failure'] = traceback.format_exc()
        raise
    finally:
        report['recorded_utc'] = datetime.now(timezone.utc).isoformat()
        OUT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
