from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import uuid

import level1_fidelity as fidelity
import natural_level4_support_column as support

ROOT = Path(__file__).resolve().parents[1]
BASE = 11740
END = 12240
SHA256 = 'df39d4ac769d61e0073f1382ddca883e5572e7dfca48a7f4e6868d79557183b2'
PATTERNS = {
    'right_long_medium': [(11742, 'down', 'x'), (11778, 'up', 'x'),
                          (11782, 'down', 'n'), (11783, 'up', 'n'),
                          (11785, 'down', 'z'), (11812, 'up', 'z')],
    'right_short_medium': [(11742, 'down', 'x'), (11762, 'up', 'x'),
                           (11766, 'down', 'n'), (11767, 'up', 'n'),
                           (11769, 'down', 'z'), (11787, 'up', 'z')],
    'left_short_medium': [(11742, 'down', 'z'), (11762, 'up', 'z'),
                          (11766, 'down', 'n'), (11767, 'up', 'n'),
                          (11769, 'down', 'x'), (11787, 'up', 'x')],
}


def check(condition, description):
    if not condition:
        raise ValueError(description)


def make_route(source, pattern, last=END):
    check(pattern in PATTERNS, 'unknown candidate input')
    check(last > max(row[0] for row in PATTERNS[pattern]), 'candidate expires before key release')
    check(source.startswith(b'LEZAC_LEVEL1_ROUTE_V1\n'), 'invalid pinned route header')
    lines = source.decode('ascii').splitlines()
    check(lines[-1] == 'end' and lines.count('ticks 11740') == 1, 'invalid pinned route')
    check(not any(line.startswith('event ') and int(line.split()[1]) >= BASE for line in lines),
          'existing route already extends beyond anchor')
    lines[lines.index('ticks 11740')] = f'ticks {last}'
    added = [f'event {tick} {action} {key}' for tick, action, key in PATTERNS[pattern]]
    return ('\n'.join([*lines[:-1], *added, 'end']) + '\n').encode('ascii')


def pinned():
    route = support.FIXTURE / 'route.txt'
    source = route.read_bytes()
    check(hashlib.sha256(source).hexdigest() == SHA256, 'untrusted route bytes')
    support.check_route(route)
    evidence = support.manifest()
    guard = (support.FIXTURE / 'guard-input.json').read_bytes()
    check(hashlib.sha256(guard).hexdigest() == evidence['fixture_pins']['guard-input.json'] and
          evidence['guard_input_source']['kind'] == 'cpp_typed_mutation_stimulus_only' and
          evidence['guard_input_source']['tick'] == BASE and
          evidence['guard_input_source']['phase'] == 'post_update' and
          evidence['reference_header']['level4_completion_claim'] is False,
          'untrusted endpoint stimulus or scope')
    return source, fidelity.strict_json(guard.decode('utf-8'))


