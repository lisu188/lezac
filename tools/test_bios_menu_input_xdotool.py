#!/usr/bin/env python3
"""Observe original-backed buffered keyboard rules in the normal SDL app."""

import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from check_main_menu_fixture import HEADER, ROOT, load_fixture, require, sha


def acquire_window(pid, xdo):
    try:
        windows = xdo("search", "--onlyvisible", "--pid", str(pid), "--name", "Larax").split()
        if not windows:
            return None
        window = windows[-1]
        xdo("windowfocus", "--sync", window)
        geometry = dict(line.split("=", 1) for line in xdo("getwindowgeometry", "--shell", window).splitlines())
        return window, geometry
    except subprocess.CalledProcessError as error:
        if (error.cmd[1] == "search" and error.returncode == 1) or "BadWindow" in (error.stderr or ""):
            return None
        raise


def observe(exe, output, scenario, expected):
    from PIL import Image, ImageGrab
    output.mkdir()
    env = dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="x11", SDL_RENDER_DRIVER="software")
    result = dict(status="capturing", scenario=scenario, audio="dummy", normal_entry_point=True,
                  gameplay_seeded=False, startup_timing_gated=False, physical_keys=True,
                  manual_input=False, whole_game_parity=False, exe_sha256=sha(exe.read_bytes()),
                  harness_sha256=sha(Path(__file__).read_bytes()), events=[], captures=[])
    started = time.monotonic()
    with (output / "process.log").open("w") as log:
        child = subprocess.Popen([str(exe)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            def xdo(*args):
                return subprocess.check_output(["xdotool", *args], env=env, text=True, timeout=5,
                                               stderr=subprocess.PIPE).strip()

            def wait(predicate, timeout=20):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    require(child.poll() is None, "owned normal app exited early")
                    value = predicate()
                    if value:
                        return value
                    time.sleep(.005)
                raise RuntimeError("buffered keyboard observation timed out")

            # A startup XID may disappear between discovery and focus.
            window, geometry = wait(lambda: acquire_window(child.pid, xdo))
            x, y, w, h = (int(geometry[key]) for key in ("X", "Y", "WIDTH", "HEIGHT"))
            require((w, h) == (960, 600), "normal app window geometry")

            def frame():
                return ImageGrab.grab(xdisplay=env["DISPLAY"]).crop((x, y, x+w, y+h)).convert("RGB").resize(
                    (320, 200), Image.Resampling.NEAREST)

            def full(language="italian"):
                image = frame()
                return image if image.tobytes() == expected[language + "-full"][len(HEADER):] else None

            def capture(name, image=None):
                image = frame() if image is None else image
                image.save(output / (name + ".png"))
                image.resize((960, 600), Image.Resampling.NEAREST).save(output / (name + "-preview.png"))
                result["captures"].append(dict(name=name, seconds=time.monotonic() - started,
                                               pixel_sha256=sha(image.tobytes())))
                return image

            def key(kind, value):
                result["events"].append(dict(kind=kind, key=value, seconds=time.monotonic() - started))
                xdo(kind, value)

            mapping = subprocess.check_output(["xmodmap", "-pke"], env=env, text=True, timeout=5)
            x11 = ctypes.CDLL("libX11.so.6")
            xtst = ctypes.CDLL("libXtst.so.6")
            x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XFlush.argtypes = [ctypes.c_void_p]
            x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]

            def raw(name):
                # Xvfb has another decimal keysym outside the legacy keypad slot.
                lookup = "KP_Delete" if name == "KP_Decimal" else name
                matches = [int(row.split()[1]) for row in mapping.splitlines() if lookup in row.split()[3:]]
                require(len(matches) == 1, "ambiguous physical key mapping: " + name)
                result["events"].append(dict(kind="physical-keycode", key=name, lookup_keysym=lookup, code=matches[0],
                                             seconds=time.monotonic() - started))
                display = x11.XOpenDisplay(env["DISPLAY"].encode())
                require(display, "private X display unavailable")
                try:
                    for down in (1, 0):
                        require(xtst.XTestFakeKeyEvent(display, matches[0], down, 0), "raw key event failed")
                        x11.XFlush(display)
                        time.sleep(.025)
                finally:
                    x11.XCloseDisplay(display)

            def no_skip(name):
                image = capture(name)
                require(image.tobytes() != expected["italian-full"][len(HEADER):], name + " skipped typing")

            def no_change(language, name):
                require(full(language), name + " changed ready menu before Alt release")

            def keypad_noncharacters(prefix, check):
                for modifier, names in (("Alt_L", ("KP_Subtract", "KP_Add", "KP_Decimal", "KP_Multiply", "KP_Divide", "KP_Enter")),
                                        ("Control_L", ("KP_Subtract", "KP_Add", "KP_Decimal", "KP_Multiply", "KP_Divide"))):
                    key("keydown", modifier)
                    try:
                        for name in names:
                            raw(name)
                            check(prefix + "-" + modifier + "-" + name)
                    finally:
                        key("keyup", modifier)

            def compose(value, language):
                key("keydown", "Alt_L")
                for digit in str(value):
                    raw("KP_" + digit)
                    no_change(language, "Alt+" + str(value))

            def intro(image):
                colors = image.crop((0, 0, 320, 80)).getcolors(25600)
                return bool(colors and len(colors) == 7 and min(count for count, _ in colors) > 1000)

            def white(image):
                return sum(count for count, color in image.getcolors(64000) if color == (255, 255, 255))

            def intro_frame():
                image = frame()
                return image if intro(image) else None

            def natural_typing():
                image = frame()
                return image if image.tobytes() == expected["italian-line0-step06"][len(HEADER):] else None

            capture("natural-typing-checkpoint", wait(natural_typing))
            if scenario == "noncharacters":
                for i, value in enumerate(("1", "3", "4", "5", "7", "8", "9", "0", "equal",
                                           "semicolon", "apostrophe", "grave", "comma", "period", "slash")):
                    key("key", "ctrl+" + value)
                    no_skip("control-noncharacter-" + str(i))
                key("keydown", "Control_L")
                key("keydown", "1")
                try:
                    time.sleep(.9)
                    no_skip("held-control-one")
                finally:
                    key("keyup", "1")
                    key("keyup", "Control_L")
                for prefix in ("", "shift+", "ctrl+", "alt+"):
                    for function in ("F11", "F12"):
                        key("key", prefix + function)
                        no_skip("enhanced-" + prefix.replace("+", "-") + function)
                key("key", "alt+Tab")
                no_skip("alt-tab")
                for value in (0, 256):
                    key("keydown", "Alt_L")
                    for digit in str(value):
                        raw("KP_" + digit)
                    key("keyup", "Alt_L")
                    no_skip("alt-zero-" + str(value))
                raw("1")
                capture("fresh-one-consumed-skip", wait(full, 3))
            elif scenario == "intro":
                key("key", "ctrl+2")
                capture("control-two-consumed-skip", wait(full, 3))
            elif scenario == "keypad":
                keypad_noncharacters("menu", no_skip)
                raw("KP_Add")
                capture("unmodified-plus-consumed-skip", wait(full, 3))
            else:
                key("key", "space")
                capture("space-consumed-skip", wait(full, 3))
                time.sleep(.2)
                compose(108, "italian")
                capture("alt-108-held-no-character")
                key("keyup", "Alt_L")
                capture("alt-108-released-english", wait(lambda: full("english")))
                time.sleep(.2)
                compose(364, "english")
                key("keyup", "Alt_L")
                capture("alt-364-wrapped-italian", wait(full))
                time.sleep(.2)
                for value in (0, 256, 76):
                    compose(value, "italian")
                    key("keyup", "Alt_L")
                    time.sleep(.05)
                    no_change("italian", "Alt release " + str(value))
                compose(108, "italian")
                key("keydown", "Alt_R")
                key("keyup", "Alt_R")
                capture("first-alt-release-english", wait(lambda: full("english")))
                time.sleep(.2)
                for digit in "108":
                    raw("KP_" + digit)
                    no_change("english", "overlapping Alt cleared")
                key("keyup", "Alt_L")
                no_change("english", "second Alt release")
                capture("second-alt-release-no-duplicate")
                key("keydown", "Alt_L")
                for name in ("KP_1", "KP_Subtract", "KP_Add", "KP_Multiply", "KP_Divide", "KP_Enter", "KP_Decimal", "KP_8"):
                    raw(name)
                    no_change("english", "keypad decimal composition")
                capture("alt-decimal-held-no-character")
                key("keyup", "Alt_L")
                capture("alt-decimal-released-italian", wait(full))

            time.sleep(.2)
            raw("1")
            capture("fresh-one-intro", wait(intro_frame, 3))
            if scenario == "intro":
                for value in ("ctrl+1", "F11", "F12"):
                    key("key", value)
                image = capture("intro-noncharacters-ignored")
                require(intro(image) and white(image) < 620, "noncharacter skipped intro typing")
                key("keydown", "Alt_L")
                raw("KP_1")
                image = capture("intro-alt-one-held")
                require(intro(image) and white(image) < 620, "Alt digit skipped intro before release")
                key("keyup", "Alt_L")
                capture("intro-alt-release-consumed-skip", wait(lambda: intro_frame() if white(frame()) == 620 else None, 3))
                time.sleep(2.3)
                key("key", "ctrl+1")
                key("key", "F12")
                image = capture("intro-awaiting-fresh-character")
                require(intro(image) and white(image) == 620, "noncharacter acknowledged intro wait")
                key("key", "Return")
                wait(lambda: not intro(frame()), 3)
                capture("fresh-return-gameplay")
            elif scenario == "keypad":
                def ignored_intro(name):
                    image = capture(name)
                    require(intro(image) and white(image) < 620, "keypad word skipped intro typing")

                keypad_noncharacters("intro", ignored_intro)
                key("keydown", "Control_L")
                raw("KP_Enter")
                key("keyup", "Control_L")
                capture("control-keypad-enter-consumed-skip", wait(lambda: intro_frame() if white(frame()) == 620 else None, 3))
                time.sleep(2.3)

                def awaiting_intro(name):
                    image = capture(name)
                    require(intro(image) and white(image) == 620, "keypad word acknowledged intro wait")

                keypad_noncharacters("intro-wait", awaiting_intro)
                key("keydown", "Control_L")
                raw("KP_Enter")
                key("keyup", "Control_L")
                wait(lambda: not intro(frame()), 3)
                capture("fresh-control-keypad-enter-gameplay")
            for i in range(6):
                key("key", "Escape")
                time.sleep(2.3 if i == 0 else .2)
            require(child.wait(timeout=5) == 0, "normal app did not exit cleanly")
            result["status"] = "observed"
        except Exception as error:
            result.update(status="failed", error=str(error))
            if isinstance(error, subprocess.CalledProcessError):
                result["command_stderr"] = error.stderr
            raise
        finally:
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
    require(bool(os.environ.get("DISPLAY")), "private Xvfb required")
    _, expected = load_fixture()
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="lezac-bios-menu-", dir=args.out))
    results = [observe(args.exe.resolve(), output / scenario, scenario, expected)
               for scenario in ("noncharacters", "intro", "composition", "keypad")]
    (output / "result.json").write_text(json.dumps(dict(status="observed", cases=results), indent=2) + "\n")
    print("bios_menu_live=ok control_noncharacters=15 enhanced_cases=8 alt_release=1 alt_modulo=1"
          " alt_zero=1 alt_overlap=1 intro_noncharacters=1 intro_release=1 normal_entry_point=1"
          " audio=dummy gameplay_seeded=0 whole_game_parity=0 keypad_alt=6 keypad_control=5"
          " keypad_intro=1 alt_decimal_zero=1 out=" + str(output))


if __name__ == "__main__":
    main()
