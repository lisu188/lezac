# Port Completion Status

Last reviewed: 2026-09-19

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

The [2026-10-06 level-export metadata correction](level_export_denominator_metadata_2026-10-06.md)
aligns all seven exported and committed destruction denominators with physical
word tags and the original `fieldB` headers. The runtime loader already used
this calculation; the change does not alter gameplay completion or prove a
newly completed level. The exporter regression verifies the original bank,
boundary words and semantic regeneration without rewriting resource files.
All broad OPEN items and global completion/fidelity flags remain unchanged.

The [natural Level 3 return regression](natural_level3_return_runtime_2026-10-05.md)
recovers the dirty-gated ammunition panel through an ordinary reserve loss and
reentry. Its full route compares 6038 RGB frames, 12000 mapped boundaries and
1422 added lifecycle boundaries, reaching eight objectives and 93 of 148
destroyed structures. Live Medium ammunition refills from eight to ten without
repainting the original's retained `08`. Level 3 completion, later levels and
all broad completion/fidelity flags remain open.

The [2026-10-05 natural campaign regression](natural_campaign_runtime_2026-10-05.md)
promotes the retained ordinary Level 1/2 completion and Level 3 entry route to
a self-contained full production replay. It checks 2,761 native-observed RGB
presentations and 5,446 mapped boundaries through three Level 2 objectives,
the 61-percent empty-collapse completion gate, result reels and carried health,
reserves and ammunition. The shorter zero-objective routes below are separate
evidence, not a statement that no earlier route finished Level 2. Later levels,
full actor state and broad whole-game completion/fidelity flags remain open.

The [ordinary Level 3 objective regression](natural_level3_objective_runtime_2026-10-05.md)
adds a fresh original-backed 650-frame movement/bomb/pickup segment after that
unchanged prefix. Its full replay checks 3,411 RGB frames and 6,746 mapped
boundaries, ending with one objective, 36 destroyed structures, 62 health and
one reserve. This is not Level 3 completion or all-actor/campaign fidelity;
all four broad OPEN items and global flags remain unchanged.

The [second Level 3 pickup regression](natural_level3_second_objective_runtime_2026-10-05.md)
adds 320 ordinary movement/jump frames without another bomb. Its complete
4758-tick route compares 3731 full RGB frames and 7386 mapped boundaries,
ending with two objectives, 36 destroyed structures, 62 health and one reserve.
It retains native-only provenance and rejects 20 semantic/fixture, fourteen
producer and 291 typed/map/palette mutations. Level 3 completion, all actor
fields and whole-game fidelity remain unverified; all four broad OPEN items
and global flags remain unchanged.

The [third Level 3 pickup regression](natural_level3_third_objective_runtime_2026-10-05.md)
adds 500 ordinary movement/jump frames and one Medium bomb. Its complete
5258-tick route compares 4231 full RGB frames and 8386 mapped boundaries,
ending with three objectives, 36 destroyed structures, 46 health and one reserve.
It retains native-only provenance and rejects 22 semantic/fixture, twelve
producer and 291 typed/map/palette mutations. Level 3 completion, all actor
fields and whole-game fidelity remain unverified; all four broad OPEN items
and global flags remain unchanged.

The [natural Level 3 portal return](natural_level3_portal_runtime_2026-10-05.md)
adds 970 ordinary frames through the lower shaft, three more objectives and a
natural teleport. The full 6228-tick route matches 5201 RGB frames and 10326
mapped boundaries, ending with six objectives and 57 destroyed structures.
It recovers the original floor sampling, consumed Down banks, preserved motion
carries and animated arrival marker without the port's invented cooldown.
Thirty semantic/fixture, twelve producer and 291 typed/map/palette mutations
are rejected. Level 3 completion, natural two-player/pool saturation, all actor
fields and whole-game fidelity remain unverified; all four broad OPEN items
and global flags stay unchanged.

The [natural Level 3 portal escape](natural_level3_portal_escape_runtime_2026-10-05.md)
adds a separately pinned 500-frame ordinary-input branch after tick 6109.
Its full 6609-tick route compares 5582 RGB frames and 11088 mapped boundaries,
collecting objectives seven and eight without a death/reentry transition or
reserve loss. It ends with eight objectives and 80 of 148 required destroyed
tiles, so Level 3 is still incomplete. Tick 6354 retains seven objectives,
26 energy, one reserve and thirteen Medium bombs for the next ordinary-input
fork. Thirty-eight semantic/fixture, twelve producer and 291 typed/map/palette
mutations are rejected. The earlier portal fixture and all four broad OPEN
items/global flags remain unchanged; all-actor and whole-game fidelity are
not claimed.

