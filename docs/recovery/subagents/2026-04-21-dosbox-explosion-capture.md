# 2026-04-21 DOSBox Explosion Capture Workstreams

## Subagent A - Ghidra/disassembly mapper

- Recommended breakpoints for `1000:75f1`, `1000:414a`, `1000:370e`, and the
  playback helper window `1000:3a56..4d3b`.
- Identified the most useful dumps as sound globals, debris records at
  `DS:2093`, collapse records at `DS:6611`, lookup bytes at `DS:c1e0`, and
  effect entries at `DS:c21e`.

## Subagent B - Gameplay fidelity

- Identified the immediate level-1 bomb-object collapse route: bomb tile
  `(24,22)`, object tile `0x67`, target above `(24,21)`, word `0x0009`,
  expected flagged word `0x8009`, and a two-cell collapse group.
- Identified a later level-4 route that can exercise collapse and debris from
  one footprint once there is a reliable way to enter level 4 in the original.

## Subagent C - Rendering/assets

- Recommended keeping fixture assertions limited to raw metadata and memory
  bytes until a breakpoint proves the exact downstream sprite/table selector.
- Proposed preserving raw 8-byte effect entries and queue records rather than
  claiming sprite names or frame timing.

## Subagent D - Verification

- Recommended a `--debug-explosion-playback-oracle <fixture> [--expect-error]`
  parser modeled after the state-2 runtime oracle.
- Recommended synthetic and malformed-segment fixtures first, with a later
  `explosion_playback_oracle_original.txt` only after live bytes are captured.

## Subagent E - Integration/docs/refactor

- Flagged stale `RECOVERY_STATUS.md` content after branch creation.
- Recommended documenting failed automation as an attempted capture, not as
  original evidence, including command, environment, temp-copy status, input
  sequence, and failure reason.

## Integrated Decision

This slice captures real entry-segment evidence from `DEBUG LEZAC.EXE` and adds
the strict parser/test landing zone for a future real explosion transcript. The
automated session did not reach an explosion breakpoint because Enter was not
delivered to the debugger command line in this environment. No visual playback
claim is made.
