#!/usr/bin/env python3
"""Record physical fire-key IRQs across natural level-1 death and reentry.

The main-loop hook writes a bounded ring without waiting for the observer.
Only guarded code and unused recorder memory are written; gameplay state and
input bytes are never seeded. Every child runs silently on private Xvfb.
"""

import argparse
from contextlib import ExitStack, contextmanager
import hashlib
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import time

import capture_original_behavior4_lockstep as environment
import capture_original_render_boundary as render
import seed_original_level as seeder
from level1_original import far_call, resident_program, RESIDENT_MARKER, RESIDENT_PARAGRAPHS

ROOT = Path(__file__).resolve().parent.parent
EXE_SHA256 = "7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec"
CS, COUNTERS, RING, STRIDE, SLOTS = 0x01ED, 0x7F0, 0x800, 128, 16
HOOKS = ((0x10A1, 6, 0x200), (0x7A57, 5, 0x300))
WINDOWS = {0x10A1: bytes.fromhex("e460b4013c2c"),
           0x10BD: bytes.fromhex("3c31750488267b1b"),
           0x110F: bytes.fromhex("3cb1750488267b1b"),
           0x7A57: bytes.fromhex("c606e87900")}


def irq_stub(image):
    entry, length, _ = HOOKS[0]
    # The far CALL occupies five of six displaced bytes. Return past all six,
    # including when restoration replaces the padding while this stub runs.
    code = bytearray.fromhex("5589e536c74602")
    code += struct.pack("<H", entry + length) + b"\x5d"
    code += image[entry:entry + 4] + b"\x9c"
    for key, address in ((0x31, COUNTERS + 2), (0xB1, COUNTERS + 4)):
        code += bytes((0x3C, key, 0x75, 5)) + b"\x2e\xff\x06" + struct.pack("<H", address)
    return bytes(code + b"\x9d" + image[entry + 4:entry + length] + b"\xcb")


def frame_stub(image):
    entry, length, target = HOOKS[1]
    # Preserve flags/registers/ES and briefly mask IRQs for a coherent record.
    code = bytearray.fromhex("9cfa6006fc8cc88ec0")
    code += b"\x2e\xa1" + struct.pack("<H", COUNTERS)
    code += bytes.fromhex("405048250f00c1e007") + b"\x05" + struct.pack("<H", RING)
    code += bytes.fromhex("89c726c705000089fb83c702")
    # Caller CS/DS/ES/SS/SP/BP; the stack also holds the far return address.
    code += bytes.fromhex("89e6368b4418ab8cd8ab368b4402ab8cd0ab89e083c01aab89e8ab")
    for address, count in ((0x78C2, 2), (0x1B78, 10), (0x1B6C, 8), (0x1B74, 2),
                           (0x1B88, 38), (0xC21E, 8), (0x79E5, 9),
                           (0x79CA, 1), (0x79B9, 1), (0x208D, 1)):
        code += b"\xbe" + struct.pack("<H", address) + b"\xb9" + struct.pack("<H", count) + b"\xf3\xa4"
    for address in (COUNTERS + 2, COUNTERS + 4):
        code += b"\x2e\xa1" + struct.pack("<H", address) + b"\xab"
    code += bytes.fromhex("a0b779aa")
    code += bytes.fromhex("58268907") + b"\x2e\xa3" + struct.pack("<H", COUNTERS)
    code += bytes.fromhex("07619d") + image[entry:entry + length] + b"\xcb"
    if target + len(code) > COUNTERS:
        raise RuntimeError("frame recorder overlaps counters")
    return bytes(code)


@contextmanager
def runtime_hooks(read, write, stop, resume, cs, recorder, segment, image):
    """Restore every attempted patch, including a partially written CALL."""
    attempted, restored = [], []
    try:
        try:
            stop()
            for at, expected in WINDOWS.items():
                if read(cs + at, len(expected)) != expected:
                    raise RuntimeError(f"runtime guard {at:04x}")
            if read(recorder + 0x200, 0xE00) != bytes(0xE00):
                raise RuntimeError("recorder arena is occupied")
            for index, (entry, length, target) in enumerate(HOOKS):
                stub = irq_stub(image) if index == 0 else frame_stub(image)
                write(recorder + target, stub)
                if read(recorder + target, len(stub)) != stub:
                    raise RuntimeError("recorder stub verification failed")
                patch = far_call(target, segment) + bytes([0x90]) * (length - 5)
                attempted.append((entry, length))
                write(cs + entry, patch)
                if read(cs + entry, length) != patch:
                    raise RuntimeError("recorder hook verification failed")
        finally:
            resume()
        yield restored
    finally:
        if attempted:
            errors = []
            try:
                stop()
                for entry, length in attempted:
                    original = image[entry:entry + length]
                    try:
                        write(cs + entry, original)
                        if read(cs + entry, length) != original:
                            raise RuntimeError(f"original hook restoration failed at {entry:04x}")
                        restored.append(f"restored hook={entry:04x} bytes={original.hex()}")
                    except Exception as error:
                        errors.append(error)
            finally:
                resume()
            if errors:
                raise RuntimeError("hook cleanup failed: " + "; ".join(map(str, errors))) from errors[0]


