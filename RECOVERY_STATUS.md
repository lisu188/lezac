# Recovery Status

Last reviewed: 2026-04-22
Branch: `codex/sprite-blit-contract`
Baseline: `ee67978` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for rendering/disassembly mapping,
  rendering fidelity, asset/UI coverage, verification, and integration/docs.
- Created a fresh branch from `origin/main` so this slice does not stack on open
  draft PRs #23-#31.
- Added `--debug-sprite-blit-contract`, a synthetic renderer contract that
  draws through the actual `drawSprite()` path over a prefilled framebuffer.
- The new diagnostic proves source palette index `0` preserves the destination,
  nonzero source indices are written through the active palette, `0xff` is
  visible, and pixels outside the sprite bounds stay unchanged.
- Added CTest coverage for `sprite_blit_contract`.
- Updated README, Ghidra notes, and a dated subagent recovery note with the
  direct blitter evidence.

## Validation

- Baseline before edits:
  - `cmake -S . -B build` passed.
  - `cmake --build build` passed with the known WSL/OneDrive clock-skew warning.
  - `./build/lezac_cpp --debug-sprite-transparency` passed.
  - `ctest --test-dir build --output-on-failure` passed: 36/36.
- Post-change:
  - `cmake -S . -B build` passed.
  - `cmake --build build` passed with the known WSL/OneDrive clock-skew warning.
  - `./build/lezac_cpp --debug-sprite-blit-contract` passed.
  - `ctest --test-dir build --output-on-failure -R "^(sprite_blit_contract|sprite_transparency)$"` passed: 2/2.
  - `ctest --test-dir build --output-on-failure` passed: 37/37.
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

This branch intentionally avoids the state-2, PROEFS, explosion, contact damage,
GRAN, monster-motion, sprite-raw-roundtrip, and AGENTS workflow surfaces.

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
- Exact sprite frame tables for impact/death/reward frames remain unresolved
  even after the raw-bank and blit-contract guards.

## Next Planned Target

Use the sprite asset and blit-contract guards to recover exact sprite frame
selection tables for impact/death/reward frames, or tighten
`debugCollisionPushout()` to assert final player and monster clearance after
pushout instead of only proving loop termination.
