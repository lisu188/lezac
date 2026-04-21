# Sound Latch Recovery Subagents - 2026-04-20

This pass used five read-only subagents and integrated their findings into a
focused sound-latch patch.

## A - Ghidra/Disassembly Mapper

Key findings:

- `1000:0630..06aa` loads `PROEFS.SON`. The first word is `0x0082`, a count of
  130 six-byte sound entries; the loader reads `0x82 * 6 = 780` payload bytes.
- `1000:0fbe..1088` is the PC speaker tick routine. It uses `DS:79c4` as the
  active flag, `DS:78c0` as the current cursor/direct sweep value,
  `DS:79a0..79a2` as tick/gate/period fields, and `DS:79c0` as the sound-bank
  far pointer.
- `1000:165a..167d` is the request latch. It copies pending cursor
  `DS:2074` and pending priority `DS:799f` into `DS:78c0`/`DS:799e` unless an
  active request has priority high enough to reject it.
- Explosion values `0xea74`, `0xea7e`, `0xea88`, and `0xeace` are direct
  PC-speaker sweep cursors, not `PROEFS.SON` record offsets.

## B - Gameplay Fidelity

Integrated:

- Kept existing event sound identities stable except for the high-confidence
  bomb explosion path.
- Routed bomb explosion requests through the recovered priority latch.
- Deferred latch playback until the end of the update tick so same-frame
  explosion requests arbitrate before SDL audio is queued.

Open:

- Non-explosion gameplay event priorities remain provisional until their
  direct callsite writes to `DS:2074`/`DS:799f` are implemented.

## C - Rendering/Audio/Assets

Integrated:

- Added direct-sweep synthesis for `DS:78c0 > 0xea60`, matching the tick
  routine branch that subtracts four from the cursor until it reaches
  `0xea60`.
- Kept the older five-byte chunk renderer isolated for non-explosion sounds.
- Added a raw SON payload roundtrip that verifies the converted JSON preserves
  all 780 original payload bytes.

## D - Verification/Test Harness

Integrated:

- `--debug-son-raw-roundtrip`
- `--debug-sound-priority-latch`
- `--debug-sound-selector-map`

CTest now covers those commands as `son_raw_roundtrip`,
`sound_priority_latch`, and `sound_selector_map`.

## E - Integration/Docs

Integrated:

- Added a sound playback evidence section to `docs/GHIDRA_NOTES.md`.
- Updated README and `RECOVERY_STATUS.md` to distinguish recovered latch/direct
  sweep behavior from still-approximate `PROEFS.SON` step timing.
- Kept all changes localized in `src/main.cpp`; extracting an audio helper
  remains a future maintainability task once more sound callsites are mapped.
