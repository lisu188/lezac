# Monster Death Transients

Branch: `codex/recover-monster-death-transients`, based on PR #209.
Scope: normal kind-0C corpse-expiry effects, not the whole actor pool,
corpse-motion/countdown path, or reward-motion behavior.

## Original Capture

The older level-1 capture in `build/monster-capture-attempt4` includes two
kind-0B effects in its full actor rows at polled frame 312: VX/VY (89,-164)
and (143,-132), timer 14, animation `46454f00020201`, descriptor `10107d3f`.
The promoted sprite-consumption fixture omitted these actors and C++ only
consumed their four velocity draws. That older full-DS polling is not an
atomic emulator stop; the new guarded capture establishes phase/lifecycle.

All new runs used the private asset copy
`/tmp/lezac-player-posture-20260905-4jbVwK`. The shipped executable on disk
was not patched. Both repository and temporary executable SHA-256 match:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The launcher creates a private Xvfb/DOSBox child and terminates it after
capture. The capture preflight also rejects a differing temporary executable.

```sh
python3 tools/capture_original_death_transients.py \
  --run-dir /tmp/lezac-player-posture-20260905-4jbVwK \
  --out /tmp/lezac-player-posture-20260905-4jbVwK/death_transients_v3.txt \
  --approve-procmem --approve-runtime-instrumentation
```

Startup/intro/level waits are 10/8/5 seconds. All eight cases completed,
each with 41 consecutive post-actor-pass checkpoints. Attempt v1 stopped
before probe writes: its 766D guard incorrectly included a relocated far-call
segment. The corrected guard checks the opcode and call offset. Seven-case
v2 completed; v3 adds inherited fractions and the executable hash. The v1
failure is a tooling observation, not game behavior.

Hooks are Ghidra `1000:7EC5` (before actor iteration) and `1000:7EEA` (after
all actors). They preserve flags/registers and replay displaced instructions.
Other guards cover 766D, 772A, 65A2, 2FAD and 7A6B. Captured registers:
CS=01A2, DS=0C44, ES=0C44, SS=18B3, saved-SP=3FE4, BP=3FFE. Runtime hooks
are `01A2:7EC5` and `01A2:7EEA`. The launcher's nominal CS=01ED/DS=0C8F
are memory-base conventions, not the observed register values.

Each case seeds one kind-0C/behavior-2 corpse with timer zero, visual position
(336,174), hotspot 6, zero velocity and an assigned RNG seed. Timer zero
isolates expiry on either parity; it does not validate natural countdown.
Pool probes add stationary filler actors at (440,240). DS:79A6 is zeroed to
disable unrelated spawns (guarded at 7A6B); player visual position is set to
(240,168) for framing. Collapse/debris queues are cleared per case. Actor
state is never reseeded between the 41 checkpoints. The last case starts
with fractional-position bytes 9A/4E.

Promoted fixture: `tests/fixtures/death_transients_original.txt`.
SHA-256 of its promoted LF bytes:
`a8512b3d75b163cbf7fe12fd597a56984b3ed917e5ae639a8567fac548b865fd`.

## Recovered Rules

- Kind-0C expiry at 766D draws `Random(100)`, then `Random(20)` for sound
  cursor EA74 plus the draw, priority 4. The existing threshold table selects
  rewards. A reward reuses the corpse slot rather than allocating beside it.
- Failed rolls enter 760D: the existing actor becomes kind 0, behavior 5,
  zero velocity, timer 18, one-based sprite/cursor 69..79, delay 2, mode 1.
  Fractions survive, including 9A/4E in the last probe. This converted actor
  does not update twice in its creation frame. Its visual Y is retained.
- 772A..777D attempts two kind-0B/behavior-5 particles for a normal corpse.
  Each draws VX then VY as `Random(600)-300`, even on full-pool failure.
  Initial timer is 15; initial sprite argument is decimal 13. Successful
  allocation initializes animation 69..79, delay 2, mode 2. DS:006A=45 and
  DS:006D=4F are the animation endpoint bytes.
- The actor loop at 7ECB reloads DS:208D each iteration, visiting appended
  particles in the same pass. Their first presented sprite is one-based 70
  (zero-based 69), not allocator placeholder 13. Coordinates/fractions already
  include one integration step.
- Behavior 5 advances animation, subtracts `frame&1` from the timer, deletes
  at zero, or integrates Y then X without gravity or collision. Particles
  have 29 live checkpoints on even-frame creation and 28 on odd creation.
  The in-place fade has 35/36 respectively, skipping its creation update.
- At count 29, a successful reward leaves room for one particle. At count
  30 no particle fits, but the reused reward/fade exists. All six RNG draws
  still occur: reward seed 90E25B93 ends at 0A08326D; seed zero ends at
  ABF18B42. C++ excludes the expired monster while counting its replacement.

File offsets are Ghidra offset + 0x770. Read-only disassembly used
`objdump -D -b binary -mi386 -Maddr16,data16` for the actor loop, expiry and
allocator/animation calls. The transient update is shared with pickup and
fracture actors; producers now supply their animation profile explicitly.

## Validation

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-death-transients-original tests/fixtures/death_transients_original.txt \
  build-codex-tmp/death-transients-cpp-v1
```

Eight cases, 328 checkpoints, 455 live effect states and 164 reward-presence
states match. C++ initializes each case once and runs production
`updateWithControls` continuously. Compared effect fields: kind, timer,
behavior, velocities, full fraction words, hotspot, all seven animation
bytes, X/Y and four descriptor bytes. Shared count and RNG also match.
Unused actor bytes and identical visual-slot indices are not claimed. The
filler actors model occupied slots, not their incidental actor fields.

Optional output contains 328 rendered frames and a CSV manifest with hashes,
RNG/counts and effect kind, X/Y, VX/VY, timer and sprite. With no output
directory, no frame files are written. LF and CRLF fixtures pass. Removing
completion or mutating the first particle timer fails, demonstrating actual
sensitivity to original data rather than only a port constant.

Nine focused tests pass. Full CTest: 432 passed, one interactive test skipped
under dummy SDL (42.19 seconds). The separate interactive test passed
(3.69 seconds), covering all 433 tests across the two runs. Full log:
`build-codex-tmp/death-transients-full-tests-passing.log`. Diff whitespace
validation passes. The existing debris diagnostic snprintf warning remains.

Original v2 `death_transients_v2_reward_odd_010.png` and C++
`reward_odd_10.ppm` were inspected and shown to the user. Both show expanding
particles using shipped artwork. DOSBox is frozen before presenting the
current actor pass, so the screenshots are not frame-aligned. The static
C++ reward also differs from original movement. No pixel parity is claimed.

## Open Work

- Full corpse movement/countdown needs continuous production comparison;
  these probes start at expiry.
- Reward motion, timer and later expiry remain open. This comparison checks
  reward presence, sprite and initial position only: `reward_motion_claim=0`.
- Global allocation/order remains split among collections. Same-pass particle
  updates do not prove arbitrary actor interaction ordering.
- Related expiry of kinds 0D..12 is outside the normal-corpse replay. Pickup
  allocation failure's last-actor animation overwrite is still open.
- Full-game completion and original-fidelity flags remain zero.
