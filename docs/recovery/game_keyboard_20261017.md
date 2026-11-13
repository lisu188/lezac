# Original Game Keyboard Drain

## Recovered Behavior

`GameKeyboardOperation` composes the recovered CRT and original game caller at
`game:7A00..7A13`. Far-call pushes, the caller's OR/JE, ReadKey calls, DS:2058
writes and the backward branch remain individually resumable dispatches.
Snapshots preserve a suspended CRT/BIOS operation and either caller-owned or
delegated IRQ0 context. The caller still owns interrupt eligibility.

The original drains all available characters before continuing the frame.
It does not clear DS:2058 when no character is available; the previous byte is
retained. Each successful ReadKey replaces that byte. An extended key writes
the zero prefix, loops through KeyPressed/ReadKey again, writes the pending
scan byte and drains the queue before reaching 7A13. These are not separate
frame inputs. Enhanced keys discarded by the pinned BIOS do not become game
characters. CheckBreak's console/INT23 handoff propagates out instead of
continuing the game loop.

## Original Evidence

A fresh silent, unseeded original gameplay run completed all three selected
whole-loop windows with the original CRT and BIOS handler executing normally:

| Initial Queue | States | ReadKey Calls |
| --- | ---: | ---: |
| Empty | 14 | 0 |
| ASCII | 47 | 1 |
| Extended | 69 | 2 |

All 130 states match in uninterrupted and per-dispatch snapshot/restore replay,
giving 260 comparisons. Registers, control flags under mask `0x700`, the
128-byte stack window, 132 BIOS bytes, CRT pending/break bytes, DS:2058, sound
globals and ordered I/O are compared. Later observations are never injected.
The extended-key prefix and scan-byte writes occur inside one natural window.
There is no observed IRQ0 entry in this corpus; no eligibility claim is made.

The separate read-only observer preserves earlier CRT/pacing fixtures. The
original CPU-core and BIOS-handler bodies are unchanged, and producer/parser,
contract, observer, patch and getter hashes bind the frozen evidence. Five raw
RAM/PNG checkpoints independently match all 43,552 relocated original code
bytes. The emulator exits zero with a terminal trace and unchanged canonical
assets. Raw RAM and PNG files remain local; frozen validation reports zero
raw RAM files verified rather than implying access to unpublished samples.

- CPU projection SHA-256:
  `89497a184c532bf098361a91c012ec9866e51ba327a4d41f847753bc15eaf7b8`
- Compressed trace SHA-256:
  `7665e1730d7c42b4faf15a210f07a374e257a06f9128f654b17d681e5bf6f10c`
- Observation host SHA-256:
  `9231a4f113fcb2573b56b6a1668ea152dd5ca11e9b9ab83058beb9face071ccc`

## Validation

- 48 focused Linux CTests pass, including four new game-drain checks and all
  retained focused CRT, frame-display, elapsed-time, pacing and IRQ proofs.
- Native MSVC `/W4 /WX` build, unit tests and original replay pass. Four fixture
  test methods pass on Linux and Windows.
- Ten unit profiles cover empty-byte retention, multiple ASCII keys, extended
  prefixes, pending carry, NUL translation, numpad translation, enhanced-key
  discard and BIOS ring wrap. CheckBreak handoff also has focused coverage.
- IRQ0 replay passes at 445 eligible boundaries with 36 handler dispatches and
  unchanged caller results; 26 masked boundaries reject without state changes.
- Frozen validation rejects 60 changed/missing-source/output-preservation
  controls, three corrupted files and three trace terminal/dispatch controls.
- Eight isolated behavioral faults are detected: skipped caller OR, wrong ZF,
  far-call push order, scan/ASCII store, lost zero-prefix write, early exit,
  clearing the last byte on empty input and timer SI restoration.
- The skipped-OR mutant passes the unit assertions, but the independent
  original replay rejects its changed far-return stack. It is retained as
  evidence that runtime observation adds coverage beyond model-derived work.
- Source guardrails pass 19 controls with 122 mapped sources. Diff whitespace
  checking passes.

## Remaining Frame Work

The original pacing operation still ends at 79E8. Its conditional HUD prelude
at 79E8..7A00 calls 3184 and is not silently skipped or stubbed by this operation.
The downstream player/render path after 7A13, active IRQ1/repeat timing,
console/INT23 termination and production App cadence integration remain
incomplete. No whole-game, wall-clock, complete-frame or pixel parity is claimed.

New builds, captures and validation remain RAM-only under the explicit user
exception while C: exceeds the 90-percent guard. Five decoded CMake fixture
inputs were removed only after byte equality with authenticated retained frozen
generators and absence of active users were verified; the completed CTests
regenerated them. No source, fixture, unique raw evidence, failed run, host
binary or Windows-volume artifact was removed. Full local App and full-suite
validation were not rerun. Current-head review and fresh CI are required.
