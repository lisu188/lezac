# Original background and CRT work profile

## Scope

Two fresh runs executed the original `LEZAC.EXE` unchanged, with normal-core
DOSBox fixed at 6000 cycles. The host emulator was explicitly instrumented at
decode boundaries. This is diagnostic CPU-work evidence, not uninstrumented
wall-clock or complete frame-stream acceptance. The guest executable SHA256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

Only the isolated record-file fixture was seeded: six zero scores and a final
minus-one score allow naturally acquired zero-score level-1 play to enter the
rank-seven path. There were no guest memory writes, instruction injections,
process pauses, or gameplay/RNG/heap/clock seeds. Audio used the dummy driver.
Each of fourteen full-RAM observations verified 43,552 relocated code bytes.
RAM and RGB observations were asynchronous, not an atomic CPU/frame snapshot.

The committed fixtures contain 24,008 CSV records in two gzip files, totaling
568,186 bytes. They contain selected CPU registers, frame locals, cycle/dispatch
counters, and seven DAC entries. No full RAM images or screenshots are included.
`tests/fixtures/original_work_clock/manifest.json` records compressed and
uncompressed hashes, source/build pins, capture hashes, and expected profiles.

## Measured Background Work

The eight complete `CS:01fc` fills use eight different horizontal/vertical pairs.
Each has 402 sampled pixels, all 200 row boundaries, and 201 consecutive pixel
pairs. The analyzer verifies the following IRQ-excluded decode dispatch costs:

| Work | Dispatches |
| --- | ---: |
| Horizontal update | 4, plus 2 on carry |
| Row test | 7 |
| Color computation | 11 |
| VGA byte write | 1 |
| Tail to next pixel | 5 |
| Final tail to `CS:0309`, before `LEAVE` | 3 |

The row-only software floating-point work has a 200-element profile, identical
across all eight fills after subtracting two dispatches for a vertical carry.
Its entries range from 504 to 719 and sum to 137,748. These are emulator normal-
core dispatches, not hardware instruction timing or semantic cursor stages.

The measured cycle clock is deliberately separate from dispatch count. REP
clearing charges many cycles in one normal-core iteration, and budget-boundary
overruns also contribute differences. For example, one complete fill measured
1,986,291 dispatches versus 2,050,384 exclusive cycle-clock units. Treating one
`PatternFill` stage or one dispatch as one cycle is not supported by this evidence.

## Measured CRT Delay

The trace follows the CRT far routine at runtime segment `CS+084a`, offset
`029c`, through its actual return tuple. All 413 completed delays match:

```text
dispatches(N > 0, C) = 9 + N * (11 * C + 5)
```

Here `C` is the original CRT calibration word at `DS:7f68`, observed as 544.
The captured nonzero arguments and dispatches are:

| Argument | Dispatches | Completed observations |
| --- | ---: | ---: |
| 16 | 95,833 | 31 |
| 81 | 485,118 | 191 |
| 82 | 491,107 | 191 |

The unchanged-COM-byte zero-argument path is five dispatches by disassembly;
no completed zero-argument delay was captured here. The delay polls the byte at
`0040:0000`, not the BIOS tick at `0040:006c`. Each host shutdown interrupted
one pending delay; the analyzer reports both unfinished calls explicitly.
All 1,124 observed IRQ8/IRQ9 entries have matching returns and excluded work.

## Open Fidelity Finding

The calibrated game delay word at `DS:78ce` was 81 in every RAM sample of run
one and 82 in every sample of run two. The corresponding character-delay calls
used those same values. Disassembly of the startup routine at `CS:247f` shows
DOS time measurements around CRT delays and a software-real division whose
result is stored at `DS:78ce`; this capture starts after that calibration.

The current C++ UI still uses fixed `kLevelIntroCharacterDelayMs = 81` and
`kMainMenuCharacterDelayMs = 80`. This evidence does not justify replacing them
with a different universal constant. Recovering startup calibration, work-clock
scheduling, IRQ ordering, and natural rendering remains open. This PR changes
no C++ gameplay or timing behavior and does not close the rank-eight corrupted-
handler/frozen-frame finding.

## Validation

`tools/test_original_work_clock.py` replays both pinned original-backed traces,
compares raw and gzip decoding, rejects 29 structured corruptions and five
malformed streams, and checks the bounded decompression reserve. CTest registers
`original_work_clock_evidence`; focused CI runs it on Linux and Windows.

The host probe and minimal normal-core patch are under
`tools/original_work_probe/`. The host was built in tmpfs without installing
packages. See its README for the exact source boundary and build caveats.
The new raw evidence remains volatile in `/dev/shm` under the user's RAM-only
validation instruction. Committed compact fixtures are independent of that
temporary retention.
