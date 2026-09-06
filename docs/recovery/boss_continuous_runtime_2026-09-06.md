# Continuous Boss Runtime and Visual Order

## Result

Two original level-7 captures now replay 1,200 continuous production updates:
8,400 boss-actor states, 7,200 motion-link states, 92 pickup-effect states and
60 full-width views (2,845,440 normalized pixels) match. The closer capture
includes player contact damage from energy 100 to 15 without forcing damage.

This exposed and fixes three production errors:

- The head used a private counter. Original `1000:5E59` gates RNG on the
  shared 16-bit `DS:78C2` clock. The first replay diverged at frame 116,
  when the original drew movement values and the port did not. The port now
  uses that shared clock, including its 65535-to-0 rollover.
- GRAN.MST sprite bytes and the boss animation ranges are one-based visual
  descriptors, not zero-based decoded sprite indexes. The live constructor
  now subtracts one, initializes the cursor from the animation range, and
  disables animation for static segments. The raw animation table remains
  unchanged; only its consumer converts the index convention.
- Boss actor order is visual slots `6,7,8,5,4,3,2`, whereas the original
  driver draws increasing visual slots. The port previously used update
  order for both. Boss actors now retain separate stable visual-order keys.
  Correcting draw order removed 3,941 differing pixels in the near capture;
  the actor-update order is unchanged.

The original head now appears with the proper surrounding arm/hand frames.
An independent ImageMagick comparison of the original and C++ near-case
sample-0 PPMs reports `AE=0`.

## Capture Provenance

Guarded original executable SHA256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

Both runs use a temporary asset copy, private Xvfb and DOSBox. The existing
level seeder satisfies earlier objective counters, then traverses the
original results/intro routines to reach level 7. This is not natural
campaign completion. Commands from the repository under WSL:

```sh
mkdir -p /tmp/lezac-boss-continuous-v1
cp LEZAC.EXE *.DAT *.SPR *.PAL *.SCH *.SON *.MST *.CAR *.ZBG *.DOC /tmp/lezac-boss-continuous-v1/
env PYTHONUNBUFFERED=1 python3 tools/capture_original_boss_continuous.py \
  --run-dir /tmp/lezac-boss-continuous-v1 \
  --out build-codex-tmp/boss-continuous-v1.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The near capture uses `/tmp/lezac-boss-continuous-v3`, output
`build-codex-tmp/boss-continuous-v3.txt` and `--near-encounter`. That option
was added after v1; the v1 trace is preserved without rewriting its header.
The near run waits 258 original idle updates for the head to reach
`(720,312)`. No boss position is forced during that approach.

Hooks, in main-CS coordinates:

- `7EBB`: before the original link-update gate and non-player actor pass.
- `6813`: normalized active-player input, after collision/animation setup.
- `7A57`: completed playfield rendering.

Trampolines preserve registers/FLAGS, execute the displaced instruction and
restore original code bytes after successful completion. The capture checks
34 instruction windows and the full executable hash. Actual registers are
CS=`01a2`, DS=`0c44`, SS=`18b3`; pre-pass ES=`0c44`, render ES=`a000`.
Pre-pass/render saved SP/BP are `3fe4/3ffe`; input uses `3fa2/3fee`.
Helper-relative CS=`01ed` and DS=`0c8f` use an adjusted host-memory base,
not the actual runtime register values.

At each case boundary, the same observed actor/link/player state and map are
restored once, RNG is set to `12345678`, the frame clock is selected, lives
and energy are initialized, and spawners/previous effect queues are disabled.
The first capture's observed head is `(255,244)`; the near capture's is
`(720,312)`. P1 starts at the original `(840,328)` in both.

Each capture has three 200-update cases:

- `idle_phase`: frame 100, idle controls throughout.
- `approach`: frame 101, Left for 100 updates, Right for 40, then idle.
- `clock_wrap`: frame 65520, idle controls throughout.

Normalized input is supplied at `6813`. Subsequent actor/link/player state,
velocities, carries, RNG and map changes run continuously without per-tick
restoration. The movement route naturally collects pickups and creates
effects; the replay checks them as part of the shared actor pool.

Promoted, unchanged capture hashes:

- `tests/fixtures/boss_continuous_original_level7.txt`:
  `feed00ccbe888044caa5bcd5c00a66db5edf5ec425feacb6a2766591a53b066a`
- `tests/fixtures/boss_continuous_near_original_level7.txt`:
  `01e2f3a9ba39081afabbe2efc4d109f023459f84f48c96093c0db9db3bf3c0ce`

## Replay Scope

`--debug-boss-continuous-original FIXTURE [OUT_DIR]` calls production
`updateWithControls`. It checks all seven boss actors, six link outputs and
phases, player motion/animation/energy/lives, shared pool counts, spawned
pickup effects, RNG, map deltas and camera values. The optional output
directory contains 30 PPMs and a state/pixel-difference manifest.

The original observed map and random backdrop are environmental inputs.
The nonrandom backdrop gradient is checked before adopting the star region.
The word plane is retained as capture provenance, not claimed as a separate
runtime writeback comparison. Colors are normalized with BOMPAL/the recovered
backdrop ramp, not sampled from the live DAC. No HUD or complete screen
comparison is claimed.

`check_boss_continuous_fixture.py` pins both capture hashes, independently
checks the 30 indexed-view hashes per fixture, tests LF/CRLF, and challenges
the replay with truncations and field/pixel mutations. The original files
are never regenerated from C++ results.

Both fixture guards reject 86 mutations and two truncations. The 19 focused
Linux boss/visual-order tests pass in 72.17 seconds.

Final validation: the Linux build and all 492 CTests pass in 158.00 seconds
(`build-codex-tmp/boss-continuous-full-tests.log`). The Windows Release build
and all 19 focused boss/visual-order tests pass in 74.92 seconds.

## Remaining Work

The old `boss_lockstep_evidence` diagnostic restores position, velocity,
fractions, RNG and timer before each transition. It is useful single-step
evidence, but did not prove continuous production behavior. Its historical
fixture is unchanged; the new replays close that specific continuity gap.

The near v2 capture stopped after sample 179 because the original skipped
the active-player input hook. This is consistent with entering death/state-2,
but that failed run did not retain a final raw state and is not promoted.
The capture harness now handles a missing active-input hook and persists
partial traces. The successful v3 capture stayed alive through its window;
the diagnostic deliberately rejects dead-player states rather than claiming
unverified reentry parity.

Boss flame damage, the complete defeat conversion/explosion chain, longer
natural combat, player death/reentry, two-player boss interactions and
arbitrary actor/link deletion remain open. In particular, current boss-debris
expiry still creates compatibility flashes instead of a verified complete
original bomb lifecycle. This batch does not make the port functionally
complete or establish whole-game fidelity.
