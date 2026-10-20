# Continuous Original Nonplayer Caller

## Recovered Boundary

NonplayerLoopOperation composes the existing caller/prologue, pre-contact,
contact/cache, tile classifier, motion/terrain, expiry and common finish
operations. It executes the real 7EBB caller and every 6053 actor call through
its near return. Original 7EE4 increments DS:2082 and 7EE8 branches to 7ECB;
both opcodes were verified in the pinned MZ and added to FrameActorEntryOperation.

Every child borrows the same memory bus and SS. No fresh private stack is
substituted between actors. Return checks require the original caller BP/SP and
7EE4 destination. Actor/visual compaction, the callee's slot decrement, and the
caller's next increment remain original instructions, not host-side iteration.

The operation stops at 7EEA before the player phase. Behavior 0/1 reaching 6737
is an explicit PlayerMotion handoff, not a simulated player update. Original
runtime and divide faults also remain explicit endpoints.

## Unchanged Original Captures

Two independent original captures agree byte-for-byte:

- Executable SHA-256:
  7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec.
- Projection: 2,396,804 bytes, SHA-256
  cd8c2481bb0b00553a3536499eea106f3e68c4c89fcabed4da8e3504f00af1b3.
- Manifest SHA-256:
  63413defbef7be8db9bbcee979a472e87f41c4c859c8b8886aafa3db580e097a.
- Gzip: 435,169 bytes, SHA-256
  427136e20cd8456479774ccfac19db6f92bf7d5cd4762958393c7e66ae1d6e6f.

The 92 cases include 0/1/2/3/5/30 actors, player states 0/1/2, behavior bytes
0..6, extreme coordinate deltas, first/last/all expiry, two stack positions,
direction-flag profiles, a stack-check runtime error and a zero-period divide.
There are 453 actual calls, 449 actual returns, 213,051 register states,
38,232 ordered writes and 2,294 stack/slot checkpoints.

All initial state is controlled and declared before entry. There are no
instruction patches, stubbed calls, later injections or delivered interrupts in
the frozen original captures. Observed and unobserved complete memory/registers
agree, writes reconstruct all memory and original code bytes are unchanged.
An initial rejected preflight lacked the visual-compaction code range; the
successful pair also seeds the matching live visual count and exercises actual
physical/visual compaction. The rejected producer and failure record are retained.

## Verification

The C++ matrix runs 92 cases across 1/17/4096-instruction and 1/2/all-byte copy
grants: 828 replays, 676,160 register comparisons and 1,912,098 dispatches.
Every endpoint register, complete memory and ordered write matches. Intermediate
arithmetic flag bits 0x08D5 remain excluded, as in the established actor tests.
REP iteration alignment uses the existing expiry-test convention.

Ten additional computed IRQ controls restore CPU state, advance the BIOS tick,
reject nesting and continue consistently across grants/snapshot restores. One
control interrupts a genuinely partial visual-table copy. These controls
dispatch 360 IRQ instructions; they do not prove a natural original IRQ schedule.

Strict GCC, strict native MSVC /W4 /WX, ASan/UBSan, fixture authentication and
negative controls cover the same boundary. Native Windows initially exposed a
missing direct array include in the test; the fixed include-complete source
passes unchanged assertions. Compiled caller/stack/handoff/IRQ faults are
required to fail rather than merely compile.

## Remaining Production Gap

Case 18 has both players inactive. At original 6350, both X deltas are 6000,
but the first Y remains word 63707 (-1829), and the second remains 33895
(-31641), across consecutive actors. The current production target adapter
instead supplies (6000,0). A standalone distance formula therefore cannot
restore this behavior without the actual caller-stack lifetime.

This composition is not yet the live App's nonplayer scheduler. Production
wiring must use direct physical/map/shared-state owners and a shared caller SS,
not a diagnostic deep-copy/reconcile path. The stack must eventually be shared
with the other original frame phases as well, rather than reset each frame.
The full player-motion block, production IRQ/work-clock scheduling, natural
routes, rendering alignment and whole-frame/pixel acceptance remain incomplete.
