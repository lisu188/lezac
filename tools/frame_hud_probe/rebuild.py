"""Incrementally rebuild an owned observation host while retaining its previous identity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--host',type=Path,required=True)
parser.add_argument('--retain',type=Path,required=True);args=parser.parse_args()
host=args.host.resolve(strict=True);retain=args.retain.resolve();source=Path(__file__).with_name('lezac_work_probe.h')
assert host.is_relative_to(Path('/dev/shm')) and retain.is_relative_to(Path('/dev/shm')) and not retain.exists()
assert shutil.disk_usage('/dev/shm').free>256*1024**2
record=json.loads((host/'build.json').read_bytes());sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
binary=host/'dosbox-0.74-3/src/dosbox';header=host/'dosbox-0.74-3/src/cpu/lezac_work_probe.h'
assert sha(binary)==record['host_sha256'] and sha(header)==record['probe_sha256']
assert sha(host/'dosbox-0.74-3/src/cpu/core_normal.cpp')==record['source_hashes']['src/cpu/core_normal.cpp']
retain.mkdir()
for path,name in [(binary,'dosbox'),(header,'lezac_work_probe.h'),(host/'build.json','build.json')]:
    shutil.copy2(path,retain/name)
assert sha(retain/'dosbox')==record['host_sha256'] and sha(retain/'lezac_work_probe.h')==record['probe_sha256']
shutil.copy2(source,header)
result=subprocess.run(['make','-j2'],cwd=host/'dosbox-0.74-3',capture_output=True,
    env=dict(os.environ,TMPDIR='/dev/shm'),timeout=600)
(retain/'rebuild.log').write_bytes(result.stdout+result.stderr);result.check_returncode()
record.update(host_sha256=sha(binary),probe_sha256=sha(source),reused_task_owned_host=True,
    previous_host_retained=str(retain),rebuild_producer_sha256=sha(Path(__file__)),build_exit=0,status='built')
(host/'build.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(host_sha256=record['host_sha256'],
    rebuild_producer_sha256=record['rebuild_producer_sha256'])),flush=True)
