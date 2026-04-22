# State-2 Runtime Frame Oracle Hardening

Date: 2026-04-21

## Subagent A - Debugger/Disassembly Mapper

- Treated PR #22 as merged and recommended a follow-up branch.
- Found a controllable debugger launch shape:

```sh
env TERM=xterm-256color xvfb-run -a dosbox-debug \
  -c "mount c /tmp/lezac-dosbox-capture" \
  -c "c:" \
  -c "DEBUG LEZAC.EXE"
```

- The debugger shows a usable `->` prompt when launched this way. Commands such
  as `BP CS:3108`, `BPLIST`, `D DS:0060`, and `MEMDUMP DS:0060 80` work when
  sent with carriage return. F5/run can be sent as the xterm sequence
  `\x1b[15~`.
- A real death/reentry capture still needs an input sequence that reaches the
  state-2 breakpoints and copies/renames each `MEMDUMP.TXT` before the next
  dump overwrites it.

## Subagent B - Gameplay Fidelity

- Recommended no live death/reentry rendering, life decrement timing change, or
  `DS:c21e` respawn placement change until original runtime bytes are captured.
- Identified a debug-only state/accounting model as a later safe slice if live
  DOSBox capture remains blocked.

## Subagent C - Rendering/Assets

- Recommended deterministic raw frame-table row reporting and stronger missing
  dump diagnostics for real capture analysis.
- Kept sprite-bank matching and visual claims blocked until table bytes can be
  tied to non-visual metadata.

## Subagent D - Verification

- Recommended negative fixtures for malformed breakpoint translation, missing
  global bytes, and missing frame-table rows.
- Kept the existing synthetic happy path as the only non-original fixture.

## Subagent E - Integration/Docs

- Confirmed PR #22 was merged and advised opening a new follow-up PR rather
  than extending the merged branch.
- Recommended documenting this as oracle hardening unless a real capture is
  obtained.

## Integrated Decision

The runtime-frame oracle now prints every captured frame-table row and has
negative coverage for breakpoint, segment, global-byte, and table-row failures.
The fixtures remain synthetic or malformed; no original death/reentry art is
claimed and live rendering remains unchanged.
