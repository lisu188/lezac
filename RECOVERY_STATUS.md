# Recovery Status

Last reviewed: 2026-04-22
Branch: `codex/consolidated-recovery`
Baseline: `ee67978` / `origin/main`

## Completed This Consolidation

- Consolidating open draft recovery PRs #23 through #33 into one integration
  branch before merging to `main`.
- Integrated state-2 runtime oracle hardening from #23 and the original
  temp-copy `dosbox-debug` state-2 fixture from #24.
- Integrated `PROEFS.SON` six-byte step field diagnostics from #25 while
  preserving bytes `+4..+5` as raw uninterpreted fields.
- Integrated explosion object debug coverage from #26.
- Integrated the explosion playback oracle harness and DOSBox capture attempt
  notes from #27, keeping the checked-in fixtures as parser coverage with
  `visual_claim=0`.
- Integrated original per-player damage counters and level-1 dummy-SDL frame
  inspection from #28.
- Preserved synthetic parser-hardening coverage, original `01ED:7C89` state-2
  capture, sound step diagnostics, explosion/object metadata coverage,
  explosion debugger capture instructions, live damage-counter coverage, and
  level-1 frame inspection.

## Validation

- Pending until all draft PRs are consolidated and conflicts are resolved.

## Remaining Top Gaps

- Interpret captured state-2 frame-table bytes and confirm the visual
  consumption path before wiring live dead-player rendering.
- Exact explosion/debris/collapse sprite playback around `1000:3a56..4d3b`
  remains blocked on live debugger bytes from an explosion event.
- Semantic meaning of `PROEFS.SON` bytes `+4..+5` remains unknown; current
  diagnostics preserve them as raw fields only.
- Many non-explosion sound callsites still need exact cursor/priority mapping.
- Exact actor update behavior around `1000:6053..777f`, especially monster AI,
  collision contact flags, passability thresholds, and behavior-specific
  movement response.
- Exact state-2 life-count decrement, `DS:79b9` fallback behavior,
  active-player accounting edge cases, and live dead-player visual playback
  from original frame bytes.
- Exact two-player panel artwork and full death/reentry presentation.
- Exact sprite frame tables for impact/death/reward frames remain unresolved.
- `GRAN.MST` field semantics remain only partially decoded until the GRAN
  coverage PR is integrated.

## Next Planned Target

Finish consolidating PRs #29 through #33, run full validation, close the
individual draft PRs, and merge the consolidated result into `main`.
