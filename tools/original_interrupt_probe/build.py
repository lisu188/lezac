"""Copy and rebuild the pinned configured recovery host, entirely in RAM."""
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
original = args.source.resolve(strict=True)
out = args.out.resolve()
assert original.is_relative_to(Path('/dev/shm')), 'The configured source must remain in RAM'
assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
assert shutil.disk_usage('/dev/shm').free > 2 * 1024**3
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(original / 'src/dosbox') == '4d8eaba9db5e3f733b49c35f191eff98f1f5730035f7374c5c703693a080c8ac'
assert sha(original / 'src/cpu/core_normal.cpp') == '4aa44efa8c6d8788f23d6bcc29d24beb4a4123d3e442b51f03a03bdbdf8c6516'
out.mkdir()
root = out / 'dosbox-0.74-3'
shutil.copytree(original, root)
header = Path(__file__).with_name('lezac_work_probe.h')
shutil.copy2(header, root / 'src/cpu/lezac_work_probe.h')
report = dict(base_host_sha256=sha(original / 'src/dosbox'),
    base_cpu_sha256=sha(original / 'src/cpu/core_normal.cpp'),
    cpu_source_unchanged=sha(root / 'src/cpu/core_normal.cpp') == sha(original / 'src/cpu/core_normal.cpp'),
    probe_sha256=sha(header), source_filesystem='tmpfs', output_filesystem='tmpfs',
    guest_instruction_patches=0, host_instrumented=True, copied_build_products=True,
    external_sdk='/dev/shm/lezac-work-oracle-t190/sdk')
(out / 'preflight.json').write_text(json.dumps(report, indent=2) + '\n')
result = subprocess.run(['make', '-j2'], cwd=root, env=dict(os.environ, TMPDIR='/dev/shm'),
                        capture_output=True, timeout=600)
(out / 'build.log').write_bytes(result.stdout + result.stderr)
report.update(build_exit=result.returncode, host_sha256=sha(root / 'src/dosbox'))
(out / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report), flush=True)
assert result.returncode == 0
assert sha(root / 'src/cpu/lezac_work_probe.h') == sha(header)
