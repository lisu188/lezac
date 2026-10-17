"""Extract unchanged original palette functions and execute them against native SDL RGB32."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--sdk',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();source=args.source.resolve(strict=True);sdk=args.sdk.resolve(strict=True);out=args.out.resolve()
assert out.is_relative_to(Path('/dev/shm')) and not out.exists() and shutil.disk_usage('/dev/shm').free>256*1024**2
sha=lambda raw:hashlib.sha256(raw).hexdigest()
pins={'src/gui/render.cpp':'3bce9f5aded634ec34497a0ee8875e89e0b90cdb7de6e72bbbb81482c09dc7fc',
    'src/gui/sdlmain.cpp':'59e78cf3f7c3423e17a27adde5993c8c4156bdef0e2a03927e88fa6b7bf85c6b'}
assert all(sha((source/name).read_bytes())==digest for name,digest in pins.items())
render=(source/'src/gui/render.cpp').read_text();gfx=(source/'src/gui/sdlmain.cpp').read_text()
palette=render[render.index('static void Check_Palette(void) {'):render.index('\nvoid RENDER_SetPal(')]
mapping=gfx[gfx.index('Bitu GFX_GetRGB('):gfx.index('\nvoid GFX_Stop()')]
driver=Path(__file__).with_name('palette_oracle_driver.cpp').read_text()
assert driver.count('// ORIGINAL_FUNCTIONS')==1
out.mkdir();generated=driver.replace('// ORIGINAL_FUNCTIONS',palette+'\n'+mapping)
(out/'oracle.cpp').write_text(generated)
command=['g++','-std=c++17','-O2','-I'+str(sdk/'usr/include/SDL'),str(out/'oracle.cpp'),
    '-L'+str(sdk/'usr/lib/x86_64-linux-gnu'),'-lSDL','-o',str(out/'oracle')]
result=subprocess.run(command,capture_output=True,env=dict(os.environ,TMPDIR='/dev/shm'),timeout=90)
(out/'build.log').write_bytes(result.stdout+result.stderr);result.check_returncode()
with (out/'oracle.bin').open('xb') as stream:
    result=subprocess.run([str(out/'oracle')],stdout=stream,stderr=subprocess.PIPE,
        env=dict(os.environ,SDL_AUDIODRIVER='dummy',SDL_VIDEODRIVER='dummy'),timeout=30)
(out/'run.log').write_bytes(result.stderr);result.check_returncode()
report=dict(status='passed',cases=96,original_source_sha256=pins,producer_sha256=sha(Path(__file__).read_bytes()),
    driver_sha256=sha(Path(__file__).with_name('palette_oracle_driver.cpp').read_bytes()),
    palette_function_sha256=sha(palette.encode()),mapping_function_sha256=sha(mapping.encode()),
    generated_source_sha256=sha(generated.encode()),binary_sha256=sha((out/'oracle').read_bytes()),
    oracle_sha256=sha((out/'oracle.bin').read_bytes()),sdl_library_sha256=sha((sdk/'usr/lib/x86_64-linux-gnu/libSDL.so').resolve().read_bytes()),
    native_sdl_mapping=True,original_function_bodies_changed=False,original_host_execution=False,
    scope='controlled RGB32 Check_Palette and GFX_GetRGB only; other branches not executed')
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
