# Player Damage And Death Sound Recovery

Date: 2026-04-21

## Subagent A - Disassembly Mapper

- Confirmed `1000:7f84..7f8f` as the player hurt/damage sound request.
  The bytes at file offset `0x86f4` write `DS:2074 = 0x002d`,
  `DS:799f = 0x04`, and call the sound latch at `1000:165a`.
- Confirmed the surrounding loop calls the actor update routine at
  `1000:6053`, subtracts accumulated per-player damage from the live energy
  byte, and only then checks whether damage was nonzero.
- Confirmed the life-loss helper at `1000:30a3` is separate: it writes
  `DS:2074 = 0x0056`, `DS:799f = 0x05`, calls `1000:165a`, then moves the
  actor into the death/reentry state. The field writes at `1000:3123..3134`
  set actor byte `+0x15 = 2`, word `+0x10 = 0x003c`, and energy byte
  `+0x24 = 0x64`.

## Subagent B - Gameplay Fidelity

- Recommended placing the hurt cue only in the shared `damagePlayer` gate after
  the dead/cooldown guard and after accepted energy loss. That covers monster
  contact, debris/collapse hazards, bomb blasts, and both players without
  duplicating calls in individual hazards.
- Recommended preserving the global latch; same-frame two-player damage and
  fatal damage should arbitrate through the existing priority rule.

## Subagent C - Rendering/Audio/Assets

- Confirmed cursor `0x002d` is a bounded `PROEFS.SON` cursor already covered by
  the stop map: it stops at cursor `0x0031`, spans four six-byte steps, and
  renders 2361 samples through the current recovered cursor synthesizer.
- Confirmed cursor `0x0056` is also a bounded `PROEFS.SON` cursor: it stops at
  cursor `0x0069`, spans 19 six-byte steps, and renders non-empty synthesized
  output.
- Confirmed priority `4` means the hurt cue can replace priority `3` cues, tie
  and refresh other priority `4` cues by call order, and lose to priority
  `5+` cues such as death/life-loss, bonus, and stronger explosions.

## Subagent D - Verification

- Recommended a command-line debug probe rather than an SDL audio test.
- The implemented `--debug-player-damage-sound` now asserts nonlethal accepted
  damage latches cursor `0x002d` priority `4`, cooldown blocks repeated damage
  cues, priority arbitration follows the original latch rule, lethal damage
  ends with cursor `0x0056` priority `5`, and the death helper restores energy
  to `100`.
- Added CTest `player_damage_sound` with a regex over the recovered cursor and
  priority values.
- Added `--debug-original-damage-counters` and CTest coverage for the original
  counter-drain model: accumulated per-player byte damage is subtracted once,
  zero-damage passes are silent, actor state `2` skips subtraction but can still
  request hurt, and unsigned byte underflow dispatches death when the wrapped
  energy exceeds `0x00c8`.

## Subagent E - Integration/Docs

- Kept hurt/damage and death/life-loss wording separate. The player hurt cue is
  `0x002d` priority `4`; the death/life-loss helper is `0x0056` priority `5`.
- Updated README and Ghidra notes with the address ranges, evidence, mapped C++
  functions, and the remaining limitation that exact continuous-contact damage
  timing is still approximated by the current cooldown model.

## Integrated Decision

The C++ port now routes accepted damage through `requestPlayerDamageSound`,
routes `beginPlayerDeath` through `requestPlayerDeathSound`, and restores the
player energy value to `100` on death. On fatal damage, the hurt request is
issued first and then replaced by the higher-priority death request, matching
the recovered `1000:165a` latch semantics. The original `+0x10 = 0x003c`
countdown is documented but not mapped to the C++ reentry timer yet. The
original counter model is now locked by a debug probe before changing the live
cooldown-based gameplay cadence.
