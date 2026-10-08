"""Compare production collapse actor creation with executed original records."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from check_original_collapse_update import metadata as legacy_metadata, records as legacy_records
from check_original_debris_update import compact
from source_guardrails import function_ranges, source_files

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests/gameplay/collapse_actor_creation_original.bin.gz'
META = ROOT / 'tests/gameplay/collapse_actor_creation_original.json'
META_SHA = '81bd9b9c0aabc58fda81d76c1e02a380b9e15991fd477786ba26e6ae2c84c666'
CONTRACT = {
    'debugOriginalDebrisUpdate': (
        'if (collapseUpdate) updateCollapseRecords();',
        'const size_t actorCount = le16(take(2), 0);',
        'if (actorCount > 30) throw std::runtime_error("invalid collapse actor count");',
        'actor.vx8 = static_cast<int16_t>(le16(raw, 6));',
        'actor.vy8 = static_cast<int16_t>(le16(raw, 8));',
        'actor.fracX = raw[10];', 'actor.fracY = raw[12];',
        'actor.x = le16(raw, 38);', 'actor.y = le16(raw, 40);',
        'transientActors_.push_back(actor);',
        'appendWord(result, static_cast<uint16_t>(transientActors_.size()));',
        'const auto actorBytes = collapseActorBytes(transientActors_[actorIndex], actorIndex);',
        'bytes[1] = static_cast<uint8_t>(index + 3);',
        'setWord(6, static_cast<uint16_t>(actor.vx8));',
        'setWord(8, static_cast<uint16_t>(actor.vy8));',
        'setWord(10, actor.fracX);', 'setWord(12, actor.fracY);',
        'const auto animation = actor.animation.packed();',
        'const auto& sprite = sprites_.sprites.at(actor.spriteIndex);',
        'appendWord(bytes, static_cast<uint16_t>(pixelOffset));'),
    'updateCollapseRecords': (
        'const int actorCell = last - randomRangeValue(0, static_cast<uint16_t>(last % width - first % width + 1));',
        'spawnTransientActor((actorCell % width) * 8, (actorCell / width) * 8, 0, 74, 0x0b, 8, ActorAnimation::initialize(74, 79, 2, 1));'),
    'spawnTransientActor': ('if (sharedActorCount() >= 30) return nullptr;',),
}


def ranges_for(source):
    # The shared locator excludes aggregate defaults from its signature grammar.
    located = source.replace('ActorAnimation animation = {0, 0, 0, 0, 0, 0, 1}', 'ActorAnimation animation')
    ranges = function_ranges(located, list(CONTRACT))
    if set(ranges) != set(CONTRACT): raise ValueError('missing collapse actor production helper')
    return ranges


def contract(source):
    ranges = ranges_for(source)
    for name, statements in CONTRACT.items():
        first, last = ranges[name]
        body = compact('\n'.join(source.splitlines()[first - 1:last]))
        for statement in statements:
            if body.count(compact(statement)) != 1:
                raise ValueError('collapse actor production routing differs: ' + name + ': ' + statement)


def metadata():
    raw = META.read_bytes()
    if hashlib.sha256(raw).hexdigest() != META_SHA: raise ValueError('collapse actor metadata differs')
    data = json.loads(raw)
    legacy = legacy_metadata()
    paths = {ROOT / 'LEZAC.EXE': data['original_exe_sha256'], FIXTURE: data['fixture_sha256'],
             ROOT / 'tests/fixtures/fracture_actor_original.txt': data['native_fixture_sha256'],
             ROOT / 'tests/gameplay/collapse_update_original.json': data['legacy_metadata_sha256'],
             ROOT / 'tools/capture_original_collapse_actors.py': data['generator_sha256']}
    paths.update({ROOT / 'tools' / name: digest for name, digest in data['dependency_sha256'].items()})
    for path, digest in paths.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('collapse actor provenance differs: ' + str(path.relative_to(ROOT)))
    if (data['schema'] != 'lezac.original-collapse-actors.v1' or data['cases'] != 2476
            or data['legacy_crosschecked_cases'] != legacy['cases'] or data['native_actor_creation_crosschecks'] != 1
            or data['executor'] != 'Unicorn 2.1.4' or data['original_calls_stubbed']
            or data['original_instructions_patched'] or not data['original_return_boundaries_verified']
            or not data['record_table_initializers_executed'] or not data['actors_in_creation_order']
            or not data['existing_actors_unchanged'] or not data['clean_unused_actor_slots']
            or data['stale_slot_claim'] or data['constructor_context'] != 3
            or not data['constructor_context_native_backed'] or data['initial_pool_counts'] != [0, 1, 28, 29, 30]
            or data['actor_bytes_compared'] != 38 or data['visual_bytes_compared'] != 8
            or not data['complete_live_records_maps_rng'] or data['sound_state_compared']
            or data['natural_gameplay'] or data['compiled_cpp_comparison'] or data['visual_parity_claim']
            or data['whole_game_complete'] or data['entry_counts']['actor_constructor'] != 462):
        raise ValueError('collapse actor evidence scope differs')
    return data


def records(data):
    ih, oh = hashlib.sha256(), hashlib.sha256()
    previous = iter(legacy_records(legacy_metadata()))
    actor_states = admissions = 0
    with gzip.open(FIXTURE, 'rb') as fixture:
        if fixture.read(12) != b'LZAF0001' + struct.pack('<I', data['cases']):
            raise ValueError('collapse actor fixture header differs')
        for index in range(data['cases']):
            lengths = fixture.read(8)
            if len(lengths) != 8: raise ValueError('truncated collapse actor fixture')
            a, b = struct.unpack('<II', lengths)
            if not (20 <= a < 100000 and 14 <= b < 100000): raise ValueError('collapse actor record sizes differ')
            request, result = fixture.read(a), fixture.read(b)
            if len(request) != a or len(result) != b: raise ValueError('truncated collapse actor record')
            width, height, tick, rng, fragments, collapses, destroyed, next_word = struct.unpack_from('<HHHIHHHH', request)
            after_fragments, after_collapses = struct.unpack_from('<HH', result, 4)
            cells = width * height
            input_offset = 18 + 3 * cells + 11 * fragments + 15 * collapses
            output_offset = 12 + 3 * cells + 11 * after_fragments + 15 * after_collapses
            if (not 0 < width <= 300 or not 0 < height <= 200 or cells > 16384
                    or max(fragments, after_fragments) > 1401 or max(collapses, after_collapses) > 250
                    or input_offset + 2 > a or output_offset + 2 > b):
                raise ValueError('collapse actor base layout differs')
            before = struct.unpack_from('<H', request, input_offset)[0]
            after = struct.unpack_from('<H', result, output_offset)[0]
            if not 0 <= before <= after <= 30 or a != input_offset + 2 + 46 * before or b != output_offset + 2 + 46 * after:
                raise ValueError('collapse actor pool layout differs')
            if result[output_offset + 2:output_offset + 2 + 46 * before] != request[input_offset + 2:]:
                raise ValueError('collapse actor existing pool differs')
            for actor in range(after):
                start = output_offset + 2 + actor * 46
                if result[start:start + 2] != bytes((0x0b, actor + 3)):
                    raise ValueError('collapse actor kind or visual slot differs')
            if index < 2395:
                old_request, old_result = next(previous)
                if before or request[:input_offset] != old_request or result[:output_offset] != old_result:
                    raise ValueError('collapse actor legacy crosscheck differs')
            actor_states += after
            admissions += after - before
            ih.update(request)
            oh.update(result)
            yield request, result, output_offset
        if (fixture.read(1) or ih.hexdigest() != data['input_sha256'] or oh.hexdigest() != data['output_sha256']
                or actor_states != 1822 or admissions != 414 or next(previous, None) is not None):
            raise ValueError('collapse actor fixture digests or coverage differ')


def compare(actual, expected, case_sizes):
    left, right = actual.read_bytes(), expected.read_bytes()
    if left == right: return
    first = next((i for i, pair in enumerate(zip(left, right)) if pair[0] != pair[1]), min(len(left), len(right)))
    offset = 0
    for case, size in enumerate(case_sizes):
        if first < offset + size:
            location = f'case={case} case_byte={first - offset}'
            break
        offset += size
    else: location = f'case={len(case_sizes)} case_byte={first - offset}'
    raise ValueError(f'collapse actors differ at byte {first}; {location}; actual={len(left)} expected={len(right)}')


def run_probe(exe, incoming, actual, expected, case_sizes):
    command = [str(exe.resolve()), '--debug-original-collapse-actors', str(incoming), str(actual)]
    result = None
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=90,
                                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'))
        if result.returncode or result.stderr or result.stdout.strip() != 'original_collapse_actors=ok cases=2476':
            raise RuntimeError('compiled collapse actor probe failed: ' + result.stdout + result.stderr)
        compare(actual, expected, case_sizes)
    except Exception as error:
        try:
            failures = ROOT / 'build/collapse-actor-failures'
            failures.mkdir(parents=True, exist_ok=True)
            retained = Path(tempfile.mkdtemp(prefix='collapse-actors-', dir=failures))
            for source in (incoming, expected, actual):
                if source.exists(): shutil.copy2(source, retained / source.name)
            def output(name):
                value = getattr(result if result is not None else error, name, '')
                return value.decode(errors='replace') if isinstance(value, bytes) else value
            failure = dict(error=str(error), command=command,
                replay_command=[command[0], command[1], str(retained / incoming.name), str(retained / 'rerun-actual.bin')],
                returncode=getattr(result, 'returncode', None), stdout=output('stdout'), stderr=output('stderr'),
                case_sizes=case_sizes, github_sha=os.environ.get('GITHUB_SHA'), audio='dummy', video='dummy')
            (retained / 'failure.json').write_text(json.dumps(failure, indent=2) + '\n', encoding='utf-8', newline='\n')
            print('collapse_actor_failure_retained=' + str(retained), flush=True)
        except Exception as retention_error:
            print('collapse_actor_retention_error=' + str(retention_error), flush=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--exe', type=Path)
    mode.add_argument('--oracle-only', action='store_true')
    mode.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    data = metadata()
    source = '\n'.join(item.text for item in source_files(ROOT, 'app', 'runtime'))
    contract(source)
    cases = list(records(data))
    if args.self_check:
        mutants = 0
        ranges = ranges_for(source)
        for name, statements in CONTRACT.items():
            first, last = ranges[name]
            body = '\n'.join(source.splitlines()[first - 1:last])
            for statement in statements:
                # Compacting lets multiline production calls remain one mutation target.
                changed = source.replace(body, compact(body).replace(compact(statement), ''))
                try: contract(changed)
                except ValueError: mutants += 1
                else: raise ValueError('collapse actor checker accepted source mutant')
        with tempfile.TemporaryDirectory(prefix='lezac-collapse-actor-controls-') as directory:
            actual, expected = (Path(directory) / name for name in ('actual.bin', 'expected.bin'))
            expected.write_bytes(b'abcdefgh')
            compare(expected, expected, [3, 5])
            for value in (b'', b'abc', b'abXdefgh', b'abcXefgh', b'abcdefgX', b'abcdefghx'):
                actual.write_bytes(value)
                try: compare(actual, expected, [3, 5])
                except ValueError: pass
                else: raise ValueError('collapse actor comparator accepted mutant')
        print(f'original_collapse_actors_contract=ok source_mutants={mutants} comparator_mutants=6 compiled_cpp=0')
        return
    if args.oracle_only:
        print('original_collapse_actors_oracle=ok cases=2476 actor_states=1822 admissions=414 compiled_cpp=0 natural_gameplay=0')
        return
    with tempfile.TemporaryDirectory(prefix='lezac-collapse-actors-') as directory:
        directory = Path(directory)
        incoming, actual, expected = (directory / name for name in ('input.bin', 'actual.bin', 'expected.bin'))
        sizes = [len(result) for request, result, offset in cases]
        incoming.write_bytes(b'LZCA0001' + struct.pack('<I', len(cases)) + b''.join(request for request, result, offset in cases))
        expected.write_bytes(b''.join(result for request, result, offset in cases))
        run_probe(args.exe, incoming, actual, expected, sizes)
        original = actual.read_bytes()
        case_base = sum(sizes[:2395])
        actor_base = case_base + cases[2395][2] + 2
        # Deliberate output controls are outside failure retention for real probes.
        for offset in (0, case_base + cases[2395][2], actor_base, actor_base + 22, actor_base + 38, actor_base + 42):
            changed = bytearray(original)
            changed[offset] ^= 1
            actual.write_bytes(changed)
            try: compare(actual, expected, sizes)
            except ValueError: pass
            else: raise ValueError('collapse actor comparator accepted output mutant')
    print('original_collapse_actors=ok cases=2476 actor_states=1822 admissions=414 output_mutants=6 clean_unused_slots=1 natural_gameplay=0')


if __name__ == '__main__':
    main()
