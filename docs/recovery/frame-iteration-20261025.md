# Continuous Original Frame Operation

## Implementation

`FrameIterationOperation` composes the existing original-instruction owners:
`FramePrefixOperation`, `FrameActorPassOperation`,
`FrameTransientQueuesOperation`, and `FrameTailOperation`.
The same memory bus, SS, and actual registers flow through every handoff.
The original boundaries are `7EBB`, `804E`, and `806A`; no gameplay state is
manufactured at these boundaries. UI, restart, completion, escape, view-change,
runtime-error, divide-error, and termination remain explicit outcomes.

Snapshots retain the active child and completed phase counters. Restoration
rejects contradictory child ownership, stack anchors, active/future phase work,
missing mandatory prior work, incompatible outcomes, and inconsistent timer or
dispatch totals. Zero grants and terminal operations consume no work.
One-instruction delegation retains each child's actual REP copy budget and IRQ
behavior. The production App does not use this new operation yet.

Full `7903` and post-render `7A57` entry constructors are admitted and restored
by unit tests. Their continuous execution through this new composition is not
covered by the new original corpus, which starts at `7EBB`.

## Original Evidence

The independent producer executes the unchanged canonical DOS MZ through
Unicorn 2.1.4, binding the actual mapped native library, all 20 producer/helper
sources, and the executable SHA-256. It never calls the C++ implementation.
Initial data is controlled; later phase state is never injected. The original
sine initializer supplies the boss table. Instructions are not patched, calls
are not stubbed, and no hardware input or timer interrupt is delivered.
Only emulated VGA DAC outputs are observed; there is no host hardware I/O.

The 1,102 cases cover 3,744,434 original instructions, 675,918 ordered writes,
480 ordered DAC outputs, and 64 dense traces. They include the complete actor
profile matrix, coupled spark/debris/collapse queues, countdown callbacks,
completion/escape/restart routing, both players, E/R view limits, and DF variants.
The corpus has 1,030 complete actor/queue/tail paths, 70 actor stops, and two
queue stops. Its cases do not reach collapse-copy helper `50BE`; that helper has
separate component evidence and is not claimed as new coupled coverage here.

Hooked and endpoint-only original runs must agree on all registers, full 1 MiB
memory, and ordered DAC outputs. Ordered writes must reconstruct that entire
memory. Only compact initial differences, traces, writes, and ports are retained;
no full guest memory or core dump is written. Producer failures use the bounded
diagnostic helper. The 64 MiB plus ten-percent RAM-reserve guard is retained.

The consumer replays six instruction/copy-grant schedules, restoring a snapshot
after every grant. All 6,612 replays match: 237,846 register comparisons,
21,968,850 C++ dispatches, exact endpoint flags, complete endpoint memory, ordered
writes, and ordered ports. Undefined arithmetic flags are not promoted to proof;
the six queue-caller comparison boundaries additionally compare all flags.
Unicorn's zero-count REP trace row is normalized explicitly.

## REA And Ghidra

REA 6.7.0 was actually run on WSL Ubuntu with Ghidra 12.1.4 and the existing
Linux JDK. The provider verified the canonical DOS MZ with
`x86:LE:16:Real Mode`, the default compiler, and load segment `1000`.
REA addresses are linear byte offsets: `1000:805D` is `0x1805d`.

The audit decoded 17 selected instructions, resolved four direct call sites,
and obtained two advisory decompilations. It independently confirmed the queue
gate comparisons and calls `805D -> 45FA`, `8067 -> 5102`, the `806A` tail gate,
and the `82B6 -> 7903` next-frame jump. The compact companion
`frame-iteration-ghidra-20261025.json` retains provider/evidence IDs, observations,
and SHA-256 hashes of the original responses and session report.

All 26 MCP calls completed without a reported error, the session closed cleanly,
and the target SHA-256 remained
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Ghidra applies MZ relocations in its temporary import, not in the target file.
The full static snapshot and responses remain in RAM; they are not guest dumps.
No REA registration or unrelated project configuration was changed.

Static decoding/reference resolution corroborates control flow, not runtime
execution. Decompiler types, calling conventions, and inferred stack locals are
advisory. The original-executable corpus supplies the bounded runtime evidence.

## Validation And Limits

- Strict GCC C++23 and native MSVC builds pass unit and all original replays.
- ASan/UBSan passes the same unit and 6,612-replay corpus.
- Unit tests reject 144 contradictory snapshots at three phase entries and the
  terminal boundary; three computed IRQ cases execute 108 timer instructions.
- Four wrong-entry controls, zero-grant, nested IRQ, and terminal controls pass.
- Fourteen compiled handoff, ownership, outcome, and accounting faults are
  detected against a passing positive baseline, with protected sources unchanged.
- Seven fixture rejection tests pass on Linux; Windows passes with the hardlink
  case skipped because that operation is unsupported on the WSL share.
  A fixture-only Windows rerun also passes all seven on NTFS, including hardlinks;
  that rerun used auto-cleaned host temporary files rather than RAM. The original,
  C++ native, sanitizer, and producer validation artifacts remain RAM-only.
- Four focused CTests pass, covering unit, fixture contract, replay, and rejection
  tests. The compiled-fault suite also passes independently of CTest.
- Independent regeneration reproduces both frozen files byte-for-byte. A focused
  real autocrlf-enabled checkout preserves all four new-family inputs and detects
  the missing-protection negative control. The complete 36-family catalog is
  registered, but a full 36-family cold checkout was not run locally.

These results do not establish natural campaign behavior, physical input,
shared-clock timing, continuous rendering-prefix execution, whole-game parity,
or production App integration. They do not explain the historical intermittent
optimized actor-pass failures. PR #458's stability hold therefore remains, and
any PR that depends on this composition must remain a draft until resolved.
