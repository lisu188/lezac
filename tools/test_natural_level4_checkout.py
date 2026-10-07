"""Keep native evidence byte-exact under an autocrlf-enabled Git checkout."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = (
    'tests/fixtures/natural_level4_first_objective',
    'docs/recovery/evidence/natural_level4_first_objective_20261007',
    'tests/fixtures/natural_level4_portal',
    'docs/recovery/evidence/natural_level4_portal_20261007',
    'tests/fixtures/natural_level4_third_objective',
    'docs/recovery/evidence/natural_level4_third_objective_20261007',
)
RULES = {f'{directory}/** -text'.encode() for directory in DIRECTORIES}
MANIFESTS = tuple(directory + '/manifest.json' for directory in DIRECTORIES[1::2])


class EvidenceCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.git = shutil.which('git')
        self.assertIsNotNone(self.git, 'Git is required to verify checkout transformations')
        self.files = {path.relative_to(ROOT).as_posix(): path.read_bytes()
                      for directory in DIRECTORIES
                      for path in sorted((ROOT / directory).rglob('*')) if path.is_file()}
        for manifest in MANIFESTS:
            self.assertIn(manifest, self.files)
        for directory in DIRECTORIES[::2]:
            self.assertIn(directory + '/route.txt', self.files)
            self.assertIn(directory + '/guard-input.json', self.files)

    def checkout(self, omit_pins=False):
        with tempfile.TemporaryDirectory(prefix='lezac-level4-checkout-') as temporary:
            repo = Path(temporary)
            environment = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                               GIT_ATTR_NOSYSTEM='1')

            def git(*arguments, data=None):
                try:
                    return subprocess.check_output(
                        [self.git, '-c', 'core.autocrlf=true', '-c', 'core.safecrlf=false',
                         '-c', 'safe.directory=' + repo.as_posix(),
                         '-c', 'core.attributesFile=' + os.devnull, *arguments],
                        cwd=repo, env=environment, input=data, stderr=subprocess.PIPE)
                except subprocess.CalledProcessError as error:
                    self.fail(error.stderr.decode(errors='replace'))

            git('init', '--quiet')
            attributes = (ROOT / '.gitattributes').read_bytes()
            if omit_pins:
                attributes = b'\n'.join(line for line in attributes.splitlines() if line not in RULES) + b'\n'
            (repo / '.gitattributes').write_bytes(attributes)
            for name, data in self.files.items():
                blob = git('hash-object', '-w', '--stdin', data=data).decode().strip()
                git('update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + name)
            output = repo / 'checkout'
            output.mkdir()
            git('checkout-index', '--all', '--force', '--prefix=checkout/')
            return {name: (output / name).read_bytes() for name in self.files}

    def test_all_pinned_files_survive_autocrlf_checkout(self):
        checked_out = self.checkout()
        for name, expected in self.files.items():
            with self.subTest(path=name):
                self.assertEqual(expected, checked_out[name])

    def test_missing_rules_reproduce_manifest_hash_failure(self):
        checked_out = self.checkout(omit_pins=True)
        for manifest in MANIFESTS:
            self.assertNotIn(b'\r\n', self.files[manifest])
            self.assertIn(b'\r\n', checked_out[manifest])
            self.assertNotEqual(self.files[manifest], checked_out[manifest])
        for directory in DIRECTORIES[::2]:
            route = directory + '/route.txt'
            self.assertNotEqual(self.files[route], checked_out[route])


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(EvidenceCheckoutTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    print('natural_level4_checkout_attributes=ok tests=2 negative_control=1')
