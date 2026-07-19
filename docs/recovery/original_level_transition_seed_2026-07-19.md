# Original Level Transition And GRAN Runtime Capture - 2026-07-19

## Scope

`tools/seed_original_level.py` now reaches any playable original level through
the original completion, results, level-increment, reload, and intro paths. It
does not patch the level byte. Optional process-memory writes only satisfy the
current level's native objectives; the original game derives its completion
flags and performs every transition itself.

All live runs used plain DOSBox under Xvfb, a temporary copy of the shipped
assets, runtime `DS=0C8F`, and the two explicit process-memory approvals. No
repository game data or `RECS.DAT` was modified.

## Static Transition Model

`tools/ghidra/DumpLevelTransition.java` and the executable windows pinned by
`--self-check` establish:

- `DS:79B7` is a 1-based level byte. New game writes `1` at `1000:2F5A`.
- Playable levels are `1..7`. `1000:829B` treats values above `7` as the
  completed-game path, so value `8` is a sentinel rather than level 8.
- The level loader reads the destructible tile byte into `DS:79B4`, the bonus
  target word into `DS:2086`, and the destruction target byte into `DS:79B3`.
- Current bonus/destruction counters are `DS:2088` and `DS:79B5`.
  Previous-display counters are `DS:208A` and `DS:79B6`.
- `1000:3184` derives bonus flag `DS:79C5` and destruction flag `DS:79C6`
  after the corresponding current counters reach their targets.
- `1000:8283` enters the result flow only when both completion flags are set
  and the collapse queue count at `DS:2080` is zero.
- The result routine at `1000:1D61` reaches `1000:2051`, which increments
  `DS:79B7`, then reloads the next level.

The results animation needs about 10 seconds before its final blocking key
read. The next level intro types 26 characters at 81 ms each; a key during
typing removes the delay and is consumed, so the harness waits and sends a
separate intro key.

## Live Level Results

A complete target-level-7 run performed six original transitions:

| From | Bonus target | Destruction target | To |
| --- | ---: | ---: | --- |
| 1 | 1 | 50 | 2 |
| 2 | 3 | 60 | 3 |
| 3 | 7 | 20 | 4 |
| 4 | 3 | 70 | 5 |
| 5 | 8 | 65 | 6 |
| 6 | 8 | 40 | 7 |

Every gate reported both original-derived completion flags set and collapse
queue zero. Every reload reported the new targets, reset flags, and matching
current/previous counters. Captured level-2 and level-7 PNG frames were
visually inspected and showed live gameplay at the requested levels.

Example:

```sh
xvfb-run -a python3 tools/seed_original_level.py \
  --run-dir /tmp/lezac-original-level7 \
  --target-level 7 \
  --dump-runtime-state \
  --approve-procmem \
  --approve-runtime-instrumentation
```

The tool writes `original_level_N_gameplay.png` and, with
`--dump-runtime-state`, pre/post actor, visual, motion-link, camera, and view
snapshots beside it.

## Live GRAN Placement

`tools/ghidra/DumpGranPlacement.java` dumps the original generic actor reader,
camera update, visual allocator/draw path, boss link functions, head brain,
and actor update. Live level-7 snapshots confirm the static model and correct
two earlier C++ assumptions.

The placement snapshot used `--level-start-seconds 0.1`; its pre-capture table
was read about 0.1 seconds after gameplay became ready, while the post-capture
table followed the DOSBox screenshot by about one second. Later snapshots
intentionally show the same actor/link mapping after boss motion has begun.
The captures establish:

- `DS:208D` and `DS:79F9` are counts for 1-based actor and motion-link tables.
  Slot 0 is reserved; the seven actors are slots `1..7`, and the six motion
  links are slots `1..6`.
- The visual allocator count `DS:C496` is `2` before GRAN loading and `9`
  afterward. GRAN visual and link indexes therefore use rebase `+2`, not
  `+4`.
- The original initial visual slots are:

| Visual | Position | Role |
| ---: | ---: | --- |
| 2 | `(138,110)` | segment |
| 3 | `(142,104)` | segment |
| 4 | `(93,110)` | segment |
| 5 | `(88,116)` | segment |
| 6 | `(100,100)` | head, sprite frame 40 |
| 7 | `(92,118)` | segment, sprite frame 42 |
| 8 | `(139,117)` | segment, sprite frame 43 |

The head actor references visual 6. The six segment actors reference visuals
`7,8,5,4,3,2`, matching the permuted visual bytes in `GRAN.MST`. All six live
motion links target head visual 6.

The checked-in raw-table capture
`tests/fixtures/boss_runtime_original_level7.txt` is parsed by
`--debug-boss-runtime-evidence`. The diagnostic validates the fixed one-based
slots, true behavior offset `+0x15`, actor/link counts, complete visual mapping,
head box, allocator count, and `+2` rebase against the C++ live model.
It also matches all six links against the C++ `gain`, `mode`, `radiusX`,
`radiusY`, `offX`, `offY`, and `biasY` fields, including the two-spring /
four-orbit split. The runtime-advanced `phase`, `outX`, and `outY` fields are
deliberately excluded from that static motion-parameter claim.

The C++ `kBossVisualBase`, boss-model diagnostic, and autoplayer expectations
now use this live `+2` contract. `--debug-gran-boss-model` reports
`original_runtime_placement_claim=1`; exact original motion timing remains
unpromoted.

## Camera And Presentation Evidence

The level-7 snapshot recorded player visual `(840,328)`, camera
`(688,248)`, maximum camera `(800,248)`, and zero subpixel offsets. A quick
level-1 snapshot pinned the invariant view globals:

```text
view width=320 height=160
camera center_x=152 center_tile=19
buffer_source=8
page_dest=1284
```

`1284 = 4 * 320 + 4`, and overlay present copies `(width - 8)` by
`(height - 8)` from source offset 8. The original and current level-7 frames
have the same level artwork, but registration currently measures a stable
port displacement of about `(-4,-28)` for the original relative to the port.
This is retained as follow-up evidence for exact camera/map/HUD alignment; no
renderer offset was guessed in this iteration.

The colorful lower-right cluster in the natural level-7 frame is level
artwork, not the GRAN boss. Both original and port boss actors begin outside
the natural player-start viewport. The C++ `boss_level7` frame sequence keeps
that fact visible in its manifest: boss metadata moves while the rendered
natural-view hash remains unchanged.

## Validation Boundary

Promoted now:

- native reachability of original levels 1 through 7
- exact transition objective fields and completion gate
- exact GRAN actor/link index bases and visual rebase
- exact initial GRAN actor-to-visual mapping
- original view and camera globals at captured checkpoints

Still open:

- frame-by-frame original GRAN motion timing and collision outcomes
- exact camera/map/presentation transform in the C++ renderer
- a promoted paired visual fixture under the visual-claim guardrail
