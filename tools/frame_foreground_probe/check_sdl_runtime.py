"""Reproduce an external-SDK loader mismatch and verify the pinned runtime fix."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from sdl_provenance import loaded_library,MARKER

parser=argparse.ArgumentParser(description=__doc__)
for name in ('source','sdk','out'):parser.add_argument('--'+name,type=Path,required=True)
args=parser.parse_args();out=args.out.resolve();sdk=args.sdk.resolve(strict=True)
assert out.is_relative_to(Path('/dev/shm')) and not out.exists() and shutil.disk_usage('/dev/shm').free>256*1024**2
out.mkdir();private=out/'sdk';headers=private/'usr/include/SDL';headers.parent.mkdir(parents=True)
shutil.copytree(sdk/'usr/include/SDL',headers)
libraries=private/'usr/lib/x86_64-linux-gnu';libraries.mkdir(parents=True)
original=(sdk/'usr/lib/x86_64-linux-gnu/libSDL.so').resolve(strict=True).read_bytes()
image=libraries/'libSDL-1.2.so.0';image.write_bytes(original+b'\nLEZAC runtime identity regression only\n')
(libraries/'libSDL.so').symlink_to(image.name)
sha=lambda raw:hashlib.sha256(raw).hexdigest()
command=[sys.executable,'-B',str(Path(__file__).with_name('build_palette_oracle.py')),'--source',str(args.source),
    '--sdk',str(private),'--out',str(out/'fixed')]
result=subprocess.run(command,capture_output=True,env=dict(os.environ,TMPDIR='/dev/shm',LD_LIBRARY_PATH='/nonexistent-lezac-sdk'),timeout=90)
(out/'fixed.log').write_bytes(result.stdout+result.stderr);result.check_returncode()
report=json.loads((out/'fixed/report.json').read_bytes())
assert report['sdl_runtime_library']['path']==str(image.resolve()) and report['sdl_runtime_library']['sha256']==sha(image.read_bytes())
assert report['run_environment']['LD_LIBRARY_PATH']==str(libraries)
legacy_environment=dict(PATH='/usr/bin:/bin',TMPDIR='/dev/shm',LANG='C.UTF-8',SDL_AUDIODRIVER='dummy',SDL_VIDEODRIVER='dummy')
legacy=subprocess.run([str(out/'fixed/oracle')],capture_output=True,env=legacy_environment,timeout=30)
(out/'without-loader-pin.log').write_bytes(legacy.stderr);legacy.check_returncode()
rejected=False
try:loaded_library(legacy.stderr,image,sha(image.read_bytes()))
except ValueError:rejected=True
assert rejected,'External SDK regression did not reproduce the review finding'
entries=[line[len(MARKER):] for line in legacy.stderr.decode().splitlines() if line.startswith(MARKER)];assert len(entries)==1
actual=Path(entries[0]).resolve(strict=True)
assert sha(actual.read_bytes())!=sha(image.read_bytes())
record=dict(status='passed',fixed_runtime=report['sdl_runtime_library'],legacy_runtime=dict(path=str(actual),sha256=sha(actual.read_bytes())),
    legacy_provenance_rejected=True,private_sdk_has_appended_identity_marker=True,original_sdk_unchanged=sha(original)==sha((sdk/'usr/lib/x86_64-linux-gnu/libSDL.so').resolve().read_bytes()),
    fixed_oracle_sha256=report['oracle_sha256'],legacy_oracle_sha256=sha(legacy.stdout),fixture_inputs_modified=False)
(out/'report.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