def read_record(read, recorder, sequence, total):
    if total <= sequence or total - sequence > SLOTS:
        raise RuntimeError(f"recorder overrun: observed={sequence} recorded={total}")
    wanted = sequence + 1
    address = recorder + RING + ((wanted - 1) % SLOTS) * STRIDE
    raw = read(address, STRIDE)
    if len(raw) != STRIDE or int.from_bytes(raw[:2], "little") != wanted or read(address, 2) != raw[:2]:
        raise RuntimeError("ring record changed during read")
    return raw


def validate_lifecycle(samples, events, mode):
    """Require one natural death/reentry, observed IRQs, and no restart."""
    if not samples or len(samples) > 1800:
        raise RuntimeError("invalid sample count")
    dying = waiting = resumed = None
    first_frame = samples[0]["frame"]
    first_regs = samples[0]["regs"]
    previous_makes = previous_breaks = 0
    previous_fallback = 0
    for seq, row in enumerate(samples, 1):
        p1, flags = row["p1"], row["flags"]
        if row["seq"] != seq or row["frame"] != (first_frame + seq - 1) % 65536:
            raise RuntimeError("nonconsecutive original samples")
        if row["regs"] != first_regs or len(first_regs) != 12:
            raise RuntimeError("inconsistent original registers")
        cs, ds, es, _, _, _ = struct.unpack("<6H", row["regs"])
        if ds - cs != 0xAA2 or es != 0xA000:
            raise RuntimeError("unexpected original segments")
        if len(p1) != 38 or len(flags) != 9 or len(row["hardware"]) != 10:
            raise RuntimeError("invalid original row size")
        if row["level"] != 1 or row["gate"] != 1 or flags[1] not in (1, 2) or flags[2] != 0:
            raise RuntimeError("capture left natural single-player level one")
        if not (previous_makes <= row["makes"] <= 65535 and previous_breaks <= row["breaks"] <= 65535):
            raise RuntimeError("IRQ counters regressed")
        previous_makes, previous_breaks = row["makes"], row["breaks"]
        if p1[21] == 2 and dying is None:
            dying = seq
        if flags[1] == 2 and waiting is None:
            waiting = seq
        if dying is not None and p1[21] == 0 and resumed is None:
            resumed = seq
        expected_behavior = 2 if dying is not None and resumed is None else 0
        if p1[21] != expected_behavior:
            raise RuntimeError("multiple or invalid death transitions")
        expected_fallback = previous_fallback + 1 if flags[1] == 2 else 0
        if row["fallback"] != expected_fallback or row["fallback"] >= 230:
            raise RuntimeError("fallback restart or inconsistent waiting counter")
        previous_fallback = row["fallback"]
        expected_lives = 1 if (waiting is not None or resumed is not None) else 2
        if flags[5] != expected_lives:
            raise RuntimeError("unexpected reserve-life transition")
    if dying is None or resumed is None or len(samples) < resumed + 24:
        raise RuntimeError("incomplete natural lifecycle")
    if (waiting or resumed) - dying != 60:
        raise RuntimeError("death countdown does not span 60 updates")
    expected = [("keydown", "start"), ("keyup", "resumed")]
    if mode == "release_repress":
        expected = [("keydown", "start"), ("keyup", "death"), ("keydown", "waiting"), ("keyup", "resumed")]
        if waiting is None or resumed <= waiting + 10:
            raise RuntimeError("missing released waiting interval")
    elif mode != "hold_through" or waiting is not None:
        raise RuntimeError("held fire did not reenter at countdown expiry")
    if [(e["kind"], e["reason"]) for e in events] != expected:
        raise RuntimeError("unexpected physical input sequence")
    last_ack = 0
    for event in events:
        after, ack = event["after_seq"], event["ack_seq"]
        if not (max(1, last_ack) <= after < ack <= len(samples)) or ack - after > 20:
            raise RuntimeError("missing or late input acknowledgement")
        before, observed = samples[after - 1], samples[ack - 1]
        counter = "makes" if event["kind"] == "keydown" else "breaks"
        if observed[counter] <= before[counter]:
            raise RuntimeError("input command has no observed IRQ")
        if event["kind"] == "keyup" and observed["hardware"][3] != 0:
            raise RuntimeError("released fire key remained set")
        if event["reason"] == "death" and not (dying <= after < ack < waiting):
            raise RuntimeError("death key release outside dying interval")
        if event["reason"] == "waiting" and not (after >= waiting + 10 and ack <= resumed):
            raise RuntimeError("reentry lacks an observed new make IRQ")
        if event["reason"] == "resumed" and after < resumed + 4:
            raise RuntimeError("final release precedes resumed gameplay")
        last_ack = ack
    if events[0]["after_seq"] < 4 or samples[dying - 1]["makes"] < 2:
        raise RuntimeError("missing initial idle interval or physical repeats")
    if mode == "hold_through" and samples[resumed - 1]["makes"] <= samples[dying - 1]["makes"]:
        raise RuntimeError("held fire has no repeat IRQs during death")
    if mode == "release_repress":
        release, press = events[1], events[2]
        baseline = samples[release["ack_seq"] - 1]["makes"]
        for row in samples[release["ack_seq"] - 1:press["after_seq"]]:
            if row["hardware"][3] != 0 or row["makes"] != baseline:
                raise RuntimeError("fire remained active during released waiting interval")
    if samples[0]["makes"] or samples[0]["breaks"] or samples[-1]["breaks"] != len(events) // 2:
        raise RuntimeError("unexpected extra release IRQs")
    if samples[-1]["hardware"][3] != 0:
        raise RuntimeError("fire key still held at completion")
    return dict(samples=len(samples), dying_seq=dying, waiting_seq=waiting or 0,
                resumed_seq=resumed, makes=previous_makes, breaks=previous_breaks)


