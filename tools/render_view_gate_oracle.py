"""Execute unchanged original camera/draw/present calls on controlled state bytes."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct

import unicorn
from render_view_gate_origin import authenticate, MANIFEST_SHA, RECIPE_SHA
from unicorn.x86_const import (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX,
    UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES,
    UC_X86_REG_SS, UC_X86_REG_SP, UC_X86_REG_IP, UC_X86_REG_EFLAGS, UC_X86_INS_IN, UC_X86_INS_OUT)

REGS = (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX, UC_X86_REG_SI, UC_X86_REG_DI,
    UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS, UC_X86_REG_SP,
    UC_X86_REG_IP, UC_X86_REG_EFLAGS)
PROFILES = [(1, state, 0) for state in (0, 1, 2, 255)] + [
    (2, first, second) for first in (0, 1, 2, 255) for second in (0, 1, 2, 255)]
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def generate(root, capture, out):
    assert unicorn.__version__ == '2.1.4'
    out = out.resolve()
    assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
    recipe_raw = (capture / 'report.json').read_bytes()
    recipe = json.loads(recipe_raw)
    origin = authenticate(root)
    assert sha(recipe_raw) == RECIPE_SHA and recipe == origin
    assert recipe['passed'] is True and recipe['canonical_assets_unchanged'] is True
    sample = next(s for s in recipe['samples'] if s['name'] == 'gameplay-middle')
    ram = gzip.decompress((capture / 'gameplay-middle.ram.gz').read_bytes())
    assert len(ram) == 1048576 and sha(ram) == sample['ram_sha256']
    exe = (root / 'LEZAC.EXE').read_bytes()
    assert sha(exe) == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    cs, ds = recipe['code_segment'], recipe['data_segment']
    assert ds == cs + 0xaa2
    data = ds * 16
    image = bytearray(exe[0x770:])
    mz = struct.unpack_from('<14H', exe)
    for i in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + i * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + cs) & 65535)
    assert ram[cs * 16:cs * 16 + 43552] == image[:43552]
    width = struct.unpack_from('<H', ram, data + 0xc204)[0]
    assert width == 60
    out.mkdir()
    output = bytearray(b'LZVIEW01' + struct.pack('<I', len(PROFILES)))
    cases = []
    for index, (players, first, second) in enumerate(PROFILES):
        initial = bytearray(ram)
        pitch = 320 if players == 1 else 160
        half = pitch // 2 - 8
        controls = [(0xc1ea, pitch // 8), (0xc1ec, pitch), (0xc1ee, 160), (0xc206, 320 - pitch),
            (0xc1f6, 0), (0xc1f8, pitch), (0x78bc, half), (0x78be, half // 8),
            (0x2094, (width - pitch // 8) * 8), (0x79f0, 1284), (0x79f2, 1444), (0x2098, 0)]
        initial[data + 0x79e6:data + 0x79e8] = bytes((first, second))
        for at, value in controls:
            struct.pack_into('<H', initial, data + at, value)
        initial[data + 0xc49c] = 1
        initial[0xa0000:0xb0000] = bytes(((i // 320 // 8) * 3 + i % 320 // 8 + index) & 255 for i in range(65536))
        values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x3ffe,
                  cs, ds, 0x40, cs + mz[7], 0x3fe4, 0x7a13, 0x202)
        endpoints = []
        calls, writes, instructions = [], [0, 0], [0]
        for observed in (True, False):
            engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
            engine.mem_map(0, 1048576)
            engine.mem_write(0, bytes(initial))
            for register, value in zip(REGS, values):
                engine.reg_write(register, value)
            def code(uc, address, size, user):
                instructions[0] += 1
                segment, offset = uc.reg_read(UC_X86_REG_CS), uc.reg_read(UC_X86_REG_IP)
                kind = 0 if segment == cs and offset == 0x3587 else 1 if segment == cs + 0x8ac and offset == 0xf4 else 2 if segment == cs + 0x8ac and offset == 0x3c8 else None
                if kind is not None:
                    ss, sp = uc.reg_read(UC_X86_REG_SS), uc.reg_read(UC_X86_REG_SP)
                    returned = int.from_bytes(uc.mem_read(ss * 16 + sp, 2), 'little')
                    player = 0 if returned in (0x7a25, 0x7a2a, 0x7a35) else 1
                    assert returned == ((0x7a25, 0x7a2a, 0x7a35), (0x7a47, 0x7a4c, 0x7a57))[player][kind]
                    calls.append((player, kind, returned))
            def memory(uc, access, address, size, value, user):
                for at in range(max(address, 0xa0000), min(address + size, 0xa0000 + 160 * 320)):
                    writes[(at - 0xa0000) % 320 // 160] += 1
            def external(*unused):
                raise RuntimeError('Original render crossed an unmodeled interrupt or I/O boundary')
            engine.hook_add(unicorn.UC_HOOK_INTR, external)
            engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_IN)
            engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_OUT)
            if observed:
                engine.hook_add(unicorn.UC_HOOK_CODE, code)
                engine.hook_add(unicorn.UC_HOOK_MEM_WRITE, memory, begin=0xa0000, end=0xaffff)
            try:
                engine.emu_start(cs * 16 + 0x7a13, cs * 16 + 0x7a57, count=3000000)
                registers = [engine.reg_read(register) for register in REGS]
                final = bytes(engine.mem_read(0, 1048576))
                assert registers[7] == cs and registers[12] == 0x7a57
                assert final[cs * 16:cs * 16 + 43552] == image[:43552]
                endpoints.append((registers, final))
            except Exception as error:
                (out / 'failed.json').write_text(json.dumps(dict(index=index, profile=[players, first, second],
                    observed=observed, error=str(error), calls=calls, writes=writes), indent=2) + '\n')
                raise
        assert endpoints[0] == endpoints[1]
        registers, final = endpoints[0]
        expected_calls = [(player, kind, returned) for player, state in enumerate((first, second)) if state
            for kind, returned in enumerate(((0x7a25, 0x7a2a, 0x7a35), (0x7a47, 0x7a4c, 0x7a57))[player])]
        assert calls == expected_calls
        expected_writes = [23712, 23712] if players == 1 and first else [0, 0] if players == 1 else [23104 if state else 0 for state in (first, second)]
        assert writes == expected_writes
        for player in range(players):
            if (first, second)[player] != 0:
                continue
            left, extent = (0, 320) if players == 1 else (player * 160, 160)
            for y in range(160):
                at = 0xa0000 + y * 320 + left
                assert final[at:at + extent] == initial[at:at + extent]
        output.extend(struct.pack('<3B13HI13HI3IB', players, first, second, *values, *registers,
                                  instructions[0], *writes, len(calls)))
        for call in calls:
            output.extend(struct.pack('<BBH', *call))
        output.extend(initial[0xa0000:0xa0000 + 64000])
        output.extend(final[0xa0000:0xa0000 + 64000])
        cases.append(dict(index=index, profile=[players, first, second], calls=calls, vga_write_bytes=writes,
            unicorn_steps=instructions[0], full_endpoint_flags=True, full_memory_control_identical=True,
            initial_vga_sha256=sha(initial[0xa0000:0xa0000 + 64000]), final_vga_sha256=sha(final[0xa0000:0xa0000 + 64000])))
        print(json.dumps(cases[-1]), flush=True)
    initialization = bytearray(b'LZVGIN01' + struct.pack('<I', 2))
    initialization_cases = []
    for players in (1, 2):
        initial = bytearray(ram)
        initial[data + 0x79b8] = players
        initial[data + 0x79e6:data + 0x79e8] = b'\0\0'
        struct.pack_into('<H', initial, data + 0x79ee, 40)
        initial[0xa0000:0xb0000] = b'\x4f' * 65536
        values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x3ffe,
                  cs, ds, 0x40, cs + mz[7], 0x3fe4, 0x2c7a, 0x202)
        endpoints = []
        for observed in (True, False):
            engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
            engine.mem_map(0, 1048576)
            engine.mem_write(0, bytes(initial))
            for register, value in zip(REGS, values):
                engine.reg_write(register, value)
            engine.hook_add(unicorn.UC_HOOK_INTR, external)
            engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_IN)
            engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_OUT)
            if observed:
                engine.hook_add(unicorn.UC_HOOK_CODE, lambda *unused: None)
            # Separate unchanged original callsites, not continuous intro execution.
            engine.emu_start(cs * 16 + 0x2c7a, cs * 16 + 0x2c89, count=3000000)
            assert engine.reg_read(UC_X86_REG_IP) == 0x2c89 and bytes(engine.mem_read(0xa0000, 64000)) == bytes(64000)
            engine.reg_write(UC_X86_REG_IP, 0x2cf6)
            engine.emu_start(cs * 16 + 0x2cf6, cs * 16 + 0x2cf9, count=3000000)
            registers = [engine.reg_read(register) for register in REGS]
            final = bytes(engine.mem_read(0, 1048576))
            assert registers[12] == 0x2cf9 and final[cs * 16:cs * 16 + 43552] == image[:43552]
            endpoints.append((registers, final))
        assert endpoints[0] == endpoints[1]
        registers, final = endpoints[0]
        pixels = final[0xa0000:0xa0000 + 64000]
        initialization.extend(bytes([players]) + pixels)
        initialization_cases.append(dict(players=players, width=320, state_bytes=[0, 0],
            blocks=[[0x2c7a, 0x2c89], [0x2cf6, 0x2cf9]], full_endpoint_flags=True,
            full_memory_control_identical=True, final_vga_sha256=sha(pixels)))
    compressed = gzip.compress(output, mtime=0)
    initialization_compressed = gzip.compress(initialization, mtime=0)
    record = dict(schema='lezac-original-render-view-gates-v1', cases=cases, producer_sha256=sha(Path(__file__).read_bytes()),
        origin_sha256=sha(Path(__file__).with_name('render_view_gate_origin.py').read_bytes()),
        source_capture_manifest_sha256=MANIFEST_SHA,
        original_executable_sha256=sha(exe), source_ram_sha256=sha(ram), source_recipe_sha256=sha(recipe_raw),
        source_sample='gameplay-middle', code_segment=cs, data_segment=ds, projection_sha256=sha(output),
        projection_bytes=len(output), compressed_sha256=sha(compressed), compressed_bytes=len(compressed),
        original_calls_stubbed=0, instruction_patches=0, source_code_bytes_verified=43552, raw_memory_published=False,
        raw_memory_available_to_frozen_checker=False, controlled_geometry=True, controlled_state_bytes=True,
        controlled_initial_vga=True, natural_gameplay_claim=False, whole_frame_parity=False, work_clock_claim=False,
        unicorn=unicorn.__version__)
    record.update(initialization_cases=initialization_cases, initialization_sha256=sha(initialization),
        initialization_bytes=len(initialization), initialization_compressed_sha256=sha(initialization_compressed),
        initialization_compressed_bytes=len(initialization_compressed))
    (out / 'oracle.bin').write_bytes(output)
    (out / 'oracle.bin.gz').write_bytes(compressed)
    (out / 'initialization.bin').write_bytes(initialization)
    (out / 'initialization.bin.gz').write_bytes(initialization_compressed)
    (out / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(cases=len(cases), bytes=len(output), compressed_bytes=len(compressed))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    generate(args.repo, args.capture, args.out)
