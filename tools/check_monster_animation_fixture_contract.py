"""Exercise compiled animation replay's input binding without an original CPU."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    raw = args.fixture.read_bytes().replace(b'\r\n', b'\n')
    assert len(raw) == 56244
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
    executable = str(args.exe.resolve())
    rejected = 0
    with tempfile.TemporaryDirectory(prefix='lezac-animation-contract-') as directory:
        root = Path(directory)
        def execute(path):
            return subprocess.run([executable, str(path)], env=environment,
                capture_output=True, text=True, timeout=10)

        for label, payload in (('lf', raw), ('crlf', raw.replace(b'\n', b'\r\n'))):
            path = root / (label + '.txt')
            path.write_bytes(payload)
            result = execute(path)
            assert result.returncode == 0 and 'monster_animation_original=ok cases=53 updates=636' in result.stdout, result
        mutations = {
            'empty': b'',
            'truncated': raw[:-1],
            'changed_byte': raw.replace(b'active=09060900000001', b'active=08060900000001', 1),
            'trailing_record': raw + b'complete cases=53 updates=636\n',
            'isolated_cr': raw.replace(b'\n', b'\r', 1),
            'oversized': b'x' * (128 * 1024 + 1),
        }
        for label, payload in mutations.items():
            assert payload != raw
            path = root / (label + '.txt')
            path.write_bytes(payload)
            result = execute(path)
            assert result.returncode != 0 and 'monster_animation_original failed:' in result.stderr, result
            rejected += 1
        result = execute(root / 'missing.txt')
        assert result.returncode != 0 and 'monster_animation_original failed:' in result.stderr, result
        rejected += 1
    print(f'monster_animation_fixture_contract=ok accepted=2 rejected={rejected} compiled_helper=1 production_app=0')


if __name__ == '__main__':
    main()
