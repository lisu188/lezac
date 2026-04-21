# Recovery Status

Last reviewed: 2026-04-21
Branch: `codex/state2-runtime-frame-oracle`
Baseline: `39abdc5` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for debugger/disassembly mapping,
  gameplay fidelity, rendering/assets, verification, and integration/docs.
- Confirmed PR #21 was merged into `origin/main`, then created this branch from
  the updated main baseline.
- Verified `dosbox-debug` is installed and can start its debugger UI. A direct
  `dosbox-debug -help` invocation is not a help mode; it opens the debugger and
  must be driven interactively or with a more controlled input setup.
- Added `--debug-state2-runtime-frame-oracle <dump.txt>`, a strict parser for
  normalized saved DOSBox debugger transcripts. It records runtime `CS`/`DS`,
  validates translated breakpoints, parses `D DS:0060` globals, resolves
  `DS:c322 + 4 * frame` table rows for the death/reentry frame range, and reads
  the first `DS:c21e` effect-entry position words.
- Added a synthetic oracle fixture that proves parser mechanics and address
  math without claiming original runtime frame data.
- Added a malformed segment fixture and `--expect-error` mode to keep negative
  parser coverage deterministic in CTest.
- Updated README and Ghidra notes to document the oracle and to keep live
  dead-player rendering blocked on real `dosbox-debug` bytes.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `ctest --test-dir build --output-on-failure -R "state2_runtime_frame_oracle|state2_animation_advance_model|state2_effect_placement_model"` passed: 4/4.
- `ctest --test-dir build --output-on-failure` passed: 36/36.
- `./build/lezac_cpp --validate` passed.
- `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-ui 3` passed.
- `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-controls` passed.
- `git diff --check` passed.

## Remaining Top Gaps

- Capture real runtime values of `DS:006a`, `DS:006c`, `DS:006d`, and the
  `DS:c322..c324` frame metadata table during death/reentry with
  `dosbox-debug`.
- Add an `original` oracle fixture from that capture and only then wire
  dead-player rendering to recovered original frame data.
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

Drive `dosbox-debug` manually or through a controllable PTY setup in a temp copy
of the game. Record runtime `CS`/`DS`, break at `CS:3108`, `CS:6148`,
`CS:7c89`, and `CS:7ddf`, then paste the resulting `D DS:0060`,
`D DS:C21E`, and frame-table dumps into
`tests/fixtures/dosbox/state2_runtime_frame_oracle_original.txt`.
