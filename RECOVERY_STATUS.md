# Recovery Status

Last reviewed: 2026-04-20
Branch: `codex/autonomous-recovery-iteration`
Baseline: `d083d74` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly, gameplay, rendering
  and audio, verification, and integration/docs.
- Added `--debug-level-raw-roundtrip`, which parses original `LIVELS.SCH`
  directly and compares it against the converted JSON level resource.
- Switched destruction progress to the original low word-layer physical-damage
  denominator (`fieldB`) instead of visible tile-id counts.
- Changed trigger rewrite accounting so triggers open/replace tiles without
  advancing physical destruction progress.
- Changed sprite rendering to treat only palette index `0` as transparent;
  index `0xff` is now visible, matching the transparent blit note at
  `18ac:00f4`.
- Tightened high-score name entry toward `1000:1845..1ad4`: letters and space
  only, lowercase storage, Backspace deletion, Enter commit, and ignored
  digits/Delete.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `ctest --test-dir build --output-on-failure` passed: 18/18.
- `./build/lezac_cpp --validate` passed.
- Focused checks passed after implementation:
  - `./build/lezac_cpp --debug-level-raw-roundtrip`
  - `./build/lezac_cpp --debug-levels`
  - `./build/lezac_cpp --debug-trigger-accounting`
  - `./build/lezac_cpp --debug-sprite-transparency`
  - `./build/lezac_cpp --debug-record-name-entry build/records_name_manual.dat`
  - `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-controls`

## Remaining Top Gaps

- Exact actor update behavior around `1000:6053..777f`, especially monster AI
  and object/terrain interactions.
- Exact game-over/completed-game flow around `1000:1b14..1d42`, including
  separate two-player record prompts and ending presentation.
- Exact `PROEFS.SON` playback semantics and sound latch/tick routine around
  `1000:1500..166a`.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`;
  current gameplay carries the mapped records but still renders simplified
  effects.
- `GRAN.MST` field semantics.

## Next Planned Target

Use the recovered `1000:1b14..1d42` and `1000:1845..1ad4` evidence to finish
game-over/completed-game presentation and two-player high-score prompting, then
add deterministic record-flow tests.
