# Recovery Status

Last reviewed: 2026-04-22
Branch: `codex/explosion-runtime-capture`
Baseline: `14f4319` / `origin/main`

## Completed This Iteration

- Spawned five recovery workstreams for the requested explosion runtime capture
  target: disassembly mapping, gameplay route, rendering/assets evidence,
  verification harness, and integration/docs.
- Rebuilt the temp-copy `dosbox-debug` launch for original `LEZAC.EXE` and
  confirmed the program entry stop again reaches `CS=01ED`, `DS=01DD`,
  `IP=7783` at `01ED:7783 9A00000D0B call 0B0D:0000`.
- Confirmed the xterm F5 sequence (`\x1b[15~`) continues execution from the
  debugger UI into the original game.
- Retried debugger command entry through raw PTY, piped stdin, and a real Xvfb
  `zutty` terminal captured with `script`. In all paths printable command
  characters reached the `->` prompt, but Return, keypad Enter, CR, LF,
  Ctrl-J, and Ctrl-M did not execute the pending debugger command.
- Preserved the exact breakpoint/dump plan for the level-1 bomb-object collapse
  route and documented the current environment blocker. No original
  explosion/debris/collapse playback bytes were captured in this iteration, and
  no `visual_claim` was made.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `ctest --test-dir build --output-on-failure` passed: 53/53.
- `./build/lezac_cpp --validate` passed.
- `git diff --check` passed.

## Remaining Top Gaps

- Interpret captured state-2 frame-table bytes and confirm the visual
  consumption path before wiring live dead-player rendering.
- Exact explosion/debris/collapse sprite playback around `1000:3a56..4d3b`
  remains blocked on live debugger bytes from an explosion event.
- Semantic meaning of `PROEFS.SON` bytes `+4..+5` remains unknown; current
  diagnostics preserve them as raw fields only.
- Many non-explosion sound callsites still need exact cursor/priority mapping.
- Exact actor update behavior around `1000:6053..777f`, especially original
  contact flags, passability thresholds, tile snapping, behavior-3 ledge/wall
  handling, and behavior-4 collision response.
- The probable contact scanner around `1000:5cb0..604f` needs naming,
  cross-reference mapping, and runtime confirmation before the C++ clearance
  model can be called original-faithful.
- Exact state-2 life-count decrement, `DS:79b9` fallback behavior,
  active-player accounting edge cases, and live dead-player visual playback
  from original frame bytes.
- Exact two-player panel artwork and full death/reentry presentation.
- Exact sprite frame tables for impact/death/reward frames remain unresolved.
- `GRAN.MST` field semantics remain unknown; consolidation only locks file
  shape and raw/json byte preservation.

## Next Planned Target

Use a debugger control path where Enter works, or another DOSBox debugger
automation method, to set the `01ED:75F1`, `01ED:414A`, `01ED:370E`,
`01ED:3A7E`, `01ED:3B18`, `01ED:3BB2`, and `01ED:3D46` breakpoints; then run
the level-1 `(24,22)` bomb route and normalize the live dumps into
`tests/fixtures/dosbox/explosion_playback_oracle_original.txt`.
