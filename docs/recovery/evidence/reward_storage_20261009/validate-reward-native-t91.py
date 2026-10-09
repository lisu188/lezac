"""Validate repeated original streams without claiming C++ App write-through."""
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import traceback

VIS = Path('/mnt/c/Users/andrz/.codex/visualizations/2026/07/05/019f3283-94f8-7603-b1b5-c9d78bf86769')
SOURCE = Path('/tmp/lezac-marker-writeback-20261009-t90')
OUT = Path('/tmp/lezac-reward-native-validation-20261009-t91')
CAP = 8 * 1024**2
STATE = 1585
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def le16(raw, at):
    return struct.unpack_from('<H', raw, at)[0]


def signed(raw, at):
    return struct.unpack_from('<h', raw, at)[0]


def actor(state, slot):
    return state[slot * 38:(slot + 1) * 38]


def visual(state, ref):
    return state[1178 + ref * 8:1178 + (ref + 1) * 8]


def records(state):
    result = {}
    assert len(state) == STATE and state[1570] <= 30
    for slot in range(1, state[1570] + 1):
        raw = actor(state, slot)
        key = raw[36:38]
        assert key not in result and 2 <= raw[1] <= state[1571] - 1
        result[key] = (raw, visual(state, raw[1]))
    return result


def check_step(before, after, tick, descriptors):
    old, new = records(before), records(after)
    assert set(new) <= set(old), 'reward pass allocated a new actor'
    assert after[1571] == before[1571] + after[1570] - before[1570]
    assert before[1442:1570] == after[1442:1570], 'reward pass changed inactive links'
    assert before[1572:1575] == after[1572:1575], 'reward pass changed link count or allocation result'
    assert before[:38] == after[:38] and before[1178:1194] == after[1178:1194], 'player fixture bytes changed'
    assert before[1581:1585] == after[1581:1585], 'reward pass changed alive/contact bytes'
    draws = 0
    for player in range(2):
        previous, current = before[1579 + player], after[1579 + player]
        if previous != current:
            assert previous == 0 and 1 <= current <= 7
            draws += 1
    rng = struct.unpack_from('<I', before, 1575)[0]
    for unused in range(draws):
        rng = (rng * 0x08088405 + 1) & 0xffffffff
    assert struct.unpack_from('<I', after, 1575)[0] == rng, 'pickup RNG consumption changed'
    counts = Counter(draws=draws, retired=len(old) - len(new))
    for identity, (raw, row) in new.items():
        previous, previous_row = old[identity]
        assert raw[3:6] == previous[3:6] and raw[14:20] == previous[14:20]
        assert raw[29:38] == previous[29:38], 'opaque tail or animation backup changed'
        if previous[0] >= 0x13:
            assert 0x13 <= previous[0] <= 0x19 and previous[21] == 2
            timer = (previous[2] - (tick & 1)) & 255
            if raw[0] == previous[0]:
                assert raw[2] == timer and timer not in (0, 255)
                assert raw[20:22] == previous[20:22]
                assert row[4:6] == previous_row[4:6], 'ordinary animation rewrote dimensions'
                counts['reward_continuations'] += 1
            elif raw[0] == 0:
                assert timer in (0, 255) and raw[2] == 18 and raw[21] == 5
                assert raw[6:10] == bytes(4)
                assert raw[22:29] == bytes((74, 74, 79, 2, 2, 1, 1))
                assert row[4:8] == descriptors[74 * 4:75 * 4]
                assert raw[20] == 16 - row[5]
                counts['expiry_conversions'] += 1
            elif raw[0] == 11:
                assert draws and raw[2] == 26 - (tick & 1) and raw[21] == 5
                assert raw[27] == 0
                sprite = (88, 86, 87, 88, 89, 86, 90)[previous[0] - 0x13]
                assert row[4:8] == descriptors[sprite * 4:(sprite + 1) * 4]
                assert raw[20] == 16 - row[5]
                counts['pickup_conversions'] += 1
            else:
                raise AssertionError('unexpected reward conversion')
        else:
            assert previous[0] in (0, 11) and previous[21] == 5
            assert raw[0] == previous[0] and raw[20:22] == previous[20:22]
            assert raw[2] == ((previous[2] - (tick & 1)) & 255) and raw[2] != 0
            assert row[4:6] == previous_row[4:6]
            for position, velocity, fraction in ((0, 6, 10), (2, 8, 12)):
                delta = previous[fraction] + signed(previous, velocity)
                assert le16(row, position) == (le16(previous_row, position) + delta // 256) & 65535
                assert raw[fraction:fraction + 2] == struct.pack('<H', delta & 255)
            assert raw[6:10] == previous[6:10]
            counts['transient_continuations'] += 1
    return counts


def main():
    assert not OUT.exists() and not (VIS / 'reward-native-validation-t91.json').exists()
    assert shutil.disk_usage('/dev/shm').free > 1503238553
    OUT.mkdir()
    report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(),
        producer_sha256=sha(Path(__file__).read_bytes()), actual_app_runtime_verified=False,
        full_reward_cpp_comparison=False, original_only_full_tables=True,
        compiled_helper_scope='ActorAnimation only; each input is an original pre-pass record, not a continuous C++ game replay',
        natural_route=False, whole_game_claim=False, masks_applied=False, commands=[])
    try:
        roots = [Path('/tmp/lezac-reward-storage-' + name + '-20261009-t91-v3') for name in ('original', 'repeat')]
        originals = [json.loads((root / 'original-reward-storage.json').read_bytes()) for root in roots]
        assert all(row['passed'] and row['operations'] == 4982 and len(row['cases']) == 87 for row in originals)
        assert originals[0]['cases'] == originals[1]['cases']
        assert all(row['producer_sha256'] == sha((VIS / 'capture-reward-storage-t91-v3.py').read_bytes()) for row in originals)
        streams = {}
        report['streams'] = {}
        for name in ('requests', 'expected'):
            packed = (roots[0] / (name + '.bin.gz')).read_bytes()
            assert packed == (roots[1] / (name + '.bin.gz')).read_bytes() and len(packed) < 256 * 1024
            raw = gzip.decompress(packed)
            assert len(raw) < CAP
            assert all(sha(packed) == row[name]['sha256'] and sha(raw) == row[name]['raw_sha256'] for row in originals)
            streams[name] = raw
            report['streams'][name] = dict(bytes=len(raw), sha256=sha(raw), compressed_bytes=len(packed), compressed_sha256=sha(packed))
        request, expected = streams['requests'], streams['expected']
        assert request[:8] == b'LZRW0001' and expected[:8] == b'LZRO0001'
        count = struct.unpack_from('<I', request, 8)[0]
        assert count == struct.unpack_from('<I', expected, 8)[0] == 4982
        assert len(expected) == 12 + count * STATE
        descriptors = request[12 + 1980 + 3960:12 + 1980 + 3960 + 368]
        assert [16 - descriptors[sprite * 4 + 1] for sprite in range(62, 69)] == [4, 6, 6, 6, 6, 6, 0]
        at, operation = 12 + 1980 + 3960 + 368, 0
        totals, coverage = Counter(), Counter()
        animation_inputs, animation_expected = bytearray(), bytearray()
        validated_steps = []
        for case in originals[0]['cases']:
            assert operation == case['first_operation'] and request[at] == ord('S')
            at += 1
            before = request[at:at + STATE]
            at += STATE
            assert before == expected[12 + operation * STATE:12 + (operation + 1) * STATE]
            assert before[1570] == case['count']
            records(before)
            operation += 1
            for frame in range(100 + case['parity'], 100 + case['parity'] + case['frames']):
                assert request[at] == ord('U') and le16(request, at + 1) == frame
                at += 3
                after = expected[12 + operation * STATE:12 + (operation + 1) * STATE]
                totals.update(check_step(before, after, frame, descriptors))
                old, new = records(before), records(after)
                for identity, (raw, row) in new.items():
                    previous = old[identity][0]
                    if raw[0] == previous[0] and 0x13 <= raw[0] <= 0x19:
                        advanced = previous[27] != 0 and ((previous[25] + 1) & 255) > previous[26]
                        animation_inputs.extend(previous[22:36])
                        animation_expected.extend(raw[22:29] + bytes((advanced,)))
                        coverage[str(previous[27])] += 1
                        if advanced:
                            assert row[6:8] == descriptors[raw[22] * 4 + 2:raw[22] * 4 + 4]
                        else:
                            assert row[6:8] == old[identity][1][6:8]
                if before[1570] == after[1570] == 1:
                    validated_steps.append((before, after, frame))
                before = after
                operation += 1
            assert before[1570] == case['final_count']
            assert list(before[1579:1581]) == case['final_pending']
            if case['label'].startswith(('lifetime-', 'pool-')) or case['gate'] in ('p1', 'p2', 'both', 'occupied-p1'):
                assert before[1570] == 0
        assert operation == count and at == len(request) and set(coverage) == {'0', '1', '2', '3'}
        assert totals['draws'] == 35 and totals['pickup_conversions'] == 28
        assert totals['retired'] == 159
        helper_count = len(animation_expected) // 8
        helper_input = b'LZRP0001' + struct.pack('<I', helper_count) + animation_inputs
        helper_expected = b'LZRA0001' + struct.pack('<I', helper_count) + animation_expected
        (OUT / 'animation-input.bin').write_bytes(helper_input)
        (OUT / 'animation-expected.bin').write_bytes(helper_expected)

        def run(label, args):
            result = subprocess.run(list(map(str, args)), cwd=SOURCE, env=ENV, capture_output=True, timeout=120)
            (OUT / (label + '.stdout')).write_bytes(result.stdout)
            (OUT / (label + '.stderr')).write_bytes(result.stderr)
            report['commands'].append(dict(label=label, args=list(map(str, args)), returncode=result.returncode,
                stdout_sha256=sha(result.stdout), stderr_sha256=sha(result.stderr)))
            assert result.returncode == 0, (label, result.stderr[-2000:])

        run('compile', ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-O1', '-I', SOURCE / 'src',
                        VIS / 'reward-animation-probe-t91.cpp', '-o', OUT / 'animation-probe'])
        run('probe', [OUT / 'animation-probe', OUT / 'animation-input.bin', OUT / 'animation-actual.bin'])
        actual = (OUT / 'animation-actual.bin').read_bytes()
        assert actual == helper_expected
        # Corrupt one independently checked semantic field at a time, without relying on a hash gate.
        controls = {}
        before, after, tick = next(row for row in validated_steps if actor(row[0], 1)[0] == actor(row[1], 1)[0] >= 0x13)
        raw = actor(after, 1)
        for label, offset in (('opaque', 38 + 3), ('backup', 38 + 29), ('timer', 38 + 2),
                              ('behavior', 38 + 21), ('hotspot', 38 + 20), ('visual-width', 1178 + raw[1] * 8 + 4),
                              ('rng', 1575), ('alive', 1583), ('hits', 1581), ('allocation-result', 1573),
                              ('links', 1442), ('player-row', 1178)):
            changed = bytearray(after)
            changed[offset] ^= 1
            try:
                check_step(before, bytes(changed), tick, descriptors)
            except AssertionError:
                controls[label] = True
            else:
                raise AssertionError('semantic control survived: ' + label)
        source = (SOURCE / 'src/app/app.cpp').read_bytes()
        body = source.split(b'    void updateBonusDrops(', 1)[1].split(b'    void applyPendingBonus(', 1)[0]
        assert b'.animation.advance(' not in body and b'actorSlots_.write' not in body
        report.update(passed=True, operations=count, compared_native_table_bytes=count * STATE,
            original_repeat_equal=True, native_semantic_totals=dict(totals),
            compiled_animation_cases=helper_count, animation_modes=dict(coverage),
            compiled_animation_output_sha256=sha(actual), semantic_negative_controls=controls,
            source_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, env=ENV, text=True).strip(),
            app_source_sha256=sha(source), animation_header_sha256=sha((SOURCE / 'src/gameplay/actor_models.hpp').read_bytes()),
            current_reward_updater_missing_animation_advance=True,
            current_reward_updater_missing_physical_write_through=True,
            current_source_unchanged=True)
    except BaseException:
        report['failure'] = traceback.format_exc()
    finally:
        report['root_bytes'] = sum(path.stat().st_size for path in OUT.rglob('*') if path.is_file())
        assert report['root_bytes'] < CAP
        raw = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
        (OUT / 'validation.json').write_bytes(raw)
        (VIS / 'reward-native-validation-t91.json').write_bytes(raw)
        print(json.dumps(dict(passed=report['passed'], operations=report.get('operations'),
            compiled_animation_cases=report.get('compiled_animation_cases'), totals=report.get('native_semantic_totals'),
            failure=report.get('failure'), root_bytes=report['root_bytes'])), flush=True)
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
