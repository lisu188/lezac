"""Compare compiled pickup post-allocation initialization with executed original bytes."""
import argparse
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import tempfile

from source_guardrails import function_ranges, mask_cpp


ROOT = Path(__file__).resolve().parents[1]
GZIP_SHA = '7439d7b682f0b7927d0eb2c4914b8f537b0d4634c155f7b806d566a0c76fa3e2'
METADATA_SHA = 'bd704b411728f092c52bd7c84bb936a8716f39b0bad954f5ba2f1d6e2327445d'
RAW_SHA = 'a6e62f1397c08c90a4b1f88d45a66add2e883f5b8bc6ce8856c73cc5a55e09d1'
EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
NATIVE_SHA = '8604621c87c91e23bbe02f66cedfb312fd95b2c5a5cc429b0eca37872345f55e'
GENERATOR_SHA = '3e3aa504e8cdca8aa08b0351beb897c5ab5c80f29a469e0c491e7a9ab3077075'
ENTRY_SHA = '361243c87d22b18dcde990025dc20068ef1ab40e4f297f2264835f6ee2649892'
BANNER = 'pickup_post_init_probe=ok cases=480 audio=dummy\n'
BOUNDARIES = ((0, 0), (1, 0), (29, 0), (29, 13), (29, 14), (30, 0), (30, 13), (30, 14))
PATTERNS = (bytes((71, 69, 79, 1, 2, 1, 1)), bytes((79, 69, 79, 250, 2, 2, 255)),
            bytes((0, 0, 0, 0, 0, 0, 1)))


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fixture():
    folder = ROOT / 'tests/gameplay'
    packed = (folder / 'pickup_post_init_original.bin.gz').read_bytes()
    encoded = (folder / 'pickup_post_init_original.json').read_bytes()
    if digest(packed) != GZIP_SHA or digest(encoded) != METADATA_SHA:
        raise RuntimeError('pinned pickup fixture differs')
    metadata, expected = json.loads(encoded), gzip.decompress(packed)
    if len(expected) != 79320 or digest(expected) != RAW_SHA:
        raise RuntimeError('pickup vector length/hash differs')
    original = (ROOT / 'LEZAC.EXE').read_bytes()
    native = (ROOT / 'tests/fixtures/fracture_actor_original.txt').read_text(encoding='ascii').encode('ascii')
    generator = (ROOT / 'tools/capture_original_pickup_post_init.py').read_bytes()
    if (digest(original) != EXE_SHA or digest(native) != NATIVE_SHA or
            digest(generator) != GENERATOR_SHA or
            digest(original[0x770 + 0x6d81:0x770 + 0x6e01]) != ENTRY_SHA):
        raise RuntimeError('original pickup provenance differs')
    required = dict(schema='lezac.original-pickup-post-init.v1', cases=480,
        original_exe_sha256=EXE_SHA, native_descriptor_fixture_sha256=NATIVE_SHA,
        generator_sha256=GENERATOR_SHA, entry_bytes_sha256=ENTRY_SHA,
        compressed_sha256=GZIP_SHA, outputs_sha256=RAW_SHA, output_bytes=79320,
        executor='Unicorn 2.1.4', entry_anchor='1000:6D81', exit_anchor='1000:6E01',
        admissions=240, full_pool_attempts=120, pickup_cap_skips=120,
        categories=['effect', 'marker', 'monster', 'reward', 'static_bomb'],
        complete_random_constructor_and_animation_helpers=True,
        boundary_registers_verified=True, bomb_animation_implicit_static=True,
        original_calls_stubbed=False, original_instructions_patched=False,
        hardware_io_permitted=False, full_actor_fields_compared=False,
        natural_full_pool_pickup_reachability_proven=False, visual_parity_claim=False,
        sound_parity_claim=False, whole_game_complete=False)
    if any(metadata.get(key) != value for key, value in required.items()):
        raise RuntimeError('pickup evidence scope differs')
    rows, offset = [], 0
    for count, pickups in BOUNDARIES:
        for category, pattern, seed, sprite in itertools.product(range(5), range(3),
                                                               (0x12345678, 0xffffffff), (80, 90)):
            admitted = pickups < 14 and count < 30
            length = 6 + 7 * (count + int(admitted))
            rows.append(dict(count=count, pickups=pickups, category=category, pattern=pattern,
                             seed=seed, sprite=sprite, output_bytes=length))
            record = expected[offset:offset + length]
            if record[:2] != bytes((count + admitted, pickups + admitted)):
                raise RuntimeError('original pickup count boundary differs')
            animations = [PATTERNS[pattern]] * count
            if count and category == 4:
                animations[-1] = PATTERNS[2]
            if admitted:
                animations.append(PATTERNS[2])
            elif pickups < 14:
                animations[-1] = PATTERNS[2]
            if record[6:] != b''.join(animations):
                raise RuntimeError('original pickup animation boundary differs')
            if pickups >= 14 and int.from_bytes(record[2:6], 'little') != seed:
                raise RuntimeError('pickup-cap skip consumed RNG')
            offset += length
    if rows != metadata['cases_in_order'] or offset != len(expected):
        raise RuntimeError('pickup case order/extent differs')
    return expected, rows


