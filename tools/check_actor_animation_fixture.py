"""Authenticate the controlled original actor-animation instruction corpus."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/'tests/fixtures/actor_animation'
MANIFEST_SHA = '924a90a31810300368480f4025ce7c7ac30540548c957ad132a83d5778c2af2a'
INPUTS = ('LEZAC.EXE','tools/actor_animation_oracle.py','tools/frame_camera_oracle.py')
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw = (fixture/'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA,'Frozen actor-animation manifest differs')
    manifest = json.loads(raw)
    require(sha((root/'LEZAC.EXE').read_bytes()) == manifest['executable_sha256'],'Original executable differs')
    for name,digest in manifest['sources'].items():
        require(sha((root/'tools'/name).read_bytes()) == digest,'Actor-animation producer differs: '+name)
    require(manifest['schema'] == 'lezac-controlled-actor-animation-v1' and manifest['cases'] == 1011 and
        manifest['register_states'] == 71759 and manifest['writes'] == 14347 and manifest['string_bytes'] == 1897,
        'Actor-animation evidence domain differs')
    compressed = (fixture/'oracle.bin.gz').read_bytes()
    require(len(compressed) == manifest['compressed_bytes'] and sha(compressed) == manifest['compressed_sha256'],
        'Compressed actor-animation corpus differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        decoded = stream.read(2354312)
    require(len(decoded) == 2354311 == manifest['projection_bytes'] and sha(decoded) == manifest['projection_sha256'],
        'Decoded actor-animation corpus differs')
    return decoded


def run(root,fixture,out=None,report=None):
    protected = [root/name for name in INPUTS]+[fixture/'manifest.json',fixture/'oracle.bin.gz']
    for candidate in (out,report):
        if candidate:
            require(all(candidate.resolve() != path.resolve() and not (
                candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'Animation output must not replace an authenticated input')
    if out and report:
        require(out.resolve() != report.resolve() and not (
            out.exists() and report.exists() and out.samefile(report)),'Animation report/export overlap')
    result = dict(status='failed',whole_game_parity=False)
    try:
        decoded = read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes() == decoded,'Existing animation export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=1011,bytes=len(decoded),sha256=sha(decoded))
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        if report:
            report.write_text(json.dumps(result,sort_keys=True)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--report',type=Path)
    args = parser.parse_args()
    print(json.dumps(run(ROOT,FIXTURE,args.out,args.report),sort_keys=True))
