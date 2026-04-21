# Recovery Status

Last reviewed: 2026-04-21
Branch: `codex/proefs-son-field-diagnostics`
Baseline: `ee67978` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly mapping,
  gameplay/audio fidelity, rendering/assets, verification, and integration/docs.
- Created a new branch from updated `origin/main`. PR #23 and PR #24 remain
  separate open draft PRs and are not dependencies of this sound diagnostic
  branch.
- Ran baseline build, full CTest, and asset validation before editing.
- Kept `tools/export_resources_to_json.py` and `src/PROEFS.SON.json`
  byte-preserving; no schema change was made.
- Added `--debug-son-step-fields`, a debug-only field view over the recovered
  130 six-byte `PROEFS.SON` steps. It reports `step_index`, `period_word`,
  `gate_tick`, `period_ticks`, `unknown4`, and `unknown5`.
- Added CTest coverage for the new diagnostic. The test locks the first period
  word `0x00f7`, the first stop cursor `0x0005`, the final stop cursor
  `0x0082`, and 118 steps with a nonzero unknown byte pair.
- Updated README and Ghidra notes to document the field names while keeping
  bytes `+4..+5` explicitly uninterpreted.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed. `make` reported local clock-skew warnings on
  the pre-edit baseline build, but compilation/linking completed successfully.
- Baseline `ctest --test-dir build --output-on-failure` passed: 36/36 before
  editing.
- `./build/lezac_cpp --validate` passed.
- `ctest --test-dir build --output-on-failure -R "son_raw_roundtrip|son_step_fields|sound_cursor_segments|sound_render"` passed: 4/4.
- `ctest --test-dir build --output-on-failure` passed: 37/37.
- `./build/lezac_cpp --validate` passed after editing.
- `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-ui 3` passed.
- `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-controls` passed.
- `git diff --check` passed.

## Remaining Top Gaps

- Semantic meaning of `PROEFS.SON` bytes `+4..+5` remains unknown; the new
  diagnostic preserves them as raw fields only.
- Many non-explosion sound callsites still need exact cursor/priority mapping.
- Interpret captured state-2 frame-table bytes from PR #24 and confirm the
  visual consumption path before wiring live dead-player rendering.
- Exact actor update behavior around `1000:6053..777f`, especially monster AI,
  object/terrain interactions, and mode-specific animation side effects.
- Exact original continuous-contact damage cadence, delayed state-2 life-count
  decrement, `DS:79b9` fallback behavior, and active-player accounting edge
  cases.
- Exact two-player panel artwork and full death/reentry presentation.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`.
- `GRAN.MST` field semantics.

## Next Planned Target

Use the field diagnostics to map the next non-explosion sound callsite with
direct disassembly evidence. Keep bytes `+4..+5` as raw unknowns until a routine
is found that reads or transforms them.
