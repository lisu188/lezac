# Tall-Level Background Reads

## Scope And Result

Five original DOSBox captures add 71 controlled views: 13 each on levels 3
and 6, 15 each on levels 4 and 5, and 15 on level 3 with the 160-byte
backdrop pitch initialized through two-player mode. The normal views are
312x152; the split probe isolates the 152x152 left viewport and disables P2.
All 3,002,304 new viewport pixels match C++ after normalized palette
conversion. Together with the earlier level-1 fixtures, this is 131 views
and 5,118,144 pixels. This is not natural-route or whole-game visual parity.

The old C++ renderer allocated 61,440 backdrop bytes, padded the uninitialized
tail with palette index 222, and wrapped still-larger reads into that buffer.
The level-6 clear-map fixture exposed 8,568 mismatching pixels, including
2,514 in `clear_bottom_right`. The recovered lookup removes both fallbacks.

## Recovered Memory Layout

The original requests exactly 60,000 bytes at file 0x2fe9. In these runs the
backdrop pointer DS:C498/C49A is `3002:0008`, physical offset 196648. The map
allocation begins immediately after it, at `3ea8:0008`; the loader rounds
the map pointer forward to `3ea9:0000`, leaving an eight-byte gap. Thus a
background source index relative to the actual far pointer reads:

| Relative index | Source |
| --- | --- |
| 0..59999 | Initialized gradient and generated skyline |
| 60000..60007 | Stale metadata in the map allocation's alignment gap |
| 60008..65527 | First 5,520 bytes of the live tile map |
| 65528..65535 | Segment prefix before the backdrop pointer, zero in all five captures |

The source offset wraps at 16 bits relative to segment `3002`, not relative
to the allocated buffer's length. All shipped tall-level viewport reads
remain below that wrap point; the memory probe additionally checks the
whole 5,536-byte tail, including the wrapped prefix. Shorter levels 1, 2
and 7 do not expose this overflow at their normal camera limits. A split
backdrop's 160-byte pitch also keeps its actual view reads below 60,000.

The metadata is not a fixed level-color pattern. The loader frees the old
word plane first (file 0x13ff..1423), then the old byte plane (0x1426..1448),
and allocates `width*height+16` bytes for the new map (0x14d0..1514). The
Pascal allocator rounds requests to multiples of eight (0x9e01..9e11).
FreeMem writes that size as offset and paragraph words at allocation bytes
4..7 (0x9d70..9d74). Both frees retract the heap top, retaining those bytes;
the next aligned map load does not overwrite the gap.

| Current level | Previous map allocation, rounded | Captured gap bytes |
| --- | --- | --- |
| 3, including split | 5,320 | `00 00 00 00 08 00 4c 01` |
| 4 | 9,016 | `00 00 00 00 08 00 33 02` |
| 5 | 5,816 | `00 00 00 00 08 00 6b 01` |
| 6 | 6,840 | `00 00 00 00 08 00 ab 01` |

C++ tracks the previous loaded map's allocation size on `resetLevel`, not
the current level number or a captured byte table. `backdropByte` reads the
current `level_.tiles`, so mutations are visible immediately. No captured
tail data is supplied to the production renderer. The diagnostic derives
all tail bytes through this lookup and checks both pre-render and post-render
memory. It also validates the backdrop, aligned map, raw map allocation,
aligned word-plane and raw word allocation pointers where recorded.

## Capture Provenance

Executable SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The capture uses temporary copies, private Xvfb displays and child-process
memory instrumentation at main CS:7A13 and CS:7A57, as described in
[the render-boundary recovery](render_boundary_runtime_2026-09-06.md).
Runtime main CS/DS are 01ed/0c8f in these captures. Register relationships,
unchanged frame/map/visual inputs and consecutive frames are checked.
The current tool guards 12 original instruction windows, including the
allocation/free/alignment instructions above; the new split run verified
all 12 live before installing hooks.

Levels are reached through original transitions using the existing seeder's
completion-counter instrumentation. Startup/intro/level-start/results waits
are 10/8/5/10 seconds. Each render probe disables spawners and non-player
actors, retains one sprite-0 visual entry, and seeds lives/energy to 99/100.
The original map and skyline are explicit inputs to the C++ replay. Gradient
bytes outside the skyline band are checked against C++ generation first.

