# Recovery Status

Last reviewed: 2026-04-20
Branch: `codex/sound-latch-recovery`
Baseline: `f7927e1` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly, gameplay, rendering
  and audio, verification, and integration/docs.
- Mapped `PROEFS.SON` loading at `1000:0630..06aa` as 130 six-byte sound
  steps, while preserving the existing JSON chunk container.
- Added the original `1000:165a..167d` sound request priority latch with
  `DS:2074`, `DS:799f`, `DS:799e`, `DS:78c0`, and `DS:79c4` semantics.
- Routed bomb explosion sound requests through the latch using the recovered
  direct PC-speaker sweep cursors `0xea74`, `0xea7e`, `0xea88`, and `0xeace`.
- Added direct-sweep synthesis for the `DS:78c0 > 0xea60` tick-routine branch.
- Added `--debug-son-raw-roundtrip`, `--debug-sound-priority-latch`, and
  `--debug-sound-selector-map`, with CTest coverage.
- Updated README, Ghidra notes, and subagent notes with sound evidence,
  implementation mapping, validation, and remaining unknowns.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `ctest --test-dir build --output-on-failure` passed: 22/22.
- `./build/lezac_cpp --validate` passed.
- Focused checks passed after implementation:
  - `./build/lezac_cpp --debug-son-raw-roundtrip`
  - `./build/lezac_cpp --debug-sound-priority-latch`
  - `./build/lezac_cpp --debug-sound-selector-map`
  - `./build/lezac_cpp --debug-explosions`
  - `./build/lezac_cpp --debug-sound-render`
  - `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-ui 3`
  - `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-controls`
  - `git diff --check`

## Remaining Top Gaps

- Exact actor update behavior around `1000:6053..777f`, especially monster AI
  and object/terrain interactions.
- Exact non-explosion `PROEFS.SON` step playback semantics around
  `1000:0fbe..1088`: six-byte gate/period fields, stop handling, and mapping
  of all non-explosion callsites to `DS:2074`/`DS:799f`.
- Exact post-game presentation details beyond the recovered strings and record
  prompt order: cursor drawing, key wait timing, and completed-game flag side
  effects.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`;
  current gameplay carries the mapped records but still renders simplified
  effects.
- `GRAN.MST` field semantics.

## Next Planned Target

Map the remaining direct callsites to `1000:165a`, replace provisional
non-explosion `playSound(index)` calls with evidence-backed cursor/priority
requests, and then refine the `PROEFS.SON` six-byte step renderer.
