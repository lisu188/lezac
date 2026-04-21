# State-2 Death/Reentry Recovery

Date: 2026-04-21

## Subagent A - Disassembly Mapper

- Confirmed `1000:30a3` queues the death/life-loss sound and writes the actor
  death fields: `+0x15 = 2`, `+0x10 = 0x003c`, and `+0x24 = 0x64`.
- Mapped the state-2 drain path around `1000:7c89..7db5`. It decrements actor
  word `+0x10`, waits for zero, then decrements the Pascal-style
  `DS:79e9 + player` life/reentry counter (`DS:79ea` for player 1,
  `DS:79eb` for player 2).
- When that byte wraps to `0xff`, the original marks `DS:79e5 + player = 0`
  and decrements active-player count `DS:79b8`. When lives remain, it sets
  `DS:79e5 + player = 2` and initializes a visual/effect entry for reentry.
- Identified the normal return-to-active path at `1000:7ddf..7ea7` as a future
  target: it waits for `DS:79a3 == 1`, restores actor state for player 1 or 2,
  writes `DS:79e5 + player = 1`, clears two player bytes, and resets energy.

## Subagent B - Gameplay Fidelity

- Recommended mirroring the original `+0x10 = 0x003c` countdown separately from
  the current C++ `kReentryTicks` timeout. The original countdown is proven as
  actor state, but not as the player-facing manual reentry policy.
- Recommended not deferring C++ life decrement or changing `kReentryTicks` until
  the original state-2 life/reentry path and input gating are mapped more
  completely.

## Subagent C - Rendering/Audio/Assets

- Confirmed `0x0056` is a bounded `PROEFS.SON` cursor ending at `0x0069`.
- Confirmed `1000:06ab` initializes a seven-byte animation-state structure at
  `actor + 0x16`; it does not prove exact sprite indices yet.
- Current rendering still skips dead players and does not display a recovered
  death/reentry animation, so visual fidelity remains open.

## Subagent D - Verification

- Recommended focused CLI probes for death fields and state-2 behavior.
- Implemented `--debug-player-state2-death-fields` and CTest coverage. It
  asserts the recovered death sound, energy reset, `deathStateTimer = 60`,
  velocity/grounded clearing, manual reentry clearing the timer, and two-player
  zero-life player-out behavior without immediate game over.

## Subagent E - Integration/Docs

- Kept state-2 actor countdown wording separate from the C++ reentry timeout.
- Documented the live C++ improvement to unsigned byte underflow death dispatch
  while keeping the original multi-hit counter cadence listed as approximate.

## Integrated Decision

The port now mirrors the original death-state countdown as `deathStateTimer`
and uses the recovered unsigned byte underflow test for player death. The
state-2 countdown is diagnostic state for now; the C++ manual reentry timeout
and visual presentation remain compatibility behavior until the
`1000:7ddf..7ea7` return-to-active path is mapped in more detail.
