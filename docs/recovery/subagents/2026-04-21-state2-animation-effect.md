# State-2 Animation/Effect Recovery

Date: 2026-04-21

## Subagent A - Disassembly Mapper

- Ghidra CLI was unavailable, so mapping used manual byte inspection with
  `file offset = 0x770 + code offset`.
- Confirmed `1000:06ab` / file `0x0e1b` writes the seven-byte animation cursor
  used at `actor + 0x16`.
- Mapped `1000:3108..311d` / file `0x3878..0x388d`: the player death/life-loss
  helper targets `actor + 0x16`, reads `DS:006c` and `DS:006d`, and calls
  `1000:06ab` with delay `3` and mode `1`.
- Mapped the actor update consumer around `1000:6053..6156`: it advances the
  cursor, then selects sprite/effect metadata through `DS:c322..c324`.
- Confirmed the state-2 return path reads `DS:c21e + 8 * actor[+0x01]` for
  placement and descent.

## Subagent B - Gameplay Fidelity

- Recommended a conservative debug-model slice rather than changing live player
  rendering before the runtime frame table is known.
- Kept lives, countdown, active-player fallback, and manual reentry behavior on
  the already recovered model.

## Subagent C - Rendering/Audio/Assets

- Confirmed `actor + 0x16` is an animation cursor, not a direct sprite id.
- Confirmed current live rendering still skips dead players, and exact
  death/reentry art cannot be claimed until `DS:006a`, `DS:006c`, `DS:006d`,
  and `DS:c324` are observed at runtime.
- Flagged sprite ranges `57..60` and `68..78` as plausible effect art by asset
  shape only; this remains an inference, not an implemented mapping.

## Subagent D - Verification

- Recommended deterministic headless debug commands for the recovered byte and
  placement models.
- Added CTest coverage for `--debug-original-state2-animation-init` and
  `--debug-original-state2-effect-placement`.

## Subagent E - Integration/Docs

- Kept this iteration scoped to evidence-backed debug models and documentation.
- Updated README, Ghidra notes, and recovery status to distinguish proven
  animation/effect state from still-unproven live sprite playback.

## Integrated Decision

The C++ port now has deterministic probes for the original state-2 animation
initializer and effect-entry placement/descent math. Live death/reentry
rendering remains intentionally unchanged until DOSBox debugger observation
captures the runtime frame globals and `DS:c324` table entries.
