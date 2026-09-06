#!/usr/bin/env python3
"""Pin render evidence and reject pixel, camera, and coverage mutations."""

import argparse
import hashlib
from itertools import groupby
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
        "render_boundary_original.txt": "e247440fadfdf9a5220a9363e0455ac6b34dd8ea9334fdebf64b583ca716e929",
        "render_boundary_split_original.txt": "3c8b344a1de502abaea5de4add845485d61322f8c8c9df5ee06baea85c880e12",
        "render_boundary_tall_level3_original.txt": "532c62a4e23619a574514d58b7427c9e3bf7ee7ff52dc955e7b114d34a00cf2a",
        "render_boundary_tall_level4_original.txt": "745c443754b451b8c08086da33b07c026002ad0d32b23f52f857b8315e27cb73",
        "render_boundary_tall_level5_original.txt": "70d39de38ab750fe0885de24ab34170844fa67d1ba79d65e2ece035f21051dec",
        "render_boundary_tall_level6_original.txt": "fe8c42e872618db6b4b32ef2e784490acae9ba0b6efc45a488b735e18127910f",
        "render_boundary_tall_level3_split_original.txt": "b18f3a41d53d756dc576154a8651deabcd46369ae052532b4847a9357ecbbcd3",
    }
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    initial_files = set(root.glob("*.ppm"))
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="lezac-render-fixture-") as directory:
        fixture = Path(directory) / "fixture.txt"
        for name, digest in hashes.items():
            source = (root / "tests/fixtures" / name).read_text(encoding="ascii")
            if hashlib.sha256(source.encode("ascii")).hexdigest() != digest:
                raise RuntimeError(f"capture hash mismatch: {name}")
            width = 152 if "split" in name else 312
            tall = "tall" in name
            alias_probe = "capture=render_boundary_tall_original_v2 " in source
            views = (15 if alias_probe else 13) if tall else 30

            def run(content, error=None):
                fixture.write_bytes(content.encode("ascii"))
                result = subprocess.run([str(args.exe.resolve()), "--debug-render-boundary-original", str(fixture)],
                                        cwd=root, env=env, capture_output=True, text=True, timeout=90)
                output = result.stdout + result.stderr
                valid = (result.returncode == 0 and f"render_boundary_original=ok views={views} width={width}" in output
                         and "whole_game_parity=0" in output) if error is None else (
                             result.returncode != 0 and error in output and "render_boundary_original=ok" not in output)
                if not valid:
                    raise RuntimeError(f"expected={error or 'success'}: {output}")

            run(source)
            run(source.replace("\n", "\r\n"))
            rows = source.splitlines()
            run("\n".join(row for row in rows if not row.startswith("complete ")) + "\n",
                "missing render-boundary completion")

            def mutate(prefix, field, transform, error):
                nonlocal mutations
                changed = rows.copy()
                index = next(i for i, row in enumerate(changed) if row.startswith(prefix))
                fields = dict(token.split("=", 1) for token in changed[index].split()[1:])
                value = transform(fields[field])
                if value == fields[field]:
                    raise RuntimeError("fixture mutation is a no-op")
                fields[field] = value
                changed[index] = changed[index].split()[0] + " " + " ".join(f"{key}={value}" for key, value in fields.items())
                run("\n".join(changed) + "\n", error)
                mutations += 1

            def change_pixel(value):
                first, rest = value.split(",", 1)
                count, pixel = first.split(":")
                return f"{count}:{int(pixel, 16) ^ 15:02x},{rest}"

            first = "view name=upper " if tall else "view name=minimum "
            shake = "view name=clear_bottom_shake " if tall else "view name=shake_fine_carry "
            mutate(first, "pixels", change_pixel, "pixel mismatches")
            mutate(first, "pixels", lambda _: "999999:00", "run overflow")
            mutate(first, "pixels", lambda _: "1:00", "truncated render-boundary pixels")
            mutate("view name=spawn ", "frame", lambda value: str(int(value) + 1), "nonconsecutive")
            mutate("view name=spawn ", "coarse_x", lambda value: str(int(value) + 8), "camera/driver mismatch")
            mutate(shake, "fine_x", lambda _: "6", "camera/driver mismatch")
            mutate(shake, "shake", lambda _: "-1", "invalid render-boundary shake")
            mutate(first, "backdrop_stride", lambda _: "1", "camera/driver mismatch")
            mutate(first, "after_regs", lambda value: value[:8] + "0000" + value[12:], "segment mismatch")
            mutate(first, "source", lambda _: "0", "invalid render-boundary view")
            mutate(first, "name", lambda _: "unknown", "incomplete render-boundary coverage")
            mutate("view name=spawn ", "name", lambda _: "upper" if tall else "minimum", "invalid render-boundary view")
            mutate("sprites ", "descriptors", lambda value: value[:8] + "00" + value[10:], "sprite descriptor mismatch")
            mutate("backdrop ", "bytes", change_pixel, "background gradient mismatch")
            if tall:
                def change_byte(value, index):
                    data = bytearray()
                    for run in value.split(","):
                        count, pixel = run.split(":")
                        data.extend([int(pixel, 16)] * int(count))
                    data[index] ^= 15
                    return ",".join(f"{sum(1 for _ in run)}:{pixel:02x}" for pixel, run in groupby(data))

                mutate("heap ", "offset", lambda _: "0", "invalid render-boundary heap")
                for field in ("segment", "map_segment"):
                    mutate("heap ", field, lambda value: str(int(value) + 1), "invalid render-boundary heap")
                for index in (0, 4, 6, 8, 5535):
                    mutate("heap ", "tail", lambda value: change_byte(value, index), "heap/map alias mismatch")
                for field in ("backdrop", "tile_bytes" if alias_probe else "damage_words", "tile_words"):
                    mutate("heap ", field, lambda _: "00000000", "allocation pointer mismatch")
                if alias_probe:
                    for field in ("tile_allocation", "word_allocation"):
                        mutate("heap ", field, lambda _: "00000000", "allocation pointer mismatch")
                mutate("view name=clear_bottom_right ", "map_mode", lambda _: "level", "invalid render-boundary map mode")
                for field in ("tail_before", "tail_after"):
                    mutate("view name=clear_bottom_right ", field, lambda value: change_byte(value, 8), "live heap/map alias mismatch")
    if set(root.glob("*.ppm")) != initial_files:
        raise RuntimeError("replay without output directory wrote frames")
    print(f"render_boundary_fixture=ok captures={len(hashes)} lf_crlf=1 truncated_rejected={len(hashes)} mutations_rejected={mutations} no_output_files=1")


if __name__ == "__main__":
    main()
