# Player Posture and Pickup-Driven Collapse

Status: locally validated on `codex/recover-player-down-landing`. The focused
original replays and the full regression suite pass, including interactive UI.
This is not a full-game, full-collapse-engine, or pixel-parity claim.

## Original Evidence

All runs use the temporary asset copy
`/tmp/lezac-player-posture-20260905-4jbVwK`. The shipped executable was not
modified. Its SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

The harness injects only the declared normalized control bytes. Guarded
checkpoints save registers and replay displaced instructions. These routes
do not seed player coordinates, velocity, animation, map tiles, or collapse
records. C++ initializes the player once from the first captured entry and
then runs continuously; no per-tick expected state is copied into gameplay.

```sh
python3 tools/capture_original_player_walk.py --animation \
  --route platform_drop \
  --run-dir /tmp/lezac-player-posture-20260905-4jbVwK \
  --out /tmp/lezac-player-posture-20260905-4jbVwK/platform_drop.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The `hill_jump_fall`, `hill_fall`, and `down_floor` captures use the same
command shape with their respective route and output names. Startup used
the default 6/3/1.5-second waits. The map/collapse capture used:

```sh
python3 tools/capture_original_player_walk.py --animation --world \
  --route platform_collapse \
  --run-dir /tmp/lezac-player-posture-20260905-4jbVwK \
  --out /tmp/lezac-player-posture-20260905-4jbVwK/platform_collapse_world.txt \
  --startup-seconds 10 --intro-seconds 8 --level-start-seconds 5 \
  --approve-procmem --approve-runtime-instrumentation
```

The capture tool launches a private Xvfb/DOSBox process through
`seed_original_level.py`; level 1 requires no level-transition seeding.
The original process is terminated by that launcher after capture.
Two earlier attempts to capture an initial plane with the default waits
timed out before the first gameplay checkpoint (`marker=0`, `frame=0`).
They produced no usable trace. Longer startup waits succeeded; those
failures are not treated as game behavior.

Captured `platform_collapse` registers at the first pre-input stop are
CS=01A2, DS=0C44, ES=3EA9, SS=18B3, saved-SP=3FA2, BP=3FEE.
The launcher's nominal DS=0C8F is a memory-base convention, not the observed
DS. Ghidra `1000:offset` anchors map to runtime `01A2:offset` in this run.
The hooks are at 6064 (before animation), 6813 (before normalized input),
6B55 (after input), and 741E (after shared integration).

## Recovered Rules

- Hard landing: `1000:6768` tests incoming VY greater than 1600. Landing
  snaps the local Y to an eight-pixel boundary, selects the temporary
  cursor, and changes VY to `-VY / 4` with signed truncation. The natural
  `hill_jump_fall` sample 131, frame 160, changes 1612 to -403.
- The landing cursor is `{17,17,18,3,3,3,1}` for player 1, but the displayed
  zero-based sprite is immediately 17. The active cursor is copied into
  backup, except idle mode initializes a one-frame idle backup. This does
  not create a drop counter.
- Down on a one-way platform selects `{17,17,19,3,3,3,1}` and writes actor
  `+0E=4` (`1000:6A47`). Each eligible update adds two to local Y, decrements
  that word, and sets idle byte F8 (`6A5E..6A76`). Solid bottom tiles 1..4C,
  nonzero VY, no bottom contact, and an already-active counter gate a new
  drop. The platform trace matches Y=162,164,166,168 on the four drop ticks.
- Player pickups scan the cached four-cell interior clockwise
  (`1000:6CB8..6DAA`), not the older post-movement 12x16 rectangle.
  Consume helper `5AFD` accepts tiles 67..72, clears unflagged words, and
  leaves FF in the byte plane for a flagged word. Caller `6D49..6D65` seeds
  the cell above, with zero velocities, when its word is nonzero/unflagged.
- Scores from DS:0002..0019 (file B192) are
  `50,100,200,250,500,800,1000,1500,2000,3000,5000,1000`.
  Objective collection increments the objective count, independently of
  that score table. The following table selects transient pickup actors;
  those actors are not yet implemented by this recovery.
- The collapse seeder `370E` preserves the glyphs and flags their words.
  It does not award destruction at seed time. The actual mover `5102`
  processes records newest-first. The new C++ implementation replaces the
  prior 24-tick timer/rectangle overlay with map movement and record state.

## Collapse Lifecycle

The 15-byte record layout is: start/end byte offsets (words), flagged word,
signed VX/VY, signed sub-X/sub-Y, previous magnitude (word), flags, rest
counter, and unsigned affected-byte weight. The first slot is DS:6620;
DS:2080 is the live count. The route captures every byte before and after
the player update, and sparse map changes relative to its initial planes.

In `platform_collapse` (144 consecutive frames, first frame 86):

- Sample 33/frame 119 collects tile 67 at (24,22). The new record is
  `060a080a0980000000000000000004`: group 9 spans (23,21)..(24,21).
- The same game frame's collapse pass adds gravity 4. Entry sample 34 has
  VY=4, sub-Y=0, magnitude=4, rest=1. Unsupported ticks reset rest before
  incrementing it, so it remains 1 while the platform falls.
- Entry sample 42/frame 128 has start/end 0A7E/0A80, VY=32, sub-Y=16,
  flags=80, rest=1. Both platform glyphs moved from row 21 to row 22.
- Sample 46 has VY=0 after its blocked downward step. Sub-Y remains 16.
- Sample 135 has rest=94. Sample 136/frame 222 has no live record and
  unflagged group-9 words in row 22. The original retirement check is 95,
  not the former reconstruction-only timer of 24.

The C++ verifier matches all 144 entry records and map deltas. It currently
does not compare post-player/pre-collapse records against a separate C++
checkpoint. The seeded probes below separately cover basic collision,
cross-record momentum, fracture map writes, and RNG. Broader shapes and
transient-actor presentation still require recovery.

## Initial Map Tail

Level 1 declares 1980 cells, but its compressed streams describe 1971 tile
bytes and 3948 word bytes. Original decoder `082D:0000` (file 8A40..8B4E)
uses the requested output length as its termination condition and ignores
the supplied compressed length. It reads stale bytes beyond the compressed
stream in the shared input buffer to fill the final partial row.

The defined payload prefixes match. Outside them, this run differs from
the port at tile index 1971 and word indices 1974..1979. The verifier
reports `initial_tile_differences=1 initial_word_differences=6`, then checks
all subsequent changes relative to each version's initial plane. It does
not inject the original's stale tail into the C++ map. This is a stated
initial-state boundary, not full initial-map parity.

## Validation and Remaining Work

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-player-posture-original tests/fixtures/player_posture_original \
  build-codex-tmp/player-posture-all-v2
```

