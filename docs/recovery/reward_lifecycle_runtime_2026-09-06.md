# Original Reward Motion And Expiry

## Scope And Provenance

Nine seeded original level-1 cases match 2,169 continuous production C++
updates: 1,789 live reward states and 438 live effect states. The cases cover
all seven reward kinds, inherited fractions, movement, landing, wall response,
the gravity limit, timer phase, fade animation and retirement. This is not a
natural kill-to-collection route, full corpse recovery, or pixel-parity claim.

Promoted fixture: `tests/fixtures/reward_lifecycle_original.txt`.
SHA-256 (LF bytes):
`877a8cc3351214fc4816f1808ab8c1c865bb060bea7914aca0c7e8416756b0cc`.
Shipped executable SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

The capture ran in a private Xvfb/DOSBox child with a temporary asset copy:

```sh
python3 tools/capture_original_death_transients.py --reward-lifecycle \
  --run-dir /tmp/lezac-reward-20260906-f4iAhN \
  --out build-codex-tmp/reward-lifecycle-original-v3.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The existing seeder launches `LEZAC.EXE` on level 1 with startup/intro/level
waits of 10/8/5 seconds. Both the temporary and repository EXE bytes must
match before launch. Twelve instruction windows are checked, then guarded
trampolines stop before and after the shared actor pass. They preserve flags
and registers and replay displaced instructions. Hooks are Ghidra `7EC5`
and `7EEA`; actual runtime stops were `01A2:7EC5` and `01A2:7EEA`.
Captured registers: CS=01A2, DS=0C44, ES=0C44, SS=18B3, saved-SP=3FE4,
BP=3FFE. The fixture records these at every checkpoint. No per-actor IP
breakpoint was installed. Raw actor bytes are read at DS:1BAE, stride 38;
visual entries at DS:C21E, stride 8; descriptors at DS:C322, stride 4.

Spawners are disabled with DS:79A6=0; actor count starts at one, player visual
position is 240,168, and collapse/debris queues are cleared at each case
boundary. The actor is seeded only once per case, then 241 consecutive
post-actor-pass checkpoints are recorded without reseeding. The camera/player
placement and these starting actor states are exogenous.

The first exploratory run completed with non-sprite-derived hotspots in
direct reward probes and an overly broad filler filter. It was not promoted.
A corrected run was interrupted and its temporary output was unavailable on
resume. No process remained. The final v3 run used fresh temporary assets,
saved its output in the workspace, completed all nine cases and exited zero.
An earlier static-guard address typo failed before live instrumentation; it
was a capture-tool error, not game behavior.

## Cases

Every actor starts with fractional carries X=9A, Y=4E and disabled animation.
The two `expiry_*` cases start a stationary kind-0C corpse at visual 336,174,
hotspot 6, timer zero, RNG=90E25B93, on even/odd frame parity respectively.
They reach the original reward-selection path, selecting Present and ending
the six creation RNG draws at 0A08326D. They do not prove a full corpse timer.

The other seven cases seed the reward directly with timer 100,
RNG=12345678, sprite-derived hotspot, and parity `kind % 2`:

| Case | Reward | Visual X,Y | VX,VY (8.8) | Hotspot |
| --- | --- | --- | --- | --- |
| kind_0 | Present | 336,174 | 0,-200 | 4 |
| kind_1 | FirstAid | 336,130 | 389,-800 | 6 |
| kind_2 | HotDog | 430,174 | 600,-200 | 6 |
| kind_3 | JollyCloud | 336,174 | -300,-200 | 6 |
| kind_4 | YellowBombBox | 336,30 | 0,2040 | 6 |
| kind_5 | GreenBombBox | 336,174 | 0,-1900 | 6 |
| kind_6 | BigDiamond | 440,174 | 1800,-200 | 0 |

## Recovered Rules

- Ghidra `7018..7058`: behavior 2 adds gravity 64 unless supported with
  nonnegative VY, clamps at 07FF, snaps a downward landing to an 8-pixel
  boundary and applies bottom-gated horizontal friction. The existing bomb
  physics uses this same branch and is now shared with rewards. The
  `kind_4` first update changes VY=07F8 to 07FF and carry Y=4E to 4D.
- The common actor response handles top and side contact before Y then X
  fixed-point integration. Fractional carries persist across landing.
  The wall and airborne cases are compared through all later updates, not
  just their first velocities.
- `75A7..75C8`: after integration, subtract the global frame's odd bit
  from the byte timer; zero or FF enters expiry.
- `76DE`: a newly selected reward has timer 100. `76EE` subtracts 200 from
  inherited VY. Fractions and VX survive. Only stationary-corpse creation
  is runtime-covered here; arbitrary incoming corpse velocities remain
  a static mapping plus direct reward-motion coverage.
- The sprite helper `5A75..5AF9` changes the hotspot to `16 - sprite height`
  without shifting the stored visual position. Present therefore changes
  from corpse hotspot 6 to reward hotspot 4, while preserving visual Y=174.
- A reused corpse slot is not dispatched a second time on its creation
  frame. C++ limits the reward update to the rewards that existed before
  the monster pass. This is a bounded fix, not global actor-order closure.
- Expired rewards become kind 0, behavior 5, zero velocity, timer 18, using
  DS:006C's one-based sprite 74 and the 74..79 delay-2 mode-1 animation.
  The visual position and fractions survive; the 16-pixel fade sprite sets
  hotspot zero. No new pair of death particles is allocated for reward
  expiry (`76F4` excludes kinds >=13).
- The port's artificial one-pixel reward bobbing is removed. The original
  reward descriptor remains fixed until expiry; movement is actor physics.

## Replay And Validation

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-reward-lifecycle-original \
  tests/fixtures/reward_lifecycle_original.txt \
  build-codex-tmp/reward-lifecycle-cpp-v2
python3 tools/check_death_transients_fixture.py --reward-lifecycle \
  --exe build/lezac_cpp
```

