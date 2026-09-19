#!/usr/bin/env python3
"""Pin the original prepass evidence and reject changed/truncated replay inputs."""

import argparse
import copy
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

from check_reentry_wait_evidence import parse


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests/fixtures/state2_prepass_original_level1.txt"
SHA256 = "bf65110c9ce3621102c0b0c3681973b2665a23ade5a3735cf8ad7e48c1eb4fc5"


def serialize(rows):
    return "\n".join(tag + " " + " ".join(f"{k}={v}" for k, v in fields.items()) for tag, fields in rows) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    args = parser.parse_args()
    source = FIXTURE.read_text(encoding="ascii")
    if hashlib.sha256(source.encode("ascii")).hexdigest() != SHA256:
        raise RuntimeError("changed original state2 prepass capture")
    rows = parse(source)
    if len(rows) != 57 or sum(tag == "case" for tag, _ in rows) != 54:
        raise RuntimeError("incomplete original probe")
    env = dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy")
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="lezac-prepass-") as directory:
        path = Path(directory) / "probe.txt"

        def run(text, valid=False):
            path.write_bytes(text.encode("ascii"))
            result = subprocess.run([str(args.exe.resolve()), "--debug-state2-prepass-original", str(path)],
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            output = result.stdout + result.stderr
            success = result.returncode == 0 and "state2_prepass_original=ok cases=54" in output
            rejected = result.returncode == 1 and "fatal:" in output and "state2_prepass_original=ok" not in output
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

        for index in range(2, 56):
            visual = bytearray.fromhex(rows[index][1]["visual_after"])
            visual[2] ^= 1
            change(index, "visual_after", visual.hex())
        for index in (2, 29):
            for field in ("after", "visual_after", "inventory_after", "states", "keys", "regs"):
                original = bytes.fromhex(rows[index][1][field])
                for offset in range(len(original)):
                    mutated = bytearray(original)
                    mutated[offset] ^= 1
                    change(index, field, mutated.hex())
            for field in ("lives", "gate_after", "counter"):
                change(index, field, str(int(rows[index][1][field]) + 1))
        for index, key, value in ((0, "seeded", "0"), (0, "natural", "1"), (0, "cases", "53"),
                                  (0, "hooks", "7c3d,7ec5"), (1, "width", "59"),
                                  (2, "before", "00"), (2, "extra", "1"), (2, "player", "2"),
                                  (56, "whole_game_parity", "1"), (56, "cases", "53")):
            change(index, key, value)
        for changed in (serialize(rows[:-1]), serialize(rows[:-2] + rows[-1:]),
                        source + rows[2][0] + " extra=1\n", source.replace("player=1", "player=1 player=1", 1)):
            run(changed)
            mutations += 1
    print(f"state2_prepass_fixture=ok cases=54 mutations={mutations} newline_variants=2 silent_children=1 whole_game_parity=0")


if __name__ == "__main__":
    main()
