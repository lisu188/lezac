# Original Bomb Fuse Recovery

The earlier 41-tick small-bomb claim read the monster-spawner table at
`DS:74A8`, not a bomb. This recovery reads actual actors at `DS:1BAE`, stride
`0x26`, bounded by the last-live-slot byte `DS:208D`.

## Original Instructions

All anchors below use Ghidra segment `1000`; file offsets add `0x770`.
The executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

- `6C0A..6C25`: weapon selector 1/2/3 gives `selector * 10 + 10`;
  selector 4 gives `0xC8`. The result is staged in `DS:79A3`.
- `6C55..6C5B`: pass that seed to the actor constructor `2F9F`.
- `3052`: constructor stores the seed at actor `+0x02`.
- `75A7..75B0`: subtract `DS:78C2 & 1` from actor `+0x02`.
- `75B4..75C8`: branch to expiry on counter 0 or `0xFF`.
- `75CB..75FB`: bomb kinds `0x0D..0x12` invoke the original blast dispatch.

The captured player weapons are kinds `0x0D..0x10`, behavior 2. Their normal
positive seeds reach zero, not the defensive `0xFF` expiry case.

## Runtime Capture

`tools/capture_original_bomb_fuses.py` launches only a temporary asset copy,
under private Xvfb, using the existing level seeder. The exact live command
for each of weapon `1..4` and placement parity `0..1` was:

```sh
python3 tools/capture_original_bomb_fuses.py \
  --run-dir /tmp/lezac-bomb-fuses-20260905 \
  --out /tmp/lezac-bomb-fuses-20260905/weapon1_phase0.txt \
  --weapon 1 --parity 0 \
  --approve-procmem --approve-runtime-instrumentation
```

A real XTEST `keydown n` reaches the placement branch. The tool releases N
and overrides only the branch-local weapon selector at `SS:BP-0x12`. It
adjusts the constructor frame by at most one to choose parity. These are
exogenous probe inputs, not a claim that the original HUD selected all four
weapons naturally. No bomb timer or trajectory field is seeded by the tool.

Guarded CS trampolines stop before seed calculation (`6C0A`), after the
constructor (`6C5E`), after each countdown subtraction (`75B4`), and at
expiry (`75CB`). They save all general registers and FLAGS, record actual
segments, and replay displaced instructions. Immutable polling code uses
a data release flag and monotonic event sequence. Only the child process's
memory is opened. Host SIGSTOP protects patch installation/restoration;
physics, constructor, timer and blast instructions are not changed.

Runtime segments were `CS=01A2`, `DS=0C44`, `SS=18B3`. Constructor checkpoint
`ES=0C44`, `BP=3FEE`, saved post-push `SP=3FA2`. The trace stores all six
register words at construction and expiry. Actual segments calibrate far
pointers; the seeder's nominal DS is only used to locate physical memory.

Each trace records the full 38-byte constructed actor, every full actor
record after subtraction, its 8-byte visual row, and the final expiry frame.
The first countdown update occurs on the frame after construction.

| Weapon | Actor Seed | Even Placement | Odd Placement |
| --- | ---: | ---: | ---: |
| Small | 20 | 39 updates | 40 updates |
| Medium | 30 | 59 updates | 60 updates |
| Large | 40 | 79 updates | 80 updates |
| Super | 200 | 399 updates | 400 updates |

For example, small/even is constructed at frame 28 with counter `0x14`;
frames 29/30 have `0x13`, frames 31/32 have `0x12`, and frame 67 reaches 0.
The checked-in evidence is `tests/fixtures/bomb_fuses_original/`.

The initial short N tap missed placement and was rejected. A later polling
attempt duplicated frame 33; that incomplete trace was rejected too. The
final sequence-number handshake prevents reuse of a previous stop, and
consecutive-frame validation remains mandatory.

## C++ Mapping

`BombProfile::fuseTicks` now holds the maximum update count 40/60/80/400.
`placeBombAt` subtracts the next frame's odd bit, because fire events precede
the next `updateWithControls` increment. The existing remaining-ticks timer
model is retained. After an update, `(timer + 1) / 2` is the corresponding
original byte counter. Pause stops both the frame counter and bomb lifetime.

`--debug-bomb-fuse-original` replays all eight original traces through the
production placement/expiry helpers, checks all 1,156 countdown samples,
rejects missing or non-consecutive evidence, and inspects armed, last-live
and expiry framebuffers. `--debug-bomb-fuse` still covers the delayed
final-life transition and stale-expired-bomb reset guard.

The original PNG checkpoint shows level-1 gameplay and the armed blue small
bomb. Original frame-table bytes are retained for every sample. This recovery
does not claim bomb trajectory, exact explosion rendering, or cross-game
global-frame alignment. At the time of this fuse recovery, placed bombs in
the port were stationary. The subsequent
[bomb motion recovery](bomb_motion_runtime_2026-09-05.md) implements and
validates their trajectories separately. Absolute wall-clock seconds remain
subject to the separately recovered game governor.

## Validation

- Eight complete original traces: 1,156 consecutive countdown samples.
- C++ replay: `bomb_fuse_original=ok`, all eight constructors and expiry
  times match; pause and inventory consumption checks pass.
- Existing final-life and reset-guard regression: `bomb_fuse=ok fuse=39`.
- 24 nonuniform C++ frame checkpoints in
  `build-codex-tmp/bomb-fuse-frames/`; small/last and super/expiry inspected.
  Last framebuffer FNV hash: `36b04f5effb1b9f8`.
- Original small-bomb X11 checkpoint inspected at
  `build-codex-tmp/bomb-fuse-original-small.png`.
- Capture instruction guards and the five-entry uncertainty inventory pass.
- All 420 local CTest cases covered: 419 passed under dummy SDL, with the
  intentionally skipped UI case passing separately under Xvfb (4.20 seconds).
  Full headless suite elapsed time: 235.14 seconds; no failures.
