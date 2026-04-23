# Recovery Status

Last reviewed: 2026-04-23
Branch: `codex/level1-passable-objects`
Baseline: `4493397` / `origin/main`

## Completed This Iteration

- Fixed level 1 passable-object collision by making `solidPixel` use a
  cell-aware helper instead of a tile-id-only helper.
- Kept portal tile `0x45` and bomb-object tiles `0x67..0x72` passable, and
  added low word-layer physical-object cells (`word != 0`, undamaged,
  `word < 0x4000`) as passable object cells.
- Preserved high word-layer floor/link markers as solid unless their tile id is
  already a known passable object.
- Extended `--debug-passable-objects` and CTest coverage to assert the real
  level 1 object column at `(17,22)` is passable, the high-word floor marker
  `(53,23)` remains solid, and holding right from the level 1 start advances
  through the formerly blocked route.
- Documented the implemented model and remaining original-evidence gap in
  `docs/GHIDRA_NOTES.md` and
  `docs/recovery/level1_passable_objects_2026-04-23.md`.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `ctest --test-dir build --output-on-failure` passed: 55/55.
- `./build/lezac_cpp --validate` passed.
- `./build/lezac_cpp --debug-passable-objects` passed with
  `level1_word_clear=1`, `high_word_solid=1`, and `level1_route_clear=1`.
- Direct live `./build/lezac_cpp --smoke-controls` was attempted and hung in
  this SDL/audio environment after `pa_write() failed...`; the process was
  killed and the dummy-SDL equivalent was run instead.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --smoke-controls` passed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-level1-frame-inspection` passed and confirmed level 1 gameplay,
  bomb placement with `N`, explosion visibility, and level advancement.
- `git diff --check` passed.

## Remaining Top Gaps

- Confirm the low-word passable-object cell rule against original
  `LEZAC.EXE`, ideally by DOSBox frame inspection or debugger/runtime collision
  evidence around `1000:6053..777f`.
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

Use DOSBox/frame inspection on the original level 1 start route to confirm the
low-word object passability rule, then continue with paired original/C++
checkpoint comparison around bomb-object explosion and collapse/debris playback.
