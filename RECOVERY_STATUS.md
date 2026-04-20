# Recovery Status

Last reviewed: 2026-04-20
Branch: `codex/autonomous-recovery-iteration`
Baseline: `3c127fc` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly, gameplay, rendering
  and audio, verification, and integration/docs.
- Recovered the `1000:1b14..1d42` post-game dispatcher into the C++ state
  machine: game-over and completed-game terminal pages, final-level completion
  routing, and per-player record prompting.
- Added separate player 2 scoring for objective collection, bonus collection,
  and bomb-object points through bomb ownership.
- Added a pending record candidate queue that checks player 1 first, then
  re-checks player 2 against the updated high-score table before prompting.
- Added `--debug-end-flow-records` and CTest `end_flow_records_temp` covering
  mid-level completion, one-player records, non-qualifying game over,
  player-2-only records, double qualifiers, and final-level completion.
- Aligned sprite contact-sheet export with runtime blitting by drawing
  palette index `0xff`; only index `0` is transparent.
- Updated README, Ghidra notes, and subagent notes with addresses, mapped C++
  functions, validation, and remaining unknowns.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed with a transient clock-skew warning from the
  OneDrive-backed filesystem.
- `ctest --test-dir build --output-on-failure` passed: 19/19.
- `./build/lezac_cpp --validate` passed.
- Focused checks passed after implementation:
  - `./build/lezac_cpp --debug-end-flow-records build/end_flow_manual.dat`
  - `./build/lezac_cpp --debug-sprite-transparency`
  - `./build/lezac_cpp --debug-record-name-entry build/records_name_manual.dat`
  - `./build/lezac_cpp --debug-bonuses`
  - `./build/lezac_cpp --debug-bomb-fuse`
  - `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-ui 3`
  - `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-controls`
  - `git diff --check`

## Remaining Top Gaps

- Exact actor update behavior around `1000:6053..777f`, especially monster AI
  and object/terrain interactions.
- Exact `PROEFS.SON` playback semantics and sound latch/tick routine around
  `1000:1500..166a`.
- Exact post-game presentation details beyond the recovered strings and record
  prompt order: cursor drawing, key wait timing, and completed-game flag side
  effects.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`;
  current gameplay carries the mapped records but still renders simplified
  effects.
- `GRAN.MST` field semantics.

## Next Planned Target

Map the `1000:165a` sound priority latch and `PROEFS.SON` offset/selector
semantics, then route high-confidence gameplay sound requests through the
original priority model.
