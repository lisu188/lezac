# Frame PPM Raster Boundary Repair

Historical PR #36 review finding `discussion_r3129466443` remained reproducible
on main `ffb726a3bfb1e23d6858d7894a30c1de8464c6a2`: the dependency-free P6 reader
discarded all whitespace after Maxval, including valid binary raster samples.
The pre-fix regression failure is retained in the task control evidence.

The [Netpbm PPM specification](https://netpbm.sourceforge.net/doc/ppm.html)
defines one whitespace character between Maxval and the binary raster. The
reader now consumes exactly that separator, recognizes the six ASCII whitespace
characters in the header, and never tokenizes P6 raster bytes. In particular,
after a CR separator an LF can be the first sample; it is not silently consumed
as a second header separator. P3 token parsing and first-image handling remain
supported. Invalid dimensions and truncated rasters are rejected.

`tools/check_frame_compare_ppm.py` checks 1,551 valid inputs, including all 256
possible first samples after each of six separators, leading whitespace runs,
hash-valued pixels, header comments, plain P3 rasters, and a following P6 image.
It rejects 12 malformed inputs. It calls `read_ppm` directly, so optional Pillow
fallback cannot hide a native reader failure. CTest and early Windows/Linux CI
run this regression.

This repairs frame-comparison input integrity. It does not generate, modify, or
promote original captures, establish a new RGB comparison, or prove gameplay,
physical timing, sound, or whole-game fidelity. All broad completion and fidelity
flags remain false. Fresh exact-head full CI, package checks, and external code
review remain separate delivery requirements.
