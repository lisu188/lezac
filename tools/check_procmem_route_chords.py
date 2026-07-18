#!/usr/bin/env python3
"""Check chord parsing and xdotool ordering in the process-memory route helper."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from types import ModuleType


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_capture_helper(path: Path) -> ModuleType:
    name = "capture_original_explosion_procmem_chord_check"
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    sys.modules[name] = module
    source = path.read_text(encoding="utf-8")
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check process-memory route chord parsing and key ordering."
    )
    parser.add_argument(
        "repo_root", nargs="?", type=Path, default=default_repo_root()
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    helper = load_capture_helper(root / "tools" / "capture_original_explosion_procmem.py")

    step = helper.parse_route_step(" z + x :0.50")
    if step.key != "z+x" or step.seconds != 0.5:
        raise RuntimeError(f"unexpected parsed chord: {step!r}")

    commands: list[list[str]] = []
    sleeps: list[float] = []
    activations: list[tuple[dict[str, str], str]] = []

    helper.activate_window = lambda env, window: activations.append((env, window))
    helper.run = lambda command, env, check=True: commands.append(command) or ""
    helper.time.sleep = sleeps.append
    env = {"DISPLAY": ":99"}
    helper.hold_key(env, "123", step.key, step.seconds)

    expected_commands = [
        ["xdotool", "keydown", "z"],
        ["xdotool", "keydown", "x"],
        ["xdotool", "keyup", "x"],
        ["xdotool", "keyup", "z"],
    ]
    if commands != expected_commands:
        raise RuntimeError(f"unexpected chord command order: {commands!r}")
    if sleeps != [0.5, 0.15]:
        raise RuntimeError(f"unexpected chord sleeps: {sleeps!r}")
    if activations != [(env, "123")]:
        raise RuntimeError(f"unexpected chord window activation: {activations!r}")

    invalid = ["+x:0.5", "z+:0.5", "z++x:0.5"]
    for value in invalid:
        try:
            helper.parse_route_step(value)
        except argparse.ArgumentTypeError as exc:
            if "chord keys must not be empty" not in str(exc):
                raise RuntimeError(f"unexpected malformed-chord error: {exc}") from exc
        else:
            raise RuntimeError(f"malformed chord unexpectedly parsed: {value}")

    print(
        "procmem_route_chords=ok chord=z+x hold_seconds=0.5 "
        "keydown=z,x keyup=x,z invalid=3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
