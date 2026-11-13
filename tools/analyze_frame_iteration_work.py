"""Partition authenticated historical original iterations, not host wall time."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

from analyze_original_frame_pacing import analyze, require
from original_capture_contract import read_canonical_assets

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/frame_pacing'
MANIFEST_SHA = '64fb11f77053cbcad274082c9d11122747573270dd09e42c80abc762d0cb91fe'


def partition(rows):
    """A next 7903 entry closes the prior iteration; a terminal delay does not."""
    intervals = []
    before = after_delay = None
    for row in rows:
        kind = row['kind']
        if kind == 'frame_before':
            if before is not None:
                require(after_delay is not None, 'Iteration has no completed pacing prefix')
                require(row['frame_counter'] == (before['frame_counter'] + 1) % 65536,
                        'Iteration counter is not consecutive')
                values = {}
                for key in ('dispatch', 'clock'):
                    prefix = after_delay[key] - before[key]
                    remainder = row[key] - after_delay[key]
                    require(prefix > 0 and remainder > 0, 'Iteration work partition is not positive')
                    values[key] = dict(pacing=prefix, after_delay=remainder, total=prefix + remainder)
                intervals.append(dict(counter=before['frame_counter'], next_counter=row['frame_counter'],
                    delay=after_delay['delay'], dispatch=values['dispatch'], work_clock=values['clock']))
            before, after_delay = row, None
        elif kind == 'delay_after':
            require(before is not None and after_delay is None, 'Duplicate or unpaired delay return')
            require(row['frame_counter'] == (before['frame_counter'] + 1) % 65536,
                    'Delay return counter differs from its frame entry')
            after_delay = row
    require(intervals, 'No complete original iterations')
    return intervals, int(before is not None), int(after_delay is not None)


def summarize(intervals, key):
    return {phase: dict(min=min(row[key][phase] for row in intervals),
                        max=max(row[key][phase] for row in intervals),
                        total=sum(row[key][phase] for row in intervals))
            for phase in ('pacing', 'after_delay', 'total')}


def analyze_run(raw, recipe):
    pacing = analyze(raw, recipe)
    rows = [{key: value if key == 'kind' else int(value) for key, value in row.items()}
            for row in csv.DictReader(io.StringIO(raw[:-4].decode('ascii')))]
    intervals, unclosed_entries, terminal_delay = partition(rows)
    clock = summarize(intervals, 'work_clock')
    return dict(run=recipe['run'], completed_iterations=len(intervals),
        completed_pacing_prefixes=pacing['completed_frames'],
        unclosed_frame_entries=unclosed_entries, terminal_delay_without_next_entry=terminal_delay,
        dispatch=summarize(intervals, 'dispatch'), work_clock=clock,
        profile_milliseconds=dict(min=clock['total']['min'] / 6000,
                                  max=clock['total']['max'] / 6000,
                                  mean=clock['total']['total'] / (6000 * len(intervals))),
        intervals=intervals)


def report():
    manifest_raw = (FIXTURE / 'manifest.json').read_bytes()
    require(hashlib.sha256(manifest_raw).hexdigest() == MANIFEST_SHA, 'Pinned pacing manifest differs')
    manifest = json.loads(manifest_raw)
    for item in manifest['files']:
        raw = (FIXTURE / item['name']).read_bytes()
        require(len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'],
                'Pinned pacing fixture differs: ' + item['name'])
    sources = {'capture_producer_sha256': 'tools/frame_pacing_probe/capture.py',
               'host_probe_sha256': 'tools/frame_pacing_probe/lezac_work_probe.h',
               'capture_contract_sha256': 'tools/original_capture_contract.py'}
    for key, name in sources.items():
        require(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == manifest[key],
                'Pinned pacing source differs: ' + name)
    read_canonical_assets(ROOT)
    runs = [analyze_run((FIXTURE / (name + '.csv')).read_bytes(),
                        json.loads((FIXTURE / (name + '-recipe.json')).read_bytes()))
            for name in ('r2', 'r3')]
    return dict(schema='lezac-historical-iteration-work-v1', status='analyzed',
        evidence='existing authenticated original captures; not a fresh observation',
        fixture_manifest_sha256=MANIFEST_SHA, cycles_per_profile_millisecond=6000,
        iteration='game 7903 to next game 7903', pacing_prefix='game 7903 to 79E8',
        after_delay='game 79E8 to next game 7903: HUD, keyboard, rendering and gameplay',
        interrupts_included=True, dispatches_are_work_clock_credits=False,
        after_delay_is_only_gameplay=False, physical_hardware_timing_claim=False,
        production_app_clock_integrated=False, whole_game_parity=False, runs=runs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists() and not args.out.is_symlink(), 'Output already exists')
    result = report()
    encoded = json.dumps(result, indent=2, allow_nan=False) + '\n'
    with args.out.open('x', encoding='utf-8', newline='\n') as output:
        output.write(encoded)
    print(json.dumps(dict(schema=result['schema'], runs=[
        {key: run[key] for key in ('run', 'completed_iterations', 'profile_milliseconds')}
        for run in result['runs']])))


if __name__ == '__main__':
    main()
