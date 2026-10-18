"""Execute unchanged 326E ammunition HUD plus real 07C5, 12DB and 313D callees."""
import argparse
import gzip
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT

from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

ASSET_SHA = {'CARO.CAR': '949cce4db6071d6675a291c978d725c6e4ee1730b2c7a428bc1c8a8185cbd8d8',
             'BOMOMIMK.SPR': '08dfd0e59ba191c52af2529bdfa140fd15a57829f0c6c13bbb78e156769ac0d1'}


def profiles():
    result = []
    def add(**values):
        row = dict(entry=0x326e, player=1, selected=0, ammo=2, dirty=2, x=121, y=163,
                   width=8, height=8, source=0x2000, flags=0x202, floor=0x200,
                   sp=0x3fe4, ink=0, background=18, shipped=False, window=False, error=False)
        row.update(values)
        result.append(row)
    for player in (1, 2):
        for selected in range(4):
            for ammo in range(256):
                add(player=player, selected=selected, ammo=ammo,
                    dirty=(0, 1, 2, 255)[(ammo + player + selected) % 4],
                    x=121 + (player - 1) * 180, ink=(ammo * 13 + selected) & 255, shipped=True)
    for selected in (0, 1, 2, 3, 198, 199, 255):
        for width, height in ((1, 1), (2, 3), (17, 5), (31, 2)):
            for flags in (0x202, 0x602):
                for x, y in ((0xfff0, 0xfffe), (0x7ff8, 0x8000)):
                    add(selected=selected, width=width, height=height, flags=flags,
                        x=x, y=y, source=0xfff8, ammo=selected * 13 & 255, ink=245)
    for width, height in ((1, 1), (16, 16), (160, 160), (0, 1), (1, 2)):
        for flags in (0x202, 0x602):
            add(entry=0x7c5, x=0xfff8, y=0xffff, width=width, height=height, flags=flags)
    for width, height in ((1, 1), (2, 3), (16, 16), (255, 1)):
        for flags in (0x202, 0x602):
            for background in (0, 18):
                add(entry=0x12db, selected=57, x=0xfff8, y=0xffff,
                    width=width, height=height, flags=flags, background=background,
                    ink=245, source=0xfff8)
    for width, height in ((1, 1), (2, 3), (16, 16), (255, 1)):
        for background in (0, 18):
            for ink in (0, 1, 245, 255):
                add(entry=0x12db, selected=57, x=64, y=64, width=width, height=height,
                    background=background, ink=ink, source=0xfff8, window=True)
    for values in (
        dict(floor=0x4000), dict(sp=0x200, floor=0), dict(floor=0x3dc7),
        dict(floor=0x3dc3), dict(dirty=1, floor=0x3dcb),
        dict(entry=0x7c5, floor=0x3ddf), dict(entry=0x12db, floor=0x3dd7),
    ):
        add(**values, error=True)
    add(floor=0x3dc2)
    return result


def sprites(raw):
    result, at = [], 1
    for _ in range(raw[0]):
        width, height = raw[at:at + 2]
        at += 2
        pixels = raw[at:at + width * height]
        if len(pixels) != width * height:
            raise ValueError('Original sprite geometry differs')
        result.append((width, height, pixels))
        at += len(pixels)
    if at != len(raw) or len(result) != 91:
        raise ValueError('Original sprite atlas differs')
    return result


