# Recovery Status

Last reviewed: 2026-04-21
Branch: `codex/sound-latch-recovery`
Baseline: `f7927e1` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly, gameplay, rendering
  and audio, verification, and integration/docs.
- Re-disassembled the player damage loop around `1000:7f34..804e`. The
  `1000:7f84..7f8f` block writes `DS:2074 = 0x002d`, `DS:799f = 4`, then
  calls the recovered sound latch when accumulated player damage is nonzero.
- Mapped the separate life-loss helper at `1000:30a3`: it writes
  `DS:2074 = 0x0056`, `DS:799f = 5`, and calls `1000:165a` before moving the
  actor into the death/reentry state.
- Routed accepted C++ player damage through `requestPlayerDamageSound` and
  routed `beginPlayerDeath` through `requestPlayerDeathSound`, so lethal damage
  first queues the priority-`4` hurt cue and then replaces it with the
  priority-`5` death cue.
- Added `--debug-player-damage-sound` and CTest coverage for nonlethal damage,
  cooldown suppression, latch priority arbitration, and lethal replacement.
- Updated README, Ghidra notes, and a new subagent note with the address range,
  evidence, implementation mapping, validation, and remaining unknowns.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `ctest --test-dir build --output-on-failure` passed: 27/27.
- `ctest --test-dir build --output-on-failure -R player_damage_sound` passed.
- `./build/lezac_cpp --validate` passed.
- `./build/lezac_cpp --debug-player-damage-sound` passed.
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
  the hurt/death sounds are now mapped, but the C++ damage cadence still uses
  the reconstructed cooldown model.
- Exact post-game presentation details beyond the recovered strings and record
  prompt order: cursor drawing, key wait timing, and completed-game flag side
  effects.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`;
  current gameplay carries the mapped records but still renders simplified
  effects.
- `GRAN.MST` field semantics.

## Next Planned Target

Advance from the recovered hurt/death cue mapping into the original damage
accumulation path: map the `1000:6053` actor overlap increments at
`1000:63f0`/`1000:6491`, the `DS:79e8`/`DS:79e9` clear cadence, and the
death/reentry state fields written by `1000:30a3`, then tighten C++ damage
cooldown behavior only where the evidence supports it.
