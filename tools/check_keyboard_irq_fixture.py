"""Authenticate natural IRQ1 traces and the independent BIOS function oracle before export."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile

from original_capture_contract import read_canonical_assets
from keyboard_irq_probe.project import projection, validate_opcodes

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/keyboard_irq'
MANIFEST_SHA = '1581397389b978a431865bc5c74aa1ffdb364d2d584fd0c4c1622d75b26ed6f6'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read_fixture(root=FIXTURE, source_root=ROOT):
    raw = (root / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen IRQ1 manifest differs')
    manifest = json.loads(raw)
    require(manifest['schema'] == 'lezac-keyboard-irq-fixture-v1', 'Frozen IRQ1 schema differs')
    for name, digest in manifest['sources'].items():
        require(sha((source_root / name).read_bytes()) == digest, 'Frozen IRQ1 source differs: ' + name)
    assets = read_canonical_assets(source_root)
    require({name: dict(bytes=len(data), sha256=sha(data)) for name, data in assets.items()} == manifest['assets'],
            'IRQ1 canonical assets differ')
    domain = {'natural-r5.csv.gz', 'natural-r5-recipe.json', 'natural-r6.csv.gz', 'natural-r6-recipe.json',
              'bios.bin.gz', 'bios-origin.json'}
    require({item['name'] for item in manifest['files']} == domain, 'IRQ1 fixture file domain differs')
    files = {}
    for item in manifest['files']:
        data = (root / item['name']).read_bytes()
        require(len(data) == item['bytes'] and sha(data) == item['sha256'], 'Frozen IRQ1 file differs: ' + item['name'])
        files[item['name']] = data
    fragments, cases, states = [], 0, 0
    source = manifest['sources']
    common = 'tools/frame_foreground_probe/'
    for label in ('r5', 'r6'):
        recipe = json.loads(files['natural-' + label + '-recipe.json'])
        host = recipe['host_build']
        require(recipe['schema'] == 'lezac-original-keyboard-irq-v1' and recipe['status'] == 'observed' and
                recipe['passed'] is True and recipe['validated_target_completed'] is True and recipe['child_exit_code'] == 0 and
                recipe['canonical_assets_unchanged'] is True and recipe['assets'] == manifest['assets'], 'IRQ1 capture did not complete')
        require(recipe['executable_sha256'] == manifest['original_executable_sha256'] and
                recipe['dosbox_sha256'] == host['host_sha256'] == manifest['host_sha256'] ==
                'f74c3a0c885d687cc6205dcfc004f1edc49811721eafde30e32473ea63fac108', 'IRQ1 executable/host identity differs')
        require(recipe['keyboard_layout'] == 'none' and recipe['bios_observation_bytes'] == 152 and
                recipe['audio'] == recipe['dosbox_environment']['SDL_AUDIODRIVER'] == 'dummy' and
                recipe['environment_is_complete'] is True and recipe['original_executable_changed'] is False and
                recipe['arithmetic_flags_claim'] is recipe['whole_game_claim'] is False, 'IRQ1 scope/profile differs')
        require(all(recipe[name] == 0 for name in ('process_memory_writes', 'process_pauses', 'guest_instruction_patches',
                'calls_stubbed', 'host_probe_guest_register_writes', 'host_probe_guest_memory_writes')) and
                recipe['gameplay_state_seeded'] is recipe['input_bytes_seeded'] is False, 'IRQ1 original mutation profile differs')
        require(host['cpu_source_unchanged'] is True and host['keyboard_append_only'] is True and
                host['build_exit'] == 0 and host['guest_instruction_patches'] == 0, 'IRQ1 observer changed original execution')
        expected_recipe_sources = {'tools/keyboard_irq_probe/' + name for name in
            ('capture.py', 'trace.py', 'rebuild.py', 'contract.py', 'lezac_work_probe.h', 'keyboard_irq_api.h', 'keyboard_irq_observation.inc')}
        expected_recipe_sources |= {'tools/original_capture_contract.py', 'tools/seed_original_level.py'}
        require(set(recipe['sources']) == expected_recipe_sources and all(source[name] == digest for name, digest in recipe['sources'].items()),
                'IRQ1 capture source domain/binding differs')
        for field, name in [('probe_sha256', 'tools/keyboard_irq_probe/lezac_work_probe.h'),
            ('rebuild_producer_sha256', 'tools/keyboard_irq_probe/rebuild.py'),
            ('repair_producer_sha256', 'tools/frame_foreground_live_probe/rebuild.py'),
            ('patch_sha256', common + 'dos_time_hook.patch'), ('clock_patch_sha256', common + 'clock_hook.patch'),
            ('clock_api_sha256', common + 'lezac_clock_observation.h')]:
            require(host[field] == source[name], 'IRQ1 host producer/observer binding differs: ' + field)
        require(host['keyboard_irq_sources'] == {name: source['tools/keyboard_irq_probe/' + name]
            for name in ('keyboard_irq_api.h', 'keyboard_irq_observation.inc')}, 'IRQ1 hardware getter binding differs')
        expected_fragments = {'pic_tickers_observation.inc', 'vga_clock_observation.inc', 'render_clock_observation.inc',
                              'gfx_clock_observation.inc', 'keyboard_clock_observation.inc', 'mixer_clock_observation.inc'}
        require(set(host['device_fragment_hashes']) == expected_fragments and
                all(source[common + name] == digest for name, digest in host['device_fragment_hashes'].items()), 'IRQ1 shared getter binding differs')
        trace = root / ('natural-' + label + '.csv.gz')
        require(sha(files[trace.name]) == recipe['trace_sha256'] and len(files[trace.name]) == recipe['trace_bytes'],
                'IRQ1 recipe/trace binding differs')
        validate_opcodes(trace, assets['LEZAC.EXE'], recipe)
        cpu, details = projection(trace)
        require(details['irq_windows'] == recipe['irq_windows'] and details['states'] == recipe['states'] and
                details['trace_uncompressed_sha256'] == recipe['trace_uncompressed_sha256'], 'IRQ1 observation domain differs')
        fragments.append(cpu[12:]); cases += len(details['irq_windows']); states += details['states']
    cpu = b'LZKIRQ01' + struct.pack('<I', cases) + b''.join(fragments)
    require(cases == manifest['cases'] == 82 and states == manifest['states'] == 6776 and
            len(cpu) == manifest['cpu_bytes'] and sha(cpu) == manifest['cpu_sha256'], 'IRQ1 CPU projection differs')
    origin = json.loads(files['bios-origin.json'])
    with gzip.GzipFile(fileobj=io.BytesIO(files['bios.bin.gz'])) as stream:
        bios = stream.read(20251541)
    require(len(bios) == manifest['bios_bytes'] == origin['oracle_bytes'] == 20251540 and
            sha(bios) == manifest['bios_sha256'] == origin['oracle_sha256'] and origin['cases'] == manifest['bios_cases'] == 65536,
            'BIOS function oracle projection differs')
    require(origin['source_sha256'] == '880ef5796c968db80b7e0d23f2d5f68e86fd3d065b40f141bd77642ad2d89416' and
            origin['producer_sha256'] == source['tools/keyboard_irq_probe/build_bios_oracle.py'] and
            origin['driver_sha256'] == source['tools/keyboard_irq_probe/bios_oracle_driver.cpp'] and
            origin['original_functions_changed'] is origin['original_host_execution'] is False and origin['can_use_lock'] is True and
            origin['keyboard_layout'] == 'none' and origin['pause_callback_idle_is_explicit_handoff'] is True,
            'BIOS original function provenance/profile differs')
    require(all(manifest[name] is False for name in ('raw_memory_published', 'raw_memory_available_to_frozen_checker',
                'full_arithmetic_flags_claim', 'irq_eligibility_claim', 'app_cadence_claim', 'whole_game_claim')), 'IRQ1 evidence scope differs')
    print('keyboard_irq_fixture=ok natural_runs=2 cases=82 states=6776 bios_cases=65536 raw_ram_files_verified=0 app_cadence_claim=0')
    return cpu, bios


def remove_temporary(path):
    if path is not None:
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            print(f'IRQ1 temporary file retained at {path}: {error}', file=sys.stderr)


def export(cpu=None, bios=None):
    """Stage the pair and roll back handled I/O failures; not a crash-atomic transaction."""
    require(not cpu or not bios or cpu.resolve() != bios.resolve(), 'IRQ1 outputs alias each other')
    payloads = read_fixture()
    for path in (cpu, bios):
        if path:
            require(not path.is_symlink() and (not path.exists() or path.is_file()),
                    'IRQ1 output must be a regular file: ' + str(path))
    entries, complete = [], False
    try:
        for path, raw in zip((cpu, bios), payloads):
            if not path or (path.exists() and path.read_bytes() == raw):
                continue
            fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.stage', dir=path.parent)
            entry = dict(path=path, stage=Path(name), backup=None, backed_up=False, published=False)
            entries.append(entry)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            if path.exists():
                fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.backup', dir=path.parent)
                entry['backup'] = Path(name)
                os.close(fd)
        # All payloads and backup names are prepared before changing either destination.
        for entry in entries:
            if entry['backup'] is not None:
                os.replace(entry['path'], entry['backup'])
                entry['backed_up'] = True
        for entry in entries:
            os.replace(entry['stage'], entry['path'])
            entry['published'] = True
        complete = True
    except BaseException as error:
        failures = []
        for entry in reversed(entries):
            try:
                if entry['backed_up']:
                    os.replace(entry['backup'], entry['path'])
                    entry['backed_up'] = False
                elif entry['published']:
                    entry['path'].unlink()
            except OSError as rollback_error:
                failures.append(f"{entry['path']} (backup {entry['backup']}): {rollback_error}")
        if failures:
            raise RuntimeError('IRQ1 rollback incomplete; retain recovery files: ' + '; '.join(failures)) from error
        raise
    finally:
        for entry in entries:
            remove_temporary(entry['stage'])
            if complete or not entry['backed_up']:
                remove_temporary(entry['backup'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu', type=Path)
    parser.add_argument('--bios', type=Path)
    args = parser.parse_args()
    export(args.cpu, args.bios)
