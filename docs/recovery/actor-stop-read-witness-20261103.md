# Stopped Operand Read Witness

## Purpose

The [retained pre-allocation failure](actor-preallocation-20261103.md) includes
a nonzero masked native register operand alongside equal bounded ownership
fields read after the stop. It does not establish the earlier load values or
explain the divergence. This follow-up strengthens the next capture's read
provenance without changing the historical ELF or production game operations.

For each supported operand, the observer now performs, without resuming the
owned child:

1. A bounded `/proc/PID/mem` read of one, four or eight bytes.
2. A `PTRACE_PEEKDATA` native-word read at the same address, retaining only the
   requested logical bytes in the typed private report.
3. A second bounded `/proc/PID/mem` read.
4. A second complete `PTRACE_GETREGS` sample after all operand reads.

The witness distinguishes `cross_reader_agreement`, `contradiction` and an
incomplete `collecting` state. Short reads, changed memory, changed registers
and peek errors cannot produce a successful capture. The failure report keeps
the stop address/registers, message and available partial witness; the parent
still kills and reaps its owned child on every failure path.

## Read Bounds

The decoder's existing `host_metadata_bytes_read` count is the **logical first
read** count, not total kernel-interface traffic. The new witness reports
`logical_operand_bytes`, `proc_bytes_returned`, `ptrace_word_bytes` and
`host_memory_bytes_returned` separately. For a normal stack guard, these are
33, 66, 40 and 106 bytes respectively. A tag peek reads a full native word,
but only the requested tag byte is interpreted or retained. The register-input
constructor profile still never reads its not-yet-initialized parent/tag area.
The witness's logical count records requested operands even when a read fails;
the interface counts record only successfully returned bytes.

Native signed `long` results are preserved bit-for-bit, including a valid
all-ones word; the ptrace wrapper distinguishes that result from an actual
error using errno. Unsupported read sizes and invalid native words are rejected.
The report does not contain a full host or guest memory image.

## Validation

A live synthetic owned-child calibration verifies aligned words, unaligned
words and tag bytes through the actual WSL kernel interfaces. Its positive
control compares 17 logical bytes through 58 bytes of interface traffic and
confirms unchanged native registers. A deliberately changed **observer return
byte**, not a target-memory write, is rejected. The child is reaped and the
observer sources are preserved. This is not a game, original-oracle or replay
fault-capture calibration.

Seventeen operand-reader tests pass on Linux and native Windows Python. Nineteen
Linux diagnostic-report tests include five full mocked guard-stop paths:
agreement, changed memory, changed registers, a native peek error and a failed
second `/proc` read. They
check retained diagnostics, collector exclusion on failure, protected inputs
and kill/reap cleanup. The five focused diagnostic CTests pass.

The [compact receipt](actor-stop-read-witness-20261103.json) retains the final
bounded historical campaign outcome and evidence hashes separately from the
synthetic calibration. A campaign without a guard hit does not exercise the
new witness on the historical replay and cannot verify it retrospectively
against the earlier failure.

The sixteen-attempt fixed-update-bank campaign completes with fifteen passing
replays and one ordinary failure on attempt 5 (zero-based): `Frame actor entry
ID-toggle profile differs`. No watched contact guard is hit, so the new read
witness is not exercised on the historical replay. The supervisor exits
nonzero with `other_failures_without_target_capture`, retaining the failure
instead of calling the campaign a pass. Protected inputs remain byte-equal.
This campaign precedes the partial-read retention review fix below; it is not
rerun or represented as a current-head passing campaign.

## Partial-Read Review Fix

Review of `38d575a` finds that an operand sample was appended only after all
three reads completed. A peek or second-read error could therefore discard
earlier returned bytes before child cleanup. The fix creates an incomplete
sample before starting and records each successful observation immediately,
with its current stage and cumulative interface byte counts. An exception
retains those bytes plus its stage/type and leaves the witness incomplete.
Calling `finish` cannot promote an incomplete sample to agreement.

Focused controls cover failures at the first read, peek and second read.
The full supervisor tests verify retained first/peek bytes after both later
I/O failures, collector exclusion and kill/reap cleanup. The actual synthetic
kernel calibration is repeated successfully on the fixed reader. No new
historical replay or retrospective witness claim is made by that repair.

## Entry Guard Follow-Up

The uncaptured failure changes the next observation target. A fresh actual
REA/Ghidra session on WSL byte-verifies nineteen selected instructions in the
exact historical ELF around five entry-ID guard sites:

| Guard Offset | Native Context |
| --- | --- |
| `3184B` | FrameActorEntry.validate |
| `3D02D` | FrameActorPass.registers inline entry validation |
| `3DA27` | FrameActorPass.interruptInProgress inline entry validation |
| `89FE3` | FrameActorPass.advance inline entry validation |
| `91849` | FrameActorPass.deliverTimerInterrupt inline entry validation |

Selected observations include all five guard entries and exception-string
references, four memory-ID tests/branches, and the register-query ID load.
Every selected instruction matches the executable's bytes through an
independently parsed executable PT_LOAD segment. The session closes, server
exits zero and target is preserved. Format-specific ELF load attestation
remains unsupported. These are native C++ ELF observations, not original DOS
instruction or runtime-capture evidence.

The failed attempt is not attributed to any one of these sites. They are not
yet admitted operand layouts in the contact observer, and no entry-ID runtime
capture is claimed. The next observer must qualify that separate guard family
instead of treating another passing contact-only campaign as coverage of it.

## Limits

Both read interfaces share the same kernel. Agreement is **not independent
hardware evidence**, a proof of the earlier native loads, or a compiler/CPU
diagnosis. No production guard is relaxed and no recovered instruction is
changed. Earlier failures remain retained; the actor-pass integration hold,
`actual_app_integration=0` and `full_frame_claim=0` remain unchanged.

All new runtime artifacts and test scratch are RAM-backed, audio/video drivers
are dummy, and core dumps are disabled. No full guest RAM is exported.
