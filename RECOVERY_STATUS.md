# Recovery Status

Last reviewed: 2026-04-21
Branch: `codex/state2-animation-model`
Baseline: `702d1d4` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly mapping, gameplay
  fidelity, rendering/assets, verification, and integration/docs.
- Mapped `1000:06ab` / file `0x0e1b` as the seven-byte animation initializer
  used by `actor + 0x16`.
- Mapped the player death/life-loss animation setup at
  `1000:3108..311d`: it targets `actor + 0x16`, uses `DS:006c` and
  `DS:006d` as the frame range, passes delay `3`, mode `1`, and leaves the
  actor in state `+0x15 = 2` with countdown `+0x10 = 0x003c`.
- Mapped the actor update consumer around `1000:6053..6156`: it advances the
  `actor + 0x16` cursor and resolves the current frame through the sprite/effect
  metadata tables before writing the visual/effect entry.
- Mapped state-2 return placement math for `DS:c21e + 8 * actor[+0x01]`:
  `x_tile = word0 >> 3`, `y_tile = ((word2 + 7) >> 3) + 1`, tiles `0x01` and
  `0x4c` block placement, the right tile is checked too, and unblocked entries
  decrement word `+2` while it is greater than `0x18` before the action gate is
  evaluated.
- Added `--debug-original-state2-animation-init` with CTest coverage for the
  exact initializer byte order: current/start/end/counter/delay/mode/step.
- Added `--debug-original-state2-effect-placement` with CTest coverage for
  effect-entry slot addresses, tile math, solid/marker/right-tile blocking,
  floor stopping, and descent-before-gate ordering.
- Updated README, Ghidra notes, and subagent recovery notes with addresses,
  evidence, mapped C++ debug commands, and the remaining runtime-frame
  uncertainty.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed. The build emitted a filesystem clock-skew
  warning, but completed successfully.
- `ctest --test-dir build --output-on-failure -R "state2_animation_init_model|state2_effect_placement_model|original_state2_return_model|player_state2_return_active"` passed: 4/4.
- `ctest --test-dir build --output-on-failure` passed: 33/33.
- `./build/lezac_cpp --validate` passed.
- `./build/lezac_cpp --debug-original-state2-animation-init` passed.
- `./build/lezac_cpp --debug-original-state2-effect-placement` passed.
- `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-ui 3` passed.
- `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-controls` passed.
- `git diff --check` passed.

## Remaining Top Gaps

- Exact runtime values of `DS:006a`, `DS:006c`, `DS:006d`, and the
  `DS:c324` frame metadata table during death/reentry. These are needed before
  dead-player rendering can claim original art fidelity.
- Exact actor update behavior around `1000:6053..777f`, especially monster AI,
  object/terrain interactions, and mode-specific animation side effects.
- Exact non-explosion `PROEFS.SON` semantics for bytes `+4..+5` in each
  six-byte step, plus mapping of remaining sound callsites to events.
- Exact original continuous-contact damage cadence, delayed state-2 life-count
  decrement, `DS:79b9` fallback behavior, and active-player accounting edge
  cases.
- Exact two-player panel artwork and full death/reentry presentation.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`.
- `GRAN.MST` field semantics.

## Next Planned Target

Use `dosbox-debug` as an oracle for the state-2 visual path: break after asset
setup and at the death helper/animation consumer, then dump `DS:0060`,
`DS:c21e`, and `DS:c324` during death/reentry. Use those runtime values to
replace the current skipped-dead-player rendering with the recovered original
animation range.
