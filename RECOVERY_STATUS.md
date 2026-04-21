# Recovery Status

Last reviewed: 2026-04-21
Branch: `codex/explosion-debug-coverage`
Baseline: `ee67978` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly mapping, gameplay
  fidelity, rendering/assets, verification, and integration/docs.
- Created a fresh branch from `origin/main` so this slice does not stack on the
  open draft PRs for state-2 runtime fixtures or PROEFS.SON diagnostics.
- Added `--debug-bomb-object-explosion-effects`, which drives the real
  explosion path against real level tiles for one low-word collapse case and
  one high-word debris case. The probe asserts that consumed bomb-object tiles
  remain passable, award exactly one object score, keep the explosion sound
  priority latched, and route the tile above the 2x2 footprint into the expected
  queue.
- Added stable `explosion_profiles=ok` and `damage_queues=ok` summary lines to
  the existing diagnostics so CTest can lock recovered metadata without brittle
  full-output matching.
- Wired CTest coverage for explosion dispatcher/sound metadata, debris/collapse
  queue metadata, and integrated bomb-object explosion side effects.
- Updated README/Ghidra notes and recorded the subagent workstream decisions for
  this slice.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `ctest --test-dir build --output-on-failure -R "explosion_profiles|damage_queues|bomb_object_explosion_effects"` passed: 3/3.
- Full `ctest --test-dir build --output-on-failure` passed: 39/39.
- `./build/lezac_cpp --validate` passed.
- `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-ui 3` passed.
- `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-controls` passed.
- `git diff --check` passed.

## Remaining Top Gaps

- Exact explosion/debris/collapse sprite playback around `1000:3a56..4d3b`.
  This branch locks metadata and integrated passability/routing side effects
  only; it does not claim original visual frame timing.
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

Use `dosbox-debug` in a temporary copy to capture an explosion that consumes a
bomb object and damages both a low-word collapse group and a high-word debris
tile. Export the `1000:414a` and `1000:3a56..4d3b` windows, then build a narrow
oracle for the original playback slots before changing live sprite rendering.
