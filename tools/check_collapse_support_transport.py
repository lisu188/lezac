"""Verify pinned support-fixture bytes through real Git LF and CRLF checkouts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    'tests/gameplay/collapse_support_history_original.json':
        'a822125d99a78815dc4e7f1c831c01423858132285d3352d1002ce3332e59844',
    'tests/gameplay/collapse_support_history_original.bin.gz':
        '9435a944d7209a90f8de5584589d8e3cdbd2102af8fb89cf08bae91118a72f0a',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='attempt-', dir=args.out))
    report = dict(passed=False, game_executed=False, cases=[])
    git = shutil.which('git')
    if git is None:
        raise ValueError('Git is required for real checkout-byte regression')
    attributes = (ROOT / '.gitattributes').read_bytes()
    payloads = {name: (ROOT / name).read_bytes() for name in FILES}
    json_name, gzip_name = FILES
    json_rule, gzip_rule = (name.encode() + b' -text' for name in FILES)
    if any(attributes.splitlines().count(rule) != 1 for rule in (json_rule, gzip_rule)):
        raise ValueError('support fixtures must each have exactly one byte-preserving attribute')
    if any(sha(payloads[name]) != pin for name, pin in FILES.items()):
        raise ValueError('support fixture source bytes differ before checkout')
    variants = (
        ('lf', False, attributes, set()),
        ('crlf', True, attributes, set()),
        ('missing-json-rule', True, attributes.replace(json_rule + b'\n', b''), {json_name}),
        ('forced-json-text', True, attributes.replace(json_rule, json_name.encode() + b' text eol=crlf'), {json_name}),
        ('forced-gzip-text', True, attributes.replace(gzip_rule, gzip_name.encode() + b' text eol=crlf'), {gzip_name}),
    )
    try:
        for label, autocrlf, rules, changed in variants:
            directory = out / label
            repo, checkout = directory / 'repo', directory / 'checkout'
            repo.mkdir(parents=True)
            commands = []

            def run(*arguments):
                result = subprocess.run([git, *map(str, arguments)], cwd=repo, capture_output=True, timeout=20,
                    env=dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull))
                commands.append(dict(args=list(map(str, arguments)), returncode=result.returncode,
                    stdout=result.stdout.decode(errors='replace'), stderr=result.stderr.decode(errors='replace')))
                if result.returncode:
                    raise ValueError('checkout transport command failed: ' + str(arguments))
                return result.stdout

            run('init', '--quiet')
            for key, value in (('gc.auto', '0'), ('maintenance.auto', 'false'), ('core.autocrlf', str(autocrlf).lower()),
                               ('core.eol', 'crlf' if autocrlf else 'lf'), ('core.safecrlf', 'false')):
                run('config', key, value)
            (repo / '.gitattributes').write_bytes(rules)
            for name, raw in payloads.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            run('add', '--', '.gitattributes', *FILES)
            attribute_bytes = run('check-attr', '-z', 'text', '--', *FILES)
            fields = attribute_bytes.split(b'\0')
            if fields[-1] != b'' or len(fields) != 7:
                raise ValueError('Git attribute response dimensions differ')
            rows = [tuple(value.decode() for value in fields[index:index + 3]) for index in (0, 3)]
            if label in ('lf', 'crlf') and rows != [(name, 'text', 'unset') for name in FILES]:
                raise ValueError('Git does not see byte-preserving support attributes')
            run('checkout-index', '--prefix=' + checkout.resolve().as_posix() + '/', '--', *FILES)
            outputs = {name: (checkout / name).read_bytes() for name in FILES}
            actual_changed = {name for name in FILES if outputs[name] != payloads[name]}
            if actual_changed != changed:
                raise ValueError('checkout-byte mutant was not detected: ' + label)
            if label in ('missing-json-rule', 'forced-json-text'):
                if outputs[json_name] != payloads[json_name].replace(b'\n', b'\r\n'):
                    raise ValueError('metadata failure is not the exact CRLF conversion')
                if json.loads(outputs[json_name]) != json.loads(payloads[json_name]):
                    raise ValueError('metadata transport changed semantic data unexpectedly')
            (directory / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
            report['cases'].append(dict(label=label, core_autocrlf=autocrlf, attributes=rows,
                changed=sorted(actual_changed), checkout_sha256={name: sha(raw) for name, raw in outputs.items()}))
        report.update(passed=True, real_git_checkouts=5, transport_mutants=3, exact_fixture_pins=FILES)
    except BaseException as error:
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print('collapse_support_transport_retained=' + str(out.resolve()), flush=True)
        if sum(path.stat().st_size for path in args.out.rglob('*') if path.is_file()) >= 8 * 1024**2:
            raise ValueError('fixture transport diagnostics exceed local reserve')
    print('collapse_support_transport_contract=ok real_git_checkouts=5 transport_mutants=3 game_executed=0')


if __name__ == '__main__':
    main()
