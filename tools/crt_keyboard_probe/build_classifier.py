import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess

parser=argparse.ArgumentParser(description='Execute the exact pinned original BIOS key classifier')
parser.add_argument('--source',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();SOURCE=args.source.resolve(strict=True);OUT=args.out.resolve()
assert OUT.is_relative_to(Path('/dev/shm')) and not OUT.exists();OUT.mkdir()
raw=SOURCE.read_bytes();sha=lambda raw:hashlib.sha256(raw).hexdigest()
assert sha(raw)=='880ef5796c968db80b7e0d23f2d5f68e86fd3d065b40f141bd77642ad2d89416'
text=raw.decode();start=text.index('static bool IsEnhancedKey(');end=text.index('\nstatic Bitu INT16_Handler',start)
original=text[start:end]
driver='#include <cstdint>\n#include <cstdio>\nusing Bit16u=uint16_t;\n'+original+'''
int main() {
    for(unsigned value=0;value<65536;++value) {
        Bit16u key=static_cast<Bit16u>(value);
        const bool enhanced=IsEnhancedKey(key);
        std::putchar(enhanced);std::putchar(key&255);std::putchar(key>>8);
    }
}
'''
(OUT/'original-classifier.cpp').write_text(driver)
build=subprocess.run(['g++','-std=c++23','-O2',str(OUT/'original-classifier.cpp'),'-o',str(OUT/'original-classifier')],
    capture_output=True,env=dict(os.environ,TMPDIR='/dev/shm'),timeout=180);build.check_returncode()
data=subprocess.check_output([str(OUT/'original-classifier')]);assert len(data)==65536*3
(OUT/'classification.bin').write_bytes(data);(OUT/'classification.bin.gz').write_bytes(gzip.compress(data,mtime=0))
record=dict(source_sha256=sha(raw),original_function_sha256=sha(original.encode()),driver_sha256=sha(driver.encode()),
    inputs=65536,projection_sha256=sha(data),bytes=len(data),original_function_unchanged=True,
    whole_bios_handler_execution_claim=False)
(OUT/'manifest.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
