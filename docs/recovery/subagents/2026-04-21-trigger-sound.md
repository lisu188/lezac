# 2026-04-21 Tile Trigger Sound Routing Workstreams

Five focused subagents were spawned for this recovery loop. Their read-only
findings were integrated with a narrow implementation: tile-trigger and portal
sound routes were changed, because their surrounding helpers and record scans
are visible in the disassembly.

## Subagent A - Ghidra/disassembly mapper

- Broadened byte-level inspection around the remaining `1000:165a` candidates.
- Local disassembly showed `1000:4b2c..4b32` is inside debris/collapse playback,
  so it is not a safe objective-pickup mapping.
- `1000:5740..586e` is the strongest implemented slice: it masks the trigger
  key, queues `DS:2074 = 0x0027` and `DS:799f = 6`, restores the caller's
  `DS:2074`, then scans the 14-byte tile-trigger rewrite records.
- `1000:5999..5a72` scans the 7-byte portal records for the word-layer key,
  copies destination coordinates into the actor frame, queues
  `DS:2074 = 0x001a` and `DS:799f = 4`, then creates the portal visual effect.

## Subagent B - Gameplay Fidelity

- Rechecked the current objective, portal, trigger, player death, level clear,
  bomb placement, monster death, bonus, and bomb-object hooks.
- Recommended replacing only the sound call at the same source location after
  the same gameplay mutation once a cursor/priority pair is confirmed.
- The implementation keeps tile rewrites, portal destinations, and cooldowns
  unchanged, and only replaces successful trigger/portal sound requests.

## Subagent C - Rendering/audio/assets

- Confirmed request-style sound routing changes scheduling semantics: the
  original-style latch can collapse multiple same-frame cues down to the
  highest accepted priority before `pumpSoundLatch`.
- Confirmed cursors `0x001a` and `0x0027` render as non-direct `PROEFS.SON`
  cursors through the flattened six-byte step payload.

## Subagent D - Verification/test harness

- Recommended direct latch-state assertions over audible SDL output.
- This loop added `--debug-trigger-sound`, `--debug-portal-sound`, and CTest
  coverage. The debug commands drive actual tiles `0x72` and `0x45` through
  `updatePortalsAndTriggers`, verify cooldowns and destination/rewrite state,
  check cursors `0x0027`/`0x001a` at priorities `6`/`4`, pump the latch, and
  verify the pumped cursor/priority.

## Subagent E - Integration/docs/refactor

- Recommended keeping raw cursor/priority writes separate from inferred event
  labels.
- Objective pickup labels remain provisional. The docs now describe the
  confirmed trigger and portal helpers by address range and state writes.

## Implemented Slice

- Mapped `1000:5740..586e` to the tile-trigger rewrite helper.
- Replaced the C++ successful tile-trigger `playSound(1)` compatibility call
  with `requestTileTriggerSound`, which queues cursor `0x0027` at priority `6`.
- Mapped `1000:5999..5a72` to the portal record helper.
- Replaced the C++ successful portal `playSound(1)` compatibility call with
  `requestPortalTeleportSound`, which queues cursor `0x001a` at priority `4`.
- Added `--debug-trigger-sound`, `--debug-portal-sound`, and CTests
  `trigger_sound`/`portal_sound`.

## Open Questions

- Objective pickup, player damage/death, monster death, level clear, and
  remaining menu/record sounds still need callsite-by-callsite mapping before
  replacing compatibility hooks.
- Bytes `+4..+5` in each `PROEFS.SON` six-byte step remain unreferenced in the
  recovered tick window.
