#!/usr/bin/env python3
"""Pin original key-bank evidence and exercise the C++ replay's rejection paths."""

import argparse
import copy
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

from check_reentry_wait_evidence import parse

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests/fixtures/key_ownership_original_level1.txt"
SHA256 = "27fbe55858af359ddc8c4f8c01cbeaf9cd45b1ea4589c940b2aeb0b47a866ab4"


def serialize(rows):
    return "\n".join(tag + " " + " ".join(f"{k}={v}" for k, v in fields.items()) for tag, fields in rows) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    args = parser.parse_args()
    source = FIXTURE.read_text(encoding="ascii")
    if hashlib.sha256(source.encode("ascii")).hexdigest() != SHA256:
        raise RuntimeError("changed original key-ownership capture")
    rows = parse(source)
    if len(rows) != 86 or sum(tag == "sample" for tag, _ in rows) != 84:
        raise RuntimeError("incomplete original samples")
    env = dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy")
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="lezac-key-ownership-") as directory:
        path = Path(directory) / "probe.txt"

        def run(text, valid=False):
            path.write_bytes(text.encode("ascii"))
            result = subprocess.run([str(args.exe.resolve()), "--debug-key-ownership-original", str(path)],
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            output = result.stdout + result.stderr
            success = result.returncode == 0 and "key_ownership_original=ok cases=21 samples=84" in output
            rejected = result.returncode == 1 and "fatal:" in output and "key_ownership_original=ok" not in output
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

        for index in range(1, 85):
            value = bytearray.fromhex(rows[index][1]["normalized"])
            value[(index - 1) % 5] ^= 1
            change(index, "normalized", value.hex())
        for key in ("hardware", "normalized", "actor", "visual", "regs"):
            change(1, key, "00")
        for offset in range(10):
            value = bytearray.fromhex(rows[1][1]["hardware"])
            value[offset] ^= 1
            change(1, "hardware", value.hex())
        for index, key, value in ((0, "physical_keys", "0"), (0, "actor_seeded", "1"),
                                  (0, "ammo_seeded", "0"), (0, "hooks", "0000,0000"),
                                  (1, "case", "1"), (1, "keys", "Up"), (1, "phase", "break"),
                                  (1, "player", "2"), (2, "frame", "0"),
                                  (85, "whole_game_parity", "1")):
            change(index, key, value)
        for changed in (serialize(rows[:-1]), serialize(rows[:-2] + rows[-1:]),
                        serialize(rows + rows[-1:]), serialize(rows[:1] + rows[2:]),
                        source.replace("case=0", "case=0 case=0", 1)):
            run(changed)
            mutations += 1
    print(f"key_ownership_fixture=ok cases=21 samples=84 mutations={mutations} newline_variants=2 silent_children=1")


if __name__ == "__main__":
    main()
