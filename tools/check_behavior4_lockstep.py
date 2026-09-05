#!/usr/bin/env python3
"""Reject corrupt or incomplete behavior-4 evidence through the C++ replay."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

import capture_original_behavior4_lockstep as capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    fixture = root / "tests/fixtures/behavior4_lockstep_original_level3.txt"
    original = fixture.read_text(encoding="ascii")
    # Hash normalized newlines so Windows Git's CRLF conversion is harmless.
    assert hashlib.sha256(original.encode("ascii")).hexdigest() == (
        "d2bd2d27b298950ccb4ad40aeace8e543f3eed3c13b03f82ffdaf92e9cf77d59"
    )
    horizontal = fixture.with_name("behavior4_lockstep_original_level3_horizontal.txt")
    assert hashlib.sha256(horizontal.read_text(encoding="ascii").encode("ascii")).hexdigest() == (
        "d5258bcc3464351324c257e72cb52666a0ca28e85ef9da3f74bb5a0d34ff9e4a"
    )
    capture.self_check(root / "LEZAC.EXE")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    cases = [
        (original.replace(" fx=0", "", 1), "missing behavior4 tick field"),
        (original.replace(" fx=0", " fx=0 fx=0", 1), "duplicate behavior4 tick key"),
        (original.replace(" vx=0", " vx=1", 1), "disagree with raw actor"),
        (original.replace(" x=352", " x=352bad", 1), "invalid behavior4 integer"),
        (original.replace("tick 299 ", "tick 300 ", 1), "frames are not consecutive"),
        (original.replace("phase=natural_far", "phase=seeded_near", 1), "phase sequence mismatch"),
        (original.replace("visual_claim=0", "visual_claim=1", 1), "header mismatch"),
    ]
    with tempfile.TemporaryDirectory(prefix="lezac-behavior4-check-") as directory:
        path = Path(directory) / "invalid.txt"
        for content, reason in cases:
            assert content != original
            path.write_text(content, encoding="ascii")
            result = subprocess.run(
                [str(args.exe.resolve()), "--debug-behavior4-lockstep-evidence", str(path)],
                cwd=root, env=env, capture_output=True, text=True, timeout=30,
            )
            assert result.returncode != 0 and reason in result.stderr, (
                reason, result.returncode, result.stdout, result.stderr
            )
    print(f"behavior4_lockstep_guard=ok malformed={len(cases)} capture_hash=verified static_windows=6")


if __name__ == "__main__":
    main()