def body(source, name):
    source = source.replace('ActorAnimation animation = {0, 0, 0, 0, 0, 0, 1}', 'ActorAnimation animation')
    source = source.replace('void collectObjectiveTiles(const Player& player, uint8_t playerIndex) {',
                            'void collectObjectiveTilesDelegating(const Player& player, uint8_t playerIndex) {')
    ranges = function_ranges(source, [name])
    if name not in ranges:
        raise RuntimeError('missing pickup function: ' + name)
    first, last = ranges[name]
    return mask_cpp(''.join(source.splitlines(keepends=True)[first - 1:last]))


def source_contract(app, cmake, workflow):
    initialize = body(app, 'initializePickupTailAnimation')
    collect = body(app, 'collectObjectiveTiles')
    probe = body(app, 'debugOriginalPickupPostInit')
    requirements = (
        (initialize, ('const auto entries = sharedActorEntries();', 'if (entries.empty()) return;',
            'const auto& entry = entries.back();', 'const ActorAnimation stopped{0, 0, 0, 0, 0, 0, 1};',
            'transientActors_[entry.index].animation = stopped;',
            'launchPadMarkers_[entry.index].animation = stopped;',
            'bonusDrops_[entry.index].animation = stopped;',
            'monster.animCursor = monster.animStart = monster.animEnd = 0xff;',
            'monster.animTick = monster.animDelay = monster.animMode = 0;', 'monster.animStep = 1;')),
        (collect, ('if (pickupActorCount() < 14) {',
            'const auto vy8 = static_cast<int16_t>(-40 - randomRangeValue(0, 200));',
            'pickupSprites[tile - 0x67], 0x0a, 12);\n                initializePickupTailAnimation();')),
        (probe, ('category < 5', 'randomSeed_ = seed;', 'collectObjectiveTiles(player_, 1);',
            'const auto entries = sharedActorEntries();', 'output.put(static_cast<char>(pickupActorCount()));',
            'output.put(static_cast<char>(randomSeed_ >> shift));', 'const auto packed = actual.packed();',
            'monster.animCursor + 1', 'monster.animFrame != 43', 'launchPadMarkers_[entry.index].frame != 91')),
        (cmake, ('NAME pickup_post_init_original', 'NAME pickup_post_init_contract',
            'NAME pickup_post_init_checker_failures', '--exe $<TARGET_FILE:lezac_cpp>',
            '"${CMAKE_CURRENT_BINARY_DIR}/pickup-post-init-checks"')),
        (workflow, ("-R '^(pickup_post_init_(original|contract|checker_failures)|transient_actor_limits)$'",)),
    )
    for text, snippets in requirements:
        for snippet in snippets:
            if snippet not in text:
                raise RuntimeError('missing pickup routing: ' + snippet)
    if 'monster.animFrame =' in initialize or 'readFile(' in probe or 'ifstream' in probe:
        raise RuntimeError('pickup initialization changes visible frame or probe reads expected data')
    if collect.count('initializePickupTailAnimation();') != 1:
        raise RuntimeError('pickup tail initialization multiplicity differs')
    for platform in ('linux', 'windows'):
        for phase in ('focused', 'final'):
            if 'name: pickup-post-init-' + platform + '-' + phase not in workflow:
                raise RuntimeError('missing pickup diagnostic upload')


def compare_vectors(expected, actual, rows):
    if len(actual) != len(expected):
        raise RuntimeError(f'pickup vector length: actual={len(actual)} expected={len(expected)}')
    if actual == expected:
        return
    byte = next(index for index, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1])
    offset = 0
    for index, row in enumerate(rows):
        if byte < offset + row['output_bytes']:
            raise RuntimeError(f'pickup mismatch: case={index} controls={row} record_byte={byte - offset} byte={byte}')
        offset += row['output_bytes']
    raise RuntimeError('pickup mismatch outside case extents')


