# Continuous Nonfatal Boss Hits

## Scope

Two original DOSBox captures contain two 180-update cases each, at shared
clocks 100 and 101. They restore the observed boss, links, player, map and
RNG only at the case boundary, seed head HP 0 and lives 1, and place one
zero-fuse small bomb at head visual `(x+16,y+8)`. All subsequent flame damage,
animation, motion, contact, map changes and effects run continuously. Inputs
are idle; neither capture forces the boss position.

The initial-position capture starts the head at `(270,255)`. The near capture
waits 273 natural updates and starts at `(803,276)`. These are controlled
nonfatal-hit scenes, not natural full-health boss victories.

## Recovered Rule

The original link routine `1000:432A` reads the visual table `DS:C21E`, not
the actor caller's collision-space Y. The spring Y reads at `1000:43E8`
(file `4B58`) use self visual Y from `DS:C220+8*self`, then target visual Y
from `ES:[DI+2]`. The orbital branch reads target visual Y at `1000:4503`
(file `4C73`). The port now includes signed hotspots for both spring inputs
and the orbital anchor.

Before correction, the near replay first diverged at `hit_even` sample 3:
link 0 was `(120,280)` instead of `(120,220)`. The signed hotspot became -4
on the preceding hit; omitting it added `4*15 = 60` to the spring force.
Both complete captures match after this production-code correction.

At sample 2, both scenes change HP `0 -> 254` and lives `1 -> 0`, without
defeat. The near cases finish damage at HP 249 after five damaged updates
each; the initial-position cases reach HP 243 after six. The head stays
active for the remainder of every case. The visible damage descriptor is
one-based PROVA `0x2F`, with signed hotspot -4 from `1000:5A75`. Ordinary
animation continues; it does not restore the hotspot when its payload next
advances. The replay compares those animation bytes and descriptors on every
update, not only the selected screenshots.

## Capture Provenance

Original executable SHA256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The MZ image starts at file `0x770`. Hooks are main-CS anchors `7EBB`
(pre-link/actor pass), `6813` (normalized player input), and `7A57`
(completed playfield). Actual captured CS/DS/SS are `01A2/0C44/18B3`, so
the corresponding runtime hooks are `01A2:7EBB`, `01A2:6813`, and
`01A2:7A57`. ES is `0C44` at pre-pass, `A000` at render, and an observed
heap segment at input. Saved SP/BP are `3FE4/3FFE` at pre-pass/render and
`3FA2/3FEE` at input. Every case/tick retains its register block.

Tables are the same mapped actor, visual, link, flame, mass, RNG and clock
tables listed in [the defeat evidence](boss_defeat_runtime_2026-09-06.md).

The initial-position run used this command in WSL from the repository:

```sh
mkdir -p /tmp/lezac-boss-impact-offscreen-v1
cp LEZAC.EXE *.DAT *.SPR *.PAL *.SCH *.SON *.MST *.CAR *.ZBG *.DOC /tmp/lezac-boss-impact-offscreen-v1/
env SDL_AUDIODRIVER=dummy PYTHONUNBUFFERED=1 \
  python3 tools/capture_original_boss_defeat.py --nonfatal \
  --run-dir /tmp/lezac-boss-impact-offscreen-v1 \
  --out build-codex-tmp/boss-impact-offscreen-v1.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The near run used `/tmp/lezac-boss-impact-near-v2`, output
`build-codex-tmp/boss-impact-near-v2.txt`, and the prototype
`build-codex-tmp/capture_boss_impact_probe.py --near-encounter` with the same
approval flags and dummy audio. The promoted `--nonfatal` mode preserves
its state capture, case seeds, input and sampling contract. It additionally
guards the three instruction windows above, for 37 guarded windows total.
To repeat a near capture, add `--near-encounter` to the promoted command.
Always use fresh temporary/output paths. The launcher now forces dummy SDL
audio for its child sessions. An earlier audible near attempt was stopped
before capture; it is not a fixture.

Immutable LF-normalized fixture SHA256 values:

- `tests/fixtures/boss_impact_original_level7.txt`:
  `dfdf3475a192d82bd3d1bf75ed0b1282bf26e1ae0a8ae180822dbb621ed03a23`
- `tests/fixtures/boss_impact_near_original_level7.txt`:
  `0ac513b52f734875a4ed3944c6fb08f590e1f3825db23821a71ca6f8c2d486e9`

## Validation

`--debug-boss-impact-original FIXTURE [OUTPUT_DIRECTORY]` calls production
`updateWithControls`, without per-tick actor, link, RNG or map restoration.
Each fixture matches 2,520 boss states, 2,160 link states, 185 effect states,
112 flame states, all 360 player/input/RNG/map checkpoints, and 30 views /
1,422,720 normalized pixels. Together: 720 updates, 22 damaged updates,
four life losses, 5,040 boss states, 4,320 link states and 2,845,440 pixels.

Original and C++ near samples 20 and 99 were visually inspected side by side
and independently compared with ImageMagick: AE=0 for both. They show the
same surviving boss, player and geometry, during and after the explosion
effects. The playfield is cropped
to 312x152 and palette-normalized, not an actual VGA DAC/HUD comparison.

The fixture guard accepts LF/CRLF, pins indexed view hashes, and rejects
two truncations and 129 mutations per fixture, including post-hit links, HP/lives, hotspot,
animation, flames, and seed/header contradictions. Both replays, both guards
and the capture self-check are registered in CTest.

Windows Release compiled and all 53 selected boss, GRAN model, visual-order,
bomb and flame checks passed in 220.09 seconds, including both new fixture
guards. An initial Linux guard attempt overlapped a relink and failed with
`ETXTBSY`; that invocation is not counted as validation.
After linking completed, the full Linux suite passed all 502 tests in
204.49 seconds, including both 129-mutation impact guards.

## Still Open

Full-health natural victory, all flame-mass branches, player death/reentry
during boss combat, two-player combat, actual VGA/HUD parity and whole-game
fidelity remain unproven. These captures test a small-bomb hit from seeded
HP/lives; they do not establish every reachable combat interaction. The
word plane is an initial environmental seed, not a per-tick writeback oracle.
Raw globals and unmapped actor/flame bytes remain provenance only.
`whole_game_parity=0` is unchanged.
