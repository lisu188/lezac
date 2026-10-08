"""Compare compiled transient creation/shared clamp with original constructor output."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from source_guardrails import function_ranges, mask_cpp


ROOT = Path(__file__).resolve().parents[1]
GZIP_SHA = 'f1380c0ca0e64d81b97a1cb60da4194b868c930312854df80b25cddaeaf8ac41'
METADATA_SHA = '129542766d38e617b3f3f10cb7916c470a19ccf6c4a43e1f06fcdd1b3d5c3fa5'
RAW_SHA = '8d1cf2ab4126b1f9f67604ab763541d037aab549b6ba5aa2c7e91fe588890fe8'
EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
BANNER = ('actor_constructor_velocity_scan=ok axis_inputs=131072 transient_constructors=131072'
          ' x_shared_helper=65536 y_transient_path=65536 audio=dummy\n')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fixture():
    folder = ROOT / 'tests/gameplay'
    packed = (folder / 'actor_constructor_velocity_original.bin.gz').read_bytes()
    encoded = (folder / 'actor_constructor_velocity_original.json').read_bytes()
    if digest(packed) != GZIP_SHA or digest(encoded) != METADATA_SHA:
        raise RuntimeError('pinned constructor fixture differs')
    metadata = json.loads(encoded)
    expected = gzip.decompress(packed)
    if len(expected) != 524288 or digest(expected) != RAW_SHA:
        raise RuntimeError('constructor vector length/hash differs')
    original = (ROOT / 'LEZAC.EXE').read_bytes()
    # The evidence text is pinned in its canonical LF representation.
    native = (ROOT / 'tests/fixtures/fracture_actor_original.txt').read_text(encoding='ascii').encode('ascii')
    generator = ROOT / 'tools/capture_original_actor_constructor_velocity.py'
    if (digest(original) != EXE_SHA or
            digest(original[0x770 + 0x2f9f:0x770 + 0x30a3]) != metadata['constructor_bytes_sha256'] or
            digest(native) != metadata['native_descriptor_fixture_sha256'] or
            digest(generator.read_bytes()) != metadata['generator_sha256']):
        raise RuntimeError('original constructor provenance differs')
    if (metadata['exhaustive_axis_cases'] != 131072 or
            not metadata['complete_constructor_executed'] or
            not metadata['return_boundaries_verified'] or
            metadata['original_calls_stubbed'] or metadata['original_instructions_patched'] or
            metadata['natural_reachability_proven'] or metadata['whole_game_complete']):
        raise RuntimeError('constructor evidence scope differs')
    return expected


def body(source, name):
    source = source.replace('ActorAnimation animation = {0, 0, 0, 0, 0, 0, 1}',
                            'ActorAnimation animation')
    ranges = function_ranges(source, [name])
    if name not in ranges:
        raise RuntimeError('missing constructor function: ' + name)
    first, last = ranges[name]
    return mask_cpp(''.join(source.splitlines(keepends=True)[first - 1:last]))


def source_contract(app, models, cmake, workflow):
    requirements = (
        (body(models, 'clampConstructedActorVelocity8'), (
            'if (velocity == -32768) return velocity;',
            'if (velocity < -0x07ff) return -0x07ff;',
            'if (velocity > 0x07ff) return 0x07ff;',
        )),
        (body(app, 'spawnTransientActor'), ('actor.vy8 = clampConstructedActorVelocity8(vy8);',)),
        (body(app, 'placeBombAt'), (
            'bomb.vx8 = clampConstructedActorVelocity8(static_cast<int16_t>(3 * player.vx8) / 2);',
            'bomb.vy8 = clampConstructedActorVelocity8(static_cast<int16_t>(player.vy8 - 500));',
        )),
        (body(app, 'debugOriginalActorConstructorVelocity'), (
            'axis != 2', 'input != 65536', 'transientActors_.clear();',
            'spawnTransientActor(184, 160, axis == 1 ? value : 0,',
            'word(axis == 0 ? clampConstructedActorVelocity8(value) : actor->vx8);',
            'word(actor->vy8);',
        )),
        (cmake, ('NAME actor_constructor_velocity_original', 'NAME actor_constructor_velocity_contract',
                 'NAME actor_constructor_velocity_checker_failures', '--exe $<TARGET_FILE:lezac_cpp>',
                 '"${CMAKE_CURRENT_BINARY_DIR}/actor-constructor-velocity-checks"')),
        (workflow, ("-R '^(actor_constructor_velocity_(original|contract|checker_failures)|bomb_launch_word)$'",)),
    )
    for text, snippets in requirements:
        for snippet in snippets:
            if snippet not in text:
                raise RuntimeError('missing constructor routing: ' + snippet)
    probe = body(app, 'debugOriginalActorConstructorVelocity')
    if 'readFile(' in probe or 'readBinaryFile(' in probe or 'ifstream' in probe:
        raise RuntimeError('constructor probe reads external expected data')


def compare_vectors(expected, actual):
    if len(actual) != len(expected):
        raise RuntimeError(f'constructor vector length: actual={len(actual)} expected={len(expected)}')
    if actual != expected:
        byte = next(i for i, (left, right) in enumerate(zip(expected, actual)) if left != right)
        row = byte // 4
        axis, word = divmod(row, 65536)
        raise RuntimeError(f'constructor mismatch: axis={axis} input_word={word} byte={byte}')


def self_check(expected):
    compare_vectors(expected, expected)
    app = (ROOT / 'src/app/app.cpp').read_text(encoding='utf-8')
    models = (ROOT / 'src/gameplay/actor_models.hpp').read_text(encoding='utf-8')
    cmake = (ROOT / 'CMakeLists.txt').read_text(encoding='utf-8')
    workflow = (ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8')
    source_contract(app, models, cmake, workflow)
    mutants = (
        (app.replace('actor.vy8 = clampConstructedActorVelocity8(vy8);', 'actor.vy8 = vy8;'), models, cmake, workflow),
        (app, models.replace('if (velocity == -32768) return velocity;', ';'), cmake, workflow),
        (app, models.replace('velocity > 0x07ff', 'velocity > 0x0800'), cmake, workflow),
        (app, models.replace('velocity < -0x07ff', 'velocity < -0x0800'), cmake, workflow),
        (app.replace('static_cast<int16_t>(3 * player.vx8) / 2', '3 * player.vx8 / 2'), models, cmake, workflow),
        (app.replace('static_cast<int16_t>(player.vy8 - 500)', 'player.vy8 - 500'), models, cmake, workflow),
        (app.replace('word(actor->vy8);', 'word(axis == 1 ? value : 0);'), models, cmake, workflow),
        (app, models, cmake, workflow.replace('actor_constructor_velocity_(original|contract|checker_failures)',
                                            'actor_constructor_velocity_unused')),
    )
    for index, changed in enumerate(mutants):
        if changed == (app, models, cmake, workflow):
            raise RuntimeError(f'source mutation {index} was ineffective')
        try:
            source_contract(*changed)
        except RuntimeError:
            continue
        raise RuntimeError(f'source mutation {index} was accepted')
    bad = [b'', expected[:-1], expected + b'\x00']
    for row, axis, value in ((32768, 0, -2047), (65536 + 32768, 1, -2047),
                             (2048, 0, 2048), (65536 + 2048, 1, 2048),
                             (63488, 0, -2048), (65536 + 63488, 1, -2048),
                             (32767, 0, -2047), (65536 + 32767, 1, -2047), (0, 1, 1)):
        mutated = bytearray(expected)
        struct.pack_into('<h', mutated, row * 4 + axis * 2, value)
        bad.append(bytes(mutated))
    for index, actual in enumerate(bad):
        if actual == expected:
            raise RuntimeError(f'comparison mutation {index} was ineffective')
        try:
            compare_vectors(expected, actual)
        except RuntimeError:
            continue
        raise RuntimeError(f'comparison mutation {index} was accepted')


def run_binary(exe, out, expected, runner=None):
    out.mkdir(parents=True, exist_ok=True)
    retained = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    actual = retained / 'actual.bin'
    (retained / 'expected.bin').write_bytes(expected)
    command = [str(exe.resolve()), '--debug-original-actor-constructor-velocity', str(actual.resolve())]
    stdout = stderr = ''
    report = dict(command=command, cwd=str(ROOT), audio='dummy', expected_sha256=digest(expected),
                  success=False, natural_reachability_proven=False, whole_game_complete=False)
    try:
        result = (runner or subprocess.run)(command, cwd=ROOT,
            env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'),
            capture_output=True, text=True, encoding='utf-8', timeout=30)
        stdout, stderr = result.stdout, result.stderr
        report['returncode'] = result.returncode
        if result.returncode != 0 or stdout != BANNER:
            raise RuntimeError('compiled constructor probe failed or its coverage banner differs')
        compare_vectors(expected, actual.read_bytes())
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
    expected = fixture()
    self_check(expected)
    if args.self_check:
        print('actor_constructor_velocity_contract=ok source_mutations=8 comparator_mutations=12 compiled_claim=0')
        return
    retained = run_binary(args.exe, args.out.resolve(), expected)
    print('actor_constructor_velocity_original=ok axis_cases=131072 x_shared_helper=65536 '
          'y_transient_path=65536 original_complete_constructor=1 natural_reachability=0 whole_game_parity=0')
    print('retained=' + str(retained))


if __name__ == '__main__':
    main()