def observe(pid, base, run_dir, output, image, mode):
    cs, ds = base + (CS << 4), base + (seeder.RUNTIME_DS << 4)
    palette = (ROOT / "BOMPAL.PAL").read_bytes()
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(at, count):
            value = os.pread(mem.fileno(), count, at)
            if len(value) != count:
                raise RuntimeError("short held-fire read")
            return value

        def write(at, value):
            if os.pwrite(mem.fileno(), value, at) != len(value):
                raise RuntimeError("short held-fire write")

        def stop():
            os.kill(pid, signal.SIGSTOP)
            deadline = time.monotonic() + 2
            while "State:\tT" not in Path(f"/proc/{pid}/status").read_text():
                if time.monotonic() > deadline:
                    raise RuntimeError("owned DOSBox stop timeout")
                time.sleep(0.001)

        residents = []
        for marker in seeder.scan_process(pid, RESIDENT_MARKER):
            at = marker - 0x120
            segment = int.from_bytes(read(at + 0x160, 2), "little")
            mcb = read(at - 16, 16)
            if (mcb[0] in (ord("M"), ord("Z")) and int.from_bytes(mcb[1:3], "little") == segment and
                    int.from_bytes(mcb[3:5], "little") >= RESIDENT_PARAGRAPHS):
                residents.append((at, segment, mcb))
        if len(residents) != 1:
            raise RuntimeError("resident recorder allocation is ambiguous")
        recorder, segment, mcb = residents[0]
        if cs < recorder + RESIDENT_PARAGRAPHS * 16:
            raise RuntimeError("recorder overlaps original executable")
        lines = [f"capture schema=held_fire_irq_v3 mode={mode} level=1 physical_keys=1 gameplay_seeded=0 main_loop_wait=0"
                 f" irq_masked_during_record=1 exe_sha256={EXE_SHA256} hooks=10a1,7a57 slots={SLOTS} stride={STRIDE}"
                 f" resident={segment:04x} mcb={mcb.hex()} source_sha256={hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}"
                 f" irq_sha256={hashlib.sha256(irq_stub(image)).hexdigest()} frame_sha256={hashlib.sha256(frame_stub(image)).hexdigest()}"
                 f" dosbox_sha256={hashlib.sha256(Path(f'/proc/{pid}/exe').read_bytes()).hexdigest()}"]
        sequence, dead, waiting, resumed, released = 0, None, None, None, None
        first_frame = None
        made, repress = False, False
        final_release = False
        pending = None
        samples, events, restored = [], [], []
        stack = ExitStack()
        written, flushed_sequence = 0, 0

        def flush():
            nonlocal written, flushed_sequence
            if written < len(lines):
                with output.open("a", encoding="ascii") as stream:
                    stream.write("\n".join(lines[written:]) + "\n")
                written = len(lines)
                flushed_sequence = sequence

        def key(kind, reason):
            nonlocal pending
            subprocess.run(["xdotool", kind, "n"], check=True, timeout=5)
            pending = dict(after_seq=sequence, kind=kind, reason=reason, ack_seq=0)
            events.append(pending)
            lines.append(f"event after_seq={sequence} kind={kind} key=n reason={reason}")
            print(lines[-1], flush=True)

        def screenshot(label):
            def word(at):
                return int.from_bytes(read(ds + at, 2), "little")

            # Read the latest original view without injecting a screenshot hotkey.
            memory_base = cs - (regs[0] << 4)
            source = word(0xC214) + word(0xC20A) + word(0xC20C) * 320
            buffer = memory_base + (word(0xC212) << 4)
            pixels = b"".join(read(buffer + source + row * 320, 312) for row in range(152))
            if len(set(pixels)) < 2:
                raise RuntimeError("uniform original view")
            render.write_preview(output.with_name(output.stem + "_" + label + ".ppm"), pixels, 312, 152, palette)
            lines.append(f"screenshot after_seq={sequence} label={label} frame_alignment=0 normalized_palette=1"
                         f" indexed_sha256={hashlib.sha256(pixels).hexdigest()}")

        try:
            restored = stack.enter_context(runtime_hooks(
                read, write, stop, lambda: os.kill(pid, signal.SIGCONT), cs, recorder, segment, image))
            window = subprocess.check_output(["xdotool", "search", "--pid", str(pid), "--name", "DOSBox"],
                                             text=True, timeout=5).split()[-1]
            subprocess.run(["xdotool", "windowfocus", "--sync", window], check=True, timeout=5)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and sequence < 1800:
                total = int.from_bytes(read(recorder + COUNTERS, 2), "little")
                if total < sequence or total - sequence > SLOTS:
                    raise RuntimeError(f"recorder overrun: observed={sequence} recorded={total}")
                while sequence < total:
                    wanted = sequence + 1
                    raw = read_record(read, recorder, sequence, total)
                    sequence = wanted
                    regs = struct.unpack_from("<6H", raw, 2)
                    frame, = struct.unpack_from("<H", raw, 14)
                    if regs[1] - regs[0] != 0xAA2:
                        raise RuntimeError("unexpected runtime segments")
                    if cs - (regs[0] << 4) != recorder - (segment << 4):
                        raise RuntimeError("caller and resident memory bases disagree")
                    if first_frame is None:
                        first_frame = frame
                    if frame != (first_frame + sequence - 1) % 65536:
                        raise RuntimeError("nonconsecutive original frames")
                    actor, flags = raw[36:74], raw[82:91]
                    makes, breaks = struct.unpack_from("<HH", raw, 94)
                    samples.append(dict(seq=sequence, frame=frame, makes=makes, breaks=breaks,
                                        hardware=raw[16:26], p1=actor, flags=flags, gate=raw[91],
                                        fallback=raw[92], level=raw[98], regs=raw[2:14]))
                    lines.append(f"sample seq={sequence} frame={frame} makes={makes} breaks={breaks}"
                                 f" hardware={raw[16:26].hex()} ammo={raw[26:34].hex()} selected={raw[34:36].hex()}"
                                 f" p1={actor.hex()} visual={raw[74:82].hex()} flags={flags.hex()} gate={raw[91]}"
                                 f" fallback={raw[92]} count={raw[93]} level={raw[98]} regs={raw[2:14].hex()}")
                    if pending is not None and sequence > pending["after_seq"]:
                        counter = "makes" if pending["kind"] == "keydown" else "breaks"
                        before = samples[pending["after_seq"] - 1][counter]
                        if samples[-1][counter] > before:
                            if pending["kind"] == "keyup" and raw[19] != 0:
                                raise RuntimeError("break IRQ did not release fire")
                            pending["ack_seq"] = sequence
                            lines.append(f"ack seq={sequence} after_seq={pending['after_seq']} kind={pending['kind']}"
                                         f" reason={pending['reason']} makes={makes} breaks={breaks}")
                            pending = None
                        elif sequence - pending["after_seq"] > 20:
                            raise RuntimeError("physical key command was not acknowledged")
                    if dead is None and actor[21] == 2:
                        dead = sequence
                        print(f"held_fire dying_seq={dead} makes={makes} breaks={breaks}", flush=True)
                        screenshot("dying")
                    if dead is not None and waiting is None and flags[1] == 2:
                        waiting = sequence
                        print(f"held_fire waiting_seq={waiting}", flush=True)
                    if dead is not None and resumed is None and actor[21] == 0:
                        resumed = sequence
                        print(f"held_fire resumed_seq={resumed} makes={makes} breaks={breaks}", flush=True)
                        screenshot("resumed")
                if sequence >= 4 and not made:
                    key("keydown", "start")
                    made = True
                if mode == "release_repress" and dead is not None and released is None and pending is None:
                    key("keyup", "death")
                    released = sequence
                if mode == "release_repress" and resumed is None and waiting is not None and sequence >= waiting + 10 and not repress and pending is None:
                    key("keydown", "waiting")
                    repress = True
                if resumed is not None and sequence >= resumed + 4 and not final_release and pending is None:
                    key("keyup", "resumed")
                    final_release = True
                if sequence - flushed_sequence >= 20:
                    flush()
                if resumed is not None and sequence >= resumed + 24 and final_release and pending is None:
                    break
                time.sleep(0.002)
            result = validate_lifecycle(samples, events, mode)
            screenshot("final")
            lines.append("observed " + " ".join(f"{key}={value}" for key, value in result.items()))
            flush()
        finally:
            try:
                subprocess.run(["xdotool", "keyup", "n"], check=True, timeout=5)
            finally:
                try:
                    stack.close()
                finally:
                    lines.extend(restored)
                    flush()
        return dict(result, hooks_restored=len(restored))


