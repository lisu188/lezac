# Startup clock and continuous physical reentry

Base: main `9879b70699170b8b48805bd36db9d89ae6489eed` (PR #248).
Scope: natural original level-1 clock/input observation, not campaign parity.

## Combined recorder

`tools/capture_original_startup_held_fire.py` composes the existing startup
session with the v4 physical held-fire recorder. A temporary executable waits
before the original Randomize call while a guarded clock recorder is installed.
The original DOS clock function then runs unchanged. No clock value, RNG seed,
objective, control byte or player state is supplied by the host.

Clock-only startup mode does not install RNG draw hooks or menu/intro/gameplay
phase gates. Two separate verified 4096-byte DOS allocations hold the startup
and gameplay recorders. This is 8192 resident bytes, not the old single-arena
4096-byte configuration. Dynamic original CS/DS addresses are derived from the
owned process, and the existing v4 ring, record fields and stub bytes do not
change. Physical menu/intro input starts only after the gameplay recorder is
installed, so the first retained gameplay sample is frame 1.

The combined sidecar binds the natural clock, packed seed and unchanged menu
RNG to the same CS/DS pair and DOSBox binary as the v4 trace. It checks the first
gameplay RNG against the recovered 398-draw initialization, an unchanged clock
record and one clock call after the route. Completion additionally requires
the strict v4 lifecycle, three restored gameplay hooks, one restored clock hook
and owned DOSBox exit 0. The legacy startup session still defaults to all six
phase/draw hooks; the legacy held-fire CLI still uses its original allocation
and startup path.

On failure the clock context and raw trace stay incomplete. Cleanup attempts
each owned hook and waits for the owned child; failed observations are not
repaired into completion. Every launched child uses dummy audio on a private
Xvfb display. No system volume setting changes.

## Natural original run A

RAM output: `/dev/shm/lezac-startup-physical-held-a-20260930`.
The unchanged clock metadata and compressed v4 trace are pinned under
`tests/fixtures/startup_held_fire_original/`.

- DOS CX=5143, DX=1309; packed initial/menu RNG `85791767`.
- Frame 1 RNG `1932475625`, exactly 398 generator steps from that seed.
- 290 continuous samples; dying sequence 206, resumed sequence 266.
- 267 make IRQs, one break, no waiting interval and 60 countdown updates.
- Exact death hook: frame 205, RNG `1384092689`, collected=0, remaining=1,
  required=1 and gate=1. Later sampled RNG is not substituted for this boundary.
- Clock record unchanged through the route, four verified hook restorations,
  owned DOSBox exit 0 and nonblank menu/intro/post-reentry screenshots.
- Canonical trace SHA-256
  `3df12c8484fc780c0d4c90f9506915d38be00c2ad6cb92f7dbe159010a0452a0`.

The raw capture predates later validator/cleanup hardening. Its original source
hashes remain unchanged, not re-signed. The current stronger validator accepts
the exact retained bytes with both LF and CRLF input. Synthetic unit-test joins
are explicitly not original observations.

## Separate checks and limits

The extracted Linux and native Windows `f39d444` packages both reproduce the
initial/menu RNG `85791767`, intro RNG `3618928815` and gameplay/first-present
RNG `1932475625` using the observed original clock. These are controlled C++
startup diagnostics, not natural C++ clocks or a physical route replay.

The default phase-gated startup recorder also completes a fresh regression:
one clock call, no pre-game draws, 398 initialization draws, two game starts,
all six hooks restored. Its old source/fixture pins are not changed.

The separate natural release/repress run B remains incomplete, with its raw
trace and startup context retained at
`/dev/shm/lezac-startup-physical-release-b-20260930`. Its strict lifecycle guard
rejects departure from the accepted gate/level/player conditions. Its recorded
clock seed is `874779676`, not run A's seed; no cross-run alignment is claimed.
The first rejected primary gate is at sequence/frame 205: collected=0,
remaining=0, required=1, gate=0. The exact death hook is frame 204 with RNG
`3586226925`. All three gameplay hooks and the clock hook are restored, the
clock record is unchanged and the owned child exits 0, but the lifecycle
remains incomplete.

Menu screenshots were inspected and shown from the original natural run and
the C++ controlled-clock diagnostic. They show different menu presentation
moments and are not a pixel-parity result. Startup RNG equality does not settle
menu cycling, physical typematic timing, actor/collision behavior, objective
destruction or rendering during the route. A controlled C++ physical replay
using the recorded startup clock and IRQ/update boundaries is the next step.
Natural full-campaign fidelity and reconstruction completion remain unproven.
