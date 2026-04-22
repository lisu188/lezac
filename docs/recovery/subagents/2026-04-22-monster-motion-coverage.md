# 2026-04-22 Monster Motion Coverage Workstreams

## Subagent A - Ghidra/disassembly mapper

- Confirmed this slice stayed within the actor update anchors: animation/motion
  dispatch around `1000:6053`, behavior `3`/`4` branches around
  `1000:70bc..7148` and `1000:728c..731b`, and 8.8 integration around
  `1000:73e5..741b`.
- Identified an address-backed monster lifecycle correction at
  `1000:74a6..7513`: the fatal damage branch sets death state `2`, kind
  `0x0c`, timer `0x19`, and returns the source spawner live slot immediately
  around `1000:74e6..74f9`.

## Subagent B - Gameplay fidelity

- Recommended a deterministic `--debug-monster-motion-model` command as the
  smallest non-overlapping gameplay target.
- The command now exercises positive 8.8 carry, negative fractional movement,
  behavior-3 ground-walker initialization, ledge turning with kind-1 directional
  frames, and behavior-4 chase retarget countdown.

## Subagent C - Rendering/audio/assets

- Recommended a separate future sprite raw-roundtrip and exact transparency
  fixture. That was not integrated in this slice to keep the PR focused on
  actor motion and avoid widening the shared-file conflict surface.

## Subagent D - Verification

- Recommended adding CTest coverage for the existing `--debug-fixed` command
  because it already covers the signed 8.8 helper used by active monsters.
- This slice adds `fixed_point_integration` alongside the new
  `monster_motion_model` CTest.

## Subagent E - Integration/docs/refactor

- Confirmed this branch starts from `origin/main` at PR #22 and that open draft
  PRs #23-#29 share conflict-prone files.
- Recommended avoiding the state-2, sound, explosion, damage, GRAN, and AGENTS
  lanes in this branch.

## Integrated Decision

This slice does not claim exact original monster AI. It adds deterministic
coverage for the current reconstruction model so the next address-backed actor
update pass can replace behavior pieces while preserving known 8.8 arithmetic,
frame-direction selection, and timer semantics. It also corrects source-spawner
live-slot accounting to return the slot at monster death entry, while retaining
the later death-timer removal as visual/lifecycle cleanup only. A separate
`hasSpawner` flag mirrors the original `actor+0x25 > 0` guard so synthetic or
unowned actors do not credit level spawner state.
