# Original Spark And Debris Updater

## Recovered Operation

`TransientUpdateOperation` executes original 1000:45FA..4D3B and returns
to its actual 8060 caller. It composes the separately recovered 3EDA
motion, 452A/458D removal, and 1920:0945 signed-long-division operations
on the same memory bus and physical caller stack. Existing terrain
seeding, type-1 effect construction, sound, RNG, stack-check and Real48
instructions execute through their current instruction owners. No App
gameplay model, synthetic helper result, or synthetic return is used.

The new generated instruction owner contains 1,057 explicit original
instructions: the complete updater body and 3A7E/3B18 velocity lookups
and 3BB2/3D46 weighted collision blending. The pinned Capstone 5.0.3
generator transcribes structured operands from the canonical MZ. Raw
98/99 opcodes explicitly retain 16-bit CBW/CWD despite decoder aliases.
There is no runtime decoder or generic x86 execution fallback in the port.

Flagged lookup identities distinguish collapse and debris pools. A
missing flagged identity leaves DS:661E unchanged; an unflagged identity
clears it. Matching records update both velocity and the actual one-based
slot. Blending uses the real signed-long divider, updates participating
records, and preserves original missing-identity and zero-mass behavior.
The original zero-mass IDIV fault remains a `DivideError` endpoint at
4818/484C, before any synthetic DOS exception presentation.

## Continuation Ownership

The generator derives 1,847 static stack profiles and 62 direct-call
descriptors from the original call graph. The operation retains bounded
caller frames, validates near/far entry widths and Pascal cleanup, and
binds profiled SP/BP to those caller frames. The motion, removal and
long-divider children retain their established independent ownership
checks. Actual returns must reach their recorded call-site continuation.
Foreground, active-child and completed-child counters are conserved.

The existing Real48 routines use BP as arithmetic scratch and a
data-dependent stack. Their internal instructions remain delegated to
the existing owner, not falsely described as having a fixed SP/BP
profile. Their saved call entry and caller continuation are owned here;
their running CS/PC is restricted to the existing library instruction
catalog. This is not comprehensive validation of arbitrary corrupted
Real48 computational state or a security-authenticated snapshot format.

## Independent Original Corpus

The producer executes unchanged original MZ instructions in pinned
Unicorn 2.1.4, verifying the actual mapped library hash. Fresh hooked and
unhooked engines must agree in all final registers and all 1 MiB of
memory. Ordered writes must independently reconstruct complete final
memory. No full RAM image is written or published. Output is a bounded
compact projection of initial seeds, traces, writes and canonical MZ.

The 1,142 cases cover the existing airborne/support/contact/cascade/
shatter debris matrix; spark motion, collisions, compaction, missing
identities and zero mass; and three actual root/nested stack-error
paths. Outcomes are 1,138 returns, three runtime errors and one divide
error. Original execution covers 1,110,956 instructions and 122,985
ordered writes. Eighteen cases retain dense register/control traces;
other cases retain entry/endpoint registers and every ordered write.

The compact raw corpus has 2,371,154 bytes, SHA-256
694d7c57f59df83e15aae6d00524950f4aa9dcc78578db437d4b2a4a5afda25c.
Deterministic gzip has 132,840 bytes, SHA-256
f8d8a07afffa9f6c875711432f73023dae23afb00ebf8d630b13f76aaf8db930.
The manifest pins producer sources, canonical asset and exact scope.
Fresh independent generation reproduces both manifest and compressed
projection byte-for-byte. Regenerating the C++ instruction owner also
produces an identical file.
The fixture checker bounds reads and decompression, rejects changed
inputs and output aliases, and retains failed reports for missing or
unreadable canonical inputs.

## Validation

Strict optimized GCC C++23, native MSVC /W4 /WX /O2, and GCC ASan/UBSan
pass 6,852 replays under three dispatch budgets and two copy budgets.
They compare 14,783 register/control checkpoints, every ordered write,
complete final memory, and every endpoint flag. Dense intermediate
arithmetic flags use mask 08D5 because borrowed MUL/Real48 code includes
undefined flag behavior; this is not an all-intermediate-flags claim.

The same test rejects 8,514 malformed continuations and computes eight
timer interrupts at observed boundaries. It checks exact foreground
restoration, one BIOS clock increment, nested-delivery rejection and
identical resumed execution under different dispatch budgets. These
are computed controls, not naturally observed original IRQ timing.
Ten independently compiled behavioral/ownership faults are detected
after an authenticated positive baseline. Seven fixture tests pass on
Linux; Windows passes six with the UNC hardlink case explicitly skipped.
The combined removal/motion/updater CTest selection passes all 17 tests,
including all three mutation campaigns, cold-checkout preservation,
source guardrails and recovery-Python compatibility.

The new operation is not integrated into the live App or the held frame
actor pass. Complete-frame execution, natural gameplay progression,
all original transient inputs, all intermediate flags, and end-to-end
original visual fidelity remain separate acceptance work. The existing
level-7 seeded App replay still matches 711,360 pixels across 15 views;
it is not visual proof of this new instruction-level operation.