def inspect_trace(directory, endpoint, pattern, last, route, settings, events):
    check((directory / 'trace.jsonl').is_file(), 'missing scout trace')
    expected_native = support.fixture()[-2]
    check((expected_native['section'], expected_native['index'], expected_native['phase']) ==
          ('level4', BASE, 'post_update'), 'wrong original-backed checkpoint')
    expected_route_hash = fidelity.fnv1a64(route.read_bytes())
    asset_hashes = {name: fidelity.fnv1a64((ROOT / name).read_bytes()) for name in fidelity.ASSETS}
    header_seen = False
    last_seq = None
    checkpoint_count = 0
    found = False
    complete = False
    snapshots = 0
    checked_images = 0
    presented_frames = 0
    next_tick = BASE
    best_destroyed = 244
    first_gain = None
    lowest_health = None
    first_level5 = None
    gate_ticks = []
    final = None
    with (directory / 'trace.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            check(0 < len(line) <= 12 * 1024 * 1024, 'bad scout trace line')
            row = fidelity.strict_json(line)
            if row['kind'] == 'header':
                check(not header_seen and snapshots == 0 and row['ticks'] == last and
                      row['schema'] == 'lezac.level1.scout.v1' and
                      row['source'] == 'cpp' and row['capture_from_tick'] == BASE and
                      row['phase_model'] == 'cpp-pre-actors-v2' and
                      row['state_scope'] == 'level1-observations-v2' and
                      row['input_model'] == 'sdl-events-original-intro-wait-v1' and
                      row['seed'] == settings['seed'] and row['step_us'] == settings['step_us'] and
                      row['route_fnv1a64'] == expected_route_hash and
                      row['asset_fnv1a64'] == asset_hashes and
                      (row['width'], row['height']) == (320, 200) and
                      row['candidate_only'] is True and row['original_fidelity_claim'] is False,
                      'unexpected C++ capture provenance')
                header_seen = True
                continue
            check(header_seen, 'missing C++ scout header')
            if row['kind'] == 'complete':
                check(not complete and last_seq is not None and row['ticks'] == last and
                      row['frames'] == last - BASE + 1 and
                      row['retained_checkpoints'] == checkpoint_count and
                      row['checkpoints'] == last_seq + 1 and
                      row['events'] == sum(map(len, events.values())) and
                      row['capture_from_tick'] == BASE and
                      row['level1_route_complete'] is True and
                      row['candidate_only'] is True and
                      row['original_fidelity_claim'] is False and
                      row['port_functionally_complete'] is False, 'bad C++ scout footer')
                complete = True
                continue
            check(not complete and row['kind'] == 'checkpoint' and
                  row['phase'] in ('input', 'present', 'after_nonplayers', 'post_update'), 'bad C++ state boundary')
            tick = row['tick']
            check(row['events'] == events.get(tick - 1, []) and
                  row['time_ms'] == (tick - 1) * settings['step_us'] // 1000,
                  'scout input or time boundary differs')
            if last_seq is not None:
                check(row['seq'] == last_seq + 1, 'missing C++ checkpoint sequence')
            last_seq = row['seq']
            checkpoint_count += 1
            if row['phase'] == 'present':
                presented_frames += 1
            if row['phase'] == 'present' and (tick in (BASE, last) or tick % 100 == 0):
                check(row['frame'] == f'frame_{tick:06d}.ppm', 'incorrect presentation filename')
                pixels = fidelity.read_ppm(directory / row['frame'])
                check(fidelity.fnv1a64(pixels) == row['rgb_fnv1a64'],
                      'captured C++ image differs from its reported fingerprint')
                checked_images += 1
            if row['phase'] != 'post_update':
                continue
            check(tick == next_tick and tick <= last, 'missing or reordered C++ post-update state')
            state = row['state']
            if tick == BASE:
                check(not found and state['level'] == 4 and state['progress'][:2] == [3, 244] and
                      state['words_hex'] == endpoint['words_hex'] and
                      state['tiles_hex'] == endpoint['tiles_hex'] and
                      state['random_seed'] == endpoint['random_seed'] and
                      state['logic_tick'] == endpoint['logic_tick'] and
                      all(state['players'][0][key] == endpoint['players'][0][key] for key in
                          ('x', 'y', 'vx8', 'vy8', 'frac_x', 'frac_y', 'score',
                           'animation', 'inventory', 'hud_score')) and
                      state['players'][0]['health'][:2] == endpoint['players'][0]['health'] and
                      state['players'][1]['inventory'] == endpoint['players'][1]['inventory'],
                      'candidate diverges before the new input')
                support.recovered.check_cpp(state, expected_native)
                found = True
            if state['level'] == 4:
                destroyed = state['progress'][1]
                check(0 <= destroyed <= 435, 'invalid Level 4 destruction counter')
                if destroyed > best_destroyed:
                    best_destroyed = destroyed
                    if first_gain is None:
                        first_gain = tick
                if state['progress'][0] >= 3 and destroyed >= 305 and not state['collapse']:
                    gate_ticks.append(tick)
            if state['level'] >= 5 and first_level5 is None:
                first_level5 = tick
            health = state['players'][0]['health'][0]
            lowest_health = health if lowest_health is None else min(lowest_health, health)
            next_tick = tick + 1
            snapshots += 1
            final = state
    check(found and complete and snapshots == last - BASE + 1 and
          presented_frames == last - BASE + 1 and next_tick == last + 1,
          'incomplete C++ candidate trace')
    return dict(status='candidate_only', pattern=pattern, original_game_verified=False,
                level4_complete_verified=False, original_level5_handoff_verified=False,
                route_end_tick=last, baseline_destroyed=244, best_destroyed=best_destroyed,
                new_destruction=best_destroyed - 244, first_gain_tick=first_gain,
                lowest_health=lowest_health, final_level=final['level'],
                final_objectives=final['progress'][0], final_destroyed=final['progress'][1],
                final_health=final['players'][0]['health'][0],
                final_player_xy=[final['players'][0]['x'], final['players'][0]['y']],
                cpp_gate_candidate_ticks=gate_ticks[:12], cpp_level5_first_tick=first_level5,
                checked_cplusplus_images=checked_images, post_update_states=snapshots)


def replay(exe, out, pattern, last, timeout):
    check(exe.is_file() and not out.exists(), 'executable missing or output already exists')
    source, endpoint = pinned()
    out.mkdir(parents=True)
    candidate_route = out / 'candidate.route'
    candidate_route.write_bytes(make_route(source, pattern, last))
    base_settings, base_events = fidelity.read_route(support.FIXTURE / 'route.txt')
    settings, events = fidelity.read_route(candidate_route)
    check(settings == {**base_settings, 'ticks': last} and
          {tick: rows for tick, rows in events.items() if tick < BASE} == base_events,
          'ordinary-input campaign prefix changed')
    capture = out / ('run-' + uuid.uuid4().hex)
    command = [str(exe.resolve()), '--replay-level1-scout', str(candidate_route),
               str(capture), str(BASE), '--original-intro-wait', '--result-reels']
    environment = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
                       LEZAC_LOAD_JSON_ASSETS='0', LEZAC_LOAD_ORIGINAL_ASSETS='1')
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                            timeout=timeout, env=environment)
    (out / 'child.json').write_text(json.dumps(dict(exit_code=result.returncode,
        stderr_tail=result.stderr[-2400:]), sort_keys=True), encoding='utf-8')
    check(result.returncode == 0, 'C++ candidate failed: ' + result.stderr[-1800:])
    check(hashlib.sha256((support.FIXTURE / 'route.txt').read_bytes()).hexdigest() == SHA256,
          'campaign replay modified its original route')
    report = inspect_trace(capture, endpoint, pattern, last, candidate_route, settings, events)
    (out / 'summary.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n',
                                      encoding='utf-8')
    frame = capture / f'frame_{last:06d}.ppm'
    if frame.is_file():
        shutil.copyfile(frame, out / 'last-frame.ppm')
    return report


