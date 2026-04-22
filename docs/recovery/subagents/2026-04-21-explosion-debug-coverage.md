# 2026-04-21 Explosion Debug Coverage Workstreams

## Subagent A - Ghidra/disassembly mapper

- Confirmed the documented `1000:370e` mapping against raw `LEZAC.EXE` bytes:
  high-word damage checks `0x8000`, uses threshold `0x4000`, writes 11-byte
  debris records at `0x2093 + 0x0b * count`, and low-word damage writes
  15-byte collapse records at `0x6611 + 0x0f * count`.
- Confirmed the repository has no checked-in `docs/recovery/exports` dump for
  the playback window yet.
- Recommended turning the existing damage queue diagnostic into a CTest gate
  before attempting live playback changes.

## Subagent B - Gameplay fidelity

- Identified the highest-risk gameplay boundary as the integrated bomb-object
  explosion path: 2x2 footprint, passable object consumption, score award,
  sound priority, and `queueTileDamage(x, y - 1)` routing were covered mostly
  by isolated tests.
- Recommended a focused debug command that explodes a bomb on real object tiles
  and asserts post-explosion passability plus collapse/debris queue effects.

## Subagent C - Rendering/assets

- Confirmed explosion dispatcher and sound metadata are recoverable today, but
  exact explosion/debris/collapse sprite frame selectors are still unresolved.
- Recommended a future `dosbox-debug` playback oracle for `1000:414a` and
  `1000:3a56..4d3b` before claiming original-accurate visual playback.

## Subagent D - Verification

- Recommended wiring deterministic CTests for `--debug-explosions` and
  `--debug-damage-queues` using targeted summary patterns rather than
  full-output matching.
- Noted that diagnostics must run with the repository as working directory
  because resource loading expects the converted asset files.

## Subagent E - Integration/docs/refactor

- Recommended documenting this as metadata/debug coverage only.
- Flagged `RECOVERY_STATUS.md` as stale on branch creation and requested an
  update before PR publication.
- Requested wording that keeps `1000:414a` and `1000:370e` evidence separate
  from unresolved sprite playback around `1000:3a56..4d3b`.

## Integrated Decision

This slice adds a real-asset gameplay regression for bomb-object explosion side
effects and CTest coverage for the recovered explosion/debris/collapse metadata.
The live renderer remains a simplified reconstruction. Exact original playback
will require a future debugger capture or disassembly export of
`1000:3a56..4d3b`.
