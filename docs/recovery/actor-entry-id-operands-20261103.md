# Native Entry-ID Operand Observation

## Scope

The prior contact-only campaign retained an ordinary `Frame actor entry
ID-toggle profile differs` failure without a contact guard hit. The new
`--entry-id-guard-bank` option targets that separate family in the same
unchanged historical ELF. No production C++ operation, canonical replay source,
original executable or frozen fixture is changed. The root cause and the
dependent actor-pass/full-frame integration hold remain open.

## Qualified Layouts

The historical ELF is pinned by complete SHA-256
`b1c719393f987cd2a98090055c8cc06d5d71589090599a36f32c4d2fd5da47f6`.
Before admitting a read, the observer checks each predicate and conditional
branch, allocation call, exception-string reference, constructor call, and
the exact entry-ID exception string. The register-input load is also pinned.

| Guard | Native Context | ID Fields Read At The Stop |
| --- | --- | --- |
| `3184B` | Entry.validate | `[RDI+734]` |
| `3D02D` | Pass.registers.entry | `[RSP+22A4]`, `[RSP+1AE4]`, native `ECX` |
| `3DA27` | Pass.interruptInProgress.entry | `[RSP+734]`, `[RSP+EF4]` |
| `89FE3` | Pass.advance.entry | `[RSP+734]`, `[RSP+EF4]` |
| `91849` | Pass.deliverTimerInterrupt.entry | `[RSP+734]`, `[RSP+EF4]` |

Each memory field is exactly four bytes. The ordinary object/stack guards use
a memory `TEST`; the register-query guard uses `TEST ECX, FFDFFFFF`. Its live
low-32-bit register operand is retained separately from both memory copies.
Native ZF is retained without interpreting a later memory read as the value
of an earlier memory operand. Invalid ID bits are never normalized away.

The two four-slot banks cover all five sites. The standalone, register-query
and advance sites are watched in both banks; the other two alternate. Contact
and entry-ID bank selection is mutually exclusive. The default contact and
constructor observer remains available. Entry-ID constructor-entry captures
are explicitly unsupported for operand decoding, because exception allocation
has already clobbered relevant input registers. No such state is guessed.

## Read Witness

Entry fields use the same incremental `/proc`/`ptrace`/`/proc` witness and
second complete register sample as contact fields. Four-byte reads preserve
their exact logical width; `PTRACE_PEEKDATA` still returns an eight-byte native
word. One ID field therefore accounts for four logical bytes and sixteen
returned interface bytes. A two-copy layout accounts for eight and thirty-two.
Partial observations survive later read errors and child cleanup.

Both interfaces share a kernel. Their agreement is not independent hardware
evidence, full-snapshot ownership proof, or a compiler/CPU diagnosis.

## Actual REA/Ghidra Evidence

A fresh REA 6.7.0 / Ghidra 12.1.4 session on WSL observes 27 selected native
instructions, including the previously missing register predicate/branch and
the exact stack-copy address/REP sequences. Every selected instruction is
byte-equal to the executable file at an independently parsed executable
PT_LOAD offset. The session closes, server exits zero and target is preserved.
Complete inline instruction Evidence remains in bounded private files.

The provider's format-specific ELF load attestation remains **unsupported**.
The measured image base is `100000`; neither a verified whole load image nor
original DOS instruction/runtime evidence is claimed by this native analysis.

## Validation And Runtime

- Seven new layout tests pass on Linux and native Windows Python. They cover
  exact addresses/widths, register/memory distinction, missing inputs, short
  reads, unsupported constructors, witness accounting, bank coverage and 37
  changed-signature controls. The actual pinned ELF also passes qualification.
- Seventeen existing reader/witness tests pass on both platforms, now including
  a four-byte word case.
- Twenty-two Linux report tests pass. The full mocked hardware-stop test has
  twenty paths across contact, standalone entry, register entry and stack entry
  layouts, each with agreement or one of four controlled failures.
- All six focused diagnostic CTests pass. No native Windows C++ result or
  new-head hosted CI result is inferred from these Python/diagnostic checks.
- Actual synthetic owned-child kernel calibration passes for aligned and
  unaligned words, tag bytes and the new four-byte read: 21 logical bytes and
  74 returned interface bytes. Its changed observer-return-byte control fails
  as expected. No target register or memory is manually changed.
- Two historical unit-negative-control attempts, one per bank, exit zero but
  hit no entry guard. They are not a successful live fault-capture calibration.
- The real sixteen-attempt campaign arms each bank eight times. All complete
  historical replays pass, with no guard stop, uncaptured failure or operand
  witness. Protected inputs remain byte-equal. This is **bounded
  non-reproduction**, not a stability proof or a retrospective witness for any
  earlier failure.

The [compact receipt](actor-entry-id-operands-20261103.json) retains the final
outcomes, static observations and private evidence hashes. All new analysis,
runtime scratch and outputs remain RAM-backed, cores are disabled and audio
is dummy. No full guest RAM is exported. Existing failures,
`actual_app_integration=0`, `full_frame_claim=0` and campaign limits are unchanged.
