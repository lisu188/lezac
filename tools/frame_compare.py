#!/usr/bin/env python3
"""Compare two captured Larax & Zaco frames.

The script has no required third-party dependencies for PPM/PNM and BMP files.
If Pillow is installed, it is used as a fallback for formats such as DOSBox PNG
screenshots.
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
from pathlib import Path
from typing import Iterable, Tuple


Image = Tuple[int, int, bytearray]


def _netpbm_tokens(data: bytes) -> Iterable[bytes]:
    i = 0
    while i < len(data):
        while i < len(data) and data[i] in b" \t\r\n":
            i += 1
        if i < len(data) and data[i] == ord("#"):
            while i < len(data) and data[i] not in b"\r\n":
                i += 1
            continue
        if i >= len(data):
            break
        start = i
        while i < len(data) and data[i] not in b" \t\r\n":
            i += 1
        yield data[start:i]


def read_ppm(path: Path) -> Image:
    data = path.read_bytes()
    tokens = list(_netpbm_tokens(data))
    if len(tokens) < 4 or tokens[0] not in (b"P3", b"P6"):
        raise ValueError("not a P3/P6 PPM image")
    magic = tokens[0]
    width = int(tokens[1])
    height = int(tokens[2])
    maxval = int(tokens[3])
    if maxval != 255:
        raise ValueError(f"unsupported PPM maxval {maxval}")
    if magic == b"P3":
        values = [int(token) for token in tokens[4:]]
        if len(values) != width * height * 3:
            raise ValueError("P3 payload size does not match dimensions")
        return width, height, bytearray(values)

    header_end = 0
    found = 0
    in_comment = False
    while header_end < len(data) and found < 4:
        ch = data[header_end]
        header_end += 1
        if in_comment:
            if ch in b"\r\n":
                in_comment = False
            continue
        if ch == ord("#"):
            in_comment = True
            continue
        if ch in b" \t\r\n":
            continue
        found += 1
        while header_end < len(data) and data[header_end] not in b" \t\r\n":
            header_end += 1
    while header_end < len(data) and data[header_end] in b" \t\r\n":
        header_end += 1
    payload = data[header_end:]
    expected = width * height * 3
    if len(payload) < expected:
        raise ValueError("P6 payload is shorter than dimensions")
    return width, height, bytearray(payload[:expected])


def read_bmp(path: Path) -> Image:
    data = path.read_bytes()
    if len(data) < 54 or data[:2] != b"BM":
        raise ValueError("not a BMP image")
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    dib_size = struct.unpack_from("<I", data, 14)[0]
    if dib_size < 40:
        raise ValueError("unsupported BMP DIB header")
    width = struct.unpack_from("<i", data, 18)[0]
    raw_height = struct.unpack_from("<i", data, 22)[0]
    planes = struct.unpack_from("<H", data, 26)[0]
    bits_per_pixel = struct.unpack_from("<H", data, 28)[0]
    compression = struct.unpack_from("<I", data, 30)[0]
    if planes != 1 or compression != 0 or bits_per_pixel not in (24, 32):
        raise ValueError("only uncompressed 24/32-bit BMP is supported")
    if width <= 0 or raw_height == 0:
        raise ValueError("invalid BMP dimensions")
    height = abs(raw_height)
    top_down = raw_height < 0
    bytes_per_pixel = bits_per_pixel // 8
    stride = ((width * bytes_per_pixel + 3) // 4) * 4
    pixels = bytearray(width * height * 3)
    for y in range(height):
        src_y = y if top_down else height - 1 - y
        src = pixel_offset + src_y * stride
        for x in range(width):
            b, g, r = data[src + x * bytes_per_pixel:src + x * bytes_per_pixel + 3]
            dst = (y * width + x) * 3
            pixels[dst:dst + 3] = bytes((r, g, b))
    return width, height, pixels


def read_with_pillow(path: Path) -> Image:
    try:
        from PIL import Image as PillowImage  # type: ignore
    except ImportError as exc:
        raise ValueError(
            "unsupported image format; install Pillow or convert to PPM/BMP"
        ) from exc
    with PillowImage.open(path) as image:
        rgb = image.convert("RGB")
        return rgb.width, rgb.height, bytearray(rgb.tobytes())


def read_image(path: Path) -> Image:
    errors = []
    for reader in (read_ppm, read_bmp, read_with_pillow):
        try:
            return reader(path)
        except Exception as exc:  # noqa: BLE001 - preserve fallback details.
            errors.append(str(exc))
    raise ValueError("; ".join(errors))


def crop_image(image: Image, crop: str | None) -> Image:
    if not crop:
        return image
    width, height, pixels = image
    parts = [int(part) for part in crop.split(",")]
    if len(parts) != 4:
        raise ValueError("crop must be x,y,w,h")
    x, y, w, h = parts
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise ValueError("crop is outside the image")
    out = bytearray(w * h * 3)
    for row in range(h):
        src = ((y + row) * width + x) * 3
        dst = row * w * 3
        out[dst:dst + w * 3] = pixels[src:src + w * 3]
    return w, h, out


def downscale_integer(image: Image, target_width: int, target_height: int) -> Image:
    width, height, pixels = image
    if width % target_width != 0 or height % target_height != 0:
        raise ValueError(
            f"cannot integer-scale {width}x{height} to {target_width}x{target_height}"
        )
    sx = width // target_width
    sy = height // target_height
    out = bytearray(target_width * target_height * 3)
    for y in range(target_height):
        for x in range(target_width):
            src = ((y * sy) * width + (x * sx)) * 3
            dst = (y * target_width + x) * 3
            out[dst:dst + 3] = pixels[src:src + 3]
    return target_width, target_height, out


def normalize_sizes(left: Image, right: Image) -> tuple[Image, Image, str]:
    lw, lh, _ = left
    rw, rh, _ = right
    if (lw, lh) == (rw, rh):
        return left, right, "none"
    if rw >= lw and rh >= lh and rw % lw == 0 and rh % lh == 0:
        return left, downscale_integer(right, lw, lh), f"right_downscaled_{rw}x{rh}_to_{lw}x{lh}"
    if lw >= rw and lh >= rh and lw % rw == 0 and lh % rh == 0:
        return downscale_integer(left, rw, rh), right, f"left_downscaled_{lw}x{lh}_to_{rw}x{rh}"
    raise ValueError(f"size mismatch left={lw}x{lh} right={rw}x{rh}")


def write_ppm(path: Path, image: Image) -> None:
    width, height, pixels = image
    with path.open("wb") as handle:
        handle.write(f"P6\n{width} {height}\n255\n".encode("ascii"))
        handle.write(pixels)


def diff_image(width: int, height: int, a: bytearray, b: bytearray) -> Image:
    out = bytearray(width * height * 3)
    for i in range(width * height):
        base = i * 3
        dr = abs(a[base] - b[base])
        dg = abs(a[base + 1] - b[base + 1])
        db = abs(a[base + 2] - b[base + 2])
        delta = max(dr, dg, db)
        if delta == 0:
            out[base:base + 3] = b"\x00\x00\x00"
        else:
            out[base:base + 3] = bytes((255, min(255, delta * 4), min(255, delta * 4)))
    return width, height, out


def compare(a_img: Image, b_img: Image, threshold: int) -> dict[str, float | int]:
    aw, ah, a = a_img
    bw, bh, b = b_img
    if (aw, ah) != (bw, bh):
        raise ValueError(f"size mismatch left={aw}x{ah} right={bw}x{bh}")
    pixels = aw * ah
    exact_diff = 0
    threshold_diff = 0
    total_abs = 0
    total_sq = 0
    max_delta = 0
    for i in range(pixels):
        base = i * 3
        deltas = [
            abs(a[base] - b[base]),
            abs(a[base + 1] - b[base + 1]),
            abs(a[base + 2] - b[base + 2]),
        ]
        pixel_max = max(deltas)
        if pixel_max != 0:
            exact_diff += 1
        if pixel_max > threshold:
            threshold_diff += 1
        max_delta = max(max_delta, pixel_max)
        total_abs += sum(deltas)
        total_sq += sum(delta * delta for delta in deltas)
    channels = pixels * 3
    return {
        "pixels": pixels,
        "exact_match": 1 if exact_diff == 0 else 0,
        "exact_different_pixels": exact_diff,
        "threshold_different_pixels": threshold_diff,
        "max_delta": max_delta,
        "mean_abs_delta": total_abs / channels,
        "rmse": math.sqrt(total_sq / channels),
    }


def registered_delta(left, right, region, max_dx, max_dy):
    """Find the (dx, dy) shift of `right` vs `left` (over `region`) minimizing
    mean absolute delta. Compensates for scroll/camera offset between two
    capture harnesses so the metric reflects rendering, not alignment."""
    width, height, lp = left
    _, _, rp = right
    x0, y0, rw, rh = region
    best = None
    for dy in range(-max_dy, max_dy + 1):
        for dx in range(-max_dx, max_dx + 1):
            total = 0
            count = 0
            for y in range(y0, min(y0 + rh, height), 3):
                ry = y + dy
                if ry < 0 or ry >= height:
                    continue
                base_l = y * width
                base_r = ry * width
                for x in range(x0, min(x0 + rw, width), 3):
                    rx = x + dx
                    if rx < 0 or rx >= width:
                        continue
                    li = (base_l + x) * 3
                    ri = (base_r + rx) * 3
                    total += (abs(lp[li] - rp[ri]) + abs(lp[li + 1] - rp[ri + 1]) +
                              abs(lp[li + 2] - rp[ri + 2]))
                    count += 3
            if count and (best is None or total / count < best[0]):
                best = (total / count, dx, dy)
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left")
    parser.add_argument("right")
    parser.add_argument("--threshold", type=int, default=0)
    parser.add_argument("--max-diff-pixels", type=int, default=0)
    parser.add_argument("--crop", help="compare only x,y,w,h")
    parser.add_argument("--diff", help="write a PPM visual diff")
    parser.add_argument("--register", help="align before differencing: MAX_DX,MAX_DY")
    parser.add_argument("--register-region", help="region for --register: x,y,w,h")
    args = parser.parse_args()

    if args.threshold < 0 or args.threshold > 255:
        parser.error("--threshold must be 0..255")
    if args.max_diff_pixels < 0:
        parser.error("--max-diff-pixels must be non-negative")

    left = crop_image(read_image(Path(args.left)), args.crop)
    right = crop_image(read_image(Path(args.right)), args.crop)
    left, right, normalized = normalize_sizes(left, right)
    stats = compare(left, right, args.threshold)

    if args.diff:
        write_ppm(Path(args.diff), diff_image(left[0], left[1], left[2], right[2]))

    register_suffix = ""
    if args.register:
        try:
            max_dx, max_dy = (int(v) for v in args.register.split(","))
        except ValueError:
            parser.error("--register must be MAX_DX,MAX_DY")
        if args.register_region:
            region = tuple(int(v) for v in args.register_region.split(","))
        else:
            region = (0, 0, left[0], min(154, left[1]))
        best = registered_delta(left, right, region, max_dx, max_dy)
        if best is not None:
            register_suffix = (
                f" registered_mean_abs_delta={best[0]:.6f}"
                f" registered_dx={best[1]} registered_dy={best[2]}"
            )

    print(
        "frame_compare=ok"
        f" size={left[0]}x{left[1]}"
        f" normalized={normalized}"
        f" pixels={stats['pixels']}"
        f" exact_match={stats['exact_match']}"
        f" exact_different_pixels={stats['exact_different_pixels']}"
        f" threshold={args.threshold}"
        f" threshold_different_pixels={stats['threshold_different_pixels']}"
        f" max_delta={stats['max_delta']}"
        f" mean_abs_delta={stats['mean_abs_delta']:.6f}"
        f" rmse={stats['rmse']:.6f}"
        f"{register_suffix}"
    )
    return 0 if stats["threshold_different_pixels"] <= args.max_diff_pixels else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - command line diagnostic.
        print(f"frame_compare=error reason={exc}", file=sys.stderr)
        raise SystemExit(1)
