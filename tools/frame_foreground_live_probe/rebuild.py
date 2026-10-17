"""Replace only an owned host's read-only selector, retaining the previous identity."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--host',type=Path,required=True);parser.add_argument('--retain',type=Path,required=True)
args=parser.parse_args();host=args.host.resolve(strict=True);retain=args.retain.resolve()
assert host.is_relative_to(Path('/dev/shm')) and retain.is_relative_to(Path('/dev/shm')) and not retain.exists()
assert shutil.disk_usage('/dev/shm').free>256*1024**2
root=host/'dosbox-0.74-3';common=Path(__file__).resolve().parents[1]/'frame_foreground_probe'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();record=json.loads((host/'build.json').read_bytes())
binary=root/'src/dosbox';header=root/'src/cpu/lezac_work_probe.h'
assert sha(binary)==record['host_sha256'] and sha(header)==record['probe_sha256']
assert sha(root/'src/cpu/core_normal.cpp')==record['source_hashes']['src/cpu/core_normal.cpp']
assert sha(root/'src/cpu/lezac_clock_observation.h')==record['clock_api_sha256']==sha(common/'lezac_clock_observation.h')
assert all(sha(root/'src/cpu'/name)==digest==sha(common/name) for name,digest in record['device_fragment_hashes'].items())
assert all(sha(root/name)==digest for name,digest in record['patched_device_sources'].items())
retain.mkdir()
for path,name in [(binary,'dosbox'),(header,'lezac_work_probe.h'),(host/'build.json','build.json')]:
 shutil.copy2(path,retain/name);assert sha(path)==sha(retain/name)
source=Path(__file__).with_name('lezac_work_probe.h');shutil.copy2(source,header)
environment=dict(PATH='/usr/bin:/bin',TMPDIR='/dev/shm',LANG='C.UTF-8',LC_ALL='C.UTF-8')
result=subprocess.run(['make','-j2'],cwd=root,env=environment,capture_output=True,timeout=600)
(retain/'build.log').write_bytes(result.stdout+result.stderr);result.check_returncode()
record.update(host_sha256=sha(binary),probe_sha256=sha(source),rebuild_producer_sha256=sha(Path(__file__)),
 repair_producer_sha256=sha(Path(__file__)),previous_host_retained=str(retain),build_exit=0,status='built',
 build_environment=environment,build_environment_is_complete=True)
(host/'build.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(host_sha256=record['host_sha256'])),flush=True)
