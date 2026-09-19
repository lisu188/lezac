#!/usr/bin/env python3
"""Pin active-fire evidence and reject changed or incomplete replay inputs."""

import argparse
import copy
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

from check_reentry_wait_evidence import parse

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests/fixtures/active_fire_original_level1.txt"
SHA256 = "8808b7d195fd55523716cb7f83d2f0a167bb2caaa85aa4c0fb151b1cd231deba"


def serialize(rows):
    return "\n".join(tag + " " + " ".join(f"{k}={v}" for k, v in fields.items()) for tag, fields in rows) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    args = parser.parse_args()
    source = FIXTURE.read_text(encoding="ascii")
    if hashlib.sha256(source.encode("ascii")).hexdigest() != SHA256:
        raise RuntimeError("changed original active-fire capture")
    rows = parse(source)
    if len(rows) != 66 or sum(tag == "case" for tag, _ in rows) != 64:
        raise RuntimeError("incomplete original probes")
    env = dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy")
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="lezac-active-fire-") as directory:
        path = Path(directory) / "probe.txt"

        def run(text, valid=False):
            path.write_bytes(text.encode("ascii"))
            result = subprocess.run([str(args.exe.resolve()), "--debug-active-fire-original", str(path)],
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            output = result.stdout + result.stderr
            success = result.returncode == 0 and "active_fire_original=ok cases=64" in output
            rejected = result.returncode == 1 and "fatal:" in output and "active_fire_original=ok" not in output
            if not (success if valid else rejected):
                raise RuntimeError(f"valid={valid} status={result.returncode}: {output}")

        run(source, True)
        run(source.replace("\n", "\r\n"), True)

        def change(index, key, value):
            nonlocal mutations
            changed = copy.deepcopy(rows)
            changed[index][1][key] = value
            run(serialize(changed))
            mutations += 1

        for index in range(1, 65):
            change(index, "pool_after", str(int(rows[index][1]["pool_after"]) + 1))
        for index in (1, 33):
            for key in ("inventory_after", "keys_after"):
                changed = bytearray.fromhex(rows[index][1][key])
                changed[0] ^= 1
                change(index, key, changed.hex())
            for at in (0, 1, 2, 6, 8, 10, 12, 20, 21):
                changed = bytearray.fromhex(rows[index][1]["raw"])
                changed[at] ^= 1
                change(index, "raw", changed.hex())
            for at in (0, 2, 4, 5):
                changed = bytearray.fromhex(rows[index][1]["visual"])
                changed[at] ^= 1
                change(index, "visual", changed.hex())
            change(index, "weapon_after", "4")
        for index, key, value in ((0, "natural", "1"), (0, "cases", "63"),
                                  (1, "regs", "00"), (1, "player", "2"),
                                  (65, "whole_game_parity", "1")):
            change(index, key, value)
        for changed in (serialize(rows[:-1]), serialize(rows[:-2] + rows[-1:])):
            run(changed)
            mutations += 1
    print(f"active_fire_fixture=ok cases=64 mutations={mutations} newline_variants=2 silent_children=1")


if __name__ == "__main__":
    main()