def inputs(index, p, tiles, atlas):
    seeds = []
    def put(address, raw):
        seeds.append((address, raw))
    def data(offset, raw):
        put(0x1aa20 + offset, raw)
    def bank(segment, offset, raw):
        # Byte accesses wrap the offset; word high bytes remain linear on the bus.
        count = min(65536 - offset, len(raw))
        put(segment * 16 + offset, raw[:count])
        if count < len(raw):
            put(segment * 16, raw[count:])
    sp = p['sp']
    put(0x70000 + sp - 64, bytes((i * 29 + index * 7 + 11) & 255 for i in range(84)))
    if p['entry'] == 0x326e:
        args = (0x7c70, p['player'], p['y'], p['x'])
    elif p['entry'] == 0x7c5:
        args = (0x7c70, p['background'], p['height'], p['width'], p['y'], p['x'])
    else:
        args = (0x7c70, p['selected'], p['y'], p['x'])
    put(0x70000 + sp, struct.pack('<' + 'H' * len(args), *args))
    for offset, value in ((0x1afa, p['floor']), (0xc1fa, 0x4000), (0x2070, 0x9000),
                          (0x2072, 0xa55a), (0x2074, 0x5aa5)):
        data(offset, struct.pack('<H', value))
    data(0x79a3, bytes((p['background'] if p['entry'] == 0x12db else index & 255,)))
    data(0x661e, bytes((p['ink'],)))
    bank(0x1aa2, 0x9000, tiles[121 * 64:131 * 64])
    if p['window']:
        for row in range(p['height']):
            put(0xa0000 + (p['y'] + row) * 320 + p['x'], bytes((17,)) * p['width'])
    if p['entry'] == 0x326e:
        data(0x1b73 + p['player'], bytes((p['selected'],)))
        data(0x1b75 + p['player'], bytes((p['dirty'],)))
        data(0x1b67 + p['player'] * 4 + p['selected'], bytes((p['ammo'],)))
    if p['entry'] != 0x7c5:
        selected = p['selected'] + 57 if p['entry'] == 0x326e else p['selected']
        if p['shipped']:
            width, height, pixels = atlas[selected]
        else:
            width, height = p['width'], p['height']
            pixels = bytes((0, 1, 53, 18, 255)[(i + index) % 5] for i in range(width * height))
        descriptor = bytes((width, height)) + struct.pack('<H', p['source'])
        data((0xc322 + (selected & 255) * 4) & 65535, descriptor)
        if selected > 255:
            data((0xc322 + selected * 4) & 65535, bytes((17, 19, 0x5a, 0xa5)))
        bank(0x4000, p['source'], pixels)
    return seeds


