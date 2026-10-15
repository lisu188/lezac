"""Capture original raw-cell debris seeds without changing the pinned producer."""
import argparse
import ast
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

import capture_original_outside_map_seeding as historical
from capture_original_collapse_contact_continuity import retain_failure

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'tools/capture_original_outside_map_seeding.py'
PARENT_SHA = 'c3fc40a4aaa783c57fa7daad8114d232c6267c44ae1ab99be5028c9651ddab46'
SCENES = [
    dict(name='debris-consume-wrap-debris', first=40, target=32748, target_word=0x4101,
         debris=True, consume=True, raw_cell=65516, raw_glyph=39),
    dict(name='debris-move-wrap-debris', first=40, target=32748, target_word=0x4101,
         debris=True, consume=False, raw_cell=65516, raw_glyph=56),
]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def adapted_capture():
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError('wrapped debris parent producer fingerprint differs')
    tree = ast.parse(raw)
    original, = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'capture']
    function = copy.deepcopy(original)
    scenes, = [node for node in ast.walk(function) if isinstance(node, ast.Assign) and
               any(isinstance(target, ast.Name) and target.id == 'scenes' for target in node.targets)]
    scenes.value = ast.parse(repr(SCENES), mode='eval').body
    cases, = [node for node in ast.walk(function) if isinstance(node, ast.For) and
              isinstance(node.target, ast.Tuple) and [item.id for item in node.target.elts] == ['case_index', 'scene']]
    initializer, = [node for node in cases.body if isinstance(node, ast.For) and
                    isinstance(node.target, ast.Name) and node.target.id == 'executor']
    raw_seed = ast.parse("executor.cpu.mem_write(0x40000 + scene['raw_cell'], bytes([scene['raw_glyph']]))").body[0]
    initializer.body.append(raw_seed)
    initial_index, = [index for index, node in enumerate(cases.body) if isinstance(node, ast.Assign) and
                      any(isinstance(target, ast.Name) and target.id == 'initial' for target in node.targets)]
    observe_input = ast.parse("scope['capture_input'] = initial").body[0]
    cases.body.insert(initial_index + 1, observe_input)
    code, = [node for node in ast.walk(function) if isinstance(node, ast.FunctionDef) and node.name == 'code']
    observe_record = ast.parse("""if address == 0x1379b:
    pointer = cpu.reg_read(regs.UC_X86_REG_ES) * 16 + cpu.reg_read(regs.UC_X86_REG_DI)
    scope['raw_seed_records'].append(dict(case=case_index, address=pointer,
        cell=int.from_bytes(bytes(cpu.mem_read(pointer, 2)), 'little')))
""").body[0]
    code.body.append(observe_record)

    restored = copy.deepcopy(function)
    restored_scenes, = [node for node in ast.walk(restored) if isinstance(node, ast.Assign) and
                        any(isinstance(target, ast.Name) and target.id == 'scenes' for target in node.targets)]
    original_scenes, = [node for node in ast.walk(original) if isinstance(node, ast.Assign) and
                       any(isinstance(target, ast.Name) and target.id == 'scenes' for target in node.targets)]
    restored_scenes.value = copy.deepcopy(original_scenes.value)
    restored_cases, = [node for node in ast.walk(restored) if isinstance(node, ast.For) and
                       isinstance(node.target, ast.Tuple) and [item.id for item in node.target.elts] == ['case_index', 'scene']]
    restored_initializer, = [node for node in restored_cases.body if isinstance(node, ast.For) and
                             isinstance(node.target, ast.Name) and node.target.id == 'executor']
    restored_initializer.body.pop()
    restored_cases.body.pop(initial_index + 1)
    restored_code, = [node for node in ast.walk(restored) if isinstance(node, ast.FunctionDef) and node.name == 'code']
    restored_code.body.pop()
    if ast.dump(restored, include_attributes=False) != ast.dump(original, include_attributes=False):
        raise ValueError('wrapped debris adapter changed the original execution algorithm')
    namespace = dict(vars(historical), __file__=str(Path(__file__).resolve()))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                 str(Path(__file__).resolve()), 'exec'), namespace)
    return namespace['capture']


def capture(out):
    if out.exists() or sys.flags.optimize or os.environ.get('SDL_AUDIODRIVER') != 'dummy':
        raise ValueError('original capture requires a new output directory and silent, checked execution')
    scope = historical.base.functions.__globals__
    scope['raw_seed_records'] = []
    report = dict(passed=False, schema='lezac.wrapped-debris-seeding.v1', original_fidelity_claim=False,
                  whole_game_complete=False, parent_producer_sha256=PARENT_SHA)
    try:
        import unicorn
        if unicorn.__version__ != '2.1.4':
            raise ValueError('original capture requires the pinned Unicorn 2.1.4')
        adapted_capture()(out)
        report = json.loads((out / 'outside_map_seeding_original.json').read_bytes())
        events = json.loads(gzip.decompress((out / 'map-events.json.gz').read_bytes()))
        glyph_reads = []
        for index, scene in enumerate(SCENES):
            reads = [event for event in events if event[0] == index and event[1] == 0x137b8 and
                     event[2] == 0x40000 + scene['raw_cell'] and event[3:5] == [1, 0]]
            if not reads or any(event[5] != scene['raw_glyph'] for event in reads):
                raise ValueError('original seeder did not read the distinct raw-cell glyph')
            if not any(item['case'] == index and item['cell'] == scene['raw_cell'] for item in scope['raw_seed_records']):
                raise ValueError('original seeder did not store the raw cell in its debris record')
            glyph_reads.extend(reads)
        report.update(schema='lezac.wrapped-debris-seeding.v1', parent_producer_sha256=PARENT_SHA,
            unicorn_version=unicorn.__version__, raw_seed_records=scope['raw_seed_records'],
            raw_glyph_reads=glyph_reads, input_bytes=157806, state_bytes=157796,
            original_fidelity_claim=False, whole_game_complete=False)
        (out / 'outside_map_seeding_original.json').write_text(json.dumps(report, indent=2) + '\n',
                                                             encoding='utf-8', newline='\n')
    except BaseException as error:
        report.update(passed=False, error=str(error), error_type=type(error).__name__)
        out.mkdir(parents=True, exist_ok=True)
        executors = [(name, scope[name]) for name in ('observed', 'neutral') if name in scope]
        if executors:
            retain_failure(out, executors, scope.get('tracked', []), scope['output'], report, scope.get('capture_input'))
        (out / 'wrapped-debris-failure.json').write_text(json.dumps(report, indent=2) + '\n')
        raise
    finally:
        if out.exists() and sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) >= 8388608:
            raise ValueError('wrapped debris capture exceeds the artifact reserve')
    print('wrapped_debris_original_capture=ok cases=2 raw_cell=65516 word_alias=32748 glyphs=39,56 masks=0', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--unicorn-path', type=Path)
    args = parser.parse_args()
    if args.self_check:
        if args.out or args.unicorn_path:
            parser.error('--self-check does not execute the emulator')
        adapted_capture()
        print('wrapped_debris_capture_adapter=ok cases=2 pinned_parent=1 input_and_observer_only=1 emulator_executed=0')
    else:
        if not args.out or not args.unicorn_path:
            parser.error('--out and --unicorn-path are required')
        sys.path.insert(0, str(args.unicorn_path.resolve()))
        capture(args.out.resolve())
