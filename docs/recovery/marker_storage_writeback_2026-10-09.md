# Marker Physical Storage Write-Through

This recovery batch binds launch-pad and portal marker construction and updates
to the physical actor/visual tables. It is a controlled constructor-tail and
continuous behavior-5 comparison, not natural input, sound or campaign evidence.

## Original Evidence

Two independent CPU executions of the unmodified, pinned `LEZAC.EXE` produce
identical request and result streams. The producer and both manifests are in
`evidence/marker_storage_20261009/`; compressed fixtures are in
`tests/fixtures/marker_storage/`.

The launch constructor tail executes `1000:6932..6964`, including the real
`2F9F` allocator and successful caller's `695F` animation-mode clear. The portal
tail executes `1000:5A1C..5A69`, including allocation and the real `06AB`
seven-byte animation initializer. No expected animation is injected after
either constructor. The earlier input/tile gates, teleport destination lookup,
player impulse and sound prefix are outside this fixture's scope.

Each of 44 cases seeds complete physical actor, visual, link and scalar tables
once. Both initial tick parities, animation modes 0..3, counts 0/1/3/29/30,
permuted visual references, fractional carries, signed velocities, coordinate
word wraps, retained inactive bytes and later zero-timer records are exercised.
Subsequent constructors and actor passes operate continuously on that state.
Four dedicated last-record expiry cases cover terminal bytes that would be
overwritten by stable compaction when only middle records expire.

The 1,008 recorded boundaries comprise 44 seeds, 644 original shared-actor
passes, 160 launch attempts and 160 portal attempts. Launch admits 140 and
refuses 20; portal admits 124 and refuses 36. All 1,575 physical table bytes
are compared at every boundary: 1,587,600 compared bytes, with no masks.

A write observer is checked against a separate observer-free executor after
every boundary: all 1 MiB of emulated memory and 14 registers must agree.
Original instructions are not patched, calls are not stubbed, and hardware
I/O is not permitted. These are seeded CPU executions, not DOSBox gameplay
captures or naturally reached states.

## Recovered Rules

- Launch allocation clears only active animation mode at actor byte 27. The
  remaining active-animation bytes and the whole backup survive slot reuse.
- Portal allocation initializes active animation to `74,74,79,2,2,1,1`, keeping
  backup and other opaque bytes intact.
- Full-capacity attempts still call the allocator and set its success word to
  zero. The input action, player impulse or teleport is not conditional on a
  cosmetic marker being allocated.
- Behavior 5 unconditionally subtracts tick parity from its byte timer.
  A zero timer wraps to 255 on an odd tick; zero on an even tick retires.
- Animation executes before timer retirement. Updates write through before
  stable compaction, preserving terminal and inactive-tail bytes.
- A single ordered marker update may retire only that marker, not later
  zero-timer markers that have yet to execute their animation/timer step.
- Motion uses signed 8.8 integration and signed coordinate-word wrapping.
  Animation changes the visual pixel-offset word, retaining width/height.

## Production Validation

`--debug-marker-storage-original requests.bin actual.bin` seeds only on explicit
`S` requests. Constructors call the same `spawnLaunchPadMarker` and
`spawnPortalMarker` helpers as accepted gameplay actions. Updates call the
production `updateOrderedActors` dispatcher. Legacy adoption/retirement is
disabled, and physical identity/order is checked after every operation.

The standalone helper exercises the same marker updater and storage writer.
It is not a substitute for the actual App comparison. CTest registers separate
helper, App and checker-contract tests; both CI hosts preserve focused raw
results, process output and test logs immediately after those tests.

Local helper, sanitizer, source and registration results are recorded separately
from CI App execution. Full local game builds and the existing launch visual
fixture guard are deferred under the disk reserve: its two original text
fixtures alone exceed 10 MiB. Do not relabel skipped checks as passed.

## Remaining Scope

This advances physical write-through for another actor family. It does not
establish authoritative ownership of every original actor field, all actor
families, natural marker routes, complete campaigns, pixel fidelity, physical
timing or sound fidelity. Broad completion/fidelity flags remain unchanged.
