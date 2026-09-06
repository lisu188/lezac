# Launch marker, allocation and player impulse

## Result

Actual original launch-pad input on levels 6 and 7 creates a visible 12x10
marker, using one-based sprite 91. It is not an invisible sentinel.
The C++ port now renders that marker in shared visual order, respects the
shared 30-actor capacity and applies the launch impulse after gravity.
Allocation failure still launches the player and requests sound. Fractional
player coordinates survive the impulse.

The level-7 comparison also exposed use of the wrong player sprite bank:
the original uses PROVA.SPR, including its player sprites. The port now uses
that bank for the level-7 player and launch marker. Before the player-bank
fix every compared level-7 viewport differed by 38 pixels.

## Provenance

The guarded executable SHA256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Both captures use a temporary original asset copy, private Xvfb and DOSBox.
The seeder reaches the requested level through the original results/intro
code by satisfying earlier objective counters. This is not a naturally
completed campaign.

Commands, run from the repository under WSL:

```sh
mkdir -p /tmp/lezac-launch-level6-v3
cp LEZAC.EXE *.DAT *.SPR *.PAL *.SCH *.SON *.MST *.CAR *.ZBG *.DOC /tmp/lezac-launch-level6-v3/
env PYTHONUNBUFFERED=1 python3 tools/capture_original_launch_marker.py \
  --level 6 --run-dir /tmp/lezac-launch-level6-v3 \
  --out build-codex-tmp/launch-level6-v3.txt \
  --approve-procmem --approve-runtime-instrumentation
```

Level 7 uses the same command with level/run/output changed to 7.
The capture tool guards 39 instruction windows and refuses existing output
paths, a non-temporary run directory or a different executable.

The capture hooks are main-CS `6064` (player actor entry), `6813` (normalized
input), `6B55` (input response), `7A57` (completed render) and `6932` (sound
latch return). Trampolines preserve registers and FLAGS, replay displaced
instructions and restore original bytes on successful completion. The sound
hook snapshots the accepted cursor/priority before host waiting; IRQ-driven
playback can advance the live cursor during later observation.

Actual registers are CS=`01a2`, DS=`0c44`, SS=`18b3`; render ES=`a000`.
Player input/response saved SP/BP=`3fa2/3fee`; render=`3fe4/3ffe`.
Helper-relative CS=`01ed` and DS=`0c8f` use an adjusted host-memory base and
must not be mislabeled as actual registers.

Promoted unmodified capture hashes:

- `tests/fixtures/launch_marker_level6_original.txt`:
  `7e24e0195ae87fae283b9d722eac48611e0c0636e786403952fabc069a5a22aa`
- `tests/fixtures/launch_marker_level7_original.txt`:
  `2490eea3cfd83f8601bafece71118230538d1a72c00d62ca0b69b1e89ad98946`

## Observed Rules

Each level has ten 12-update cases: pool counts 0, 29 and 30 at both frame
parities; Up+Down and idle controls; and two fractional-position cases.
P1 is placed once at the first real pad: level 6 `(105,42)`, player
`(840,320)`; level 7 `(38,43)`, player `(304,328)`. Fractional probes seed
X/Y carries `83/149`. The shared pool is seeded after its update pass with
stationary, off-camera mode-5 fillers. Spawners are disabled.

Normalized controls are supplied at `6813`. Cached collision flags, cached
tile bytes and the shipped map are NOT forced to make the gate pass. Later
player and marker states run continuously with idle controls. There is no
per-tick position, velocity, marker or map restoration.

- Original cached below-left tile is `27`; the overhead flag is zero.
  Up+Down cancels both inputs, and idle does not launch.
- `691F` assigns VY=`-2000` after gravity. `6932` captures accepted sound
  cursor `0035`, priority `05`, including pool-30 failures.
- Constructor `2F9F` appends only below the 30-slot limit. The successful
  marker has kind `0b`, mode `05`, timer `05`, velocity `(0,-200)`, zero
  fractions, visual position `(playerX+4,playerY+13)` and hotspot 6.
- Descriptor `DS:C322 + 91*4` is `0c0a994d` on level 6 and `0c0ad351`
  on level 7. Both refer to sprite 90 of their respective decoded banks;
  the marker pixels are identical. Descriptor zero is the zero row.
- The marker decrements on odd game frames and integrates signed 8.8 motion.
  Even-frame creation survives eight subsequent updates and retires on the
  ninth; odd-frame creation retires on the tenth.
- Pool 29 accepts the marker; pool 30 rejects it without changing the
  launch velocity or sound behavior. Player carry is not reset by launch.

## Replay and Visual Scope

`--debug-launch-marker-original FIXTURE [OUT_DIR]` drives production
`updateWithControls`, shared actor updates and rendering. It compares player
motion/carry/animation continuity, input response, sound request, constructor
result, actor/visual counts, filler states, marker states and rendered player
coordinates/sprite. It checks both full lifetimes and camera values.

The two fixtures contain 240 views and 11,381,760 indexed pixels. Their
normalized RGB comparisons have zero differences. There are 114 visible
marker checkpoints across both levels, checked at both input-response and
render boundaries (228 state comparisons).

The observed original map and randomly generated backdrop are environmental
inputs to this focused replay. The backdrop's nonrandom gradient is checked
against the port before its star region is adopted. Palette colors are
normalized through BOMPAL/the recovered backdrop ramp, not the live VGA DAC.
This is a controlled launch comparison, NOT natural-route, complete level,
HUD, background-RNG-phase, two-player or whole-game pixel parity.

`check_launch_marker_fixture.py` pins capture hashes, independently verifies
every indexed-view SHA256, tests LF/CRLF and rejects two truncations and
63 mutations per fixture.
The autoplayer also compares an otherwise identical rendered frame with and
without the marker; player movement alone can no longer satisfy visibility.

Earlier v1 probes observed the post-IRQ sound cursor advance to `0036` in
some cases. The v2/v3 hook captures the immediate accepted pair instead.
A level-7 v2 run timed out entering gameplay while WSL was failing with I/O
errors. It was not promoted. After a user-approved WSL restart, both v3
captures completed successfully. Old zero-row evidence remains in its
historical fixture/report with an explicit supersession notice.

Final validation after the production changes:

- Linux build and all 487 CTests pass in 100.14 seconds. The full output is
  `build-codex-tmp/launch-marker-final-tests.log`.
- Windows Release build succeeds; the ten launch-marker, launch-pad and
  boss-fight frame tests pass in 41.31 seconds.

## Boss Screenshots

The user-requested `boss_level7_fight` C++ frame sequence moves from the
original spawn, throws bombs via normal input events and captures the
encounter through tick 220. It does not teleport the player or force boss
damage. The inspected tick-140 frame shows the boss and a thrown bomb.

The separate original `build-codex-tmp/capture_boss_encounter.py` run uses
the same temporary-copy level seeder, then attempts Left and N through
xdotool. Those injected keys did not change player position or create bombs;
this is documented as failed key injection, not original control behavior.
The boss naturally approached from X=276 to X=822 while P1 stayed at X=840.
The final screenshot (original frame 919) shows the encounter, with energy
falling from 100 to 99. Original/C++ screenshots have different times and
cameras and are not presented as an aligned comparison.
