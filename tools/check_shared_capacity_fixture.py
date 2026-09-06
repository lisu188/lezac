#!/usr/bin/env python3
"""Pin original pool-capacity captures and challenge their production replays."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    hashes = {
        "bomb": "ff86eb9de5bb95355e18e5ead64aa359a155d0a2f3ed5b66e5edb1019efefe27",
        "spawner": "91a763af3b4a56f3bc88bd651b1ea576be403c6a9b3f956ff4f04def1294b7f9",
    }
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    mutations = 0
    initial_files = set(root.glob("*.ppm"))
    with tempfile.TemporaryDirectory(prefix="lezac-shared-capacity-") as directory:
        fixture = Path(directory) / "fixture.txt"
        for mode, digest in hashes.items():
            source = (root / "tests/fixtures" / f"shared_capacity_{mode}_original.txt").read_text(encoding="ascii")
            if hashlib.sha256(source.encode("ascii")).hexdigest() != digest:
                raise RuntimeError(f"shared-capacity capture hash mismatch: {mode}")
            rows = source.splitlines()

            def run(content, valid):
                fixture.write_bytes(content.encode("ascii"))
                result = subprocess.run([str(args.exe.resolve()), "--debug-shared-capacity-original", str(fixture)],
                                        cwd=root, env=env, capture_output=True, text=True, timeout=60)
                output = result.stdout + result.stderr
                success = result.returncode == 0 and f"shared_capacity_original=ok mode={mode}" in output
                failure = result.returncode != 0 and "shared-capacity" in output and "shared_capacity_original=ok" not in output
                if not (success if valid else failure):
                    raise RuntimeError(f"expected_valid={valid}: {output}")

            run(source, True)
            run(source.replace("\n", "\r\n"), True)
            run("\n".join(row for row in rows if not row.startswith("complete ")) + "\n", False)

            def mutate(prefix, field, transform, occurrence=0):
                nonlocal mutations
                changed = rows.copy()
                index = [i for i, row in enumerate(changed) if row.startswith(prefix)][occurrence]
                tag, *tokens = changed[index].split()
                fields = dict(token.split("=", 1) for token in tokens)
                old = fields[field]
                fields[field] = transform(old)
                if fields[field] == old:
                    raise RuntimeError("no-op shared-capacity mutation")
                changed[index] = tag + " " + " ".join(f"{key}={value}" for key, value in fields.items())
                run("\n".join(changed) + "\n", False)
                mutations += 1

            def byte(value, offset):
                data = bytearray.fromhex(value)
                data[offset] ^= 1
                return data.hex()

            def actor(value, offset, visual=False, last=True):
                actors = value.split(",")
                index = -1 if last else 0
                pair = actors[index].split(":")
                pair[int(visual)] = byte(pair[int(visual)], offset)
                actors[index] = ":".join(pair)
                return ",".join(actors)

            for field in ("count", "visuals", "result", "frame", "selected", "fire"):
                mutate("after ", field, lambda value: str(int(value) + 1))
            mutate("after ", "rng", lambda value: byte(value, 0))
            mutate("after ", "inventory", lambda value: byte(value, 0))
            for offset in (9, 10, 27):
                mutate("after ", "spawner", lambda value, at=offset: byte(value, at))
            mutate("after ", "regs", lambda value: byte(value, 2))
            for offset in (0, 1, 6, 8, 10, 20, 21):
                mutate("after ", "actors", lambda value, at=offset: actor(value, at))
            for offset in (0, 2, 4):
                mutate("after ", "actors", lambda value, at=offset: actor(value, at, visual=True))
            mutate("after ", "actors", lambda value: actor(value, 2, last=False), occurrence=1)
            mutate("after ", "actors", lambda value: actor(value, 0, visual=True, last=False), occurrence=1)
            mutate("before ", "rng", lambda value: byte(value, 0))
            mutate("before ", "inventory", lambda value: byte(value, 0))
            mutate("case ", "count", lambda value: str(int(value) + 1))
            mutate("frame ", "frame", lambda value: str(int(value) + 1))
            mutate("complete ", "cases", lambda value: str(int(value) - 1))
            mutate("after ", "rng", lambda value: byte(value, 0), occurrence=2)
            mutate("after ", "inventory", lambda value: byte(value, 0), occurrence=2)
            if mode == "spawner":
                mutate("frame ", "count", lambda _: "30", occurrence=3)
                mutate("after ", "spawner", lambda value: byte(value, 27), occurrence=3)
    if set(root.glob("*.ppm")) != initial_files:
        raise RuntimeError("unrequested shared-capacity frame output")
    print(f"shared_capacity_fixture=ok captures=2 lf_crlf=1 truncated_rejected=2 mutations_rejected={mutations} no_output_files=1")


if __name__ == "__main__":
    main()
