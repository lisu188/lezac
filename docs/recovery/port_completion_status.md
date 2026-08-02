# Port Completion Status

Last reviewed: 2026-07-28

The C++17/SDL2 reconstruction of `LEZAC.EXE` is functionally complete: every
recovered gameplay, data, UI, and sound subsystem of the original game has a
C++ implementation with deterministic validation coverage. The diagnostic
`--debug-port-completion-status` declares this state as machine-checkable
output, and `tools/check_port_completion_status.py` keeps the source table,
this document, and the CTest expectation aligned.

The completion claim is a *functional port* claim only. Remaining
original-evidence follow-ups are fidelity verification items against the
original runtime; each stays `visual_claim=0` and
`original_fidelity_claim=0` until the matching original fixture is promoted
under the existing guardrails (`tools/check_visual_claim_guardrail.py`,
`tools/check_runtime_evidence_guardrail.py`).

## Implemented Subsystems

Each subsystem lists the representative deterministic validation entry point
reported by the diagnostic; CTest exercises these paths on every run.

- `resource_loading` — all 14 shipped data files decode (`--validate`)
- `shipped_file_manifest` — byte-exact shipped file pinning
  (`--debug-shipped-file-manifest`)
- `sprites` — SPR decode/transparency/blit (`--debug-sprite-raw-roundtrip`)
- `background` — `SFONLEF.ZBG` decode (`--export-background`)
- `palette_fonts` — palette/font raw preservation
  (`--debug-core-resource-raw-roundtrip`)
- `levels` — `LIVELS.SCH` loader (`--debug-level-raw-roundtrip`)
- `gran_mst_preservation` — opaque byte preservation
  (`--debug-gran-raw-roundtrip`)
- `sound_playback` — `PROEFS.SON` tick playback (`--debug-sound-render`)
- `sound_priority_latch` — recovered latch model
  (`--debug-sound-priority-latch`)
- `menu_ui` — menu/help/setup flows (`--debug-menu-frame-flow`)
- `records` — `RECS.DAT` load/save (`--debug-records-raw-roundtrip`)
- `record_name_entry` — cursor/typematic entry
  (`--debug-record-name-entry-cursor`)
- `player_input` — recovered fire-key/IRQ gates
  (`--debug-input-fire-key-model`)
- `bombs_explosions` — fuse/damage/lane playback
  (`--debug-autoplayer level1_bomb_route`)
- `collapse_playback` — collapse lane playback
  (`--debug-autoplayer collapse_playback_route`)
- `passable_objects_portals` — portals/weapons
  (`--debug-autoplayer portal_weapon_route`)
- `monsters_behaviors` — behaviors 1-4 and rewards
  (`--debug-autoplayer monster_behavior4_chase`)
- `monster_spawners` — spawner lifecycle
  (`--debug-autoplayer monster_spawner_cycle`)
- `level7_boss` — GRAN.MST multi-segment boss from the static consumer model
  and live original placement tables (`--debug-autoplayer boss_level7`)
- `player_death_state2` — death/state-2/reentry
  (`--debug-autoplayer death_reentry`)
- `two_player` — two-player routes/progression/HUD
  (`--debug-autoplayer two_player_progression`)
- `pause_end_flow` — pause overlay and end flow
  (`--debug-autoplayer pause_flow`)
- `autoplayer_frame_harness` — deterministic frame capture
  (`--capture-frame-sequence`)

## Open Original-Evidence Items

These are fidelity verification follow-ups tracked in `RECOVERY_STATUS.md`
under "Remaining Top Gaps". They require original-runtime evidence
(DOSBox/DOSBox-debug/process-memory captures) and do not represent missing
port functionality.

