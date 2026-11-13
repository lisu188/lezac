# Complete Original Boss-Link Instructions

## Recovered Scope

`BossLinksOperation` executes the complete original `1000:432A..4529` loop,
returning to the actual frame caller at `1000:7EC5`. It includes the original
stack check, signed/word arithmetic, LongInt multiplication, orbit phase and
table reads, software Real48 multiplication and integer truncation. It does
not use host `sin`, floating-point fitting, a guest-function stub or a direct
semantic replacement for an instruction sequence.

The software Real48 instruction surface is reused from `FrameDisplayOperation`
through its resumable snapshot interface, one library instruction per outer
dispatch. Its unrelated game caller is never dispatched. The existing Real48
and frame-clock regressions remain unchanged and pass. The new operation
keeps its live register/stack state, outcome and dispatch count across every
budget boundary. Zero-budget and completed advances are inert.

This is a complete helper proof, not a completed frame, actor body or App
integration. The current App still has a typed boss-link helper. In particular,
its post-defeat physical-link evolution remains unproved; a clean instruction
model does not retroactively establish that live ownership behavior.

## Fresh Original Evidence

`tools/boss_links_oracle.py` executes the authoritative executable with
SHA-256 `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The producer requires Unicorn 2.1.4 and verifies the actually mapped native
library hash, both before and after the run. All 43,552 relocated code bytes
remain unchanged. Unexpected guest code segments, writes outside the declared
stack/link outputs, interrupts and hardware I/O fail closed.

Before the cases, the original startup loop `1000:2714..2767` computes all
128 six-byte sine values through its real software RTL callees. Its observed
and unobserved executions agree on complete 1 MiB memory and all 14 endpoint
registers. Its ordered writes reconstruct final memory. The resulting table
hash is `466aea5bff071d610e66710d74d2ddecc79853ece03a4ae038113e83609e72d8`,
exactly the fingerprint already recorded from historical unpatched DOSBox
captures in `tests/fixtures/pattern_fill_original.json`. That corroboration
is historical; this turn did not make a new natural DOSBox capture.

The 1,413 controlled cases cover:

- Counts zero through seven, mixed spring/orbit lists and the full byte count
  255 in an explicitly non-shipped all-spring profile.
- Every mode byte, spring gain, initial orbit phase, radius byte and signed
  bias byte.
- Target/self visual indices 0, 1, 31, 32, 127 and 255, including equal indices.
- Signed-word boundary offsets and low-word wrap/carry behavior.
- Three original stack-error paths, with both direction-flag states exercised
  throughout the corpus.

Every observed helper call agrees with a fresh unobserved engine on complete
memory and all 14 endpoint registers. Ordered writes independently reconstruct
the full memory image. Two final generations, `lezac-boss-links-t239-a` and
`-b`, produce byte-identical manifests and compressed projections. There are
368,425 register checkpoints and 45,014 writes across 355 helper/RTL code
addresses; the initializer separately visits 413 original code addresses.

Intermediate register traces compare control flags but exclude materialized
arithmetic flags, whose undefined bits vary with instruction implementation.
All endpoint flag bits are compared. Branch outcomes, every register value,
every ordered memory write and complete final memory must match regardless.

The frozen projection is 11,599,956 bytes, compressed to 1,093,356 bytes. Its
raw SHA-256 is `acec0bcfcfe60d3f4a135e4979b97dec32cda0cde71eb947ad9c350bb80e34a0`;
the manifest SHA-256 is
`61028c7c10ffcd7726b21e15e426fe975bc7135800b19d3673ee8f827e6521ae`.
Only compact register/write projections, table bytes and provenance metadata
are published, not full RAM images or screenshots.

## Validation

All 5,652 C++ replays match at budgets 1, 17, 97 and 4,096, with snapshot
reconstruction after each advance. The one-instruction variant consumes the
entire original register trace. Every variant compares exact ordered writes,
complete memory and endpoint registers/flags, including original errors.

Strict GCC C++23, native MSVC `/std:c++latest /W4 /WX /O2`, AddressSanitizer and
UndefinedBehaviorSanitizer replays pass. Entry validation rejects three wrong
entry fields, and an unknown segment fails without writes. All 20 selected
link/animation/Real48/ownership CTests pass. The first local batch had one
adjacent frame-clock test not run because its target was not built; its logs
were retained and the complete rerun passes after building that target.

Eight separately compiled faults are detected: skipping later links, unsigned
bias, wrong phase mask, wrong cosine phase, wrong spring Y offset, lost
multiply high word, wrong orbit radius and a missing phase write. Sources are
unchanged by the mutation run.

Fixture controls reject changed, missing and unreadable executable/producer
inputs and damaged projections, retain failed reports and existing exports,
and prevent input/output aliasing. Native Windows frozen cold checkout passes
15 families, 51 files and 15 CRLF rejection controls. All generated local
artifacts remain RAM-only under the disk reserve.

## Remaining Integration

The next frame stages must connect this operation to the recovered prefix on
the same live bus and stack, then execute the actor loop/body and remaining
frame tail. Continuous App work-clock/IRQ ownership and natural campaign
evidence remain required. No original-fidelity, natural gameplay, rendered
pixel, full-frame or whole-game parity claim is made by this CPU helper proof.