def _generate(root, out):
    producer_sha = sha(Path(__file__).read_bytes())
    shared_sha = sha(Path(__file__).with_name('frame_camera_oracle.py').read_bytes())
    if unicorn.__version__ != '2.1.4' or any(k in os.environ for k in ('LD_PRELOAD', 'LIBUNICORN_PATH')):
        raise ValueError('Unsupported Unicorn loader profile')
    library = Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes()) != LIB_SHA or not any(
            line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual Unicorn library mapping differs')
    exe, tiles, sprite_bytes = ((root / name).read_bytes() for name in ('LEZAC.EXE', 'CARO.CAR', 'BOMOMIMK.SPR'))
    if sha(exe) != EXE_SHA or len(tiles) != 8450 or tiles[:2] != bytes((0, 132)):
        raise ValueError('Original executable or tiles differ')
    if sha(tiles) != ASSET_SHA['CARO.CAR'] or sha(sprite_bytes) != ASSET_SHA['BOMOMIMK.SPR']:
        raise ValueError('Canonical original atlas fingerprint differs')
    atlas = sprites(sprite_bytes)
    mz = struct.unpack_from('<14H', exe)
    image = bytearray(exe[mz[4] * 16:])
    for i in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + i * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
    cases = profiles()
    output = bytearray(b'LZAMMO02' + struct.pack('<I', len(cases)))
    app = bytearray(b'LZAMAPP1' + struct.pack('<I', 2048))
    coverage, states, errors, write_total = set(), 0, 0, 0
    try:
        for index, p in enumerate(cases):
            initial = bytearray(1048576)
            initial[0x10000:0x10000 + len(image)] = image
            seeds = inputs(index, p, tiles[2:], atlas)
            for address, raw in seeds:
                initial[address:address + len(raw)] = raw
            values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x3ffe,
                      0x1000, 0x1aa2, 0x40, 0x7000, p['sp'], p['entry'], p['flags'])
            endpoints, trace, writes = [], [], []
            for observed in (True, False):
                engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
                engine.mem_map(0, 1048576)
                engine.mem_write(0, bytes(initial))
                for reg, value in zip(REGS, values):
                    engine.reg_write(reg, value)
                def external(*unused):
                    raise ValueError('Ammunition HUD crossed an unmodeled interrupt or I/O')
                def code(uc, address, size, user):
                    registers = tuple(uc.reg_read(reg) for reg in REGS)
                    trace.append(registers)
                    coverage.add((registers[7], registers[12]))
                def write(uc, access, address, size, value, user):
                    if size not in (1, 2) or not (0x1aa20 <= address < 0x2aa20 or
                            0x70000 <= address < 0x74010 or 0xa0000 <= address < 0xb0001):
                        raise ValueError('Ammunition HUD wrote outside data/stack/VGA')
                    writes.append((address, size, value & ((1 << (size * 8)) - 1)))
                engine.hook_add(unicorn.UC_HOOK_INTR, external)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE, code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
                until = 0x192e2 if p['error'] else 0x17c70
                engine.emu_start(0x10000 + p['entry'], until, count=2000000)
                registers = tuple(engine.reg_read(reg) for reg in REGS)
                final = bytes(engine.mem_read(0, 1048576))
                if registers[7] * 16 + registers[12] != until:
                    raise ValueError('Ammunition HUD did not reach its declared endpoint')
                if final[0x10000:0x1aa20] != image[:0xaa20]:
                    raise ValueError('Original code changed during execution')
                endpoints.append((registers, final))
            if endpoints[0] != endpoints[1]:
                raise ValueError('Ammunition observation affected complete memory/registers')
            registers, final = endpoints[0]
            expected = bytearray(initial)
            for address, size, value in writes:
                expected[address:address + size] = value.to_bytes(size, 'little')
            if expected != final:
                raise ValueError('Observed writes do not reconstruct complete final memory')
            trace.append(registers)
            states += len(trace)
            write_total += len(writes)
            errors += int(p['error'])
            if index < 2048:
                app.extend(bytes((p['player'], p['selected'], p['ammo'], p['dirty'], p['ink'],
                    initial[0x1aa20 + 0x79a3], final[0x1aa20 + 0x79a3],
                    final[0x70000 + p['sp'] - 4], final[0x1aa20 + 0x1b75 + p['player']])))
            output.extend(struct.pack('<II13HI13HI', index, int(p['error']), *values, *registers))
            output.extend(struct.pack('<I', len(seeds)))
            for address, raw in seeds:
                output.extend(struct.pack('<II', address, len(raw)) + raw)
            output.extend(struct.pack('<I', len(trace)))
            # Column storage retains every observation while compressing repeated
            # unchanged register values without an additional codec dependency.
            for column in range(14):
                code = 'I' if column == 13 else 'H'
                output.extend(struct.pack('<' + code * len(trace), *(item[column] for item in trace)))
            output.extend(struct.pack('<I', len(writes)))
            for address, size, value in writes:
                output.extend(struct.pack('<IBH', address, size, value))
        raw = bytes(output)
        compressed = gzip.compress(raw, mtime=0)
        if sha(Path(__file__).read_bytes()) != producer_sha or sha(
                Path(__file__).with_name('frame_camera_oracle.py').read_bytes()) != shared_sha:
            raise ValueError('Oracle source bytes changed before export')
        for name, expected_sha in dict(ASSET_SHA, **{'LEZAC.EXE': EXE_SHA}).items():
            if sha((root / name).read_bytes()) != expected_sha:
                raise ValueError('Canonical asset bytes changed before export: ' + name)
        (out / 'oracle.bin.gz').write_bytes(compressed)
        (out / 'app.bin').write_bytes(app)
        manifest = dict(schema='lezac-controlled-ammunition-hud-v1', executable_sha256=EXE_SHA,
            tile_atlas_sha256=sha(tiles), sprite_atlas_sha256=sha(sprite_bytes), shipped_cases=2048,
            producer_sha256=producer_sha, shared_oracle_sha256=shared_sha,
            app_bytes=len(app), app_sha256=sha(app), window_sprite_cases=32,
            source_bytes_rechecked_before_export=True, canonical_assets_rechecked_before_export=True,
            unicorn_version=unicorn.__version__, unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True, cases=len(cases), register_states=states,
            runtime_errors=errors, ordered_writes=write_total,
            executed_instructions=[list(pair) for pair in sorted(coverage)],
            projection_bytes=len(raw), projection_sha256=sha(raw), compressed_bytes=len(compressed),
            compressed_sha256=sha(compressed), controlled_initial_memory=True,
            full_memory_observer_control=True, raw_memory_published=False, natural_capture=False,
            full_frame_claim=False, work_clock_claim=False, trace_arithmetic_flags_compared=False,
            endpoint_all_flags_compared=True, instruction_patches=0, calls_stubbed=0,
            interrupts_delivered=0, hardware_io=0,
            rep_trace_policy='raw-unicorn-transfer-and-zero-count-observations',
            trace_storage='register-columns-v1')
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        print(json.dumps(dict(status='passed', cases=len(cases), states=states, runtime_errors=errors,
                              bytes=len(raw), compressed=len(compressed), sha256=sha(raw))), flush=True)
    except Exception as error:
        (out / 'failed.json').write_text(json.dumps(dict(status='failed', case=index, error=str(error))) + '\n')
        raise


def generate(root, out):
    out = out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only output directory')
    out.mkdir()
    try:
        _generate(root, out)
    except Exception as error:
        failed = out / 'failed.json'
        if not failed.exists():
            failed.write_text(json.dumps(dict(status='failed', error=str(error))) + '\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    generate(args.repo.resolve(), args.out)
