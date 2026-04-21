# State-2 Return-To-Active Recovery

Date: 2026-04-21

## Subagent A - Disassembly Mapper

- Confirmed code-segment file offset mapping: `file offset = 0x770 + offset`.
- Mapped key return-to-active anchors:
  - `1000:7ddf` / file `0x854f`: state-2 return path begins.
  - `1000:7e74` / file `0x85e4`: requires `DS:79a3 == 1`.
  - `1000:7e97` / file `0x8607`: writes `DS:79e5 + player = 1`.
  - `1000:7ea7` / file `0x8617`: restores actor energy `+0x24 = 0x64`.
  - `1000:7ef8` / file `0x8668`: unresolved no-active-player fallback counter.
- `DS:79a3` is copied from player action key bytes: `DS:1b7b` for player 1
  and `DS:1b80` for player 2. Those bytes are set/cleared by keyboard IRQ
  scan codes `0x31`/`0xb1` and `0x52`/`0xd2`.
- The normal path reads `DS:c21e + 8 * actor[+0x01]`, computes tile occupancy
  from effect words `+0`/`+2`, may decrement effect `+2` as a placement/descent
  adjustment, then restores actor state `+0x15` to `0` for player 1 or `1` for
  player 2.

## Subagent B - Gameplay Fidelity

- Recommended using the recovered `0x003c` state-2 countdown as a hard
  return-to-active gate while keeping current C++ lives, two-player
  player-out, and compatibility reentry timeout semantics.
- Deferred riskier changes: delayed life decrement, explicit active-player
  count, and `DS:79b9` fallback behavior.

## Subagent C - Rendering/Audio/Assets

- Confirmed there is no additional sound request in the mapped
  `1000:7c89..7ea7` state-2 return path; the only confirmed state-2 audio cue
  remains death/life-loss cursor `0x0056` at priority `5`.
- Confirmed `1000:06ab` initializes a seven-byte animation state at
  `actor + 0x16`, but exact death/reentry sprite frame IDs remain unresolved
  until the playback consumer and `DS:006c`/`DS:006d` values are mapped.
- Current renderer skips dead players; a diagnostic frame would be technically
  safe but not evidence-backed as original visual fidelity.

## Subagent D - Verification

- Recommended deterministic CLI probes instead of SDL-only tests.
- Implemented `--debug-original-state2-return-model` for the original state
  byte model and `--debug-player-state2-return-active` for live C++ gate
  behavior.

## Subagent E - Integration/Docs

- Corrected the recovery status branch naming and kept the return-to-active
  scope anchored to `1000:7ddf..7ea7`.
- Kept claims conservative: the countdown now gates reentry, but exact
  effect-entry descent, fallback, and death/reentry visuals remain open.

## Integrated Decision

The C++ port now rejects manual reentry and unwinnable-level restart while the
recovered state-2 countdown is nonzero. Once the countdown reaches zero, the
existing manual reentry controls perform the current compatibility respawn.
This mirrors the proven original ordering without yet claiming exact original
effect-entry placement, delayed life-count decrement, fallback promotion, or
death/reentry rendering.
