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

Resolved: `level1_route_timing_original_confirmation` — tick-locked
/proc-mem measurement against the original (frame counter `DS:0x78C2`)
recovered the governed 24-25 fps game rate, the flat 4 px/tick walk, the
8.8 fixed-point jump (v0=-848, gravity +64/tick, floor-to-pixel — every
observed per-tick delta reproduces exactly) and the 41-tick small-bomb
fuse; the port's walk speed (90→98 px/s), jump kinematics and fuse
(0.33s→1.67s) were corrected to match, pinned by
`tests/fixtures/route_timing_original_level1.txt` and the
`route_timing_evidence` ctest.

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

- `natural_forward_debris_writeback_3d2d` — natural forward debris writeback
  capture at `1000:3D2D`
- `exact_explosion_sprite_playback` — exact explosion/debris/collapse sprite
  playback semantics around `1000:3a56..4d3b`
- `sound_callsite_cursor_priority_map` — exact cursor/priority mapping for the
  remaining compatibility sound hooks
- `actor_update_original_contact_semantics` — original contact
  flags/passability/tile snapping around `1000:6053..777f`
- `contact_scanner_runtime_confirmation` — runtime confirmation for
  `1000:5cb0..604f`, now statically identified as the level-7 boss-head
  brain rather than a generic contact scanner
- `behavior4_branch_runtime_fixture` — behavior-4 branch semantics fixture at
  `1000:728C..731B`
- `monster_sprite_table_runtime_consumption` — original runtime consumption of
  impact/death/reward sprite frames
- `gran_mst_runtime_motion_timing` — live original capture now confirms the
  1-based actor/link tables, visual allocator count, `+2` visual rebase, and
  initial boss placement (`--debug-gran-boss-model`); exact frame-by-frame
  motion/collision timing still needs paired original evidence
- `ds79b9_fallback_runtime_reachability` — runtime reachability of the
  `DS:79b9` fallback

## Guardrails

- `tools/check_port_completion_status.py` fails when the source tables, this
  document, or the CTest summary expectation drift apart, and rejects
  duplicate or resized tables whose declared counts do not match.
- The diagnostic always reports `original_fidelity_claim=0`; promoting any
  open item requires the normal original-evidence pipeline, not an edit to
  the completion tables.
