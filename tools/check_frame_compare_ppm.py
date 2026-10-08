#!/usr/bin/env python3
"""Check PPM header/raster boundaries without relying on the Pillow fallback."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile

from frame_compare import read_ppm


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    cases = 0
    rejected = 0
    whitespace = b" \t\r\n\v\f"
    with tempfile.TemporaryDirectory(prefix="lezac-ppm-boundary-") as directory:
        path = Path(directory) / "case.ppm"

        def check(data: bytes, pixels: bytes, size: tuple[int, int] = (1, 1)) -> None:
            nonlocal cases
            path.write_bytes(data)
            width, height, actual = read_ppm(path)
            if (width, height) != size or actual != pixels:
                raise AssertionError("PPM reader changed raster bytes or dimensions")
            cases += 1

        # Every possible first sample follows every legal one-byte separator.
        for separator in whitespace:
            for first in range(256):
                pixels = bytes((first, 255 - first, 127))
                check(b"P6\n1 1\n255" + bytes((separator,)) + pixels, pixels)
        pixels = b"\t\n\r \v\f#P6\x00\xff\x7f"
        check(b"P6\n2 2\n255\n" + pixels, pixels, (2, 2))
        for separator in whitespace:
            header = b"P6" + bytes((separator,)) + b"# dimensions\r\n1 1\n# maxval\n255\n"
            check(header + b"#\n\r", b"#\n\r")
        check(b"P6\n1 1\n255\r\n\t\x20", b"\n\t\x20")
        check(b"P6\n1 1\n255\n\x01\x02\x03P6\n1 1\n255\n\x04\x05\x06", b"\x01\x02\x03")
        for separator in whitespace:
            check(b"P3" + bytes((separator,)) + b"1 1\n255\n# raster\n9 10 32\n", b"\t\n ")
        malformed = (
            b"", b"P6\n", b"P7\n1 1\n255\n\x00\x00\x00",
            b"P6\n1 1\n255", b"P6\n1 1\n255\n\x00\x00",
            b"P6\n0 1\n255\n", b"P6\n1 0\n255\n",
            b"P6\n-1 1\n255\n", b"P6\n1 -1\n255\n",
            b"P6\n1 1\n256\n\x00\x00\x00",
            b"P3\n1 1\n255\n1 2", b"P3\n1 1\n255\n1 2 256",
        )
        for data in malformed:
            path.write_bytes(data)
            try:
                read_ppm(path)
            except (ValueError, IndexError):
                rejected += 1
            else:
                raise AssertionError("PPM reader accepted malformed header or raster")
    print(f"frame_compare_ppm=ok cases={cases} malformed_rejected={rejected} "
          "first_samples=256 separators=6 pillow_fallback=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
