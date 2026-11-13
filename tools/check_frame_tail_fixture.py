"""Authenticate the frozen original post-queue tail projection."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/frame_tail'
MANIFEST_SHA = 'f042999d326385cbd2a96bc8be5c43440c6e7142960ee3050ad2aaf2213ad95a'
PROJECTION_BYTES = 14476040
COVERAGE = dict(cases=2576, completion_handoff=1158, dac_writes=40752,
    escape_handoff=210, instructions=688022, next_frame=616, runtime_error=576,
    view_change_handoff=16, writes=72808)
INPUTS = ('LEZAC.EXE','tools/actor_steering_oracle.py',
    'tools/frame_camera_oracle.py','tools/frame_tail_oracle.py')
sha = lambda raw: hashlib.sha256(raw).hexdigest()

def require(yes, message):
    if not yes:
        raise ValueError(message)

def bounded(path, size):
    with path.open('rb') as stream:
        raw = stream.read(size + 1)
    require(len(raw) <= size, 'Frame tail input exceeds its reserve')
    return raw

def read_fixture(root=ROOT, fixture=FIXTURE):
    raw = bounded(fixture/'manifest.json',65536)
    require(sha(raw)==MANIFEST_SHA, 'Frozen frame tail manifest differs')
    manifest = json.loads(raw)
    inputs = {**manifest['asset_sha256'],
        **{'tools/'+name:digest for name,digest in manifest['source_sha256'].items()}}
    require(set(inputs)==set(INPUTS), 'Frame tail input catalog differs')
    for name,digest in inputs.items():
        require(sha(bounded(root/name,1048576))==digest, 'Frame tail input differs: '+name)
    require(manifest['status']=='passed' and manifest['schema']=='lezac-controlled-frame-tail-v1' and
        manifest['coverage']==COVERAGE and manifest['unicorn_version']=='2.1.4' and
        manifest['unicorn_library_sha256']=='ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        manifest['observer_control']=='register-write-trace-versus-stop-only-code-hooks' and
        manifest['emulated_output_ports']==[0x3c8,0x3c9] and manifest['original_code_bytes_verified']==43552 and
        all(manifest[key] is True for key in ('actual_library_mapping_verified',
            'complete_initial_seed_reconstruction','complete_memory_observer_control',
            'ordered_writes_reconstruct_memory')) and
        all(manifest[key]==0 for key in ('instruction_patches','calls_stubbed','hardware_inputs','interrupts_delivered')) and
        all(manifest[key] is False for key in ('host_hardware_io','later_state_injected',
            'production_app_comparison','natural_capture','natural_route','full_frame_claim','raw_memory_published')),
        'Frame tail proof domain differs')
    require(manifest['projection_bytes']==PROJECTION_BYTES and manifest['compressed_bytes']==231225,
        'Frame tail projection reserve differs')
    packed = bounded(fixture/'oracle.bin.gz',231225)
    require(len(packed)==manifest['compressed_bytes'] and sha(packed)==manifest['compressed_sha256'],
        'Compressed frame tail projection differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        decoded = stream.read(PROJECTION_BYTES+1)
    require(len(decoded)==PROJECTION_BYTES and sha(decoded)==manifest['projection_sha256'],
        'Decoded frame tail projection differs')
    return decoded

def run(root, fixture, out=None, report=None):
    protected = [root/name for name in INPUTS]+[
        fixture/'manifest.json',fixture/'oracle.bin.gz',Path(__file__).resolve()]
    for candidate in (out,report):
        if candidate:
            require(all(candidate.resolve()!=path.resolve() and not
                (candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'Frame tail output must not replace a protected input')
    if out and report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)), 'Frame tail report/export overlap')
    result = dict(status='failed',whole_game_parity=False)
    try:
        decoded = read_fixture(root,fixture)
        if out:
            if out.exists():
                require(bounded(out,PROJECTION_BYTES)==decoded,'Existing frame tail export differs; preserved')
            else:
                with out.open('xb') as stream:
                    stream.write(decoded)
        result.update(status='passed',cases=COVERAGE['cases'],bytes=len(decoded),sha256=sha(decoded))
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
