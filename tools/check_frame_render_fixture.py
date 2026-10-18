"""Authenticate the frozen unchanged-original render-caller projection."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/frame_render'
MANIFEST_SHA='bfa8b74cf80e4932f3ca5ffff257919a6772cca8a7ac7043a9927de034d5f5c9'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=(fixture/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen render-caller manifest differs')
    manifest=json.loads(raw)
    require(set(manifest['sources'])=={'frame_render_inputs.py','frame_render_oracle.py',
        'frame_world_raster_inputs.py','frame_world_raster_oracle.py'},'Render source domain differs')
    require(set(manifest['assets'])=={'LEZAC.EXE','CARO.CAR','BOMOMIMK.SPR','BOMPAL.PAL'},'Render asset domain differs')
    for name,digest in manifest['sources'].items():
        require(sha((root/'tools'/name).read_bytes())==digest,'Render source differs: '+name)
    for name,digest in manifest['assets'].items():
        require(sha((root/name).read_bytes())==digest,'Canonical render asset differs: '+name)
    require(manifest['schema']=='lezac-controlled-render-caller-v1' and len(manifest['cases'])==26 and
        len(manifest['instruction_addresses'])==524 and manifest['unicorn_version']=='2.1.4' and
        manifest['unicorn_library_sha256']=='ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        all(manifest[k] is True for k in ('actual_library_mapping_verified','controlled_initial_state',
            'full_memory_observer_control','endpoint_all_flags_compared','interrupts_and_io_rejected')) and
        all(manifest[k] is False for k in ('raw_memory_published','natural_capture','full_frame_claim','work_clock_claim')) and
        manifest['original_calls_stubbed']==0 and manifest['instruction_patches']==0,
        'Render evidence profile differs')
    compressed=(fixture/'oracle.bin.gz').read_bytes()
    require(len(compressed)==manifest['compressed_bytes'] and sha(compressed)==manifest['compressed_sha256'],
        'Frozen compressed render trace differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        decoded=stream.read(14783107)
    require(len(decoded)==14783106==manifest['projection_bytes'] and sha(decoded)==manifest['projection_sha256'],
        'Frozen decoded render trace differs')
    return decoded


def run(root,fixture,out=None,report=None):
    if out and report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),
            'Render report and export must not overlap')
    result=dict(status='failed',full_frame_claim=False)
    try:
        decoded=read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes()==decoded,'Existing render export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=26,bytes=len(decoded),sha256=sha(decoded))
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
