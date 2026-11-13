#!/usr/bin/env python3
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path('/mnt/c/Users/andrz/git/LEZAC')
WORK = Path('/dev/shm/lezac-natural-level2-20261005')
sys.path.insert(0, str(ROOT / 'tools'))
import level1_fidelity as fidelity
import level1_original as original

BASE = ROOT / 'docs/recovery/evidence/pickup_landing_2026-10-01/base-observer.py'
BASE_SHA = 'acb311ed85fb594afc1d92d6774036a742388339b920bcc0f81206cabfb30dec'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('record', 'capture', 'compare', 'inspect'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--native', type=Path)
    parser.add_argument('--cpp', type=Path)
    args = parser.parse_args()
    config = fidelity.strict_json(args.config.read_text())
    fidelity.require(set(config) == {'frames', 'events'} and
                     fidelity.integer(config['frames'], 1, 3000), 'invalid route configuration')
    events = {}
    for key, items in config['events'].items():
        fidelity.require(key.isdigit() and str(int(key)) == key and int(key) < config['frames'],
                         'invalid route event index')
        fidelity.require(isinstance(items, list) and items, 'empty event list')
        for item in items:
            fidelity.require(isinstance(item, list) and len(item) == 2 and
                             item[0] in ('down', 'up') and item[1] in original.BANK,
                             'non-gameplay event')
        events[int(key)] = [tuple(item) for item in items]
    fidelity.require(fidelity.sha256(BASE) == BASE_SHA, 'retained base observer changed')
    spec = importlib.util.spec_from_file_location('level2_exploration_base', BASE)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    base.ROOT, base.FRAMES, base.EVENTS = ROOT, config['frames'], events
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    out = args.out.resolve()
    fidelity.require(out.parent == Path('/dev/shm') and out.name.startswith('lezac-natural-level2-'),
                     'owned RAM output required')
    if args.command == 'inspect':
        manifest = fidelity.load_manifest(out)
        samples = []
        for row in fidelity.trace_rows(out, manifest):
            if row['kind'] != 'checkpoint' or row['phase'] != 'post_update' or row['tick'] < base.FIRST_TICK:
                continue
            state = row['state']
            index = row['tick'] - base.FIRST_TICK
            player = state['players'][0]
            sample = {'sample': index, 'tick': row['tick'], 'level': state['level'],
                      'xy': [player['x'], player['y']], 'velocity': [player['vx8'], player['vy8']],
                      'health': player['health'], 'inventory': player['inventory'],
                      'progress': state['progress'], 'flow': state['flow'],
                      'rng': state['random_seed'], 'frame': 'frame_' + f"{row['tick']:06d}" + '.ppm',
                      'objective_positions': [[(i % state['dimensions'][0]) * 8,
                                               (i // state['dimensions'][0]) * 8]
                                              for i, tile in enumerate(bytes.fromhex(state['tiles_hex']))
                                              if tile == 110],
                      'monsters': len(state['monsters']), 'collapse': len(state['collapse'])}
            samples.append(sample)
            if index % 20 == 0 or index in events or index + 1 == config['frames']:
                print(json.dumps(sample), flush=True)
        (out / 'exploration-states.json').write_text(json.dumps(samples, indent=2) + '\n')
        return
    fidelity.require(not out.exists(), 'output already exists; preserve previous evidence')
    planned = (743 + config['frames']) * 350000 + 32 * 1024 ** 2 if args.command == 'record' else 64 * 1024 ** 2
    base.reserve(planned)
    parent = base.ExtensionSession

    class RetainedSession(parent):
        ds_stream = None
        ds_sequence = 0

        def dynamic_state(self):
            state = super().dynamic_state()
            if self.ds_stream is not None:
                data = self.read(self.ds, 65536)
                self.ds_stream.write(data)
                self.ds_sequence += 1
            return state

        def extend(self, emit):
            with gzip.open(out / 'extension-ds.bin.gz', 'wb') as stream:
                self.ds_stream = stream
                try:
                    super().extend(emit)
                finally:
                    self.ds_stream = None
            (out / 'extension-ds.json').write_text(json.dumps({
                'encoding': 'concatenated-65536-byte-original-data-segments',
                'boundaries': 'initial post, then pre/rendered/post for each extension frame',
                'snapshots': self.ds_sequence, 'frames_requested': config['frames'],
                'ds_stream_sha256': fidelity.sha256(out / 'extension-ds.bin.gz'),
                'scope': 'Main routine remains stopped; interrupt-owned clock and sound bytes may advance.',
            }, indent=2) + '\n')

        def close(self):
            if self.child is not None and self.child.poll() is None and self.mem is not None and self.ds:
                (out / 'final-ds.bin').write_bytes(self.read(self.ds, 65536))
                (out / 'final-handshake.bin').write_bytes(self.read(self.resident + original.SCRATCH, 20))
            super().close()

    base.ExtensionSession = RetainedSession
    try:
        if args.command == 'record':
            fidelity.require(args.exe is not None, 'executable required')
            base.record(args.exe, out)
        elif args.command == 'capture':
            base.capture(out)
        else:
            fidelity.require(args.native is not None and args.cpp is not None, 'both captures required')
            base.compare(args.native.resolve(), args.cpp.resolve(), out)
    finally:
        if out.is_dir():
            shutil.copyfile(Path(__file__), out / 'route-explorer.py')
            shutil.copyfile(BASE, out / 'base-observer.py')
            shutil.copyfile(args.config, out / 'route-config.json')
            (out / 'route-provenance.json').write_text(json.dumps({
                'schema': 'lezac-natural-level2-exploration-v1',
                'explorer_sha256': fidelity.sha256(Path(__file__)),
                'base_observer_sha256': BASE_SHA, 'config_sha256': fidelity.sha256(args.config),
                'runtime_overrides': ['ROOT', 'FRAMES', 'EVENTS', 'full-DS read snapshots', 'close-time raw snapshot'],
                'state_injections': False, 'seed_scope': 'unchanged single initial Level 1 prefix seed',
                'audio': 'dummy', 'whole_game_parity': False,
            }, indent=2) + '\n')


if __name__ == '__main__':
    main()
