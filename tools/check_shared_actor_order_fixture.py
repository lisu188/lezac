#!/usr/bin/env python3
"""Pin the original ordered actor passes and challenge the production replay."""

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
    source = (root / "tests/fixtures/shared_actor_order_original.txt").read_text(encoding="ascii")
    digest = "765b724713778f7fa86e7df8fe7812de9e40b029cf85b46bc6e25ed9ecdd6e4e"
    if hashlib.sha256(source.encode("ascii")).hexdigest() != digest:
        raise RuntimeError("shared-order capture hash mismatch")
    rows = source.splitlines()
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    initial_files = set(root.glob("*.ppm"))
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="lezac-shared-order-") as directory:
        fixture = Path(directory) / "fixture.txt"

        def run(content, valid):
            fixture.write_bytes(content.encode("ascii"))
            result = subprocess.run([str(args.exe.resolve()), "--debug-shared-actor-order-original", str(fixture)],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=60)
            output = result.stdout + result.stderr
            success = result.returncode == 0 and "shared_actor_order_original=ok cases=10 samples=410 actor_states=7685" in output
            failure = result.returncode != 0 and "shared-order" in output and "shared_actor_order_original=ok" not in output
            if not (success if valid else failure):
                raise RuntimeError(f"expected_valid={valid}: {output}")

        run(source, True)
        run(source.replace("\n", "\r\n"), True)
        run("\n".join(rows[:-1]) + "\n", False)
        run("\n".join(rows[:len(rows) // 2]) + "\n", False)

        def mutate(prefix, field, transform, occurrence=0):
            nonlocal mutations
            changed = rows.copy()
            index = [i for i, row in enumerate(changed) if row.startswith(prefix)][occurrence]
            tag, *tokens = changed[index].split()
            fields = dict(token.split("=", 1) for token in tokens)
            old = fields[field]
            fields[field] = transform(old)
            if fields[field] == old:
                raise RuntimeError("no-op shared-order mutation")
            changed[index] = tag + " " + " ".join(f"{key}={value}" for key, value in fields.items())
            run("\n".join(changed) + "\n", False)
            mutations += 1

        def byte(value, offset):
            data = bytearray.fromhex(value)
            data[offset] ^= 1
            return data.hex()

        def actor(value, offset, visual=False, last=False):
            actors = value.split(",")
            index = -1 if last else 0
            pair = actors[index].split(":")
            pair[int(visual)] = byte(pair[int(visual)], offset)
            actors[index] = ":".join(pair)
            return ",".join(actors)

        for field in ("sample", "frame", "count", "visuals"):
            mutate("tick ", field, lambda value: str(int(value) + 1))
        for offset in range(0, 12, 2):
            mutate("tick ", "regs", lambda value, at=offset: byte(value, at))
            mutate("case ", "regs", lambda value, at=offset: byte(value, at))
        for offset in (0, 1, 2, 6, 8, 10, 11, 12, 13, 20, 21):
            mutate("tick ", "actors", lambda value, at=offset: actor(value, at))
        for offset in (0, 2, 4):
            mutate("tick ", "actors", lambda value, at=offset: actor(value, at, visual=True))
        for offset in (0, 2, 6, 8, 10, 12, 20, 21, 22, 23, 24, 25, 26, 27, 28):
            mutate("tick ", "actors", lambda value, at=offset: actor(value, at, last=True), occurrence=123)
        for offset in (0, 2, 4):
            mutate("tick ", "actors", lambda value, at=offset: actor(value, at, visual=True, last=True), occurrence=123)
        for occurrence in (0, 82, 123, 164, 205, 246, 287, 328, 369, 409):
            mutate("tick ", "rng", lambda value: byte(value, 0), occurrence=occurrence)
        for occurrence in (82, 123, 164, 205):
            mutate("tick ", "count", lambda value: str(int(value) + 1), occurrence=occurrence)
        mutate("tick ", "actors", lambda value: ",".join(reversed(value.split(","))))
        mutate("tick ", "map", lambda _: "0:ff")
        mutate("case ", "frame", lambda _: "102")
        mutate("case ", "rng", lambda _: "12345679")
        mutate("case ", "samples", lambda _: "40")
        mutate("case ", "name", lambda _: "unknown")
        mutate("case ", "actors", lambda value: actor(value, 6, last=True))
        mutate("end ", "samples", lambda _: "40")
        mutate("complete ", "samples", lambda _: "409")
        mutate("complete ", "cases", lambda _: "9")
        mutate("capture=", "seeded", lambda _: "0")
        mutate("capture=", "temp_copy", lambda _: "0")

        first_tick = next(i for i, row in enumerate(rows) if row.startswith("tick "))
        malformed = [
            rows[:first_tick] + rows[first_tick + 1:],
            rows[:first_tick] + [rows[first_tick]] + rows[first_tick:],
            rows + [rows[first_tick]],
            rows[:first_tick] + [rows[first_tick] + " extra=1"] + rows[first_tick + 1:],
            rows[:first_tick] + [rows[first_tick] + " sample=0"] + rows[first_tick + 1:],
        ]
        for changed in malformed:
            run("\n".join(changed) + "\n", False)
            mutations += 1
    if set(root.glob("*.ppm")) != initial_files:
        raise RuntimeError("unrequested shared-order frame output")
    print(f"shared_actor_order_fixture=ok cases=10 samples=410 lf_crlf=1 truncated_rejected=2 mutations_rejected={mutations} no_output_files=1")


if __name__ == "__main__":
    main()
