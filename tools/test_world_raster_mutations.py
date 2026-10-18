"""Require live-raster ownership controls to reject seven isolated faults."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def run(cxx, libraries, viewport_oracle, camera_oracle, out):
    out = out / str(time.time_ns())
    out.mkdir(parents=True)
    paths = ('src/rendering/world_raster.cpp', 'src/gameplay/map_plane_memory.hpp', 'src/rendering/game_renderer.cpp')
    originals = {name: (ROOT / name).read_bytes() for name in paths}
    faults = (
        ('physical_visual_bypass', paths[0], 'physical_ = world.physicalVisuals;', 'physical_ = nullptr;'),
        ('wrapped_word_high_byte', paths[1],
         'return readByte(objectBase + offset, tiles, words);',
         'return readByte(objectBase + static_cast<uint16_t>(offset), tiles, words);'),
        ('wrong_vga_destination', paths[0], '1284+layout.left[0]', '1285+layout.left[0]'),
        ('caller_bypass', paths[2], 'worldRaster_.drawGame(world, presentation_, canvas_);', 'preview.drawGame();'),
        ('unknown_data_zero_fill', paths[0],
         'throw std::out_of_range("World raster reached unrecovered data byte " + std::to_string(offset));',
         'return 0;'),
        ('camera_overwrites_player_visual', paths[0],
         'execute(world,presentation,canvas,&camera);',
         'word(0xc21e,static_cast<uint16_t>(static_cast<int>(camera.x))); '
         'word(0xc220,static_cast<uint16_t>(static_cast<int>(camera.y))); execute(world,presentation,canvas);'),
        ('camera_identity_alias', paths[0], 'if (camera) {',
         'if (camera && camera == &world.players[1].player) {'))
    report = dict(status='failed', faults=[], original_sha256={
        name: hashlib.sha256(raw).hexdigest() for name, raw in originals.items()})
    try:
        for name, relative, before, after in faults:
            source = originals[relative].decode('ascii')
            if source.count(before) != 1:
                raise ValueError('Mutation location differs: ' + name)
            variant = out / name
            target = variant / Path(relative).relative_to('src')
            target.parent.mkdir(parents=True)
            target.write_text(source.replace(before, after), encoding='ascii')
            cpp = target if target.suffix == '.cpp' else ROOT / paths[0]
            test = 'viewport_width_original_test.cpp' if relative == paths[2] else 'world_raster_test.cpp'
            arguments = [str(viewport_oracle)] if relative == paths[2] else []
            camera_fault = name.startswith('camera_')
            if camera_fault:
                test = 'standalone_camera_original_test.cpp'
                arguments = [str(camera_oracle)]
            exe = variant / 'test'
            command = [cxx, '-std=c++23', '-O2', '-Wall', '-Wextra', '-Werror', '-pedantic',
                       '-I', str(variant), '-I', str(ROOT / 'src'),
                       str(ROOT / 'tests/rendering' / test), str(cpp),
                       *map(str, libraries), '-o', str(exe)]
            built = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (variant / 'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Mutant did not compile: ' + name)
            checked = subprocess.run([str(exe), *arguments], cwd=ROOT, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, timeout=30)
            (variant / 'replay.log').write_bytes(checked.stdout)
            expected = (b'standalone_camera_original=failed' if camera_fault else
                b'GameRenderer bypassed the recovered render caller' if relative == paths[2] else b'world_raster_owners=failed')
            if checked.returncode != 1 or expected not in checked.stdout:
                raise ValueError('Live-raster fault was not detected: ' + name)
            report['faults'].append(dict(name=name, exit_code=checked.returncode,
                                        output=checked.stdout.decode()))
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        report['original_source_preserved'] = all(
            (ROOT / name).read_bytes() == raw for name, raw in originals.items())
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    if not report['original_source_preserved']:
        raise ValueError('Live-raster source changed during mutation checks')
    print('world_raster_mutations=ok faults=7 original_source_preserved=1 report=' + str(out / 'report.json'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', required=True)
    parser.add_argument('--library', type=Path, action='append', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--viewport-oracle', type=Path, required=True)
    parser.add_argument('--camera-oracle', type=Path, required=True)
    args = parser.parse_args()
    run(args.cxx, args.library, args.viewport_oracle, args.camera_oracle, args.out)
