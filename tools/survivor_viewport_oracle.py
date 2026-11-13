"""Execute original life-loss, survivor view setup and backdrop-gradient blocks."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct

import unicorn
from unicorn.x86_const import (UC_X86_REG_CS, UC_X86_REG_IP, UC_X86_REG_SP,
                              UC_X86_INS_IN, UC_X86_INS_OUT)
from render_view_gate_origin import authenticate, MANIFEST_SHA, RECIPE_SHA
from render_view_gate_oracle import REGS

PROFILES = [(lost, 0, target) for lost in (1, 2) for target in (168, 240, 320)] + [
    (1, 1, 168), (2, 1, 168)]


def generate(root, capture, out):
    assert unicorn.__version__ == '2.1.4'
    assert out.resolve().is_relative_to(Path('/dev/shm')) and not out.exists()
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    recipe = authenticate(root)
    assert sha((capture / 'report.json').read_bytes()) == RECIPE_SHA
    ram = gzip.decompress((capture / 'gameplay-middle.ram.gz').read_bytes())
    sample = next(item for item in recipe['samples'] if item['name'] == 'gameplay-middle')
    assert len(ram) == 1048576 and sha(ram) == sample['ram_sha256']
    cs, ds = recipe['code_segment'], recipe['data_segment']
    data = ds * 16
    exe = (root / 'LEZAC.EXE').read_bytes()
    assert sha(exe) == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    mz = struct.unpack_from('<14H', exe)
    image = bytearray(exe[0x770:])
    for index in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + index * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + cs) & 65535)
    assert ram[cs * 16:cs * 16 + 43552] == image[:43552]
    out.mkdir()
    records = []
    for lost, reserve, target in PROFILES:
        initial = bytearray(ram)
        initial[data + 0x79b8] = 2
        initial[data + 0x79e6:data + 0x79e8] = b'\x01\x01'
        initial[data + 0x79ea:data + 0x79ec] = b'\x02\x02'
        initial[data + 0x79e9 + lost] = reserve
        initial[data + 0x79ca] = 1
        initial[data + 0x1b7b] = initial[data + 0x1b80] = 0
        initial[data + 0x1b76] = initial[data + 0x1b77] = 0
        initial[data + 0xc496] = 2
        initial[data + 0xc49c] = 1
        struct.pack_into('<H', initial, data + 0x79ee, 40)
        struct.pack_into('<H', initial, data + 0xc1f8, 160)
        struct.pack_into('<H', initial, data + 0x2098, 0)
        actor = ram[data + 0x1b88:data + 0x1b88 + 38]
        descriptor = initial[data + 0xc326:data + 0xc32a]
        for player, x in ((1, 104), (2, 296)):
            base = data + 0x1b62 + player * 38
            initial[base:base + 38] = actor
            initial[base + 1] = player - 1
            initial[base + 21] = 2 if player == lost else player - 1
            struct.pack_into('<H', initial, base + 16, 1 if player == lost else 0)
            initial[data + 0xc21e + (player - 1) * 8:data + 0xc226 + (player - 1) * 8] = struct.pack('<HH', x, 168) + descriptor
        values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x3ffe,
                  cs, ds, 0x40, cs + mz[7], 0x3fe4, 0x838, 0x202)
        stages = [
            ('geometry', [(0x838, 0xfff0, 20)], None),
            ('initial', [(0x2c7a, 0x2c89, None), (0x2cf6, 0x2cf9, None), (0x7a13, 0x7a57, None)], None),
            ('life_loss', [(0x7c3d, 0x7ebb, None)], None),
            ('survivor_draw', [(0x7a13, 0x7a57, None)], None),
            ('e_at_split', [(0x820f, 0x8283, None)], ord('e')),
            ('r_reframe', [(0x820f, 0x8283, None)] * ((target - 160) // 8), ord('r')),
            ('reframed_draw', [(0x7a13, 0x7a57, None)], None),
            ('next_level_frame', [(0x2be4, 0x2bf9, None), (0x2c7a, 0x2c89, None), (0x2cf6, 0x2cf9, None)], None),
            ('backdrop_reinit', [(0x77e4, 0x77f4, None)], None),
            ('new_backdrop_draw', [(0x7a13, 0x7a57, None)], None),
        ]
        controls = []
        observed_records = []
        for observed in (True, False):
            engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
            engine.mem_map(0, 1048576)
            engine.mem_write(0, bytes(initial))
            for register, value in zip(REGS, values):
                engine.reg_write(register, value)
            def external(*unused):
                raise RuntimeError('Unexpected original interrupt or I/O')
            engine.hook_add(unicorn.UC_HOOK_INTR, external)
            engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_IN)
            engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_OUT)
            calls = []
            def code(uc, address, size, user):
                segment, ip = uc.reg_read(UC_X86_REG_CS), uc.reg_read(UC_X86_REG_IP)
                if (segment, ip) in ((cs, 0x7c5), (cs, 0x2959), (cs, 0x838), (cs, 0x56b),
                                     (cs, 0x3587), (cs + 0x8ac, 0xf4), (cs + 0x8ac, 0x3c8)):
                    calls.append([segment - cs, ip])
            if observed:
                engine.hook_add(unicorn.UC_HOOK_CODE, code)
            endpoints = []
            try:
                for name, blocks, key in stages:
                    calls.clear()
                    if key is not None:
                        engine.mem_write(data + 0x2058, bytes([key]))
                    if name == 'backdrop_reinit':
                        engine.reg_write(UC_X86_REG_CS, cs + 0x8ac)
                        engine.reg_write(UC_X86_REG_IP, 0xbc)
                        engine.emu_start((cs + 0x8ac) * 16 + 0xbc, (cs + 0x8ac) * 16 + 0xf0, count=3000000)
                        assert engine.reg_read(UC_X86_REG_IP) == 0xf0
                        engine.reg_write(UC_X86_REG_CS, cs)
                    for start, stop, argument in blocks:
                        if key is not None:
                            engine.mem_write(data + 0x2058, bytes([key]))
                        if argument is not None:
                            engine.mem_write(values[10] * 16 + values[11], struct.pack('<HH', stop, argument))
                            engine.reg_write(UC_X86_REG_SP, values[11])
                        engine.reg_write(UC_X86_REG_IP, start)
                        engine.emu_start(cs * 16 + start, cs * 16 + stop, count=3000000)
                        assert engine.reg_read(UC_X86_REG_CS) == cs and engine.reg_read(UC_X86_REG_IP) == stop
                    final = bytes(engine.mem_read(0, 1048576))
                    registers = [engine.reg_read(register) for register in REGS]
                    assert final[cs * 16:cs * 16 + 43552] == image[:43552]
                    endpoints.append((registers, final))
                    if observed:
                        word = lambda at: struct.unpack_from('<H', final, data + at)[0]
                        directory = out / f'p{lost}-reserve{reserve}-target{target}'
                        directory.mkdir(exist_ok=True)
                        (directory / (name + '.ram.gz')).write_bytes(gzip.compress(final, mtime=0))
                        record = dict(lost=lost, reserve=reserve, target=target, stage=name, registers=registers, calls=list(calls),
                            active_count=final[data + 0x79b8], states=list(final[data + 0x79e6:data + 0x79e8]),
                            reserves=list(final[data + 0x79ea:data + 0x79ec]),
                            geometry={hex(at): word(at) for at in (0xc1ea, 0xc1ec, 0xc1f8, 0xc1f6, 0x79ee, 0x79f0, 0x79f2)},
                            visuals=final[data + 0xc21e:data + 0xc22e].hex(), ram_sha256=sha(final),
                            vga_sha256=sha(final[0xa0000:0xa0000 + 64000]))
                        observed_records.append(record)
                        print(json.dumps(record), flush=True)
            except Exception as error:
                (out / 'failed.json').write_text(json.dumps(dict(lost=lost, reserve=reserve, observed=observed,
                    stage=name, error=repr(error), registers=[engine.reg_read(register) for register in REGS], calls=calls), indent=2) + '\n')
                raise
            controls.append(endpoints)
        assert controls[0] == controls[1]
        records.extend(observed_records)
        (out / 'report.json').write_text(json.dumps(dict(cases=records, observed_unobserved_identical=True,
            raw_memory_published=False, instruction_patches=0, calls_stubbed=0,
            controlled_state=True, natural_death_route=False, whole_game_claim=False), indent=2) + '\n')

    output = bytearray(b'LZSURV01' + struct.pack('<IIHH', len(PROFILES), 10, 60, 33))
    word = lambda at: struct.unpack_from('<H', ram, data + at)[0]
    map_at = word(0xc1fe) * 16
    backdrop_at = word(0xc49a) * 16 + word(0xc498)
    output.extend(ram[map_at:map_at + 1980])
    output.extend(ram[backdrop_at:backdrop_at + 60000])
    output.extend(ram[data + 0xc322:data + 0xc322 + 368])
    for lost, reserve, target in PROFILES:
        output.extend(struct.pack('<BBH', lost, reserve, target))
        profile = [item for item in records if (item['lost'], item['reserve'], item['target']) == (lost, reserve, target)]
        assert len(profile) == 10
        initial_pixels = None
        for index, item in enumerate(profile):
            final = gzip.decompress((out / f'p{lost}-reserve{reserve}-target{target}' / (item['stage'] + '.ram.gz')).read_bytes())
            assert sha(final) == item['ram_sha256']
            pixels = final[0xa0000:0xa0000 + 64000]
            geometry = list(item['geometry'].values())
            output.extend(struct.pack('<6B7H', index, item['active_count'], *item['states'], *item['reserves'], *geometry))
            output.extend(bytes.fromhex(item['visuals']))
            output.extend(pixels)
            if index == 1:
                initial_pixels = pixels
            if index == 2:
                assert item['active_count'] == (1 if reserve == 0 else 2)
                assert item['states'][lost - 1] == (0 if reserve == 0 else 2)
                assert item['reserves'][lost - 1] == (255 if reserve == 0 else 0)
                assert pixels[51200:] == initial_pixels[51200:]
                for y in range(160):
                    for x in range(320):
                        at = y * 320 + x
                        cleared = reserve == 0 and x // 160 == lost - 1
                        assert pixels[at] == (0 if cleared else initial_pixels[at])
            if index == 5:
                assert geometry[1] == (target if reserve == 0 else 160)
                assert geometry[2] == 160
            if index == 8:
                assert geometry[2] == geometry[1] and geometry[3] == 0
                output.extend(final[backdrop_at:backdrop_at + 60000])
    compressed = gzip.compress(output, mtime=0)
    manifest = dict(schema='lezac-original-survivor-viewport-v1', profiles=PROFILES, cases=records,
        sources={name: sha((root / name).read_bytes()) for name in ('tools/survivor_viewport_oracle.py',
            'tools/render_view_gate_oracle.py', 'tools/render_view_gate_origin.py')},
        source_capture_manifest_sha256=MANIFEST_SHA, source_recipe_sha256=RECIPE_SHA,
        source_ram_sha256=sha(ram), source_sample='gameplay-middle',
        original_executable_sha256=sha(exe), code_segment=cs, data_segment=ds,
        projection_bytes=len(output), projection_sha256=sha(output), compressed_bytes=len(compressed),
        compressed_sha256=sha(compressed), observed_unobserved_full_memory_registers_equal=True,
        source_code_bytes_verified=43552, instruction_patches=0, calls_stubbed=0, unicorn=unicorn.__version__,
        controlled_state=True, controlled_geometry=True, controlled_block_transfers=True,
        key_reinjected_before_each_handler=True, palette_initialization_io_excluded=True,
        backdrop_gradient_block=[0x8ac, 0xbc, 0xf0], backdrop_latch_block=[0x77e4, 0x77f4],
        raw_memory_published=False, raw_memory_available_to_frozen_checker=False,
        natural_death_route=False, work_clock_claim=False, whole_game_claim=False)
    assert len(output) == 5665280
    (out / 'oracle.bin').write_bytes(output)
    (out / 'oracle.bin.gz').write_bytes(compressed)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(profiles=len(PROFILES), stages=len(records), bytes=len(output), compressed=len(compressed))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    generate(args.repo, args.capture, args.out)
