# 2026-04-20 Sound Cursor Recovery Workstreams

Five focused subagents were spawned for this recovery loop and their findings
were integrated into the cursor-based `PROEFS.SON` patch.

## Subagent A - Ghidra/disassembly mapper

- Rechecked `LEZAC.EXE` bytes using `file_offset = 0x770 + CS_offset`.
- Confirmed `1000:0fbe..1088` as the INT 1Ch sound tick routine:
  non-direct playback reads `sound_bank + (DS:78c0 * 6) - 6`, uses word
  `0x7530` as the stop sentinel, copies byte `+2` to `DS:79a1`, copies byte
  `+3` to `DS:79a2`, and does not reference bytes `+4..+5` in the recovered
  window.
- Reconfirmed `1000:165a..167d` as the request latch and `1000:414a` /
  `1000:75f1..75fb` as direct-sweep explosion request paths.

## Subagent B - Gameplay Fidelity

- Enumerated remaining approximate sound hooks in `src/main.cpp`: objective
  pickup, portal/trigger transitions, player damage/death, level clear, bomb
  placement, monster death, and bonus pickup.
- Recommended keeping explosion routing unchanged and replacing non-explosion
  hooks only as their cursor/priority writes are proven.
- The branch around `1000:6e4b..6f8d` was selected for this slice because it
  applies pickup effects and then queues cursor `0x0008` at priority `5`.

## Subagent C - Rendering/audio/assets

- Confirmed the raw sound payload shape as `u16le 0x0082` plus `0x82 * 6`
  payload bytes.
- Recommended keeping the JSON record chunking as a compatibility container but
  rendering from a flattened six-byte step view.
- Identified direct-sweep rendering as a separate path from banked
  `PROEFS.SON` cursor playback.

## Subagent D - Verification/test harness

- Recommended keeping `son_raw_roundtrip`, `sound_render`,
  `sound_priority_latch`, and `sound_selector_map` as core audio gates.
- Suggested making the latch pump result textual; `--debug-sound-priority-latch`
  now prints the post-pump cursor/priority state.
- Suggested a deterministic cursor-segment check; `--debug-sound-cursor-segments`
  now validates the shipped stop-cursor map and renders known cursor starts.

## Subagent E - Integration/docs/refactor

- Recommended documenting confirmed evidence separately from unknown fields.
- The Ghidra notes now explicitly map `loadSon`, `synthesizeSoundCursor`,
  `synthesizeDirectSweep`, and the latch helpers to their source ranges.
- Remaining unknowns are kept visible: bytes `+4..+5` in each six-byte sound
  step, most non-explosion callsite mappings, collapse/debris playback, and
  `GRAN.MST`.

## Implemented Slice

- Flattened `PROEFS.SON` JSON chunks into a 130-step payload view without
  changing the resource format.
- Added `synthesizeSoundCursor` for non-direct playback using the recovered
  six-byte step layout and `0x7530` stop sentinel.
- Changed latch pumping so non-direct cursors render by cursor rather than by
  the old five-byte chunk approximation.
- Routed bonus pickup audio through `requestSoundCursor(0x0008, 5)`.
- Added `--debug-sound-cursor-segments` and CTest coverage.

## Open Questions

- The meaning of bytes `+4..+5` in each sound step remains unknown.
- The exact cursor/priority writes for objective pickup, portal/trigger,
  player death, bomb placement, monster death, level clear, and end-run stingers
  still need callsite-by-callsite mapping before replacing their compatibility
  `playSound(index)` hooks.
