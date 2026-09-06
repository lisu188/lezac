#!/usr/bin/env python3
"""Pin original palette evidence and reject phase, DAC, pixel and coverage mutations."""

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
        "red_palette_level1_original.txt": "82cdf7be2f6868830e001e0944dfcf833bbc0014c94c644e47bc1ea77917a5d0",
        "red_palette_level4_original.txt": "cede678ae46c44f4a8050c46ce7bf012b393b9abcf430282d306fa25289471eb",
    }
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    initial_files = set(root.glob("*.ppm"))
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="lezac-red-palette-") as directory:
        fixture = Path(directory) / "fixture.txt"
        for name, digest in hashes.items():
            source = (root / "tests/fixtures" / name).read_text(encoding="ascii")
            if hashlib.sha256(source.encode("ascii")).hexdigest() != digest:
                raise RuntimeError(f"palette capture hash mismatch: {name}")
            rows = source.splitlines()
            view = next(row for row in rows if row.startswith("view "))
            encoded = dict(token.split("=", 1) for token in view.split()[1:])["pixels"]
            pixels = bytearray()
            for run in encoded.split(","):
                count, value = run.split(":")
                pixels.extend([int(value, 16)] * int(count))
            if len(pixels) != 312 * 152 or len(set(pixels)) < 16:
                raise RuntimeError("missing varied original indexed view")
            pixel_hash = hashlib.sha256(pixels).hexdigest()
            for row in rows:
                if row.startswith("sample "):
                    fields = dict(token.split("=", 1) for token in row.split()[1:])
                    if fields["indexed_sha256"] != pixel_hash:
                        raise RuntimeError("original indexed-view hash mismatch")

            def run(content, error=None):
                fixture.write_bytes(content.encode("ascii"))
                result = subprocess.run([str(args.exe.resolve()), "--debug-red-palette-original", str(fixture)],
                                        cwd=root, env=env, capture_output=True, text=True, timeout=90)
                output = result.stdout + result.stderr
                valid = (result.returncode == 0 and "red_palette_original=ok cases=4 samples=122" in output
                         and "actual_dac=1" in output and "whole_game_parity=0" in output) if error is None else (
                             result.returncode != 0 and error in output and "red_palette_original=ok" not in output)
                if not valid:
                    raise RuntimeError(f"expected={error or 'success'}: {output}")

            run(source)
            run(source.replace("\n", "\r\n"))
            run("\n".join(row for row in rows if not row.startswith("complete ")) + "\n", "missing palette completion")

            def mutate(prefix, field, transform, error):
                nonlocal mutations
                changed = rows.copy()
                index = next(i for i, row in enumerate(changed) if row.startswith(prefix))
                fields = dict(token.split("=", 1) for token in changed[index].split()[1:])
                value = transform(fields[field])
                if value == fields[field]:
                    raise RuntimeError("palette mutation is a no-op")
                fields[field] = value
                changed[index] = changed[index].split()[0] + " " + " ".join(f"{key}={value}" for key, value in fields.items())
                run("\n".join(changed) + "\n", error)
                mutations += 1

            def change_byte(value, index):
                data = bytearray.fromhex(value)
                data[index] ^= 15
                return data.hex()

            def change_pixel(value):
                first, rest = value.split(",", 1)
                count, pixel = first.split(":")
                return f"{count}:{int(pixel, 16) ^ 15:02x},{rest}"

            first = "sample case=continuous index=0 "
            second = "sample case=continuous index=1 "
            mutate(first, "before_phase", lambda value: str(int(value) ^ 15), "pre-phase mismatch")
            mutate(first, "after_phase", lambda value: str(int(value) ^ 15), "post-phase mismatch")
            for field in ("before_dac", "after_dac"):
                mutate(first, field, lambda value: change_byte(value, 690), "DAC mismatch")
                mutate(first, field, lambda value: "ff" + value[2:], "invalid six-bit palette DAC")
            mutate(second, "frame", lambda value: str(int(value) + 1), "nonconsecutive palette sample")
            mutate(second, "index", lambda _: "0", "nonconsecutive palette sample")
            mutate(second, "indexed_sha256", lambda _: "0" * 64, "indexed view changed")
            mutate(first, "after_regs", lambda value: change_byte(value, 2), "register mismatch")
            mutate("case name=frame_wrap ", "phase", lambda _: "61", "invalid palette case seed")
            mutate("case name=frame_wrap ", "frame", lambda _: "65519", "invalid palette case seed")
            mutate("case name=continuous ", "samples", lambda _: "70", "invalid palette case seed")
            mutate("view ", "x", lambda value: str(int(value) + 1), "invalid palette view")
            mutate("view ", "pixels", lambda _: "47424:00", "lacks gameplay variation")
            mutate("view ", "pixels", lambda value: "1:00," + value, "palette run overflow")
            mutate("view ", "pixels", lambda _: "1:00", "truncated palette pixels")
            mutate("view ", "pixels", change_pixel, "red palette pixel mismatches")
            mutate(first, "after_dac", lambda value: change_byte(value, 528), "red palette pixel mismatches")
            mutate("sprites ", "descriptors", lambda value: change_byte(value, 4), "sprite descriptor mismatch")
            mutate("complete ", "samples", lambda _: "121", "incomplete palette coverage")
    if set(root.glob("*.ppm")) != initial_files:
        raise RuntimeError("palette replay wrote unrequested frames")
    print(f"red_palette_fixture=ok captures=2 lf_crlf=1 truncated_rejected=2 mutations_rejected={mutations} indexed_hashes=1 no_output_files=1")


if __name__ == "__main__":
    main()
