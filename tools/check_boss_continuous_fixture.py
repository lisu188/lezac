#!/usr/bin/env python3
"""Pin the original continuous boss trace and reject incomplete/corrupt replays."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--near", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    filename = "boss_continuous_near_original_level7.txt" if args.near else "boss_continuous_original_level7.txt"
    expected_hash = "01e2f3a9ba39081afabbe2efc4d109f023459f84f48c96093c0db9db3bf3c0ce" if args.near else "feed00ccbe888044caa5bcd5c00a66db5edf5ec425feacb6a2766591a53b066a"
    source = (root / "tests/fixtures" / filename).read_text(encoding="ascii")
    if hashlib.sha256(source.encode("ascii")).hexdigest() != expected_hash:
        raise RuntimeError("original boss capture hash mismatch")
    rows = source.splitlines()
    views = 0
    for row in rows:
        if not row.startswith("view "):
            continue
        fields = dict(token.split("=", 1) for token in row.split()[1:])
        pixels = bytearray()
        for run in fields["pixels"].split(","):
            count, color = run.split(":")
            pixels.extend([int(color, 16)] * int(count))
        if len(pixels) != 312 * 152 or len(set(pixels)) < 16 or hashlib.sha256(pixels).hexdigest() != fields["indexed_sha256"]:
            raise RuntimeError("original boss indexed view/hash mismatch")
        views += 1
    if views != 30:
        raise RuntimeError("incomplete original boss views")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    before = set(root.glob("*.ppm"))
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="lezac-boss-") as directory:
        fixture = Path(directory) / "fixture.txt"

        def run(text, valid=False):
            fixture.write_bytes(text.encode("ascii"))
            result = subprocess.run([str(args.exe.resolve()), "--debug-boss-continuous-original", str(fixture)],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=90)
            output = result.stdout + result.stderr
            success = result.returncode == 0 and "boss_continuous_original=ok cases=3 samples=600" in output
            failure = result.returncode != 0 and "boss-continuous" in output and "boss_continuous_original=ok" not in output
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
                raise RuntimeError("no-op boss mutation")
            run("\n".join(changed) + "\n")
            mutations += 1

        def byte(value, at):
            raw = bytearray.fromhex(value)
            raw[at] ^= 1
            return raw.hex()

        def pixel(value):
            first, rest = value.split(",", 1)
            count, color = first.split(":")
            return f"{count}:{int(color, 16) ^ 15:02x},{rest}"

        def actor(value, index, part, offset):
            actors = value.split(",")
            parts = actors[index].split(":")
            parts[part] = byte(parts[part], offset)
            actors[index] = ":".join(parts)
            return ",".join(actors)

        for field in ("temp_copy", "seeded_case_boundary", "observed_backdrop"):
            mutate("capture=", field, lambda _: "0")
        for field in ("per_tick_actor_seed", "natural_campaign"):
            mutate("capture=", field, lambda _: "1")
        mutate("case ", "name", lambda _: "../outside")
        mutate("case ", "frame", lambda _: "99")
        mutate("case ", "regs", lambda v: byte(v, 2))
        mutate("sprites ", "descriptors", lambda v: byte(v, 160))
        mutate("backdrop ", "bytes", pixel)
        for field in ("sample", "frame", "count", "visuals", "link_count", "energy", "lives"):
            mutate("tick ", field, lambda v: str(int(v) + 1))
        mutate("tick ", "control", lambda _: "left")
        for field in ("rng", "regs", "input_regs"):
            mutate("tick ", field, lambda v: byte(v, 0))
        for offset in (0, 6, 8, 10, 12, 14, 22, 25, 29):
            mutate("tick ", "p1", lambda v, at=offset: byte(v, at))
        for offset in (0, 2, 4):
            mutate("tick ", "player", lambda v, at=offset: byte(v, at))
        for offset in (0, 2, 3, 4, 5, 6, 7, 9, 11, 13, 15):
            mutate("tick ", "links", lambda v, at=offset: byte(v, at))
        for offset in (0, 1, 2, 6, 8, 10, 12, 14, 15, 20, 21, 22, 25, 26, 27, 28, 36):
            mutate("tick ", "actors", lambda v, at=offset: actor(v, 0, 0, at))
        for offset in (0, 2, 4):
            mutate("tick ", "actors", lambda v, at=offset: actor(v, 0, 1, at))
        mutate("tick ", "actors", lambda v: actor(v, 1, 0, 14))
        mutate("tick ", "actors", lambda v: actor(v, 6, 1, 2))
        mutate("tick sample=15 ", "actors", lambda v: actor(v, 7, 0, 2), "approach")
        mutate("tick sample=199 ", "rng", lambda v: byte(v, 0), "clock_wrap")
        mutate("tick ", "map", lambda _: "0:ff")
        for field in ("coarse_x", "coarse_y", "fine_x", "fine_y", "source", "destination"):
            mutate("view ", field, lambda v: str(int(v) + 1))
        mutate("view ", "pixels", pixel)
        mutate("view ", "pixels", lambda _: "1:00")
        mutate("view ", "pixels", lambda _: "999999:00")
        mutate("view ", "pixels", lambda _: "-1:00")
        mutate("view ", "pixels", lambda _: "1:gg")
        mutate("view sample=199 ", "pixels", pixel, "clock_wrap")
        mutate("complete ", "samples", lambda _: "599")
        index = next(i for i, row in enumerate(rows) if row.startswith("tick "))
        for changed in (rows[:index] + rows[index + 1:], rows + [rows[index]],
                        rows[:index] + [rows[index] + " extra=1"] + rows[index + 1:],
                        rows[:index] + [rows[index] + " sample=0"] + rows[index + 1:]):
            run("\n".join(changed) + "\n")
            mutations += 1
    if set(root.glob("*.ppm")) != before:
        raise RuntimeError("unrequested boss frame output")
    print(f"boss_continuous_fixture=ok near={int(args.near)} cases=3 samples=600 indexed_hashes={views} lf_crlf=1 truncations_rejected=2 mutations_rejected={mutations} no_output_files=1")


if __name__ == "__main__":
    main()
