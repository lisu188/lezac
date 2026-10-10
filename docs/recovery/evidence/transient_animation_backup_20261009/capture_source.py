"""Observe original corpse conversions without patching original instructions."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from types import ModuleType

CAP = 8 * 1024 * 1024


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bound_module(path, expected=None):
    raw = path.read_bytes()
    if expected is not None:
        assert sha(raw.replace(b"\r\n", b"\n")) == expected
    module = ModuleType(path.stem)
    module.__file__ = str(path)
    module.__package__ = ""
    module.__source_sha256__ = sha(raw)
    exec(compile(raw, str(path), "exec", dont_inherit=True), vars(module))
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not sys.flags.optimize and os.environ["SDL_AUDIODRIVER"] == "dummy"
    out = args.out.resolve()
    assert not out.exists() and out.parent == Path("/tmp")
    out.mkdir()
    oracle = Path("/dev/shm/lezac-oracle-current-main-20261008-t69")
    native_root = Path("/dev/shm/lezac-shared-crosscheck-main-20261009-t75")
    sys.path.insert(0, "/dev/shm/lezac-sound-machinecode-deps-20261008-t24")
    helper = bound_module(oracle / "tools/original_bomb_cpu.py",
        "fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c")
    reader = bound_module(native_root / "tools/check_original_shared_actor_native.py")
    native = reader.read_native(native_root)
    case = next(c for c in native["cases"] if c["seed"]["name"] == "corpse_front_full")
    import unicorn
    from unicorn import x86_const as registers
    tracked = [getattr(registers, "UC_X86_REG_" + name) for name in
               ("AX", "BX", "CX", "DX", "SI", "DI", "BP", "SP", "CS", "DS", "ES", "SS", "IP", "EFLAGS")]
    observed, neutral = helper.BombCPU(oracle), helper.BombCPU(oracle)
    assert observed.descriptors == native["descriptors"]
    actor_address = observed.DATA + 0x1bae + 38
    events = []
    enabled = False

    def observe_write(cpu, access, address, size, value, unused):
        if enabled and address < actor_address + 38 and address + size > actor_address:
            assert actor_address <= address and address + size <= actor_address + 38
            assert len(events) < 2000
            events.append(dict(cs=f'{cpu.reg_read(registers.UC_X86_REG_CS):04x}',
                ip=f'{cpu.reg_read(registers.UC_X86_REG_IP):04x}', physical_address=f'{address:05x}',
                offset=address - actor_address, bytes=size,
                before=bytes(cpu.mem_read(address, size)).hex(),
                after=(value & ((1 << (size * 8)) - 1)).to_bytes(size, "little").hex()))

    observed.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, observe_write)

    def seed(executor, actors, rng):
        cpu, data = executor.cpu, executor.DATA
        cpu.context_restore(executor.initial_context)
        cpu.mem_write(0, executor.initial_memory)
        cpu.mem_write(data + 0x1bae, bytes(31 * 38))
        cpu.mem_write(data + 0xc21e, bytes(33 * 8))
        cpu.mem_write(data + 0xc322, native["descriptors"])
        for offset, value in ((0xc1e0, struct.pack("<HH", 0, 0x4000)),
                (0xc1fe, struct.pack("<H", 0x4000)), (0xc204, struct.pack("<HH", 60, 33)),
                (0x206e, struct.pack("<H", 0x5000)), (0x6612, struct.pack("<HH", 0, 0x5000)),
                (0x78c4, struct.pack("<H", 0x4000))):
            cpu.mem_write(data + offset, value)
        executor.registers(0xf000, 0xff00)
        cpu.emu_start(0x1293d, 0x12949, count=4)
        executor.assert_return(0x2949, 0xf000, 0xff00)
        assert bytes(cpu.mem_read(data + 0x207a, 4)) == struct.pack("<HH", 0x6620, 0x209e)
        cpu.emu_start(0x12852, 0x12858, count=2)
        executor.assert_return(0x2858, 0xf000, 0xff00)
        assert bytes(cpu.mem_read(data + 0xc1fc, 2)) == struct.pack("<H", 0xc21e)
        cpu.mem_write(0x40000, native["map"])
        cpu.mem_write(0x50000, native["words"])
        for offset, value in ((0x79a6, bytes(1)), (0x79ea, b"\x63\x63\x64\x64"),
                (0x79e6, b"\x01\x00"), (0x2080, bytes(2)), (0x207e, struct.pack("<H", 199)),
                (0x2076, bytes(2)), (0x208e, bytes(1)), (0x79f9, bytes(1)),
                (0x1afe, struct.pack("<I", rng)), (0x78c2, struct.pack("<H", 101)),
                (0xc21e, struct.pack("<HH", 240, 168)), (0x208d, bytes((len(actors),))),
                (0xc496, bytes((len(actors) + 2,)))):
            cpu.mem_write(data + offset, value)
        for slot, (raw, visual) in enumerate(actors, 1):
            cpu.mem_write(data + 0x1bae + slot * 38, raw)
            cpu.mem_write(data + 0xc21e + raw[1] * 8, visual)

    marker = bytes((43, 43, 46, 2, 2, 2, 255))
    seeds = [dict(name="native_control", actors=case["actors"], rng=0x12345678, samples=4)]
    for pool in (1, 30):
        for mode in (0, 3):
            for rng in (0, 0x12345678):
                actors = list(case["actors"][:pool])
                raw = bytearray(actors[0][0])
                assert raw[0] == 12 and raw[21] == 2
                raw[29:36] = marker
                if mode == 3:
                    raw[22:29] = bytes((9, 6, 9, 0, 0, 3, 1))
                else:
                    assert raw[27] == 0
                actors[0] = (bytes(raw), actors[0][1])
                seeds.append(dict(name=f"pool{pool}_mode{mode}_rng{rng:08x}", actors=actors,
                                  rng=rng, samples=6))
    actors = list(case["actors"][:1])
    raw = bytearray(actors[0][0])
    raw[2], raw[22:29], raw[29:36] = 3, bytes((9, 6, 9, 0, 0, 3, 1)), marker
    actors[0] = (bytes(raw), actors[0][1])
    seeds.append(dict(name="delayed_mode3", actors=actors, rng=0x12345678, samples=8))
    templates = dict(
        reward=next(pair for c in native["cases"] for pair in c["actors"] if 19 <= pair[0][0] <= 25),
        bomb=next(pair for c in native["cases"] for pair in c["actors"] if 13 <= pair[0][0] <= 16),
        effect=next(pair for c in native["cases"] for pair in c["actors"] if pair[0][21] == 5))
    for operation in ("reward_expiry", "reward_pickup", "bomb_expiry", "effect_animation"):
        template = templates["reward" if operation.startswith("reward_") else
                             "bomb" if operation == "bomb_expiry" else "effect"]
        for mode in (0, 3):
            raw, visual = bytearray(template[0]), bytearray(template[1])
            raw[1], raw[2], raw[29:36] = 2, (0 if operation.endswith("expiry") else 64), marker
            raw[22:29] = bytes((9, 6, 9, 0, 0, mode, 1))
            if operation == "reward_pickup":
                visual[0:4] = struct.pack("<HH", 240, 168)
            seeds.append(dict(name=f"{operation}_mode{mode}", actors=[(bytes(raw), bytes(visual))],
                              rng=0x12345678, samples=6))
    report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(),
        producer_sha256=__source_sha256__, helper_sha256=helper.__source_sha256__,
        native_reader_sha256=reader.__source_sha256__, native_fixture_sha256=native["sha256"],
        original_exe_sha256=sha(observed.raw), original_instructions_patched=False,
        original_calls_stubbed=False, hardware_io_permitted=False, audio="dummy",
        seeded=True, natural_route_claim=False, rendered_pixels_claim=False,
        compiled_cpp_comparison=False, whole_game_complete=False,
        observed_range="CS:7ebb..7eea", post_pass_range="CS:804e..806a",
        observer_neutrality_memory_bytes=1024**2, observer_neutrality_registers=14,
        cases=[], actor_passes=0, tagged_backup=marker.hex())
    try:
        for item in seeds:
            enabled = False
            for executor in (observed, neutral):
                seed(executor, item["actors"], item["rng"])
            row = dict(name=item["name"], initial_count=len(item["actors"]),
                rng=f'{item["rng"]:08x}', initial_actor=item["actors"][0][0].hex(),
                initial_visual=item["actors"][0][1].hex(),
                initial_actors=[dict(actor=raw.hex(), visual=visual.hex()) for raw, visual in item["actors"]],
                ticks=[])
            report["cases"].append(row)
            for sample in range(item["samples"]):
                report["active_case"], report["active_sample"] = item["name"], sample
                events.clear()
                for executor in (observed, neutral):
                    executor.cpu.mem_write(executor.DATA + 0x78c2, struct.pack("<H", 101 + sample))
                    executor.registers(0xf000, 0xff00)
                    executor.instructions = 0
                    enabled = executor is observed
                    executor.cpu.emu_start(0x17ebb, 0x17eea, count=2000000)
                    enabled = False
                    executor.assert_return(0x7eea, 0xf000, 0xff00)
                memory = bytes(observed.cpu.mem_read(0, 1024**2))
                assert memory == bytes(neutral.cpu.mem_read(0, 1024**2))
                actual_regs = [observed.cpu.reg_read(reg) for reg in tracked]
                assert actual_regs == [neutral.cpu.reg_read(reg) for reg in tracked]
                data, cpu = observed.DATA, observed.cpu
                raw = bytes(cpu.mem_read(actor_address, 38))
                visual = bytes(cpu.mem_read(data + 0xc21e + raw[1] * 8, 8))
                count = cpu.mem_read(data + 0x208d, 1)[0]
                if item["name"] == "native_control":
                    expected = case["ticks"][sample]
                    assert count == int(expected["count"])
                    assert bytes(cpu.mem_read(data + 0x1afe, 4)) == bytes.fromhex(expected["rng"])
                    for slot, (expected_actor, expected_visual) in enumerate(expected["entries"], 1):
                        captured = bytes(cpu.mem_read(data + 0x1bae + slot * 38, 38))
                        assert captured == expected_actor
                        assert bytes(cpu.mem_read(data + 0xc21e + captured[1] * 8, 8)) == expected_visual
                row["ticks"].append(dict(sample=sample, frame=101 + sample, actor=raw.hex(),
                    visual=visual.hex(), count=count, visual_count=cpu.mem_read(data + 0xc496, 1)[0],
                    rng=bytes(cpu.mem_read(data + 0x1afe, 4)).hex(),
                    registers=actual_regs, memory_sha256=sha(memory),
                    instructions=observed.instructions, writes=list(events)))
                report["actor_passes"] += 1
                for executor in (observed, neutral):
                    executor.registers(0xf000, 0xff00)
                    executor.cpu.emu_start(0x1804e, 0x1806a, count=2000000)
                    executor.assert_return(0x806a, 0xf000, 0xff00)
                assert bytes(observed.cpu.mem_read(0, 1024**2)) == bytes(neutral.cpu.mem_read(0, 1024**2))
                assert [observed.cpu.reg_read(reg) for reg in tracked] == [neutral.cpu.reg_read(reg) for reg in tracked]
        report.update(passed=True, case_count=len(seeds), native_control_passes=4,
                      observed_and_neutral_passes=2 * report["actor_passes"])
    except BaseException as error:
        report["error"] = repr(error)
        raise
    finally:
        raw_report = (json.dumps(report, indent=2) + "\n").encode()
        assert len(raw_report) < 1024 * 1024
        (out / "original-conversion-backup-v1.json").write_bytes(raw_report)
        assert sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) <= CAP
    print(json.dumps(dict(path=str(out / "original-conversion-backup-v1.json"),
                         sha256=sha(raw_report), cases=len(seeds), passes=report["actor_passes"],
                         passed=report["passed"], first_states=[dict(name=row["name"],
                         initial=row["initial_actor"], after=row["ticks"][0]["actor"])
                         for row in report["cases"]])), flush=True)


if __name__ == "__main__":
    path = Path(__file__).resolve()
    raw = path.read_bytes()
    namespace = dict(__file__=str(path), __name__="bound_conversion_backup_capture", __source_sha256__=sha(raw))
    exec(compile(raw, str(path), "exec", dont_inherit=True), namespace)
    namespace["main"]()
