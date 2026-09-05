# Original Player Movement Recovery

Bomb launch captures exposed an error in the port's player model: after a
short right-input approach the original had VX=448, not an immediate 1024.
Five new original control streams establish the acceleration ramp, braking,
direction changes and the ordering needed to reproduce all 445 motion states.

## Original Instructions

Ghidra anchors below use segment `1000`; file offsets add `0x770`.
`LEZAC.EXE` SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

- `6053` updates the actor selected by the far pointer at `SS:BP+4`.
  Player 1 has kind 0, behavior 0 and zero sprite-height bias. Player 2's
  behavior 1 is normalized to 0 inside the original updater.
- `66F3` dispatches normalized behavior 0 to the player branch. It uses the
  shared two-cell edge scan, with `C=(x+4)>>3`, `R=y>>3`: top `(C,R-1)` and
  `(C+1,R-1)`, bottom `(C,R+2)` and `(C+1,R+2)`, left `(C-1,R)` and
  `(C-1,R+1)`, right `(C+2,R)` and `(C+2,R+1)`. Side/top solidity is 1..0x4C;
  bottom solidity is 1..0x52.
- `66FD..6734` identifies a step-hop when a side edge is solid but its upper
  tile is not. Directional input sets VY=-500 and VX=-250/+250, clears that
  side edge and then applies normal horizontal acceleration.
- `6743..6753` adds 64 to VY when airborne or rising, clamping at 0x07FF.
  Otherwise positive VY snaps Y to an 8-pixel boundary and becomes zero
  below the hard-landing threshold. Above 1600, the original has additional
  landing animation/cooldown handling and changes VY to `-VY/4`. This batch
  maps the velocity branch, not the complete hard-landing presentation.
- `6813` handles normalized input `DS:1B82..1B86` (jump, left, right, fire,
  down). Both horizontal directions clear each other and feed the existing
  weapon-switch chord; they do not force VX to zero.
- `6AC6` subtracts 64 if left is pressed and VX>-1024. `6B1C` adds 64 if
  right is pressed and VX<1024. These are pre-add threshold tests, not clamps.
- `6B27` handles grounded jump (VY=0 -> -848) and no-direction friction.
  Shared helper `5B86`, guard at `5B9C`, zeros speeds with absolute value
  below 43; otherwise it removes 42 toward zero. Airborne release coasts.
- The input-response checkpoint `6B55` precedes animation-delay selection.
  Shared collision at `738F` sets upward VY to 1 at a ceiling. Both side
  edges zero VX; a wall in the direction of motion reflects VX to `-VX/2`
  (signed truncation), nudging X one pixel in the new direction (zero uses
  +1). Y then X integrate with retained low-byte fractional carry. `741E`
  is the post-integration checkpoint, before visual/actor writeback.

The original runs gravity/landing before input. A newly requested jump is
therefore integrated at -848, without an intervening gravity add. The old
port's move-then-gravity shortcut happened to reproduce a clean jump arc but
failed to reproduce the actual velocity state, ceiling handling and landing
carry. It also cleared fractions at rest, which the original does not do.

## Runtime Capture

The capture uses a temporary copy of shipped assets at
`/tmp/lezac-player-walk-20260905`, a private Xvfb display and its own DOSBox
child. The existing launcher starts level 1 through the original menu. For
each route `braking`, `reversal`, `reaccelerate`, `air_coast`, `switch_coast`:

```sh
python3 tools/capture_original_player_walk.py \
  --run-dir /tmp/lezac-player-walk-20260905 \
  --route braking --out /tmp/lezac-player-walk-20260905/braking.txt \
  --approve-procmem --approve-runtime-instrumentation
```

Only the five normalized control bytes are exogenous gameplay writes.
Positions, velocities, fractions, timers, edge flags and frame parity are
not seeded. Three register/FLAGS-preserving trampolines pause before input,
after input response and after integration. They replay the displaced
instructions, use a monotonic sequence/release handshake, and filter the
shared post-integration stop to player behavior. Installation and restoration
stop only the owned child. Nine instruction windows and the empty scratch
area are checked. This is normalized-control injection, not a claim of
per-tick XTEST/keyboard-IRQ equivalence.

The runtime registers recorded in the fixtures are `CS=01A2`, `DS=0C44`,
`ES=3EA9`, `SS=18B3`, saved post-push `SP=3FA2`, `BP=3FEE`. Accordingly the
actual checkpoint IPs are `01A2:6813`, `01A2:6B55`, `01A2:741E`; Ghidra's
`1000` is not assumed to be the runtime segment. The capture translates the
far actor pointer using the observed segment base.

Each row preserves the 0x26-byte actor, its 8-byte visual row selected at
`DS:C21E + visualIndex*8`, and three 0x3A-byte local frames from `SS:BP-3A`
through `BP-1`. Actor offsets +6/+8 are signed VX/VY, +0A/+0C contain the
fractional low bytes, +14 is height bias and +15 is behavior. Local X/Y are
`BP-2C/-2E`, VX/VY are `BP-0C/-0E`, fractions are `BP-10/-11`; bottom/top/
left/right flags are `BP-21/-22/-23/-24`, step-left/right `BP-25/-26`.
Pre-input actor/visual bytes are from the prior committed state; the local
pre-input Y/VY can already include this update's gravity or landing snap.

