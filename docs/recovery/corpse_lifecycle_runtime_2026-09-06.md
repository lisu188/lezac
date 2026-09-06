# Original Corpse Motion And Fatal Conversion

## Scope And Provenance

Twelve seeded level-1 original cases match 3,612 consecutive production C++
updates: 586 corpse states, 2,200 reward states and 1,104 effect states. Eight
cases begin with a corpse and four begin with a live kind-1 walker that the
original converts after contact with a seeded damaging tile. Each runs to
the disappearance of the corpse, reward and effects without actor reseeding.
This is not a natural bomb-to-collection route or a full-game fidelity claim.

Fixture: `tests/fixtures/corpse_lifecycle_original.txt`.
SHA-256 (LF bytes):
`68789c98624eabf104de51086162da61c524070525327759f6d3a956a8e26d30`.
Shipped executable SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

```sh
python3 tools/capture_original_death_transients.py --corpse-lifecycle \
  --run-dir /tmp/lezac-corpse-20260906-QpdUHo \
  --out build-codex-tmp/corpse-lifecycle-original-v1.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The run used copied shipped assets and the seeder's private Xvfb/DOSBox child,
with startup/intro/level waits of 10/8/5 seconds. A prior invocation against
an expired temporary directory failed preflight; it did not start the game.
The final capture completed all cases and exited zero. Repository assets
were not modified.

Fifteen instruction windows are guarded. The existing hooks at Ghidra
`7EC5` and `7EEA` freeze before/after the shared actor pass, preserving
registers/flags and replaying displaced instructions. Actual runtime hooks:
`01A2:7EC5`, `01A2:7EEA`. Captured CS=01A2, DS=0C44, ES=0C44,
SS=18B3, saved-SP=3FE4, BP=3FFE; register marker
`a201440c440cb318e43ffe3f`. Actor bytes are read from DS:1BAE, stride 38;
visual rows from DS:C21E, stride 8; descriptors from DS:C322, stride 4.
There is no per-actor IP breakpoint or native audio observation in this run.

The map pointer DS:C1FE is translated using the captured runtime segment,
not the seeder's nominal segment. Width DS:C204 is verified as 60. Spawners
are disabled, actor count starts at one, queues are cleared, and player
visual position is seeded to 240,168. Each case has 301 post-pass samples.
The player/camera and starting actor/map state are exogenous. Seeded damage
cells are restored between cases and after capture.

## Cases

All initial actors have fractional carries X=9A, Y=4E and hotspot 6. The
first eight start as kind 0C, behavior 2, timer 25, disabled animation and
zero-based sprite 47. Initial source-spawner byte is zero. RNG is 90E25B93
except `no_reward`, which starts at zero.

| Case | Visual X,Y | VX,VY (8.8) | First-pass parity |
| --- | --- | --- | --- |
| ground_even | 336,174 | 0,0 | even |
| ground_odd | 336,174 | 0,0 | odd |
| air_even | 336,130 | 389,-800 | even |
| air_odd | 336,130 | 389,-800 | odd |
| wall | 430,174 | 600,-200 | even |
| left | 336,174 | -300,-200 | odd |
| terminal | 336,30 | 0,2040 | even |
| no_reward | 336,174 | 0,0 | odd |
| fatal_ground_even | 336,174 | 208,0 | even |
| fatal_ground_odd | 336,174 | 208,0 | odd |
| fatal_air_even | 336,130 | 389,-800 | even |
| fatal_air_odd | 336,130 | 389,-800 | odd |

The four fatal cases instead seed kind 1, behavior 3, HP byte zero (one
remaining hit point), AI0=208 and timer zero. One glyph 75 is placed in the
pre-motion footprint: cell 1302 for ground cases or 942 for airborne cases.
The original actor update itself performs the fatal conversion. No death
timer, velocity, fraction or sprite is written after initial setup.

## Recovered Rules

- `7018..7058`: normal corpses use the same behavior-2 gravity, landing,
  friction and common collision/integration as bombs and rewards. Gravity
  adds 64 with a 07FF limit; landing snaps to an 8-pixel boundary. Movement
  occurs before countdown, including the expiry frame.
- `75A7..75C8`: subtract the global odd-frame bit from the raw byte timer;
  zero or FF expires. A seeded timer-25 corpse first processed on an even
  frame has 49 visible post-pass states; an odd first pass has 48. Fatal
  conversion sets 25 after the countdown branch, so its visible lifetime
  including the conversion frame is 49 on an even fatal frame or 50 on odd.
- `7427` calls damage scanner `56B6` after integration using the pre-motion
  2x2 footprint. Glyph 75 contributes two damage; ordinary solid glyphs
  1..4C contribute one each with this caller's DS:208C=1, DS:2072=0 setup.
  The four runtime cases establish fatal glyph-75 contact, not every
  nonfatal or solid-cell combination.
- `74BB..74FC`: fatal conversion disables animation, sets behavior 2,
  kind 0C and timer 25, and releases the spawner slot. It does not clear
  velocities or fractions. The fatal sprite uses post-motion VX sign.
  Hotspot becomes `16 - corpse sprite height` before visual Y writeback.
- In `fatal_air_even` sample 0 (frame 3092), VX=389, VY=-736,
  fractions=1F/6E, visual position=338,127 and timer=25. The odd case's
  first sample (frame 3393) has the same state. The four descriptor bytes
  are `110a522e`, identifying zero-based sprite 48. Ground fatal cases
  retain VX=208, VY=0 with fractions=6A/4E and visual position=337,174.
- Expiry inherits the moving corpse's position, velocities and fractions
  into reward creation, then applies the recovered -200 VY impulse.
  The no-reward case instead creates the in-place fade. Both paths create
  the recovered moving particles and run continuously through retirement.
- The port's extra red death rectangle has no counterpart in these original
  captures and is removed. Normal death sound remains outside this evidence.

C++ stores the corpse countdown as remaining updates, deriving the raw byte
as `(remaining + 1) / 2` for comparison. The direct blast path still converts
before the monster pass and compensates its same-tick countdown; the seeded
tile path converts after movement. Full original bomb/actor ordering remains
open, including the live-motion rule on an ordinary bomb's fatal frame.

## Validation And Frame Inspection

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-corpse-lifecycle-original \
  tests/fixtures/corpse_lifecycle_original.txt \
  build-codex-tmp/corpse-lifecycle-cpp-v2
python3 tools/check_death_transients_fixture.py --corpse-lifecycle \
  --exe build/lezac_cpp
```

