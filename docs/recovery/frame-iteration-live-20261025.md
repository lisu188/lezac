# Natural Full-Frame Stream Recovery, 2026-10-25

## Scope

The recovery verifier now executes four consecutive original level-one frame
iterations, starting at game `7903` and ending at the fifth `7903` boundary.
The original frame counter advances naturally from 4 to 8. Each iteration runs
the active/render prefix, post-render prefix, actors, transient queues and tail.
The operation is `FrameIterationOperation`, not the legacy App update loop.

The compact record in `frame-iteration-live-20261025.json` supplies the exact
run identities, instruction counts, endpoint hashes and verification output.
Separate fresh runs have different timer phases and pixel hashes; they are not
represented as deterministic wall-clock repetitions.

## Original Observation

The host is rebuilt from the pinned DOSBox 0.74-3 sources and SDL inputs already
documented in `frame_active_20261018.md`. The normal-core observation hook and
read-only device getters are retained. The CPU decode implementation and guest
instruction bytes are not modified to accommodate the C++ operation.

The private Xvfb route sends ordinary `1` and Return input to start one player.
The four-frame observation begins only after the original reaches a bounded
early-game frame with an idle keyboard controller. No guest gameplay, clock,
IRQ, RNG or heap state is seeded. No helper instruction is stubbed. The child
environment and actual loaded SDL image are witnessed while it is running.
Both original and C++ execution use dummy audio; host volume is untouched.

The observer rejects unsupported VGA endpoint profiles. The accepted endpoints
have chained VGA backing, a six-bit DAC and PEL mask 255. Every intervening
instruction is observed and checked by the C++ replay; this route contains
write-index/data DAC output and timer EOI output, not mask programming.

## Memory Transport

The initial and final 1 MiB images are copied internally, with VGA backing read
without changing VGA read latches. They are sent over one inherited AF_UNIX
stream socket. A strict receiver accepts exactly two ordered, size-bounded
messages and rejects trailing data. The images remain in process memory.

The CPU projection includes those images, so it is passed to the verifier only
through a pipe. There is no `cpu.bin`, `.ram`, `.ram.gz` or core dump. Core dumps
are disabled before child processes start. The retained clock projection and
instruction trace contain compact observations, not full-memory images.
Rendered RGB and PNG endpoints are permitted visual evidence, not RAM dumps.

Each independent replay schedule seeds C++ memory, registers and device state
once, at the first `7903`. The following three iteration constructors receive
only computed registers. Memory, device state, DAC write continuation and clock
state carry forward. Later original states are comparisons, never injections.

## Comparison

Both ordinary execution and reconstruction after every dispatch are checked.
The verifier compares registers, unchanged opcode bytes, the original defined
flag masks, PIC/PIT queues and device/palette snapshots at every observation.
This is not a claim that every x86 flag bit is defined or compared.

Timer IRQs are predicted by the recovered work clock, including IRQs delivered
during rendering. They are not supplied from the recorded IRQ schedule. Final
memory is compared byte-for-byte over the complete 1 MiB in both schedules.
The final computed RGB frame is compared with the observed original VGA/palette
endpoint over all 64,000 pixels. The passing runs have zero differing pixels.

The new `VgaDacWriter` handles write-index/data transactions, six-bit masking,
bit replication, index wrapping and resumable partial RGB writes. Renderer
palette programming updates the dirty range without prematurely committing a
native LUT. Initial unobserved DAC read state is not inferred; data writes
before an observed index write are rejected.

## Validation

- Nineteen focused CTests pass: eleven operation/transport/DAC checks and eight
  shared device-clock/foreground checks, including their original-backed,
  rejection, coupling and SDL-provenance coverage.
- Nine transport tests cover the real C++ sender, bounded receiver, malformed
  headers, truncation, trailing data, unsupported descriptors, closed peers and
  frozen LF/CRLF source forms.
- Seven compiled DAC/palette mutations are detected after a positive baseline.
  Repeating the CTest retains a fresh owned run instead of colliding with the
  previous output directory.
- The DAC unit covers every byte value, snapshot continuation, index reset,
  invalid continuations and callback failure without continuation corruption.
- The DAC unit passes ASan/UBSan and native MSVC `/W4 /WX /O2`.
- The full-frame verifier also compiles under native MSVC. Its live original
  comparison has been run on Linux, not on native Windows or under sanitizers.
- A fresh Git-archive checkout passes all nine transport tests. The builder
  accepts only the two pinned raw LF/CRLF forms of each frozen observer input
  and records the actual raw hash. Original EXE bytes are never normalized.
- Source ownership guardrails pass with 177 mapped production sources.

The first exploratory capture exhausted the inherited 500,000-instruction
reserve in its second frame. A later full capture exposed the prefix-only
verifier's rejection of DAC output. Those are retained failures, not passing
evidence. The new observer has a bounded two-million-dispatch reserve and the
passing full comparison includes the real DAC effects.

## Reproduction

Keep all generated builds, source archives, traces and verification outputs in
RAM. Use fresh owned host/output paths and retain earlier host identities.
First build a pristine observer using `tools/active_frame_probe/build.py` and
the pinned inputs in `frame_active_20261018.md`, then run:

```sh
python3 -B tools/frame_iteration_live_probe/build.py \
  --host /dev/shm/lezac-pristine-observer \
  --retain /dev/shm/lezac-pristine-observer-before-full-frame
cmake -S . -B /dev/shm/lezac-full-frame-build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build /dev/shm/lezac-full-frame-build \
  --target lezac_frame_iteration_live_test
env SDL_AUDIODRIVER=dummy PYTHONDONTWRITEBYTECODE=1 TMPDIR=/dev/shm \
  xvfb-run -a -s '-screen 0 1024x768x24 -extension MIT-SHM' \
  python3 -B tools/frame_iteration_live_probe/capture.py \
  --dosbox /dev/shm/lezac-pristine-observer/dosbox-0.74-3/src/dosbox \
  --verifier /dev/shm/lezac-full-frame-build/lezac_frame_iteration_live_test \
  --out /dev/shm/lezac-natural-four-frame-observation
```

The compact record is durable. Large local traces, clock projections and PNG
views remain RAM-only and are not permanent fixtures. Replaying the live proof
after those processes and their in-memory endpoints have gone requires a new
natural original capture, not reconstruction from retained endpoint RAM files.

## Remaining Boundaries

This is a bounded early level-one observation, not campaign, boss, physical
keyboard, audio-output or UI-transition acceptance. It does not wire the
operation into the actual App. The existing REA/Ghidra prefix audit remains
separately scoped; no new whole-program decompilation claim is added here.

The historical optimized actor-pass failures tracked on draft #458 are still
unexplained. Passing these new natural windows does not explain or dismiss
them. This work depends on held #467/#468 and must remain draft until that
stability gate is resolved and exact-head review/validation permit merging.