The [2026-10-05 natural Level 2 table comparison](natural_level2_runtime_2026-10-05.md)
adds two 500-frame ordinary-input routes after the pinned Level 1 completion
and handoff. Both match all displayed RGB pixels and mapped states. One also
matches 6,050 live debris-record observations, 4,151 collapse-record observations
and 1,339 naturally spawned kind-1/2 monster states through 1,000 present/post
boundaries. The compact regression drives the normal SDL input/production loop
without per-tick state injections. Both routes collect zero objectives and
do not complete Level 2. Complete campaigns, other actors/fields and physical
timing remain open; no broad OPEN item or global fidelity flag changes.

The [2026-10-05 shipped-profile constructor replay](shipped_monster_profiles_runtime_2026-10-05.md)
now exercises all 15 shipped Level 1..6 spawner profiles through native
construction, then 64 continuous actor updates for each of three RNG seeds.
Two independent original captures agree byte-for-byte; the C++ production
spawner and monster update paths match 45 constructors and 2,880 updates.
This verifies the shipped kind 1..4 profiles, behaviors 3/4, animation,
hotspots, RNG, descriptor selection and bounded room trajectories. Spawn
positions, allocation allowance, countdown, terrain and initial player state
are explicitly controlled, and per-tick player targets are exogenous in C++.
Actual level geometry, natural spawning timing, full player/world updates,
actor-pool interactions and campaigns remain unverified. It closes no broad
OPEN item and changes no whole-game completion or fidelity flag.

The [2026-10-04 tile-damage recovery](monster_tile_damage_runtime_2026-10-04.md)
matches 1,312 seeded full native behavior-4 updates, including 552 impacts,
96 fatal conversions and 96 post-motion-only damage placements. It restores
the missing impact-sprite entries for kinds 5..8 and corrects earlier compact
writeback HP attribution: original health is actor byte +0x24, not +3.
Natural constructors, other behaviors and repeated/campaign trajectories
remain unverified. All four broad items remain OPEN and global flags unchanged.

The [2026-10-04 signed-coordinate recovery](monster_coordinate_word_wrap_runtime_2026-10-04.md)
matches 768 seeded full native behavior-4 writebacks across kinds 1..8, including
120 positive and 120 negative coordinate-word wraps. The recovered monster
path now narrows its coordinates after common integration while the generic
32-bit API and other callers remain unchanged. General out-of-map scans, later
updates, other actor/behavior boundaries, natural routes and whole-game fidelity
remain unverified. This closes no broad OPEN item or global completion flag.

The [2026-10-04 monster coordinate-writeback recovery](monster_coordinate_writeback_runtime_2026-10-04.md)
matches 256 seeded full native writebacks for kinds 1..8, including 112 positions
outside the port's former level-bound clamps. The production clamp removal is
original-backed; next-update out-of-map reads, coordinate-word overflow, natural
trajectories and whole-game actor/campaign fidelity remain unverified. This
does not close any of the four OPEN items or change global fidelity flags.

The [2026-10-01 Level 1 completion-gate recovery](level1_completion_gate_runtime_2026-10-01.md)
fixes premature results entry, dirty-only objective palette requests, and
gameplay ticking during results. An ordinary-input route with default reserves
matches 305 full original frames and 610 mapped states through the native
empty-collapse gate. The subsequent [results-reel recovery](level1_results_runtime_2026-10-01.md)
matches 42 native loop-boundary frames, the whole bonus award, digit reels,
and delayed RNG draws while gameplay remains frozen. The subsequent
[unskipped typing recovery](level1_typing_runtime_2026-10-01.md) matches 89 native
draw-before-delay windows and their five-column color/shadow writes, with score
and RNG frozen until the final character delay. The subsequent
[natural handoff recovery](level1_handoff_runtime_2026-10-01.md) carries the
spent ammunition through ordinary results/intro acknowledgments and restores
the full level palette without resetting its animation phase. It matches
twelve native Level 2 entry frames, 24 mapped states and both complete map
planes. A [longer pickup-landing route](pickup_landing_runtime_2026-10-01.md)
matches 600 additional natural Level 2 frames and fixes the pickup indicator
origin after ground snap/drop. It reaches player damage and structural collapse
but no objective collection or level completion; its permanent regression is
a small seeded C++ indicator-lifetime probe. A subsequent
[walker ledge recovery](walker_ledge_runtime_2026-10-01.md) extends the route to
900 Level 2 frames and fixes an off-screen monster turn concealed by the
earlier camera coverage. The RGB, mapped-state and newly decoded monster-motion
projections match; a 32-frame seeded walker probe provides the permanent
regression. This route destroys 87 structures but collects no objective and
loses one objective tile, so it is not a Level 2 finish. Complete Level 2 progression,
typing skip/escape, two-player/English
native handoffs and physical presentation cadence remain open; these checks
do not change the whole-game completion flags or provide an overall
completion percentage.