| Route | Normalized Input Sequence | Samples |
| --- | --- | ---: |
| braking | right 20, idle 28, left 20, idle 28 | 96 |
| reversal | right 20, left 36, right 36, idle 28 | 120 |
| reaccelerate | right 20, idle 7, right 12, idle 28; mirrored left | 134 |
| air_coast | right 10, jump+right 1, idle 28 | 39 |
| switch_coast | right 20, both 8, idle 28 | 56 |

All five captures completed, with consecutive frame counters and explicit
completion rows. They are retained at `tests/fixtures/player_walk_original`.
Screenshots at samples 8, 20 and 32 show the last presented original frame
while integration is paused, not necessarily the just-computed post state.

Representative zero-based checkpoints:

- Braking sample 15 reaches X=138, VX=1024 from initial X=104/VX=0. Sample
  19 is X=154. The first release update is X=157, VX=982, fracX=214. After
  25 idle updates VX=0 at X=200, retaining fracX=200.
- Reacceleration produces 16 states at absolute VX=1050, eight in each
  direction. A post-add clamp at 1024 would fail this evidence.
- Air sample 10 is X/Y=120/164, VX/VY=704/-848, fractions=128/176. At sample
  13 ceiling contact changes VY to 1. Sample 22 reaches Y=170, VY=577; on
  the next update the original first snaps Y=168 and VY=0, then brakes VX
  from 704 to 662. Twelve idle airborne states retain nonzero horizontal
  speed. The landing does not clear fracY.

## Production Replay And Frames

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-player-walk-original \
  tests/fixtures/player_walk_original build-codex-tmp/player-walk-frames
python3 tools/capture_original_player_walk.py --self-check
```

`debugPlayerWalkOriginal` initializes each route from only its first original
state, then feeds the complete control stream through production
`updateWithControls`/`updatePlayer`. No per-tick position, velocity, fraction
or edge state is injected. Every prior committed state and every resulting
X/Y, VX/VY and both fractional carries must match. A separate assertion checks
all 445 input-response VX fields against the shared production helper.

The new CTests `player_walk_original` and `player_walk_capture_contract` pin
five cases, 445 full-motion states, 445 input responses, 16 overspeed states,
12 airborne coasting states and nine guarded instruction windows.

The optional harness writes 27 320x200 PPMs and a CSV manifest containing
route, sample, phase, original frame, player motion fields and framebuffer
hash. All 27 images were checked for nonuniform RGB data. The viewed contact
sheet `build-codex-tmp/player-walk-frames/inspection.png` includes braking,
reversal, airborne coasting and the weapon chord. Original screenshots
`braking_020.png`, `air_coast_020.png` and `switch_coast_032.png` were also
viewed: gameplay is visible, the jump is airborne and the selected weapon
changes. Final port frame hash: `74ef633833698f6c`. Different camera/animation
timing prevents a full-frame pixel-parity claim.

The existing collision regression now invokes the production player update,
checking wall reflection and floor snapping while preserving fractional
carry. The older timing fixture warms up through 16 ordinary right-input
updates before measuring its established 4-pixel cruising speed. The bomb
route predicts its braking distance using the recovered floor friction,
executes ordinary controls and stops before the weapon chord; no teleport,
velocity override, bomb repositioning or timer shortcut is added.

The first full run passed 421 cases, skipped the separate Xvfb UI test, and
failed only the old `object_collision_jump_live` fixture. It seeded the player
above a passable object at `(17,22)` (tile 0x60, word 1) and expected it to grant
an immediate jump despite a clear bottom edge. The corrected regression
rejects that airborne jump, then holds ordinary jump input while the player
falls naturally to the solid floor below and verifies a -848 launch there.
The obsolete object-support fallback is removed rather than restored to
satisfy a port-only assumption. The normal level-1 route remains covered.

Local validation: the 423-case run took 226.03 seconds, with 421 passed,
one UI skip and that sole outdated fixture failure. After the fixture-only
correction and removal of its unused fallback helpers, `ctest --rerun-failed`
passed in 0.97 seconds; the separate Xvfb UI case passed in 4.64 seconds.
Thus all 423 cases are covered, including the 445-state original replay and
the bomb/collapse routes. The build and `git diff --check` pass. The existing
unrelated debris-debug `snprintf` warning is unchanged. CI will repeat the
full Linux and Windows suites on the final commit before merge.

## Remaining Boundaries

These are five bounded level-1 streams, not all-level or unrestricted game
lockstep. Step-hop flags and hard-landing branches are instruction-backed but
not reached by this fixture bundle. The original hard-landing animation,
cooldown and presentation offsets still need a focused recovery. Player
sprite/animation cadence, placement/event ordering, interactive IRQ sampling,
damage and contact interactions remain separate fidelity questions. The
terminal clamp is directly byte-cited, but these traces do not reach it.
The overall game is not claimed fully reverse engineered by this recovery.
