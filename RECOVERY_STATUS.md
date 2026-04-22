# Recovery Status

Last reviewed: 2026-04-21
Branch: `codex/state2-runtime-frame-oracle-hardening`
Baseline: `ee67978` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for debugger/disassembly mapping,
  gameplay fidelity, rendering/assets, verification, and integration/docs.
- Confirmed PR #22 had merged into `origin/main`, then moved the follow-up work
  to a new branch from the updated main baseline.
- Tried a PTY `dosbox-debug` run from a temporary copy of the original game.
  The reliable launch shape is `env TERM=xterm-256color xvfb-run -a
  dosbox-debug ... -c "DEBUG LEZAC.EXE"`; it exposes the debugger `->` prompt,
  accepts `BP`/`D`/`MEMDUMP` commands by carriage return, and runs with the
  xterm F5 sequence `\x1b[15~`.
- Hardened `--debug-state2-runtime-frame-oracle` so successful synthetic
  fixtures report every captured frame-table row in deterministic raw-byte
  form: `frame@address:b0,b1,b2,b3`.
- Added negative oracle fixtures for malformed breakpoint translation, missing
  global bytes, and missing frame-table rows, alongside the existing malformed
  segment fixture.
- Updated README and Ghidra notes to describe the row reporting while keeping
  `visual_claim=0` and blocking live dead-player rendering on real
  `dosbox-debug` bytes.
- Updated `AGENTS.md` with the reliable local `dosbox-debug` launch shape:
  `TERM=xterm-256color`, `xvfb-run`, `DEBUG LEZAC.EXE`, carriage-return PTY
  commands, `MEMDUMP`, and the xterm F5 continue sequence.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed. `make` reported local clock-skew warnings, but
  compilation and linking completed successfully.
- `ctest --test-dir build --output-on-failure -R "state2_runtime_frame_oracle|state2_animation_advance_model|state2_effect_placement_model"` passed: 7/7.
- `ctest --test-dir build --output-on-failure` passed: 39/39.
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
- Exact original state-2 life decrement timing, active-player accounting, and
  `DS:79b9` fallback behavior remain modeled but not live.
- Exact actor update behavior around `1000:6053..777f`, especially monster AI,
  object/terrain interactions, and mode-specific animation side effects.
- Exact non-explosion `PROEFS.SON` semantics for bytes `+4..+5` in each
  six-byte step, plus mapping of remaining sound callsites to events.
- Exact two-player panel artwork and full death/reentry presentation.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`.
- `GRAN.MST` field semantics.

## Next Planned Target

Drive `dosbox-debug` from a temp copy with `TERM=xterm-256color` and
`DEBUG LEZAC.EXE`. Record runtime `CS`/`DS`, set breakpoints with `BP CS:3108`,
`BP CS:6148`, `BP CS:7c89`, and `BP CS:7ddf`, run with F5 (`\x1b[15~`), then
save `MEMDUMP DS:0060 80`, `MEMDUMP DS:C21E 80`, and the needed frame-table
dump into `tests/fixtures/dosbox/state2_runtime_frame_oracle_original.txt`.
