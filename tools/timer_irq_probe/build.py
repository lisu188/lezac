"""Build a source-pinned, read-only normal-core timer observer in a new RAM directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
source, out = args.source.resolve(strict=True), args.out.resolve()
assert source.is_relative_to(Path('/dev/shm')) and out.is_relative_to(Path('/dev/shm'))
assert not out.exists() and shutil.disk_usage('/dev/shm').free > 2 * 1024**3
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
pins = {
    'src/dosbox': '4d8eaba9db5e3f733b49c35f191eff98f1f5730035f7374c5c703693a080c8ac',
    'src/dos/dos.cpp': 'c563c5c0df429350ccba90019252abc0d6bcca2264fa36a3971b512ecd6ac002',
    'src/cpu/core_normal.cpp': '4aa44efa8c6d8788f23d6bcc29d24beb4a4123d3e442b51f03a03bdbdf8c6516',
    'src/cpu/callback.cpp': '945f1b696b2f031f6f5e4ffc00aecd77103eaf5be4a9cf7051814517ce6e74bf',
    'src/cpu/cpu.cpp': '0e897027875de7eea33a35b9eeefcd5a7cd15facb4a409172e3e712766b08098',
    'include/dos_inc.h': 'c044eedc836ddcd1f18c0f16ad8f62861078fe065cf858094513ffdea9589e3a',
    'config.h': '01aca5c63f5c70af786ea29d8a769b9a475edfcb9a36e2d762af00bbc204f786',
    'src/ints/bios.cpp': 'b07734c610138cefb7383782aafdbf49d19dcc95c8b0113555261fcfdd71baa5',
    'src/hardware/iohandler.cpp': 'd7ef9acf52269924d8331b1b46140e5b5f621cc386a7bf733c95b6985d313393',
}
assert all(sha(source / name) == pin for name, pin in pins.items())
out.mkdir()
root = out / 'dosbox-0.74-3'
shutil.copytree(source, root)
header = Path(__file__).with_name('lezac_work_probe.h')
shutil.copy2(header, root / 'src/cpu/lezac_work_probe.h')
report = dict(base_host_sha256=pins['src/dosbox'], source_hashes=pins, probe_sha256=sha(header),
    copied_build_products=True, host_instrumented=True, guest_instruction_patches=0,
    source_filesystem='tmpfs', output_filesystem='tmpfs')
try:
    built = subprocess.run(['make','-j2'], cwd=root, capture_output=True,
        env=dict(os.environ,TMPDIR='/dev/shm'), timeout=600)
    (out / 'build.log').write_bytes(built.stdout + built.stderr)
    report.update(build_exit=built.returncode,host_sha256=sha(root / 'src/dosbox'),
        cpu_source_unchanged=sha(root / 'src/cpu/core_normal.cpp') == pins['src/cpu/core_normal.cpp'])
    built.check_returncode()
    assert report['cpu_source_unchanged']
    report['status']='built'
except BaseException as error:
    report.update(status='failed',error=repr(error))
    raise
finally:
    (out / 'build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
