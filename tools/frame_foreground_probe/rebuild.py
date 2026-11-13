"""Reuse an owned host, retaining its binary and every replaced observer source."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--host',type=Path,required=True)
parser.add_argument('--retain',type=Path,required=True);args=parser.parse_args()
host=args.host.resolve(strict=True);retain=args.retain.resolve();source=Path(__file__).parent
assert host.is_relative_to(Path('/dev/shm')) and retain.is_relative_to(Path('/dev/shm')) and not retain.exists()
assert shutil.disk_usage('/dev/shm').free>256*1024**2
record=json.loads((host/'build.json').read_bytes());sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
root=host/'dosbox-0.74-3';binary=root/'src/dosbox'
assert sha(binary)==record['host_sha256']
assert sha(root/'src/cpu/core_normal.cpp')==record['source_hashes']['src/cpu/core_normal.cpp']
old={'lezac_work_probe.h':record['probe_sha256'],'lezac_clock_observation.h':record['clock_api_sha256'],**record['device_fragment_hashes']}
assert all(sha(root/'src/cpu'/name)==digest for name,digest in old.items())
gfx=root/'src/gui/sdlmain.cpp';pin='59e78cf3f7c3423e17a27adde5993c8c4156bdef0e2a03927e88fa6b7bf85c6b'
assert sha(gfx)==pin
assert all(sha(root/name)==digest for name,digest in record['patched_device_sources'].items())
retain.mkdir()
for path,name in [(binary,'dosbox'),(host/'build.json','build.json'),(gfx,'sdlmain.cpp')]+[(root/'src/cpu'/name,name) for name in old]:
    shutil.copy2(path,retain/name)
    assert sha(path)==sha(retain/name)
fragments={**record['device_fragment_hashes'],'gfx_clock_observation.inc':''}
for name in ['lezac_work_probe.h','lezac_clock_observation.h',*fragments]:
    shutil.copy2(source/name,root/'src/cpu'/name)
before=gfx.read_text();after=before+'\n#include "../cpu/gfx_clock_observation.inc"\n'
patch=''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),
    fromfile='a/src/gui/sdlmain.cpp',tofile='b/src/gui/sdlmain.cpp'))
patch_path=retain/'gfx-getter.patch';patch_path.write_text(patch)
result=subprocess.run(['patch','--batch','--forward','-p1','-i',str(patch_path)],cwd=root,capture_output=True,timeout=30)
(retain/'patch.log').write_bytes(result.stdout+result.stderr);result.check_returncode()
result=subprocess.run(['make','-j2'],cwd=root,capture_output=True,
    env=dict(os.environ,TMPDIR='/dev/shm'),timeout=600)
(retain/'rebuild.log').write_bytes(result.stdout+result.stderr);result.check_returncode()
record['source_hashes']['src/gui/sdlmain.cpp']=pin
record['patched_device_sources']['src/gui/sdlmain.cpp']=sha(gfx)
record.update(host_sha256=sha(binary),probe_sha256=sha(source/'lezac_work_probe.h'),
    clock_api_sha256=sha(source/'lezac_clock_observation.h'),
    device_fragment_hashes={name:sha(source/name) for name in fragments},
    gfx_patch_sha256=sha(patch_path),reused_task_owned_host=True,
    previous_host_retained=str(retain),rebuild_producer_sha256=sha(Path(__file__)),build_exit=0,status='built')
(host/'build.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(host_sha256=record['host_sha256'],
    rebuild_producer_sha256=record['rebuild_producer_sha256'])),flush=True)
