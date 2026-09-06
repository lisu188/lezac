# Port Completion Status

Last reviewed: 2026-09-06

The C++17/SDL2 reconstruction of `LEZAC.EXE` is not yet functionally complete.
The earlier claim was based on a subsystem inventory and compatible tests,
not a complete comparison with original behavior. The 2026-09-05 player and
collapse captures exposed absent pickup handling and a placeholder collapse
timer in place of actual map movement. Recovery is in progress; see
[the runtime evidence](player_posture_collapse_runtime_2026-09-05.md).
`--debug-port-completion-status` now reports `port_functionally_complete=0`.
`tools/check_port_completion_status.py` keeps the inventory and that claim
aligned with the CTest expectation.

Remaining work includes both functional recovery and original-evidence
verification. Claims stay `visual_claim=0` and
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

These are historical fidelity follow-ups tracked in `RECOVERY_STATUS.md`.
New [shared-capacity evidence](shared_actor_capacity_runtime_2026-09-06.md)
covers 16 original bomb/spawner allocation boundaries and fixes spawning
before same-frame effect expiry. The subsequent [shared-order recovery](shared_actor_order_runtime_2026-09-06.md)
matches 410 original passes and 7,685 ordered actor states, replacing grouped
updates with stable shared dispatch, in-place conversion and same-pass tail
appends. The subsequent [visual-order recovery](visual_order_runtime_2026-09-06.md)
matches 80 controlled overlapping-actor views and 2,821,120 normalized pixels,
including clipping and shake. Boss-link repair and other constructor paths
remain open. New guarded descriptor captures also contradict the older
launch-marker invisibility claim. The subsequent [actual launch recovery](launch_marker_runtime_2026-09-06.md)
resolves it with level-6/7 original input, 30-slot boundaries, fractional
player starts and complete marker lifetimes. Its 240 controlled views match
11,381,760 normalized pixels, using the observed original backdrop. Natural
launch routes and wider two-player interactions are not closed by these probes.
They are not an exhaustive list of functional recovery gaps. Missing
shared-actor allocation/interaction edge cases, collision semantics, and complete
natural bomb/collapse progression still need implementation and original
evidence. Pickup/fracture transients now have focused original replays; see
[transient actor evidence](transient_actors_runtime_2026-09-05.md). Normal
corpse-expiry particles and fading actors also have
[focused original replays](monster_death_transients_runtime_2026-09-05.md).
Reward motion and expiry now have
[nine continuous original replays](reward_lifecycle_runtime_2026-09-06.md).
Normal corpse motion/countdown and seeded kind-1 fatal conversion now have
[12 continuous original replays](corpse_lifecycle_runtime_2026-09-06.md).
Nonfatal impact and zero-based HP conversion now have
[143 continuous original states](monster_impact_runtime_2026-09-06.md).
Live explosion propagation and delayed repeated damage now have
[1,040 continuous original states](flame_lifecycle_runtime_2026-09-06.md),
including all four weapons, player damage and fatal monster/reward states.
Another [520 original states](flame_chain_capacity_runtime_2026-09-06.md)
cover basic chain reactions, pool limits and compaction. Natural collection
routes, flagged-word chain interactions and two-player flames still need
broader recovery and verification. This
does not close the broader actor-pool or rendering fidelity gaps. There is no
definitive whole-game rendering result. New [render-boundary evidence](render_boundary_runtime_2026-09-06.md)
matches 60 controlled full/split-width views (2,115,840 pixels), fixing the
two-player backdrop pitch and shake row-crossing foreground. Another
[71 tall-level views](tall_background_runtime_2026-09-06.md) match 3,002,304
normalized pixels and recover background overreads into allocator metadata
and the live map. Screenshot inspection separately exposed unrecovered
runtime red-palette changes at indices 230..235. The subsequent
[red-palette recovery](red_palette_runtime_2026-09-06.md) matches 244 original
fixed-scene frames and 11,571,456 pixels using sampled VGA colors, including
the update cadence and frame/byte rollover. Live actor
ordering, HUD phase and natural-route rendering still need evidence. There is no
defensible overall completion percentage without an exhaustive behavior
inventory; the test pass rate is not a completion metric.

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
recovered the governed 24-25 fps game rate, the 4 px/tick cruising walk, the
8.8 fixed-point jump (v0=-848, gravity +64/tick, floor-to-pixel — every
observed per-tick delta reproduces exactly). The earlier 41-tick small-bomb
fuse claim was withdrawn: it sampled a monster spawner, not a bomb. The
movement evidence is pinned by
`tests/fixtures/route_timing_original_level1.txt` and the
`route_timing_evidence` ctest.

