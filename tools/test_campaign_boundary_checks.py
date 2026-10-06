"""Single-pass extra checks must preserve campaign and lifecycle rejection gates."""
from contextlib import ExitStack
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import level1_fidelity as fidelity
import natural_campaign as campaign
import natural_level3_return as returned


class CampaignBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='lezac-boundary-check-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.route = self.root / 'route.txt'
        self.route.write_bytes(b'route')
        self.rgb = b'rgb'
        self.mapped = {'value': 7}
        self.expected = [dict(kind='header', assets={}),
                         self.boundary(1, 'present'), self.boundary(1, 'post_update'),
                         self.boundary(4, 'result'), dict(kind='complete')]
        self.trace = [dict(kind='header', input_model='sdl-events-original-intro-wait-v1'),
                      dict(kind='checkpoint', tick=0, phase='initial', state=self.mapped),
                      dict(kind='checkpoint', tick=1, phase='present', state=self.mapped, frame='frame_000001.ppm'),
                      dict(kind='checkpoint', tick=1, phase='post_update', state=self.mapped),
                      dict(kind='complete', ticks=1)]
        reels = [dict(kind='header')]
        for index in range(76):
            name = f'result_frame_{index:06d}.ppm'
            (self.root / name).write_bytes(self.rgb)
            reels.append(dict(kind='sample', sample=index, player=1, frame=name, state=self.mapped))
        reels.append(dict(kind='complete', samples=76, original_fidelity_claim=False))
        (self.root / 'result_reels.jsonl').write_text('\n'.join(json.dumps(row) for row in reels), encoding='utf-8')
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(fidelity, 'load_manifest', return_value={'asset_sha256': {}}))
        self.reader = self.stack.enter_context(mock.patch.object(fidelity, 'trace_rows', side_effect=lambda *_: iter(self.trace)))
        self.stack.enter_context(mock.patch.object(fidelity, 'read_ppm', return_value=self.rgb))
        self.stack.enter_context(mock.patch.object(fidelity, 'validate_state'))
        self.stack.enter_context(mock.patch.object(campaign, 'cpp_boundary', side_effect=lambda state, *_: state))

    def boundary(self, tick, phase):
        return dict(tick=tick, phase=phase, region='test', mapped=self.mapped,
                    rgb_sha256=None if phase == 'post_update' else hashlib.sha256(self.rgb).hexdigest())

    def compare(self, **kwargs):
        return campaign.compare_rows(self.root, self.expected, self.route, 1, **kwargs)

    def test_default_report_and_single_validated_read(self):
        result = self.compare()
        self.assertEqual((result['frames'], result['boundaries'], result['pixels']), (2, 3, 128000))
        self.assertEqual(result['status'], 'match')
        self.reader.assert_called_once()

    def test_hook_visits_only_matched_present_post_and_result(self):
        calls = []
        result = self.compare(check_extra=lambda actual, wanted: calls.append((actual, wanted)))
        self.assertEqual([(wanted['tick'], wanted['phase']) for _, wanted in calls],
                         [(1, 'present'), (1, 'post_update'), (4, 'result')])
        self.assertEqual(calls[-1][0]['sample'], 4)
        self.assertEqual(result['boundaries'], 3)
        self.reader.assert_called_once()

    def test_hook_failure_is_not_swallowed(self):
        def reject(*_):
            raise fidelity.EvidenceError('extra mismatch')
        with self.assertRaisesRegex(fidelity.EvidenceError, 'extra mismatch'):
            self.compare(check_extra=reject)

    def test_mapped_mismatch_still_rejected_before_hook(self):
        self.trace[2]['state'] = {'value': 8}
        hook = mock.Mock()
        with self.assertRaisesRegex(fidelity.EvidenceError, 'differs'):
            self.compare(check_extra=hook)
        hook.assert_not_called()

    def test_rgb_mismatch_still_rejected_before_hook(self):
        self.expected[1]['rgb_sha256'] = '0' * 64
        hook = mock.Mock()
        with self.assertRaisesRegex(fidelity.EvidenceError, 'displayed pixels differ'):
            self.compare(check_extra=hook)
        hook.assert_not_called()

    def test_duplicate_boundary_is_rejected_before_second_hook(self):
        self.trace.insert(3, copy.deepcopy(self.trace[2]))
        hook = mock.Mock()
        with self.assertRaisesRegex(fidelity.EvidenceError, 'duplicate replay boundary'):
            self.compare(check_extra=hook)
        self.assertEqual(hook.call_count, 1)

    def test_missing_boundary_is_still_rejected(self):
        self.trace.pop(3)
        with self.assertRaisesRegex(fidelity.EvidenceError, 'missing native campaign boundaries'):
            self.compare(check_extra=lambda *_: None)

    def test_hook_cannot_bypass_incomplete_footer(self):
        self.trace[-1]['ticks'] = 0
        with self.assertRaisesRegex(fidelity.EvidenceError, 'incomplete full route'):
            self.compare(check_extra=lambda *_: None)

    def test_hook_cannot_bypass_result_inventory(self):
        (self.root / 'result_frame_000000.ppm').unlink()
        with self.assertRaisesRegex(fidelity.EvidenceError, 'result image inventory differs'):
            self.compare(check_extra=lambda *_: None)


class ReturnLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.state = dict(players=[dict(health=[100, 0, False], waiting=[65531, 0, True, 0])], flow=[False] * 8)
        self.extension = [dict(kind='header')]
        for index in range(4):
            self.extension.append(dict(tick=6355 + index // 2, phase=('present', 'post_update')[index % 2],
                                       lifecycle=returned.cpp_lifecycle(self.state)))
        self.extension.append(dict(kind='complete'))
        self.selected = self.extension[1:-1]
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(returned, 'FRAMES', 2))
        self.stack.enter_context(mock.patch.object(returned, 'fixture', return_value=self.extension))
        self.stack.enter_context(mock.patch.object(returned, 'prefix_rows', return_value=[]))
        self.stack.enter_context(mock.patch.object(campaign, 'fixture', return_value=[{}, {}]))
        self.stack.enter_context(mock.patch.object(campaign, 'compare_rows', side_effect=self.compare_rows))
        self.reader = self.stack.enter_context(mock.patch.object(fidelity, 'trace_rows',
                                              side_effect=AssertionError('unexpected second full trace read')))

    def compare_rows(self, cpp, rows, route, ticks, *, check_extra):
        for wanted in self.selected:
            check_extra(dict(state=self.state), wanted)
        return dict(status='match', frames=6038, boundaries=12000, pixels=386432000)

    def test_lifecycle_checks_share_main_comparison(self):
        report = returned.compare(Path('unused'))
        self.assertEqual(report['lifecycle_boundaries'], 4)
        self.reader.assert_not_called()

    def test_lifecycle_mismatch_is_rejected(self):
        self.state['players'][0]['waiting'][0] += 1
        with self.assertRaisesRegex(fidelity.EvidenceError, 'return lifecycle differs'):
            returned.compare(Path('unused'))

    def test_missing_lifecycle_boundary_is_rejected(self):
        self.selected = self.selected[:-1]
        with self.assertRaisesRegex(fidelity.EvidenceError, 'missing return lifecycle boundaries'):
            returned.compare(Path('unused'))

    def test_duplicate_lifecycle_boundary_is_rejected(self):
        self.selected.insert(1, self.selected[0])
        with self.assertRaisesRegex(fidelity.EvidenceError, 'return lifecycle differs'):
            returned.compare(Path('unused'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
