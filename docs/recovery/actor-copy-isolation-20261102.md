# Actor Copy Isolation And Failure Context

## Actual Failure Retained

The actor-pass stability hold is still open. A new full replay with the
failure-context logger raises `Frame actor contact ID-toggle/callee ownership
differs` in case 722, mode 6, copy limit 65535, budget 1, row 251. The reported
stage is `advance`, with 251 dispatched instructions, no timer instructions
or deliveries, and outer callee alternative 1. The 232-byte child log has
SHA-256 `73bd78144e0657884e7e1e800b423e925486f156d925895a7ce359ed5a4107d2`.

This run's direct full-corpus test passes, but the next CLI positive replay
fails. The complete focused run passes 11 of 13 tests: the CLI replay fails
as above, and the mutation runner separately fails on a CRLF-sensitive source
anchor. These are different failures. Neither is discarded or replaced by a
later passing run. Earlier current-model and historical failures also remain
valid evidence; the production cause has not been identified.

## Diagnostic Changes

The C++ replay test now reports the case, schedule, trace cursor, execution
stage and safe outer snapshot counters when an exception escapes a replay
iteration. It then rethrows. It does not reconstruct a possibly invalid child
to obtain registers while handling an exception. Initial operation construction
is outside this diagnostic catch, so that path is not covered by the new line.
All register comparisons, ordered writes, complete-memory checks, schedules
and computed IRQ controls remain enabled.

The CLI already retained each child's combined output in `positive.log`.
It now additionally includes up to the last 4096 bytes in its failure message
and records the child's exit code, output extent and SHA-256 in its JSON
receipt. A success marker never overrides a nonzero exit or a missing
canonical-MZ marker. This improves visibility without retrying away failures.

The source-mutation runner now uses universal-newline decoding on its captured
source bytes before applying each unique mutation. Canonical files and their
raw byte hashes are not changed. All 45 anchors are checked before compiling
the positive baseline. Seven pure contract tests pass on both Linux and native
Windows Python, including 135 LF/CRLF/CR anchor controls, missing/duplicate
anchor rejection, child-output identity, failure propagation and console bounds.
An invalid preflight anchor retains its failed receipt without launching the
compiler. The preflight remains inside the report-retention boundary.

Three validation-only injected exceptions at `advance`, `restore` and
`endpoint` each retain exactly one context line and return exit 1 with the
original exception text. Their generated sources and executables stay in RAM.
They are logger controls, not reproductions of the natural ownership failure.

## Synthetic Copy Controls

A GNU/Linux x86-64 diagnostic executable has two bounded modes, each limited
to 16 million iterations:

- `words` copies a 2072-byte by-value array twice per iteration, checking every
  word in both copies and selected ownership-shaped fields. The observed GCC
  copy boundary uses `rep movsq` for 259 words. A 16-million-iteration run
  completes 32 million copies without a reported mismatch.
- `variant` copies the real `FrameActorContactSnapshot` through a non-inlined
  by-value probe. A mutable callee rotates among three valid synthetic phases,
  and the reconstructed operation's complete register state is checked on each
  iteration. All 16 million iterations pass. No guest instruction is advanced,
  no original game state is used, and no memory bus is exercised.

The three new copy-control CTests pass. Their CLI test admits four positive
shapes and rejects twelve invalid shapes while protecting source/executable
hashes. The controls explicitly report no diagnosis or hold clearance. They
do not establish host stability or game fidelity, and they cannot exonerate a
specific compiler, copying instruction, variant implementation or hardware.

## Additional Bounded Evidence

- All four hardware execution-breakpoint slots independently trap at the
  historical ELF's verified `main` offset. Each owned child is killed/reaped;
  the ELF hash is preserved. This is debugger calibration before guest code,
  not a capture of the requested validation branch.
- Memcheck 3.22.0 reports zero errors for filtered cases 656 and 813, each
  executed under all nine schedules. All heap blocks are freed. This is not
  full-corpus Memcheck and does not prove absence of undefined behavior.
- The unchanged reviewed source at `d5f265d3b8240cfd111f10b158d329a8e89f0e9d`
  compiles under strict C++23 `-O1` with GCC 13.3 and Clang 18.1.3. Four
  interleaved full-corpus runs per compiler pass, preserving source, executable,
  fixture and MZ hashes. Each run covers 876 cases, 7884 schedules, 10432263
  comparisons, 29521980 dispatches and all 19 computed IRQ controls.
- Eight earlier full-corpus runs of the context-enabled test also pass. The
  subsequent case-722 failure above directly prevents treating this bounded
  non-reproduction as a stability fix. GCC's dangling-reference warning check
  also compiles cleanly; that is not proof of lifetime correctness.
- Sixteen filtered replays of case 722 pass all nine schedules. They authenticate
  all 876 fixture cases but execute only case 722 and no computed IRQ controls.
  The isolated case has not reproduced the full-corpus failure.

After the harness repairs, the focused CTest suite passes 14/14, including
the authenticated full replay and CLI control plus all 45 source-mutation
probes. The full-corpus comparison gates and the earlier failed suite remain
in force. Moving the preflight inside the retention boundary adds a seventh
pure contract regression; the 45 mutation bodies are unchanged by that move.
The final seven-test diagnostic/contract subset also passes after the move.
Native Windows C++ execution and new-head hosted CI are not claimed by these
local results; native Windows evidence here is Python-only.

No recovered production header, original binary or frozen fixture is changed
by this candidate. All builds and runtime validation are RAM-only and silent;
no full guest RAM or core is exported. Compact receipts and the actual failed
child log are retained durably. App integration, natural campaign completion,
pixel fidelity, physical input and owner acceptance are not newly validated.

The [machine-readable receipt](actor-copy-isolation-20261102.json) records the
completed validation scopes. This remains a stacked draft above PR #472 and
does not clear its actor-pass or dependent full-frame merge hold.
