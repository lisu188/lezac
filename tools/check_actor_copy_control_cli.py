"""Check bounded copy-control modes without claiming game or host stability."""
import argparse
import hashlib
import os
from pathlib import Path
import resource
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def run(exe):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    exe = exe.resolve(strict=True)
    paths = [exe, Path(__file__).resolve(), ROOT / 'tools/actor_copy_control.cpp',
             *sorted((ROOT / 'src/core').glob('*.hpp'))]
    protected = {path: sha(path) for path in paths}
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
    for mode, prefix in [('words', b'actor_copy_control=ok '), ('variant', b'actor_variant_control=ok ')]:
        for iterations in (1, 200000):
            result = subprocess.run([str(exe), str(iterations), mode], capture_output=True,
                                    timeout=30, env=environment)
            if (result.returncode or result.stderr or not result.stdout.startswith(prefix) or
                    b'diagnosis_claim=0 intermittent_hold_cleared=0' not in result.stdout):
                raise ValueError('Copy control positive result or scope differs')
    negatives = [['0'], ['16000001'], ['-1'], ['+1'], [''], ['1suffix'], [' 1'],
                 ['18446744073709551616'], ['1', 'unknown'], ['--help'],
                 ['1', 'words', 'extra'], ['1', 'variant', 'extra']]
    for arguments in negatives:
        result = subprocess.run([str(exe), *arguments], capture_output=True, timeout=30, env=environment)
        if result.returncode != 2 or result.stdout or result.stderr:
            raise ValueError('Copy control admitted an invalid CLI shape')
    if any(sha(path) != digest for path, digest in protected.items()):
        raise ValueError('Protected copy-control source or executable changed')
    print('actor_copy_control_cli=ok positive_controls=4 negative_controls=12 sources_preserved=1 '
          'game_fidelity_claim=0 host_stability_claim=0 intermittent_hold_cleared=0')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    run(parser.parse_args().exe)