Resolved: `sound_callsite_cursor_priority_map` — the two remaining
compatibility hooks were captured live by sampling the ACCEPTED sound pair
(cursor `DS:0x78C0`, priority `DS:0x799E`; the pending scratch
`DS:0x2074`/`0x799F` is written by many routines and yields only noise):
`objective_pickup` = cursor 0x0000 priority 3 (read at the tick the
objective counter `DS:0x2088` went 0->1) and `level_complete` = cursor
0x003d priority 10 (also matching the static banner routine at file
0x250c..0x2517). The player-damage sound was observed at 0x002d/p4 in the
same runs, independently confirming the port's existing constant. This
exposed a real audible bug: `playCompatibilitySound` synthesized from the
shared index table, whose level-complete entry is 0x0027 — a different
genuine sound start — so the port played the wrong completion sound. Both
hooks now submit the captured cursor *and* the captured priority through the
recovered priority latch (`requestSoundCursor`), the same route every other
in-game callsite uses, so the recovered priority is live gameplay behaviour:
the latch accepts the pair over a seeded records-page request and rejects the
hook behind a louder pending one (`latch_accepted=1`, `pumped=0x0000/p3` and
`pumped=0x003d/p10`, `high_seed_rejected=1`). The diagnostic keeps
`latch_route_claim=inferred_accepted_pair_only`, because the values come from
the accepted words — whose only writer is the latch at `1000:165a` — while
the originating callsite is still unattributed. Pinned by
`tests/fixtures/sound_callsite_original_hooks.txt` and the
`sound_hook_evidence` ctest.

Resolved: `level1_route_timing_original_confirmation` — tick-locked
/proc-mem measurement against the original (frame counter `DS:0x78C2`)
recovered the governed 24-25 fps game rate, the flat 4 px/tick walk, the
8.8 fixed-point jump (v0=-848, gravity +64/tick, floor-to-pixel — every
observed per-tick delta reproduces exactly) and the 41-tick small-bomb
fuse; the port's walk speed (90→98 px/s), jump kinematics and fuse
(0.33s→1.67s) were corrected to match, pinned by
`tests/fixtures/route_timing_original_level1.txt` and the
`route_timing_evidence` ctest.

Resolved: `ds79b9_fallback_runtime_reachability` — an original last-life
death was captured on level 1 (lives forced to 1 via `DS:0x79EA`, killed by
own-bomb self-damage), tick-locked against `DS:0x78C2`: when the final life
is lost the game runs the `1000:7ef8..7f2a` fallback and `DS:0x79B9`
increments 0->1 (climbing to 0x11 while the game-over state is held) with
lives `DS:0x79EA` 1->0. Pinned by
`tests/fixtures/ds79b9_fallback_original_gameover.txt` and the
`ds79b9_fallback_reachability` ctest (the diagnostic reports
`original_reachability=1` with the fixture).

Resolved: `state2_death_presentation_frame_compare` — a live original death
was captured (snail contact on level 1, frames plus DS snapshots showing
`DS:0x79EA` lives 2→1 and the `DS:0x79EC` energy reset on reentry); the
presentation is the white smoke-puff sequence, BOMOMIMK sprites 73..78,
confirming a +6 bank rebase over the recovered state-2 visual rows — the
port now draws those sprites and `--capture-death-frames` reproduces the
sequence.

Resolved: `two_player_panel_artwork_frame_compare` — the two-player split
views and doubled HUD were rebuilt from an original in-container DOSBox
two-player capture and diff to the pixel floor (view frames exact, HUD at
the sprite-decode floor); see the RECOVERY_STATUS iteration entry.

