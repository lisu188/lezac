# Original Post-Queue Tail CPU Recovery

This adds an independent C++23 operation beginning at original `1000:806A`,
after the debris/collapse queues. It recovers shake RNG, palette interpolation,
DAC writes, the countdown tile callback `3F27`, and its actual `370E` tile-writer
call. The writer reuses the existing actor-terrain instruction owner. Library
RNG and stack checks use the existing frame-spawner owner without call stubs.

The operation stops before the next-frame prefix (`7903`), completion call
(`8298`), Escape/menu body (`82B9`), view-resize bodies (`8224`/`825E`), or
runtime-error presentation (`1920:00E2`). It borrows the original caller stack;
actual near/far returns are checked before classifying terminal boundaries.
Snapshots retain nested return ownership and optional timer-IRQ state.

## Original Evidence

Two independent Unicorn 2.1.4 captures agree on the whole packed projection,
whole decoded projection and detailed observation report. The canonical MZ is
52,384 bytes with SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The producer verifies the loaded native Unicorn library, all producer sources,
relocated original code and exact reconstruction of initial and final 1 MiB RAM.
Detailed tracing agrees with stop-only code hooks on RAM, registers and ports.
There are no instruction patches, stubbed calls or later-state injections.

The 2,576 controlled cases observe 688,022 original instructions, 72,808 writes,
and 40,752 emulated DAC events. Endpoints comprise 616 next-frame, 1,158
completion, 210 Escape, 576 runtime-error and sixteen view-change handoffs.
Eight cases execute excluded-tile substitution. Signed fragment boundaries,
direction flags, palette loops, callback skips and stack-floor failures are
included. Existing 2,412 case records remain byte-identical as a prefix.

The compact `LZTAIL01` projection contains initial patches, entry/end registers,
delta register traces, ordered writes and DAC events, not complete RAM images.
Its decoded length is 14,476,040 bytes, SHA-256
`176eb02c288fb29c1f013e55f74781eb53055ad2f66c34bb5fc24246e6a9871a`.
The 231,225-byte gzip has SHA-256
`5821ed1b9cab839bba67c5dae0fc31c60b5ae57a48c08f447ccf8ab8bd3f6a29`.

An earlier all-zero word-map seed caused the original region scan to exceed
the instruction cap. The failed report and RAM remain retained. The final
controlled scene seeds finite neighboring groups; original instructions and
the cap were not altered. This is a harness-scene correction, not a game fix.

## Validation

The C++ replay passes all 7,728 executions at grants 1, 17 and 4,096, restoring
after every grant. It checks 732,276 register/control checkpoints, all ordered
writes, all final RAM bytes, exact endpoint flags, and exact DAC output order.
Intermediate arithmetic flags are masked with the existing parent policy;
this is not a claim of exhaustive defined-flag equivalence at every instruction.

Controls reject 41 base snapshots, 69 running/nested continuation mutations
and 33 malformed actual return frames. Eleven computed IRQ checkpoints execute
396 ISR instructions and preserve complete continuation across grant sizes.
These IRQ forks are C++ tests, not original-schedule observations. Original
captures deliver zero interrupts. Twenty compiled faults are rejected only
after unmodified unit and complete-original baselines pass. Six mocked runner
tests verify that a failed baseline or wrong projection earns no fault credit.
The excluded-tile fault passed the older dataset and fails the expanded one.

Strict GCC C++23 and native MSVC `/std:c++latest /W4 /WX /O2` builds pass the
complete corpus. AddressSanitizer and UndefinedBehaviorSanitizer also pass it.
Fixture rejection tests and eight command-line negative controls preserve
authenticated inputs and retain failure artifacts. Frozen-checkout protection
now includes this family; local cold-checkout validation is deliberately scoped
to this family because the full 28-family reserve exceeds RAM headroom.

## Remaining Scope

There is no production App integration or rendered-frame comparison for this
operation. Prefix, actor pass, queues, tail and work clock are not yet one
continuous original-backed frame. View/UI bodies, natural campaign routes,
original interrupt scheduling and whole-game fidelity remain open. This does
not clear the separately held actor-pass stability finding or change global
completion percentages or fidelity flags.
