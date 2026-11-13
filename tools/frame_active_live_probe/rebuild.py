"""Extend an owned pristine observer, retaining its complete previous identity."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OWN=Path(__file__).resolve().parent
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()


def rebuild(host,retain):
    host=host.resolve(strict=True);retain=retain.resolve()
    if not host.is_relative_to(Path('/dev/shm')) or not retain.is_relative_to(Path('/dev/shm')) or retain.exists():
        raise ValueError('Use an owned RAM host and a new RAM retention directory')
    if shutil.disk_usage('/dev/shm').free<512*1024**2:
        raise ValueError('RAM reserve is insufficient')
    root=host/'dosbox-0.74-3';binary=root/'src/dosbox'
    record=json.loads((host/'build.json').read_bytes())
    if record['schema']!='lezac-pristine-observer-build-v1' or record['status']!='built' or record['build_exit']!=0:
        raise ValueError('Host is not a completed pristine observer build')
    if sha(binary)!=record['host_sha256'] or sha(ROOT/'tools/active_frame_probe/build.py')!=record['builder_sha256']:
        raise ValueError('Pristine host or builder identity differs')
    for name,digest in {**record['compiled_source_hashes'],**record['release_generated_hashes']}.items():
        if sha(root/name)!=digest:
            raise ValueError('Retained compiler input differs: '+name)
    retain.mkdir()
    for path,name in [(binary,'dosbox'),(host/'build.json','build.json'),
            (root/'src/cpu/lezac_work_probe.h','lezac_work_probe.h'),(root/'src/hardware/vga_draw.cpp','vga_draw.cpp')]:
        shutil.copyfile(path,retain/name)
        if sha(path)!=sha(retain/name):
            raise ValueError('Retention copy differs')
    record.update(schema='lezac-active-observer-build-v1',status='building',build_exit=None,
        previous_host_retained=str(retain),previous_host_sha256=sha(retain/'dosbox'),
        previous_build_sha256=sha(retain/'build.json'),active_rebuilder_sha256=sha(Path(__file__)))
    try:
        shutil.copyfile(OWN/'lezac_work_probe.h',root/'src/cpu/lezac_work_probe.h')
        shutil.copyfile(OWN/'vga_frame_observation.inc',root/'src/cpu/vga_frame_observation.inc')
        target=root/'src/hardware/vga_draw.cpp';before=target.read_text()
        after=before+'\n#include "../cpu/vga_frame_observation.inc"\n'
        patch=''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),
            fromfile='a/src/hardware/vga_draw.cpp',tofile='b/src/hardware/vga_draw.cpp'))
        (retain/'active-vga.patch').write_text(patch)
        environment=record['build_environment']
        result=subprocess.run(['patch','--batch','--forward','-p1','-i',str(retain/'active-vga.patch')],
            cwd=root,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
        (retain/'patch.log').write_bytes(result.stdout);result.check_returncode()
        sources={str(path.relative_to(root)):sha(path) for parent in ('src','include')
            for path in (root/parent).rglob('*') if path.is_file() and path.suffix in ('.cpp','.h','.inc')}
        result=subprocess.run(['make','-j2'],cwd=root,env=environment,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)
        (retain/'build.log').write_bytes(result.stdout);record['build_exit']=result.returncode
        result.check_returncode()
        for name,digest in {**sources,**record['release_generated_hashes']}.items():
            if sha(root/name)!=digest:
                raise ValueError('Source changed during rebuild: '+name)
        record['patched_device_sources']['src/hardware/vga_draw.cpp']=sha(target)
        record.update(status='built',host_sha256=sha(binary),probe_sha256=sha(OWN/'lezac_work_probe.h'),
            active_vga_fragment_sha256=sha(OWN/'vga_frame_observation.inc'),compiled_source_hashes=sources,
            patched_vga_sha256=sha(target))
        print(json.dumps(dict(status='built',host_sha256=record['host_sha256'])),flush=True)
    except BaseException as error:
        record.update(status='failed',error=repr(error))
        raise
    finally:
        (host/'build.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',type=Path,required=True)
    parser.add_argument('--retain',type=Path,required=True)
    args=parser.parse_args();rebuild(args.host,args.retain)
