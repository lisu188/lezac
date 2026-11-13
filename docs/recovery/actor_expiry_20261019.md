# Original Actor Expiry And Compaction

`ActorExpiryOperation` continues behavior 5 at `1000:65A8`. It executes the
original countdown, `3358..346A` physical-record removal and reference repair,
and the `18AC:0594..05DB` visual compactor. Stack checking, the 38-byte RTL
Move calls, timer IRQ execution and the actor's actual `LEAVE`/`RET 4` reuse
already recovered single-instruction operations on the same live memory bus.

The three explicit boundaries are an unexecuted motion tail at `73E5`, the
actual caller return, and the RTL error boundary at `1920:00E2`. The next
caller-loop iteration and the DOS runtime-error handler are not executed.
This operation is not integrated into production App gameplay.

## Recovered Behavior

The countdown subtracts `tick & 1` from the pointed-to actor's life byte.
Zero life on an even tick removes the actor immediately; zero on an odd tick
wraps to 255 and leaves for motion. These original byte semantics are retained.

Removal uses the signed current-index word against the zero-extended physical
count byte. It removes the selected visual entry, shifts subsequent 38-byte
physical records with real RTL Move calls, decrements the live count, and repairs
physical visual IDs and both descriptor reference bytes only when they exceed
the deleted visual ID. It then rewinds the caller's current-index word and,
for cached kind 10, decrements the separate kind-10 count byte. Original count
underflow and memory aliases are not normalized or clamped.

The visual compactor copies subsequent eight-byte entries in place, obeys DF,
and rereads the live count for its final decrement. Both copy routines support
bounded transfers and snapshot resumption. Zero-copy grants leave copy registers
and memory unchanged; oversized visual grants fail before a transfer.

## Original Evidence

Two independent final captures are byte-identical. They run unchanged original
code under Unicorn 2.1.4, fingerprint its actual mapped library before/after,
and pin the executable plus nine producer sources. Observed and unobserved runs
agree on all registers and the entire 1 MiB memory image. Ordered writes
reconstruct every complete final image. No call is stubbed, instruction patched,
hardware I/O performed, or IRQ injected into these original captures.

- `LEZAC.EXE` SHA-256:
  `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
- Projection: 199,196,044 bytes, SHA-256
  `e7e48d8b25e3a367c3ad90c59cc2a0e4ee0eb69892f2c4370e9f253443602bd0`.
- Published gzip: 21,524,580 bytes, SHA-256
  `aa993f44b378450ecbd0f261231a2ccfbb405a4be3c76f5542ecb9a864bd63a2`.
- Frozen manifest SHA-256:
  `6776b29677aee000904fe9ed35356e78eca7a7b85b21b4da3d34c941a18478bb`.

The final corpus has 3,258 cases, 4,300,118 register states and 2,428,750 ordered
writes. Outcomes are 602 motion handoffs, 2,650 actual returns and six RTL-error
handoffs. It covers all 143 newly implemented instruction addresses.

Profiles include full byte sweeps for life, kind, physical count, index, visual
count, deleted visual ID and reference count; reference-byte comparisons;
signed-index, parity, table-alias, DF and stack-probe cases. Of the 96 continuous
cases, 72 pass the physical DGROUP actor record. Twenty-four of those start at
the real `7EBB` caller, which pushes the physical pointer and creates the actual
`7EE4` return word. The other continuous cases start at `6053` and execute the
real prologue, contact/cache and tile dispatch before expiry. No memory or
registers are injected at any handoff. C++ composition is test-only.

An initial serialization exceeded its 192 MiB projection guard because each
visual byte was stored as a separate initial patch. Coalescing contiguous
patches preserved all 3,186 baseline initial images, register/flag traces and
ordered writes byte-for-byte. The physical-owner and real-caller cases were
then added, not substituted for earlier cases. The failed producer, superseded
captures and exact producers remain local evidence; final fixtures use the two
fresh expanded-domain captures. No full RAM images or screenshots are published.

## Validation

Strict GCC C++23, native MSVC `/W4 /WX /O2`, and ASan/UBSan each pass 29,322
replays over the complete instruction/string-grant matrix. Each performs
10,863,429 register/control comparisons and 30,652,164 logical dispatches, and
compares every ordered write and the complete final memory image. Trace
arithmetic flags retain the documented exclusion for undefined inherited
instruction results; all endpoint flags compare.

Twenty computed C++ IRQ targets pass immediate full-context restoration,
nested/finished rejection, BDA tick advancement and equivalent snapshot/grant
continuation, using 720 established timer-handler instructions. Two targets
interrupt real partially completed copies after exactly one byte is transferred.
These controls are not a new original-capture IRQ proof.

Twenty compiled faults are detected, covering parity/life, physical stride and
copy size, compaction, counts/index rewind, kind selection, equality/reference
repair, visual stride/direction, near-return cleanup and IRQ context/accounting.
Real source and tests are preserved. Fixture authentication/rejection controls
run on Linux and native Windows, retain existing evidence, report input failures,
and protect input/export/report aliases. All six focused CTests pass, including
the registered fault matrix and source guardrails (20 controls, 154 mapped
sources). Native Windows Git checkout preserves all 21 frozen families and 69
files, and reproduces 21 CRLF negative controls when protections are removed.

These are bounded original CPU, memory and toolchain results. They do not prove
production integration, natural gameplay, subsequent actor/frame continuation,
rendered frame alignment, frame timing or whole-game parity.