The diagnostic initializes each case once and invokes production
`updateWithControls` continuously. It compares reward kind, timer, behavior,
animation-disable byte, hotspot, velocities, full fraction words, visual X/Y
and four descriptor bytes; all seven animation bytes are compared for fading
and particle actors. Shared count, reward/effect presence and RNG also match.
Unused actor fields and identical visual-slot indices are not claimed.

All 2,169 rendered frames are inspected and hashed. Optional output saves a
CSV row for each checkpoint and eight representative PPM frames per case.
LF and CRLF traces pass; removing completion or changing the first reward
VY byte causes failure, and replay without an output directory creates no
frame files. Existing bomb-motion, reward-collection and death-effect tests
also pass. Full CTest: 435 passed and the interactive test skipped under
dummy SDL, in 47.18 seconds. The separate interactive test passed in 3.72
seconds, covering all 436 tests across the two runs. The pre-existing debris
diagnostic snprintf warning remains. Full-suite results are recorded in
`RECOVERY_STATUS.md`.

Original `reward-lifecycle-original-v3_expiry_odd_040.png` and C++
`expiry_odd_40.ppm` were inspected and shown to the user. Both show the
settled Present at the recovered position. DOSBox is stopped before the
current pass is presented, so these are not frame-aligned screenshots.
Terrain and HUD differences remain visible; no pixel claim is promoted.
The original `kind_1_010.png` and C++ `kind_1_10.ppm` airborne FirstAid views
were also inspected and shown, with the one-presentation-step offset noted.

## Remaining Work

- Full natural corpse motion and countdown, including moving death entry.
- Natural reward selection for all types, collection geometry/order,
  two-player arbitration and the original JollyCloud rain producer.
- Full shared actor-pool ordering, allocation failures and interactions with
  bombs, monsters and collapse across levels.
- Unrestricted visual fidelity and natural-route comparisons. Full-game
  completion and original-fidelity flags remain zero.