Version-1 tall captures contain 13 views: upper, spawn, center, lower corners,
clear upper, camera-Y thresholds 280/288/296, clear lower corners, clear
bottom with shake 7, and clear bottom with background disabled. Version 2
adds two alias probes: an otherwise zero map has its first 512 bytes set to
`1 + index % 174`, outside the bottom camera's visible tile rows. Those bytes
appear as colors in the overrun backdrop on full-width views; they do not
appear in the split-width probe. The early version-1 field `damage_words`
actually records the byte-map pointer DS:C1E0; version 2 names it `tile_bytes`
and records raw allocation pointers as well. Original fixture bytes are
preserved, not rewritten to rename that field.

| Fixture suffix after `render_boundary_` | Frames | SHA-256 |
| --- | --- | --- |
| `tall_level3_original.txt` | 276..288 | `532c62a4e23619a574514d58b7427c9e3bf7ee7ff52dc955e7b114d34a00cf2a` |
| `tall_level4_original.txt` | 387..401 | `745c443754b451b8c08086da33b07c026002ad0d32b23f52f857b8315e27cb73` |
| `tall_level5_original.txt` | 488..502 | `70d39de38ab750fe0885de24ab34170844fa67d1ba79d65e2ece035f21051dec` |
| `tall_level6_original.txt` | 590..602 | `fe8c42e872618db6b4b32ef2e784490acae9ba0b6efc45a488b735e18127910f` |
| `tall_level3_split_original.txt` | 272..286 | `b18f3a41d53d756dc576154a8651deabcd46369ae052532b4847a9357ecbbcd3` |

Example reproduction after copying the shipped assets into a fresh directory:

```sh
python3 tools/capture_original_render_boundary.py --level 4 \
  --run-dir /tmp/lezac-render-tall4-v2 \
  --out build-codex-tmp/render-tall4-v2.txt \
  --approve-procmem --approve-runtime-instrumentation
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-render-boundary-original \
  tests/fixtures/render_boundary_tall_level4_original.txt \
  build-codex-tmp/render-tall4-cpp-after
```

The other source prefixes are `render-tall3-v1`, `render-tall5-v2`,
`render-tall6-v3`, and `render-tall3-split-v2`, all under `build-codex-tmp`.
The current tool produces the 15-view version 2 for each tall level.
An initial level-6 attempt reached its target but rejected the nonzero far
offset; the reader was corrected to include that offset and segment wrapping.
A reduced-wait attempt failed to leave the intro and was not promoted.

## Validation And Remaining Gaps

The fixture guard now pins seven captures, accepts LF/CRLF, rejects seven
truncated captures and 174 mutations, and checks no implicit frame writes.
Mutations cover pixels, camera/registers, descriptors, gradient generation,
map modes, physical allocation pointers, gap size bytes, live map bytes and
wrapped prefix bytes. Five tall view tests and the expanded capture-contract
test complement the existing full/split fixtures.

All 461 CTests pass under Xvfb in 107.59 seconds. Full log:
`build-codex-tmp/tall-background-full-tests.log`. The build retains an existing
unrelated `snprintf` truncation warning in `debugDebrisShatterPlayback`.

All 23 new DOSBox screenshot crops were compared with normalized indexed
buffer previews. Eighteen match exactly, including every clear-map and alias
probe. Five terrain screenshots differ only at red palette entries 230..235:
level-4 spawn/lower-right have 108/109 differing pixels; level-5 lower-right
has 55; level-6 spawn/lower-right each have 14. For example, level-4 index
235 changes from displayed RGB (109,0,0) at spawn to (138,0,0) at lower-right,
while its static BOMPAL color is (255,0,0). These runtime palette changes are
not reproduced by this normalized renderer test. The exact pairs and counts
are recorded locally in `build-codex-tmp/tall-palette-analysis.json`.

Remaining work includes that red-palette behavior, skyline RNG alignment,
natural-route rendering, HUD phase, shared actor ordering/capacity, and
simultaneous P2 activity. This is not a general Pascal heap emulator: other
allocation histories, boss/new-game heap reuse and arbitrary map/view sizes
still need independent observation. Functional completion and whole-game
fidelity remain unproven.
