# 2026-04-22 GRAN And Spawner Fixture Workstreams

## Subagent A - Ghidra/disassembly mapper

- Recommended avoiding open state-2, sound-field, explosion, and damage-counter
  PR surfaces for this slice.
- Identified actor update and shipped spawner behavior counts as the next broad
  recovery area, with behavior `3` and `4` as the bounded target set.

## Subagent B - Gameplay fidelity

- Recommended monster behavior `3`/`4` AI and collision as the next high-impact
  gameplay target after current open PRs settle.
- Confirmed the existing `--debug-spawners` output provides a useful fixture for
  that work: 15 enabled spawners, kind counts `1:7,2:2,3:3,4:3`, and behavior
  counts `3:9,4:6`.

## Subagent C - Rendering/audio/assets

- Recommended a `GRAN.MST` raw/json validation gate because the exporter already
  treats the file as exactly `7 * 57` bytes while runtime loading did not
  enforce the same shape.
- Suggested keeping this non-semantic: preserve bytes and record shape without
  claiming field meanings.

## Subagent D - Verification

- Recommended CTest coverage for `--debug-spawners` using the shipped summary
  tail as the PASS regex.
- The GRAN roundtrip was added as a second deterministic asset-shape check.

## Subagent E - Integration/docs/refactor

- Confirmed this branch starts from `origin/main` and should avoid stacking on
  open PRs #23-#28.
- Recommended documenting the overlap queue in `RECOVERY_STATUS.md` and keeping
  this slice away from the conflict-heavy state-2/explosion/sound work.

## Integrated Decision

This slice locks two data fixtures needed for continued recovery:

- `GRAN.MST` remains semantically opaque, but its 399 raw bytes are now checked
  against the converted JSON on every test run.
- The shipped monster spawner summary is now a CTest fixture for the upcoming
  actor-update and behavior `3`/`4` recovery work.
