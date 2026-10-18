# Boss Physical Ownership Counterexample

## Verified Failure

The diagnostic-only branch starts from integration PR #439 at
`0031cf0964d165f56d7283b5ebba6933d1a5e15a`. It adds an actual-App command,
`--debug-boss-physical-ownership`, without changing production behavior.
The command disables the legacy adapter, loads the real level-7 setup and
calls the production boss-link and monster-update helpers for eight ticks.
This is a controlled App helper test, not a natural route, whole-frame loop
test or new original-game comparison. It injects no per-tick actor state.

The isolated Linux App object was compiled with the current CMake App flags
and linked against the existing #439 objects/libraries. With original assets
and dummy SDL audio/video, the command returns 1:

```text
boss_physical_first_mismatch tick=1 order=2 typed=92,117 physical=92,118
boss_physical_ownership initial_cursor_byte_differences=35 coordinate_mismatches=46 ticks=8 legacy_adapter=0 actual_App_helpers=1 natural_route=0 original_comparison=0
fatal: boss physical visual/animation owner is stale
```

## Source Boundary

`spawnLevel7BossFromBank` allocates physical records through the generic
constructor but does not install the complete copied GRAN actor/animation
state. The original loader copies 38-byte records and rebases visual/link
indexes; generic constructor state is not an equivalent lifetime.

`updateMonsters` writes shared animation and final physical motion only for
kinds 1..8. The boss head/segments use kinds 30/31, so their typed state moves
while the physical visual rows remain stale. `WorldRaster` now reads those
rows during normal play. Existing seeded boss screenshots select the explicit
legacy visual adapter and do not test this ownership boundary.

The finding is a merge blocker on #429 and #439 even if their hosted CI and
automated reviews are green. Both PRs were returned to draft and the finding
was recorded in conversation comments. #440's unintegrated CPU prologue
recovery is separate and remains stacked on the blocked #439 dependency.

## Required Repair

Recover physical GRAN initialization, visual permutation, owner fields and
link records against original evidence. Connect shared animation, descriptor,
motion, damage and conversion writes to the live physical boss records while
preserving latched dimensions and opaque bytes. Add actual-App no-legacy
regressions and original-backed physical-state/frame checks.

Do not enable the legacy adapter in normal play or reconstruct all physical
visuals from typed vectors at render time. Keep the verified failure until a
production repair passes the same boundary and the broader boss regressions.
There is no fix, native Windows proof, natural boss victory or whole-game
parity claim in this diagnostic checkpoint.

## Original Loader Exploration

A first exploratory Unicorn run executes the unchanged original `08A5..0C32`
GRAN loader and all guest callees. An explicit host DOS-file device services
the requested open/read calls from canonical `GRAN.MST` bytes; this is not a
DOSBox kernel or natural-play capture, and guest DOS services are modeled.
No guest function is stubbed or code patched. The loader consumes all 399
file bytes, returns to the seeded caller at `1000:2E9C`, leaves actor/visual/link
counts `7/9/6`, and preserves all 43,552 original code bytes.

The exact exploratory source is retained at
`evidence/boss_physical_ownership_20261018/gran_loader_probe_source.py`.
Its hard-coded RAM/dependency paths describe the actual research invocation,
not a portable supported command. The generated 1 MiB memory remains RAM-only
and is not published. This probe has not yet gained independent repeats,
observed/unobserved controls, bounded compact fixture export, complete input
binding or C++ comparison. Its output is not a frozen regression expectation
and does not clear the merge blocker.

The next step is a guarded original-loader corpus with explicit DOS-device
contracts, then physical GRAN initialization and ongoing actor writes checked
against those original outputs and the existing continuous boss evidence.
