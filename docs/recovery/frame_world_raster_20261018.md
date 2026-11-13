# Resumable Original World Raster

`FrameWorldRasterOperation` recovers the entire unchanged driver routine
`08AC:00F4..03C8` (exclusive end), file `0x9324..0x95F8`: 724 bytes and
283 instruction addresses. It copies the optional backdrop, draws masked or
opaque tiles, rejects invisible sprites, and draws fully visible or clipped
transparent sprites. There are no stubbed callees.

The C++23 operation retains registers, stack, scratch words, flags and return
state across instruction grants. Separate REP grants bound MOVSW transfers.
Word accesses can cross offset FFFF physically; SI/DI wrap between transfers.
DF affects LODS/STOS/MOVS, but a transparent sprite pixel uses the original
forward INC DI even when DF is set. This behavior is intentionally not normalized.

## Controlled Original Evidence

The producer runs the original MZ-loaded instructions in hash-pinned Unicorn
2.1.4, with no instruction substitutions, interrupt responses or port I/O.
Observed and unobserved executions agree on complete 1 MiB memory and every
endpoint register/flag. Loaded original code is checked unchanged.

The declared inputs use the actual 132-tile CARO bank and packed BOMOMIMK
sprite pixels, with explicit synthetic heap placement, map bytes, backdrop and
sprite descriptors. They are not a reconstruction of a natural heap snapshot.
The input source, EXE, tile/sprite assets and BOMPAL palette are authenticated.

Twenty-two cases cover pitches 320, 160 and 168; backdrop bytes 0, 1, 2 and 255;
both DF values; zero sprites; a 79-descriptor table; all clipping sides and
touching boundaries; signed coordinate extremes; all-byte tile indices with
controlled backing beyond the bank; unaligned buffers; segment wrap; and
nonzero/wrapping backdrop gaps. All 283 instruction addresses are exercised.

The compact public projection retains complete 65,538-byte output buffers,
six scratch words, 72 stack bytes, endpoint registers/flags and every original
byte/word write in address, width, value and order. No full RAM image is published.

- Projection: 8,119,240 bytes; compressed: 2,267,987 bytes.
- Projection SHA256: `a7f0b070b5b87513792df2c4f18f48347942d0e01308dc4206051fe86cca73ad`.
- Manifest SHA256: `b8ed194eb2564869f170efff7b6c1af51d5b03c5ec1ad1b9a958db624af54701`.
- EXE SHA256: `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
- Actual mapped Unicorn library SHA256: `ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c`.

The checker imports neither producer nor input module. Thus a deleted or
unreadable producer/input source still produces a failed report instead of
failing during import. It authenticates all frozen bytes before exporting;
matching outputs are reused and conflicting outputs preserved. Fifty rejection
calls cover changed/missing/unreadable sources/assets, new/existing exports,
conflicting existing output and overlapping report/export paths.

## Validation

Three instruction/REP budget pairs, `(1,1)`, `(17,3)` and `(4096,65535)`, produce
66 replays with snapshot reconstruction after each advance. All output bytes,
registers, complete endpoint flags, scratch/stack bytes, REP word counts and
2,860,080 original write events match. Zero-budget, empty REP, invalid grants
and finished no-ops are covered.

Strict GCC C++23 and native MSVC C++latest `/W4 /WX` pass. The fixture rejection
test passes under Linux and native Windows. AddressSanitizer and
UndefinedBehaviorSanitizer pass. Five new CTests and 19 existing source-guardrail
controls pass. Four isolated faults are detected: truthy backdrop mode,
discarded tile mask, opaque zero-valued sprite pixels, and lost clipping stride.
Fault diagnostics are retained without changing the actual source.

Original and C++ offscreen buffers were inspected in the authenticated canonical
palette and match byte-for-byte. These images are controlled buffer projections,
not gameplay screenshots, live DAC observations or full-screen HUD comparisons.

## Remaining Integration

This operation is not yet consumed by the App renderer or work-clock scheduler.
The next integration is the original gated camera/raster/copy caller at
`7A13..7A57`; `FrameForegroundOperation` still ends at `7A13`. A fresh App build
or natural-route capture is not claimed for this component-only change.

Dispatch counts are not DOSBox work-clock credits. Intermediate undefined flags
follow existing pinned DOSBox conventions but are not independently compared
against Unicorn at every instruction. Natural IRQ delivery during rendering,
live owner-bus/resource wiring, active-frame cadence, campaign-wide acceptance
and whole-game fidelity remain unproved. No broad completion flag is promoted.

All local builds, evidence, fault diagnostics and image projections remain in
RAM while C: is above the repository disk guard.
