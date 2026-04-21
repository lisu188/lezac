# State-2 Runtime Frame Oracle

Date: 2026-04-21

## Subagent A - Debugger/Disassembly Mapper

- Confirmed `dosbox-debug` is installed and can start the original game from a
  temp copy, but noninteractive capture did not reach a debugger prompt.
- Reconfirmed the key breakpoints: `1000:3108`, `1000:6148`, `1000:7c89`, and
  `1000:7ddf`.

## Subagent B - Gameplay Fidelity

- Recommended no live gameplay or rendering change before runtime frame bytes
  are captured.
- Recommended a debug-only parser for DOSBox dump text as the safest next C++
  slice.

## Subagent C - Rendering/Assets

- Confirmed the existing sprite loaders expose dimensions and pixels, but a
  dump must prove `DS:c322..c324` table bytes before any art mapping is trusted.
- Recommended strict output that reports captured globals/table rows and makes
  `visual_claim=0` explicit.

## Subagent D - Verification

- Recommended a synthetic fixture for parser mechanics and a malformed fixture
  for segment mismatch rejection.
- Kept the future original fixture blocked on real DOSBox debugger bytes.

## Subagent E - Integration/Docs

- Confirmed PR #21 had merged, so this work started on a new branch from
  updated `origin/main`.
- Recommended documenting the exact next capture path rather than changing live
  rendering.

## Integrated Decision

The C++ port now has a deterministic runtime-frame oracle command for saved
DOSBox debugger transcripts. The checked-in fixture is synthetic, so it proves
the parser and address math only. Live state-2 rendering remains unchanged
until an original DOSBox capture is checked in and validated.
