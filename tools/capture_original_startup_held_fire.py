#!/usr/bin/env python3
"""Observe natural startup clock and continuous physical reentry in one DOSBox.

The temporary pre-clock installation gate does not replace the DOS clock.
No menu/intro/gameplay phase gate or RNG draw hook remains in the live route.
Two verified DOS-owned recorder arenas keep the existing v4 ring unchanged.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time

import capture_original_held_fire as held
import capture_original_startup_rng as startup
import check_held_fire_capture as checker

require = startup.require


def initialization_rng(seed):
    for _ in range(398):
        seed = (seed * 0x08088405 + 1) & 0xFFFFFFFF
    return seed


def clock_snapshot(session):
    row = session.sample("menu_before_physical_start")
    # There is no draw hook in this mode; do not present its zero counter as
    # an observed draw count. Only the menu RNG equality is checked.
    return {key: row[key] for key in ("clock_calls", "clock_cx", "clock_dx",
                                      "initialized_rng", "rng", "clock_registers")}


def validate_context(result, text):
    require(result["schema"] == "lezac_startup_held_fire_v1" and result["status"] == "captured",
            "incomplete combined capture")
    require(result["exe_sha256"] == held.EXE_SHA256 and result["audio"] == "dummy" and
            result["gameplay_seeded"] is False and result["main_phase_gates"] is False and
            result["rng_draw_hook"] is False and result["temporary_preclock_gate"] is True and
            result["whole_game_parity"] is False and result["frame_alignment"] is False,
            "invalid combined evidence claims")
    require(all(type(result[key]) is int for key in ("clock_hooks_restored", "child_exit_code", "final_clock_calls",
                                                    "code_segment", "data_segment", "resident_segment")),
            "invalid combined numeric context")
    require(result["clock_hooks_restored"] == 1 and result["child_exit_code"] == 0 and
            result["final_clock_calls"] == 1 and result["error"] is None,
            "clock cleanup or owned process exit incomplete")
    require(result["clock_stub_sha256"] == hashlib.sha256(startup.clock_stub(result["code_segment"] + 0x920)).hexdigest(),
            "startup clock recorder identity differs")
    canonical = text.replace("\r\n", "\n")
    require(result["trace_sha256"] == hashlib.sha256(canonical.encode("ascii")).hexdigest(),
            "combined trace identity differs")
    records = checker.parse(canonical)
    header = records[0][1]
    require(header["schema"] == "held_fire_irq_v4", "combined capture needs objective context")
    require(header["dosbox_sha256"] == result["dosbox_sha256"] and
            header["source_sha256"] == result["held_source_sha256"], "combined recorder/process identity differs")
    require(result["final_clock_record"] == result["initial_clock_record"], "clock context changed during gameplay")
    raw = bytes.fromhex(result["initial_clock_record"])
    require(len(raw) == 16, "truncated clock record")
    cx, dx, low, high, ds, ss, ip, cs = struct.unpack("<8H", raw)
    row = result["clock"]
    require(all(type(row[key]) is int for key in ("clock_cx", "clock_dx", "clock_calls", "initialized_rng", "rng")),
            "invalid clock sample number")
    require(row["clock_cx"] == cx and row["clock_dx"] == dx and row["clock_calls"] == 1 and
            row["initialized_rng"] == row["rng"] == startup.clock_seed(cx, dx) == startup.clock_seed(low, high) and
            cx >> 8 < 24 and cx & 255 < 60 and dx >> 8 < 60 and dx & 255 < 100,
            "natural startup clock or menu RNG differs")
    require(row["clock_registers"] == dict(cs=cs, ds=ds, ss=ss, return_ip=ip) and
            cs == result["code_segment"] and ds == result["data_segment"] and ds - cs == 0xAA2 and
            ip == startup.CLOCK_IP + 5, "original startup register boundary differs")
    resident = result["resident_segment"]
    mcb = bytes.fromhex(result["resident_mcb"])
    require(0 < resident < cs < ds < 0xA000 and len(mcb) == 16 and mcb[0] in (77, 90) and int.from_bytes(mcb[1:3], "little") == resident and
            int.from_bytes(mcb[3:5], "little") >= 0x100 and cs >= resident + 0x100,
            "startup recorder allocation not owned")
    other = int(header["resident"], 16)
    require(other != resident and (other >= resident + 0x101 or resident >= other + 0x101),
            "startup and gameplay recorder arenas overlap")
    first = next(fields for tag, fields in records if tag == "sample")
    regs = struct.unpack("<6H", bytes.fromhex(first["regs"]))
    require(regs[:2] == (cs, ds), "startup and gameplay are not the same original process")
    require(int(first["frame"]) == 1 and int(first["rng"]) == initialization_rng(row["initialized_rng"]),
            "first gameplay frame or 398-draw startup chain differs")
    summary = checker.validate_text(canonical)
    require(result["mode"] == summary["mode"] and summary["hooks_restored"] == 3,
            "combined route or gameplay restoration differs")
    return dict(summary, startup_rng=row["initialized_rng"], first_gameplay_rng=int(first["rng"]),
                first_gameplay_frame=int(first["frame"]), total_hooks_restored=4)


def capture(args):
    require(args.approve_procmem and args.approve_runtime_instrumentation, "capture approvals required")
    require(sys.platform.startswith("linux"), "combined capture requires Linux/WSL")
    if not args.private_xvfb:
        env = dict(os.environ, SDL_AUDIODRIVER="dummy", PYTHONDONTWRITEBYTECODE="1")
        env.pop("SDL_VIDEODRIVER", None)
        subprocess.run(["xvfb-run", "-a", sys.executable, "-B", str(Path(__file__).resolve()),
                        *sys.argv[1:], "--private-xvfb"], env=env, timeout=120, check=True)
        return
    require(os.environ.get("DISPLAY"), "missing private display")
    output = args.out.resolve()
    require(not output.exists() and output != held.ROOT and held.ROOT not in output.parents,
            "use a fresh output outside the checkout")
    output.mkdir(parents=True)
    trace = output / "held_fire.txt"
    trace.touch(exist_ok=False)
    session, observations = startup.Session(output), []
    metadata = dict(schema="lezac_startup_held_fire_v1", status="capturing", mode=args.mode,
                    exe_sha256=held.EXE_SHA256, audio="dummy", gameplay_seeded=False,
                    main_phase_gates=False, rng_draw_hook=False, temporary_preclock_gate=True,
                    frame_alignment=False, whole_game_parity=False, error=None,
                    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    startup_source_sha256=hashlib.sha256(Path(startup.__file__).read_bytes()).hexdigest(),
                    held_source_sha256=hashlib.sha256(Path(held.__file__).read_bytes()).hexdigest())

    def persist():
        metadata["clock_hooks_restored"] = len(session.restored)
        metadata["child_exit_code"] = session.child.returncode if session.child is not None else None
        text = trace.read_text(encoding="ascii")
        metadata["trace_sha256"] = hashlib.sha256(text.encode("ascii")).hexdigest()
        (output / "result.json").write_text(json.dumps(metadata, indent=2) + "\n")

    def prepare():
        session.key("1")
        time.sleep(.5)
        session.key("1")
        time.sleep(4)
        session.screenshot("intro")
        session.key("Return")

    def run():
        try:
            metadata.update(session.launch(clock_only=True, resident_loader=("L1ORACLE.COM", held.resident_program())))
            metadata["clock_stub_sha256"] = hashlib.sha256(startup.clock_stub(session.rtl_segment)).hexdigest()
            time.sleep(5)
            metadata["clock"] = clock_snapshot(session)
            metadata["initial_clock_record"] = session.read(session.recorder + startup.CLOCK_RECORD, 16).hex()
            session.screenshot("menu")
            persist()
            observations.append(held.observe(session.child.pid, session.base, session.run, trace,
                                            session.raw[0x770:], args.mode, True,
                                            code_segment=session.code_segment, prepare=prepare))
            session.screenshot("post-reentry")
        finally:
            try:
                if session.mem is not None and session.child.poll() is None:
                    try:
                        metadata["final_clock_calls"] = int.from_bytes(session.read(session.recorder + startup.COUNTERS, 2), "little")
                        metadata["final_clock_record"] = session.read(session.recorder + startup.CLOCK_RECORD, 16).hex()
                    except Exception as diagnostic_error:
                        metadata["clock_diagnostic_error"] = str(diagnostic_error)
            finally:
                try:
                    session.close()
                finally:
                    persist()
        return session.child.returncode

    try:
        held.complete_capture(run, trace, observations, True)
        metadata["status"] = "captured"
        persist()
        summary = validate_context(metadata, trace.read_text(encoding="ascii"))
        metadata["verification"] = summary
        persist()
        print("startup_held_fire=ok " + " ".join(f"{key}={value}" for key, value in summary.items()) +
              " audio=dummy gameplay_seeded=0 whole_game_parity=0", flush=True)
    except BaseException as error:
        metadata.update(status="incomplete", error=str(error))
        persist()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--mode", choices=("hold_through", "release_repress"), default="hold_through")
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    parser.add_argument("--private-xvfb", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    require(args.out is not None, "--out is required")
    capture(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
