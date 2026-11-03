# Actor Ownership Operand Observation

## Status

The actor-pass fidelity hold remains open. This follow-up improves native
failure observation without changing recovered production code or relaxing
any ownership guard. It does not identify a compiler, hardware or game-logic
cause, and it must not clear the dependent full-frame integration hold.

## Case 722 Original Boundary

The authenticated 876-case original projection locates the previously retained
case-722 failure cursor at row 251, `1000:6540`. The surrounding retained rows
are `653A`, `653C`, `653E`, `6540`, `654E`, `6552`, `655B`. At rows 251 and 252
the recorded flags are `0246`, CX is zero, and only IP changes from `6540` to
`654E`. These are selected rows from retained controlled original evidence,
not a fresh natural gameplay capture or a complete campaign comparison.

Actual REA 6.7.0 with Ghidra 12.1.4 on WSL decodes original bytes `76 0C` as
`JBE 1000:654E` at `6540`. Its byte extent equals the canonical MZ bytes.
The existing recovered branch tests carry or zero and selects the same target.
Eight surrounding instructions are observed; the transport's two inherited
decompilations at `2F9F` and `06AB` remain advisory and unrelated to this claim.
The session closes, the server exits zero, and the original target is unchanged.
This static result does not explain a host ownership validation exception.

Boundary evidence ID:
`ev_b84130c7de40177252dba0be21e61995c83d9b5937d45d862aed045f84578210`.

## Real Post-Allocation Failure

An unchanged historical executable is observed with hardware-only execution
stops at `3ABFE` and `8AD03`: immediately after exception allocation and before
the exception constructor. It retains a real contact-ownership exception at
`3ABFE`, inside `ActorUpdate.interruptInProgress`, with replay cursor 2929.
The optimized debugger cannot supply a case index, so this observation is not
attributed to case 722.

The capture reads exactly 33 bytes: four eight-byte game/ID ownership fields
and one variant tag. Parent, prefix child, contact child and source parent all
contain game segment `1000` and ID-toggle mask `00200000`; the tag is zero.
Only the prefix-child candidate is active under that tag. The contact-child
candidate overlaps inactive variant storage and is not a second active child
or independent ownership proof. These captured values agree after allocation.
They do not establish what the
guard read before allocation and cannot diagnose the failing predicate.
Optimized DWARF values remain advisory; the 33-byte raw field read is separately
qualified by its pinned native layout and stop phase.

This campaign captures the stop on attempt 15, after fifteen completed attempts:
fourteen pass and one reports an uncaptured contact-ownership exception. The
uncaptured failure remains recorded. No complete-memory or register-write
patch, software breakpoint, preload hook or full guest RAM/core export is used.
The historical ELF and all 684625 owned executable bytes remain unchanged;
the supervising parent kills and reaps the observed child after collection.

## Native Coverage Gap

The pinned executable has eight distinct constructor call sites for the same
contact-ownership exception text. Earlier targeted guard stops cover only
the `interruptInProgress` and `registers` instantiations. Missing those two
sites does not prove absence of another inlined failure.

The new observer records the return address at the exception constructor and
qualifies it against all eight pinned call sites. Each call signature verifies
the exception-string reference, argument move and call to the constructor PLT.
Three operand layouts are supported: `ActorUpdate.interruptInProgress`,
`ActorUpdate.registers` and `ActorUpdate.advance`. The remaining five sites are
reported explicitly as unsupported layouts, with only their eight-byte caller
return address retained. No guessed stack layout is used.

Direct guard stops retain 33 typed host-metadata bytes before allocation.
Supported constructor-entry stops retain 41 bytes, including the caller return
address, after allocation. Their phase labels are intentionally different.
The new `advance` profile follows its own destination variant tag; the other
two layouts follow the tag loaded from their source copy. Short reads and
unknown callers fail rather than generating an ownership interpretation.
Reports identify the selected child candidate and explicitly disqualify the
overlapping inactive candidate as ownership proof.

## Validation

- Seven operand-reader unit tests pass on Linux and native Windows Python.
  They cover all three direct/constructor layouts, the five unsupported sites,
  every short-read position, unknown callers, invalid tags, padding exclusion,
  and eleven changed native call/allocation signatures.
- All eight real constructor signatures and three allocation sites verify
  against the exact historical ELF, not only against synthetic unit data.
- Fifteen existing diagnostic-report tests still pass, including missing or
  changed inputs, uncaptured replay failures and collector cleanup.
- The focused eight-test diagnostic CTest subset passes.
- An actual invalid-argv hardware/GDB calibration captures its expected
  runtime-error constructor, preserves inputs and reaps its owned child. It is
  explicitly a calibration, not a natural game failure.

A later sixteen-attempt campaign watches the unchanged executable's
`interruptInProgress` and `advance` guards before allocation, with constructor
stops also enabled. All sixteen full replays exit zero and no throw is
captured. Protected inputs remain unchanged. This is bounded non-reproduction,
not an explanation or removal of the earlier real failures. The final follow-up
only adds the selected-child/inactive-overlap labels and corresponding unit
checks; it does not change the pinned reads or native site selection.

The [compact receipt](actor-owner-operands-20261103.json) records subsequent
observation outcomes and evidence hashes. Raw typed host reports stay private.
No new actual-App integration, natural campaign completion, pixel comparison,
physical input or owner acceptance is claimed by this diagnostic work.

The [before-allocation follow-up](actor-preallocation-20261103.md) supersedes
the initial three-layout reader described here. This report and its retained
capture hashes remain the record of the earlier observation.
