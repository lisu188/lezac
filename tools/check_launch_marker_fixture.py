#!/usr/bin/env python3
"""Pin original launch evidence and challenge the continuous production replay."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile


HASHES = {6: "7e24e0195ae87fae283b9d722eac48611e0c0636e786403952fabc069a5a22aa",
          7: "2490eea3cfd83f8601bafece71118230538d1a72c00d62ca0b69b1e89ad98946"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--level", type=int, choices=(6, 7), required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    source = (root / "tests/fixtures" / f"launch_marker_level{args.level}_original.txt").read_text(encoding="ascii")
    if hashlib.sha256(source.encode("ascii")).hexdigest() != HASHES[args.level]:
        raise RuntimeError("launch capture hash mismatch")
    rows = source.splitlines()
    views = 0
    for row in rows:
        if not row.startswith("view "):
            continue
        fields = dict(token.split("=", 1) for token in row.split()[1:])
        pixels = bytearray()
        for run in fields["pixels"].split(","):
            count, value = run.split(":")
            pixels.extend([int(value, 16)] * int(count))
        if len(pixels) != 312 * 152 or len(set(pixels)) < 16 or hashlib.sha256(pixels).hexdigest() != fields["indexed_sha256"]:
            raise RuntimeError("invalid launch pixels/hash")
        views += 1
    if views != 120:
        raise RuntimeError("incomplete launch views")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    before = set(root.glob("*.ppm"))
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="lezac-launch-") as directory:
        fixture = Path(directory) / "fixture.txt"

        def run(content, valid=False):
            fixture.write_bytes(content.encode("ascii"))
            result = subprocess.run([str(args.exe.resolve()), "--debug-launch-marker-original", str(fixture)],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=90)
            output = result.stdout + result.stderr
            success = result.returncode == 0 and f"launch_marker_original=ok level={args.level} cases=10 samples=120 views=120" in output
            failure = result.returncode != 0 and "launch-marker" in output and "launch_marker_original=ok" not in output
            if not (success if valid else failure):
                raise RuntimeError(f"expected_valid={valid}: {output}")

        run(source, True)
        run(source.replace("\n", "\r\n"), True)
        run("\n".join(rows[:-1]) + "\n")
        run("\n".join(rows[:len(rows) // 2]) + "\n")

        def mutate(prefix, field, transform, case=None):
            nonlocal mutations
            changed = rows.copy()
            start = next(i for i, row in enumerate(rows) if row.startswith(f"case name={case} ")) if case else 0
            index = next(i for i in range(start, len(rows)) if rows[i].startswith(prefix))
            tag, *tokens = changed[index].split()
            fields = dict(token.split("=", 1) for token in tokens)
            fields[field] = transform(fields[field])
            changed[index] = tag + " " + " ".join(f"{key}={value}" for key, value in fields.items())
            if changed == rows:
                raise RuntimeError("no-op launch mutation")
            run("\n".join(changed) + "\n")
            mutations += 1

        def byte(value, offset):
            data = bytearray.fromhex(value)
            data[offset] ^= 1
            return data.hex()

        def pixel(value):
            first, rest = value.split(",", 1)
            count, color = first.split(":")
            return f"{count}:{int(color, 16) ^ 15:02x},{rest}"

        for field in ("seeded_position", "seeded_pool", "temp_copy", "observed_backdrop"):
            mutate("capture=", field, lambda _: "0")
        mutate("capture=", "cached_gate_seed", lambda _: "1")
        mutate("capture=", "natural_route", lambda _: "1")
        mutate("sprites ", "descriptors", lambda value: byte(value, 364))
        mutate("backdrop ", "bytes", pixel)
        mutate("case ", "name", lambda _: "../outside")
        for field in ("frame", "initial_count", "pad_x", "pad_y", "x", "y"):
            mutate("case ", field, lambda value: str(int(value) + 1))
        mutate("case ", "entry", lambda value: byte(value, 10))
        for field in ("sample", "frame", "count", "visuals", "result"):
            mutate("tick ", field, lambda value: str(int(value) + 1))
        for field in ("sound_snapshot", "normalized"):
            mutate("tick ", field, lambda value: byte(value, 0))
        mutate("tick ", "response", lambda value: byte(value, 44))
        mutate("tick ", "edges", lambda value: byte(value, 13))
        mutate("tick ", "pre", lambda value: byte(value, 24))
        mutate("tick ", "before_regs", lambda value: byte(value, 2))
        mutate("tick ", "after_regs", lambda value: byte(value, 6))
        mutate("tick sample=1 ", "entry", lambda value: byte(value, 12), "fraction_even")
        for offset in (0, 2, 8, 12, 20, 21, 27):
            mutate("tick ", "actors", lambda value, at=offset: byte(value.split(":")[0], at) + ":" + value.split(":")[1])
        for offset in (0, 2, 4):
            mutate("tick ", "actors", lambda value, at=offset: value.split(":")[0] + ":" + byte(value.split(":")[1], at))
        mutate("tick ", "result", lambda _: "1", "pool30_even")
        mutate("tick ", "sound_snapshot", lambda _: "-", "pool30_even")
        for field in ("sample", "frame", "coarse_x", "coarse_y", "fine_x", "fine_y", "source", "destination"):
            mutate("view ", field, lambda value: str(int(value) + 1))
        mutate("view ", "player", lambda value: byte(value, 0))
        mutate("view ", "player", lambda value: byte(value, 4))
        mutate("view ", "pixels", pixel)
        for value in ("1:00", "999999:00", "-1:00", "1:gg"):
            mutate("view ", "pixels", lambda _, replacement=value: replacement)
        mutate("view sample=8 ", "pixels", pixel, "pool0_odd")
        mutate("view sample=9 ", "pixels", pixel, "fraction_odd")
        mutate("complete ", "views", lambda _: "119")
        index = next(i for i, row in enumerate(rows) if row.startswith("tick "))
        for changed in (rows[:index] + rows[index + 1:], rows + [rows[index]],
                        rows[:index] + [rows[index] + " extra=1"] + rows[index + 1:],
                        rows[:index] + [rows[index] + " sample=0"] + rows[index + 1:]):
            run("\n".join(changed) + "\n")
            mutations += 1
    if set(root.glob("*.ppm")) != before:
        raise RuntimeError("unrequested launch frame output")
    print(f"launch_marker_fixture=ok level={args.level} views=120 lf_crlf=1 truncated_rejected=2 mutations_rejected={mutations} indexed_hashes=120 no_output_files=1")


if __name__ == "__main__":
    main()
