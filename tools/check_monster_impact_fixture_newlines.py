#!/usr/bin/env python3
"""Replay the impact-sprite evidence with both Git checkout newline formats."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    fixture = root / "tests/fixtures/monster_impact_sprites_original_level1.txt"
    content = fixture.read_text(encoding="ascii")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    with tempfile.TemporaryDirectory(prefix="lezac-impact-newlines-") as directory:
        path = Path(directory) / "fixture.txt"
        for newline in ("\n", "\r\n"):
            path.write_bytes(content.replace("\n", newline).encode("ascii"))
            result = subprocess.run(
                [str(args.exe.resolve()), "--debug-monster-impact-sprites", str(path)],
                cwd=root, env=env, capture_output=True, text=True, timeout=30,
            )
            if result.returncode or "monster_impact_sprites=ok" not in result.stdout:
                raise RuntimeError(f"newline={newline!r}: {result.stdout}{result.stderr}")
    print("monster_impact_fixture_newlines=ok lf=1 crlf=1")


if __name__ == "__main__":
    main()
