# Port Completion Status

Last reviewed: 2026-07-19

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

- `natural_forward_debris_writeback_3d2d` — natural forward debris writeback
  capture at `1000:3D2D`
- `exact_explosion_sprite_playback` — exact explosion/debris/collapse sprite
  playback semantics around `1000:3a56..4d3b`
- `actor_update_original_contact_semantics` — original contact
  flags/passability/tile snapping around `1000:6053..777f`
- `behavior4_branch_runtime_fixture` — behavior-4 branch semantics fixture at
  `1000:728C..731B`
- `monster_sprite_table_runtime_consumption` — original runtime consumption of
  impact/death/reward sprite frames

## Guardrails

- `tools/check_port_completion_status.py` fails when the source tables, this
  document, or the CTest summary expectation drift apart, and rejects
  duplicate or resized tables whose declared counts do not match.
- The diagnostic always reports `original_fidelity_claim=0`; promoting any
  open item requires the normal original-evidence pipeline, not an edit to
  the completion tables.