The replay seeds each initial state once and calls `updateWithControls`
continuously. Every sample compares corpse kind, raw timer, behavior,
animation-disable byte, hotspot, velocities, full fraction words, visual
position and descriptor. Reward/effect fields, shared count and RNG are
also compared using the previous lifecycle harness. All 3,612 rendered
frames are inspected and hashed; optional output saves 13 PPMs per case
and a per-checkpoint CSV manifest. Last frame hash: `152647ce100a2e5f`.
LF/CRLF pass; truncated completion and a mutated corpse timer fail; no
output directory means no frame files are created.

The initial broad run exposed nine tests assuming stationary corpses or
an unconditional 49-tick lifetime. Historical polling fixtures remain
unchanged. Their synthetic bomb replays are explicitly not phase-aligned;
the original 49 observed states remain reported separately from the odd
synthetic route's 50 updates. New atomic cases independently check both
phases. The direct blast test now checks the moving handoff and inherited
velocity/fractions rather than expecting the initial death position.

Focused tests: 12/12. Full headless CTest: 438 passed, one interactive test
skipped, 53.51 seconds. The separate interactive test passed in 3.66 seconds
(3.70 seconds total), covering all 439 tests across both runs. The full log
is preserved at `build-codex-tmp/corpse-lifecycle-full-tests-passing.log`.
The pre-existing debris diagnostic snprintf warning remains.

Inspected and shown together: original
`corpse-lifecycle-original-v1_fatal_air_odd_010.png` and C++
`corpse-lifecycle-cpp-v2/fatal_air_odd_10.ppm` (also converted to
`cpp-corpse-airborne-v2.png`). The unsupported red rectangle seen in the
first C++ rendering is absent after the correction. DOSBox stops before
presenting the current actor pass, giving a one-presentation-step offset.
Terrain/HUD differences remain; no pixel-parity claim is made.

## Remaining Work

- Natural bomb damage ordering and nonfatal impact presentation, including
  collision/collection interactions outside these seeded cases.
- Other corpse kinds, two-player cases and wider level coverage; the fatal
  conversion runtime evidence here is specifically kind 1 on level 1.
- Shared actor allocation/order, natural reward selection and collection,
  and ordinary death audio verification.
- Full-game functional completion and original-fidelity flags remain zero.