class ScoutChecks(unittest.TestCase):
    def setUp(self):
        self.source = b'LEZAC_LEVEL1_ROUTE_V1\nseed 305441741\nticks 11740\nstep_us 40800\nevent 1 down x\nevent 2 up x\nend\n'

    def test_prefix_retained(self):
        for key in PATTERNS:
            rows = make_route(self.source, key).decode().splitlines()
            self.assertEqual(rows[:3], ['LEZAC_LEVEL1_ROUTE_V1', 'seed 305441741', 'ticks 12240'])
            self.assertEqual(rows[3:6], ['step_us 40800', 'event 1 down x', 'event 2 up x'])
            self.assertEqual(rows[-1], 'end')
            self.assertEqual(len(rows), 13)

    def test_inputs_are_balanced(self):
        for rows in PATTERNS.values():
            held = set()
            for tick, action, key in rows:
                self.assertGreater(tick, BASE)
                if action == 'down':
                    self.assertNotIn(key, held)
                    held.add(key)
                else:
                    self.assertIn(key, held)
                    held.remove(key)
            self.assertFalse(held)

    def test_preexisting_future_input_rejected(self):
        damaged = self.source.replace(b'end\n', b'event 11750 down z\nend\n')
        with self.assertRaisesRegex(ValueError, 'existing route'):
            make_route(damaged, 'right_long_medium')

    def test_incomplete_release_rejected(self):
        with self.assertRaisesRegex(ValueError, 'candidate expires'):
            make_route(self.source, 'right_long_medium', 11812)

    def test_unknown_candidate_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unknown candidate'):
            make_route(self.source, 'nonexistent')

    def test_pinned_original_route_unchanged(self):
        source, endpoint = pinned()
        self.assertEqual(hashlib.sha256(source).hexdigest(), SHA256)
        self.assertEqual((endpoint['level'], endpoint['progress']), (4, [3, 244]))


    def attempt_trace(self, mutation=None):
        endpoint = dict(level=4, progress=[3, 244], words_hex='0000', tiles_hex='00',
                        random_seed=12345, logic_tick=10117, players=[
                            dict(x=255, y=360, vx8=0, vy8=0, frac_x=47, frac_y=126,
                                 score=51190, animation=[1, 10, 17, 1, 4, 0, 1],
                                 inventory=[200, 4, 0, 0, 1], hud_score=[51190, 2],
                                 health=[22, 0]),
                            dict(inventory=[200, 20, 6, 0, 0])])
        state = dict(endpoint, collapse=[], players=[
            {**endpoint['players'][0], 'health': [22, 0, False]},
            endpoint['players'][1]])
        seed, step = 305441741, 40800
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            route = root / 'candidate.route'
            route.write_bytes(b'synthetic candidate route')
            header = dict(kind='header', schema='lezac.level1.scout.v1',
                          source='cpp', capture_from_tick=BASE, ticks=BASE + 1,
                          phase_model='cpp-pre-actors-v2',
                          state_scope='level1-observations-v2',
                          input_model='sdl-events-original-intro-wait-v1',
                          seed=seed, step_us=step,
                          route_fnv1a64=fidelity.fnv1a64(route.read_bytes()),
                          asset_fnv1a64={}, width=320, height=200,
                          candidate_only=True, original_fidelity_claim=False)
            rows = [header]
            for tick in (BASE, BASE + 1):
                for phase in ('input', 'present', 'after_nonplayers', 'post_update'):
                    row = dict(kind='checkpoint', seq=len(rows) - 1, tick=tick,
                               phase=phase, events=[], time_ms=(tick - 1) * step // 1000,
                               state=copy.deepcopy(state))
                    if phase == 'present':
                        row['frame'] = f'frame_{tick:06d}.ppm'
                        row['rgb_fnv1a64'] = fidelity.fnv1a64(b'pixel')
                    rows.append(row)
            rows.append(dict(kind='complete', ticks=BASE + 1, frames=2,
                             retained_checkpoints=8, checkpoints=8, events=0,
                             capture_from_tick=BASE, level1_route_complete=True,
                             candidate_only=True, original_fidelity_claim=False,
                             port_functionally_complete=False))
            if mutation == 'route':
                rows[0]['route_fnv1a64'] = '0' * 16
            elif mutation == 'player':
                rows[4]['state']['players'][0]['x'] = 256
            elif mutation == 'missing':
                rows.pop(-2)
                rows[-1]['retained_checkpoints'] = 7
                rows[-1]['checkpoints'] = 7
            elif mutation == 'missing_present':
                rows.pop(2)
                for row in rows[2:-1]:
                    row['seq'] -= 1
                rows[-1]['retained_checkpoints'] = 7
                rows[-1]['checkpoints'] = 7
            (root / 'trace.jsonl').write_text(
                '\n'.join(json.dumps(row) for row in rows) + '\n', encoding='utf-8')
            expected = dict(section='level4', index=BASE, phase='post_update')
            with mock.patch.object(support, 'fixture', return_value=[{}, expected]), \
                 mock.patch.object(support.recovered, 'check_cpp'), \
                 mock.patch.object(fidelity, 'ASSETS', ()), \
                 mock.patch.object(fidelity, 'read_ppm', return_value=b'pixel'):
                return inspect_trace(root, endpoint, 'right_long_medium', BASE + 1,
                                     route, dict(seed=seed, step_us=step), {})

    def test_synthetic_trace_valid(self):
        report = self.attempt_trace()
        self.assertEqual((report['post_update_states'], report['checked_cplusplus_images']), (2, 2))
        self.assertFalse(report['original_game_verified'])

    def test_route_substitution_rejected(self):
        with self.assertRaisesRegex(ValueError, 'provenance'):
            self.attempt_trace('route')

    def test_changed_player_start_rejected(self):
        with self.assertRaisesRegex(ValueError, 'candidate diverges'):
            self.attempt_trace('player')

    def test_omitted_post_update_or_present_rejected(self):
        for mutation in ('missing', 'missing_present'):
            with self.assertRaisesRegex(ValueError, 'incomplete C++ candidate trace'):
                self.attempt_trace(mutation)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('self-test', 'replay'))
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--pattern', choices=sorted(PATTERNS), default='right_long_medium')
    parser.add_argument('--ticks', type=int, default=END)
    parser.add_argument('--timeout', type=int, default=800)
    args = parser.parse_args()
    if args.action == 'self-test':
        result = unittest.TextTestRunner(verbosity=0).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(ScoutChecks))
        if not result.wasSuccessful():
            raise SystemExit(1)
        print('campaign_level4_continuation_scout=ok checks=10 candidates=3')
        return
    check(args.exe is not None and args.out is not None, 'executable and output required')
    report = replay(args.exe, args.out, args.pattern, args.ticks, args.timeout)
    print('campaign_level4_candidate=' + json.dumps(report, sort_keys=True, separators=(',', ':')),
          flush=True)


if __name__ == '__main__':
    main()
