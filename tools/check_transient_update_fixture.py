"""Authenticate the original complete 45FA compact updater corpus."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/transient_update'
MANIFEST_SHA='86f3361c2974cc476a80f8c24a146909a9e9b2d193c8de6f7b07fd2a35f78b99'
PROJECTION_BYTES=2371154
INPUTS=('LEZAC.EXE','tools/transient_update_oracle.py','tools/capture_original_debris_update.py',
        'tools/scan_livels_debris_sites.py','tools/frame_camera_oracle.py')
sha=lambda raw:hashlib.sha256(raw).hexdigest()

def require(yes,message):
    if not yes:
        raise ValueError(message)

def bounded(path,size):
    with path.open('rb') as stream:
        raw=stream.read(size+1)
    require(len(raw)<=size,'Updater input exceeds reserve')
    return raw

def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=bounded(fixture/'manifest.json',65536)
    require(sha(raw)==MANIFEST_SHA,'Frozen updater manifest differs')
    manifest=json.loads(raw)
    inputs={**manifest['asset_sha256'],**{'tools/'+k:v for k,v in manifest['source_sha256'].items()}}
    require(set(inputs)==set(INPUTS),'Updater input catalog differs')
    for name,digest in inputs.items():
        require(sha(bounded(root/name,1048576))==digest,'Updater input differs: '+name)
    require(manifest['schema']=='lezac-controlled-transient-update-v1' and manifest['cases']==1142 and
        manifest['dense_cases']==18 and manifest['outcomes']==[1138,3,1] and
        manifest['original_instructions']==1110956 and manifest['ordered_writes']==122985 and
        manifest['unicorn_version']=='2.1.4' and
        manifest['unicorn_library_sha256']=='ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        all(manifest[k] is True for k in ('actual_library_mapping_verified','complete_memory_observer_control',
            'ordered_writes_reconstruct_memory','controlled_initial_memory')) and
        all(manifest[k]==0 for k in ('instruction_patches','calls_stubbed','interrupts_delivered','hardware_io')) and
        all(manifest[k] is False for k in ('later_state_injected','natural_capture','raw_memory_published',
            'actual_app_integration','full_frame_claim')),'Updater proof domain differs')
    require(manifest['projection_bytes']==PROJECTION_BYTES and manifest['compressed_bytes']==132840,
        'Updater projection reserve differs')
    packed=bounded(fixture/'oracle.bin.gz',132840)
    require(len(packed)==manifest['compressed_bytes'] and sha(packed)==manifest['compressed_sha256'],
        'Compressed updater projection differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        decoded=stream.read(PROJECTION_BYTES+1)
    require(len(decoded)==PROJECTION_BYTES and sha(decoded)==manifest['projection_sha256'],
        'Decoded updater projection differs')
    return decoded

def run(root,fixture,out=None,report=None):
    protected=[root/name for name in INPUTS]+[fixture/'manifest.json',fixture/'oracle.bin.gz',Path(__file__).resolve()]
    for candidate in (out,report):
        if candidate:
            require(all(candidate.resolve()!=path.resolve() and not
                (candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'Updater output must not replace protected input')
    if out and report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),'Updater report/export overlap')
    result=dict(status='failed',whole_game_parity=False)
    try:
        decoded=read_fixture(root,fixture)
        if out:
            if out.exists():
                require(bounded(out,PROJECTION_BYTES)==decoded,'Existing updater export differs; preserved')
            else:
                with out.open('xb') as stream:
                    stream.write(decoded)
        result.update(status='passed',cases=1142,bytes=len(decoded),sha256=sha(decoded))
    except Exception as error:
        result['error']=str(error)
        raise
    finally:
        if report:
            report.write_text(json.dumps(result,sort_keys=True)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path);parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    print(json.dumps(run(ROOT,FIXTURE,args.out,args.report),sort_keys=True))
