"""Authenticate the frozen complete offscreen raster projection without importing its producer."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/frame_world_raster'
MANIFEST_SHA='b8ed194eb2564869f170efff7b6c1af51d5b03c5ec1ad1b9a958db624af54701'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=(fixture/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen raster manifest differs')
    manifest=json.loads(raw)
    require(set(manifest['sources'])=={'frame_world_raster_oracle.py','frame_world_raster_inputs.py'},'Raster source domain differs')
    require(set(manifest['assets'])=={'LEZAC.EXE','CARO.CAR','BOMOMIMK.SPR','BOMPAL.PAL'},'Raster asset domain differs')
    for name,digest in manifest['sources'].items():
        require(sha((root/'tools'/name).read_bytes())==digest,'Raster source differs: '+name)
    for name,digest in manifest['assets'].items():
        require(sha((root/name).read_bytes())==digest,'Canonical raster asset differs: '+name)
    require(manifest['schema']=='lezac-controlled-world-raster-v1' and len(manifest['cases'])==22 and
        len(manifest['instruction_addresses'])==283 and manifest['unicorn_version']=='2.1.4' and
        manifest['unicorn_library_sha256']=='ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        all(manifest[k] is True for k in ('actual_library_mapping_verified','controlled_initial_state','full_memory_observer_control','endpoint_all_flags_compared')) and
        all(manifest[k] is False for k in ('raw_memory_published','natural_capture','full_frame_claim','work_clock_claim')),
        'Raster evidence profile differs')
    compressed=(fixture/'oracle.bin.gz').read_bytes()
    require(len(compressed)==manifest['compressed_bytes'] and sha(compressed)==manifest['compressed_sha256'],'Frozen compressed raster differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        decoded=stream.read(8119241)
    require(len(decoded)==8119240==manifest['projection_bytes'] and sha(decoded)==manifest['projection_sha256'],'Frozen raster projection differs')
    return decoded


def run(root,fixture,out=None,report=None):
    if out and report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),
            'Raster report and export must not overlap')
    result=dict(status='failed',full_frame_claim=False)
    try:
        raw=read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes()==raw,'Existing raster export differs; preserved')
            else:
                out.write_bytes(raw)
        result.update(status='passed',cases=22,bytes=len(raw),sha256=sha(raw))
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
