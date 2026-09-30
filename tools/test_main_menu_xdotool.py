#!/usr/bin/env python3
"""Check original-backed menu pixels and physical keys through the normal SDL app."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

from check_main_menu_fixture import HEADER, ROOT, load_fixture, require, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    require(bool(os.environ.get("DISPLAY")), "private Xvfb display required")
    from PIL import Image, ImageGrab
    _, expected = load_fixture()
    env = dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="x11", SDL_RENDER_DRIVER="software")
    output = args.out.resolve() if args.out else Path(tempfile.mkdtemp(prefix="lezac-main-menu-live-"))
    output.mkdir(parents=True, exist_ok=True)
    captures = []
    events = []
    started = time.monotonic()
    with (output / "process.log").open("w") as log:
        child = subprocess.Popen([str(args.exe.resolve())], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            def xdo(*command):
                return subprocess.check_output(["xdotool", *command], text=True, env=env, timeout=5).strip()

            window = None
            deadline = time.monotonic() + 15
            while not window and time.monotonic() < deadline:
                require(child.poll() is None, "normal app exited before window discovery")
                try:
                    window = xdo("search", "--pid", str(child.pid), "--name", "Larax").split()[-1]
                except (subprocess.CalledProcessError, IndexError):
                    time.sleep(.02)
            require(window is not None, "normal app window not found")
            xdo("windowfocus", "--sync", window)
            geometry = dict(line.split("=", 1) for line in xdo("getwindowgeometry", "--shell", window).splitlines())
            x, y, w, h = (int(geometry[k]) for k in ("X", "Y", "WIDTH", "HEIGHT"))
            require((w, h) == (960, 600), "normal app window geometry")

            def pixels():
                return ImageGrab.grab(xdisplay=env["DISPLAY"]).crop((x, y, x + w, y + h)).convert("RGB").resize(
                    (320, 200), Image.Resampling.NEAREST).tobytes()

            def capture(name, data):
                (output / (name + ".ppm")).write_bytes(HEADER + data)
                captures.append(dict(name=name, pixel_sha256=sha(data), seconds=time.monotonic() - started))

            def wait_frame(names, timeout=18):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    require(child.poll() is None, "normal app exited during menu observation")
                    data = pixels()
                    for name in names:
                        if data == expected[name][len(HEADER):]:
                            return name, data
                    time.sleep(.01)
                raise RuntimeError("normal app did not show " + ",".join(names))

            def key(*keys):
                events.append(dict(keys=keys, seconds=time.monotonic() - started))
                xdo("key", "--delay", "0", *keys)

            # Natural startup reaches an original text checkpoint without injected skips.
            name, frame = wait_frame(["italian-line0-step02", "italian-line0-step06", "italian-line0-step30"])
            capture("natural-" + name, frame)
            _, frame = wait_frame(["italian-full"])
            capture("italian-full", frame)
            key("l")
            time.sleep(.12)
            key("1")  # Fade skip, including the final 22 ms delay.
            time.sleep(.12)
            # Stop only this owned child so both physical keys reach one SDL batch.
            os.kill(child.pid, signal.SIGSTOP)
            try:
                deadline = time.monotonic() + 3
                while "State:\tT" not in Path(f"/proc/{child.pid}/status").read_text():
                    require(time.monotonic() < deadline, "owned app did not stop for queued-key check")
                    time.sleep(.001)
                key("1", "2")  # Typing skip plus queued selection must not start a game.
            finally:
                os.kill(child.pid, signal.SIGCONT)
            _, frame = wait_frame(["english-full"], 3)
            capture("english-queued-selection-consumed", frame)
            key("l")
            time.sleep(.12)
            key("Escape")
            time.sleep(.12)
            key("Escape")
            _, frame = wait_frame(["italian-full"], 3)
            capture("italian-escape-skips-consumed", frame)
            key("1")
            time.sleep(.15)
            frame = pixels()
            require(frame != expected["italian-full"][len(HEADER):] and len(set(frame)) > 8,
                    "fresh player selection did not leave the menu")
            capture("fresh-selection-intro", frame)
            key("Return")
            time.sleep(.15)
            key("Escape")
            time.sleep(.12)
            key("Escape")
            time.sleep(.12)
            key("Escape")
            _, frame = wait_frame(["italian-full"], 3)
            capture("game-return-menu", frame)
            key("Escape")
            require(child.wait(timeout=5) == 0, "fresh Escape failed to exit")
            result = dict(status="observed", exe_sha256=sha(args.exe.read_bytes()), audio="dummy",
                          normal_entry_point=True, gameplay_seeded=False, queued_key_check_gated=True,
                          startup_timing_gated=False, captures=captures, events=events,
                          whole_game_parity=False)
        except Exception as error:
            (output / "failure.json").write_text(json.dumps(dict(status="failed", error=str(error),
                                                                 captures=captures, events=events), indent=2) + "\n")
            raise
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("main_menu_live=ok original_pixels=1 languages=2 queued_selection_consumed=1 escape_skips_consumed=1 fresh_start=1 fresh_exit=1 frames=6 audio=dummy")


if __name__ == "__main__":
    main()
