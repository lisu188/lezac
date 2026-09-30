#!/usr/bin/env python3
"""Compare natural held-fire lifecycle semantics using real SDL/XTEST input."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from check_held_fire_capture import parse, validate_text

ROOT = Path(__file__).resolve().parent.parent


def summarize_objective_context(rows, deaths, statuses):
    fields = ("rng", "collected", "remaining", "required", "objective")
    for row in rows + deaths:
        if any(type(row.get(key)) is not int for key in fields) or not (
                0 <= row["rng"] <= 0xFFFFFFFF and 0 <= row["collected"] <= 65535 and
                0 <= row["remaining"] <= 1980 and 0 <= row["required"] <= 65535 and
                0 <= row["objective"] <= 255):
            raise RuntimeError("missing or invalid read-only objective context")
    for death in deaths:
        if death["player"] != 1 or death["level"] != 1 or not rows or death["reset"] != rows[0]["reset"]:
            raise RuntimeError("unexpected objective death boundary")
        if death["gate"] != int(death["collected"] + death["remaining"] >= death["required"]):
            raise RuntimeError("latched death gate differs from its objective counts")
        sampled = next((row for row in rows if row["seq"] == death["after_seq"] + 1), None)
        if sampled is None or sampled["frame"] != death["frame"] or not sampled["dead"] or sampled["gate"] != death["gate"]:
            raise RuntimeError("death context is not tied to its gameplay update")
    first_death = next((row for row in rows if row["dead"]), None)
    if first_death is not None and (not deaths or deaths[0]["after_seq"] + 1 != first_death["seq"]):
        raise RuntimeError("natural death lacks its exact gate boundary")
    menu = next((row for row in statuses if row.get("menu") == 1), None)
    if menu is None or type(menu.get("rng")) is not int or not 0 <= menu["rng"] <= 0xFFFFFFFF:
        raise RuntimeError("startup menu RNG was not observed before input")
    return dict(startup_menu_rng=menu["rng"],
                first_observed={key: rows[0][key] for key in ("frame",) + fields} if rows else None,
                death_boundaries=deaths, gate_formula_match=bool(deaths),
                gameplay_seeded=0, frame_alignment=0, whole_game_parity=0)


def validate_live(rows, events, original):
    if not rows:
        raise RuntimeError("no production gameplay samples")
    dying = next((r["seq"] for r in rows if r["dead"]), None)
    waiting = next((r["seq"] for r in rows if r["state"] == 2), None)
    resumed = next((r["seq"] for r in rows if dying and r["seq"] > dying and not r["dead"]), None)
    if dying is None or resumed is None or rows[-1]["seq"] < resumed + 24:
        raise RuntimeError("C++ physical lifecycle incomplete")
    countdown = (original["waiting_seq"] or original["resumed_seq"]) - original["dying_seq"]
    if (waiting or resumed) - dying != countdown:
        raise RuntimeError("C++ death countdown differs from original observation")
    if bool(waiting) != bool(original["waiting_seq"]):
        raise RuntimeError("C++ waiting/reentry semantics differ from original")
    previous_fallback = 0
    for seq, row in enumerate(rows, 1):
        if row["seq"] != seq or row["frame"] != rows[0]["frame"] + seq - 1:
            raise RuntimeError("missing or duplicate C++ gameplay updates")
        if row["level"] != 1 or row["reset"] != rows[0]["reset"] or row["gate"] != 1:
            raise RuntimeError("C++ restarted or left level one")
        if row["dead"] != int(dying <= seq < resumed) or row["state"] != (2 if waiting and waiting <= seq < resumed else 1):
            raise RuntimeError("unexpected C++ lifecycle transition")
        if row["lives"] != (1 if seq >= (waiting or resumed) else 2):
            raise RuntimeError("C++ reserve-life transition differs from original")
        expected = previous_fallback + 1 if row["state"] == 2 else 0
        if row["fallback"] != expected or row["fallback"] >= 230:
            raise RuntimeError("C++ fallback restart contaminated the observation")
        previous_fallback = row["fallback"]
        if seq > 1 and (row["makes"] < rows[seq - 2]["makes"] or row["breaks"] < rows[seq - 2]["breaks"]):
            raise RuntimeError("SDL event counters regressed")
    if rows[dying - 1]["countdown"] != countdown or rows[dying - 1]["repeats"] == 0:
        raise RuntimeError("missing natural death or SDL repeat evidence")
    expected_events = [("keydown", "start"), ("keyup", "resumed")]
    if original["mode"] == "release_repress":
        expected_events = [("keydown", "start"), ("keyup", "death"), ("keydown", "waiting"), ("keyup", "resumed")]
    if [(e["kind"], e["reason"]) for e in events] != expected_events:
        raise RuntimeError("unexpected physical SDL input sequence")
    last_ack = 0
    for event in events:
        after = event["after_seq"]
        if not 1 <= after < len(rows):
            raise RuntimeError("invalid physical SDL event sequence")
        counter = "makes" if event["kind"] == "keydown" else "breaks"
        before = rows[after - 1][counter]
        ack = next((r for r in rows[after:] if r[counter] > before), None)
        if ack is None or not last_ack <= after < ack["seq"] <= after + 20:
            raise RuntimeError("missing or late physical SDL event")
        event["ack_seq"] = ack["seq"]
        if event["kind"] == "keyup" and (ack["key"] or ack["latch"]):
            raise RuntimeError("SDL key-up failed to clear physical key and fire latch")
        last_ack = ack["seq"]
    if original["mode"] == "release_repress":
        release, press = events[1], events[2]
        if not (dying <= release["after_seq"] < release["ack_seq"] < waiting <= press["after_seq"] - 10):
            raise RuntimeError("C++ release/repress order differs from original")
        if not press["after_seq"] < press["ack_seq"] <= resumed:
            raise RuntimeError("C++ reentered before a new SDL make event")
        for row in rows[release["ack_seq"] - 1:press["after_seq"]]:
            if row["key"] or row["latch"]:
                raise RuntimeError("C++ fire stayed held after release")
    elif rows[resumed - 1]["repeats"] <= rows[dying - 1]["repeats"]:
        raise RuntimeError("C++ held fire lacks repeat events during death")
    if rows[-1]["key"] or rows[-1]["latch"] or rows[-1]["breaks"] != original["breaks"]:
        raise RuntimeError("C++ final fire release or event count mismatch")
    return dict(mode=original["mode"], samples=len(rows), dying_seq=dying, waiting_seq=waiting or 0,
                resumed_seq=resumed, death_updates=countdown, makes=rows[-1]["makes"], breaks=rows[-1]["breaks"],
                physical_keys=1, gameplay_seeded=0, production_update=1, lifecycle_match=1,
                frame_alignment=0, whole_game_parity=0, audio="dummy")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get("DISPLAY"):
        parser.error("run under private xvfb-run -a")
    original_text = args.original.read_text(encoding="ascii")
    original = validate_text(original_text)
    original_records = parse(original_text)
    first_frame = int(next(row["frame"] for tag, row in original_records if tag == "sample"))
    start_after = int(next(row["after_seq"] for tag, row in original_records if tag == "event"))
    first_press_after_frame = first_frame + start_after - 1
    args.out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="x11")
    identity = dict(exe_sha256=hashlib.sha256(args.exe.read_bytes()).hexdigest(),
                    observer_source_sha256=hashlib.sha256((ROOT / "src/app/app.cpp").read_bytes()).hexdigest(),
                    harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    original_capture_sha256=hashlib.sha256(original_text.encode("ascii")).hexdigest(),
                    cwd=str(ROOT), audio="dummy", physical_keys=1, gameplay_seeded=0)
    (args.out / "identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    events = []
    with (args.out / "process.log").open("w") as log:
        child = subprocess.Popen([str(args.exe.resolve()), "--debug-held-fire-live", str(args.out.resolve())],
                                 cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            def records():
                path = args.out / "live.txt"
                text = path.read_text() if path.exists() else ""
                text = text[:text.rfind("\n") + 1]
                return [(parts[0], dict(token.split("=", 1) for token in parts[1:]))
                        for line in text.splitlines() if (parts := line.split())]

            def samples():
                return [{k: v if k in ("phase", "file") else float(v) if k in ("x", "y") else int(v)
                         for k, v in row.items()} for tag, row in records() if tag == "sample"]

            def objective_context():
                trace = records()
                deaths = [{key: int(value) for key, value in row.items()} for tag, row in trace if tag == "death"]
                statuses = [{key: int(value) for key, value in row.items()} for tag, row in trace if tag == "status"]
                return summarize_objective_context(samples(), deaths, statuses)

            def wait(predicate, timeout=65):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    result = predicate()
                    if result:
                        return result
                    if child.poll() is not None:
                        raise RuntimeError(f"C++ process exited early: {(args.out / 'process.log').read_text()}")
                    time.sleep(0.01)
                raise RuntimeError("physical held-fire condition timed out")

            def command(*args):
                subprocess.run(["xdotool", *args], check=True, env=env, timeout=5)

            def send(kind, reason):
                after = samples()[-1]["seq"]
                command(kind, "n")
                events.append(dict(after_seq=after, kind=kind, reason=reason))
                print(f"held_fire_sdl_event={kind} reason={reason} after_seq={after}", flush=True)

            wait(lambda: "held_fire_live=ready audio=dummy" in (args.out / "process.log").read_text())
            window = subprocess.check_output(["xdotool", "search", "--pid", str(child.pid), "--name", "Larax"],
                                             text=True, env=env, timeout=5).split()[-1]
            command("windowfocus", "--sync", window)
            command("key", "1")
            wait(lambda: any(tag == "status" and row["intro"] == "1" for tag, row in records()))
            command("key", "space")
            wait(lambda: samples() and samples()[-1]["frame"] >= first_press_after_frame)
            send("keydown", "start")
            dying = wait(lambda: next((r for r in samples() if r["dead"]), None))
            if not dying["gate"]:
                raise RuntimeError("natural death closed the objective gate; reentry comparison is not established")
            if original["mode"] == "release_repress":
                send("keyup", "death")
                waiting = wait(lambda: next((r for r in samples() if r["state"] == 2), None))
                wait(lambda: samples()[-1]["seq"] >= waiting["seq"] + 10)
                send("keydown", "waiting")
            resumed = wait(lambda: next((r for r in samples() if r["seq"] > dying["seq"] and not r["dead"]), None))
            wait(lambda: samples()[-1]["seq"] >= resumed["seq"] + 4)
            send("keyup", "resumed")
            wait(lambda: samples()[-1]["seq"] >= resumed["seq"] + 24)
            rows = samples()
            result = validate_live(rows, events, original)
            context = objective_context()
            command("key", "--delay", "100", "Escape", "Escape")
            if child.wait(timeout=10) != 0:
                raise RuntimeError("C++ process failed during exit")
            for phase in ("active", "dying", "resumed") + (("waiting",) if original["waiting_seq"] else ()):
                data = (args.out / (phase + ".ppm")).read_bytes()
                if not data.startswith(b"P6\n320 200\n255\n") or len(set(data[15:])) < 4:
                    raise RuntimeError("missing or blank gameplay checkpoint")
        except BaseException as error:
            try:
                failure = dict(status="incomplete", error=str(error), events=events, whole_game_parity=False)
                try:
                    failure["objective_context"] = objective_context()
                except Exception as context_error:
                    failure["objective_context_error"] = str(context_error)
                (args.out / "failure.json").write_text(json.dumps(failure, indent=2) + "\n")
            except OSError:
                pass
            raise
        finally:
            try:
                subprocess.run(["xdotool", "keyup", "n"], check=False, env=env, timeout=5)
            finally:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=5)
    (args.out / "result.json").write_text(json.dumps(dict(result, events=events, objective_context=context), indent=2) + "\n")
    print("held_fire_sdl=ok " + " ".join(f"{k}={v}" for k, v in result.items()), flush=True)


if __name__ == "__main__":
    main()
