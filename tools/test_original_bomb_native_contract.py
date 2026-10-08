"""Exercise the native fixture contract without importing the optional executor."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from capture_original_bomb_lifetime import validate_lifetime_result, validate_native_report
from check_original_bomb_native import NATIVE_FIXTURES

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'tools/check_original_bomb_native.py'


class NativeBombContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = ROOT / 'tests/fixtures/bomb_motion_original'
        if folder.exists():
            names = [path.relative_to(ROOT).as_posix() for path in sorted(folder.glob('*.txt'))]
        else:
            tracked = subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', '-rz', '--name-only',
                                              'HEAD', 'tests/fixtures/bomb_motion_original'], timeout=30)
            names = [name.decode('utf-8') for name in tracked.split(b'\0') if name]
        cls.fixtures = {}
        for name in names:
            path = ROOT / name
            blob = path.read_bytes() if path.exists() else subprocess.check_output(
                ['git', '-C', str(ROOT), 'show', 'HEAD:' + name], timeout=30)
            cls.fixtures[Path(name).name] = blob.replace(b'\r\n', b'\n')
        if len(cls.fixtures) != 16:
            raise RuntimeError('expected all 16 committed native fixtures')

    def check(self, fixtures):
        with tempfile.TemporaryDirectory(prefix='lezac-bomb-native-contract-') as directory:
            root = Path(directory)
            destination = root / 'tests/fixtures/bomb_motion_original'
            destination.mkdir(parents=True)
            for name, blob in fixtures.items():
                (destination / name).write_bytes(blob)
            return subprocess.run([sys.executable, '-S', '-B', str(CHECKER), '--root', str(root), '--self-check'],
                capture_output=True, text=True, timeout=30,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1'))

    def test_lf_fixtures_without_optional_executor(self):
        result = self.check(self.fixtures)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('native_traces=16 updates=2304 executor_required=0 live=0', result.stdout)

    def test_crlf_fixtures(self):
        result = self.check({name: blob.replace(b'\n', b'\r\n') for name, blob in self.fixtures.items()})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mutated_actor_rejected(self):
        fixtures = self.fixtures.copy()
        name = sorted(fixtures)[0]
        fixtures[name] = fixtures[name].replace(b'raw=', b'raw=00', 1)
        result = self.check(fixtures)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('native trace hash mismatch', result.stderr)

    def test_truncated_trace_rejected(self):
        fixtures = self.fixtures.copy()
        name = sorted(fixtures)[0]
        fixtures[name] = fixtures[name].split(b'expiry ')[0]
        result = self.check(fixtures)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('native trace hash mismatch', result.stderr)

    def test_unregistered_trace_rejected(self):
        fixtures = {**self.fixtures, 'unexpected.txt': b'not a registered original trace\n'}
        self.assertNotEqual(self.check(fixtures).returncode, 0)

    def test_clean_lifetime_result_accepted_without_executor(self):
        validate_lifetime_result(dict(preserved_offsets_read=[],
            differential_groups_with_outside_preserved_differences=[]))

    def test_preserved_byte_read_rejected(self):
        with self.assertRaisesRegex(ValueError, 'preserved constructor bytes were read'):
            validate_lifetime_result(dict(preserved_offsets_read=[3],
                differential_groups_with_outside_preserved_differences=[]))

    def test_stale_pattern_difference_rejected(self):
        with self.assertRaisesRegex(ValueError, 'changed state outside preserved bytes'):
            validate_lifetime_result(dict(preserved_offsets_read=[],
                differential_groups_with_outside_preserved_differences=[
                    dict(group=[1, 0, 'shipped_level1', [0, 0]], field='masked_timeline_sha256')]))

    def native_report(self):
        return dict(passed=True, native_traces=16, native_updates=2304, compared_bytes=106720,
            helper_sha256='executor', generator_sha256='checker',
            traces=[dict(name=name, sha256=value) for name, value in NATIVE_FIXTURES.items()])

    def test_current_native_report_accepted(self):
        validate_native_report(self.native_report(), 'executor', 'checker')

    def test_stale_checker_report_rejected(self):
        report = self.native_report()
        report['generator_sha256'] = 'old-checker'
        with self.assertRaisesRegex(ValueError, 'checker hash mismatch'):
            validate_native_report(report, 'executor', 'checker')

    def test_changed_fixture_report_rejected(self):
        report = self.native_report()
        report['traces'][0]['sha256'] = 'modified-fixture'
        with self.assertRaisesRegex(ValueError, 'trace identities mismatch'):
            validate_native_report(report, 'executor', 'checker')

    def test_missing_fixture_report_rejected(self):
        report = self.native_report()
        report['traces'].pop()
        with self.assertRaisesRegex(ValueError, 'trace count mismatch'):
            validate_native_report(report, 'executor', 'checker')

    def test_duplicate_fixture_report_rejected(self):
        report = self.native_report()
        report['traces'][-1] = report['traces'][0].copy()
        with self.assertRaisesRegex(ValueError, 'trace identities mismatch'):
            validate_native_report(report, 'executor', 'checker')

    def test_optimized_checker_rejected(self):
        result = subprocess.run([sys.executable, '-O', '-S', '-B', str(CHECKER), '--self-check'],
            capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('optimized Python is not supported', result.stderr)

    def test_optimized_lifetime_rejected(self):
        result = subprocess.run([sys.executable, '-S', '-B',
            str(ROOT / 'tools/capture_original_bomb_lifetime.py'), '--help'],
            env=dict(os.environ, PYTHONOPTIMIZE='1'), capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('optimized Python is not supported', result.stderr)

    def test_optimized_validation_rejects_mismatch(self):
        result = subprocess.run([sys.executable, '-O', '-S', '-B', '-c',
            "from capture_original_bomb_lifetime import validate_lifetime_result;"
            "validate_lifetime_result({'preserved_offsets_read':[3],"
            "'differential_groups_with_outside_preserved_differences':[]})"],
            cwd=ROOT / 'tools', capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('preserved constructor bytes were read', result.stderr)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(NativeBombContractTests))
    if result.wasSuccessful():
        print('original_bomb_native_contract=ok tests=16 executor_required=0')
    raise SystemExit(0 if result.wasSuccessful() else 1)
