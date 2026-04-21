# 2026-04-21 Bomb Object Sound Routing Workstreams

Five focused subagents were spawned for this recovery loop. Their read-only
findings were integrated conservatively: objective pickup and portal/trigger
sound labels remain candidates, while the bomb-object score cue was implemented
because its surrounding loop is visible in the disassembly.

## Subagent A - Ghidra/disassembly mapper

- Enumerated additional `DS:2074` / `DS:799f` writes before calls into the
  `1000:165a` latch family.
- Confirmed candidate callsites including `1000:4b2c..4b32`,
  `1000:575d..5768`, `1000:5a0e..5a19`, `1000:5e81..5e8c`,
  `1000:6e34..6e3f`, `1000:6f88..6f8d`, and `1000:7381..738c`.
- The semantic labels for objective and portal/trigger remain provisional until
  broader surrounding control flow is decoded.

## Subagent B - Gameplay Fidelity

- Rechecked the current C++ objective, portal, and trigger hooks.
- Recommended leaving `playSound(index)` compatibility hooks in place until the
  exact cursor/priority writes for those events are proven.
- Flagged the global sound latch as a meaningful gameplay detail in two-player
  and same-frame event cases.

## Subagent C - Rendering/audio/assets

- Re-rendered the known cursor starts and confirmed the current flattened
  `PROEFS.SON` playback remains deterministic.
- Flagged cursor `0x0000` as a native start-cursor case where the original tick
  routine increments `DS:78c0` before indexing the six-byte step table.

## Subagent D - Verification/test harness

- Recommended adding focused debug commands that inspect cursor/priority state
  directly instead of relying on SDL audio output.
- This loop added `--debug-bomb-object-sound` and CTest coverage for the
  priority-`3` default/high bomb-object requests and their suppression behind
  an already-latched explosion cue.

## Subagent E - Integration/docs/refactor

- Recommended keeping confirmed original evidence separate from inferred
  event labels.
- The docs now describe the implemented bomb-object sound slice by address
  range and data writes, while objective/portal sound mapping stays on the
  remaining-gap list.

## Implemented Slice

- Mapped `1000:6cb3..6e3f`: the original clears `DS:2074` and `DS:79ab`,
  scans the four bomb-object offsets, sets `DS:79ab = 1` when a consumed object
  tile id is above `0x6c`, and after the scan queues priority `3`.
- The default request leaves `DS:2074 = 0x0000`; the high-object branch writes
  `DS:2074 = 0x0012` before calling the sound latch.
- The C++ `explode` path now records whether any bomb object was consumed and
  whether any consumed tile was above `0x6c`, then queues the corresponding
  recovered object cue once after the footprint scan.

## Open Questions

- Objective pickup, portal/trigger transitions, player death, monster death,
  level clear, and the remaining menu/record sound callsites still need broader
  surrounding disassembly before replacing compatibility hooks.
- Bytes `+4..+5` in each `PROEFS.SON` six-byte step remain unreferenced in the
  recovered tick window.
