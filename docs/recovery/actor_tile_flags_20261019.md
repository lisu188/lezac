# Original Actor Tile Classification

This bounded recovery continues the non-boss handoff from `1000:65A2`.
`ActorTileFlagsOperation` executes the original comparisons, byte stores and
branches through three explicit, unexecuted continuations:

- `65A8`: behavior-5 expiry work.
- `6737`: behavior-0 motion work.
- `7018`: nonzero-behavior work.

It does not execute those continuations or replace the production App actor
update. The common tail at `73E5` remains a separate recovered operation.

## Recovered Rules

The original checks the cached behavior first. Behavior 5 leaves before any
tile classification. Kind 13 uses individual cells `2055`, `2050`, `2052`,
and `204D`; other kinds use the pairs `2055/2056`, `204C/2050`, `204F/2053`,
and `2049/204A`. The first group accepts unsigned tile bytes 1 through 82,
inclusive; the other groups accept 1 through 76, inclusive. Results overwrite
four bytes at `SS:BP-33`, `-35`, `-36`, and `-34` in original order.

For behavior 0, the additional `BP-37` and `BP-38` bytes distinguish a
classified side whose first sampled cell is outside the 1..76 interval.
Nonzero behaviors leave before those two stores. `AL` changes without clearing
`AH`. The class preserves every original instruction boundary, 16-bit stack
offset wrapping, arithmetic flags, and the live caller-owned memory bus.
Timer delivery borrows only the already recovered IRQ machinery.

## Original Evidence

Two independent Unicorn 2.1.4 executions produced identical manifests and
gzip projections. The actually mapped library was fingerprinted before and
after execution. The original relocated code was unchanged, and observed and
unobserved execution agreed on all registers and the entire 1 MiB memory
image. Ordered observed writes reconstructed each complete final image.

- Original `LEZAC.EXE` SHA-256:
  `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
- Raw projection: 14,765,906 bytes, SHA-256
  `f788a59d4bc73dfc966d905631d5cd639e646617adaf24b8e07dd69e340cde04`.
- Published gzip: 1,298,824 bytes, SHA-256
  `c0fc0078d0ae0361ec27575042029a59bfe2b04679771ba31c265e394b7e37cb`.
- Frozen manifest SHA-256:
  `624263f35cc27ad540e6708a7e7abf57974ec62685cca5d25313f07451d4ca6d`.

There are 5,972 controlled cases: 5,120 cached-cell byte sweeps, 256 paired-cell
combinations, 16 kind-13 combinations, 256 kind bytes, 256 behavior bytes,
28 stack-wrap/flags profiles, and 40 continuous original actor-entry cases.
The latter start at `6053`, run the real prologue/contact/cache path and reach
this classifier without later memory or register injection. The C++ replay
harness composes the existing frame-contact operation with the new operation
on the same memory bus; this composition is test-only.

All 109 new instruction addresses execute. The complete corpus records
234,998 register states and 37,574 ordered writes. Its three outcome counts
are 9 expiry handoffs, 5,693 motion handoffs, and 270 behavior handoffs.
Initial state is controlled, not captured natural gameplay. No calls were
stubbed, instructions patched, hardware I/O performed, or IRQs injected into
the original captures. The compact projection is published; full RAM images
and screenshots are not.

## Validation

Strict GCC C++23 and native MSVC `/W4 /WX /O2` pass 53,748 replays apiece:
three instruction grants crossed with three string-copy grants. Each matrix
performs 807,228 register/control comparisons and 2,061,234 logical dispatches,
and compares every ordered write and the entire final memory image. All flags
are compared at every new classifier boundary; only the inherited prefix
retains its documented arithmetic-flag exclusion. All endpoint flags compare.
ASan/UBSan also passes the complete matrix.

Twelve computed C++ IRQ targets pass immediate full-context restoration,
nested/finished rejection, BDA tick advancement, and equivalent continuation
under one-instruction and 17-instruction grants with snapshot reconstruction.
The 432 handler instructions use the established timer operation; this is
not a new original-capture IRQ proof.

Fourteen compiled fault controls detect wrong kind selection, inclusive
bounds, sampled cells, paired cells, output slots, edge predicates, behavior
dispatch, accumulator preservation, auxiliary carry, IRQ flags and accounting.
The fault runner preserves the real source and tests. Fixture checks reject
changed, missing and directory-substituted inputs, protect aliases, retain
existing evidence, and preserve failed reports. They pass on Linux and native
Windows. Native Windows Git cold checkout passes all 20 frozen families and
66 files, with 20 reproduced CRLF negative controls. The initial native build
warning was repaired by typed optional-construction arguments in the test
harness, without changing recovered instructions or original inputs.

These are bounded CPU, memory, fixture and toolchain results. They do not
establish production App integration, a naturally reached encounter, rendered
frame alignment, full-frame timing, or whole-game parity.