The subsequent [player movement recovery](player_walk_runtime_2026-09-05.md)
corrects the earlier instantaneous-speed interpretation. Five original input
streams now match 445 continuous production updates in X/Y, VX/VY and both
fractional carries, covering acceleration, grounded braking, reversal,
reacceleration, airborne coasting, ceiling contact, landing and the weapon
chord. Input adds 64 toward the nominal 1024 threshold; grounded coasting
subtracts 42. Gravity/landing runs before input, and the jump impulse precedes
shared collision and Y/X integration. This does not close exact animation,
hard-landing presentation, step-hop runtime or all-level interaction fidelity.

The subsequent [player animation recovery](player_animation_runtime_2026-09-05.md)
matches 814 motion/cursor/descriptor states with 161 sprite changes: 808
natural-motion samples and six explicitly cursor-seeded samples. Walking,
coasting, direction changes, short idle pauses and airborne sprite cadence
now use the original pre-input advancement and speed-dependent delay. The
controlled mode-3 probe confirms restoration from backup to active cursor.
This narrows the animation follow-up above, but does not close hard-landing,
down-key, portal/death/reentry or live P2 presentation evidence.

Bomb fuse timing is now independently recovered from the actual actor table
at `DS:1BAE`, field `+0x02`: constructor seeds 20/30/40/200, subtracting the
odd-frame bit, with first update on the frame after placement. Eight original
traces cover both phases of all four weapons; see
[bomb fuse runtime evidence](bomb_fuse_runtime_2026-09-05.md). A subsequent
[bomb motion recovery](bomb_motion_runtime_2026-09-05.md) matches 16 original
idle, left, right and jump throws across all four weapons: inherited launch
velocity, collision, gravity, friction, fractional carry and sprite-height
offsets. These focused traces do not establish complete explosion visual
parity or unrestricted cross-gameplay lockstep.

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
49-original-tick corpse interval (the historical port used 120 frames; the
new atomic lifecycle evidence establishes 49/50 updates by fatal phase), delayed
Present reward sprite `61`, 54 observed original ticks of reward visibility,
and a `+2000` collection. That reward runtime claim is limited to the observed
Present/sprite `61`; the later seeded reward-lifecycle replay covers motion
for all seven types, not natural selection or collection for all types. The six
Present-expiry draws are pinned in order as `59`, `13`, `389`, `136`, `443`,
and `168`, advancing RNG state from `0x90e25b93` to `0x0a08326d`. The captured
route input and player position are explicitly exogenous; the raw actor and
visual rows, timing, RNG, and score transitions are authoritative. The
fixture and production-path diagnostic report `original_runtime_claim=1` and
`visual_claim=0`. The final four draws describe two transition-effect actors,
now instantiated and rendered by the death-effect recovery. The original
Present row also carries timer byte `+2 = 100`, initial vertical velocity
`-200`, and subsequent observed motion. The newer reward-lifecycle replay
linked above verifies those physics, countdown and fade states continuously.
The older trace's own promotion remains limited to Present sprite identity,
observed visibility and collection consumption. Global actor ordering,
natural corpse physics and pixel fidelity remain open;
`original_fidelity_claim=0` is unchanged.