Resolved: `gran_mst_runtime_motion_timing` and
`contact_scanner_runtime_confirmation` — one live level-7 campaign closed
both. `tools/seed_original_level.py` advanced the original from level 1 to
level 7 through its own results routine (six natural transitions), then 775
consecutive game ticks were sampled tick-locked on `DS:0x78C2` with one 64 KiB
pread of the whole data segment per tick. The recovered `1000:5CB0` semantics
reproduce the captured head trajectory exactly — 774/774 transitions on the
8.8 fixed-point integration including the sub-pixel fractions, and all 26 RNG
firings replayed bit-exactly through the port's own `randomRangeValue` in the
recovered roar/speed/jump draw order on the 29-tick gate. A generic contact
scanner could not produce those velocity assignments, so `1000:5CB0..604F` is
confirmed at runtime as the boss-head brain. The capture also corrected four
real port divergences: a fabricated `0x07ff` gravity clamp (the original
reaches `0x0a40`), gravity applied unconditionally instead of only when the
bottom edge flag is clear, the head being run through the generic actor
pushout (double-reflecting it and zeroing an 8.8 fraction the original keeps),
and a spurious 1 px horizontal wobble on the mode-`0xff` links, whose rule is
vertical-only with truncation toward zero. It further settles the `DS:0x79EA`
question: the motion-link table is one-based, so slot 0's bytes are the lives
and energy scalars, not a link record — there is no collision. Pinned by
`tests/fixtures/boss_lockstep_original_level7.txt` and the
`boss_lockstep_evidence` ctest, which drives the live `updateBossHead()`,
`scanBossHeadEdges()` and `updateBossLinks()` against every captured tick
rather than only replaying recovered arithmetic, so each of the five fixes
regresses the test if it is undone.

Resolved: `monster_sprite_table_runtime_consumption`. A tick-locked original
level-1 trace records 110 consecutive samples (frames 257..366), with each
sample taken from one complete 64 KiB data-segment read. The frame-257
pre-impact checkpoint is sprite `44`; the authoritative pre-fatal run is
`pre_sprite_runs=44x4,43x2`, so `last_pre_fatal_sprite=43` before sprite `47`
appears on the fatal tick (`impact_equals_death=1`). The trace also proves a
49-original-tick corpse interval normalized to 120 port engine frames, delayed
Present reward sprite `61`, 54 observed original ticks of reward visibility,
and a `+2000` collection. That reward runtime claim is limited to the observed
Present/sprite `61`; sprites `62..67` retain static table evidence. The six
Present-expiry draws are pinned in order as `59`, `13`, `389`, `136`, `443`,
and `168`, advancing RNG state from `0x90e25b93` to `0x0a08326d`. The captured
route input and player position are explicitly exogenous; the raw actor and
visual rows, timing, RNG, and score transitions are authoritative. The
fixture and production-path diagnostic report `original_runtime_claim=1` and
`visual_claim=0`. The final four draws describe two transition-effect actors
that the port consumes but does not yet instantiate or render, so neither the
visual claim nor the global original-fidelity claim is promoted. The original
Present row also carries timer byte `+2 = 100`, initial vertical velocity
`-200`, and subsequent observed motion, while the port's `BonusDrop` remains
static. This resolution promotes Present sprite identity, observed visibility,
and collection consumption, not exact reward physics or presentation.

- `natural_forward_debris_writeback_3d2d` — natural forward debris writeback
  capture at `1000:3D2D`
- `exact_explosion_sprite_playback` — exact explosion/debris/collapse sprite
  playback semantics around `1000:3a56..4d3b`
