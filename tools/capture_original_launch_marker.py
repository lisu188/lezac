#!/usr/bin/env python3
"""Observe original launch-pad input, marker lifetime and indexed view pixels.

Player position and shared-pool occupancy are seeded once per case at actor
entry. Cached collision/gate values and the shipped map are never seeded.
"""

import argparse
import hashlib
import os
from pathlib import Path
import signal
import struct
import sys
import time

import capture_original_behavior4_lockstep as environment
from capture_original_bomb_fuses import jump
import capture_original_player_walk as player
import capture_original_render_boundary as render
import seed_original_level as seeder


ROOT = Path(__file__).resolve().parent.parent
HOOKS = ((0x6064, 4), (0x6813, 3), (0x6B55, 3), (0x7A57, 5), (0x6932, 3))
SCRATCH = 0xF700
WINDOWS = player.WINDOWS | render.WINDOWS | {
    0x68C5: bytes.fromhex("a0821b30e48bd0a0861b30e403c23d0200"),
    0x68E2: bytes.fromhex("803e861b017403e97201"),
    0x6912: bytes.fromhex("803e552027754e807ede007548"),
    0x691F: bytes.fromhex("c746f230f8c70674203500c6069f7905"),
    0x6945: bytes.fromhex("6a5b6a0b6a056a05e84fc6"),
    0x6950: bytes.fromhex("833e722001750d"),
    0x6932: bytes.fromhex("8b46d405040050"),
}
CASES = tuple((f"pool{count}_{phase}", 100 + parity, count, "down")
              for count in (0, 29, 30) for parity, phase in enumerate(("even", "odd"))) + (
    ("up_down", 100, 0, "jump_down"), ("idle", 101, 0, "idle"),
    ("fraction_even", 100, 0, "down"), ("fraction_odd", 101, 0, "down"))


def trampoline(stage, image):
    entry, length = HOOKS[stage - 1]
    at = 0xF400 + (stage - 1) * 0x80
    code = bytearray(b"\x9c\x60")
    skip = None
    if stage == 1:
        code += bytes.fromhex("26807d15007500")
        skip = len(code) - 1
    if stage == 5:
        # Save the accepted pair before the sound IRQ can advance its cursor
        # during the host-side stop. Preserve the original interrupt flag.
        code += bytes.fromhex("9cfaa1c0782ea312f7a09e792ea214f79d")
    for i, op in enumerate(("8cc8", "8cd8", "8cc0", "8cd0", "89e0", "89e8")):
        code += bytes.fromhex(op) + b"\x2e\xa3" + struct.pack("<H", SCRATCH + 2 + 2 * i)
    code += b"\x2e\xff\x06" + struct.pack("<H", SCRATCH + 16)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, stage)
    code += b"\x2e\x83\x3e" + struct.pack("<H", SCRATCH + 14) + bytes([stage]) + b"\x75\xf8"
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, 0)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH + 14, 0)
    if skip is not None:
        code[skip] = len(code) - skip - 1
    code += b"\x61\x9d" + image[entry:entry + length]
    code += jump(at + len(code), entry + length)
    if len(code) > 128:
        raise RuntimeError("trampoline overflow")
    return code


