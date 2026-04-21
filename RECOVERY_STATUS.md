# Recovery Status

Last reviewed: 2026-04-21
Branch: `codex/dosbox-explosion-capture`
Baseline: `ee67978` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly mapping, gameplay
  route selection, rendering/assets, verification, and integration/docs.
- Created a fresh branch from `origin/main` so this work does not stack on the
  open draft PRs.
- Built a temporary original-game run directory at
  `/tmp/lezac-dosbox-explosion` and launched `dosbox-debug` from that copy.
- Confirmed `DEBUG LEZAC.EXE` stops at the original program entry and captured
  real entry register state in this environment: `CS=01ed`, `DS=01dd`,
  `IP=7783`.
- Confirmed the current automated control path is blocked: the debugger curses
  UI accepts printable characters through raw PTY/tmux, but Enter and Backspace
  are not delivered as command keys, so no automated explosion breakpoint was
  reached.
- Added `--debug-explosion-playback-oracle <fixture.txt> [--expect-error]`, a
  strict normalized transcript parser for future explosion/debris/collapse
  debugger captures.
- Added synthetic and malformed-segment fixtures plus CTest coverage for the
  parser. These fixtures prove address/dump parsing only and keep
  `visual_claim=0`.
- Added project-agent guidance to use frame inspection when testing UI,
  rendering, DOSBox, or live gameplay behavior.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed, with a filesystem clock-skew warning.
- `ctest --test-dir build --output-on-failure -R "explosion_playback_oracle"` passed: 2/2.
- `ctest --test-dir build --output-on-failure` passed: 38/38.
- `./build/lezac_cpp --validate` passed.
- `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-ui 3` passed; this smoke path inspects rendered frame pixels and rejects uniform frames.
- `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-controls` passed.
- `git diff --check` passed.

## Remaining Top Gaps

- Exact explosion/debris/collapse sprite playback around `1000:3a56..4d3b`
  remains blocked on live debugger bytes from an explosion event.
- Exact actor update behavior around `1000:6053..777f`, especially monster AI,
  object/terrain interactions, and mode-specific animation side effects.
- Exact non-explosion `PROEFS.SON` semantics for bytes `+4..+5` in each
  six-byte step, plus mapping of remaining sound callsites to events.
- Capture real runtime values of `DS:006a`, `DS:006c`, `DS:006d`, and the
  `DS:c322..c324` frame metadata table during death/reentry with
  `dosbox-debug`.
- Exact original continuous-contact damage cadence, delayed state-2 life-count
  decrement, `DS:79b9` fallback behavior, and active-player accounting edge
  cases.
- Exact two-player panel artwork and full death/reentry presentation.
- `GRAN.MST` field semantics.

## Next Planned Target

Run `dosbox-debug` in a terminal where Enter is accepted by the debugger command
line, set translated breakpoints for `1000:414a`, `1000:370e`, and the
`1000:3a56..4d3b` playback helpers, then normalize the first real explosion
capture into `tests/fixtures/dosbox/explosion_playback_oracle_original.txt`.