The [two-player key-ownership recovery](key_ownership_runtime_2026-09-19.md)
checks 84 original physical-key samples and fixes reversed P1/P2 movement
ownership in the host keyboard adapter. Seven silent live SDL movement/jump
cases exercise the real interactive update path. These are input-specific
checks, not whole-game or frame-aligned visual parity.

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

The subsequent [active-fire recovery](active_fire_runtime_2026-09-19.md)
compares 64 seeded original fire blocks and moves gameplay fire out of SDL
event dispatch into the governed player update. It recovers empty-ammo latch
retention, both-latch consumption on successful and rejected construction,
unchanged weapon selection, and multiple bombs in one cell. Repeated make
events relatch fire. Natural simultaneous keyboard input, host/DOS repeat
timing and held-before-death behavior remain wider verification targets.

Resolved: `ds79b9_fallback_runtime_reachability` — an original last-life
death was captured on level 1 (lives forced to 1 via `DS:0x79EA`, killed by
own-bomb self-damage), tick-locked against `DS:0x78C2`: when the final life
is lost the game runs the `1000:7ef8..7f2a` fallback and `DS:0x79B9`
increments 0->1 (climbing to 0x11 while the game-over state is held) with
lives `DS:0x79EA` 1->0. Pinned by
`tests/fixtures/ds79b9_fallback_original_gameover.txt` and the
`ds79b9_fallback_reachability` ctest (the diagnostic reports
`original_reachability=1` with the fixture).

The full shared-wait boundary is now observed separately and replayed through
production updates in three level-7 traces: 980 states, 60 normalized views,
two timed restarts (including reserve zero), and a fire-key return. The
production per-player timeout is replaced by counter 230, state promotion,
the blocking introduction and resumed gameplay with lives preserved. The
diagnostic's one-increment promotion was corrected too. The subsequent
[waiting-state recovery](state2_prepass_runtime_2026-09-19.md) replaces its
remaining standalone predicates with production-path checks and compares 54
original P1/P2 prepasses. It recovers asymmetric upward placement, countdown
inventory minima, the latched gate, and the closed-gate 1x1 descriptor.
These are seeded state probes, not complete natural two-player routes. The older reachability
fixture's interpretation of life zero as game over is superseded: zero is
still in play; byte FF marks out. See
[the production recovery and remaining gaps](shared_death_lifecycle_runtime_2026-09-13.md).

Resolved: `state2_death_presentation_frame_compare` — a live original death
was captured (snail contact on level 1, frames plus DS snapshots showing
`DS:0x79EA` lives 2→1 and the `DS:0x79EC` energy reset on reentry); the
historical interpretation used a +6 row rebase and a smoke-puff preview.
That interpretation is superseded for gameplay by the continuous level-7
death evidence: animation advances latch `cursor-1` from the active level
bank, while the initial death descriptor is preserved. The old row preview
is debug-only. See [the current descriptor evidence](boss_mass_runtime_2026-09-08.md);
normal-bank descriptor lockstep remains a follow-up.

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

