#!/usr/bin/env python3
"""Observe held menu choices and consumed intro keys through the interactive SDL loop."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

from check_main_menu_fixture import HEADER, ROOT, load_fixture, require, sha
from intro_frame import intro
from test_bios_menu_input_xdotool import acquire_window


def prepare_output(requested):
    if requested is None:
        return Path(tempfile.mkdtemp(prefix="lezac-buffered-menu-"))
    output = requested.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        # Retain prior and partial observations when CTest repeats this helper.
        return Path(tempfile.mkdtemp(prefix="run-", dir=output))
    return output


def observe(exe, output, choice, held, expected):
    from PIL import Image, ImageGrab
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="x11", SDL_RENDER_DRIVER="software")
    result = dict(status="capturing", exe_sha256=sha(exe.read_bytes()), harness_sha256=sha(Path(__file__).read_bytes()),
                  intro_detector_sha256=sha(Path(__file__).with_name("intro_frame.py").read_bytes()),
                  audio="dummy", gameplay_seeded=False, startup_timing_gated=False, physical_keys=True,
                  manual_input=False, player_choice=choice, held=held, events=[], captures=[], whole_game_parity=False)
    result["intro_key_batch_gated"] = not held
    started = time.monotonic()
    with (output / "process.log").open("w") as log:
        child = subprocess.Popen([str(exe), "--debug-menu-repeat-live", str(output), str(choice)],
                                 cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            def xdo(*args):
                return subprocess.check_output(["xdotool", *args], text=True, env=env, timeout=5,
                                               stderr=subprocess.PIPE).strip()

            def records():
                path = output / "live.txt"
                text = path.read_text() if path.exists() else ""
                return [(parts[0], dict(token.split("=", 1) for token in parts[1:]))
                        for line in text[:text.rfind("\n") + 1].splitlines() if (parts := line.split())]

            def samples():
                return [row for tag, row in records() if tag == "sample"]

            def wait(predicate, timeout=18):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    require(child.poll() is None, "owned interactive app exited early")
                    value = predicate()
                    if value:
                        return value
                    time.sleep(.005)
                raise RuntimeError("buffered menu input condition timed out")

            window, geometry = wait(lambda: acquire_window(child.pid, xdo))
            x, y, w, h = (int(geometry[key]) for key in ("X", "Y", "WIDTH", "HEIGHT"))
            require((w, h) == (960, 600), "interactive app geometry")
            result["x_repeat"] = subprocess.check_output(["xset", "q"], env=env, text=True, timeout=5)

            def frame():
                return ImageGrab.grab(xdisplay=env["DISPLAY"]).crop((x, y, x + w, y + h)).convert("RGB").resize(
                    (320, 200), Image.Resampling.NEAREST)

            def capture(name, image=None):
                image = frame() if image is None else image
                (output / (name + ".ppm")).write_bytes(HEADER + image.tobytes())
                image.resize((960, 600), Image.Resampling.NEAREST).save(output / (name + "-preview.png"))
                result["captures"].append(dict(name=name, seconds=time.monotonic() - started,
                                              pixel_sha256=sha(image.tobytes())))
                return image

            def key(kind, value):
                result["events"].append(dict(kind=kind, key=value, seconds=time.monotonic() - started))
                xdo(kind, value)

            def white(image):
                return sum(count for count, color in image.getcolors(64000) if color == (255, 255, 255))

            def gameplay_frame():
                image = frame()
                return image if not intro(image) and len(image.getcolors(64000)) > 12 and \
                    image.tobytes() != expected["italian-full"][len(HEADER):] else None

            def natural_text():
                image = frame()
                return image if image.tobytes() in (expected[name][len(HEADER):] for name in
                    ("italian-line0-step02", "italian-line0-step06", "italian-line0-step30")) else None

            def full_menu():
                image = frame()
                return image if image.tobytes() == expected["italian-full"][len(HEADER):] else None

            capture("natural-menu-typing", wait(natural_text))
            if held:
                key("keydown", str(choice))
                sample = wait(lambda: samples()[-1] if samples() else None, timeout=6)
                require(int(sample["repeats"]) >= 3 and int(sample["breaks"]) == 0 and int(sample["key"]) == 1,
                        "gameplay was not reached by future repeats of one held choice")
                require(any(tag == "status" and row.get("menu") == "0" and row.get("intro") == "0" and
                            int(row["players"]) == choice for tag, row in records()), "player mode was not observed")
                capture("held-choice-gameplay", wait(gameplay_frame, timeout=3))
                result["gameplay_sample"] = sample
                key("keyup", str(choice))
            else:
                key("key", "space")
                wait(lambda: frame().tobytes() == expected["italian-full"][len(HEADER):])
                key("key", str(choice))
                wait(lambda: intro(frame()))
                key("key", "Shift_L")
                time.sleep(.1)
                require(not samples() and intro(frame()) and white(frame()) < 620, "modifier skipped intro typing")
                os.kill(child.pid, signal.SIGSTOP)
                try:
                    wait(lambda: "State:\tT" in Path(f"/proc/{child.pid}/status").read_text(), timeout=3)
                    result["events"].append(dict(kind="queued-press", keys=["space", "Return"],
                                                  seconds=time.monotonic() - started))
                    xdo("key", "--delay", "0", "space", "Return")
                finally:
                    os.kill(child.pid, signal.SIGCONT)
                wait(lambda: intro(frame()) and white(frame()) == 620)
                capture("consumed-intro-skip")
                time.sleep(2.3)
                key("key", "Shift_L")
                time.sleep(.1)
                image = capture("intro-still-awaiting-key")
                require(not samples() and intro(image) and white(image) == 620,
                        "typing key or modifier released the original blocking intro wait")
                key("key", "Return")
                result["gameplay_sample"] = wait(lambda: samples()[-1] if samples() else None, timeout=6)
                capture("fresh-intro-ack-gameplay", wait(gameplay_frame, timeout=3))
            key("key", "Escape")
            time.sleep(.15)
            capture("game-over-before-acknowledgement")
            key("key", "Return")
            for _ in range(2):
                time.sleep(.15)
                key("key", "Escape")
            capture("returned-main-menu", wait(full_menu, 3))
            time.sleep(.15)
            key("key", "Escape")
            require(child.wait(timeout=5) == 0, "interactive app did not exit cleanly")
            result["status"] = "observed"
        except Exception as error:
            result.update(status="failed", error=str(error))
            raise
        finally:
            subprocess.run(["xdotool", "keyup", str(choice)], env=env, check=False, timeout=5)
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
            result["child_exit_code"] = child.returncode
            (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    require(bool(os.environ.get("DISPLAY")), "private Xvfb display required")
    _, expected = load_fixture()
    output = prepare_output(args.out)
    results = [observe(args.exe.resolve(), output / name, choice, held, expected)
               for name, choice, held in (("held-one", 1, True), ("held-two", 2, True), ("fresh-intro", 1, False))]
    (output / "result.json").write_text(json.dumps(dict(status="observed", output=str(output), cases=results), indent=2) + "\n")
    print("buffered_menu_live=ok held_choices=2 consumed_intro_skip=1 modifiers_ignored=1 gameplay_observed=3 audio=dummy gameplay_seeded=0 whole_game_parity=0 output=" + str(output))


if __name__ == "__main__":
    main()