Passed: five routes, 609 continuous motion/cursor/sprite states, 125 sprite
changes, 144 collapse/map states. An optional final argument selects one
route for diagnosis. Frame manifests include drop and collapse counts.
Original and C++ drop/hard-landing screenshots were visually inspected and
shown to the user. Camera framing differs; the screenshot pairs were not
claimed to be frame-aligned or pixel-identical.

The initial 424-case suite completed in 122.42 seconds: 406 passed, 17 failed,
one UI test skipped under dummy SDL. The log was preserved at
`build-codex-tmp/player-posture-regressions.log`. No merge is authorized by
that result. The regression corrections and final validation are below.

Required next work includes: map pickup/fracture transient actors and pickup
RNG draws; investigate actual collapse/player contact semantics; validate
larger and irregular collapse groups and multi-target momentum transfer;
and broaden natural bomb routes beyond the current placement smoke.
The both-horizontal plus up/down chord exception, portal/launch-pad order,
and player-2 runtime posture presentation remain outside these captures.

## Seeded Collapse Step Probes

`tools/capture_original_collapse_steps.py` captures one complete update per
explicitly artificial fixture state. It changes only a private DOSBox child
running the temporary asset copy, with register-preserving instruction
trampolines at `1000:5110` and `1000:567F`. The latter replays the loop
condition and stops only after the final record; it does not overlap the
next function. The three checked instruction windows match `LEZAC.EXE`.