def capture(pid, base, output, image, level):
    cs, ds = base + (player.CS << 4), base + (seeder.RUNTIME_DS << 4)
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(at, n):
            data = os.pread(mem.fileno(), n, at)
            if len(data) != n:
                raise RuntimeError("short launch memory read")
            return data

        def write(at, data):
            if os.pwrite(mem.fileno(), data, at) != len(data):
                raise RuntimeError("short launch memory write")

        def word(at):
            return struct.unpack("<H", read(at, 2))[0]

        def release(stage):
            write(cs + SCRATCH + 14, struct.pack("<H", stage))

        sequence = 0

        sound_snapshot = None

        def wait(stage, initial=False, sound=False):
            nonlocal sequence, sound_snapshot
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack("<9H", read(cs + SCRATCH, 18))
                if marker and not flag and current > sequence:
                    sequence = current
                    if marker == stage:
                        if regs[1] - regs[0] != 0xAA2:
                            raise RuntimeError("unexpected original segments")
                        return regs
                    if marker == 5 and sound:
                        sound_snapshot = read(cs + SCRATCH + 18, 3)
                        release(5)
                    elif initial:
                        release(marker)
                    else:
                        raise RuntimeError(f"stage {marker}, wanted {stage}")
                time.sleep(0.001)
            raise RuntimeError(f"launch stage {stage} timeout")

        def caller_at(regs):
            return cs - (regs[0] << 4) + (regs[3] << 4) + regs[5]

        def actor_at(regs):
            offset, segment = struct.unpack("<HH", read(caller_at(regs) + 4, 4))
            return cs - (regs[0] << 4) + (segment << 4) + offset

        for at, expected in WINDOWS.items():
            if read(cs + at, len(expected)) != expected:
                raise RuntimeError(f"runtime bytes at {at:04x}")
        if read(cs + 0xF400, 0x315) != bytes(0x315):
            raise RuntimeError("scratch not empty")
        os.kill(pid, signal.SIGSTOP)
        try:
            deadline = time.monotonic() + 2
            while "State:\tT" not in Path(f"/proc/{pid}/status").read_text():
                if time.monotonic() > deadline:
                    raise RuntimeError("stop timeout")
                time.sleep(0.001)
            for stage, (entry, _) in enumerate(HOOKS, 1):
                target = 0xF400 + (stage - 1) * 0x80
                write(cs + target, trampoline(stage, image))
                write(cs + entry, jump(entry, target))
        finally:
            os.kill(pid, signal.SIGCONT)
        regs = wait(1, initial=True)
        memory_base = cs - (regs[0] << 4)
        width, height = word(ds + 0xC204), word(ds + 0x2096) // 8 + 21
        if (width, height) != {6: (180, 64), 7: (140, 52)}[level] or word(ds + 0xC1EC) != 320:
            raise RuntimeError("unexpected launch level/view dimensions")
        objects = memory_base + (word(ds + 0xC1FE) << 4)
        tiles = read(objects, width * height)
        pads = [i for i, value in enumerate(tiles) if value == 0x27]
        if not pads:
            raise RuntimeError("no original launch pad")
        pad_x, pad_y = pads[0] % width, pads[0] // width
        x, y = pad_x * 8, pad_y * 8 - 16
        descriptors = read(ds + 0xC322, 368)
        background = read(memory_base + (word(ds + 0xC49A) << 4) + word(ds + 0xC498), 60000)
        original_player = read(actor_at(regs), 38)
        rows = ["# Seeded player position and pool; original cached gates/map and continuous marker updates.",
                "# executable_sha256=" + hashlib.sha256((ROOT / "LEZAC.EXE").read_bytes()).hexdigest(),
                f"capture=launch_marker_original_v1 level={level} temp_copy=1 seeded_position=1 seeded_pool=1 cached_gate_seed=0 observed_backdrop=1 natural_route=0",
                f"map width={width} height={height} bytes={tiles.hex()}",
                f"backdrop bytes={render.rle(background)}",
                f"sprites descriptors={descriptors.hex()}"]

        def state():
            count = read(ds + 0x208D, 1)[0]
            values = []
            if count > 30:
                raise RuntimeError("original actor overflow")
            for slot in range(1, count + 1):
                raw = read(ds + 0x1BAE + slot * 38, 38)
                visual = read(ds + 0xC21E + raw[1] * 8, 8)
                values.append(raw.hex() + ":" + visual.hex())
            return (f"count={count} visuals={read(ds + 0xC496, 1)[0]} result={word(ds + 0x2072)}"
                    f" player={read(ds + 0xC21E, 8).hex()} actors={','.join(values) or '-'}")

        for name, frame, count, control in CASES:
            write(ds + 0x78C2, struct.pack("<H", frame))
            write(ds + 0x79E6, b"\x01\x00")
            write(ds + 0x79EA, b"\x63\x63\x64\x64")
            write(ds + 0x79A6, bytes(1))
            write(ds + 0x208D, bytes([count]))
            write(ds + 0xC496, bytes([count + 2]))
            write(ds + 0x208E, bytes(1))
            write(ds + 0x2072, bytes(2))
            write(ds + 0x799E, bytes(2))
            write(ds + 0x78C0, bytes(2))
            write(ds + 0x2098, bytes(6))
            write(ds + 0xC49C, b"\x01")
            raw = bytearray(original_player)
            raw[6:14] = bytes(8)
            raw[14:16] = bytes(2)
            if name.startswith("fraction_"):
                raw[10], raw[12] = 83, 149
            raw[0x16:0x1D] = bytes([1, 1, 4, 0, 0, 0, 1])
            write(actor_at(regs), raw)
            write(ds + 0xC21E, struct.pack("<HH", x, y) + descriptors[4:8])
            write(ds + 0xC226, b"\xff\xff\xff\xff" + bytes(4))
            for slot in range(1, count + 1):
                filler = bytearray(38)
                filler[1], filler[2], filler[0x15] = slot + 1, 240, 5
                write(ds + 0x1BAE + slot * 38, filler)
                write(ds + 0xC21E + (slot + 1) * 8, struct.pack("<HH", 8, 8) + descriptors[320:324])
            rows.append(f"case name={name} frame={frame} initial_count={count} control={control} pad_x={pad_x} pad_y={pad_y} x={x} y={y} entry={bytes(raw).hex()}")
            for sample in range(12):
                entry = read(actor_at(regs), 38)
                release(1)
                before = wait(2)
                caller = caller_at(before)
                pre = read(caller - 0x3A, 0x3A)
                edges = read(ds + 0x2048, 16)
                write(ds + 0x1B82, bytes(player.CONTROLS[control if sample == 0 else "idle"]))
                sound_snapshot = None
                release(2)
                after = wait(3, sound=True)
                response = read(caller_at(after) - 0x3A, 0x3A)
                rows.append(f"tick sample={sample} frame={word(ds + 0x78C2)} entry={entry.hex()} pre={pre.hex()} response={response.hex()} edges={edges.hex()}"
                            f" sound_snapshot={sound_snapshot.hex() if sound_snapshot else '-'} accepted_sound={read(ds + 0x78C0, 2).hex()} priority={read(ds + 0x799E, 1)[0]} normalized={read(ds + 0x1B82, 5).hex()}"
                            f" before_regs={struct.pack('<6H', *before).hex()} after_regs={struct.pack('<6H', *after).hex()} " + state())
                if sample == 0:
                    print(f"launch_original level={level} case={name} " + rows[-1].split(" accepted_sound=")[1].split(" before_regs=")[0], flush=True)
                release(3)
                view = wait(4)
                values = {key: word(ds + at) for key, at in (("coarse_x", 0xC216), ("coarse_y", 0xC218), ("fine_x", 0xC20A),
                          ("fine_y", 0xC20C), ("source", 0xC214), ("destination", 0xC1F4))}
                source = values["source"] + values["fine_x"] + values["fine_y"] * 320
                buffer = memory_base + (word(ds + 0xC212) << 4)
                pixels = b"".join(read(buffer + source + row * 320, 312) for row in range(152))
                if read(objects, len(tiles)) != tiles:
                    raise RuntimeError("launch changed original map")
                rows.append(f"view sample={sample} frame={word(ds + 0x78C2)} regs={struct.pack('<6H', *view).hex()} " + state()
                            + "".join(f" {key}={value}" for key, value in values.items())
                            + f" indexed_sha256={hashlib.sha256(pixels).hexdigest()} pixels={render.rle(pixels)}")
                if sample in (0, 1, 4, 8, 10):
                    render.write_preview(output.with_name(f"{output.stem}_{name}_{sample:03d}.ppm"), pixels, 312, 152, (ROOT / "BOMPAL.PAL").read_bytes())
                release(4)
                regs = wait(1)
            rows.append("end samples=12")
            output.write_text("\n".join(rows) + "\n", encoding="ascii")
        rows.append(f"complete cases={len(CASES)} samples={len(CASES) * 12} views={len(CASES) * 12}")
        output.write_text("\n".join(rows) + "\n", encoding="ascii")
        for at, length in HOOKS:
            write(cs + at, image[at:at + length])
        release(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--level", type=int, choices=(6, 7), default=6)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    exe = (ROOT / "LEZAC.EXE").read_bytes()
    image = exe[0x770:]
    for at, expected in WINDOWS.items():
        if image[at:at + len(expected)] != expected:
            raise RuntimeError(f"static bytes at {at:04x}")
    for stage in range(1, len(HOOKS) + 1):
        trampoline(stage, image)
    print(f"launch_marker_capture_self_check=ok windows={len(WINDOWS)} cases={len(CASES)} live=0", flush=True)
    if args.self_check:
        return 0
    if not (args.run_dir and args.out and args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("live capture requires temporary run-dir, out and both approval flags")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    if (args.run_dir / "LEZAC.EXE").read_bytes() != exe:
        parser.error("temporary executable differs from original")
    if args.out.exists() or list(args.out.parent.glob(args.out.stem + "_*")):
        parser.error("output exists; choose a fresh path")
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_LAUNCH_MARKER_INSIDE_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(pid, base, args.out, image, args.level)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", str(args.level), "--start-key", "1",
                "--startup-seconds", "10", "--intro-seconds", "8", "--level-start-seconds", "5",
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
