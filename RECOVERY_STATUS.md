# Recovery Status

Last reviewed: 2026-04-22
Branch: `codex/gran-parser-coverage`
Baseline: `ee67978` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly mapping, gameplay
  fidelity, rendering/audio/assets, verification, and integration/docs.
- Confirmed this branch starts from the current `origin/main` baseline while
  open draft PRs #23-#28 remain unmerged.
- Tightened `GRAN.MST` JSON loading so runtime parsing now enforces the
  non-semantic shipped shape: record size `57`, exactly seven records, and each
  record decoding to 57 bytes.
- Added `--debug-gran-raw-roundtrip`, which verifies raw `GRAN.MST` is exactly
  399 bytes and that the converted JSON payload matches the raw file byte for
  byte.
- Added CTest coverage for the GRAN raw/json roundtrip.
- Added CTest coverage for the existing spawner summary dump, pinning the
  shipped actor-recovery fixture: 15 enabled spawners, monster-kind counts
  `1:7,2:2,3:3,4:3`, and behavior counts `3:9,4:6`.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed with a filesystem clock-skew warning from the
  WSL/OneDrive checkout; the target still completed successfully.
- `ctest --test-dir build --output-on-failure -R "gran_raw_roundtrip|spawners_summary"` passed: 2/2.
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

These drafts overlap mostly in README, Ghidra notes, CMake, `src/main.cpp`, and
this status file. This branch intentionally avoids the state-2, PROEFS, damage,
and explosion surfaces.

## Remaining Top Gaps

- Exact actor update behavior around `1000:6053..777f`, especially monster AI,
  object/terrain interactions, and mode-specific animation side effects.
- Exact non-explosion `PROEFS.SON` semantics for bytes `+4..+5` in each
  six-byte step, plus mapping of remaining sound callsites to events.
- Exact original continuous-contact damage cadence unless PR #28 lands, plus
  delayed state-2 life-count decrement, `DS:79b9` fallback behavior, and
  active-player accounting edge cases.
- Exact two-player panel artwork and full death/reentry presentation.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`.
- `GRAN.MST` field semantics remain unknown; this branch only locks file shape
  and raw/json byte preservation.

## Next Planned Target

Continue actor-update recovery with a behavior-3/behavior-4 monster motion
model around `1000:70bc..7148`, `1000:728c..731b`, and the already modeled
8.8 integration at `1000:73e5..741b`. The existing `spawners_summary` fixture
now pins the shipped monster kinds and behavior counts for that work.
