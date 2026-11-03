# Before-Allocation Guard Coverage

## Hold Remains Open

This extends the initial ownership observer from three layouts to all eight
inlined contact-ownership guard sites. No recovered game operation, canonical
replay test, original executable or frozen fixture is modified. The historical
and current-model failures remain retained, and their cause is unresolved.
Later passing controls do not clear the actor-pass/full-frame integration hold.

The branch integrates reviewed PR #474 with main's independently merged strict
App build repair, PR #475. That repair is not an actor-fidelity fix.

## Pinned Guard Sites

| Instantiation | Guard Offset | Observer Bank |
| --- | --- | --- |
| ActorUpdate.interruptInProgress | 3ABF4 | queries |
| ActorUpdate.validate | 3B337 | queries |
| ActorUpdate.registers | 8ACF9 | queries |
| ActorUpdate.deliverTimerInterrupt | 91B5C | queries |
| ActorUpdate.register-input constructor | 8C5DC | updates |
| ActorUpdate.advance | 960C8 | updates |
| ActorUpdate.transition | 9FCBC | updates |
| FrameActorPass.advance inlined registers | A21AD | updates |

The ELF is pinned by complete SHA-256
`b1c719393f987cd2a98090055c8cc06d5d71589090599a36f32c4d2fd5da47f6`.
The observer verifies all eight constructor calls, exception-string references
and allocation calls before admitting a contact operand read. Seven layouts
have known source/destination stack-copy locations. A direct guard stop reads
33 bytes; a constructor-entry stop adds the eight-byte caller return address.
Inactive variant overlap remains explicitly disqualified as ownership proof.

The register-input constructor is different. Its native branches can reach
`8C5DC` before the parent fields and variant tag are stored. Reading the tag at
`RSP+1008` would therefore be uninitialized-storage observation, not evidence of
an invalid C++ variant. This profile instead retains parent game/ID inputs from
the callee-saved BP/R12 registers, selects the child from the R14 entry IP, and
reads only that child's eight-byte pair. It never reads parent memory or the
uninitialized tag. Its bounded reads are 8 bytes at a guard or 16 at constructor
entry. Bad game/ID bits are retained without normalization or diagnosis.

## Actual REA/Ghidra Observation

REA 6.7.0 with Ghidra 12.1.4 on WSL observes thirteen selected instructions in
the exact historical ELF: the eight guard entries, both constructor ID tests
and failure branches, and the later tag store. Each decoded instruction's bytes
match the original file at an independently parsed ELF PT_LOAD file offset.
The measured provider image base is `100000`.

The constructor observations include:

- `8C1EA`: `TEST R12D, FFDFFFFF`.
- `8C1F1`: conditional branch to `8C5DC` on a nonzero test result.
- `8C519` / `8C520`: the corresponding test and failure branch for the other child path.
- `8C22F`: `MOV byte ptr [RSP+1008], AL`, after successful validation.

The session closes, its server exits zero, and the target SHA is preserved.
REA's format-specific ELF load-image attestation is **unsupported** in this
version. Its measured mappings and the selected byte-equal instructions are
available; a verified whole ELF load image is not claimed. No target execution
or whole-program decompilation claim is made from these static observations.

## Runtime Observation

The new `--contact-guard-bank all` option alternates four query-site stops and
four update-site stops across attempts. The exact armed addresses and enabled
slots are retained per attempt. Bank selection targets guard addresses, not
slot numbers. The default constructor/runtime-error observer remains available.
Uncaptured replay failures still make a targeted campaign fail.

A complete sixteen-attempt campaign arms each bank on eight attempts. Every
historical replay exits zero with the authenticated 876 cases, 7884 schedules,
all 19 computed IRQ controls, complete-memory and ordered-write comparisons.
No guard stop or operand capture occurs. This is bounded non-reproduction,
not a passing fault-capture calibration or proof of stability. Inputs and the
historical ELF are preserved; no source instrumentation is used in this run.

A second campaign with the final reader reaches a **real guard stop before
exception allocation** at `9FCBC`, `ActorUpdate.transition`, on attempt 9
(zero-based), after nine complete passing replays. The parent, source-parent
and selected prefix-child pairs read `gameSegment=1000`, `idToggleMask=200000`.
The source variant tag is zero. The inactive contact overlap is not ownership
evidence. These are bounded direct reads before the GDB handoff, not optimized
DWARF interpretations. All protected inputs remain equal and the owned child
is reaped.

Native `RCX=0000020000100000`, `RSI=FFFFFFFF0000FFFF` and `EFLAGS=10206`
are retained at that stop. Their bitwise AND is `0000020000000000`; ZF is zero.
The pinned native path has a masked ownership `TEST RCX, RSI` and conditional
failure branch, as well as an earlier invalid-ID branch. These registers and
the equal later memory reads are different observations. They do not establish
which earlier load changed or why, nor prove a compiler, hardware or C++ source
fault. The stopped replay cursor is 4096 from advisory optimized DWARF; no case
index is recovered. The capture is not the earlier case-722 handoff control.

A second actual REA/Ghidra session byte-verifies eighteen selected transition
instructions, including the input load, ID test, both ownership XOR/mask/test
paths and their conditional branches. Its session closes and server exits
zero, with the target preserved. This is static corroboration of the native
path, not a replay of the earlier loads. Format-specific ELF load attestation
remains unsupported in both sessions.

Two separate unit-negative-control runs, one per bank, also finish without
hitting these contact guards. They are explicitly labelled calibration and
do **not** prove live operand capture at the eight sites. The later source
follow-up only exposes that calibration mode and labels; replay watch/read
behavior is unchanged.

## Computed Handoff Control

A separate source-instrumented RAM-only test copy authenticates the frozen
projection and computes case 722, mode 6 through row 251. It owns that computed
snapshot and repeats the `6540` to `654E` handoff 500000 times. Each repetition
equals the complete one-step reference snapshot and original next register row;
complete guest memory, ordered writes and the original operation remain unchanged.

This control passes, but deliberately reseeds the computed state on each
iteration. It is not a full-case/full-corpus replay, natural gameplay, or a
stability fix. Its generated source and executable stay in RAM. Canonical test
and production sources remain untouched.

## Focused Validation

- Eleven operand-reader tests pass on Linux and native Windows Python. They
  cover all seven stack layouts, both constructor child branches, absence of
  parent/tag reads, caller stack adjustment, short reads, invalid metadata,
  missing layouts, bank coverage and sixteen changed native signatures.
- Eighteen diagnostic-report tests pass, including bank rotation, all four
  enabled slots, explicit calibration, protected inputs and uncaptured failures.
- The final five-test diagnostic CTest subset passes.
- No Windows native C++ or new-head hosted CI result is claimed by these local
  Python and diagnostic checks.

The [compact receipt](actor-preallocation-20261103.json) retains outcomes and
hashes. Raw typed host reports stay private. Builds, runtime scratch, analysis
and outputs are RAM-backed; audio/video use dummy drivers and cores are disabled.
App integration, natural campaign completion and whole-game frame fidelity are
still unproven.

## Hosted Follow-Up

PR #472 head `d5f265d3b8240cfd111f10b158d329a8e89f0e9d` finishes the
Windows full-suite job with 1185/1191 tests passing. Six tests fail or are not
run because the post-render and iteration frozen manifests still bind the
older `oracle_failure_report.py`. This is a confirmed fixture dependency gap,
not evidence of a new passing actor replay. Its failed job is retained:
`41530681835 / 125570544684`. Any fixture repair requires fresh original
recapture and complete projection equality, not a hash-only manifest change.
