"""Authenticate controller-function and natural port-clock evidence before single-file export."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile

import check_keyboard_irq_fixture as irq
from keyboard_device_probe.port_steps import projection

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/keyboard_device'
MANIFEST_SHA = 'b41fbd123223423c7211ad6453aac635b2c6ab8f7e6566fd53b6a89635754bb5'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value: raise ValueError(message)


def read_fixture():
    raw = (FIXTURE / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Keyboard device manifest differs')
    manifest = json.loads(raw)
    require(manifest['schema'] == 'lezac-keyboard-device-fixture-v1' and manifest['cases'] == 31296 and
            manifest['port_cases'] == 20 and manifest['early_core_slices'] == 14, 'Keyboard device domain differs')
    for name, digest in manifest['sources'].items():
        require(sha((ROOT / name).read_bytes()) == digest, 'Keyboard device producer differs: ' + name)
    require({item['name'] for item in manifest['files']} == {'data.bin.gz', 'origin.json'}, 'Keyboard device files differ')
    files = {}
    for item in manifest['files']:
        data = (FIXTURE / item['name']).read_bytes()
        require(len(data) == item['bytes'] and sha(data) == item['sha256'], 'Keyboard device file differs: ' + item['name'])
        files[item['name']] = data
    with gzip.open(FIXTURE / 'data.bin.gz', 'rb') as stream:
        decoded = stream.read(8917541)
    require(len(decoded) == manifest['bytes'] == 8917540 and sha(decoded) == manifest['sha256'], 'Keyboard device projection differs')
    origin = json.loads(files['origin.json'])
    require(origin['schema'] == 'lezac-keyboard-device-function-oracle-v1' and origin['cases'] == 31296 and
            origin['oracle_bytes'] == 8910328 and sha(decoded[:8910328]) == origin['oracle_sha256'] and
            origin['original_functions_changed'] is origin['original_host_execution'] is origin['whole_game_claim'] is False and
            origin['machine'] == 'VGA', 'Keyboard device original-function provenance differs')
    require(origin['producer_sha256'] == manifest['sources']['tools/keyboard_device_probe/build_oracle.py'] and
            origin['driver_sha256'] == manifest['sources']['tools/keyboard_device_probe/oracle_driver.cpp'],
            'Keyboard device oracle producer binding differs')
    require(manifest['original_irq_manifest_sha256'] == irq.MANIFEST_SHA, 'Keyboard device natural-source binding differs')
    irq.read_fixture()
    traces = ROOT / 'tests/fixtures/keyboard_irq'
    require(decoded[8910328:] == projection([traces / 'natural-r5.csv.gz', traces / 'natural-r6.csv.gz']),
            'Keyboard device natural port-clock projection differs')
    require(all(manifest[name] is False for name in
        ('original_host_function_oracle_claim', 'full_clock_claim', 'app_cadence_claim', 'whole_game_claim')), 'Keyboard device scope differs')
    print('keyboard_device_fixture=ok function_cases=31296 natural_port_cases=20 early_core_slices=14 app_cadence_claim=0')
    return decoded


def export(path=None):
    raw = read_fixture()
    if path is None: return
    require(not path.is_symlink() and (not path.exists() or path.is_file()), 'Keyboard device output must be a regular file')
    protected = set()
    for fixture in (FIXTURE, irq.FIXTURE):
        manifest = json.loads((fixture / 'manifest.json').read_bytes())
        protected.add((fixture / 'manifest.json').resolve())
        protected.update((fixture / item['name']).resolve() for item in manifest['files'])
        protected.update((ROOT / name).resolve() for name in manifest['sources'])
        protected.update((ROOT / name).resolve() for name in manifest.get('assets', {}))
    require(path.resolve() not in protected, 'Keyboard device output aliases authenticated input')
    if path.exists() and path.read_bytes() == raw: return
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.stage', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    export(parser.parse_args().out)
