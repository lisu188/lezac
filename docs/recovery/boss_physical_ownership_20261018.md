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
