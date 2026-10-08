# Bomb Launch Signed-Word Arithmetic

## Original Instructions

The shipped executable has SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The regression guards the complete launch arithmetic at `1000:6C2B..6C41`
and both constructor clamp sequences at `1000:2FC1..3000`. File offsets add
`0x770`; this is static instruction evidence, not a new live original capture.

The horizontal launch uses WORD `SHL` and `ADD` to form three times the
player's VX. Only then does `CWD/IDIV 2` divide the wrapped signed result,
truncating toward zero. The vertical `SUB AX,500` also wraps before reaching
the constructor. The constructor's `CWD/XOR/SUB` absolute value is a WORD;
`-32768` remains negative and passes its signed `<=0x07FF` test unchanged.

The previous C++ expressions widened multiplication, subtraction and absolute
value/clamping. The correction preserves these three original word boundaries
without changing input, placement order, allocation, ammunition, fuse, sprite,
position or fractional initialization.

## Bounded Evidence

Across all 65,536 signed input values, the previous horizontal expression
differs from the instruction-derived result at 24,574 values and the previous
vertical expression differs at 501. For example, VX 10923 produces -2047,
not +2047; VX 21846 produces 1, not 2047; VY -32268 produces -32768,
not -2047. These values are deliberately selected boundary inputs. Their
natural reachability is not established.

All 16 retained native constructor seeds in
`tests/fixtures/bomb_motion_original` agree with both the previous and corrected
expressions. These ordinary captured approaches do not exercise the newly
corrected overflow boundaries. Their full original trajectories remain an
independent regression, not evidence that every launch input was captured.

`tools/check_bomb_launch_word.py` derives two complete-domain fingerprints from
the guarded instructions and discriminates four arithmetic mutants. It compares
them with `--debug-bomb-launch-word-scan`, which calls the real `placeBombAt()`
for every signed value, four weapon selections and both owners: 524,288
constructors. The caller also checks coordinates, zero fractions, fuse seeds,
owner/type, ammunition consumption and both fire-latch resets. The oracle does
not derive expected values from C++ output.

Local validation passed the guarded oracle, full translation-unit syntax check
and a compiled isolated harness containing the exact unmodified production
constructor and scan bodies. The corrected body passes all 524,288 cases; the
old body and three compiled mutants are rejected. In that harness application
initialization, actor-count dependencies and sound dispatch are stubbed. It is
not a complete application runtime test. A subsequent fresh GNU Release build
of the real application passed all five selected CTests: `bomb_launch_word`,
`bomb_motion_original`, `bomb_fuse_original`, `natural_bomb_visual_original`
and `actor_floor_friction_word`. Thus the actual constructor also passed the
524,288-case scan. Initial sparse-checkout configuration/fixture failures are
preserved separately. This is a focused local result, not a full-suite result;
exact-head Linux/Windows CI and package verification remain separate gates.

The branch also carries the already prepared Linux CI job-budget correction
from 60 to 90 minutes. Test commands and per-test timeouts are unchanged; no
check is bypassed. Package verification remains a separate merge requirement.

## Remaining Scope

No new original process or natural route was run for this correction. Natural
extreme velocities, all bomb owner/damage attribution, full actor writeback,
sound equivalence, physical timing and whole-game fidelity remain unproven.
Level 4 is still incomplete and campaign completion remains 3/7. No broad
completion, fidelity or visual claim is promoted.
