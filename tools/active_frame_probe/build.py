"""Rebuild the read-only observer from pinned pristine sources, entirely in RAM."""
import argparse
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[2]
COMMON=ROOT/'tools/frame_foreground_probe'
ARCHIVE_SHA='c0d13dd7ed2ed363b68de615475781e891cd582e8162b5c3669137502222260a'
SDK_SHA='42f2799c0f5ac96f314797fdcfe90765849a6ad5389bde5b71d4be74ed448a7d'
DSC_SHA='9b1a0d34f24015912e4c294c2cbd6b187206ff1a3e4c22a6dfa290dd8cb694f1'
DISTRIBUTION_SHA='f915090262374413e520798625f5e0b948b3a408c2354ed37dd10e5bd52c083d'
SDL_SHA='b82090085ba665c89ea70909b9018a219c42029fdf9803e7d5e17c185d6d1d72'
PROBE_SHA='68fe30b3f8df287463c906a8b9f582fc2ced9f131ffb4b47eb2c3c1e450abc29'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()


def build(archive,descriptor,distribution,sdl_dev,sdl_runtime,out,probe):
    archive=archive.resolve(strict=True)
    sdl_dev=sdl_dev.resolve(strict=True)
    sdl_runtime=sdl_runtime.resolve(strict=True)
    descriptor=descriptor.resolve(strict=True)
    distribution=distribution.resolve(strict=True)
    probe=probe.resolve(strict=True)
    out=out.resolve()
    if any(sha(path)!=digest for path,digest in ((archive,ARCHIVE_SHA),(sdl_dev,SDK_SHA),
            (descriptor,DSC_SHA),(distribution,DISTRIBUTION_SHA),(sdl_runtime,SDL_SHA),(probe,PROBE_SHA))):
        raise ValueError('Pinned source, distribution or SDL input differs')
    if not out.is_relative_to(Path('/dev/shm')) or out.exists() or shutil.disk_usage('/dev/shm').free<2*1024**3:
        raise ValueError('Use a new RAM-only output with at least 2 GiB reserve')
    parsed=ast.parse((COMMON/'build.py').read_text())
    pins=next(ast.literal_eval(item.value) for item in parsed.body if isinstance(item,ast.Assign)
        and any(isinstance(target,ast.Name) and target.id=='pins' for target in item.targets))
    out.mkdir()
    report=dict(schema='lezac-pristine-observer-build-v1',status='building',build_exit=None,
        pristine_archive_sha256=ARCHIVE_SHA,sdl_development_package_sha256=SDK_SHA,
        distribution_descriptor_sha256=DSC_SHA,distribution_archive_sha256=DISTRIBUTION_SHA,
        builder_sha256=sha(Path(__file__)),host_instrumented=True,guest_instruction_patches=0,
        copied_build_products=False,source_filesystem='tmpfs',output_filesystem='tmpfs',
        baseline_uninstrumented_binary_built=False,base_host_sha256=None)
    try:
        with tarfile.open(archive) as source:
            members=source.getmembers()
            if sum(member.size for member in members)>64*1024**2 or any(
                    not (member.name.startswith('dosbox-0.74-3/') or
                        member.name=='dosbox-0.74-3' and member.isdir()) for member in members):
                raise ValueError('Pristine archive layout differs')
            source.extractall(out,filter='data')
        root=out/'dosbox-0.74-3'
        pristine_cpu=sha(root/'src/cpu/core_normal.cpp')
        with tarfile.open(distribution) as patches:
            members=patches.getmembers()
            if sum(member.size for member in members)>16*1024**2 or any(
                    not (member.name.startswith('debian/') or member.name=='debian' and member.isdir())
                    for member in members):
                raise ValueError('Distribution archive layout differs')
            patches.extractall(root,filter='data')
        sdk=out/'sdk'
        sdk.mkdir()
        subprocess.run(['dpkg-deb','-x',str(sdl_dev),str(sdk)],check=True)
        library=sdk/'usr/lib/x86_64-linux-gnu'/sdl_runtime.name
        shutil.copyfile(sdl_runtime,library)
        alias=library.parent/'libSDL-1.2.so.0'
        if alias.exists() or alias.is_symlink():
            raise ValueError('Unexpected SDK runtime alias')
        alias.symlink_to(library.name)
        report.update(sdl_runtime_source=str(sdl_runtime),sdl_runtime_sha256=sha(library),
            expected_sdl_image=str(library),pristine_cpu_sha256=pristine_cpu)
        (out/'home').mkdir()
        environment=dict(PATH=str(sdk/'usr/bin')+':/usr/bin:/bin',HOME=str(out/'home'),
            TMPDIR=str(out),LANG='C.UTF-8',LC_ALL='C.UTF-8',CONFIG_SITE='/dev/null',
            CC='/usr/bin/gcc',CXX='/usr/bin/g++',CFLAGS='-O2 -g0',CXXFLAGS='-O2 -g0 -std=gnu++17',
            SDL_CONFIG=str(sdk/'usr/bin/sdl-config'),
            CPPFLAGS='-I'+str(sdk/'usr/include/SDL')+' -D_GNU_SOURCE=1 -D_REENTRANT',
            LDFLAGS='-L'+str(library.parent)+' -Wl,-rpath,'+str(library.parent)+' -Wl,--disable-new-dtags')
        report.update(build_environment=environment,build_environment_is_complete=True)

        def run(command,name,timeout=600):
            result=subprocess.run(command,cwd=root,env=environment,stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,timeout=timeout)
            (out/(name+'.log')).write_bytes(result.stdout)
            report[name+'_exit']=result.returncode
            result.check_returncode()
            return result.stdout

        report['distribution_patches']=[]
        for index,line in enumerate((root/'debian/patches/series').read_text().splitlines()):
            parts=shlex.split(line,comments=True)
            if not parts:
                continue
            relative=Path(parts[0])
            if relative.is_absolute() or '..' in relative.parts or len(parts)>2 or len(parts)==2 and parts[1] not in ('-p0','-p1'):
                raise ValueError('Unsupported distribution patch series entry')
            path=root/'debian/patches'/relative
            run(['patch','--batch','--forward',parts[1] if len(parts)==2 else '-p1','-i',str(path)],
                'distribution-'+str(index),30)
            report['distribution_patches'].append(dict(name=parts[0],sha256=sha(path)))
        # Keep release-generated Autotools bytes; only refresh dependency timestamps.
        generated=[root/'aclocal.m4',root/'configure',root/'config.h.in',*root.rglob('Makefile.in')]
        report['release_generated_hashes']={str(path.relative_to(root)):sha(path) for path in generated}
        for path in generated:
            os.utime(path,None)
        hook=ROOT/'tools/original_work_probe/normal_core_hook.patch'
        run(['patch','--batch','--forward','-p1','-i',str(hook)],'normal-hook',30)
        for name,pin in pins.items():
            if name not in ('src/dosbox','config.h') and sha(root/name)!=pin:
                raise ValueError('Pinned configured-source input differs: '+name)
        report.update(normal_core_hook_sha256=sha(hook),normal_core_instrumentation_applied=True,
            normal_core_sha256=sha(root/'src/cpu/core_normal.cpp'),
            cpu_source_unchanged_since_observer_hook=True,cpu_source_unchanged=True)
        shutil.copyfile(probe,root/'src/cpu/lezac_work_probe.h')
        shutil.copyfile(COMMON/'lezac_clock_observation.h',root/'src/cpu/lezac_clock_observation.h')
        for name in ('dos_time_hook.patch','clock_hook.patch'):
            run(['patch','--batch','--forward','-p1','-i',str(COMMON/name)],name,30)
        fragments={'src/hardware/pic.cpp':'pic_tickers_observation.inc',
            'src/hardware/vga_draw.cpp':'vga_clock_observation.inc',
            'src/gui/render.cpp':'render_clock_observation.inc',
            'src/gui/sdlmain.cpp':'gfx_clock_observation.inc',
            'src/hardware/keyboard.cpp':'keyboard_clock_observation.inc',
            'src/hardware/mixer.cpp':'mixer_clock_observation.inc'}
        patch=[]
        for name,fragment in fragments.items():
            shutil.copyfile(COMMON/fragment,root/'src/cpu'/fragment)
            before=(root/name).read_text()
            after=before+'\n#include "../cpu/'+fragment+'"\n'
            patch.extend(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),
                fromfile='a/'+name,tofile='b/'+name))
        (out/'device-getters.patch').write_text(''.join(patch))
        run(['patch','--batch','--forward','-p1','-i',str(out/'device-getters.patch')],'device-getters',30)
        report.update(probe_sha256=sha(probe),patch_sha256=sha(COMMON/'dos_time_hook.patch'),
            clock_patch_sha256=sha(COMMON/'clock_hook.patch'),clock_api_sha256=sha(COMMON/'lezac_clock_observation.h'),
            device_patch_sha256=sha(out/'device-getters.patch'),callback_identity='direct original function pointer equality',
            device_fragment_hashes={name:sha(COMMON/name) for name in fragments.values()})
        run(['./configure','--with-sdl-prefix='+str(sdk/'usr'),'--disable-debug','--disable-opengl'],'configure')
        report['source_hashes']={name:pin for name,pin in pins.items() if name not in ('src/dosbox','config.h')}
        report['source_hashes']['config.h']=sha(root/'config.h')
        compiled_sources={str(path.relative_to(root)):sha(path) for parent in ('src','include')
            for path in (root/parent).rglob('*') if path.is_file() and path.suffix in ('.cpp','.h','.inc')}
        run(['make','-j2'],'build')
        binary=root/'src/dosbox'
        report.update(build_exit=0,host_sha256=sha(binary),
            patched_device_sources={name:sha(root/name) for name in fragments},
            patched_dos_sha256=sha(root/'src/dos/dos.cpp'),
            patched_pic_sha256=sha(root/'src/hardware/pic.cpp'),
            patched_timer_sha256=sha(root/'src/hardware/timer.cpp'))
        linked=run(['ldd',str(binary)],'linked-libraries',30).decode('utf-8')
        if not any('libSDL-1.2.so.0 =>' in line and str(alias) in line for line in linked.splitlines()):
            raise ValueError('Observation host does not select the intended SDL image')
        if sha(root/'src/cpu/core_normal.cpp')!=pins['src/cpu/core_normal.cpp']:
            raise ValueError('CPU source changed after the observation hook')
        for name,digest in {**compiled_sources,**report['release_generated_hashes']}.items():
            if sha(root/name)!=digest:
                raise ValueError('Source bytes changed during the build: '+name)
        report['compiled_source_hashes']=compiled_sources
        report['compiled_sources_unchanged_during_build']=True
        report['release_generated_bytes_unchanged_during_build']=True
        report['status']='built'
        print(json.dumps(dict(status='built',host_sha256=report['host_sha256'],expected_sdl_image=str(library))),flush=True)
    except BaseException as error:
        report.update(status='failed',error=repr(error))
        raise
    finally:
        (out/'build.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('archive','descriptor','distribution','sdl-dev','sdl-runtime','out','probe'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    build(args.archive,args.descriptor,args.distribution,args.sdl_dev,args.sdl_runtime,args.out,args.probe)
