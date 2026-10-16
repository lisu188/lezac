# Foreground Frame-Clock Caller Candidate

This candidate extends the recovered DOS/PIC execution into game:791E..7966,
where the original stores the wrapping elapsed-centisecond word at DS:2074.
It stops before the separate Real48 display calculation. The live App cadence
and gameplay are unchanged. Full frame scheduling, foreign device callbacks,
and synchronized original/port frame streams remain unproved.

## Original Instruction Phase

The unchanged original block has 29 instructions. It stores DOS CL/DH/DL into
DS:79AA/79AB/79AC, reads the previous bytes at DS:79A4/79A8/79A9, and computes:

```text
(new_minute - old_minute) * 6000
  + (new_second - old_second) * 100
  + new_hundredth - old_hundredth
```

The result wraps to 16 bits. Old bytes are not normalized into valid clock
ranges. The original push/pop and intermediate CPU/flags behavior are retained,
not replaced with a final-value-only helper. Pinned DOSBox XOR materializes AF
as zero; its DIMULW preserves materialized non-CF/OF flags and uses strict
signed bounds. The instruction oracle checks final full flags independently.

Unicorn 2.1.4 executes these unchanged bytes for 3375 controlled combinations.
Inputs are explicitly seeded CPU/memory state, not natural gameplay. There are
no instruction patches or stubbed original calls; no complete-function or
whole-game claim is made. C++ passes 6750 final comparisons across uninterrupted
and per-instruction snapshot/restore modes, including full final registers,
flags, all eleven timing bytes and the fixed 128-byte stack window.

## DOS-To-Foreground Composition

The operation continues from the computed DOS IRET result at game:791E. It does
not reopen an already-returned DOS service to force an IRQ through that API.
A separate foreground timer context uses the same memory bus and computed CPU
state. Thirty controlled cases cover hardware IRQ delivery at every boundary
of the 29-instruction phase, including immediately after DOS return and after
the elapsed store before the next foreground instruction. The clock sample is
not reread after the IRQ updates BIOS 0040:006C.

The successful t202 r3 original run supplies two complete windows: call 6 has
355 states with no IRQ, and call 308 has 391 states with a natural IRQ at state
167. The IRQ occurs inside DOS (F000:14AB to F000:FEA5), not after DOS return.
Both windows then execute the complete 29-instruction foreground phase through
the DS:2074 store. C++ passes 1492 state comparisons in uninterrupted and
per-instruction snapshot/restore modes. CPU, memory, I/O/EOI and PIC decisions
are computed; later flags and IRQ decisions are comparison outputs, not injected
inputs. A naturally post-DOS IRQ remains unobserved; only controlled boundary
tests currently cover it.

The frozen checker binds the exact trace and recipe plus capture, input-route,
shared contract and all four observer sources. Five fixture tests cover 28
changed/missing-source and existing/new-output rejection controls, corrupted
retained identities, altered raw-sample claims, incomplete traces and missing
instruction boundaries. Three additional controlled-oracle tests cover frozen
identities and producer rejection. Frozen CI does not claim to reverify raw RAM.

## Capture Status

The r1 attempt was stopped with an owned KeyboardInterrupt after inspection
confirmed a stationary level-1 prompt. Its failed report, four RAM/screenshot
checkpoints, original producer, terminal trace and normal child exit are kept.

The r2 attempt ran to its 600-second observation bound and failed the natural
interrupted-window target. It contains a complete non-interrupted control, seven
raw RAM/screenshot checkpoints, a terminal trace and normal child exit. Two
ordinary Return inputs acknowledged independently inspected level-one text
masks. It then waited at Game Over. The failed target is not relabeled as a
successful capture. Its terminal control projection retains that distinction.

The r3 producer recognizes the exact inspected white-pixel text masks for
level one and Game Over plus the exact initial menu pixels. A stalled counter
alone never triggers input; all inputs remain bounded and recorded. Background
palette variation no longer prevents recognizing these inspected prompts.
Terminal reports have a separate bounded metadata reserve, so an ordinary
artifact-limit rejection does not discard the failure report.

The separate r3 attempt succeeded after 523 seconds. The child exited normally,
the trace has its terminal marker, canonical assets are unchanged, and all eight
RAM/screenshot checkpoints were independently hash-verified. Each RAM checkpoint
also matches all 43552 relocated original code bytes. RAM/RGB/CPU observations
are not atomic. The 2336779-byte terminal trace has SHA-256
`817faba32460f6fa06ebfbf9aa5f083224239a840fb3d0d14a5eb81be6bb92f8`.
Its compact compressed trace and exact recipe are retained as fixtures; no full
RAM or PNG payload is published. All local outputs and failed attempts remain
in RAM under the user's disk-pressure exception.

The observer host is DOSBox 0.74-3 with normal core and fixed 6000 cycles,
SHA-256 `f86adc819502d49f0cf5784d314c5122b461fc9eca38ab24e02d2013d39cebd3`.
It reuses configured baseline build products; a clean reproducible host binary
build is not claimed. Sound is disabled, observation is read-only, and no guest
instructions, clocks, RNG, heap or gameplay state were patched or seeded.

The host selects the first foreground control window in addition to the two
initial DOS controls and near-PIT windows. The retained recipe's abbreviated
`observation_selection` text omits that extra control selection; the exact
observer source and trace, both authenticated, establish the actual selection.
This historical description is retained unchanged rather than rewriting the
successful capture's producer or recipe after the fact.

## Validation And Limits

Focused GCC C++23 and native Windows MSVC replay pass the natural corpus, all
3375 controlled arithmetic cases in both restore modes, and thirty foreground
IRQ boundary cases. Eight focused CTests pass. The five route-policy, five
natural-fixture and three controlled-oracle Python tests pass on both platforms.
Source ownership/guardrails pass nineteen controls with 115 mapped sources.
Four isolated C++ faults are detected: corrupted elapsed store, lost overflow
flag, doubled foreground work, and corrupted post-DOS interrupt return context.

An initial broad `^frame_` CTest selector also selected unbuilt App and pacing
executables in the intentionally small RAM-only build. Its failed/not-run log
is retained separately. Only the eight targeted new CTests are claimed passing;
no full local suite or complete native App rebuild is claimed for this stage.
Fresh full CI and completed current-head external review remain merge gates.