- `actor_update_original_contact_semantics` — original contact
  flags/passability/tile snapping around `1000:6053..777f`. **Partially
  recovered.** The terrain-contact core is now the original's: a 2x2 tile-cell
  edge scan with a `+4` column bias, side/top solid `1..0x4C` and bottom
  `1..0x52`, `vx` seeded only under the bottom flag, `trunc(-vx/2)` reflection
  with a fixed 1 px push, persistent 8.8 fractions, and bottom-gated gravity in
  the original's instruction order. Pinned live by `--debug-walker-turn-points`
  (`walker_turn_points` ctest) and the full lockstep
  `--debug-actor-contact-evidence` (`actor_contact_evidence` ctest,
  `tests/fixtures/actor_contact_original_level1.txt`: 1459 ticks, 2370/2370
  walker samples, spawn frames 257/347, 1429/1429 energy, 589/589 animation
  boundaries). Also recovered and pinned: the spawner dec-then-test countdown
  with reload-on-spawn (first spawn 256 ticks in, period 90), the 19x19 centre
  contact test with the `actor+0x14` bias (`|dx|<10` strict; the dy half-extent
  is byte-read but capture-weak), the vertical hotspot 6 (collision-space
  `monster.y`), the period-4 animation cadence with the boundary-latched facing
  flip, and the facing-consume-before-reflection order. The item stays OPEN:
  the evidence is one monster kind (1), one behaviour (3), one level, so
  behaviours 1/2/5/6, other kinds, per-tick tile-embedding
  damage, mode-2 corpse physics, contact multiplicity beyond 0/1, the
  bottom-edge `0x4D..0x52` jump-through semantics, the `0x7FF` gravity clamp,
  the player's own collision box and two-player are all unevidenced.
  **Narrowed.** Two of the listed gaps are now closed by level-2 captures:
  *other levels* -- `tests/fixtures/actor_contact_original_level2.txt` gives
  1232 tick rows of two kind-1 behaviour-3 walkers on level 2, confirming the
  kind-1 hotspot `+0x14 = 6`, the `+0x40`-per-tick gravity ladder
  (64..704 over 11 consecutive airborne ticks with no drift), the ground walk
  speed `|vx| = +0x0E`, and the two-tick wall response `208 -> -104 -> -208`
  (`trunc(-vx/2)` then restore-to-speed-with-reflected-sign), all replayed
  through the port's live rules by `actor_contact_level2_evidence`; and
  *behaviour 4*, whose contact response is now runtime-confirmed by the
  behaviour-4 capture below. The `0x7FF` gravity clamp remains INFERRED --
  the level-2 fall peaks at `vy = 704`, so the clamp is still unexercised by
  any capture, and the fixture records `gravity_clamp_exercised=0`.

- `behavior4_motion_runtime_fixture` — **CLOSED.** A level-2 tick-locked
  capture (`tests/fixtures/behavior4_motion_original_level2.txt`,
  `tools/capture_original_behavior4_motion_procmem.py`) records 666
  consecutive behaviour-4 ticks of a live kind-2 flyer, sampled from the REAL
  actor table `DS:0x1BAE` stride 0x26. (Every earlier capture tool pointed at
  `DS:0x74A8`, the level-file monster SPAWNER table; that misidentification is
  what produced the withdrawn bomb-fuse claim.)

  RNG attribution is clean: 616 of the 666 ticks advance the shared LCG by
  ZERO steps, 48 by exactly two, one by four — the two live kind-1 walkers
  draw nothing while walking, so a retarget tick's two draws are the flyer's.

  Recovered and pinned by `behavior4_motion_evidence`:

  - retarget cadence **14 ticks** (26 clean occurrences, re-derived from the
    rows), matching the port's `motionTimer = max(1, ai0)`;
  - velocity selection `v = -ai1 + Random(2*ai1)` with `ai1 = 271`, first draw
    to vx and second to vy — reproducing **47/48** vx and **43/48** vy when
    replayed through the port's OWN `randomRangeValue`. Every exception is a
    contact rule applied after selection in the same tick: five top-edge
    clamps to `vy = 1`, and one horizontal bounce that halves and negates the
    freshly drawn value (233 -> -116), which also fixes the ORDER — retarget
    first, contact response second;
  - only `+0x06`/`+0x08` (vx/vy), `+0x0A`/`+0x0C` (single-BYTE 8.8 fraction
    carries), `+0x16` (animation frame) and `+0x19` (delay counter) ever move,
    so the flyer runs the same integer-pixel + byte-fraction model the port
    already uses;
  - animation range `0x28..0x2a` with a 3-tick delay, inside the port's kind-2
    range.

  The level-2 kind-2 spawner's `param0Base=13 param0Range=2` and
  `param1Base=270 param1Range=2` bracket the captured `ai0 = 14` and
  `ai1 = 271`. The 25 velocity changes that consumed NO RNG corroborate the
  `-vx/2` bounce and the `vy = 1` top clamp the port already implements.
## Guardrails

- `tools/check_port_completion_status.py` fails when the source tables, this
  document, or the CTest summary expectation drift apart, and rejects
  duplicate or resized tables whose declared counts do not match.
- The diagnostic always reports `original_fidelity_claim=0`; promoting any
  open item requires the normal original-evidence pipeline, not an edit to
  the completion tables.
