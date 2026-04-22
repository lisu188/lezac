# Recovery Status

Last reviewed: 2026-04-22
Branch: `codex/monster-motion-coverage`
Baseline: `ee67978` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly mapping, gameplay
  fidelity, rendering/audio/assets, verification, and integration/docs.
- Created a fresh branch from `origin/main` so this slice does not stack on open
  draft PRs #23-#29.
- Added `--debug-monster-motion-model`, a deterministic synthetic fixture for
  the current actor movement reconstruction. It locks positive 8.8 carry,
  negative fractional movement, behavior-3 ground-walker initialization,
  behavior-3 ledge turning with kind-1 directional frames, and behavior-4 chase
  retarget countdown behavior.
- Added CTest coverage for `--debug-monster-motion-model`.
- Added CTest coverage for existing `--debug-fixed` output so the shared signed
  8.8 helper used by monster movement is gated directly.
- Corrected monster source-spawner live-slot accounting to match the fatal
  damage branch around `1000:74e6..74f9`: entering death state now returns the
  source slot immediately when a source exists, while later death-timer removal
  is cleanup only.
- Tightened `monster_slots` CTest coverage to prove immediate slot return and
  no double return after death animation removal.
- Documented the fixture in `docs/GHIDRA_NOTES.md` as a regression oracle for
  the current reconstruction model, not proof of exact original AI/collision.

## Validation

- Baseline before edits:
  - `cmake -S . -B build` passed.
  - `cmake --build build` passed with the known WSL/OneDrive clock-skew warning.
  - `ctest --test-dir build --output-on-failure` passed: 36/36.
- Post-change:
  - `cmake -S . -B build` passed.
  - `cmake --build build` passed with the known WSL/OneDrive clock-skew warning.
  - `./build/lezac_cpp --debug-fixed` passed.
  - `./build/lezac_cpp --debug-monster-motion-model` passed.
  - `./build/lezac_cpp --debug-monster-slots` passed.
  - `./build/lezac_cpp --debug-monster-blast-damage` passed.
  - `ctest --test-dir build --output-on-failure -R "fixed_point_integration|monster_slots|monster_motion_model|monster_blast_damage"` passed: 4/4.
  - `ctest --test-dir build --output-on-failure` passed: 38/38.
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

This branch intentionally avoids the state-2, PROEFS, explosion, contact damage,
GRAN, and AGENTS workflow surfaces.

## Remaining Top Gaps

- Exact actor update behavior around `1000:6053..777f`, especially the original
  behavior-3 and behavior-4 AI/collision details behind the current hypotheses.
- Exact non-explosion `PROEFS.SON` semantics for bytes `+4..+5` in each
  six-byte step, plus mapping of remaining sound callsites to events.
- Exact original continuous-contact damage cadence unless PR #28 lands, plus
  delayed state-2 life-count decrement, `DS:79b9` fallback behavior, and
  active-player accounting edge cases.
- Exact two-player panel artwork and full death/reentry presentation.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`.
- `GRAN.MST` field semantics remain unknown unless PR #29 lands; even then,
  only the raw/json preservation contract is covered.

## Next Planned Target

Use the new monster-motion fixture as the guardrail for a narrower actor-update
pass: recover one original behavior-3 or behavior-4 branch from
`1000:70bc..7148` / `1000:728c..731b`, replace only the proven piece of the
current model, and add a before/after debug trace for that branch.
