# Recovery Status

Last reviewed: 2026-04-21
Branch: `codex/sound-latch-recovery`
Baseline: `3525245` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly, gameplay, rendering
  and audio, verification, and integration/docs.
- Re-disassembled the player damage loop around `1000:7f34..804e`. The
  `1000:7f84..7f8f` block writes `DS:2074 = 0x002d`, `DS:799f = 4`, then
  calls the recovered sound latch when accumulated player damage is nonzero.
- Re-disassembled the state-2 life/reentry path around `1000:7c89..7db5`:
  actor `+0x10` is decremented before the Pascal-style `DS:79e9 + player`
  life/reentry counter is drained, player state `DS:79e5 + player` is set to
  `0` on wrap, and active-player count `DS:79b8` is decremented.
- Mapped the separate life-loss helper at `1000:30a3`: it writes
  `DS:2074 = 0x0056`, `DS:799f = 5`, and calls `1000:165a` before moving the
  actor into the death/reentry state.
- Routed accepted C++ player damage through `requestPlayerDamageSound` and
  routed `beginPlayerDeath` through `requestPlayerDeathSound`, so lethal damage
  first queues the priority-`4` hurt cue and then replaces it with the
  priority-`5` death cue.
- Mirrored the mapped death helper energy write at `1000:3134` by restoring
  player energy to `100` when entering the C++ death/reentry state.
- Added a separate `deathStateTimer` mirror for the original actor
  `+0x10 = 0x003c` countdown. It is decremented while dead and cleared on
  manual reentry, but it does not replace the current C++ reentry timeout yet.
- Updated live C++ `damagePlayer` to use the recovered unsigned byte
  underflow death rule (`energy > 0x00c8` after wrapping) instead of a modern
  `energy == 0` death clamp.
- Added `--debug-player-damage-sound` and CTest coverage for nonlethal damage,
  cooldown suppression, latch priority arbitration, and lethal replacement.
- Added `--debug-original-damage-counters` and CTest coverage for the original
  byte counter drain model: multi-hit accumulation, zero-counter silence,
  state-2 hurt-without-subtract behavior, and unsigned underflow death dispatch.
- Added `--debug-player-state2-death-fields` and CTest coverage for the
  recovered state-2 death fields, manual reentry clearing, and two-player
  zero-life player-out behavior without immediate game over.
- Updated README, Ghidra notes, and a new subagent note with the address range,
  evidence, implementation mapping, validation, and remaining unknowns.
- Rebased this branch onto `origin/main` after `3525245` merged the previous
  sound-latch recovery into main; the branch delta now carries the state-2
  death/reentry slice.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `ctest --test-dir build --output-on-failure` passed: 29/29.
- `ctest --test-dir build --output-on-failure -R "player_damage_sound|original_damage_counters|player_state2_death_fields|ui_controls_dummy|bomb_fuse"` passed.
- `./build/lezac_cpp --validate` passed.
- `./build/lezac_cpp --debug-player-damage-sound` passed.
- `./build/lezac_cpp --debug-original-damage-counters` passed.
- `./build/lezac_cpp --debug-player-state2-death-fields` passed.
- `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-ui 3` passed.
- `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-controls` passed.
- `git diff --check` passed.

## Remaining Top Gaps

- Exact actor update behavior around `1000:6053..777f`, especially monster AI
  and object/terrain interactions.
- Exact non-explosion `PROEFS.SON` semantics for bytes `+4..+5` in each
  six-byte step, plus mapping of the remaining non-explosion callsites to
  `DS:2074`/`DS:799f` and event labels.
- Exact original continuous-contact damage accumulation and cooldown timing:
  the hurt/death sounds and unsigned underflow death rule are now mapped, but
  the C++ damage cadence still uses the reconstructed cooldown model.
- Exact death/reentry state timing and presentation: the original death helper
  writes actor state `+0x15 = 2`, countdown `+0x10 = 0x003c`, and energy
  `+0x24 = 0x64`; the countdown is mirrored as diagnostic state but not yet
  used as the visual/reentry driver.
- Exact post-game presentation details beyond the recovered strings and record
  prompt order: cursor drawing, key wait timing, and completed-game flag side
  effects.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`;
  current gameplay carries the mapped records but still renders simplified
  effects.
- `GRAN.MST` field semantics.

## Next Planned Target

Map the normal state-2 return-to-active path at `1000:7ddf..7ea7`: confirm the
`DS:79a3 == 1` gate, effect-entry descent/placement checks, actor state restore
for both players, and energy reset. Then decide whether the mirrored
`deathStateTimer` can drive visible death/reentry animation without changing
the still-approximate manual reentry policy.
