#!/usr/bin/env python3
"""Check actual SDL keyboard ownership and player motion under private Xvfb."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
KEYS = ("z", "x", "m", "c", "Left", "Right", "Up", "Down")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not os.environ.get("DISPLAY"):
        parser.error("run under xvfb-run -a")
    env = dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="x11")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lezac-key-live-") as directory:
        path = Path(directory)
        with (path / "process.log").open("w") as log:
            child = subprocess.Popen([str(args.exe.resolve()), "--debug-key-ownership-live", str(path)],
                                     cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                def wait_for(predicate):
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        result = predicate()
                        if result:
                            return result
                        if child.poll() is not None:
                            raise RuntimeError(f"child exited: {(path / 'process.log').read_text()}")
                        time.sleep(0.01)
                    raise RuntimeError("live keyboard condition timed out")

                wait_for(lambda: "key_ownership_live=ready audio=dummy" in (path / "process.log").read_text())
                window = subprocess.check_output(["xdotool", "search", "--pid", str(child.pid), "--name", "Larax"], text=True).split()[-1]
                subprocess.run(["xdotool", "windowfocus", "--sync", window], check=True, env=env)

                def samples():
                    text = (path / "live.txt").read_text()
                    text = text[:text.rfind("\n") + 1]
                    return [dict(item.split("=", 1) for item in line.split()[1:])
                            for line in text.splitlines() if line.startswith("sample ") and " file=" in line]

                def hold(held, ticks=8):
                    subprocess.run(["xdotool", "keyup", *KEYS], check=True, env=env)
                    start = int(wait_for(samples)[-1]["tick"])
                    if held:
                        subprocess.run(["xdotool", "keydown", *held], check=True, env=env)
                    mask = "".join(str(int(key in held)) for key in KEYS)

                    def ready():
                        rows = [row for row in samples() if int(row["tick"]) > start]
                        matching = []
                        for row in rows:
                            if row["keys"] != mask:
                                matching.clear()
                            else:
                                matching.append(row)
                        return matching if len(matching) >= ticks else None

                    rows = wait_for(ready)
                    if any(row["dead1"] != "0" or row["dead2"] != "0" for row in rows):
                        raise RuntimeError("unexpected player death")
                    return rows

                cases = [("p1_left", ("z",), (-1, 0)), ("p1_right", ("x",), (1, 0)),
                         ("p2_left", ("Left",), (0, -1)), ("p2_right", ("Right",), (0, 1)),
                         ("opposed", ("z", "Right"), (-1, 1))]
                captures = []
                for name, held, directions in cases:
                    hold((), 12)
                    rows = hold(held)
                    for player, direction in enumerate(directions, 1):
                        key = f"p{player}x"
                        delta = float(rows[-1][key]) - float(rows[0][key])
                        if (direction == 0 and delta != 0) or (direction != 0 and delta * direction <= 0):
                            raise RuntimeError(f"{name} P{player} moved incorrectly: {delta}")
                    captures.append((name, rows[-1]["file"]))
                    print(f"key_ownership_live_case=ok name={name} ticks={len(rows)}", flush=True)
                for player, key in ((1, "m"), (2, "Up")):
                    idle = hold((), 35)[-1]
                    rows = hold((key,))
                    other = 3 - player
                    if min(float(row[f"p{player}y"]) for row in rows) >= float(idle[f"p{player}y"]):
                        raise RuntimeError(f"P{player} failed to jump")
                    if any(float(row[f"p{other}y"]) != float(idle[f"p{other}y"]) for row in rows):
                        raise RuntimeError(f"P{other} jumped from wrong key")
                    captures.append((f"p{player}_jump", rows[-1]["file"]))
                    print(f"key_ownership_live_case=ok name=p{player}_jump ticks={len(rows)}", flush=True)
                subprocess.run(["xdotool", "keyup", *KEYS], check=True, env=env)
                subprocess.run(["xdotool", "key", "--delay", "100", "Escape", "Escape"], check=True, env=env)
                if child.wait(timeout=10) != 0:
                    raise RuntimeError((path / "process.log").read_text())
                if args.out:
                    for name, file in captures:
                        shutil.copyfile(path / file, args.out / f"{name}.ppm")
                    for file in ("live.txt", "process.log"):
                        shutil.copyfile(path / file, args.out / file)
                print("key_ownership_live=ok cases=7 physical_keys=1 production_update=1 moving_players=2 inspected_frames=7 audio=dummy")
            finally:
                subprocess.run(["xdotool", "keyup", *KEYS], check=False, env=env)
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=5)


if __name__ == "__main__":
    main()
