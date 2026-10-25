# Original Collapse Queue Instructions

## Recovered Operation

`TransientUpdateOperation` now also admits `TransientUpdateEntry::Collapse`
at original 1000:5102. It executes the complete body through 5689 and
returns through the actual stack word to the frame caller at 806A.
The default entry remains the separately recovered 45FA spark/debris
updater. Both use the same physical memory bus, instruction budgeting,
caller-frame ownership, child counters and explicit timer delivery.

The new owner transcribes 850 unchanged MZ instructions in 4D3C..5689.
These include collapse map scans/transport, contact-lane collection,
fraction/velocity updates, record retirement and compaction. Horizontal
and vertical weighted blending execute the existing 3BB2/3D46 instruction
owners, including their actual signed-long-division child. Terrain
seeding, sound, RNG, actor construction and its 18AC:0517 graphics helper
execute through their existing owners. No constructor, collision,
division, copy or return result is stubbed.

The generated collapse catalog adds 1,354 stack profiles, 34 direct-call
descriptors and eight exact DIV fault sites. Its profile/call records
reuse the existing record types; the shared operation resolves both
catalogs. The optional pinned Capstone generator still produces exactly
the prior 1,057-instruction transient header without changing one byte.
The new header also regenerates byte-for-byte. There is no runtime x86
decoder or generic execution fallback in the port.
Real48 computational internals retain their existing ownership contract;
this does not turn arbitrary restored arithmetic state into an authenticated snapshot.

An empty standalone collapse call reaches the original Pascal termination
entry at 1920:00E9 and yields `Terminated`. That is an observed handoff,
not a claim that DOS shutdown/presentation has been executed. Runtime
errors stop at 00E2 and hardware divide faults at their actual original
instruction. The real frame caller normally skips 5102 for an empty pool.

## Independent Original Evidence

The new producer executes unmodified canonical MZ code with pinned
Unicorn 2.1.4 and verifies the actual mapped library hash. Fresh hooked
and unhooked engines must agree in every final register and all 1 MiB
of memory. Ordered writes independently reconstruct all final memory.
The producer publishes only bounded seeds/traces/writes, not full RAM.

The 2,551 controlled cases comprise the prior collapse matrix, 27
retained native cross-check cases, 150 new vertical-contact cases,
zero-width division, zero-mass vertical blending, three stack errors
and an empty-pool termination boundary. The native cases retain the
canonical level map, sprite descriptors, RNG, record and cell checks.
Synthetic rooms use width 16, native rooms width 60, and the divide
control width zero. Initial SS is 8000 and FLAGS is 0202 throughout;
this is not stack-alias or all-DF-input coverage.

The original executes 1,852,678 instructions and 328,947 ordered writes.
It enters horizontal blending 566 times, vertical blending 151 times,
record removal 454 times and actual actor construction 367 times.
Outcomes are 2,545 returns, four runtime errors, one divide error and
one termination handoff. Twenty cases retain dense register/control
traces; all others retain complete endpoints and every ordered write.

The raw projection is 10,407,081 bytes, SHA-256
6a6fd982af41b142908d34a8e2651af44a1cc6194eb45efeab1c0e0e997b8597.
Its deterministic gzip is 352,392 bytes, SHA-256
001d969b391501eb34d54d8a7dd8f176bcc6067a48ad6f56729dc3954ae3ffa5.
Independent fresh-engine regeneration reproduces both manifest and
gzip byte-for-byte. Canonical assets and every producer dependency are
pinned. The checker bounds reads/decompression, protects output aliases
and retains failed reports for changed, missing or unreadable inputs.

## Validation

Strict optimized GCC, native MSVC /W4 /WX /O2 and ASan/UBSan pass the
complete corpus: 15,306 resumptions, 26,018 register/control checkpoints,
every endpoint flag, every ordered write and all final memory. Snapshot
reconstruction follows every consumed grant. Dense intermediate flags
use arithmetic mask 08D5 for undefined borrowed MUL/Real48 behavior;
this is not an all-intermediate-flags claim.

The probe rejects 10,550 malformed continuations and checks immediate
terminal ownership. Ten computed IRQ cases verify register restoration,
one BIOS clock increment, nested rejection and equivalent continuation
under different budgets. One IRQ occurs after a single-byte partial
record copy. Zero copy grants preserve state; oversized grants are
rejected before writes; partial grants retain the REP continuation.
These are computed IRQ controls, not natural original IRQ captures.

All fourteen compiled collapse behavior/ownership faults are detected
after an authenticated positive baseline. A first fault definition was
rejected by the compiler for an unused parameter and was not counted;
the corrected definition compiles and is detected behaviorally. All 21
combined collapse/transient CTests pass, including all mutation
campaigns, frozen checkout, source guardrails and Python compatibility.
Seven Linux fixture tests pass; Windows passes six with the unsupported
WSL-UNC hardlink control explicitly skipped.

## Remaining Scope

This operation is not yet wired into the live App or a complete original
frame. The caller bridge at 804E..806A, coupled queue-pass evidence,
the held actor-pass intermittent failure and natural full-frame visual
comparison remain separate acceptance work. Complete-memory equality
for these controlled function calls is not whole-game fidelity.