```sh
python3 tools/capture_original_collapse_steps.py \
  --run-dir /tmp/lezac-player-posture-20260905-4jbVwK \
  --out /tmp/lezac-player-posture-20260905-4jbVwK/collapse_steps_v2.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The tool uses private Xvfb and the shared original-game launcher, with
startup/intro/level-start waits of 10/8/5 seconds. Runtime CS=01A2, DS=0C44,
ES=0C44, SS=18B3, saved-SP=3FCA, BP=3FF2 at the first entry. Thus the hook
addresses are runtime `01A2:5110` and `01A2:567F`. The fixture includes both
register snapshots for every case, as well as raw map/record bytes.

Twenty-seven probes cover rest-counter equality/wrap, gravity limits,
signed fractional steps on both axes, blocked moves, left/right tipping
and latch flags, cascade creation/suppression, contacts with new/live
debris and collapse records, newest-first updates, retirement, and the
63/64 fracture boundary. Input RNG is `12345678`, the fragment-word counter
is `4000`, and destruction begins at zero for each probe.

- A blocked downward step at VY=63 does not fracture. VY=64 fractures the
  two-cell group, adds two destruction units, and seeds two debris records.
- Fracture map glyphs are `47 + (frame & 2)`, with consecutive word IDs.
- Each fragment takes two random draws. The group then draws one cell for
  its transient actor at `1000:558C`, even if actor allocation fails. That
  final draw was missing in C++ and is now restored.
- The original new actor is also recorded, but the C++ replay explicitly
  reports `transient_actor_claim=0`; its presentation/lifetime is not covered.

Both independent captures completed. The final capture starts two frames
earlier than the first; all non-frame-dependent record/map/RNG results
agree. Its fracture glyph is 47 rather than 49, exactly as the frame rule
requires. Both captures pass the C++ replay, each with its own frame values.

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-collapse-steps-original tests/fixtures/collapse_steps_original.txt \
  build-codex-tmp/collapse-steps-v2
```

Result: 27 cases, 28 full 15-byte collapse records, four full 11-byte debris
records, map writes, RNG and destruction/word counters match. Twenty-seven
rendered C++ frames were inspected by the frame harness. These seeded tests
are not natural gameplay or pixel-parity evidence.

## Regression Corrections

All 17 initial failures are resolved without restoring placeholder rules:

- The natural collapse autoplayer now uses the captured 16-right/128-idle
  input stream. Pickup starts a two-cell platform; it moves down one row,
  remains intact, and retires 102 updates after creation at rest=95.
- Level-1 bomb placement remains reachable. Its body check permits one-way
  tiles overlapping the lower actor row, while rejecting full solid tiles.
- UI progression fixtures explicitly apply a downward impulse to shipped
  groups, then run the collapse mover until fracture. They do not award
  destruction at seed time or claim a natural full-level solution.
- Objective pickup tests use the original 800-point table entry and cached
  two-by-two footprint. The captured low pickup sound pair remains routed
  through the existing diagnostic hook; high pickups take their own branch.
- Debris/collapse pass ordering checks the real rest byte advancing 0->1.
  Frame manifests now expose `collapse0_rest`, not the removed fake timer.
- Repeated damage/death coverage uses a stationary behavior-3 monster and
  the original contact-counter path. The old arbitrary collapse rectangle
  had no cited original damage callsite. C++ enters state 2 on contact tick
  101, loses a life on tick 161, and reenters. Terrain-crush behavior is not
  claimed recovered by this replacement.

Final local validation: 426 passing tests and one dummy-SDL UI skip out of
427 in 45.39 seconds, followed by a passing interactive Xvfb test in 3.62
seconds. The full log is `build-codex-tmp/player-posture-regressions-fixed.log`.
Original/C++ gameplay frames were shown again after the fixes; timing, HUD,
and camera differences remain visible, with no pixel-parity claim.

## Fixture SHA-256

```text
down_floor.txt 17cf80050bad7f7b3337be8a83ca13b0d24c43f6fc15fbb993934db40a02a1e8
hill_fall.txt c6e8e09775cef99cb712147e1f474f5d263679f21ac5b31bc6bf2b08846afbb2
hill_jump_fall.txt 5860122ff628de51b24c1e0adca1a152764fd0184ac04319c352b3faad51fee5
platform_drop.txt 15961ce50a816796489e28307eea6aff32dd3f45ffb54adc725485a9d14b6d98
platform_collapse.txt 9f64fbee8445325117da3e719c6fba88f102e80cd153fd8bbceb7511b782ae26
platform_collapse.tiles.bin 6d27363a3381e8faadf247ad8188427cab5a09987f28fe20494520ed12b1973c
platform_collapse.words.bin 6712e35b68639ad85ed0ab81d6b836b71300e635eedf826f94ef62535d29ba6b
collapse_steps_original.txt a581bf59bbaac43af4ba330f0b8f6782fee468c16e7a1688b94ca2e3751f9957
```
