"""Authenticate controlled original view-copy endpoints before exporting them."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/frame_view_copy'
MANIFEST_SHA = '4ec783c7e5e2d5e37cd55fc8e027ffa920b8223c54d0d0a61f4a6f0b1c4d9086'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_fixture(root=ROOT, fixture=FIXTURE):
    raw = (fixture / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen view-copy manifest differs')
    manifest = json.loads(raw)
    require(sha((root / 'tools/frame_view_copy_oracle.py').read_bytes()) == manifest['producer_sha256'],
        'View-copy producer differs')
    exe = (root / 'LEZAC.EXE').read_bytes()
    require(sha(exe) == manifest['executable_sha256'] and
        sha(exe[0x95f8:0x9647]) == manifest['instruction_sha256'], 'Original executable differs')
    require(manifest['schema'] == 'lezac-controlled-view-copy-v1' and len(manifest['cases']) == 12 and
        manifest['controlled_initial_memory'] is True and manifest['actual_library_mapping_verified'] is True and
        manifest['unicorn_version'] == '2.1.4' and manifest['unicorn_library_sha256'] ==
        'ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        all(manifest[name] is False for name in ('natural_capture','interrupts','port_io','raw_memory_published',
            'full_frame_claim','work_clock_claim')), 'View-copy evidence scope differs')
    compressed = (fixture / 'oracle.bin.gz').read_bytes()
    require(len(compressed) == manifest['compressed_bytes'] and sha(compressed) == manifest['compressed_sha256'],
        'Frozen view-copy compressed data differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        decoded = stream.read(787525)
    require(len(decoded) == 787524 == manifest['projection_bytes'] and
        sha(decoded) == manifest['projection_sha256'], 'Frozen view-copy endpoints differ')
    return decoded


def run(root, fixture, out=None, report=None):
    if out and report:
        require(out.resolve() != report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),
            'View-copy output and report paths overlap; preserved')
    result = dict(status='failed',full_frame_claim=False)
    try:
        decoded = read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes() == decoded, 'Existing view-copy output differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=12,bytes=len(decoded),sha256=sha(decoded))
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
