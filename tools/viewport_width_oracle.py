"""Run original E/R handlers and every legal single-player viewport width."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct

import unicorn
from render_view_gate_origin import authenticate, MANIFEST_SHA, RECIPE_SHA
from render_view_gate_oracle import REGS
from unicorn.x86_const import (UC_X86_REG_CS, UC_X86_REG_IP, UC_X86_REG_SP,
                              UC_X86_INS_IN, UC_X86_INS_OUT)

sha = lambda data: hashlib.sha256(data).hexdigest()
CONTROLS = [(tiles, key, 1) for tiles in range(21, 41) for key in (ord('e'), ord('r'))] + [
    (20, ord('e'), 2), (20, ord('r'), 2), (32, ord('x'), 1), (32, ord('9'), 1)]
VIEWS = [(tiles, x, y, shake, background) for tiles in range(21, 41)
         for x, y, shake, background in ((104, 64, 0, 1), (243, 131, 3, 1), (447, 240, 7, 0))]


def generate(root, capture, out):
    assert unicorn.__version__ == '2.1.4'
    assert out.resolve().is_relative_to(Path('/dev/shm')) and not out.exists()
    recipe = authenticate(root)
    raw_recipe = (capture / 'report.json').read_bytes()
    assert sha(raw_recipe) == RECIPE_SHA and json.loads(raw_recipe) == recipe
    sample = next(item for item in recipe['samples'] if item['name'] == 'gameplay-middle')
    ram = gzip.decompress((capture / 'gameplay-middle.ram.gz').read_bytes())
    assert len(ram) == 1048576 and sha(ram) == sample['ram_sha256']
    exe = (root / 'LEZAC.EXE').read_bytes()
    assert sha(exe) == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    cs, ds = recipe['code_segment'], recipe['data_segment']
    data = ds * 16
    mz = struct.unpack_from('<14H', exe)
    image = bytearray(exe[0x770:])
    for index in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + index * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + cs) & 65535)
    assert ram[cs * 16:cs * 16 + 43552] == image[:43552]
    word = lambda offset: struct.unpack_from('<H', ram, data + offset)[0]
    width, height = word(0xc204), word(0x2096) // 8 + 21
    assert (width, height, word(0xc1f8)) == (60, 33, 320)
    tiles = ram[word(0xc1fe) * 16:word(0xc1fe) * 16 + width * height]
    background_at = word(0xc49a) * 16 + word(0xc498)
    backdrop = ram[background_at:background_at + 60000]
    descriptors = ram[data + 0xc322:data + 0xc322 + 368]
    sprite_width, sprite_height, sprite_offset = struct.unpack_from('<BBH', descriptors, 4)
    sprite_at = word(0xc1fa) * 16 + sprite_offset
    sprite = ram[sprite_at:sprite_at + sprite_width * sprite_height]
    base_values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x3ffe,
                   cs, ds, 0x40, cs + mz[7], 0x3fe4, 0x820f, 0x202)
    out.mkdir()

    def run(initial, blocks):
        endpoints, calls, steps = [], [], [0]
        for observed in (True, False):
            engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
            engine.mem_map(0, 1048576)
            engine.mem_write(0, bytes(initial))
            for register, value in zip(REGS, base_values):
                engine.reg_write(register, value)
            def external(*unused):
                raise RuntimeError('Original viewport crossed an unmodeled interrupt or I/O boundary')
            engine.hook_add(unicorn.UC_HOOK_INTR, external)
            engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_IN)
            engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_OUT)
            def observe(uc, address, size, user):
                steps[0] += 1
                segment, offset = uc.reg_read(UC_X86_REG_CS), uc.reg_read(UC_X86_REG_IP)
                if (segment, offset) in ((cs, 0x838), (cs, 0x2959), (cs, 0x7c5),
                                         (cs, 0x3587), (cs + 0x8ac, 0xf4), (cs + 0x8ac, 0x3c8)):
                    calls.append([segment - cs, offset])
            if observed:
                engine.hook_add(unicorn.UC_HOOK_CODE, observe)
            for start, stop, argument in blocks:
                if argument is not None:
                    stack = base_values[10] * 16 + base_values[11]
                    engine.mem_write(stack, struct.pack('<HH', stop, argument))
                    engine.reg_write(UC_X86_REG_SP, base_values[11])
                engine.reg_write(UC_X86_REG_IP, start)
                engine.emu_start(cs * 16 + start, cs * 16 + stop, count=3000000)
                assert engine.reg_read(UC_X86_REG_CS) == cs and engine.reg_read(UC_X86_REG_IP) == stop
            registers = [engine.reg_read(register) for register in REGS]
            final = bytes(engine.mem_read(0, 1048576))
            assert final[cs * 16:cs * 16 + 43552] == image[:43552]
            endpoints.append((registers, final))
        assert endpoints[0] == endpoints[1]
        return endpoints[0][0], endpoints[0][1], calls, steps[0]

    output = bytearray(b'LZWIDTH1' + struct.pack('<IIHHBB', len(CONTROLS), len(VIEWS), width, height,
                                               sprite_width, sprite_height) + tiles + backdrop + descriptors + sprite)
    records = []
    for index, (columns, key, players) in enumerate(CONTROLS):
        initial = bytearray(ram)
        initial[data + 0x79b8] = players
        initial[data + 0x2058] = key
        struct.pack_into('<H', initial, data + 0x79ee, columns)
        initial[0xa0000:0xb0000] = b'\x4f' * 65536
        blocks = [(0x838, 0xfff0, columns), (0x820f, 0x8283, None)]
        registers, final, calls, steps = run(initial, blocks)
        fields = [struct.unpack_from('<H', final, data + at)[0]
                  for at in (0xc1ea, 0xc1ec, 0xc206, 0xc1f4, 0xc1f6, 0x78bc, 0x79ee)]
        changed = players == 1 and ((key == ord('e') and columns > 21) or (key == ord('r') and columns < 40))
        expected_columns = columns + ((-1 if key == ord('e') else 1) if changed else 0)
        assert fields[0] == expected_columns and fields[1] == expected_columns * 8
        assert fields[2] == 320 - fields[1] and fields[3] == (328 - fields[1]) // 2
        assert fields[4] == 320 - fields[1] and fields[5] == ((expected_columns - 2) // 2) * 8
        assert fields[6] == expected_columns
        assert final[data + 0x2058] == (ord('9') if changed else key)
        assert calls == [[0, 0x838]] + ([[0, 0x7c5], [0, 0x838], [0, 0x2959],
                                       [0, 0x7c5], [0, 0x7c5]] if changed else []), (index, calls)
        pixels = final[0xa0000:0xa0000 + 64000]
        assert pixels[51200:] == b'\x4f' * 12800
        if not changed:
            assert pixels == b'\x4f' * 64000
        output.extend(struct.pack('<HBB7HBI', columns * 8, key, players, *fields, final[data + 0x2058], steps))
        output.extend(pixels)
        records.append(dict(kind='control', index=index, columns=columns, key=chr(key), players=players,
                            changed=changed, fields=fields, calls=calls, unicorn_steps=steps,
                            full_memory_and_register_control_identical=True, final_memory_sha256=sha(final),
                            endpoint_registers=registers, vga_sha256=sha(pixels)))
    for index, (columns, x, y, shake, enabled) in enumerate(VIEWS):
        initial = bytearray(ram)
        initial[data + 0x79b8] = 1
        initial[data + 0x79e6:data + 0x79e8] = b'\x01\x00'
        struct.pack_into('<H', initial, data + 0x79ee, columns)
        struct.pack_into('<H', initial, data + 0x2098, shake)
        initial[data + 0xc496] = 1
        initial[data + 0xc49c] = enabled
        initial[data + 0xc21e:data + 0xc226] = struct.pack('<HH', x, y) + descriptors[4:8]
        blocks = [(0x838, 0xfff0, columns), (0x2c7a, 0x2c89, None),
                  (0x2cf6, 0x2cf9, None), (0x7a13, 0x7a57, None)]
        registers, final, calls, steps = run(initial, blocks)
        fields = [struct.unpack_from('<H', final, data + at)[0]
                  for at in (0xc216, 0xc218, 0xc20a, 0xc20c, 0xc1f0, 0xc1ec, 0xc1f8, 0xc1f6, 0x79f0)]
        assert fields[5:8] == [columns * 8, 320, 320 - columns * 8]
        assert fields[8] == 1280 + (328 - columns * 8) // 2
        assert calls == [[0, 0x838], [0, 0x7c5], [0, 0x2959], [0, 0x7c5], [0, 0x7c5],
                         [0, 0x3587], [0x8ac, 0xf4], [0x8ac, 0x3c8]], (index, calls)
        pixels = final[0xa0000:0xa0000 + 64000]
        output.extend(struct.pack('<HHHBB9HI', columns * 8, x, y, shake, enabled, *fields, steps))
        output.extend(pixels)
        records.append(dict(kind='view', index=index, columns=columns, x=x, y=y, shake=shake, background=enabled,
                            fields=fields, calls=calls, unicorn_steps=steps, endpoint_registers=registers,
                            full_memory_and_register_control_identical=True, final_memory_sha256=sha(final),
                            vga_sha256=sha(pixels)))
        print(json.dumps(dict(index=index, columns=columns, camera=fields[:4], bytes=len(output))), flush=True)
    compressed = gzip.compress(output, mtime=0)
    record = dict(schema='lezac-original-viewport-width-v1', cases=records, sources={
        'tools/viewport_width_oracle.py': sha(Path(__file__).read_bytes()),
        'tools/render_view_gate_oracle.py': sha((root / 'tools/render_view_gate_oracle.py').read_bytes()),
        'tools/render_view_gate_origin.py': sha((root / 'tools/render_view_gate_origin.py').read_bytes())},
        original_executable_sha256=sha(exe), source_capture_manifest_sha256=MANIFEST_SHA,
        source_recipe_sha256=RECIPE_SHA, source_ram_sha256=sha(ram), source_sample='gameplay-middle',
        code_segment=cs, data_segment=ds, source_code_bytes_verified=43552,
        initial_registers=list(base_values),
        control_blocks=[[0x838, 0xfff0, 'controlled near-call return and width argument'], [0x820f, 0x8283, None]],
        view_blocks=[[0x838, 0xfff0, 'controlled near-call return and width argument'],
                     [0x2c7a, 0x2c89, None], [0x2cf6, 0x2cf9, None], [0x7a13, 0x7a57, None]],
        controlled_block_transfers=True, configured_single_player_views=True,
        natural_two_player_elimination_claim=False,
        projection_bytes=len(output), projection_sha256=sha(output), compressed_bytes=len(compressed),
        compressed_sha256=sha(compressed), unicorn=unicorn.__version__, original_calls_stubbed=0,
        instruction_patches=0, raw_memory_published=False, raw_memory_available_to_frozen_checker=False,
        controlled_geometry=True, controlled_single_visual=True, natural_route=False,
        interrupt_timing_claim=False, whole_game_fidelity_claim=False)
    (out / 'oracle.bin').write_bytes(output)
    (out / 'oracle.bin.gz').write_bytes(compressed)
    (out / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(controls=len(CONTROLS), views=len(VIEWS), bytes=len(output), compressed=len(compressed))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        generate(args.repo, args.capture, args.out)
    except Exception as error:
        if args.out.exists():
            (args.out / 'failed.json').write_text(json.dumps(dict(error=repr(error)), indent=2) + '\n')
        raise