The subsequent [continuous boss recovery](boss_continuous_runtime_2026-09-06.md)
adds two 600-update full production replays without per-tick actor/RNG/timer
restoration. They fix the shared boss clock, one-based sprite indexes and
boss visual-slot order. They match 8,400 boss states, 7,200 link states,
92 pickup-effect states and 2,845,440 normalized pixels in 60 views, including
contact damage. The older `boss_lockstep_evidence` name refers to a diagnostic
that checks individually restored transitions, not full continuous gameplay.
The [continuous defeat recovery](boss_defeat_runtime_2026-09-06.md) adds
720 updates, 2,722 boss states, 3,730 effect states, 2,912 flame states and
60 exact normalized playfield views after a boundary-seeded fatal bomb.
It replaces stationary flashes with moving kind-14 bombs, corrects the
signed impact hotspot, and opens trigger-key 1000 instead of awarding points.
The subsequent [nonfatal boss-hit recovery](boss_impact_runtime_2026-09-08.md)
matches another 720 updates, 5,040 boss states, 4,320 link states and 60 exact
normalized views. It corrects link Y inputs after damage changes the head's
hotspot and verifies repeated damage without defeat. The subsequent
[largest-bomb recovery](boss_mass_runtime_2026-09-08.md) matches another
720 updates and 60 normalized views, including 120 player dying and 198
reentry-wait states. It corrects death descriptor latching, the active sprite
bank and waiting-player placement. Mixed flame masses, actual reentry input,
long waits, longer natural combat and two-player interactions remain open. Unused post-defeat
link bookkeeping and actual VGA palette/HUD comparison are not covered by
these defeat fixtures. The subsequent
[controlled full-health combat replay](boss_active_combat_runtime_2026-10-01.md)
adds 800 continuous updates without reducing head health or planting a bomb,
with 22 ordinary shots, three fire-latch reentries and 12 exact normalized
playfield views. This combines firing and death/reentry under the controlled
case-boundary setup; it does not prove a natural campaign or full-health victory.
The separate [extended full-health replay](boss_extended_combat_runtime_2026-10-01.md)
now covers a controlled boss defeat and cleanup across 3,200 continuous updates:
96 ordinary shots, ten fire-latch reentries, all seven fatal conversions at
sample 1,714, complete boss-bomb cleanup at 1,833, and 15 matching normalized
views. This removes the missing controlled full-health defeat evidence, but
does not establish natural campaign/level completion, ordinary starting
reserves, physical keyboard input or actual VGA/HUD fidelity.

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
  bottom-edge `0x4D..0x52` jump-through semantics,
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
  behaviour-4 capture below. The historical level-2 fall peaks at `vy = 704`
  and still records `gravity_clamp_exercised=0`. The later
  [walker gravity word capture](walker_gravity_word_runtime_2026-10-03.md)
  confirms the signed `0x7FF` limit in 32 seeded cases, including two word-wrap
  boundaries, and corrects the port's wide-addition mismatch. This does not
  establish a natural terminal-speed fall or close the broader contact item.

  **Behavior-2 gravity narrowed.** Two later
  [timed-actor gravity captures](timed_gravity_word_runtime_2026-10-03.md) agree
  on 64 seeded boundaries each for kind 12 timed actors and kind 13 small bombs.
  They confirm word wrapping before the signed terminal-speed limit and twenty
  landing snaps, correcting the shared timed helper's wide-addition mismatch.
  Full-helper and actual corpse/bomb caller tests separately check velocities
  and supported landing Y. Native observations end before friction/integration;
  this does not close mode-2 corpse physics, timer/animation lifecycle, natural
  spawning/trajectories or the broader contact item.

  **Dying-player gravity narrowed.** Two independent
  [P1/P2 original captures](dying_player_gravity_word_runtime_2026-10-03.md)
  each record 64 seeded behavior-2 boundaries on the real kind-0 player
  records at `DS:1B88/1BAE`, with actual actor pointers verified. They confirm
  four word wraps before the signed limit and twenty supported landing snaps,
  correcting the separate dying-player helper. Full helper and real P1/P2
  `updateWithControls()` tests check velocities and supported landing Y.
  The native phase ends before friction/integration; natural death/timer,
  animation/reentry and full player-motion fidelity remain unproven. This
  narrows the existing OPEN item without closing it.

  **Active-player airborne gravity narrowed.** Two fresh independent
  [P1/P2 original captures](active_player_gravity_word_runtime_2026-10-04.md)
  each reproduce 32 seeded active airborne boundaries on the real kind-0
  records. Selected actor-parameter guards avoid confusing their normalized
  behavior locals. Four word wraps correct the active helper's wide-addition
  mismatch; landing/posture/rebound are unchanged. Full helper and real P1/P2
  frame callers check velocity. Native observations end before input/integration;
  bottom gating, landing, full player motion and natural trajectories are not
  established. The complete captures are retained, and this item stays OPEN.

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
  these focused captures. A subsequent
  [176-case original motion capture](flyer_contact_motion_runtime_2026-10-04.md)
  now verifies seeded floor/ceiling/side combinations, tile-class boundaries,
  steering/contact order and both fractional carries across kinds 1..8 with
  explicit shared actor profiles. It corrects the common monster side-response
  word NEG before signed division at eight seeded `-32768` boundaries. Natural
  constructors/profiles, trajectories and all-level geometry, animation/damage,
  two-player interactions and full actor writeback remain unproven;
  the item stays open. See `behavior4_runtime_2026-08-10.md`. Screenshot review
  is not paired pixel parity, so `visual_claim=0` remains unchanged.
## Guardrails

- `tools/check_port_completion_status.py` fails when the source tables, this
  document, or the CTest summary expectation drift apart, and rejects
  duplicate or resized tables whose declared counts do not match.
- The diagnostic always reports `original_fidelity_claim=0`; promoting any
  open item requires the normal original-evidence pipeline, not an edit to
  the completion tables.
