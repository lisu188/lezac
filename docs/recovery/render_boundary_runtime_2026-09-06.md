# Render Boundary Recovery

## Scope And Results

Two original DOSBox captures cover 30 seeded level-1 views each: the normal
312x152 viewport and the isolated 152x152 left viewport initialized through
two-player mode. The production C++ renderer now matches all 2,115,840 pixels
after the same VGA palette conversion. Cases cover camera limits, all eight
fine-scroll phases, positive shake, shake crossing the buffer row boundary,
and background enabled/disabled. Only one visual entry, player sprite 0, is
active. These are rendering probes, not natural gameplay or two-player routes.

This exposed and fixed two production bugs:

- The backdrop pitch was always 320 in C++. The original initializes it to
  160 in two-player mode, including the gradient fill and skyline addressing.
  The old renderer disagreed on 482,168 pixels across the split-view fixture.
- Shake can increase fine X beyond the eight spare pixels in the drawing
  buffer. The original presentation copy then reads the next row's left
  foreground into the right edge. C++ previously drew uninterrupted world
  pixels there. The first focused carry case exposed 64 incorrect pixels.

Ordinary camera offsets were already correct in these captures and were not
changed. The original draws the world before the actor-update checkpoints
used by the flame lifecycle capture; comparing that displayed view against
post-update state is not a synchronized comparison.

## Provenance

- Executable SHA-256:
  `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
- Full-width fixture: `tests/fixtures/render_boundary_original.txt`.
  SHA-256 (LF):
  `e247440fadfdf9a5220a9363e0455ac6b34dd8ea9334fdebf64b583ca716e929`.
- Split-width fixture: `tests/fixtures/render_boundary_split_original.txt`.
  SHA-256 (LF):
  `3c8b344a1de502abaea5de4add845485d61322f8c8c9df5ee06baea85c880e12`.
- Raw sources were promoted without editing from
  `build-codex-tmp/render-boundary-v5.txt` (frames 87..116) and
  `build-codex-tmp/render-boundary-split-v5.txt` (frames 85..114).
- Hooks: Ghidra `1000:7A13` and `1000:7A57`, runtime `01a2:7A13` and
  `01a2:7A57`. The first precedes camera/view drawing; the second follows
  both view-presentation calls and precedes clearing the damage bytes.
- Registers: CS `01a2`, DS `0c44`, SS `18b3`, saved SP `3fe4`, BP `3ffe`.
  ES is `0040` before and `a000` after rendering.
- Private temporary copies and private Xvfb displays were used. Startup,
  intro and level-start waits were 10/8/5 seconds. The normal menu key was
  `1`; the split capture used `2`, then disabled P2 at the probe boundary.
- Each case restores the captured map and seeds one visual entry, camera
  position, background toggle and shake. Non-player actors and spawners are
  disabled. No input state is changed between the two hooks; the capture
  verifies unchanged frame number, map bytes and visual entry after drawing.
- Pixels are read from the original drawing buffer through DS:C212/C214,
  using its actual pitch and fine scroll. They are not reconstructed from
  C++ tiles. RLE is lossless; the original map, backdrop and all 92 sprite
  descriptors are recorded alongside the pixels.

Commands after copying the shipped assets into the temporary directories:

```sh
python3 tools/capture_original_render_boundary.py \
  --run-dir /tmp/lezac-render-boundary-v5 \
  --out build-codex-tmp/render-boundary-v5.txt \
  --approve-procmem --approve-runtime-instrumentation
python3 tools/capture_original_render_boundary.py --split-view \
  --run-dir /tmp/lezac-render-boundary-split-v5 \
  --out build-codex-tmp/render-boundary-split-v5.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The first trial attached between hooks and stopped at stage 2 while waiting
for stage 1. The tool now releases that initial stage-2 stop before starting
the probe. A negative-shake trial was not promoted: production shake is an
unsigned positive RNG offset. It was replaced by positive fine-scroll carry.

## Original Drawing Pipeline

The camera helper is main CS:3587 (file 0x3cf7). Its coarse coordinates,
fine coordinates and map offset are DS:C216/C218, C20A/C20C and C1F0.
CS:36F6 adds the shake word to fine X without reclamping it.

Ghidra 18AC:00F4 (file 0x9324, runtime 0a4e:00f4) draws the backdrop at
the fine-scroll origin, tiles at the coarse origin, then visual entries in
table order. Ghidra 18AC:03C8 (file 0x95f8, runtime 0a4e:03c8) copies
`pitch-8` pixels for 152 rows, starting at source offset
`8 + fine_x + fine_y*pitch`, to VGA offset 1284 (screen coordinate 4,4).
It increments the source linearly; it does not crop away a row-crossing tail.
The C++ foreground clipping now follows those source-row spans, with the
backdrop remaining at the fine origin. Both widths and background-off carry
cases reproduce the captured result exactly.

At file 0x7f4f the driver initializes the backdrop using current view width;
file 0x7f54 latches that width in DS:C1F8. The driver fills exactly 60,000
bytes with `byte(176 + index/(4*pitch))`. The skyline writes at file
0x7fe0 and star writes at 0x8031 use the same pitch. Later width adjustment
does not repack the backdrop. C++ now stores that initialized pitch, uses it
for generation and parallax, and preserves byte wrapping beyond index 255.
The diagnostic checks generated gradient bytes outside the skyline band
against each capture before loading the captured skyline.

## Verification And Limits

`--debug-render-boundary-original FIXTURE [OUT_DIR]` validates descriptors,
camera/driver fields, register relationships, consecutive frames, required
case names, gradient generation and every converted viewport pixel. Optional
output contains 30 PPMs and a CSV with camera state, mismatch counts and
frame hashes. The fixture guard pins both captures, checks LF/CRLF input,
rejects truncation and 28 deliberate mutations, and verifies no implicit
frame writes. CTest also checks six original instruction windows.

DOSBox PNGs and indexed-buffer PPM previews were captured for spawn,
fine_x_3, maximum and background_off in each mode. The viewport crop is
`312x152+4+4` or `152x152+4+4`; compare after stripping image-page offsets.
All eight screenshot crops matched their raw-buffer previews exactly
(`compare -metric AE` returned 0 for every pair). All 455 CTests passed in
29.48 seconds under Xvfb; log: `build-codex-tmp/render-boundary-full-tests.log`.

Not established: natural-route phase lockstep, HUD timing, actor-table
ordering/capacity, sprites overlapping a wrapped buffer edge, simultaneous
P2 activity, arbitrary viewport widths, all levels, or backdrop skyline RNG
alignment across independent runs. The captured skyline is an explicit
renderer input, not proof of generation seed parity. Reads beyond the
driver's 60,000 initialized background bytes were unverified in this batch.
The subsequent [tall-level recovery](tall_background_runtime_2026-09-06.md)
replaces that padded backing and fallback using original heap/map evidence,
and records a separate runtime red-palette discrepancy.
Global functional-completion and original-fidelity claims remain false.
