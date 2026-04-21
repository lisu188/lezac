# 2026-04-21 Damage Counters And Frame Inspection Workstreams

## Subagent A - Ghidra/disassembly mapper

- Recommended replacing the live cooldown-gated damage path with the recovered
  accumulated player damage counters.
- Anchors: `1000:63f0` increments `DS:79e8`, `1000:6491` increments
  `DS:79e9`, and `1000:7f68..7f8f` subtracts the accumulated byte and requests
  the hurt sound.

## Subagent B - Gameplay fidelity

- Confirmed existing bomb fuse, passable-object, collision, and control smoke
  tests pass.
- Also recommended the damage-counter slice as the highest-impact local change
  because it affects monster contact, bomb blasts, debris/collapse hazards, and
  two-player simultaneous damage.

## Subagent C - Rendering/audio/assets

- Recommended a smaller sound invariant for a later slice: mutate
  `PROEFS.SON` bytes `+4..+5` in each six-byte step and prove current synthesis
  remains unchanged.
- Flagged frame inspection for approximate debris/collapse rendering as useful
  verification hardening, but not original-art evidence.

## Subagent D - Verification

- Recommended a deterministic level-1 frame-inspection command using dummy SDL.
- Expected coverage: main menu frame, level-1 playfield frame, HUD/world/player
  visibility, `N` key bomb placement, bomb visibility, and level advancement.

## Subagent E - Integration/docs/refactor

- Flagged stale `RECOVERY_STATUS.md` content on `origin/main`.
- Recommended keeping this work on a fresh branch from `origin/main` and
  documenting overlap with open draft PRs.

## Integrated Decision

This slice implements the evidence-backed live damage counters and adds
frame-inspected level-1 UI coverage. The frame test validates current rendering
and controls; it does not claim exact original sprite or explosion art.
