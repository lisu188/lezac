# Resumable Final View Copy

`FrameViewCopyOperation` recovers the unchanged 79-byte driver routine at
`08AC:03C8..0416`, file offsets `0x95F8..0x9647` (exclusive end). It is the
final indexed-VGA copy called by the main loop after each active player's
camera and world rasterization. It does not recover those preceding routines.

The operation uses the existing register, snapshot and segmented-bus contracts.
Each `advance` can stop at an instruction boundary; a separate REP grant bounds
the number of words transferred before returning control. SI and DI wrap after
each word, while the bus must read/write the two bytes of an unaligned word
across the physical segment boundary. DF selects the original transfer
direction; the later row adjustments remain forward additions even with DF set.
`LOOP` does not change flags. The routine loads DX with `0x3DA` but performs no
port I/O. A zero REP count does not request a transfer grant.

## Original Evidence

The producer executes original instructions in Unicorn 2.1.4 without stubs,
instruction patches, IRQs or port responses. All initial memory is explicitly
controlled, not a natural gameplay capture. The original EXE SHA256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The loaded Unicorn shared object is checked against the actual process mapping
and SHA256 `ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c`.
Loader overrides through `LD_PRELOAD` and `LIBUNICORN_PATH` are rejected.

Twelve cases cover full/split/narrowed pitches, camera fine offsets, odd source
and destination addresses, SI/DI wrap, both caller returns and both DF values.
Observed and unobserved executions have identical complete 1 MiB memory and
all endpoint registers/flags. Only compact endpoint projections are published:

- Decoded size: 787,524 bytes; compressed size: 23,206 bytes.
- Projection SHA256: `ae778371ca129d6638bc2039d8f64582783c2944d0860f9af066995909e8fefb`.
- Manifest SHA256: `4ec783c7e5e2d5e37cd55fc8e027ffa920b8223c54d0d0a61f4a6f0b1c4d9086`.

The frozen checker authenticates the manifest, producer, original EXE and both
compressed/decoded bytes before exporting data. It needs no Unicorn installation
or raw RAM. One Python test exercises 25 rejection calls, including missing,
changed and unreadable inputs with new and existing outputs. Existing output
is preserved and failed reports are retained. Matching output is reused.

An initial pattern repeated at 64 KiB and could not expose a deliberately wrong
word bus. It was not promoted. A boundary-distinguishing pattern was recaptured
from the original; the wrong bus now fails three cases. Exploratory outputs
and failure diagnostics remain separate in RAM.

## Validation And Limits

The C++ replay compares complete endpoint registers, stack and all 65,538 VGA
bytes, and separately verifies that unrelated memory is unchanged. It runs each
case with instruction budgets 1, 2, 17 and 100,000, crossed with REP grants 1,
7 and 65,535: 144 replays, reconstructing the operation from its snapshot after
every advance. Dispatch counts, zero-budget/finished no-ops, zero REP behavior,
entry/resume rejection and nonmutating invalid grants are checked too.

Strict GCC C++23 and native MSVC C++latest `/W4 /WX` builds pass. Both platforms
pass the unit and all 144 original-backed replays. All four new CTests and the
existing 19 source-guardrail controls pass. A full Linux App build also passes;
that App does not yet consume this new component.

Intermediate undefined flags follow the existing pinned DOSBox normal-core
conventions. Only complete endpoint flags are compared with Unicorn; this is
not a new independent proof of every intermediate undefined flag. The dispatch
counter is not DOSBox work-clock credit. No scheduler, device clock, natural
interrupt-during-copy, owner-bus integration, active frame or whole-game parity
claim is made. `FrameForegroundOperation` still ends at `7A13`, and production
gameplay still uses the host accumulator and existing renderer.

All local builds, original executions and captures are RAM-only while C: is
above the repository's disk guard. Games use dummy audio.
