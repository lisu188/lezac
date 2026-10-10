# Corpse reward animation disable

The original corpse-to-reward conversion explicitly writes zero to actor byte
27 at `1000:76E6`. The port instead copied the corpse's `animMode`, which
preserved a nonzero mode in seeded conversion states. Ordinary fatal conversion
already disables corpse animation, so these controls are not evidence of a
naturally reachable nonzero corpse mode.

The production conversion now preserves the other six active animation bytes
while setting the mode to zero. It does not reset the cursor, range, counters,
or signed step, and does not change reward selection or RNG draws. The existing
in-place identity repair in PR336 is separate and remains required.

## Original evidence

`evidence/reward_animation_mode_20261009/` retains the exact original CPU
producer, executor, native fixture reader, and two independently executed
reports. The original executable is unpatched; no original calls are stubbed,
and hardware I/O is rejected. Each capture covers 26 seeded cases and 156
complete actor passes, comparing full memory and 14 registers against a neutral
executor at each boundary. Modes 0, 1, 2, and 3 are exercised in pools of one
and thirty actors. The recorded writes at `1000:76E6` set byte 27 to zero.

The modes can follow different animation prologues before conversion. The
new C++ regression deliberately calls the actual production conversion
directly, testing its unconditional disable invariant and preservation of the
other six active bytes. It is not a full-record, whole-pass, backup-preservation,
natural-route, or whole-game comparison.

## Validation

`corpse_reward_animation_mode_original` runs the actual App conversion with
four input modes and checks its active animation bytes, reward creation, and
RNG draw sequence. Both CI hosts run it immediately after the build and retain
the focused log before later tests replace it. Full exact-head CI and completed
review remain required before merge.

Bounded local validation checks App syntax, source/GRAN guards, CTest/workflow
registration, and compiled copies of the exact old/new production initializer.
The old initializer fails the nonzero-mode controls. Those compiled expression
controls are not execution of the full App; hosted actual-App proof is reported
separately. Broad fidelity and completion flags remain false.
