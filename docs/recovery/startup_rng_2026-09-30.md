# Startup clock and RNG draw boundary

## Original observation

The original `LEZAC.EXE` SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Main `CS:25B1` (file `2D21`) calls RTL `0920:142F`. Its instructions at file
`AD9F` are `b42ccd21890efe1a8916001bcb`: DOS GetTime (`INT 21h`, `AH=2Ch`),
store `CX` at `DS:1AFE`, store `DX` at `DS:1B00`, far return. The low/high
words of the seed therefore pack local time as:

```text
minute | (hour << 8) | (hundredths << 16) | (second << 24)
```

The [Microsoft MS-DOS Programmer's Reference, Get Time](https://www.pcjs.org/documents/books/mspl13/msdos/dosref33/)
defines the four returned clock bytes. The original generator at RTL `13F7`
(file `AD67`) advances `seed = seed * 08088405h + 1` modulo 32 bits.

`tools/capture_original_startup_rng.py` captured the real DOS clock result and
the live seed before the menu, before introduction, before the first update,
after the first presentation, and before a second game. The retained capture
is pinned under `tests/fixtures/startup_rng_original/`.

| Boundary | Randomize calls | Draws since Randomize | Seed |
| --- | ---: | ---: | --- |
| Before menu | 1 | 0 | `12170D1E` |
| Before first introduction | 1 | 0 | `12170D1E` |
| Before first update | 1 | 398 | `D942D948` |
| First presentation | 1 | 398 | `D942D948` |
| Second game before introduction | 1 | 406 | `335B4DC0` |

The recorder retained the first 32 pre-draw seeds, Random caller addresses,
arguments and RTL near return. The first eight arguments are
`80,80,20,20,20,30,30,30`, at main return offsets
`0234,023F,014E,0158,0162,016C,0176,0180`. The remaining initialization draws
are the already recovered 390 skyline draws. All sampled seeds continue the
same generator chain. The second-game observation proves no reseed on this
quit/results/menu/start path; it does not cover every possible menu path.

## Instrumentation limits

The tool copies assets into a fresh directory outside the checkout and runs
its own DOSBox under private Xvfb with `SDL_AUDIODRIVER=dummy`. A five-byte
temporary-file gate delays Randomize until a verified DOS-owned 4096-byte
resident allocation is installed. The original clock function is then called;
no gameplay seed, key bank, actor or objective byte is replaced. Main-phase
gates pause observation boundaries while interrupts continue. Dynamic runtime
segments are derived from the resident MCB and the code/data relationship,
not a fixed debugger segment. In this capture `CS=02AD`, `DS=0D4F`.

All six runtime hooks were restored and the owned process exited. Source and
DOSBox hashes, original clock registers, resident MCB, temporary gate hash and
phase registers are retained in `result.json`. Full screenshots were captured
from the 320x200 window, with separate nearest-neighbor previews. The pinned
PPMs contain the exact RGB bytes from those screenshots. The 60000-byte
backdrop is a direct original buffer read.

Earlier allocation and input-timing failures remain under ignored scratch
directories. They are not relabeled as successful captures. In particular the
first full first-frame run failed its second-game handshake; the later run
completed both game boundaries. These are clock-seeded, phase-gated startup
observations, not uninterrupted manual gameplay or whole-game parity proof.

## C++ correction

The natural interactive entry samples local time once after loading assets,
using the recovered byte packing. It initializes only the gradient buffer
before the menu, without generating a skyline. New-game introduction then
consumes eight draws and skyline generation consumes 390. The previous fixed
interactive seed and extra 390 pre-menu draws were both discrepancies.

Controlled route recording and existing debug scenarios continue to supply
their own seeds and retain their established preview initialization. They do
not silently inherit a wall clock, and their pinned original fixtures are not
reseeded or re-baselined. The optional clock callback in `runInteractive`
lets the startup diagnostic exercise the same production boundary with the
captured DOS clock, instead of a parallel initialization implementation.

## Validation and remaining scope

The capture self-check, pinned clock/draw checks, mutation tests, restoration
failure test, local core time-packing vectors and gradient tests cover the new
boundary. Native `startup_rng_original` compares the captured-clock
introduction and first-presentation RGB frames and all backdrop bytes, and
also exercises a real local-clock sample. CI retains those C++ screenshots and
comparison manifests on both platforms, including failures.

At initial submission the Python checks passed locally; native frame checks
and fresh full suites are pending CI. Local builds and large replay batches
were deferred while the Windows volume exceeded the project's 90% guard.
Do not infer completion of those checks from this document.

The first Linux CI run exposed a test-selection bug: a `skipUnless(EXE)`
decorator was evaluated before CLI parsing, so the native case stayed skipped
even with `--exe`. Its green CTest result did not prove pixel parity and its
upload had no screenshots. The corrected test checks executable availability
at runtime, and CTest now requires the explicit native success marker.
An independent silent run against CI-built production commit `c76a426`
then passed all six cases, with zero differences across 128000 RGB pixels and
all 60000 backdrop bytes, including a separate real local-clock run. That
bounded check used RAM-backed output while the disk guard remained active.
Fresh full suites after this harness correction are still required.

This correction does not establish identical host typematic timing, physical
held-through trajectory, every results-screen RNG consumer, complete campaign
fidelity or whole-game parity. The previously failed physical held-through
capture remains a failure and must be revisited with the corrected startup.