def complete_capture(run, output, observations):
    try:
        code = run()
        if code != 0 or len(observations) != 1 or observations[0].get("hooks_restored") != len(HOOKS):
            raise RuntimeError("owned DOSBox run or hook cleanup did not complete")
        result = observations[0]
        with output.open("a", encoding="ascii") as stream:
            stream.write("complete " + " ".join(f"{key}={value}" for key, value in result.items()) +
                         " game_process_exited=1 whole_game_parity=0\n")
        print("held_fire_capture=ok " + " ".join(f"{key}={value}" for key, value in result.items()), flush=True)
        return 0
    except BaseException as error:
        try:
            with output.open("a", encoding="ascii") as stream:
                stream.write(f"failed error={type(error).__name__} whole_game_parity=0\n")
        except OSError:
            pass
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--mode", choices=("hold_through", "release_repress"), default="hold_through")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    exe = (ROOT / "LEZAC.EXE").read_bytes()
    if hashlib.sha256(exe).hexdigest() != EXE_SHA256:
        raise RuntimeError("original EXE hash")
    image = exe[0x770:]
    for at, expected in WINDOWS.items():
        if image[at:at + len(expected)] != expected:
            raise RuntimeError(f"static guard {at:04x}")
    irq_stub(image); frame_stub(image)
    if args.self_check:
        print(f"held_fire_self_check=ok hooks=2 slots={SLOTS} stride={STRIDE} resident_bytes={RESIDENT_PARAGRAPHS * 16} live=0")
        return 0
    if not (args.run_dir and args.out and args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("temporary run directory, fresh output and both instrumentation approvals required")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    if (args.run_dir / "LEZAC.EXE").read_bytes() != exe or args.out.exists():
        parser.error("fresh output and unchanged temporary EXE required")
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_HELD_FIRE_XVFB"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    environment.enter_private_xvfb(sys.argv[1:])
    with args.out.open("x", encoding="ascii"):
        pass
    (args.run_dir / "L1ORACLE.COM").write_bytes(resident_program())
    original = seeder.write_runtime_state_snapshot
    observations = []

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            observations.append(observe(pid, base, run_dir, args.out, image, args.mode))
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "1",
                "--resident-loader", "L1ORACLE.COM",
                "--startup-seconds", "10", "--intro-seconds", "8", "--level-start-seconds", "5",
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    try:
        return complete_capture(seeder.main, args.out, observations)
    finally:
        seeder.write_runtime_state_snapshot = original


if __name__ == "__main__":
    raise SystemExit(main())
