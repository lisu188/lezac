# Continuous Post-Render Recovery

## Scope

This extends `FrameIterationOperation` validation from the actor entry `7EBB`
back to post-render entry `7A57`. Existing production owners are unchanged.
The original spawner and waiting logic now execute into the existing actor,
queue, and tail owners on the same memory, registers and stack. No handoff state
is injected. The production App still does not use this operation.

The 1,348-case corpus includes 64 waiting-state profiles, 54 spawner profiles,
and 128 lifecycle profiles in addition to the complete earlier body matrix.
Lifecycle inputs set actual actor state/timers, reserves, fire latch, configured
player count, and global player state coherently at the initial boundary.
Merely changing the global state bytes is not treated as lifecycle coverage.

## Original And C++ Evidence

The independent producer executes the unchanged MZ with a pinned actual Unicorn
2.1.4 library. All registers, full 1 MiB memory, ordered writes and DAC output
must agree between observer and endpoint-only runs. Ordered writes independently
reconstruct complete final memory; original code bytes are preserved.

The original executes 4,983,001 instructions and 1,431,749 writes. All 1,348
cases enter `7A57`; 1,332 reach `7EBB`, 1,220 reach `804E`, and 1,218 reach `806A`.
Sixteen stop at `1B14` before the game-over UI executes. Original observations
include 40 placement entries, 24 clear entries, 160 dying-timer decrements,
40 configured-player decrements, and 40 placement call sites at `7D20`.
Helper counts are across the full window. There is no new `326E` or `50BE`
coverage in this corpus.

The C++ consumer passes six instruction/copy schedules: 8,088 replays,
246,710 register comparisons, and 27,461,364 dispatches. It restores a snapshot
after every grant and matches exact endpoints/flags, complete memory, ordered
writes and ports. The old 1,102-case domain remains separately pinned and passes
unchanged. Intermediate undefined arithmetic flags retain the `08D5` mask;
259 observed queue-caller comparison boundaries additionally compare all flags.

Unit controls execute all four post-render phases and a computed timer IRQ
through the prefix, plus the original cleared-gate restart handoff. The empty
test setup originally expected a next frame with the gate cleared; source and
original behavior require a restart instead. Both outcomes now have explicit
controls, without changing production behavior.

## REA And Ghidra

`tools/rea_prefix_audit.py` runs an explicit local REA MCP stdio session on WSL.
REA 6.7.0, Ghidra 12.1.4 and the existing Linux JDK were used. REA 6.8 requires a
newer Node patch than the installed 22.22.2; no Node, engine, client registration
or unrelated project configuration was changed to perform this audit.

The provider verified the DOS MZ and 16-bit real-mode language, decoded 11 valid
selected instruction boundaries, resolved three direct calls, and produced two
advisory decompilations. The calls are `7B28 -> 2F9F`, `7B5C -> 1920:13A8`, and
`7C29 -> 06AB`. REA uses linear addresses, so the far RNG target is `0x1a5a8`.
These coordinates do not identify a unique segment:offset alias.

All 19 calls completed, the session closed, and the executable SHA-256 remained
unchanged. The compact companion JSON retains provider/evidence IDs, observations,
audit-source identity, and response hashes. Static decoding corroborates the
control flow; decompiler types and calling conventions are not recovered source
or runtime proof. Ghidra relocates its ephemeral import, not the target file.

## Validation

- Strict optimized GCC and MSVC pass the unit controls and both complete corpora.
- ASan/UBSan passes the same unit controls and both complete corpora, with
  protected source, executable and fixture hashes unchanged after validation.
- All 14 compiled prefix, spawner, reserve, timer, placement and handoff faults are
  detected against a passing baseline, with protected sources and fixtures intact.
- Seven fixture tests pass on Linux; native Windows passes with unsupported
  WSL-share hardlinks explicitly skipped.
- Independent regeneration reproduces manifest and gzip byte-for-byte.
- Nine focused CTests pass, including both corpora, negative controls, source
  ownership, and a full autocrlf-enabled 37-family cold checkout: 119 files and
  37 missing-protection negative controls.
- The full App builds with the existing unrelated `snprintf` truncation warning
  in `debugDebrisShatterPlayback`. Fresh seeded level-7 App replay separately
  matches 3,200 samples and 711,360 inspected pixels; it does not use this new path.

Validation outputs remain RAM-only. The source and compact regression fixture
are retained in an isolated durable worktree after the earlier RAM workspace
disappeared. Earlier unpublished RAM-only diagnostics were lost and are not
used as retained acceptance evidence; the current producer and audit were rerun.
No full guest RAM image or core dump was written or published.

## Remaining Work

Active prefix `7903` execution, shared-clock scheduling, natural full-frame
captures, UI completion, production App integration, and whole-game equivalence
are not established here. The historical intermittent optimized actor-pass
failure remains unexplained. This work inherits the holds in #458 and #467 and
must remain draft even with green checks or a clean review.
