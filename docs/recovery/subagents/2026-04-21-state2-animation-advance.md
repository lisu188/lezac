# State-2 Animation Advance Recovery

Date: 2026-04-21

## Subagent A - Disassembly Mapper

- Confirmed the next proof target remains the runtime frame globals and table:
  `DS:006a`, `DS:006c`, `DS:006d`, and `DS:c324`.
- `dosbox-debug` is available at `/usr/bin/dosbox-debug`, so the next visual
  fidelity pass should use debugger dumps instead of static asset inference.

## Subagent B - Gameplay Fidelity

- Recommended against live dead-player rendering in this slice because the
  current evidence does not prove sprite ids or `DS:c324` table contents.
- Recommended a debug-only model for the `1000:6053` animation cursor consumer.

## Subagent C - Rendering/Audio/Assets

- Confirmed the renderer still skips dead players and `drawPlayer()` only knows
  normal walking/jump frame ranges.
- Identified plausible asset-shape candidates in frames `57..60` and `68..78`,
  but kept them as hypotheses until `dosbox-debug` captures the runtime table.

## Subagent D - Verification

- Recommended `--debug-original-state2-animation-advance` with CTest coverage
  beside the existing state-2 initializer and placement probes.
- Kept future `DS:006a`/`DS:006c`/`DS:006d` and `DS:c324` tests blocked on
  exact DOSBox debugger bytes so the tests do not pass on wildcards.

## Subagent E - Integration/Docs

- Continued on `codex/state2-animation-model` while draft PR #21 is open.
- Kept the slice narrow: no live rendering change, no life-count timing change,
  and no guessed frame-table fixture.

## Integrated Decision

The C++ port now has a deterministic `1000:6053` animation-advance model that
locks counter/delay behavior, normal wrapping, ping-pong step flipping, mode-3
secondary cursor copy, and disabled mode. Live state-2 visuals remain unchanged
until the runtime frame table is captured from the original executable.
