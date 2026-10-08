import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_corpse_identity_mutant as checker
import make_corpse_identity_mutant as generator


class IdentityCheckerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = self.root / 'tests/fixtures/input.txt'
        self.fixture.parent.mkdir(parents=True)
        self.fixture.write_bytes(b'fixture\n')
        self.exe = self.root / 'mutant.exe'
        self.exe.write_bytes(b'compiled mutant placeholder')
        self.out = self.root / 'reports'
        self.identity = patch.object(checker, 'FIXTURE_SHA256', hashlib.sha256(b'fixture\n').hexdigest())
        self.identity.start()
        self.addCleanup(self.identity.stop)

    def result(self, returncode=1, stdout=b'', stderr=b'shared-order corpse_front_full sample=0: unused birth identity\n'):
        return subprocess.CompletedProcess([], returncode, stdout, stderr)

    def reports(self):
        return [json.loads(path.read_bytes()) for path in self.out.glob('case-*/report.json')]

    def run_check(self):
        return checker.check(self.exe, self.fixture, self.out)

    def test_specific_mutant_failure_and_silent_child(self):
        def execute(command, **kwargs):
            self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
            self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
            self.assertEqual(kwargs['cwd'], self.root)
            self.assertEqual(command[1], '--debug-shared-actor-order-original')
            return self.result()
        with patch.object(checker.subprocess, 'run', side_effect=execute):
            report = self.run_check()
        self.assertTrue(report['passed'])
        self.assertEqual((report['failed_case'], report['failed_sample']), ('corpse_front_full', 0))
        self.assertEqual(report['binary_sha256'], hashlib.sha256(self.exe.read_bytes()).hexdigest())

    def test_success_is_not_mutant_rejection(self):
        with patch.object(checker.subprocess, 'run', return_value=self.result(returncode=0)):
            with self.assertRaisesRegex(ValueError, 'specific unused birth'):
                self.run_check()
        self.assertFalse(self.reports()[0]['passed'])

    def test_other_failure_is_not_mutant_rejection(self):
        with patch.object(checker.subprocess, 'run', return_value=self.result(stderr=b'cannot load assets')):
            with self.assertRaisesRegex(ValueError, 'specific unused birth'):
                self.run_check()

    def test_success_banner_invalidates_failure(self):
        with patch.object(checker.subprocess, 'run', return_value=self.result(stdout=b'shared_actor_order_original=ok')):
            with self.assertRaisesRegex(ValueError, 'specific unused birth'):
                self.run_check()

    def test_timeout_retains_partial_output(self):
        timeout = subprocess.TimeoutExpired('mutant', 60, output=b'partial out', stderr=b'partial error')
        with patch.object(checker.subprocess, 'run', side_effect=timeout):
            with self.assertRaisesRegex(ValueError, 'timed out'):
                self.run_check()
        self.assertEqual(next(self.out.glob('case-*/stdout.txt')).read_bytes(), b'partial out')
        self.assertEqual(next(self.out.glob('case-*/stderr.txt')).read_bytes(), b'partial error')
        self.assertFalse(self.reports()[0]['passed'])

    def test_changed_binary_is_rejected(self):
        def execute(*args, **kwargs):
            self.exe.write_bytes(b'replaced binary')
            return self.result()
        with patch.object(checker.subprocess, 'run', side_effect=execute):
            with self.assertRaisesRegex(ValueError, 'binary changed'):
                self.run_check()

    def test_invalid_fixture_is_attributed_before_rejection(self):
        self.fixture.write_bytes(b'bad fixture')
        with patch.object(checker.subprocess, 'run') as execute:
            with self.assertRaisesRegex(ValueError, 'fixture identity'):
                self.run_check()
            execute.assert_not_called()
        self.assertEqual(self.reports()[0]['fixture_sha256'], hashlib.sha256(b'bad fixture').hexdigest())

    def test_crlf_and_unique_retention(self):
        self.fixture.write_bytes(b'fixture\r\n')
        with patch.object(checker.subprocess, 'run', return_value=self.result()):
            self.run_check()
            self.run_check()
        self.assertEqual(len(self.reports()), 2)
        self.assertTrue(all(report['passed'] for report in self.reports()))

    def test_bounded_reads(self):
        self.fixture.write_bytes(b'12345')
        with self.assertRaisesRegex(ValueError, 'size limit'):
            checker.checked_bytes(self.fixture, 4)
        self.assertEqual(checker.checked_bytes(self.fixture, 5), b'12345')

    def test_generator_one_change_and_source_preservation(self):
        source = self.root / 'app.cpp'
        original = b'prefix\n' + generator.ANCHOR + b'suffix\n'
        source.write_bytes(original)
        output = self.root / 'generated/app.cpp'
        manifest = generator.generate(source, output)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(output.read_bytes(), original.replace(generator.ANCHOR,
                         generator.ANCHOR + b'            (void)claimActorOrder();\n'))
        self.assertEqual(manifest['source_sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(manifest['replacements'], 1)

    def test_generator_missing_or_duplicate_anchor(self):
        source = self.root / 'app.cpp'
        output = self.root / 'generated/app.cpp'
        for raw in (b'no anchor', generator.ANCHOR * 2):
            source.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'exactly one'):
                generator.generate(source, output)
        self.assertFalse(output.exists())

    def test_generator_cannot_overwrite_production_source(self):
        source = self.root / 'app.cpp'
        source.write_bytes(generator.ANCHOR)
        with self.assertRaisesRegex(ValueError, 'must not replace'):
            generator.generate(source, source)
        self.assertEqual(source.read_bytes(), generator.ANCHOR)


if __name__ == '__main__':
    unittest.main()
