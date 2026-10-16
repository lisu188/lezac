# Original IRQ Dispatch And Interrupted Clear

## New Evidence

Two corrected silent runs execute the unchanged original, SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Record rank eight and its rank-seven control use naturally acquired zero gameplay
scores and declared isolated record-file fixtures. The emulator host is
explicitly instrumented. Guest RAM/register/instruction writes and process
pauses are zero; gameplay, RNG, heap and clocks are not seeded.

The probe records guest state before normal-core decode, including live stack
and opcode bytes. Twenty asynchronous full-RAM checkpoints verify all 43,552
relocated code bytes. The analyzer independently verifies original trace opcodes
against the relocated executable. It does not claim materialized arithmetic
flags, an uninstrumented host, hardware-cycle timing or a complete frame stream.

The compact fixtures retain 1,752 rows: 1,235 rank-eight and 517 control rows.
They include recipes and exact source/host/trace pins, but no full RAM, raw VGA
or screenshots. CI validates numeric trace behavior only; raw pixel proof remains
in the user's explicitly RAM-only capture directories.

## Observed Failure Path

The rank-eight write changes the saved keyboard far target to `0800:0000`.
The original call at game `CS:1148`, `ff 1e 60 1b`, dispatches directly to that
target on the next recorded decode, with return `CS:114c` on the live stack.
The captured execution then reaches `0800:f699`, bytes `ffff`, and repeatedly
enters the INT06 vector `f000:1060`, bytes `fe 38 03 00 cf`. Sixty-five exception
entries in the recorded instruction window retain `0800:f699` in the return
frame. IF remains clear. The emulated CPU loops; it is not halted.

At keyboard-handler entry the saved interrupted instruction is game `CS:07ec`,
`REP STOSB`. ES is `a000`, AX is zero, DI is 33,712 and CX is 208. Stack words
retain row start 33,600 and 95 rows remaining. These values agree exactly:
`33600 + 320 - 208 = 33712`. Three independently saved pre-decode VGA frames
at handler entry, corrupted far-target entry and first invalid instruction all
match the later settled screen, 64,000 pixels without masks. Four later samples
retain identical screen, BIOS tick and adjacent-record bytes despite `r`, Return
and waits. The rank-seven control preserves the saved handlers, advances BIOS
ticks and changes all four corresponding frames.

The first isolated run in this batch interrupted at DI 33,596, the corrected
second run at 33,703, and a third at 33,700. The final canonical-asset-bound
recapture stopped at 33,712. Older
t186 captures interrupted at 33,705. The observed clear offset is therefore a result
of input/IRQ/work ordering, not a justified runtime constant.

## C++ Component Check

The compiled C++23 `ScreenClear` class was given the captured pre-clear background
as an explicit fixture and the independently read cursor 33,712. All 64,000
pixels match the frozen original. Budgets 33,711, 33,713, 33,703 and the older 33,705
are rejected. This is a seeded-background component replay, not independent
background generation, a full-App run or interrupt-scheduler acceptance.

The final producer persists failed terminal validation before raising, including
missing/incomplete traces, unsuccessful emulator exit, changed source assets and
short VGA snapshots. A regression executes the actual parsed finalizer against
five failure cases and one successful case. The final original recaptures are
bound to this producer; prior successful and failed attempts remain separate.
All fourteen shipped inputs are pinned before capture, and exact verified bytes
are copied. Geometry results are checked against the bound window, dimensions
and private-display bounds. The shared contract source is retained and hashed.

## Failed Layout Probe Retained

An initial probe saved only the first 64,000 bytes of host VGA linear storage.
DOSBox's compatible chained handler stores guest byte `i` at
`((i & ~3) << 2) + (i & 3)`, so that raw slice did not contain the complete frame.
Its attempted frozen-frame comparison failed. Both original first-attempt runs,
host source, traces, bad-layout snapshots, failed analysis and corrected recaptures
are retained separately in RAM. They are not overwritten or upgraded to pixel
proof. Earlier timer-entry snapshots can also legitimately precede further
clearing; only the appropriate frozen-boundary snapshots are compared as frozen.

## Remaining Integration

The App still needs work-ordered pending input/IRQ dispatch, BIOS/DOS clock
quantization and resumable original instruction/render progression. A fixed
clear prefix, a forced freeze on record rank, or the existing host millisecond
sound clock does not establish that ordering. Corrupted-target execution beyond
the observed seeded-memory profile remains unimplemented in C++.

This evidence strengthens the scheduler requirements; it does not complete
natural campaign, level-seven boss, synchronized original/C++ frame streams,
audio fidelity or owner visual acceptance. `full_app_claim=false` and
`whole_game_parity=false` remain.
