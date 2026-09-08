# Largest-Bomb Boss Combat And Player Death

## Scope

Two original DOSBox captures contain two 180-update cases each, at clocks
100 and 101. At each case boundary they restore the observed environment,
boss, links, player and RNG, set head HP/lives to 0/1, and place one
zero-fuse kind-16 bomb at head visual `(x+16,y+8)`, with one-based descriptor
61 (decoded index 60). Subsequent updates are continuous and idle. No boss
position or per-tick state is forced, and player damage remains enabled.

The distant capture starts the head at `(305,311)`, without warmup. The near
capture waits 184 natural idle updates and starts at `(770,275)`. These are
controlled low-HP boss encounters, not full-health natural victories.

## Damage Evidence

The original head scans every second column of its 5x4 collision-space box
before motion integration. At `1000:5F5F` (file `66CF`), the last sampled
flame cell is looked up by `1000:3A56` (file `41C6`), scanning flame slots in
reverse order. If `DS:78D5+slot` exceeds 1, the entire sampled-cell count is
doubled. It is not multiplied by the mass byte, which is 221 here.

The distant cases each have six damaged updates and end at HP 220. The near
cases have nine/eight damaged updates and end at HP 214/218. All four cases
lose one head life, with byte-wrap HP, and retain an active boss. In total,
29 damaged updates exercise the doubled branch. The existing production
mass rule matches; the new evidence extends it beyond synthetic flame cells.

## Player Corrections

The near replay originally stopped at sample 21 because its player checks
only accepted active behavior 0. Extending those checks exposed two real
production differences:

- At sample 22, the original player descriptor is decoded index 74 while
  the port still held index 0. Death helper `1000:30A3` initializes animation
  74..79 but leaves the visible descriptor alone. Subsequent actor animation
  advances latch `cursor-1` from the current level's bank. Gameplay now uses
  that latch, including PROVA on level 7, instead of the provisional
  BOMOMIMK row-rebase rendering. The explicit historical row/cursor preview
  remains a debug-only tool, not a gameplay claim.
- At sample 81, the original player is at `(840,328)` while the port stayed
  at `(848,328)`. At `1000:7D11`, countdown expiry calls the start-marker
  locator `1000:056B`, clears the idle byte and preserves motion/fractions.
  The driver changes global player state to 2 at `7D78` and selects the
  descriptor offset from `DS:C3C0` at `7D94` (decoded index 38). Waiting
  players skip the actor/animation pass through the `7F40` state gate.
  The port now places and draws the waiting player at that boundary and
  freezes the death animation until reentry.

In both near cases, death starts at sample 21, after the input hook. Samples
22..80 run dying motion without an input hook; 81..179 wait at the start
marker with global state 2 and lives 98. There are 120 dying and 198 waiting
states across the two cases. The head and all six links continue throughout.

The replay compares actor energy separately from cached `DS:79EC`. Death
helper `30A3` leaves the remaining objective count in scratch `DS:2074`, and
the caller copies it to the cache at `7FC2`; here the death-frame cache is 1
while actor energy is already 100. This comparison does not implement or
claim complete HUD fidelity.

## Provenance And Replay

Executable SHA256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The MZ image starts at file `0x770`. Main-CS hooks are `7EBB`, `6813` and
`7A57`; actual runtime CS/DS/SS are `01A2/0C44/18B3`. Every case/tick keeps
its register block and raw actor/visual/link/flame records. Table and saved
register details follow [the nonfatal capture](boss_impact_runtime_2026-09-08.md).

Both captures used the ignored prototype
`build-codex-tmp/capture_boss_mass_probe.py --nonfatal`, with
`--approve-procmem --approve-runtime-instrumentation`, temporary asset copies
`/tmp/lezac-boss-mass-{offscreen,near}-v1`, output
`build-codex-tmp/boss-mass-{offscreen,near}-v1.txt`, and `--near-encounter`
for the near run. Both enforced `SDL_AUDIODRIVER=dummy` and guarded the full
EXE hash plus 37 instruction windows. The promoted mode preserves the
captured contract and adds eight focused mass/death windows, for 45 total:

```sh
env SDL_AUDIODRIVER=dummy PYTHONUNBUFFERED=1 \
  python3 tools/capture_original_boss_defeat.py --mass --near-encounter \
  --run-dir /tmp/lezac-boss-mass-fresh --out /tmp/lezac-boss-mass-fresh.txt \
  --approve-procmem --approve-runtime-instrumentation
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-boss-mass-original tests/fixtures/boss_mass_near_original_level7.txt \
  /tmp/lezac-boss-mass-cpp
```

The capture command requires a fresh temporary asset copy, as documented in
AGENTS.md. Fixture SHA256 values are pinned after LF normalization:

- `boss_mass_original_level7.txt`:
  `bc0bc4a06a5a9124a371af1a34facfc6360cfdb1805adfbac6282d928e7f4905`
- `boss_mass_near_original_level7.txt`:
  `ab87a9f1afaa102e74e10bef648bf08e82af25a2786e42f96a2d5a9b0935d37e`

The production `updateWithControls` replay matches all 720 updates: 5,040
boss states, 4,320 link states, 1,324 effect states, 5,928 flame states and
60 views / 2,845,440 normalized pixels. It does not restore actors, RNG,
links or maps between ticks. Original and C++ near frames 20, 39 and 99 were
visually inspected and independently compared with ImageMagick (AE=0).
The view is the 312x152 playfield, with a normalized palette, not VGA DAC
or full HUD output.

Windows Release passed all 36 selected boss-mass, death and state-2 tests
in 248.54 seconds. The fixture guards accept LF/CRLF and reject two
truncations plus 148 distant / 238 near mutations, including seeded weapon,
death countdown, cached versus actor energy, descriptors, missing input,
waiting placement and frozen animation. Five new tests are registered in
CTest. Full regression results are recorded with the delivery PR.

## Remaining Limits

No reentry key is pressed. The port's bounded reentry timer represents the
observed waiting countdown through `raw_word = timer + 1 - kReentryTicks`
(modulo 65536); the original continues decrementing its raw actor word.
These 99 waiting updates per case do not validate the port's longer-wait
restart timeout, a full 16-bit wait wrap, zero-life underflow, unwinnable
levels, or actual input-driven reentry. Those older lifecycle approximations
remain open and must be checked against fresh original traces.

Mixed flame masses/overlapping slots, every weapon geometry, natural
full-health victory, two-player combat and whole-game fidelity are also
unproven. Initial map words/backdrop are case seeds, not per-tick writeback
oracles. Unmapped raw bytes are provenance only. `whole_game_parity=0`.