def self_check(expected, rows):
    app = (ROOT / 'src/app/app.cpp').read_text(encoding='utf-8')
    cmake = (ROOT / 'CMakeLists.txt').read_text(encoding='utf-8')
    workflow = (ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8')
    source_contract(app, cmake, workflow)
    mutants = []
    for old, new in (
        ('const auto& entry = entries.back();', 'const auto& entry = entries.front();'),
        ('initializePickupTailAnimation();', ';'),
        ('if (pickupActorCount() < 14) {', 'if (pickupActorCount() <= 14) {'),
        ('randomRangeValue(0, 200)', 'randomRangeValue(0, 199)'),
        ('transientActors_[entry.index].animation = stopped;', ';'),
        ('launchPadMarkers_[entry.index].animation = stopped;', ';'),
        ('bonusDrops_[entry.index].animation = stopped;', ';'),
        ('monster.animCursor = monster.animStart = monster.animEnd = 0xff;', 'monster.animFrame = 0;'),
        ('monster.animTick = monster.animDelay = monster.animMode = 0;', 'monster.animTick = 0;'),
        ('monster.animStep = 1;', 'monster.animStep = 0;'),
        ('collectObjectiveTiles(player_, 1);', ';'),
        ('const auto packed = actual.packed();', 'const auto packed = animation.packed();'),
    ):
        mutants.append((app.replace(old, new), cmake, workflow))
    mutants.append((app, cmake.replace('NAME pickup_post_init_original', 'NAME pickup_post_init_unused'), workflow))
    mutants.append((app, cmake, workflow.replace('pickup_post_init_(original|contract|checker_failures)', 'unused')))
    for changed in mutants:
        if changed == (app, cmake, workflow):
            raise RuntimeError('ineffective pickup source mutation')
        try:
            source_contract(*changed)
        except RuntimeError:
            continue
        raise RuntimeError('accepted pickup source mutation')
    compare_vectors(expected, expected, rows)
    bad = [b'', expected[:-1], expected + b'\0']
    for position in (0, 1, 2, 6, len(expected) - 1):
        actual = bytearray(expected)
        actual[position] ^= 1
        bad.append(bytes(actual))
    for actual in bad:
        try:
            compare_vectors(expected, actual, rows)
        except RuntimeError:
            continue
        raise RuntimeError('accepted pickup comparison mutation')
    return len(mutants), len(bad)


def run_binary(exe, out, expected, rows, runner=None):
    out.mkdir(parents=True, exist_ok=True)
    retained = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    actual = retained / 'actual.bin'
    command = [str(exe.resolve()), '--debug-original-pickup-post-init', str(actual.resolve())]
    stdout = stderr = ''
    report = dict(command=command, cwd=str(ROOT), audio='dummy', expected_sha256=digest(expected),
        success=False, compiled_execution=runner is None, cases=480,
        natural_full_pool_pickup_reachability_proven=False, whole_game_complete=False)
    try:
        (retained / 'expected.bin').write_bytes(expected)
        result = (runner or subprocess.run)(command, cwd=ROOT,
            env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'),
            capture_output=True, text=True, encoding='utf-8', timeout=30)
        stdout, stderr = result.stdout, result.stderr
        report['returncode'] = result.returncode
        if result.returncode != 0 or stdout != BANNER:
            raise RuntimeError('compiled pickup probe failed or its coverage banner differs')
        compare_vectors(expected, actual.read_bytes(), rows)
        report['success'] = True
    except Exception as error:
        if isinstance(error, subprocess.TimeoutExpired):
            stdout, stderr = error.stdout or '', error.stderr or ''
            report['timeout'] = True
        report['error'] = str(error)
        raise
    finally:
        stdout = stdout.decode('utf-8', 'replace') if isinstance(stdout, bytes) else stdout
        stderr = stderr.decode('utf-8', 'replace') if isinstance(stderr, bytes) else stderr
        (retained / 'stdout.txt').write_text(stdout, encoding='utf-8', newline='\n')
        (retained / 'stderr.txt').write_text(stderr, encoding='utf-8', newline='\n')
        report['actual_exists'] = actual.exists()
        if actual.exists():
            try:
                report['actual_sha256'] = digest(actual.read_bytes())
            except OSError as error:
                report['actual_read_error'] = str(error)
        (retained / ('result.json' if report['success'] else 'failure.json')).write_text(
            json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    return retained


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-check', action='store_true')
    mode.add_argument('--exe', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.exe and args.out is None:
        parser.error('--exe requires --out for retained evidence')
    expected, rows = fixture()
    source_mutations, comparison_mutations = self_check(expected, rows)
    if args.self_check:
        print(f'pickup_post_init_contract=ok cases=480 source_mutations={source_mutations} '
              f'comparator_mutations={comparison_mutations} compiled_claim=0')
        return
    retained = run_binary(args.exe, args.out.resolve(), expected, rows)
    print('pickup_post_init_original=ok cases=480 admissions=240 full_pool_attempts=120 '
          'pickup_cap_skips=120 natural_reachability=0 whole_game_parity=0')
    print('retained=' + str(retained))


if __name__ == '__main__':
    main()
