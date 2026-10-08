# Clocked Persistent Sound Playback

The interactive session and ordinary deterministic replay now use persistent
sound playback. They no longer synthesize and queue a whole effect at the end
of a gameplay update or clear a priority latch merely because samples were
queued. The earlier one-shot synthesis remains explicitly diagnostic-only.

## Clock And Evidence Boundary

The game's pinned original instructions install the recovered handler on
INT 1Ch, independently of the gameplay governor. The bounded original-byte
audit found the CRT Sound helper's channel-2 programming but has not proved
that every reachable instruction leaves channel 0 untouched. Actual original
IRQ cadence and startup phase have not been measured in a natural run.

The default clock is therefore an explicit inference: 1,193,182 PIT cycles
per second divided by 65,536. The primary
[DOSBox Staging v0.75.0 timer header](https://raw.githubusercontent.com/dosbox-staging/dosbox-staging/v0.75.0/include/timer.h)
defines that PIT rate, and its
[timer implementation](https://raw.githubusercontent.com/dosbox-staging/dosbox-staging/v0.75.0/src/hardware/timer.cpp)
initializes channel 0 with that divisor and schedules IRQ 0 from its period.
These sources explain the default model; they are not observations from the
installed DOSBox 0.74-3 or proof of the original game's physical cadence.

At 22,050 samples per second, the renderer carries an integer accumulator.
Each sample contributes 1,193,182 units, with an IRQ at 22,050 * 65,536 units.
The first IRQ is after one complete period; the unobserved initial phase is
zero. A transition at a sample boundary affects subsequent samples. This
quantizes IRQ placement to one output sample and is not cycle-exact emulation.

## Persistent State

The renderer calls the recovered per-IRQ transition, retaining the latch,
byte accumulator/gate/period, speaker divisor, enabled state and synthesis
phase across render chunks and accepted replacement requests. Frequencies
at most 18 do not replace or enable a speaker state. A terminal direct sweep
programs its last divisor before silencing it in the same IRQ. Gates do not
clear the priority latch, and period zero waits for the byte's 256-IRQ wrap.

The application services elapsed presentation time before event processing,
before updates and before each sound request. Interactive time comes from
SDL; deterministic replay uses its existing presentation clock, including
intro waits. Menus and pause do not stop the sound clock. Millisecond-to-sample
conversion retains its remainder and handles unsigned timestamp rollover.
Audio-device availability does not gate logical progression.

SDL output receives at most 200 ms of elapsed PCM per service call, not
future effect samples. It keeps a short initial silence lead and caps queued
presentation audio at approximately 250 ms. A host stall may discard stale
presentation audio, but all elapsed logical IRQ transitions still occur.
The device is opened with no allowed format changes, leaving continuous
hardware conversion to SDL as described by
[SDL_OpenAudioDevice](https://wiki.libsdl.org/SDL2/SDL_OpenAudioDevice).
This avoids separately resampling each small chunk with a stateless converter.

## Bounded Host-Stall Catch-Up

PR #308 review found that the previous 20 ms chunk loop synthesized every
missed sample after a host stall, even though the queue discarded most of it.
The replacement advances the stale prefix without allocating PCM and renders
only the most recent 4,410 samples. Already queued stale output is discarded.
Normal service intervals of at most 200 ms retain the existing exact renderer.

Both paths use the same recovered interrupt transition and tone-command
ordering. While a latch is active, skipping visits the actual IRQ boundaries;
after it ends, rational clock counters advance arithmetically in one step.
The shipped bank has 130 steps and an aggregate 351 period ticks. The longest
possible word-sized direct sweep takes 1,384 IRQs. Idle time therefore does not
increase the number of active transitions visited. Arithmetic splits large
sample products before multiplication to avoid intermediate overflow.

Skipped oscillator time uses modular doubling of the unchanged double-valued
per-sample increment. This is logarithmic even when an inactive latch retains
an enabled speaker. It preserves mathematical phase but can differ from the
old per-sample accumulation's floating-point roundoff. Regressions require
exact latch, byte counters, clock counters, divisor, gate and last-tone state;
phase is compared within 1e-9 cycles for the bounded reference trajectories.
One active retained PCM tail is checked exactly. Arbitrary skipped-interval
PCM equivalence and original hardware waveform parity are not claimed.

## Regressions

- `clocked_sound`: 1,000 exact rational boundaries; sixteen shipped/direct
  trajectories rendered whole and partitioned; stop ordering, priority
  lifetime, ignored commands, inherited replacement phase and period-zero wrap.
  It also covers 136 catch-up states, an active retained tail, eight-hour and
  maximum unsigned host-clock gaps, and an inactive latch with a sustained tone.
- `clocked_sound_app`: real application wrappers and presentation clock,
  menu/pause progression, terminal sweep state, timestamp rollover, bounded
  dummy-device output, an eight-hour catch-up and two inspected rendered frames.
- `clocked_sound_no_device`: the same logical transitions after closing the
  dummy output device, without gating or resetting sound state.
- `clocked_sound_live_menu` and `clocked_sound_live_pause`: bounded runs through
  the actual governed interactive loop with gameplay frozen and sound advancing.
- `clocked_sound_routing`: live/replay and request wiring, with twelve rejected
  in-memory source-routing mutations.
- `level1_replay`: existing production input/fire/pause route additionally
  requires pending priority-3 bomb-placement state after consecutive requests.

## Validation Status

The source-routing check and its twelve mutations pass locally. New compiled
catch-up tests still require fresh exact-head CI; their registration is not a
claimed pass. Local compilation and native recapture remain deferred under
unchanged disk/RAM reserve guards. The previous #308 full Linux/Windows and
package runs passed, but do not validate this changed head.

CI runs the six focused clocked-sound tests and uploads their four rendered
menu/pause frames before starting the unchanged full suite. The focused step
does not replace the actual Linux/Windows full `Test` steps or either extracted
package gate. Artifacts are named `clocked-sound-linux` and
`clocked-sound-windows` and must be tied to their exact run/head when inspected.

All agent-launched runs use dummy audio. Native timing/phase, hardware waveform,
speaker reload phase, physical device latency and whole-game sound parity
remain unverified. The current square-wave synthesis is not a complete PIT
channel-2 or analog-speaker emulation. No broad gameplay OPEN item is closed.
`sound_runtime_parity_claim=false`, `original_fidelity_claim=false` and
`port_functionally_complete=false` remain unchanged.
