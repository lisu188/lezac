"""Authenticate controlled original camera traces before exporting them."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/frame_camera'
MANIFEST_SHA='24271bd77c822a8615699b7e5c6179a78c80349b4a4fbf1ec619b9e72e755688'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=(fixture/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen camera manifest differs')
    manifest=json.loads(raw)
    require(sha((root/'tools/frame_camera_oracle.py').read_bytes())==manifest['producer_sha256'],'Camera producer differs')
    require(sha((root/'LEZAC.EXE').read_bytes())==manifest['executable_sha256'],'Original executable differs')
    require(manifest['schema']=='lezac-controlled-camera-v1' and manifest['cases']==1876 and
        manifest['register_states']==276203 and manifest['runtime_errors']==3 and
        len(manifest['executed_instructions'])==195 and manifest['unicorn_version']=='2.1.4' and
        manifest['unicorn_library_sha256']=='ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        all(manifest[k] is True for k in ('actual_library_mapping_verified','controlled_initial_memory',
            'full_memory_observer_control','endpoint_all_flags_compared')) and
        all(manifest[k] is False for k in ('raw_memory_published','natural_capture','full_frame_claim',
            'work_clock_claim','trace_arithmetic_flags_compared')),'Camera evidence profile differs')
    compressed=(fixture/'oracle.bin.gz').read_bytes()
    require(len(compressed)==manifest['compressed_bytes'] and sha(compressed)==manifest['compressed_sha256'],
        'Frozen compressed camera trace differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        decoded=stream.read(8918495)
    require(len(decoded)==8918494==manifest['projection_bytes'] and sha(decoded)==manifest['projection_sha256'],
        'Frozen decoded camera trace differs')
    return decoded


def run(root,fixture,out=None,report=None):
    if out and report:
        require(out.resolve()!=report.resolve(),'Camera report and export must not overlap')
    result=dict(status='failed',full_frame_claim=False)
    try:
        decoded=read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes()==decoded,'Existing camera export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=1876,bytes=len(decoded),sha256=sha(decoded))
    except Exception as error:
        result['error']=str(error)
        raise
    finally:
        if report:
            report.write_text(json.dumps(result,sort_keys=True)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    print(json.dumps(run(ROOT,FIXTURE,args.out,args.report),sort_keys=True))
