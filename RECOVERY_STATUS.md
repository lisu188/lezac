# Recovery Status

Last reviewed: 2026-04-20
Branch: `codex/sound-latch-recovery`
Baseline: `f7927e1` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly, gameplay, rendering
  and audio, verification, and integration/docs.
- Re-disassembled `1000:0fbe..1088` and confirmed non-direct sound playback as
  six-byte cursor steps: word `+0` tone/`0x7530` stop, byte `+2` gate-off tick,
  byte `+3` next-step tick, bytes `+4..+5` still unknown.
- Flattened the preserved `PROEFS.SON` JSON chunks into a 130-step payload view
  and changed non-direct playback to render through `synthesizeSoundCursor`
  instead of the older five-byte chunk approximation.
- Kept direct-sweep explosion playback through the recovered
  `DS:78c0 > 0xea60` path and the original `1000:165a..167d` priority latch.
- Routed the bonus pickup/effect branch through recovered request cursor
  `0x0008` at priority `5`, matching the branch around `1000:6e4b..6f8d`.
- Added `--debug-sound-cursor-segments` with CTest coverage and made
  `--debug-sound-priority-latch` print the post-pump state.
- Updated README, Ghidra notes, and subagent notes with the new sound cursor
  evidence, implementation mapping, validation, and remaining unknowns.

## Validation

- Baseline before this slice:
  - `cmake -S . -B build` passed.
  - `cmake --build build` passed.
  - `ctest --test-dir build --output-on-failure` passed: 22/22.
  - `./build/lezac_cpp --validate` passed.
- Final validation after implementation and formatting:
  - `cmake -S . -B build` passed.
  - `cmake --build build` passed.
  - `ctest --test-dir build --output-on-failure` passed: 23/23.
  - `./build/lezac_cpp --validate` passed.
  - `./build/lezac_cpp --debug-sound-cursor-segments` passed.
  - `./build/lezac_cpp --debug-son-raw-roundtrip` passed.
  - `./build/lezac_cpp --debug-sound-priority-latch` passed.
  - `./build/lezac_cpp --debug-sound-selector-map` passed.
  - `./build/lezac_cpp --debug-sound-render` passed.
  - `./build/lezac_cpp --debug-bonuses` passed.
  - `./build/lezac_cpp --debug-explosions` passed.
  - `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-ui 3` passed.
  - `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-controls` passed.
  - `git diff --check` passed.

## Remaining Top Gaps

- Exact actor update behavior around `1000:6053..777f`, especially monster AI
  and object/terrain interactions.
- Exact non-explosion `PROEFS.SON` semantics for bytes `+4..+5` in each
  six-byte step, plus mapping of all remaining non-explosion callsites to
  `DS:2074`/`DS:799f`.
- Exact post-game presentation details beyond the recovered strings and record
  prompt order: cursor drawing, key wait timing, and completed-game flag side
  effects.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`;
  current gameplay carries the mapped records but still renders simplified
  effects.
- `GRAN.MST` field semantics.

## Next Planned Target

Map the remaining non-explosion direct callsites to `1000:165a`, starting with
objective pickup and portal/trigger transitions, then replace provisional
`playSound(index)` calls with evidence-backed cursor/priority requests.
