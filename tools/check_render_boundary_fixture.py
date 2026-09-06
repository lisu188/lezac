#!/usr/bin/env python3
"""Pin render evidence and reject pixel, camera, and coverage mutations."""

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
        "render_boundary_original.txt": "e247440fadfdf9a5220a9363e0455ac6b34dd8ea9334fdebf64b583ca716e929",
        "render_boundary_split_original.txt": "3c8b344a1de502abaea5de4add845485d61322f8c8c9df5ee06baea85c880e12",
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

            def run(content, error=None):
                fixture.write_bytes(content.encode("ascii"))
                result = subprocess.run([str(args.exe.resolve()), "--debug-render-boundary-original", str(fixture)],
                                        cwd=root, env=env, capture_output=True, text=True, timeout=90)
                output = result.stdout + result.stderr
                valid = (result.returncode == 0 and f"render_boundary_original=ok views=30 width={width}" in output
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

            mutate("view name=minimum ", "pixels", change_pixel, "pixel mismatches")
            mutate("view name=minimum ", "pixels", lambda _: "999999:00", "run overflow")
            mutate("view name=minimum ", "pixels", lambda _: "1:00", "truncated render-boundary pixels")
            mutate("view name=spawn ", "frame", lambda value: str(int(value) + 1), "nonconsecutive")
            mutate("view name=spawn ", "coarse_x", lambda value: str(int(value) + 8), "camera/driver mismatch")
            mutate("view name=shake_fine_carry ", "fine_x", lambda _: "6", "camera/driver mismatch")
            mutate("view name=shake_fine_carry ", "shake", lambda _: "-1", "invalid render-boundary shake")
            mutate("view name=minimum ", "backdrop_stride", lambda _: "1", "camera/driver mismatch")
            mutate("view name=minimum ", "after_regs", lambda value: value[:8] + "0000" + value[12:], "segment mismatch")
            mutate("view name=minimum ", "source", lambda _: "0", "invalid render-boundary view")
            mutate("view name=minimum ", "name", lambda _: "unknown", "incomplete render-boundary coverage")
            mutate("view name=spawn ", "name", lambda _: "minimum", "invalid render-boundary view")
            mutate("sprites ", "descriptors", lambda value: value[:8] + "00" + value[10:], "sprite descriptor mismatch")
            mutate("backdrop ", "bytes", change_pixel, "background gradient mismatch")
    if set(root.glob("*.ppm")) != initial_files:
        raise RuntimeError("replay without output directory wrote frames")
    print(f"render_boundary_fixture=ok captures=2 lf_crlf=1 truncated_rejected=2 mutations_rejected={mutations} no_output_files=1")


if __name__ == "__main__":
    main()
