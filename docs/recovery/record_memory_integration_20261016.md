# Rank-eight memory and screen-clear integration

This branch brings the two approved recovery candidates onto main
`3e10f3439858cd86bee2224002b82bcfb295a2c2`. It preserves the later end-run
integration instead of replacing it with the old candidate base.

`RecordStore` now owns the thirteen bytes written beyond the seven original
records. `ScreenClear` retains a bounded pixel cursor between calls. The
original-backed component tests and their already-published fixtures are kept.

The `record_adjacent_app` regression exercises the actual App, SDL event path,
record-name controller and DOS save codec. It covers rank eight and a rank-seven
control, retaining frames and record files in separate per-invocation folders.
It verifies the owned-memory write without treating saved-file equality or an
intact next prompt as interrupt-execution fidelity.

## Open execution gate

The finding on merged PR #388 remains only partly addressed. Owned backing
bytes do not execute the corrupted far interrupt target. `ScreenClear` is not
yet driven by an App instruction-work scheduler. Whole-frame menu drawing,
background drawing, text drawing, keyboard-controller repeat, and IRQ order
still need original-backed integration. No stopped-frame, exact timing,
complete frame-stream, audio, campaign, or whole-game parity is claimed.

Local validation is run in RAM because the Windows backing volume is above
the repository's disk reserve. No canonical source, saves or captures are
changed by these isolated checks. Full remote CI and current-head review
remain separate delivery gates.

## Current-base validation

- The full Linux Release App builds with GCC 13.3 and SDL 2.30.0.
- All 123 configured compilation commands select C++23.
- Thirty-six focused CTests pass, including the actual App regression,
  original record/render fixtures, save/retry flows, source guardrails, and
  both original-backed and live-Xvfb physical-key ownership checks.
- The three new memory/App/clear checks pass a second invocation. Hashes of
  all 77 files from their first invocation remain unchanged.
- A compiled negative control disables the instance-owned write while leaving
  the App and save path intact. The SDL/App regression rejects it with
  `SDL commit did not retain the original rank-eight write`.
- A second compiled control turns the incremental clear into an atomic full
  clear. Its regression rejects it with `prefix or suffix changed`.
- All launched games and children use dummy audio. Build, temporary files,
  and validation outputs are directed to tmpfs; no full-suite or Windows result is
  inferred from these Linux checks.
