#!/usr/bin/env python3
"""Pin original visual-order evidence and challenge the production renderer."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--mode", choices=("single", "split"), required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    hashes = {"single": "9246ffa78c6a1769f4135e9366aa7a43f9a981786480d4e2192b1ea636fd6a6d",
              "split": "3a24807c699371aee1504d332405351337364ee9dfa78fb75ff4210d108fb0aa"}
    source = (root / "tests/fixtures" / f"visual_order_{args.mode}_original.txt").read_text(encoding="ascii")
    if hashlib.sha256(source.encode("ascii")).hexdigest() != hashes[args.mode]:
        raise RuntimeError("visual-order capture hash mismatch")
    rows = source.splitlines()
    views = 0
    width = 312 if args.mode == "single" else 152
    for row in rows:
        if not row.startswith("view "):
            continue
        fields = dict(token.split("=", 1) for token in row.split()[1:])
        pixels = bytearray()
        for run in fields["pixels"].split(","):
            count, value = run.split(":")
            pixels.extend([int(value, 16)] * int(count))
        if len(pixels) != width * 152 or len(set(pixels)) < 16 or hashlib.sha256(pixels).hexdigest() != fields["indexed_sha256"]:
            raise RuntimeError("invalid indexed visual-order pixels/hash")
        views += 1
    if views != 40:
        raise RuntimeError("incomplete visual-order hashes")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    initial_files = set(root.glob("*.ppm"))
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="lezac-visual-order-") as directory:
        fixture = Path(directory) / "fixture.txt"

        def run(content, valid=False):
            fixture.write_bytes(content.encode("ascii"))
            result = subprocess.run([str(args.exe.resolve()), "--debug-visual-order-original", str(fixture)],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=90)
            output = result.stdout + result.stderr
            success = result.returncode == 0 and f"visual_order_original=ok views=40 pixels={40 * width * 152} different_pixels=0" in output
            failure = result.returncode != 0 and "visual-order" in output and "visual_order_original=ok" not in output
            if not (success if valid else failure):
                raise RuntimeError(f"expected_valid={valid}: {output}")

        run(source, True)
        run(source.replace("\n", "\r\n"), True)
        run("\n".join(rows[:-1]) + "\n")
        run("\n".join(rows[:len(rows) // 2]) + "\n")

        def edit(prefix, transform):
            nonlocal mutations
            changed = rows.copy()
            index = next(i for i, row in enumerate(changed) if row.startswith(prefix))
            tag, *tokens = changed[index].split()
            fields = dict(token.split("=", 1) for token in tokens)
            transform(fields)
            changed[index] = tag + " " + " ".join(f"{key}={value}" for key, value in fields.items())
            if changed == rows:
                raise RuntimeError("no-op visual-order mutation")
            run("\n".join(changed) + "\n")
            mutations += 1

        def mutate(prefix, field, transform):
            edit(prefix, lambda fields: fields.update({field: transform(fields[field])}))

        def change_byte(value, offset):
            data = bytearray.fromhex(value)
            data[offset] ^= 15
            return data.hex()

        def change_pixel(value):
            first, rest = value.split(",", 1)
            count, pixel = first.split(":")
            return f"{count}:{int(pixel, 16) ^ 15:02x},{rest}"

        for name in ("mixed_forward", "mixed_reverse", "player_bomb", "two_players_mixed", "clip_right_0", "shake_7", "last_sprite_control"):
            mutate(f"view name={name} ", "pixels", change_pixel)
        first = "view name=control "
        for value in ("1:00", "999999:00", "-1:00", "1:gg"):
            mutate(first, "pixels", lambda _, replacement=value: replacement)
        for field in ("x", "y", "count", "coarse_x", "coarse_y", "fine_x", "fine_y", "source", "destination"):
            mutate(first, field, lambda value: str(int(value) + 1))
        mutate(first, "p2", lambda _: "2")
        mutate(first, "order", lambda _: "unknown")
        mutate(first, "name", lambda _: "../outside")
        mutate(first, "after_regs", lambda value: change_byte(value, 2))
        mutate(first, "after_regs", lambda value: change_byte(value, 4))
        mutate("view name=effect_bomb ", "frame", lambda value: str(int(value) + 1))
        mutate("view name=effect_bomb ", "name", lambda _: "control")
        mutate("view name=effect_bomb ", "actor_x", lambda value: str(int(value) + 1))
        mutate("view name=effect_bomb ", "actor_y", lambda value: str(int(value) + 1))
        mutate("view name=shake_7 ", "shake", lambda _: "8")
        for offset in (0, 4, 8, 16, 20):
            mutate("view name=effect_bomb ", "visuals", lambda value, at=offset: change_byte(value, at))
        for offset in (4, 6, 364):
            mutate("sprites ", "descriptors", lambda value, at=offset: change_byte(value, at))
        mutate("backdrop ", "bytes", change_pixel)
        mutate("map ", "bytes", lambda value: change_byte(value, 21 * 60 + 30))
        mutate("complete ", "views", lambda _: "39")
        mutate("complete ", "discriminating_pairs", lambda _: "5")
        mutate("capture=", "seeded", lambda _: "0")
        mutate("capture=", "temp_copy", lambda _: "0")

        def swap_layers(fields):
            fields["order"] = "bomb,effect"
            data = bytes.fromhex(fields["visuals"])
            fields["visuals"] = (data[:16] + data[24:32] + data[16:24]).hex()

        edit("view name=effect_bomb ", swap_layers)
        index = next(i for i, row in enumerate(rows) if row.startswith("view "))
        for changed in (rows[:index] + rows[index + 1:], rows + [rows[index]],
                        rows[:index] + [rows[index] + " extra=1"] + rows[index + 1:],
                        rows[:index] + [rows[index] + " x=247"] + rows[index + 1:]):
            run("\n".join(changed) + "\n")
            mutations += 1
    if set(root.glob("*.ppm")) != initial_files:
        raise RuntimeError("unrequested visual-order frame output")
    print(f"visual_order_fixture=ok mode={args.mode} views=40 lf_crlf=1 truncated_rejected=2 mutations_rejected={mutations} indexed_hashes=40 no_output_files=1")


if __name__ == "__main__":
    main()
