# Recovery Status

Last reviewed: 2026-04-22
Branch: `codex/collision-clearance-coverage`
Baseline: `ee67978` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly mapping, gameplay
  fidelity, rendering/UI impact, verification, and integration/docs.
- Created a fresh branch from `origin/main` so this slice is independent of open
  draft PRs #23-#32.
- Hardened `--debug-passable-objects` so it now checks decoded portal,
  bomb-object, and solid examples, then verifies full player/monster footprints
  across passable object tiles and the consumed bomb-object path.
- Hardened `--debug-collision-pushout` so it now forces deterministic horizontal
  and vertical collisions against a synthetic solid tile, then asserts player
  and monster footprints finish clear.
- Added behavior-4 collision coverage for half-speed reversal and retarget timer
  reset, alongside behavior-3 full horizontal reversal and vertical stop.
- Added exact CTest output contracts for `passable_objects` and
  `collision_pushout`.
- Updated README, Ghidra notes, and a dated subagent recovery note to document
  the current C++ collision/passability model and its unresolved original gaps.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed with the known WSL/OneDrive clock-skew warning.
- `./build/lezac_cpp --debug-passable-objects` passed.
- `./build/lezac_cpp --debug-collision-pushout` passed.
- `ctest --test-dir build --output-on-failure -R "^(collision_pushout|passable_objects)$"` passed: 2/2.
- `ctest --test-dir build --output-on-failure` passed: 36/36.
- `./build/lezac_cpp --validate` passed.
- `git diff --check` passed.

## Open Draft PRs / Integration Queue

- #23 `codex/state2-runtime-frame-oracle-hardening`: state-2 oracle hardening.
- #24 `codex/state2-runtime-frame-oracle-original-fixture`: original state-2
  runtime fixture.
- #25 `codex/proefs-son-field-diagnostics`: sound step field diagnostics.
- #26 `codex/explosion-debug-coverage`: explosion metadata/debug coverage.
- #27 `codex/dosbox-explosion-capture`: explosion playback oracle harness and
  DOSBox capture attempt notes.
- #28 `codex/passable-bomb-controls`: original player damage counters and
  level-1 frame inspection.
- #29 `codex/gran-parser-coverage`: GRAN raw/json roundtrip and spawner summary
  fixture.
- #30 `codex/monster-motion-coverage`: monster motion model fixture and
  immediate source-spawner slot return.
- #31 `codex/sprite-raw-roundtrip`: raw `.SPR` to JSON sprite-bank guard.
- #32 `codex/sprite-blit-contract`: sprite blit zero-transparency contract.

This branch intentionally avoids state-2, sound, explosion playback, GRAN, raw
sprite roundtrip, and record/menu surfaces, but it may conflict mechanically
with #26, #28, and #30 in shared collision/object docs and `src/main.cpp`.

## Remaining Top Gaps

- Exact actor update behavior around `1000:6053..777f`, especially original
  collision contact flags, passability thresholds, tile snapping, behavior-3
  ledge/wall handling, and behavior-4 collision response.
- The probable contact scanner around `1000:5cb0..604f` needs naming,
  cross-reference mapping, and runtime confirmation before the C++ clearance
  model can be called original-faithful.
- Exact non-explosion `PROEFS.SON` semantics for bytes `+4..+5` in each
  six-byte step, plus mapping of remaining sound callsites to events.
- Exact original continuous-contact damage cadence unless PR #28 lands, plus
  delayed state-2 life-count decrement, `DS:79b9` fallback behavior, and
  active-player accounting edge cases.
- Exact two-player panel artwork and full death/reentry presentation.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`.
- Exact sprite frame tables for impact/death/reward frames remain unresolved.

## Next Planned Target

Map and name the likely original contact scanner at `1000:5cb0..604f`, then add
a debug model that records its tile-footprint inputs, contact flags, and
velocity-response decisions separately from the current C++ pushout guard.
