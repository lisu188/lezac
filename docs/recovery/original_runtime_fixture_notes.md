# Original Runtime Fixture Notes

original_runtime_fixture_notes=1

These notes back the runtime evidence ledger. They summarize checked-in
fixtures captured from the original executable through DOSBox/debugger or
process-memory instrumentation. Every fixture listed here remains
`visual_claim=0`: it proves runtime bytes, register segments, route state, or
control-flow reachability, not exact rendered presentation.

## Explosion Playback And Lane Helpers

- `explosion_playback_oracle_original_3cd4_lane_div_scratch_runtime.txt`
  captures the forward lane divider setup before the far divide helper.
- `explosion_playback_oracle_original_3ce3_lane_div_scratch_runtime.txt`
  captures the actual forward far divide call registers.
- `explosion_playback_oracle_original_3d1b_lane_write_scratch_runtime.txt`
  captures a forward collapse lane write through scratch instrumentation.
- `explosion_playback_oracle_original_3d1b_lane_write_trampoline_runtime.txt`
  captures the safe-trampoline forward collapse lane writeback.
- `explosion_playback_oracle_original_3d2d_lane_write_runtime_seeded.txt`
  captures the seeded forward debris lane writeback path.
- `explosion_playback_oracle_original_3d2d_lane_write_trampoline_no_freeze.txt`
  records a no-freeze trampoline attempt for the forward debris writeback.
- `explosion_playback_oracle_original_3d3f_lane_result_route_step_no_freeze.txt`
  records a natural route-step attempt that armed the forward result patch but
  did not freeze.
- `explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded.txt`
  captures the seeded forward final result writeback path.
- `explosion_playback_oracle_original_3eaf_lane_write_trampoline_runtime.txt`
  captures the safe-trampoline reverse collapse lane writeback.
- `explosion_playback_oracle_original_3ec1_lane_write_runtime_seeded.txt`
  captures the seeded reverse debris lane writeback path.
- `explosion_playback_oracle_original_3ec1_lane_write_trampoline_no_freeze.txt`
  records a no-freeze trampoline attempt for the reverse debris writeback.
- `explosion_playback_oracle_original_3ed3_lane_result_runtime.txt`
  captures the reverse final result writeback path.
- `explosion_playback_oracle_original_4b6a_runtime.txt` captures reachability
  of the high-debris zero-target branch.
- `explosion_playback_oracle_original_4c75_bp4_scratch_runtime.txt` captures
  the live positive `[BP-4]` word gate value.
- `explosion_playback_oracle_original_4c75_runtime.txt` captures reachability
  of the high-debris word gate.
- `explosion_playback_oracle_original_4c96_runtime.txt` captures reachability
  of the forward effect/lane helper callsite.
- `explosion_playback_oracle_original_4c99_temp_copy.txt` captures the forward
  helper return and helper-written collapse lane bytes.
- `explosion_playback_oracle_original_4ca9_runtime.txt` captures reachability
  of the reverse effect/lane helper callsite.
- `explosion_playback_oracle_original_4cac_temp_copy.txt` captures the reverse
  helper return and helper-written collapse lane bytes.

## State-2 Runtime Frame Table

- `state2_runtime_frame_oracle_original.txt` captures the original state-2
  runtime frame-table cursor and global bytes for the dead-player visual path,
  including the row-byte-3 sequence `43,44,45,46,47,48` across frames
  `0x4a..0x4f`.
- `visual_table_oracle_original_state2_runtime.txt` normalizes the same
  original stop into the renderer-facing visual-table oracle. It binds actor
  frame `0x4a` to row address `DS:c44a`, row bytes `10,10,7d,43`, runtime
  `CS=01ED` / `DS=0C8F`, row byte 3 as the `BOMOMIMK` sprite-index candidate
  `0x43`, and effect placement `0x0068,0x00a8`, while keeping
  `visual_claim=0` until a paired frame comparison proves presentation.
