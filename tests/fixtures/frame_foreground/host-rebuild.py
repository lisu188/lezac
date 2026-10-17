import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
root=Path('/dev/shm/lezac-frame-hud-host-t208/dosbox-0.74-3')
source=Path('/dev/shm/lezac-clock-caller-t202/tools/frame_foreground_probe')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record=json.loads((root.parent/'build.json').read_bytes())
assert sha(root/'src/dosbox')==record['host_sha256']
assert sha(root/'src/cpu/lezac_work_probe.h')==record['probe_sha256']
label=sys.argv[1] if len(sys.argv)>1 else 'r1';assert label.isalnum()
retain=Path('/dev/shm/lezac-clock-frontier-t209/retained-'+label+'-host');retain.mkdir()
for path,name in [(root/'src/dosbox','dosbox'),(root/'src/cpu/lezac_work_probe.h','lezac_work_probe.h'),(root.parent/'build.json','build.json')]:
    shutil.copy2(path,retain/name);assert sha(path)==sha(retain/name)
shutil.copy2(source/'lezac_work_probe.h',root/'src/cpu/lezac_work_probe.h')
r=subprocess.run(['make','-j2'],cwd=root,capture_output=True,env=dict(os.environ,TMPDIR='/dev/shm'),timeout=600)
(retain/'build.log').write_bytes(r.stdout+r.stderr);r.check_returncode()
record.update(host_sha256=sha(root/'src/dosbox'),probe_sha256=sha(source/'lezac_work_probe.h'),
    previous_host_retained=str(retain),repair_producer_sha256=sha(Path(__file__)))
(root.parent/'build.json').write_text(json.dumps(record,indent=2)+'\n');print(record['host_sha256'])