- `natural_forward_debris_writeback_3d2d` — natural forward debris writeback
  at `1000:3D2D`. **Now OBSERVED; the blend formula remains open.**
  This item was recorded as blocked because `3D2D` is an intra-frame staging
  write that tick-locked sampling cannot see. That reasoning was incomplete:
  `3D2D` writes `debris[0x0B*(tag-0x4E20) + 4] = result`, the STRUCK record's
  vx field, and that value PERSISTS, so the next tick-locked sample shows its
  effect. What the earlier 201-tick window lacked was a fragment-on-fragment
  strike, not resolution.
  `tools/capture_original_natural_forward_debris_procmem.py` bombs a stacked
  pile of eleven adjacent seedable sites on level 2 (tiles 26..30 x 37..40) to
  force strikes and samples the whole debris record table (`DS:0x2093`, stride
  0x0B) for 3927 ticks. Three events occur in which a record's vx changes
  while EVERY other byte of that record -- tile, word, vy, both
  sub-accumulators, rest counter, lookup glyph and aux -- is byte-identical
  across the tick. Nothing else in the recovered model can do that: friction
  moves vx by exactly +/-1, the bounce moves it by `Random(0x1E)-15` AND
  clears vy, and a retire+reseed resets the rest counter and sub-accumulators.
  Pinned by `natural_forward_debris_writeback`, which re-derives the events
  from the rows rather than trusting the fixture's count.
  The natural trace still lacks the contributing inputs and per-row live
  bounds, so it does not establish the formula, live-record membership or
  a complete natural collision replay. The
  [retirement correction](debris_rest_runtime_2026-09-05.md) demonstrates
  why persistent raw slots must not be treated as live records; the natural
  samplers now exclude inactive tails. A separate
  [seeded original collision capture](debris_impact_runtime_2026-09-05.md)
  now validates the single-target weighted average, signed truncation,
  newest-record matching, bounce-before-blend order and same-tick seeding.
  The production mover implements that bounded path. The historical trace's
  `port_models_blend=0` header is preserved as capture-time metadata; its
  diagnostic now reports the current implementation separately. The open
  item remains pending a complete natural-route comparison, not a missing
  single-target arithmetic implementation.
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

- `behavior4_motion_runtime_fixture` — **Partially recovered, still open.** A level-2 tick-locked
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
    rows), consistent with `ai0=14`; this interval alone does not identify
    private versus shared-clock phase. The level-3 replay below settles that;
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
  **Level-3 extension and corrected scope.** This item previously named `1000:728C..731B` as
  the behavior-4 branch. The shipped bytes disprove that: the behavior-4 arm
  ends `1000:714F e9 da 01` (`jmp 0x732C`), stepping clean past the window, and
  the window's only external entry is `1000:7152 3c 03` / `1000:7154 74 03`
  (`cmp al,3 / je`). Its gate local `[bp-0x20]` is written at exactly four
  sites (`716B`, `71A0`, `71F3`, `723D`), all before the window inside the
  behavior-3 arm. A behavior-4 actor therefore never executes that window on
  any level, so the fixture as originally specified was unfillable — which is
  why the candidate skeleton could never be completed. Pinned by
  `tools/check_behavior4_window_attribution.py` and the
  `behavior4_window_attribution` ctest. The behavior-4 *motion* path
  (`1000:70D7..714F`, `73E5`, `741B`) is the correct target. Two original
  level-3 captures now pin 318 production motion transitions for a kind-2
  flyer: the shared 16-bit modulo clock, zero-velocity spawn waiting,
  truncating horizontal/diagonal homing, ten isolated far-retarget RNG pairs,
  persistent 8.8 fractions and one top collision. The near-player phases are
  explicitly seeded, not natural routes. Other kinds and remaining levels,
  two-player targeting and full floor/side runtime coverage remain outside
  these focused captures;
  the item stays open. See `behavior4_runtime_2026-08-10.md`. Screenshot review
  is not paired pixel parity, so `visual_claim=0` remains unchanged.
## Guardrails

- `tools/check_port_completion_status.py` fails when the source tables, this
  document, or the CTest summary expectation drift apart, and rejects
  duplicate or resized tables whose declared counts do not match.
- The diagnostic always reports `original_fidelity_claim=0`; promoting any
  open item requires the normal original-evidence pipeline, not an edit to
  the completion tables.
