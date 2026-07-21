# Recovery Status

Last reviewed: 2026-07-19
Branch: `main`
Baseline: `origin/main`

## Port Completion

The C++ port is functionally complete. Every recovered gameplay, data, UI,
and sound subsystem of `LEZAC.EXE` has a C++ implementation with
deterministic validation coverage, and the full CTest suite passes on a
clean Linux host (377/377 after this iteration's additions). The new
`--debug-port-completion-status` diagnostic declares that state as
machine-checkable output: 23 implemented subsystems with their validation
entry points and the 12 open original-evidence follow-ups, reported with
`port_functionally_complete=1` and `original_fidelity_claim=0`.
`tools/check_port_completion_status.py` plus
`docs/recovery/port_completion_status.md` keep the completion claim, the
docs, and the CTest expectation aligned. The "Remaining Top Gaps" below are
fidelity verification items against the original runtime — they require
DOSBox/DOSBox-debug/process-memory evidence hosts and stay `visual_claim=0`
under the existing guardrails; they are not missing port functionality.

## Completed This Iteration

- **Recovered and reimplemented the original level-completion banner sequence
  (routine at file 0x24d3), pixel-verified against a live original
  completion.** Seeded a real completion in DOSBox while capturing frames and
  DS snapshots, then decoded the routine from the disassembly. The original
  types four centred banner lines over the live gameplay frame at the shared
  81ms/char delay: "livello completato" (large font, 11px cells, white 31 on
  grey-25 shadow at y=60), "bonus distruzione; N" (small font, 9px cells,
  green 244 on dark-green 241 at y=81, N = destruction counter x10),
  "bomba bonus" (green 244 on grey 25 at y=99) and one
  "giocatore I   B" line per active player (white 31 on magenta 13 from
  y=120, +11 per player); the stored strings render ';' as ':' and the
  English variants live in the language table (file 0xCB1A/0xCA1A/0xC91A;
  "bomba bonus" is an inline code constant shared by both languages). The
  bomb bonus B reads the per-player 4-byte record at DS:0x1B69+4i as
  medium*100 + big*500 + super*2000 (smalls score nothing) -- confirmed live:
  inventory 200/20/6/0 displayed and awarded exactly 5000, matching the
  decode byte-for-byte. The sequence opens with sound cursor 0x3d priority
  10 after a 500ms pause, counts the award into the score at 15ms ticks
  (Random(4)>2 requesting sound cursor 0x21 per tick), pauses 200ms per
  player, then blocks on ReadKey before incrementing the level byte. The
  port now runs this sequence for interactive play (a key finishes the
  current line's typing, exactly like the original renderer), while the
  deterministic test/autoplayer path keeps the timed advance. Pixel diff of
  the port's banner against the original capture: every port text pixel
  matches on all four lines (the only residuals are world sprites the
  colour filter picks up). All banner colours are BOMPAL entries
  (13/25/31/241/244 match the measured DAC values exactly). New
  `--debug-level-outro` diagnostic + `level_outro` ctest pin the sequence,
  bonus arithmetic, award total and key advance.

- **Verified the recovered camera/sky/world rendering against original
  captures of all seven level starts and extended the sky table to band 36.**
  The completion-seed technique advanced the original through every level in
  one DOSBox run, capturing each start frame plus a DS snapshot. Findings:
  (1) the rest-pose camera constants (viewW/2-4, viewH/2+4) predict the
  recovered camera exactly on levels 1,3,4,5,7 (anchor word `DS:0xC21E`
  matches the port's portal spawn on every level); levels 2 and 6 were caught
  mid-pan -- the original's camera moves toward its target at a limited pan
  speed after a level starts (and L6's sky was drawn one 8px camera step
  ahead of its tiles in the same captured frame), which is the same dynamic
  behind the walking-lookahead observation; static rest frames are
  unaffected. (2) The banded parallax sky model holds globally: levels
  1,3,7 diff at zero bad rows, and the deeper level-2/level-5 views extended
  the measured DAC table from 30 to 37 entries (band 36 = 174,93,8); the
  same global table fits levels 1,2,3,4,6,7. (3) All remaining "solid tile"
  differences on levels 2-7 are the fading level-transition banner text
  (LIVELLO COMPLETATO / BOMBA BONUS / GIOCATORE 1) plus live sprites -- no
  world-rendering divergence on any level. Follow-ups: level 5 paints
  starfield/water backdrop regions over its lower sky; the camera pan/
  lookahead dynamics need the `DS:0xC21E` consumer routine decoded.

- **Recovered the exact gameplay backdrop, view frames, camera constants and
  the original left/right two-player split, all diffed to the pixel floor
  against in-container DOSBox captures.** Fresh original level-1 captures
  (spawn, walking, mid-jump, memory-synchronised stops) drove four recoveries.
  (1) View frames: every original gameplay viewport is framed — a 1px white
  outline plus 3px grey border in single-player (viewport x4..315, y4..155),
  and in two-player a white/grey-framed left view beside a dark-red/light-red
  framed right view (viewports 152x152 at x4/x164); the port drew no frame at
  all and used a top/bottom split. Rebuilt both modes; the frame regions now
  diff at 0 mismatched pixels. (2) Camera: cross-correlating capture viewports
  against the exported level tile map (`--export-level-world`) recovered the
  rest-pose camera anchor (viewW/2-4, viewH/2+4) — confirmed exactly by the
  two-player cams (32/208 for anchors 104/280) and every single-player capture
  (camY 88) — and `/proc` memory reads found the original player-anchor word
  `DS:0xC21E` (104 at spawn, matching the port's portal data exactly). After
  the fix all 23,234 solid-tile pixels of the spawn frame match the original
  exactly. (3) Sky: the backdrop is not a linear ramp but 4px-tall uniform
  bands with a slow vertical parallax — band = (viewportRow + camY/8 - 8)/4 —
  verified with zero mismatching rows across six captures at camY 66..88, with
  a 30-entry DAC colour table measured from the captures (the colours are not
  in BOMPAL.PAL; the original programs them separately). Whole-frame level-1
  mismatch fell 30371 → 1000 (98.4% pixel-exact; the residual is the moving
  player/monster sprites plus the known 4px HUD floor). (4) Two-player HUD:
  the original doubles the single-player column (player 2's copy at +180px:
  energy track x180..281, score panel x180..267, bomb box x299..318, lives at
  x180..196) around the shared centre objective panel; rebuilt via
  `drawPlayerHudColumn`, HUD diff now at the 8px sprite floor, two-player
  whole-frame mismatch 11203 → 3286 (rest is live-sprite state). Player-2
  spawns from portal data (280,168) exactly like the original. Added
  `--capture-two-player-frame` and retired the old placeholder `drawHudBand`;
  `two_player_panel_artwork_frame_compare` is resolved (open items 12 → 11).
  Remaining known dynamics gap: the original applies a facing-direction
  camera lookahead while walking (stationary-after-walking-right rest anchor
  sits at viewport 151 vs 156 spawn); static frames are unaffected.

- **Corrected the main-menu text rendering to match the original title
  screen.** Captured the original menu (DOSBox title screen after the
  attract marquee settles) and diffed it against the port's overlaid menu
  options. The SFONLEF.ZBG art was already pixel-perfect (0 mismatch in every
  text-free region, including the baked-in "Stefano Zanobi" credit), so the
  whole divergence was the seven option lines. Fixed four measured errors:
  (1) the strings dropped the trailing period each line carries in the
  original (LEZAC.EXE 0xb92a / 0xc679 -- the original's contiguous glyph set
  renders a source ':' as a period, so every line ends "... GIOCATORE.");
  (2) the text was drawn in the font's native gold instead of the original's
  white glyph with a blue (0,0,255) shadow; (3) it sat ~14px too high (the
  original places the first line at y74 on a 10px pitch); (4) centring now
  uses the true variable-glyph pixel width. Added a `nativePalette` font path
  and a `--capture-menu-frame` PPM dump (with a CMake smoke test) so the menu
  can be diffed like the level frames. Menu text mismatch dropped from 7575 to
  5934 px, the remainder being sub-pixel anti-aliasing where the white text
  overlaps the busy title art. Full suite green (378/378).

- **Rebuilt the single-player HUD energy bar / score panel to pixel parity.**
  Captured a fresh full-energy original level-1 gameplay frame (DOSBox under
  `xvfb-run`, dismissing the `PREPARATI PER IL LIVELLO` splash) and ran a
  quantitative per-pixel diff of the whole HUD band against the port. The
  left HUD was structurally wrong in five measured ways, all now fixed:
  (1) the energy bar was a bare 1px yellow line -- the original is a 102x3
  grey-framed (182,182,182) track with the yellow (255,255,85) fill on the
  middle row (full energy = inner 100px, x1..100);
  (2) the score panel had only a cyan left edge -- the original frames the
  blue (0,24,219) box with a 1px cyan (0,170,170) border on all four sides,
  spanning x0..87 / y172..188 (the port drew it 3px too tall);
  (3) the green score digit sat 1px too low;
  (4) the life figures overlapped the over-tall panel and were mispositioned
  (now `i*9` spacing, one row lower, starting at x0);
  (5) the bomb-selector well was (28,28,28) but the original is (32,32,32).
  Also capped the 3px grey rule with the original's white end pixels.
  Result: the full HUD band collapsed from 220 mismatched pixels to 4, and
  those 4 are the bomb fuse-spark at x128-129 -- verified to be a live
  animation (the red shades flicker between consecutive original frames while
  the bomb body stays byte-identical), so no static render can lock its phase.
  Full suite green (377/377).

- **Removed latent player steering from ground walkers.** Behavior 4
  legitimately targets the selected player, while behaviors 1-3 spawn with a
  fixed heading and reverse only at walls and floor edges. The port's zero-
  velocity fallback could steer a walker toward a player even though normal
  spawns made that path dormant; walkers now default to their positive spawn
  heading when velocity is zero.

- **Corrected and strengthened the boss-head control mapping.** The
  behavior-6 caller at `1000:6053` builds both active players' X/Y deltas,
  selects the nearest by Manhattan distance at `1000:6500..654D`, then calls
  `1000:5CB0` with its frame pointer. The head routine therefore reads the
  selected player's X delta indirectly through caller local `[BP-4]`; it does
  seek that player horizontally. The port preserves that targeting and now
  uses the original Manhattan selector. The newly recovered roar remains: on
  `DS:78C2 % 29 == 0`, the original draws `Random(100)`, requests cursor
  `0x69` at priority 4 when the result exceeds 70 on an even tick, then draws
  `Random(800)` for signed speed and conditionally `Random(1500)` for the
  grounded impulse (`1000:5E59..5EF4`). The level-7 autoplayer now proves
  left/right targeting, a two-player case where Manhattan and Euclidean
  selection disagree, roar cursor/priority, and roar-speed-jump RNG order.

- **Corrected the RNG to the original's Turbo Pascal generator (bit-exact).**
  The port's `randomRangeValue` used the Numerical Recipes LCG
  (`seed*1664525 + 1013904223`), which is the wrong algorithm. Disassembling
  the shipped runtime-library `Random` at `0x920:0x13a8` shows the original is
  Borland Turbo Pascal's generator: `RandSeed = RandSeed*0x08088405 + 1`
  (multiplier low word `0x8405` at `CS:0x142d`, increment 1), extracting
  `Random(L) = (RandSeed >> 16) mod L` (RandSeed at `DS:0x1afe`). The port
  already used the `>>16 mod L` extraction but the wrong LCG constants, so
  every RNG-driven decision (monster spawner HP, behavior rolls, the boss head
  brain's velocity/timer draws) was drawn from a different stream. Switching to
  `0x08088405`/`+1` makes the generator bit-identical to the original; the new
  `--debug-turbo-random` diagnostic (CTest `turbo_random`) pins the output
  against an independently-computed Turbo Pascal reference
  (`Random(100)` from seed 0 -> `0,56,29,76,86,17,85,3,95,96,74,16`) and
  pins the shipped entry/advance byte windows at `0x920:13A8`/`13F7`, the
  `CS:142D` multiplier word, and `DS:1AFE` seed storage. All existing
  determinism/range tests still pass unchanged, and this is the keystone that
  makes a deterministic lockstep comparison of the RNG-driven AI against the
  original feasible.

- **Confirmed the level-7 GRAN.MST boss against ORIGINAL RUNTIME (was
  static-only).** Using the newly unblocked level-7 access, the original boss
  was captured live under DOSBox and its runtime tables read from process
  memory: the actor table `DS:0x1BAE` (8 slots x 0x26 bytes) and the motion
  link table `DS:0x79EA` (8 slots x 0x10 bytes), while the head brain at
  1000:5CB0 executed each frame. Parsing the captured tables shows exactly one
  head (kind `0x1e`, behavior `6`, visual 6, hit-box 5x4, one life) and six
  segments (kind `0x1f`, behavior `5`, visuals 2, 3, 4, 5, 7, and 8), with six
  one-based segment motion links all targeting visual 6. The allocator count
  is 9 and the GRAN visual rebase is `+2`, matching the port element for
  element. The evidence is committed as
  `tests/fixtures/boss_runtime_original_level7.txt` and validated by the new
  `--debug-boss-runtime-evidence` diagnostic (CTest `boss_runtime_evidence`,
  `boss_structure_confirmed=1`), which decodes the port's boss and asserts the
  fixed actor/link slots, kinds, behaviors, visual mapping, actor/link counts,
  and head hit-box against the captured original runtime
  (`boss_structure_confirmed=1 boss_placement_confirmed=1
  boss_segment_motion_confirmed=1`). The colorful
  lower-right cluster in the natural level-7 frame is static level artwork;
  the boss starts outside the natural viewport in both builds, so exact
  frame-by-frame boss motion remains unpromoted.

  Beyond structure, the segment MOTION PHYSICS is confirmed: the runtime link
  table (`DS:0x79EA`) is initialised from the GRAN.MST link records, and all
  six segment links match the port's decoded `bossLinks_` element-for-element
  on `gain`, `mode`, `radiusX`, `radiusY`, `offX`, `offY`, and `biasY`
  (`link_params_matched=6/6`), with the same two-spring / four-orbit split
  (`mode==0xff` orbit). The per-frame `phase`/`outX`/`outY` are
  runtime-advanced and excluded; target/self visual IDs are independently
  checked against the shared `+2` mapping. This raises the level-7 boss from
  static-only decode to a runtime-confirmed structure and segment-motion
  model.

  Remaining boss frontier (characterized, not yet frame-aligned): the head
  brain at `1000:5CB0` uses `DS:C204 = 140` as the tile-map row stride,
  scans four rectangle edges with distinct inclusive solid-tile bounds, and
  enters its RNG steering branch only when `DS:78C2 % 29 == 0`. That branch
  draws exact `Random(100)`, `Random(800)`, and `Random(1500)` values; collision
  response applies gravity and signed half-speed reflection. The port models
  the head at a higher level, so exact trajectory, tile-damage ownership,
  phase-HP transitions, and death-chain sequencing remain unpromoted.
  Confirming them requires a deterministic frame-by-frame comparison harness
  with matched RNG seed and input.
  `docs/recovery/boss_head_brain_spec.md` now records the checked static
  control flow and constants without promoting those remaining field semantics
  or the trajectory to runtime parity.

- **Unblocked original level-2..7 capture (multi-session blocker solved).**
  Two long-standing obstacles to comparing the port against the original on
  any level past 1 are now resolved:
  1. *Standalone gameplay input.* SDL/DOSBox silently drops XSendEvent
     synthetic key events, so `xdotool key --window ...` never registered
     in-game -- the reason every standalone Python driver stalled on the menu.
     Real XTEST events (`xdotool windowactivate --sync` to focus, then
     `xdotool key --clearmodifiers <k>` with **no** `--window`, plus
     `keydown`/`keyup` holds for movement) drive gameplay reliably.
  2. *Completion model.* The main-loop gate at Ghidra `1000:8283` requires
     bonus flag `DS:79C5`, destruction flag `DS:79C6`, and the collapse queue
     count `DS:2080 == 0`. The harness writes only bonus/destruction current
     counters `DS:2088`/`DS:79B5` to their level-file targets
     `DS:2086`/`DS:79B3`; original helper `1000:3184` derives both flags, and
     the original result/reload path advances `DS:79B7`. Chaining that route
     captured every playable level `1..7`; value 8 is the completed-game
     sentinel.
  `tools/seed_original_level.py` exposes `--target-level <level>` with
  `--advance-to` retained as a compatibility alias. Its `--self-check` pins
  the loader, counter/flag derivation, completion gate, increment, runtime
  tables, and camera globals (CTest `seed_original_level_self_check`).

- **Verified rendering fidelity across all seven levels.** With the original
  now capturable on every level, the port's per-level start frames
  (`--capture-level-frames`, CTest `capture_level_frames`) were compared to
  the original: world geometry matches faithfully on levels 1-7 (terrain
  profile, brick/truss/pillar structures, platform layout, and level-7
  lower-right artwork). The boss itself starts outside the natural viewport in
  both builds. The HUD objective tallies were verified to match the original
  exactly on every level -- required-bonus / required-destruction of
  1/50, 3/60, 7/20, 3/70, 8/65, .../, 1/10 -- confirming both the recovered
  level data and the panel semantics (top row = required bonus, bottom row =
  required destruction). Fixed a HUD bug where the top tally row rendered the
  life count instead of the required-bonus count.

- **Reconstructed the HUD objective icons exactly.** The original HUD icon
  renderer (tile-blit primitive Ghidra `0x1156`, objective-icon routine
  `0x1174`) blits 8x8 tiles from `CARO.CAR` (132 tiles). The top tally icon is
  the level's bonus-collectible tile `DS:0x79b4` (the port's
  `level.objectiveTile`, e.g. tile 108 lemon / 110 grapes / 107 watermelon);
  the bottom tally icon is the fixed destruction star, `CARO.CAR` tile 117.
  The port now blits both (top = objectiveTile, bottom = tile 117) inside the
  black inset boxes instead of the previous yellow placeholder squares --
  verified matching the original on levels 1/2/5. The two tally numbers show
  the REMAINING objective (`required - current`), counting down as bonuses are
  collected / tiles destroyed (`requiredBonus DS:0x2086 - collected DS:0x2088`;
  `requiredDestruction DS:0x79b3 - current DS:0x79b5`), zero-padded to two
  digits. The centre bomb-selector now draws the blue bomb (BOMOMIMK sprite
  57) confirmed from captured original frames both in the HUD box and as a
  dropped world bomb; the port's earlier green sprite 58 is a different bomb
  variant.

- **Finished the bottom HUD to a pixel-for-pixel match.** The life markers now
  blit `CARO.CAR` tile 115 (the green walking figure) via the shared
  `drawHudTile8` helper; every HUD number (score, bomb count, both objective
  tallies) is drawn from `CARO.CAR` digit tiles 121-130 (`drawHudNumber`); the
  energy gauge is the original single-pixel-tall line (measured at row y0+11);
  and the life panel shows SPARE lives (`lives - 1`), so a fresh three-life
  start draws two markers exactly as every captured original level-start frame
  does. With these, the reconstructed single-player HUD matches the original
  bottom band pixel-for-pixel on level 1 (energy bar, score, life figures,
  bomb selector + count, and the objective tally icons/numbers).

- Corrected the main-menu text after a live original capture showed the
  title draws the menu OPTIONS over the logo art in Italian by default (an
  earlier PR removed the text after an intro-frame capture caught the title
  before the options drew in). The port now overlays the recovered strings
  from LEZAC.EXE 1000:b1e3 (Italian) / 1000:bf15 (English) on the SFONLEF
  title -- PREMI 1 PER UN GIOCATORE ... L: ENGLISH / ESC PER USCIRE --
  defaulting to Italian with the L key toggling English.

- Finished the per-level intro recovery and wired it into interactive play.
  Static analysis pins the palette ramp at `1000:0139`, striped generator at
  `1000:01fc`, level-loader call at `1000:2c01`, localized caption at
  `1000:b2ab`, and fixed-cell renderer at `1000:146a`. The C++ path now uses
  the original seven-color palette interpolation, scanline/sine stripe
  recurrence, 11-pixel caption cells, blue/white shadowed font sprites, and
  the captured 81 ms per-character delay. `--debug-level-intro` (CTest
  `level_intro`) reproduces the retained original frame with zero differing
  pixels (`hash=0x85e10db60f7e89f9`), verifies timed gameplay blocking and
  consumed skip/Escape input, and can emit a PPM frame when given an output
  path. Menu starts, level transitions, manual reloads, and death restarts now
  show the intro in the real interactive session; direct deterministic
  `resetLevel` harness paths remain immediate. The original wall-clock-seeded
  RNG changes the stripe parameters across launches; the exact fixture pins
  one captured draw while live play preserves the recovered draw ranges and
  order. Also fit the gameplay sky gradient to the original sky column
  (pure-sky `mean_abs_delta` 4.1 -> 1.27). Full evidence is in
  `docs/recovery/level_intro_exact_recovery_2026-07-19.md`.
- Reconstructed the single-player bottom HUD to match the original's layout
  and colours (sampled from original frames): a solid-black band with a
  grey/white top border, a yellow energy bar and blue score panel with a
  right-aligned green value, green player-life figures, a grey bomb-selector
  box with the selected bomb and its count, and a blue/cyan right panel with
  bomb/objective tallies. Level-1 route average `mean_abs_delta` improves from
  42.3 to 33.3. Exact HUD icon sprites (bomb, star, player figures) are still
  approximated with primitives; sourcing the original icons is a follow-up.
- Moved the single-player HUD from a top band to a bottom status band to
  match the original (the original's top rows are gameplay sky; the HUD is a
  bottom panel). This drops the level-1 route average `mean_abs_delta` from
  49.0 to 42.3. The HUD content is still the port's stylized layout rather
  than the original's exact icon panels (energy bar, score box, player-life
  figures, bomb selector, bomb-count and star tallies); a pixel-faithful HUD
  redesign is the next fidelity step.
- Recovered and live-validated the complete original level-transition path.
  `tools/seed_original_level.py` now reaches any playable level `1..7` by
  seeding only the current objective counters, allowing `1000:3184` to derive
  `DS:79C5/79C6`, waiting for the empty `DS:2080` collapse queue, and then
  letting the original result routine `1000:1D61` reach the level increment at
  `1000:2051`. Value 8 is the completed-game sentinel, not a playable level.
  A full level-1-to-level-7 run completed all six native result/reload flows
  and captured inspected original level-2 and level-7 gameplay frames. The
  harness can also write paired runtime snapshots for the 1-based actor table
  `DS:1BAE`, visual table `DS:C21E`, 1-based motion-link table `DS:79EA`,
  camera/view globals, and allocator count `DS:C496`. Static evidence is
  reproducible through `tools/ghidra/DumpLevelTransition.java` and
  `tools/ghidra/DumpGranPlacement.java`; full commands and observed targets
  are in
  `docs/recovery/original_level_transition_seed_2026-07-19.md`.
- Ran a live original-vs-port pixel comparison (DOSBox capture in-container)
  and fixed two major visual-fidelity bugs it exposed. Disassembling the
  original menu/display routines (`1000:030b`, decoder `1000:82d0`) revealed
  that `SFONLEF.ZBG` is the 320x200 mode-13h "LARAX & ZACO" title screen
  encoded as nibble-paired RLE (768-byte palette, 2-byte length header, then
  3-byte groups emitting `(b0>>4)+1`x`b1` + `(b0&0x0f)+1`x`b2`), not the
  321x388 PCX image the port assumed. Rewrote `loadRawBackground` and the
  core-resource inline decoder to the recovered format, regenerated
  `src/SFONLEF.ZBG.json`, and set `kBackgroundW/H` to 320x200. The main menu
  now renders the real title image (the port previously drew a text menu):
  menu-frame `mean_abs_delta` vs the DOSBox original dropped from 112.6 to
  0.42 (pixel-identical modulo 6-bit palette rounding). Separately, levels
  were wrongly tiling the (mis-decoded) `SFONLEF.ZBG` as the sky; added
  `drawGradientSky` (top `RGB(16,8,52)` to horizon `RGB(113,60,28)`, sampled
  from original frames) so gameplay shows the original clean gradient instead
  of horizontal-shear noise. Level-1 route average `mean_abs_delta` improved
  from 85.9 to 49.0; the residual gameplay delta is dominated by HUD position
  (the original HUD is a bottom bar; the port's is a top bar), tracked as a
  follow-up. Updated the pinned `core_resource_raw_roundtrip` and
  `original_asset_load` expectations.
- Recovered the original weapon-switch hold/release state machine at
  `1000:6813..68C4`. A natural process-memory stop recorded
  `runtime_hold_counter=0x14`, cursor `0x0024`, and priority 2; the C++ route
  now triggers only after five held updates followed by release and reports
  `weapon_switch_sound=ok`.
- Recovered the Down-gated launch pad at `1000:6924`, including cursor
  `0x0035`/priority 5, vertical velocity `-2000`, the invisible frame-`0x5B`
  mode-5 marker, and the shared portal Down gate. The deterministic
  `launch_pad_route` validates gameplay and captures five rendered frames.
- Classified the contact-scanner mode-6 sound route as dormant in shipped
  data. The recovery queue retains it for seeded evidence with blocker
  `shipped_actor_modes_exclude_6`; no natural or visual claim was promoted.
- Implemented the level-7 multi-segment boss from statically recovered
  original semantics, closing the last known missing gameplay content. A
  five-way static decode of the shipped executable recovered: actor kind
  bytes `0x1E`/`0x1F` and behavior states `6`/`5` for head/segments; the
  head brain at `1000:5CB0` (terrain-flag recompute over the 5x4 tile box
  from head `+0x0e`, 29-tick homing charges with grounded jumps, half-speed
  bounces, per-frame flame-tile `0x75` damage with power doubling, byte-wrap
  phase HP at `+0x24` with lives byte `+0x02`, death chain `1000:5BCC`
  converting linked segments plus head to kind-`0x0E` timed debris with a
  1000-point award); the segment motion-link system (16-byte `DS:0x79EA`
  entries recomputed by `1000:432A` and applied by `1000:5872`: spring mode
  `(target-self+offset)*gain` with per-axis pull-back, orbit mode over a
  128-step `Sin(i*6.28/128)` table, serial bit `0x80` mirroring); the
  facing anim-set pair table at `DS:0x58/0x59` (boss rows `0x0e`=41..42,
  `0x0f`=43..44, `0x10`=40..40); the level-7 `PROVA.SPR` sprite-bank
  selector at `1000:2C90`; and live original table captures confirming
  one-based actor/link indexing, visual allocator count 2 before GRAN and 9
  after it, a `+2` visual-entry rebase, head visual 6 at `(100,100)`, and
  segment visuals 2, 3, 4, 5, 7, and 8 at the decoded offsets. The port now
  spawns the boss on level-7 entry via the guardrail-named live consumer
  `spawnLevel7Boss()`, with behaviors 5/6 wired through the existing
  monster update/damage/render paths and boss sprites drawn from the
  `PROVA.SPR` bank. New coverage: `--debug-gran-boss-model` (pins selector
  and anim-table bytes, prints the decoded boss table) and
  `--debug-autoplayer boss_level7` (frame-inspects spawn layout, orbit/spring
  motion, hurt-flash and flame-drain phases, death chain, debris clearing),
  both in CTest; the GRAN usage guardrail now reports
  `live_consumer_refs=1` for the single named live consumer. Identified the
  long-standing "probable contact scanner" at `1000:5CB0` as the boss-head
  brain. Live initial placement now reports
  `original_runtime_placement_claim=1`; exact original motion/collision timing
  remains `original_runtime_timing_claim=0`.
- Statically recovered the `GRAN.MST` consumer and file layout from the
  shipped executable. The only reference to the `gran.mst` literal at
  `1000:2AD3` is the level-gate callsite `1000:2E78..2E8A`, which loads the
  file through the generic actor-file reader at `1000:08A5..0C32` only when
  the current-level byte `DS:0x79B7` equals 7. The reader layout
  `[N:1][N x 38-byte actor records][N x sprite byte][N x (dx,dy) int16 pairs]
  [M:1][M x 16-byte entries]` consumes the shipped 399 bytes exactly with
  `N=7`/`M=6`, disproving the historical `7 * 57` field-layout guess (kept
  only as the byte-preserving storage split). Records append to the actor
  table `DS:0x1BAE` (stride `0x26`), sprite bytes `46,46,45,45,40,42,43` sit
  inside the recovered `BOMOMIMK` monster frame range, `(dx,dy)` pairs place
  visual entries at `DS:0xC21E` around the `(100,100)` anchor, segments 2..7
  carry serials rebased by `DS:0x79F9` and link to the head record through
  byte `+0x25`, and the 16-byte entries append to `DS:0x79EA` — a
  multi-segment level-7 boss definition. The new
  `--debug-gran-static-consumer-model` diagnostic pins all 12 supporting
  instruction/literal byte windows and reparses the shipped file with the
  recovered layout, reporting `original_runtime_claim=0` because that
  diagnostic intentionally covers static evidence only. CTest covers it, and
  the GRAN usage guardrail permits the named live consumer
  `spawnLevel7Boss()`. The live seeding oracle, `--debug-gran-boss-model`,
  `--debug-autoplayer boss_level7`, and `boss_level7` frame sequence now cover
  the runtime placement mapping; exact original motion timing remains an
  evidence follow-up.
- Declared functional port completion with machine-checkable coverage. Added
  `--debug-port-completion-status`, which enumerates the 22 implemented
  subsystems with deterministic validation entry points and the 12 open
  original-evidence fidelity items, always reporting
  `port_functionally_complete=1 original_fidelity_claim=0`. Added
  `tools/check_port_completion_status.py` (with `--self-test` rejection
  coverage), `docs/recovery/port_completion_status.md` as the canonical
  completion statement, and CTest coverage (`port_completion_status`,
  `port_completion_status_checker`, `port_completion_status_checker_selftest`).
- Fixed the `visual_claim_guardrail` and `runtime_evidence_guardrail` CTest
  expectations, which still pinned `fixtures=78` after
  `contact_scanner_runtime_oracle_missing_dimensions.txt` became the 79th
  checked-in DOSBox fixture; both now expect `fixtures=79` and pass again.
- Validated the whole port on a clean Linux container: fresh
  `cmake`/`g++`/SDL2 build from scratch and a full dummy-SDL CTest run.
  Before the guardrail fix the suite was 354/356; with the fix and the new
  port-completion tests the full suite passes.

- Added a backtrack lane-div route preset and ran another non-pruned original
  `1000:3CE3` route-state sweep. `tools/sweep_original_lane_div_routes.py`
  now supports `--route-preset forward-helper-backtrack`, expanding to
  `x:4.00,Left:1.00,m:0.50,x:4.00`,
  `x:6.00,Left:1.00,m:0.50,x:4.00`, and
  `x:4.00,z:0.50,Left:1.00,m:0.50,x:4.00`. The live WSL/DOSBox run at
  `/tmp/lezac-lane-div-backtrack` targeted `forward-divide` with route-state
  sampling and `--skip-oracle`; all three captures loaded the `3CE3` runtime
  patch with `runtime_cs=01ED` and `runtime_ds=0C8F`, but the summary recorded
  `observed_freezes=0`, `no_freeze_candidates=3`,
  `forward_divide_candidates=0`, `route_state_sample_files=3`,
  `route_state_samples=122`, `route_state_debris_marker_candidates=0`,
  `route_state_debris_marker_samples=0`,
  `max_route_state_lane_word_global=0x0000`, and
  `max_route_state_queue_score=190`. The strict
  `--require-forward-divide --require-route-state-debris-marker` gate failed
  with `reason=no_forward_divide_candidates`, so no `3D2D` handoff was written.
  Inspected route-position and tail-freeze frames for all three routes stayed
  in live level-1 gameplay with bomb/enemy/effect frames, so this preset is
  reproducible route-pruning evidence only.
- Added a delayed-bomb lane-div route preset and ran the next non-pruned
  original `1000:3CE3` route-state sweep. `tools/sweep_original_lane_div_routes.py`
  now supports `--route-preset forward-helper-delayed-bomb`, expanding to
  `x:4.00,m:0.50,x:3.00`, `x:6.00,m:0.50,x:3.00`, and
  `x:4.00,z:0.50,m:0.50,x:3.00`. The live WSL/DOSBox run at
  `/tmp/lezac-lane-div-delayed-bomb` targeted `forward-divide` with
  route-state sampling and `--skip-oracle`; all three captures loaded the
  `3CE3` runtime patch with `runtime_cs=01ED` and `runtime_ds=0C8F`, but the
  summary recorded `observed_freezes=0`, `no_freeze_candidates=3`,
  `forward_divide_candidates=0`, `route_state_sample_files=3`,
  `route_state_samples=113`, `route_state_debris_marker_candidates=0`,
  `route_state_debris_marker_samples=0`,
  `max_route_state_lane_word_global=0x0000`, and
  `max_route_state_queue_score=190`. The strict
  `--require-forward-divide --require-route-state-debris-marker` gate failed
  with `reason=no_forward_divide_candidates`, so no `3D2D` handoff was written.
  Inspected route-position and tail-freeze frames for all three routes stayed
  in live level-1 gameplay with bomb/enemy/effect frames, so this preset is
  reproducible route-pruning evidence only.
- Added a focused behavior-4 route preset and ran a non-duplicate level-3
  spawner branch smoke against the original. `tools/sweep_original_behavior4_procmem_routes.py`
  now reports `route_preset=` and supports `--route-preset branch-x2` for the
  single `x:2.00` branch smoke route. The live WSL/DOSBox pass at
  `/tmp/lezac-behavior4-spawner-level3-branch-x2` used scenario
  `monster_spawner_behavior4_level3`, targets `behavior4_branch_start` and
  `behavior4_branch_end`, timing `before_route`, and route `x:2.00`. Both
  captures loaded runtime patches with `runtime_cs=01ED` and
  `runtime_ds=0C8F`, but the summary recorded `observed_freezes=0`,
  `observed_targets=none`, `runtime_patches_applied=2`,
  `patched_no_freeze_candidates=2`, and
  `patched_no_freeze_targets=behavior4_branch_start,behavior4_branch_end`;
  `--require-target-freeze behavior4_branch_start` failed with
  `reason=target_freeze_missing`. Inspected `020_route_position` and
  `091_tail_freeze_check` frames for both targets stayed in live gameplay with
  bomb effects, so this is route-pruning evidence only and no behavior-4 branch
  fixture was promoted.
- Added target-specific actor/contact dispatch-gate summary triage and ran the
  next live original-evidence probes. `tools/summarize_actor_dispatch_gate_sweep.py`
  now exposes repeatable `--require-dispatch-gate-target <target>` so a generic
  actor-update gate freeze cannot satisfy a focused `contact_scanner_callsite`
  reachability check. A live WSL/DOSBox all-target pass at
  `/tmp/lezac-actor-contact-all-target-before-route-x2` used
  `--all-targets --timing before_route --route x:2.00`; it recorded
  `environment_preflight=ok`, `targets=9`, `captures=9`, `freezes=6`,
  `dispatch_gate_freezes=4`,
  `observed_targets=actor_update_start,actor_update_end,actor_update_gate5,actor_update_gate5_integration,actor_update_gate5_exit,actor_update_gate6`,
  `observed_dispatch_gates=actor_update_gate5,actor_update_gate5_integration,actor_update_gate5_exit,actor_update_gate6`,
  `missing_targets=contact_scanner_callsite,contact_scanner_start,contact_scanner_end`,
  `ready_candidates=0`, and `incomplete_candidates=6`. A focused
  `/tmp/lezac-contact-callsite-nonredundant-20260617` follow-up tried
  `x:3.00,z:0.50,x:2.00` and `x:1.50,Left:0.50,x:2.00` for
  `contact_scanner_callsite`, but recorded `captures=2`, `freezes=0`, and
  `observed_dispatch_gates=none`. Inspected route/tail frames from both runs
  stayed in live level-1 playback, including bomb-effect frames on the focused
  routes, so this is route-pruning evidence only; no contact-scanner callsite
  fixture was promoted.
- Added target-specific behavior-4 procmem sweep triage and ran a live
  all-anchor original-evidence pass. `tools/summarize_behavior4_procmem_route_sweep.py`
  now reports `observed_targets=` and `patched_no_freeze_targets=` and exposes
  `--require-target-freeze <target>` so generic spawner/integration freezes do
  not masquerade as behavior-4 branch evidence. The live WSL/DOSBox run at
  `/tmp/lezac-behavior4-all-anchor-before-route-x2` used
  `--all-targets --timing before_route --route x:2.00`; all six runtime patches
  loaded with `runtime_cs=01ED` and `runtime_ds=0C8F`. The summary recorded
  `observed_freezes=3`, `observed_targets=spawner_loop_start,integration_8_8_start,integration_8_8_end`,
  `runtime_patches_applied=6`, `patched_no_freeze_candidates=3`,
  `patched_no_freeze_targets=spawner_loop_end,behavior4_branch_start,behavior4_branch_end`,
  `ready_candidates=0`, and `incomplete_candidates=6`. Inspected
  `020_route_position` and `091_tail_freeze_check` frames stayed in live level-1
  playback, so this is anchor reachability and route-pruning evidence only; a
  behavior-4 branch fixture still needs a route or seeded setup that reaches
  behavior-4 actors.
- Pruned a broadened lane-div helper-route hypothesis for the remaining natural
  forward `3D2D` search. A live WSL/DOSBox pass at
  `/tmp/lezac-lane-div-broadened-route` tested the new
  `forward-helper-broadened` route family, `x:8.00` and
  `x:5.00,m:0.50,x:4.00`, against the forward divide at `1000:3CE3` with
  route-state sampling enabled. Both captures loaded the runtime patch and
  stayed in live level-1 playback on inspected `020_route_position` and
  `090_after_sampling` frames, but summarized as `observed_freezes=0`,
  `ready_candidates=0`, `no_freeze_candidates=2`,
  `route_state_sample_files=2`, `route_state_samples=75`,
  `route_state_debris_marker_candidates=0`, and
  `max_route_state_lane_word_global=0x0000`. `tools/sweep_original_lane_div_routes.py`
  now keeps that pair as the named `forward-helper-broadened` preset so future
  searches do not repeat the same broadened route family.
- Tightened the lane-write route-manifest handoff for the remaining natural
  forward `3D2D` search. `tools/sweep_original_lane_write_routes.py` now
  derives default offsets from the promotion type when `--route-manifest` is
  used without explicit `--offset`: branch-anchor, lane-write forward-debris,
  and lane-div forward-debris manifests default to `1000:3D2D`, while plain
  lane-div forward-route manifests default to the paired forward writeback
  probes `1000:3D1B` and `1000:3D2D`. Explicit `--offset` still overrides the
  manifest default. This reduces accidental reverse `3EC1` probes when a
  forward-only route handoff is already available.
- Tightened sound-callsite procmem promotion triage after live WSL/DOSBox-debug
  probes loaded runtime patches but did not reach the patched callsites.
  `tools/capture_original_sound_callsite_procmem.sh` now emits
  `freeze_runtime_patch_applied=`, `promotion_status=`, and
  `promotion_blocker=` in manifests, raw dumps, and status lines.
  `tools/summarize_sound_callsite_route_sweep.py` reports
  `runtime_patches_applied=`, `patched_no_freeze_candidates=`, and
  `blocked_candidates=`, exposes `--require-runtime-patch`, and labels
  patched/no-freeze captures as `promotion_blocker=no_observed_freeze`.
  Live attempts on 2026-06-17 covered the default contact-scanner matrix
  (`contact_scanner_runtime_sound`, 8 route/timing captures) and a focused
  `actor_update_runtime_cursor_0035_sound` before-route `x:2.00` probe; all
  observed `runtime_cs=01ED`, `runtime_ds=0C8F`, loaded the target patch, and
  reported `observed_freezes=0`. These are route-pruning evidence only, not
  promoted sound-callsite fixtures.
- Added a stricter lane-div-to-lane-write handoff for the remaining natural
  forward `3D2D` search. `tools/summarize_lane_div_route_sweep.py` now reads
  each candidate's `route_state_samples.tsv`, reports
  `forward_debris_route_candidates=`,
  `route_state_debris_marker_candidates=`, and
  `max_route_state_lane_word_global=`, and exposes
  `--require-route-state-debris-marker`. When a route both reaches the forward
  divide at `1000:3CE3` and samples `lane_word_global_value >= 0x4e20`,
  `--write-forward-debris-route-manifest` emits
  `lane_div_forward_debris_route_candidates`; both lane-div and lane-write
  sweep wrappers now consume that manifest for focused follow-up probes. This
  is still route-state triage, not proof that natural `1000:3D2D` executed.
- Added route-state debris-marker triage to the lane-write sweep summary. The
  original process-memory capture now writes `lane_update_flag_value`,
  `lane_word_global_value`, `lane_target_offset_global_value`, and effect input
  globals into `route_state_samples.tsv`; `tools/summarize_lane_write_route_sweep.py`
  reads each candidate's route-state TSV when present and reports
  `route_state_sample_files=`, `route_state_samples=`,
  `route_state_debris_marker_candidates=`,
  `route_state_debris_marker_samples=`, and
  `max_route_state_lane_word_global=`. The new
  `--require-route-state-debris-marker` gate is search triage only: it can show
  that a route sampled a lane word at or above the `0x4e20` debris-marker base
  before another `3D2D` run, but it does not promote a natural forward debris
  writeback fixture.
- Added a lane-div route classifier for the next natural forward writeback
  search. `tools/sweep_original_lane_div_routes.py` batches guarded
  `lane-div-cs-scratch` probes at `1000:3CD4`/`3CE3`/`3E68`/`3E77`, and
  `tools/summarize_lane_div_route_sweep.py` classifies the resulting candidates
  as `ready`/`no_patch`/`no_freeze`/`incomplete`/`missing` with
  `forward_divide_candidates=` and route-step details. When
  `--require-forward-divide` passes, it can write
  `lane_div_forward_route_candidates`, and
  `tools/sweep_original_lane_write_routes.py --route-manifest` now consumes
  that handoff for focused `3D1B`/`3D2D` follow-up probes. This is helper-route
  triage only; it does not promote a natural `3D2D` fixture.
- Tightened the lane-write route-sweep promotion gate for the still-open
  natural forward debris writeback. `tools/summarize_lane_write_route_sweep.py`
  now reports `forward_debris_tag_candidates=` and
  `reverse_debris_tag_candidates=`, exposes `--require-forward-debris-tag`, and
  can write a `lane_write_forward_debris_route_candidates` manifest preserving
  the exact route steps for only routes that reach a ready forward debris
  write. `tools/sweep_original_lane_write_routes.py --route-manifest` accepts
  that handoff alongside branch-anchor route manifests. This prevents the
  already-promoted reverse debris write at `3EC1` from satisfying the
  remaining natural `3D2D` gate.
- Extended the branch-anchor to lane-write handoff: the branch-anchor
  summarizer can now write a `branch_anchor_route_candidates` manifest for
  routes satisfying `--require-route-with-targets`, preserving the exact
  `--route-step` sequence from the original sweep commands. The lane-write
  route sweep accepts that file with `--route-manifest`, so a future natural
  `1000:3D2D` probe can be driven only from routes that already proved the
  high-debris word gate and forward helper call.
- Added `tools/summarize_branch_anchor_route_sweep.py` and checker/CMake
  coverage so high-debris branch-anchor sweeps now summarize route
  reachability before another natural `1000:3D2D` attempt. The summary reports
  per-candidate `ready`/`no_patch`/`no_freeze`/`incomplete` state,
  `observed_targets=`, `observed_routes=`, route-level `route_hits=`, and
  `bp4_local_value=` when `1000:4C75` bp4-scratch evidence is present. The new
  `--require-route-with-targets high_debris_word_gate,effect_forward_pass_call`
  gate keeps future `3D2D` captures tied to routes that actually reached both
  the word gate and the forward helper call.
- Extended `tools/summarize_behavior4_procmem_route_sweep.py` and its checker
  so behavior-4 route-sweep summaries now report total
  `runtime_patches_applied=` and expose `--require-runtime-patch`. The checker
  covers a synthetic no-patch sweep that fails with
  `reason=no_runtime_patches_applied`, preventing a live matrix from looking
  useful when no runtime freeze patch was actually armed.
- Extended `tools/capture_original_behavior4_procmem.sh` so live capture status
  lines now emit `freeze_runtime_patch_applied=` directly, matching the child
  capture manifest and raw dump. The behavior-4 route-sweep summarizer still
  falls back to the child manifest for older captures, but new sweep manifests
  now carry enough top-level status metadata for `runtime_patch_applied=` and
  `patched_no_freeze_candidates=` without reopening every candidate directory.
- Extended `tools/summarize_behavior4_procmem_route_sweep.py` and its checker
  so behavior-4 route-sweep summaries now distinguish patch-loaded no-freeze
  captures from missing or unattempted candidates. Details report
  `runtime_patch_applied=`, and the summary reports
  `runtime_patches_applied=` plus `patched_no_freeze_candidates=` from either
  the top-level capture status or
  the child capture manifest's `freeze_runtime_patch_applied` field. Three
  2026-06-17 WSL smoke captures
  proved the new classification on live original runs: `behavior4_branch_start`
  before-bomb route `x:2.00`, before-bomb route `x:5.00,m:0.50,x:2.00`, and
  before-route route `x:2.00` each observed `runtime_cs=01ED`,
  `runtime_ds=0C8F`, loaded the `01ED:728C` patch, and summarized as
  `runtime_patches_applied=1`, `observed_freezes=0`,
  `patched_no_freeze_candidates=1`, `ready_candidates=0`. These are negative
  route evidence, not promoted
  behavior-4 runtime fixtures.
- Added `--debug-behavior4-static-model` and CTest coverage to pin the shipped
  `LEZAC.EXE` byte windows for the six behavior-4 runtime-capture anchors:
  spawner loop `1000:7A6B`/`1000:7C2C`, behavior-4 branch
  `1000:728C`/`1000:731B`, and 8.8 integration `1000:73E5`/`1000:741B`.
  The diagnostic reports the same target map used by
  `--debug-behavior4-runtime-oracle` and
  `tools/capture_original_behavior4_procmem.sh`, while keeping
  `visual_claim=0` so future original runtime fixtures remain the promotion
  gate for behavior-4 semantics.
- Added `--debug-lane-write-tag-model` and CTest coverage to pin the recovered
  lane write tag/address arithmetic without changing gameplay. The diagnostic
  maps collapse tags directly through the `0x0f` stride, maps debris tags by
  subtracting the `0x4e20` marker before the `0x0b` stride, and checks
  representative collapse writes `0x0002 -> 0x6635/0x6636`,
  `0x0005 -> 0x6662/0x6663` plus debris writes
  `0x4e21 -> 0x20a2/0x20a3` and `0x4ee8 -> 0x292f/0x2930`. The output keeps
  `original_capture_claim=0`, so the pending natural `1000:3D2D` capture is
  still an explicit follow-up rather than implied by the arithmetic model.
- Encapsulated the two remaining sound compatibility routes behind
  `playCompatibilitySound(...)` and a single
  `kRemainingSoundCompatibilityHooks` metadata table. Objective pickup and
  level-complete still funnel to the same compatibility `playSound(index)`
  cursors, now prove `latch_preserved=1` after seeding a recovered
  records-page latch, still report `original_cursor_priority_claim=0`, and
  still carry the blockers
  `objective_pickup:rejected_static_candidates,level_complete:no_static_candidate`,
  but the live gameplay code no longer contains scattered raw compatibility
  `playSound(...)` calls. The checker now allows only the single helper funnel
  and verifies both named hook slots plus their blockers.
- Extended `tools/sweep_original_actor_contact_routes.py` with
  `--all-targets`, mirroring the newer sound/behavior route sweeps for the
  older actor/contact process-memory path. The low-level route planner now
  runs one route/timing matrix across all nine mapped actor/contact targets,
  preserves the single-target output shape by default, and writes normalized
  `targets=`/`target_names=` metadata plus target-prefixed capture labels for
  all-target batches. `tools/summarize_actor_dispatch_gate_sweep.py` now reads
  direct route manifests with `target_names=` and strips target prefixes from
  all-target capture labels when reporting routes, so the next DOSBox-capable
  pass can summarize observed/missing actor/contact targets without routing
  everything through the dispatch-gate wrapper.
- Extended `tools/sweep_original_sound_callsite_routes.py` with
  `--all-targets`, so the next DOSBox/procmem sound pass can sweep
  `contact_scanner_runtime_sound`,
  `actor_update_runtime_cursor_0024_sound`,
  `actor_update_runtime_cursor_0035_sound`, and
  `actor_update_runtime_cursor_0021_sound` with one route/timing matrix.
  All-target capture labels are target-prefixed, and
  `tools/summarize_sound_callsite_route_sweep.py` now parses those labels while
  still accepting the legacy single-target labels. The checker covers the new
  all-target dry-run, the `--all-targets`/`--target` refusal, and all-target
  summary classification.
- Extended `docs/recovery/ready_fixture_provenance_contract.md` and
  `tools/check_ready_fixture_provenance_contract.py` so the ready-fixture
  guardrail covers the behavior-4 and sound-callsite route-sweep summary
  writers, not only the older batch/dispatch/lane summary writers. CMake now
  expects six ready-manifest writers, keeping the new procmem sweep handoffs
  under the same runtime segment, `temp_copy=1`, and `visual_claim=0`
  provenance rules before any original runtime fixture can be promoted.
- Added `tools/summarize_sound_callsite_route_sweep.py` plus
  `tools/check_sound_callsite_route_sweep_summary.py` and CMake coverage for
  `sound_callsite_route_sweep` manifests. The summary classifies each
  sound-callsite procmem capture as ready/incomplete/missing, reports observed
  freezes and per-capture `--debug-sound-callsite-oracle` commands, exposes
  `--require-ready`, `--require-observed-freeze`, and
  `--require-environment-preflight` gates, and can write a
  `debug_capture_ready_candidates` manifest for ready sound-callsite fixtures.
  The generic ready-manifest runner and result summarizer now accept the
  `sound_callsite` oracle key mapped to `--debug-sound-callsite-oracle`, so a
  completed actor/contact sound sweep can be triaged and dry-run through the
  existing promotion pipeline without manual command rewriting.
- Extended `tools/capture_original_sound_callsite_procmem.sh`,
  `tools/sweep_original_sound_callsite_routes.py`,
  `tools/check_sound_callsite_procmem_helper.py`, and CMake dry-run coverage
  from the first contact-scanner sound target to all four actor/contact runtime
  sound candidates: `contact_scanner_runtime_sound` at `1000:5E81`,
  `actor_update_runtime_cursor_0024_sound` at `1000:6844`,
  `actor_update_runtime_cursor_0035_sound` at `1000:6924`, and
  `actor_update_runtime_cursor_0021_sound` at `1000:7386`. The route-sweep
  checker now proves actor-update targets are accepted while keeping the
  default sweep focused on `contact_scanner_runtime_sound`; all generated
  candidates remain `visual_claim=0` until original latch/request bytes are
  captured.
- Extended `tools/summarize_behavior4_procmem_route_sweep.py` with
  `--write-ready-manifest`, producing the existing
  `debug_capture_ready_candidates` format for ready behavior-4 sweep outputs.
  The checker now verifies that a ready procmem sweep writes behavior-4 oracle
  metadata, source labels, target/timing/route labels, and can be dry-run by
  `tools/run_debug_capture_ready_manifest.py` through
  `--debug-behavior4-runtime-oracle`.
- Added `tools/summarize_behavior4_procmem_route_sweep.py` plus
  `tools/check_behavior4_procmem_route_sweep_summary.py` and CMake coverage for
  behavior-4 process-memory sweep triage. The summary reads
  `behavior4_procmem_route_sweep` manifests, classifies each capture candidate
  as ready/incomplete/missing, reports observed freezes and oracle commands,
  and exposes `--require-ready`, `--require-observed-freeze`, and
  `--require-environment-preflight` gates before any original behavior-4
  fixture can be promoted.
- Added `tools/sweep_original_behavior4_procmem_routes.py` plus
  `tools/check_behavior4_procmem_route_sweep.py` and CMake dry-run coverage so
  the behavior-4 process-memory fallback can be exercised as a route/timing
  matrix instead of one anchor at a time. The default matrix targets
  `behavior4_branch_start` and `integration_8_8_start` for
  `monster_behavior4_target_selection` across the reviewed behavior-4 route
  hypotheses with both pre-bomb and pre-route freeze timing; `--all-targets`
  expands the plan to all six anchors. Live runs still require
  `--approve-procmem` and `--approve-runtime-instrumentation`, write a
  `behavior4_procmem_route_sweep` manifest, and leave generated candidates
  non-promoted until semantic behavior-4 rows are captured.
- Added `tools/capture_original_behavior4_procmem.sh` plus
  `tools/check_behavior4_procmem_helper.py` and CMake dry-run coverage for the
  six behavior-4 runtime anchors: `spawner_loop_start`,
  `spawner_loop_end`, `behavior4_branch_start`, `behavior4_branch_end`,
  `integration_8_8_start`, and `integration_8_8_end`. The helper uses the
  existing DOSBox-debug child process-memory freeze path as a fallback for the
  local debugger command-submission timeout, requires
  `LEZAC_BEHAVIOR4_APPROVE_PROCMEM=1` and
  `LEZAC_BEHAVIOR4_APPROVE_RUNTIME_INSTRUMENTATION=1` for live runs, emits
  `behavior4_procmem` manifests/raw output plus a fill-in
  `behavior4_runtime` candidate fixture, and keeps `visual_claim=0` until
  semantic spawner/actor/player rows are captured.
- Ran a live WSL/Xvfb/DOSBox-debug behavior-4 target-selection evidence pass:
  `tools/capture_original_behavior4_debug.sh
  /tmp/lezac-behavior4-target-selection .
  monster_behavior4_target_selection`. The environment preflight passed on the
  WSL host and the debugger launch reached the prompt with `runtime_cs=01ED`
  and `runtime_ds=01DD`. The helper generated translated commands for
  `01ED:7A6B`, `01ED:7C2C`, `01ED:728C`, `01ED:731B`, `01ED:73E5`, and
  `01ED:741B`, with dumps under `01DD:7900`, `01DD:7A00`, and `01DD:7B00`.
  DOSBox-debug still exited by timeout (`dosbox_debug_exit=124`) before those
  commands could be submitted, so the summary remains
  `candidate_status=incomplete` with missing runtime fixture rows and no
  `behavior4_runtime_oracle_original*.txt` fixture was promoted.
- Tightened the debug-capture summary/support path used by that pass:
  `tools/summarize_debug_capture.py` now tolerates identical duplicate manifest
  fields emitted by the debug helpers while still rejecting conflicting
  duplicates, and `tools/capture_original_behavior4_debug.sh` records
  `runtime_metadata=observed` in the manifest when runtime registers are
  found. The behavior-4 helper checker and debug-summary checker cover both
  updates.
- Added `tools/sweep_original_sound_callsite_routes.py` and
  `tools/check_sound_callsite_route_sweep.py` to dry-run or execute guarded
  route/timing matrices for `contact_scanner_runtime_sound`. The sweep forwards
  `LEZAC_SOUND_CALLSITE_ROUTE_STEPS`,
  `LEZAC_SOUND_CALLSITE_RUNTIME_FREEZE_BEFORE_ROUTE`, and the sound-callsite
  process-memory approval flags to
  `tools/capture_original_sound_callsite_procmem.sh`, emits
  `sound_callsite_route_sweep` manifests, and has CTest coverage for default
  and focused dry-runs plus guard/refusal behavior.
- Added `tools/capture_original_sound_callsite_procmem.sh` plus checker and
  CTest dry-run coverage for the first actor/contact sound capture target,
  `contact_scanner_runtime_sound` at `1000:5E81`. The helper uses the existing
  DOSBox-debug child process-memory freeze path as a fallback when debugger
  command submission is unreliable, requires
  `LEZAC_SOUND_CALLSITE_APPROVE_PROCMEM=1` and
  `LEZAC_SOUND_CALLSITE_APPROVE_RUNTIME_INSTRUMENTATION=1` for live runs,
  writes `sound_callsite_procmem` manifests/raw output plus a fill-in
  `sound_callsite` candidate fixture, and preserves `visual_claim=0` until a
  valid original sound-callsite oracle fixture supplies latch/request bytes.
- Added `--debug-sound-runtime-capture-queue` to pin the four
  actor/contact-runtime sound capture targets as an ordered C++ diagnostic.
  It rechecks the shipped byte windows for `1000:5e81`, `1000:6844`,
  `1000:6924`, and `1000:7386`, reports
  `sound_runtime_capture_queue=ok`, uses
  `first_target=actor_update_runtime_cursor_0024_sound`, reports
  `route_classes=natural:3,runtime_seeded:1` and
  `state6_capture_blocker=shipped_actor_modes_exclude_6`, and names
  `tools/capture_original_sound_callsite_procmem.sh`
  plus `tools/sweep_original_sound_callsite_routes.py` as the guarded runtime
  handoff, records the approval flags `LEZAC_SOUND_CALLSITE_APPROVE_PROCMEM`
  and `LEZAC_SOUND_CALLSITE_APPROVE_RUNTIME_INSTRUMENTATION`, and preserves
  `original_cursor_priority_claim=0` until a valid
  `sound_callsite_oracle_original*.txt` fixture is captured.
  A focused WSL preflight passed for `dosbox-debug`/`xvfb-run` and the
  `contact_scanner_runtime_sound` dry-run emitted the expected `BP <CS>:5E81`
  and `BP <CS>:165A` plan, but the live run was not attempted successfully
  because `wsl.exe` began alternating between named-distro and default-distro
  launch failures.
- Extended `tools/capture_original_sound_callsite_debug.sh`, its checker, and
  dry-run CTest matrix from twelve to sixteen scenarios by adding the four
  actor/contact runtime sound candidates reported by
  `--debug-static-sound-unresolved-contexts`:
  `contact_scanner_runtime_sound`, `actor_update_runtime_cursor_0024_sound`,
  `actor_update_runtime_cursor_0035_sound`, and
  `actor_update_runtime_cursor_0021_sound`. The generated manifests and
  candidate fixtures carry `capture_class=actor_contact_runtime` plus
  `static_region=contact_scanner` or `static_region=actor_update`, so future
  DOSBox-debug captures have exact breakpoints without promoting any cue
  semantics yet.
- Added lane-write scratch tag classification to
  `tools/summarize_lane_write_route_sweep.py`. Route-sweep summaries now print
  each ready candidate's `lane_write_tag`, derived `lane_write_tag_class`, and
  summary counts for debris-marker versus collapse-tag candidates. The new
  `--require-debris-tag` gate fails unless at least one ready lane-write
  candidate has a scratch tag at or above the `0x4e20` debris-marker base,
  making the pending natural `1000:3D2D` search machine-checkable instead of
  relying on manual oracle-log inspection.
- Aligned live fire-key handling with the recovered keyboard IRQ gate bytes:
  player 1 uses `N` (`0x31`/`0xb1`) and player 2 uses keypad `0`/Insert
  (`0x52`/`0xd2`). `--debug-input-fire-key-model` now pins the shipped
  `LEZAC.EXE` handler byte windows for the make/break gates, while
  `--smoke-controls`, the optional xdotool UI smoke, and two-player autoplayer
  routes drive the SDL key events and assert bomb owner/inventory effects.
  Validation passed with the native Windows Debug build helper, direct
  dummy-SDL `--debug-input-fire-key-model`, smoke, and two-player autoplayer
  commands, focused CTest coverage for controls/menu/two-player routes, the
  broader UI/autoplayer dummy-SDL CTest group, and `bash -n` for the optional
  xdotool script. After rebasing onto refreshed `origin/main`, the full native
  Windows CTest suite passed 286/286. A WSL/Xvfb `dosbox-debug` smoke launch
  reached the debugger UI from a temp copy and was stopped by timeout without
  issuing debugger commands.
- Extended `--debug-autoplayer death_reentry` to cover the shipped-manual
  post-death choice: after the recovered 60-tick state-2 countdown, pressing
  fire reenters a still-winnable level, waiting through the reentry timeout
  restarts the level, and an unwinnable level blocks early fire and restarts
  after the state-2 countdown. The route frame-inspects each transition.
  Validation passed with the native Windows Debug build helper, direct
  dummy-SDL `--debug-autoplayer death_reentry`, focused death/state-2 CTests,
  and the broader UI/autoplayer dummy-SDL CTest group.
- Added a current-port pause flow: `P` toggles an in-game pause overlay,
  gameplay update/input state is frozen while paused, Escape clears pause and
  returns to the main menu, and `--debug-autoplayer pause_flow` frame-inspects
  the overlay/resume path while reporting `original_pause_claim=0` until
  original-game pause behavior is observed.
  Validation passed with the native Windows Debug build helper, direct
  dummy-SDL `--debug-autoplayer pause_flow`, and focused CTest coverage for
  UI smoke, controls, menu frame flow, level-1 frame inspection, and all
  `autoplayer_*_dummy` scenarios.
- Tightened `--debug-original-state2-visual-row-model` so the original
  state-2 row fixture now labels its raw field candidates: row bytes 0 and 1
  stay draw-offset candidates with bytes `0x10,0x10` / pixels `16,16`, row byte
  2 remains the stable raw constant `0x7d`, and row byte 3 remains the
  `BOMOMIMK` sprite-index range `0x43..0x48`. This is still
  `visual_claim=0`; paired original-frame comparison is required before the
  full death/reentry presentation can be promoted.
- Added `--debug-monster-sprite-table-model` to pin the current monster sprite
  table candidates against the loaded `BOMOMIMK` bank: normal frames
  `39..41`, `43..46`, `49..51`, `53..55`, adjacent impact candidates
  `42,47,48,52,56`, current death renderer sprite `18`, and reward frames
  `61..67` with the recovered reward scores. This narrows the exact
  impact/death/reward frame-table gap but remains asset/table evidence with
  `visual_claim=0`.
- Added a live central objective/progress line to the two-player HUD band and
  `--debug-two-player-hud-panel` frame inspection. The diagnostic pins both
  split world views, both player HUD bands, the central objective panel region,
  and progress/stat redraw behavior while keeping `original_art_claim=0`.
- Ran the reviewed `forward-debris-expanded` lane-write sweep against natural
  `1000:3D2D` under WSL/DOSBox, writing the bundle to
  `C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-expanded-34076294c39340d1beaaaa48bb1b85fb`.
  All ten route captures completed and the native Windows
  `build-win-codex-vs3\Debug\lezac_cpp.exe --debug-explosion-playback-oracle`
  parsed every candidate, but the summary is still negative evidence:
  `observed_freezes=0`, `ready_candidates=0`, `no_freeze_candidates=10`,
  `missing_offsets=3d2d`. The unchanged expanded matrix should not be rerun as
  the next step.
- Ran the first single-route gated `1000:3D2D` retry at
  `C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-gated-ac9c6f74892147aea45528262db7131a`
  with route `x:2.00,c:0.50`, selected bases `209e/6620/c22e`, and
  `--runtime-freeze-require-high-debris-target-byte 0x01`. The capture
  completed, but the runtime patch never loaded because the strict target-byte
  gate did not match; the lane-write summary now reports this as
  `no_patch_candidates=1` instead of treating the candidate as incomplete.
- Reran the same route with the observed later decoded state
  `2941/665c/c22e` plus target byte `0xde`, writing
  `C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-gated-observed-726a47298cea477e8a370f24cbba4f95`.
  The runtime patch loaded at `4.452` seconds after the bomb with debris count
  `202`, collapse count `5`, and lane globals `0x0004/0x072c`, but no freeze
  or natural forward-debris lane write occurred. The native oracle and summary
  classify it as a valid `no_freeze` candidate, not promotion evidence.
- Ran the word-layer gated `1000:3D2D` retry for the earlier decoded
  `209e/6620/c22e` state, writing
  `C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-word-gated-1781605749`.
  The capture reached the selected bases and target byte `0x00`, but the high
  debris word-layer value was `0x0000` instead of the requested `0x0005`, so
  the runtime patch did not apply. The Windows oracle reports no freeze and no
  natural forward-debris lane write, and the WSL summary classifies the single
  candidate as `no_patch` with `missing_offsets=3d2d`.
- Fixed `tools/sweep_original_lane_write_routes.py` so WSL sweeps that invoke a
  Windows `.exe` oracle translate `/mnt/<drive>/...` candidate paths to
  Windows drive paths for the oracle argument. The dry-run expectation checker
  now pins that host-split path shape.
- Followed the `1000:3D2D` word-layer-zero plan after the host-split oracle fix:
  `C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-word-zero-1781607694`
  required `209e/6620/c22e`, target byte `0x00`, and word-layer `0x0000`, but
  selected debris base `0x2093` at the chosen sample, so it stayed `no_patch`.
  The paired `2093` and `209e` base-specific calibrated retries at
  `...\lezac-lane-write-forward-base2093-word-zero-1781607826`,
  `...\lezac-lane-write-forward-base2093-calibrated-1781607951`, and
  `...\lezac-lane-write-forward-base209e-calibrated-1781608035` also stayed
  `no_patch` because the route alternates between early and later selected
  debris geometry.
- Ran the base-agnostic calibrated retry at
  `C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-base-agnostic-1781608123`.
  Its sample table showed why the patch still did not apply: the early
  target-byte/word match only had seven nonzero debris bytes, below the
  previous `0x20` debris threshold, while later samples had shifted target
  geometry.
- Ran the final early-state calibrated retry at
  `C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-early-threshold-1781608295`
  with queue score `0x80`, debris nonzero `0x07`, collapse nonzero `0x01`,
  collapse/effect bases `6620/c22e`, target byte `0x00`, and word-layer
  `0x0000`. This time the runtime patch applied immediately after the bomb
  (`runtime_freeze_patch_applied=1`, elapsed `0.000`, selected debris base
  `0x2093`), but no freeze or natural forward-debris lane write occurred. The
  WSL summary classifies it as a valid `no_freeze` candidate with
  `missing_offsets=3d2d`, not promotion evidence.
- Taught the lane-write and lane-result route-sweep summarizers to translate
  WSL drive paths such as `/mnt/c/...` back to Windows paths when run by native
  Python. This fixed the local forward-debris sweep summary from ten false
  `missing` candidates to ten valid `no_freeze` candidates.
- Taught the lane-write and lane-result route-sweep summarizers to distinguish
  candidates where the runtime freeze gate never applied the patch
  (`no_patch`) from incomplete fixtures. The synthetic summary checks now cover
  ready, no-freeze, no-patch, incomplete, and missing cases.
- Exposed the lower explosion process-memory helper's runtime-freeze filters
  through `tools/sweep_original_lane_write_routes.py`: queue/debris/collapse/
  effect thresholds, selected debris/collapse/effect base gates, and
  `--runtime-freeze-require-high-debris-target-byte` /
  `--runtime-freeze-require-high-debris-word-layer-value`. The sweep wrapper
  now treats those filters as valid runtime freeze gates and its dry-run
  coverage verifies that they are forwarded to the capture helper.
- Added later lane-global runtime-freeze gates to
  `tools/capture_original_explosion_procmem.py` and forwarded them through
  `tools/sweep_original_lane_write_routes.py`:
  `--runtime-freeze-require-lane-update-flag`,
  `--runtime-freeze-require-lane-word-global-value`, and
  `--runtime-freeze-require-lane-target-offset-global-value`.
- Ran the focused lane-global `1000:3D2D` retry twice. The first run under
  `/tmp/lezac-lane-write-forward-lane-globals-1781610186` kept the queue gate
  at `0x80`, so the matching `0x01/0x8002/0x07be` lane-global rows at score
  `0x78` did not arm the patch; it is recorded as `no_patch`. The corrected
  Windows-temp run
  `C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-lane-globals-q78-1781610284`
  lowered the gate to `0x78`, applied the runtime patch at `2.854s` after the
  bomb with selected bases `209e/663e/c22e` and lane globals
  `0x01/0x8002/0x07be`, and was parsed by the native Windows oracle. It still
  did not freeze or hit natural forward-debris writeback; the summary reports
  `no_freeze_candidates=1`, `ready_candidates=0`, `missing_offsets=3d2d`.
- Ran a follow-up lane-global route/timing variant sweep at
  `C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-lane-global-route-variants-1781610807`
  with routes `x:1.85,c:0.50`, `x:2.15,c:0.50`, `x:2.00,c:0.35`,
  `x:2.00,c:0.65`, and `x:2.00,z:0.35`, still targeting natural
  forward-debris `1000:3D2D`. The native oracle parsed all five candidates.
  Three routes stayed `no_patch`; `x:2.00,c:0.35` patched at `3.614s` and
  `x:2.00,c:0.65` patched at `2.970s`, both with selected bases
  `209e/663e/c22e`, lane globals `0x01/0x8002/0x07be`, and queue score
  `0x78`. Neither froze nor hit the lane write, so the summary reports
  `ready_candidates=0`, `no_patch_candidates=3`, `no_freeze_candidates=2`,
  and `missing_offsets=3d2d`.
- Ran direct q78 lane-global control-flow probes for the two route timings that
  had armed the `3D2D` patch. The `1000:4C96` loop-patch run wrote
  `C:\Users\andrz\AppData\Local\Temp\lezac-lane-global-4c96-probe-1781611559`:
  `x:2.00,c:0.35` patched at `2.769s` and `x:2.00,c:0.65` patched at
  `3.607s`, both with selected bases `209e/663e/c22e`, high-debris target
  offset `0x05bd`, lane globals `0x01/0x8002/0x07be`, and queue score
  `0x78`. The native oracle parsed both candidates as valid original fixtures
  but reported `observed_freeze_count=0`, `observed_effect_forward_call=0`,
  and no lane-write evidence. The paired `1000:4C75` bp4-scratch run wrote
  `C:\Users\andrz\AppData\Local\Temp\lezac-lane-global-4c75-probe-1781611676`:
  the same two timings patched at `2.680s` and `2.708s`, recorded scratch
  site `01ED:4C7E` / old bytes `2001`, and the oracle still reported
  `observed_freeze_count=0`, `observed_high_word_gate=0`, and
  `bp4_local_present=0`. Narrow conclusion: once the q78 lane-global predicate
  installed these patches, neither `4C75` nor `4C96` was reached later in the
  sampled/tail window. This brackets the current miss as an earlier
  control-flow/predicate question, not another nearby lane-global timing
  question.
- Ran earlier branch-window probes for the lane-global timing variants. For
  `x:2.00,c:0.35`, the selected-base `1000:4C75` bp4-scratch run at
  `C:\Users\andrz\AppData\Local\Temp\lezac-early-4c75-selected-base-1781613438`
  armed at `2.002s` with selected bases `209e/663e/c22e`, high-debris target
  offset `0x05bd`, and pre-final lane globals `0x00/0x0002/0x07bc`, but the
  oracle still reported no freeze, high-word gate, bp4 local, or lane write.
  The matching selected-base `1000:4B3F` run at
  `C:\Users\andrz\AppData\Local\Temp\lezac-early-4b3f-selected-base-1781613513`
  armed at `2.045s` with the same selected bases and also did not freeze.
  Timed `4C75` reruns at
  `C:\Users\andrz\AppData\Local\Temp\lezac-early-4c75-timed-1781613603`
  (`after_bomb=1.0`),
  `C:\Users\andrz\AppData\Local\Temp\lezac-early-4c75-after0-1781613674`
  (`after_bomb=0.0`), and
  `C:\Users\andrz\AppData\Local\Temp\lezac-early-4c75-before-bomb-1781613747`
  all loaded the patch with the early `2093/6620/c22e` state and no observed
  high-word-gate hit. Finally, before-bomb `1000:4B3F` loop patches at
  `C:\Users\andrz\AppData\Local\Temp\lezac-early-4b3f-before-bomb-1781613826`
  (`x:2.00,c:0.35`) and
  `C:\Users\andrz\AppData\Local\Temp\lezac-early-4b3f-before-bomb-c0p65-1781613903`
  (`x:2.00,c:0.65`) loaded but did not freeze. Narrow conclusion: these two
  `c` timing variants can expose late sampled lane state, but they are not
  useful natural `3D2D` branch-execution routes under the current bomb timing.
- Added `tools/sweep_original_branch_anchor_routes.py`, a guarded route
  classifier for the high-debris branch anchors `1000:4B3F`, `1000:4C75`, and
  `1000:4C96`. Its default dry-run matrix covers routes `x:2.00`,
  `x:2.00,c:0.35`, `x:2.00,c:0.65`, and `x:2.00,m:0.35` with before-bomb
  runtime patching, and it can also classify selected-base and after-bomb
  timing modes before spending another natural `3D2D` run. Added
  `tools/check_branch_anchor_route_sweep.py` plus CTest dry-run coverage for
  the command shapes, selected-base gates, Windows `.exe` oracle path
  translation, repo-output refusal, bad routes, and live approval refusal.
- Ran the new branch-anchor classifier under WSL/DOSBox, writing the default
  bundle to
  `C:\Users\andrz\AppData\Local\Temp\lezac-branch-anchor-default-1781615578`.
  Across `x:2.00`, `x:2.00,c:0.35`, `x:2.00,c:0.65`, and
  `x:2.00,m:0.35`, only `x:2.00,m:0.35` produced positive branch-anchor
  freezes in the default matrix: `1000:4C75` (`bp4_local_value=0x8002`) and
  `1000:4C96`. The successful frames
  `high_debris_word_gate\before_bomb\x2p00_m0p35\091_tail_freeze_check.png`
  and
  `effect_forward_pass_call\before_bomb\x2p00_m0p35\091_tail_freeze_check.png`
  were visually inspected and show the expected level-1 route window.
- Ran the focused all-anchor classifier for `x:2.00,m:0.35`, writing
  `C:\Users\andrz\AppData\Local\Temp\lezac-branch-anchor-m-all-1781616282`.
  This route reached `1000:492F`, `1000:4B3F`, `1000:4B61`, `1000:4B6A`,
  `1000:4C75`, and `1000:4C96`, but not `1000:4C20` or `1000:4CA9`.
  The positive `4B3F` and `4B6A` tail frames were visually inspected. The
  useful narrow reading is that `x:2.00,m:0.35` is now a proven
  branch-execution route into the zero-target/high-word/forward-call side of
  the high-debris consumer, while the reverse call and nonzero-target branch
  remain unobserved for this timing.
- Retried natural forward debris writeback `1000:3D2D` on that same
  `x:2.00,m:0.35` route, writing
  `C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-m-route-1781616090`.
  The runtime patch applied at `2.781s` after the bomb with selected bases
  `2941/665c/c22e`, target byte `0xde`, queue score `160`, debris/collapse
  counts `202/5`, and lane globals `0x00/0x0004/0x072c`, but it did not freeze
  or record a natural forward-debris lane write. The lane-write summary
  classifies the single candidate as `no_freeze_candidates=1`,
  `ready_candidates=0`, `missing_offsets=3d2d`. Frames
  `043_sample_2p00s.png` and `091_tail_freeze_check.png` were visually
  inspected: the capture reaches visible blast/smoke playback and then
  continues into normal level playback, so this is valid negative route
  evidence rather than a launch/menu failure.
- Probed the forward helper path on the same `x:2.00,m:0.35` route. The
  `1000:4C99` return capture at
  `C:\Users\andrz\AppData\Local\Temp\lezac-helper-path-4c99-m-route-1781617322`
  froze after the `4C96 -> 3BB2` helper call returned with selected bases
  `2941/665c/c22e`, target byte `0xde`, and lane globals
  `0x00/0x0004/0x072c`. The `1000:3CE3` lane-divide capture at
  `C:\Users\andrz\AppData\Local\Temp\lezac-helper-path-3ce3-m-route-1781617440`
  froze with `lane_div_kind=forward`, active count/index `1/1`, numerator
  `0xffff:0xfff3`, and weight `0x0021`. The `1000:3D1B` lane-write capture at
  `C:\Users\andrz\AppData\Local\Temp\lezac-helper-path-3d1b-m-route-1781617379`
  froze with `lane_write_kind=forward`, target `collapse`, output `0x0000`,
  `DI=0x001e`, tag `0x0002`, active count/index `1/1`, and result local
  `0x0000`. The `091_tail_freeze_check.png` frame was inspected for all three
  runs and stayed in the expected level-1 playback window. This proves the
  `m:0.35` route reaches through the forward helper and naturally writes a
  collapse lane, while the missing `3D2D` write is explained by the helper's
  active tag being below the debris marker base `0x4e20`.
- Ran a follow-up forward-helper tag search at
  `C:\Users\andrz\AppData\Local\Temp\lezac-forward-helper-tag-search-1781617957`
  across routes `x:1.50,m:0.35`, `x:2.50,m:0.35`, `x:2.00,m:0.15`, and
  `x:2.00,m:0.65`, targeting `1000:3D1B` and `1000:3D2D` with before-bomb
  runtime patching. The sweep summary reports `candidates=8`,
  `observed_freezes=2`, `ready_candidates=2`, `no_freeze_candidates=6`, and
  `missing_offsets=3d2d`. Both positive routes were `3D1B` collapse writes:
  `x:2.00,m:0.15` and `x:2.00,m:0.65` froze with output `0x0000`,
  `DI=0x004b`, tag `0x0005`, active count/index `1/1`, high-debris target
  byte `0xde`, and `observed_lane_debris_write=0`. Their paired `3D2D`
  candidates patched cleanly but did not freeze or record any lane write.
  Frames `x2p00_m0p15\3d1b\091_tail_freeze_check.png`,
  `x2p00_m0p15\3d2d\091_tail_freeze_check.png`, and
  `x2p50_m0p35\3d2d\091_tail_freeze_check.png` were visually inspected and
  stayed in the level-1 explosion/playback window. This confirms that nearby
  `m` timing variants still exercise collapse-tag helper iterations, not a
  natural debris-marker writeback state.
- Ran a broader forward-helper tag subset from the expanded route matrix at
  `C:\Users\andrz\AppData\Local\Temp\lezac-forward-helper-expanded-tag-subset-1781622932`.
  Routes `x:1.75`, `x:2.25`, `x:2.00,c:0.25`, `x:2.00,c:0.75`, and
  `x:5.00,m:0.50,x:2.00` were each captured against `1000:3D1B` and
  `1000:3D2D` with before-bomb runtime patching. The summary reports
  `routes=5`, `candidates=10`, `observed_freezes=0`, `ready_candidates=0`,
  `no_freeze_candidates=10`, and `missing_offsets=3d1b,3d2d`; every candidate
  patched and parsed as a valid no-freeze fixture. Tail frames
  `x1p75\3d2d\091_tail_freeze_check.png`,
  `x2p00_c0p25\3d2d\091_tail_freeze_check.png`, and
  `x5p00_m0p50_x2p00\3d2d\091_tail_freeze_check.png` were visually inspected
  and stayed in live level-1 playback. These routes should not be repeated as
  natural forward-helper tag candidates without a new control-flow predicate.
- Added `--route-preset forward-helper-tag-open` to
  `tools/sweep_original_lane_write_routes.py` for the two remaining unpruned
  level-1 helper-tag routes from the expanded matrix:
  `x:3.00,z:0.50,x:2.00` and `x:1.50,left:0.50,x:2.00`. CTest now pins the
  dry-run command shape when paired with `--offset forward-collapse`,
  `--offset forward-debris`, `--runtime-freeze-preset none`, and
  `--runtime-freeze-before-bomb`, so the next DOSBox-capable run can classify
  those routes without rerunning the full pruned matrix.
- Ran that focused preset at
  `C:\Users\andrz\AppData\Local\Temp\lezac-forward-helper-tag-open-nosamples-1781623828`
  after an initial sampled attempt under
  `...\lezac-forward-helper-tag-open-1781623743` failed on the second capture
  with a `/proc/<pid>/mem` `PermissionError` during route-state sampling. The
  rerun disabled route-state samples with `--route-state-interval 0` and
  completed both routes against `1000:3D1B` and `1000:3D2D`. The summary
  reports `routes=2`, `candidates=4`, `observed_freezes=0`,
  `ready_candidates=0`, `no_freeze_candidates=4`, and
  `missing_offsets=3d1b,3d2d`; the updated helper-tag classifier reports
  `debris_tag_candidates=0`, `collapse_tag_candidates=0`, and
  `max_lane_write_tag=none`. All four candidates patched and parsed as valid
  no-freeze fixtures. Route and tail frames for both `3D2D` captures were
  visually inspected and stayed in live level-1 playback. This closes the
  reviewed level-1 helper-tag route family under the current before-bomb
  patching setup.
- Added `--continue-on-oracle-error` to
  `tools/sweep_original_lane_write_routes.py`. Capture failures still stop the
  sweep, but a missing or unrunnable C++ oracle now writes an `oracle_error`
  status and keeps route captures/candidate fixtures for later parsing. This
  matches the local WSL attempt where route `x:2.00` produced a `1000:3D2D`
  candidate bundle under `/tmp/lezac-lane-write-forward-expanded`, but the
  stale Linux `./build/lezac_cpp` on the Windows mount failed with
  `Input/output error`.
- Added `--debug-bonus-reward-static-model` to pin the monster reward score
  table against shipped `LEZAC.EXE` bytes. The diagnostic validates MZ image
  base `0x0770`, file offset `0xb1c6` / Ghidra offset `1000:aa56`, the seven
  little-endian scores `2000,1000,1500,2000,3000,1000,5000`, the current C++
  bonus sprite mapping `61..67`, and `BOMOMIMK.SPR` bounds for those reward
  sprites.
- Added `--debug-actor-contact-static-model` to pin the shipped executable
  control-flow anchors for the actor/contact recovery path from the C++
  diagnostic binary: scanner entry/return `1000:5CB0..604F`, actor-update
  entry/return `1000:6053..777F`, the three `[bp-31h]` dispatch gates
  `1000:654E=06`, `1000:65A2=05`, and `1000:7595=05`, `scanner_call_count=1`
  for the sole scanner call at `1000:6555` in the `06` gate context, and the
  direct integration jumps to `1000:73E5`.
- Added `--debug-lane-write-static-model` to pin the original executable bytes
  behind the four lane writeback stores: forward/reverse collapse at
  `1000:3D1B`/`1000:3EAF`, forward/reverse debris at
  `1000:3D2D`/`1000:3EC1`, the collapse skip jumps, debris marker arithmetic
  `(tag - 0x4e20) * 0x0b`, and the shared far-result tail. This keeps the
  pending natural `3D2D` capture plan tied to original bytes without promoting
  new gameplay behavior.
- Added `--debug-sprite-layout-static-model` to pin the original `.SPR` bank
  count/header/payload layout directly from shipped `BOMOMIMK.SPR`,
  `PROVA.SPR`, and `FONTS.SPR` bytes. The diagnostic validates per-bank file
  sizes, sprite counts, pixel/zero/`0xff` counts, first/last dimensions, max
  dimensions, aggregate totals, and zero trailing bytes independently of the
  JSON round-trip loader.
- Hardened `tools/run_native_windows_validation.ps1` against missing
  `SDL2.dll` launch failures on Windows by copying the validated vcpkg runtime
  beside the freshly built `lezac_cpp.exe` after MSBuild and printing the
  `runnable_exe=...` path to launch directly.
- Added `--debug-end-flow-static-model` to pin the original
  `1000:1B14..1D42` post-game dispatcher against shipped executable bytes. The
  diagnostic validates the game-over/completed-game string branches,
  `DS:208c` completed-game flag write, player score pointers
  `DS:785a`/`DS:7888`, display markers, key latch `DS:2058`, strict seventh
  record cutoff comparison against `DS:1b52`/`DS:1b54`, and the near call back
  to `1000:1845` for qualifying name-entry prompts.
- Added `--debug-record-entry-static-model` to pin the original
  `1000:1845..1AD6` high-score entry/storage byte model. The diagnostic
  validates the `CS:183c` eight-colon empty-name template, 13-byte record
  stride calculations, 13-byte table shift copy, 8-byte name copy to record
  offset `+4`, dword score writes at offset `+0`, Backspace/Enter key checks,
  and prompt/commit sound requests.
- Added `--debug-sound-loader-static-model` to pin the original
  `1000:0630..06AA` `PROEFS.SON` loader against shipped executable bytes. The
  diagnostic validates the `proefs.son` filename anchor, `0x0082` step-count
  constant, two-byte count read into `[BP-0x82]`, `count * 6` payload-size
  sequence, and second block read through `DS:79c0`, matching the 130 six-byte
  sound-step model used by the C++ port.
- Added `--debug-level-completion-denominator` to pin the live level-completion
  gate to the recovered `LIVELS.SCH` `fieldB` denominator. With objective counts
  forced complete, the diagnostic verifies that every shipped level remains
  incomplete one physical-damage count before
  `ceil(requiredDestruction * fieldB / 100)` and completes exactly at that
  threshold, while keeping `fieldA` semantically unresolved.
- Added `--debug-sound-latch-static-model` to pin the original
  `1000:165A..167D` priority latch against shipped executable bytes. The
  diagnostic validates the inactive accept jump, active
  `(DS:799e - 1) >= DS:799f` reject jump, accepted cursor/priority copies from
  `DS:2074`/`DS:799f`, and final `DS:79c4 = 1` active-flag write.
- Added `--debug-sound-tick-static-model` to pin the original
  `1000:0FBE..1088` PC-speaker tick routine against shipped executable bytes.
  The diagnostic validates the direct-sweep branch, `cursor * 6 - 6`
  `PROEFS.SON` step address calculation, stop sentinel `0x7530`, entry reads at
  offsets `+0`, `+2`, and `+3`, and zero checked tail-read patterns for
  preserved playback-unused bytes `+4..+5`.
- Extended `--debug-shipped-file-manifest` to verify the original executable's
  lowercase runtime filename anchors. The diagnostic now pins ten unique names,
  15 total references, `proefs.son` at `1000:0626`, `gran.mst` at
  `1000:2AD4`, `livels.sch` at `1000:2EF3`, two `recs.dat` references, and
  five `fonts.spr` references without changing `GRAN.MST` from opaque data.
- Recovered the static bomb-placement sound request at
  `1000:557b..5586`: the original writes `DS:2074 = 0xea74`,
  `DS:799f = 3`, and calls the `1000:165a` latch after the successful
  placement branch. The live C++ `placeBombAt` path now uses
  `requestBombPlaceSound` instead of a direct compatibility `playSound(index)`
  call, and `--debug-bomb-place-sound` pins the queued direct-sweep request.
- Added `--debug-static-sound-requests` to scan the shipped `LEZAC.EXE` image
  and lock all 27 immediate writes to `DS:2074`. The diagnostic pins
  21 near-latch candidates, 22 near-latch call references, five direct-sweep
  writes, 17 mapped callsites, and 10 remaining unpromoted static sound
  candidates for future recovery. It now prints the full mapped-label ledger
  and the exact unresolved queue:
  `0x1d9c,0x202d,0x2c04,0x49bd,0x4b2c,0x4d3c,0x4dd3,0x5e81,0x7386,0x789c`.
  Each unresolved write is now classified with a factual label such as
  `post_end_flow_record_region`, `record_table_cursor_only`,
  `collapse_playback_rejected`, `non_objective_tile_gate_rejected`, or its
  cursor/priority shape.
- Added `--debug-static-sound-unresolved-contexts` to pin the byte windows and
  local latch/priority shape for those 10 unpromoted writes individually. The
  command verifies seven local `1000:165a` latch calls, four inline priority
  writes, two preceding priority writes, four no-local-priority cases, three
  no-latch cases, and the two `0x2710` cursor writes. It now also prints
  static region buckets for those candidates:
  `record_ui:2`, `pre_new_game_setup:1`, `explosion_playback:2`,
  `effect_extent_scan:2`, `contact_scanner:1`, `actor_update:1`, and
  `post_actor_update_no_latch:1`, without treating any of them as a recovered
  live gameplay cue.
- Switched live state-2 death rendering to the recovered row-byte-3
  `BOMOMIMK` sprite sequence `67..72` for frames `0x4a..0x4f`, now drawn with
  an explicit DS:C21E-style effect-entry base `104,168` plus the row-byte-0/1
  offset candidates `16,16`. The `death_visuals` autoplayer pins live sprites
  `67,68,69`, effect-entry frames `0x4a..0x4c`, and that draw offset against
  the old cursor-index sequence `74,75,76`, while the frame-comparison workflow
  keeps `visual_claim=0` until paired original screenshots are promoted
  separately.
- Extended `tools/capture_original_sound_callsite_debug.sh` and its guardrail
  to stage `bomb_place_sound` runtime captures alongside the existing mapped
  sound-callsite scenarios.
- Recovered the static monster-death/reward sound request at
  `1000:5c9e..5ca9`: the surrounding original helper writes death-state actor
  fields, pushes the `0x03e8` score value, then writes
  `DS:2074 = 0x003d`, `DS:799f = 12`, and calls `1000:165a`. The live C++
  `enterMonsterDeath` path now uses `requestMonsterDeathSound`, and
  `--debug-monster-death-sound` pins the queued non-direct request.
- Extended the static sound request diagnostic and sound-callsite capture
  helper for `monster_death_sound`; the static map now has 15 recovered
  immediate-write callsites and 12 remaining unlabeled candidates after the
  record/name-entry and records-page UI sound routes were promoted.
- Fixed the native Windows build packaging path by copying the discovered
  `SDL2.dll` beside `lezac_cpp.exe` after build, so CTest and manual launches no
  longer depend on an external `PATH` entry for SDL2.
- Added `--route-preset forward-debris-expanded` to
  `tools/sweep_original_lane_write_routes.py` and pinned its dry-run command
  matrix in CTest. The preset keeps the remaining natural forward debris
  writeback target (`1000:3D2D`) focused on a reviewed ten-route plan when
  combined with `--offset forward-debris`, while the existing default
  `3D2D`/`3EC1` matrix remains unchanged.
- Live DOSBox capture for that `3D2D` target was not attempted in this local
  continuation because `wsl.exe -d Ubuntu` reports
  `WSL_E_DISTRO_NOT_FOUND`; the expanded matrix is ready for the next
  DOSBox/process-memory-capable run.
- 2026-06-16 WSL named-distro evidence is usable again: `wsl.exe -d Ubuntu --`
  runs the repo under `/mnt/c/...`, `preflight_original_evidence_environment.py
  --require-debug-capture` passes with `dosbox-debug`, `xvfb-run`, `xdotool`,
  `zutty`, and `script` found, and a live `records_page_sound`
  `tools/capture_original_sound_callsite_debug.sh` run reached DOSBox-debug
  from a temp copy. It timed out at the debugger prompt instead of producing a
  promoted fixture, but the helper now reports
  `reason=dosbox_debug_timeout runtime_metadata=observed runtime_cs=01ED
  runtime_ds=01DD` and writes the translated runtime command plan
  (`BP 01ED:2083`, `BP 01ED:165A`, `D 01DD:2070`, `D 01DD:78C0`,
  `D 01DD:7990`, `D 01DD:79C0`) for the next interactive/debugger-input pass.
- Implemented the recovered delayed state-2 life decrement in the live C++
  port. Fatal damage now enters state 2 with the visible life count unchanged,
  keeps a pending life-loss flag while the `0x003c` death countdown runs, and
  consumes the life only when that countdown reaches zero before manual reentry
  or restart can proceed.
- Updated death/reentry, damage-sound, monster-contact, two-player, smoke, and
  active collapse-hazard diagnostics so they assert the pending-life window and
  final delayed decrement. The live collapse-hazard frame diagnostic now pins
  its fixture incomplete-but-reenterable, inspects rendered frames, reaches
  state 2 at frame 101, and observes life consumption after the 60-tick delay.
- Extended `--debug-original-state2-return-model` to cover the static
  `1000:7ef8..7f2a` fallback path. The model now asserts that the fallback is
  blocked while `DS:79b8` has active players, increments the `DS:79b9`
  counter only with no active players, promotes state byte `2` to `1`, and
  preserves actor state/energy because it is not the normal
  `1000:7e85..7ea7` return-to-active restore.
- Extended `--debug-player-state2-return-active` with a live C++ fallback
  boundary: player 2 stays out after final-life state-2 countdown, manual
  reentry stays blocked while player 1 remains active, and game over occurs
  only after player 1 also loses the final life. The diagnostic reports
  `live_fallback_shortcut=0` and `original_reachability=0`.
- Tightened `--debug-record-name-entry` so high-score entry now locks the
  recovered eight-byte storage behavior in addition to accepted keys: short
  names are colon padded, spaces serialize as colons in `encoded_name`, and
  overlong input is capped at eight stored characters. The diagnostic now also
  pins the original empty-name template from `CS:183c`: pressing Enter on an
  untouched prompt stores raw `::::::::`, which decodes as `nessuno`, while a
  typed `nessuno` preserves distinct raw bytes `nessuno:`.
- Added a visible name-entry cursor box to the C++ renderer and
  `--debug-record-name-entry-cursor` frame inspection. The diagnostic verifies
  the active slot starts at position 0, advances after typed letters, returns
  after Backspace, and restores the prior rendered frame.
- Added `--debug-record-name-entry-repeat` to exercise SDL repeated keydown
  events through the normal event queue. Name entry now accepts repeated
  letters/space and Backspace, ignores repeated Enter/Escape so commit/cancel
  are edge-triggered, and commits the repeated-input name through a temporary
  binary `RECS.DAT`-format file.
- Added `--debug-menu-frame-flow` dummy-SDL frame inspection for the current
  menu implementation. It verifies distinct rendered main/info/instructions/
  records pages, pumps the recovered records-page sound request, checks
  visible gameplay background-toggle frame changes, starts one-player gameplay,
  returns to the menu, and confirms main-menu Escape requests exit.
- Tightened `control_smoke` so the current port's shipped-manual performance
  controls are visible in CTest output: `s` toggles the background with frame
  inspection, the current `r/e` mapping shrinks and restores one-player
  playfield width `320->288->320`, and the same width keys remain locked out
  during two-player play.
- Added `--debug-end-flow-frame-flow` dummy-SDL coverage for the current
  game-over and completed-game presentation. The diagnostic frame-inspects
  below-cutoff game-over scores, drives natural final-level completion into the
  completed-game page, and verifies both confirmations redraw the main menu and
  clear retained score state.
- Added `--debug-core-resource-raw-roundtrip` to pin `BOMPAL.PAL`,
  `SFONLEF.ZBG`, and `CARO.CAR` against their converted JSON resources. It
  compares decoded palettes, background RLE expansion, and tile payload bytes,
  then locks palette size/sum/XOR, background raw size `34292`, decoded pixel
  count `124548`, tile count `132`, and CARO payload size `8448` in CTest.
- Added `--debug-shipped-file-manifest` to pin the complete 14-file shipped
  oracle set used by conversion, Ghidra notes, and original-runtime fixtures.
  CTest now fails if any source file fingerprint drifts, and the command also
  locks `LEZAC.EXE` as an MZ binary with size `52384`, image base `0x0770`,
  and image size `50480`.
- Made the tested original-asset path the default runtime loader and copy the
  shipped resources beside the built executable. `LEZAC_LOAD_JSON_ASSETS=1`
  still forces the JSON compatibility path, while `--debug-original-asset-load`
  proves both paths match exactly for palettes, background, tiles, sprite banks,
  records, `PROEFS.SON`, `GRAN.MST`, and `LIVELS.SCH`.
- Added `--debug-records-raw-roundtrip` to pin original `RECS.DAT` against the
  converted JSON resource: raw size `92`, seven 13-byte records, top score
  `541200`, cutoff `474930`, score sum `3508890`, all level `8`, all encoded
  names `aga:::::`, byte sum `6047`, weighted sum `278918`, and XOR `0xdd`.
- Switched high-score persistence to original binary `RECS.DAT` format for
  non-`.json` paths, including the default runtime path. `--debug-record-update`
  now locks the 92-byte temp `.dat` output and retains explicit `.json`
  compatibility coverage.
- Tightened `bonus_rewards` CTest coverage so the recovered bonus-pickup sound
  request is pinned as cursor `0x0008` at priority `5`, matching the
  `1000:6e4b..6f8d` evidence path already used by `collectBonusDrop`. The live
  path now uses `kBonusPickupSoundCursor` and `kBonusPickupSoundPriority`
  instead of raw literals.
- Pinned deterministic CTest output for monster blast rewards, trigger rewrite
  accounting, and portal cooldown/key handling so those recovered gameplay
  diagnostics no longer rely on exit status alone.
- Pinned `--debug-sound-render` CTest output for all six compatibility cursor
  starts plus aggregate sample/nonzero counts, keeping recovered `PROEFS.SON`
  synthesis from drifting silently.
- Centralized the recovered explosion direct-sweep offsets and selectors in
  `kExplosionDirectSweepSoundOffsets` and `kExplosionSoundSelectors` so the
  `1000:414a` sound mapping no longer lives as repeated raw literals.
- Tightened the default `--validate` CTest entry so the original-asset default
  path must report the same level-7 shape already pinned by the explicit JSON
  and original-asset validation modes.
- Made `--smoke-ui` report its inspected frame count and pinned both headless
  UI smoke checks in CTest, so dummy-SDL rendering/control regressions no
  longer pass on exit status alone.
- Added `tools/check_sound_compatibility_hooks.py` to keep the two remaining
  `playCompatibilitySound` routes explicit as named compatibility hooks that
  still funnel to `playSound(index)` until original cursor/priority writes are
  recovered.
- Extended the static sound diagnostic and compatibility-hook checker to report
  `remaining_compat_hooks=objective_pickup,level_complete` and the rejected
  objective-sound candidates
  `0x4b2c:collapse_playback,0x6d75:bomb_object_high_gate,0x6924:non_objective_tile_gate`.
  This keeps the known collapse playback branch, bomb-object high gate, and
  non-objective tile gate from being reused as objective-pickup mappings.
- Added `--debug-remaining-sound-compat-hooks` to exercise the live C++
  objective-pickup and level-complete compatibility paths. It reports the
  indices/cursors used by those compatibility hooks plus
  `latch_preserved=1`,
  `capture_blockers=objective_pickup:rejected_static_candidates,level_complete:no_static_candidate`,
  and `original_cursor_priority_claim=0`, so the checker now proves the hooks
  are reached without mutating a seeded recovered latch while naming why
  neither hook is currently eligible for a sound-callsite DOSBox capture
  promotion.
- Added `--debug-static-sound-contexts` to pin the original byte contexts for
  `0x1857`, `0x1a44`, `0x1d9c`, `0x202d`, and `0x2083` as
  name-entry/post-end-flow-record/record-table UI sound writes. It verifies the
  `1000:1b14..1d42` end-flow dispatcher boundary and nearby strings
  `inserisci il tuo nome`, `bomba bonus`, and `punteggi migliori`, then reports
  `level_complete_static_candidate=none` so the live level-complete
  compatibility hook cannot be replaced by those unrelated static writes.
- Extended `tools/capture_original_sound_callsite_debug.sh`, its checker, and
  dry-run CTest matrix for the statically pinned record/name-entry sound
  callsites `record_name_prompt_sound`, `record_name_commit_sound`,
  `post_end_flow_record_sound`, and `records_page_sound`. The cursor-only
  `0x202d` record-table write remains unstaged until runtime evidence proves
  the pending priority at that callsite.
- Recovered the live high-score name-entry sound requests from those static
  contexts: entering the prompt queues cursor `0x0078` at priority `11`
  (`1000:1857`), and pressing Enter queues cursor `0x0008` at priority `11`
  (`1000:1a44`) before the record table update. `--debug-record-name-sound`
  now pumps and asserts both requests through the recovered `1000:165a` latch.
- Recovered the main-menu records-page sound wrapper at `1000:2079..2094`:
  opening the records page queues cursor `0x0024` at priority `2` immediately
  before the `punteggi migliori` text. `--debug-records-page-sound` now asserts
  that live transition, while the cursor-only `1000:202d` record-table write
  remains staged.
- Extended `--debug-end-flow-records` with the original-style two-player
  threshold re-check: player 2 can qualify against the old seventh-place score,
  but is skipped after player 1 inserts a higher record and raises the table
  cutoff.
- Tightened record failure/cutoff diagnostics: `--debug-end-flow-records` now
  locks that a score equal to the current seventh-place record does not qualify,
  and `--debug-record-save-failure` verifies that a failed save preserves the
  pending name-entry score/name until a later writable-path retry commits it.
- Promoted natural, non-seeded original-runtime evidence for forward final
  lane-result writeback: `explosion_playback_oracle_original_3d3f_lane_result_runtime_natural.txt`
  captures route `x:2.00` reaching `1000:3D3F` with runtime
  `CS=01ED` / `DS=0C8F`, scratch `CS:F280`, result output `0x0002`,
  far destination `0C44:78D2`, target-before byte `0x21`, and
  `visual_claim=0`.
- Promoted natural, non-seeded original-runtime evidence for reverse debris
  lane writeback:
  `explosion_playback_oracle_original_3ec1_lane_write_runtime_natural.txt`
  captures route `x:2.00,m:0.35` reaching `1000:3EC1` with runtime
  `CS=01ED` / `DS=0C8F`, scratch `CS:F080`, output `0x00fb`, tag
  `0x4ee8`, `DI=0x0898`, active/loop counters `0x0005`/`0x0002`, and
  `visual_claim=0`.
- Updated `docs/recovery/runtime_evidence_ledger.md`,
  `docs/recovery/original_runtime_fixture_notes.md`, CMake oracle tests, and
  recovery notes so the new fixtures remain non-visual temp-copy runtime
  evidence and are covered by the ready-result and runtime-ledger guardrails.
- Added `--debug-sound-callsite-oracle <fixture> [--expect-error]` with
  synthetic and malformed DOSBox fixture coverage. The oracle normalizes
  original sound request/latch stops around `1000:165a`, checks runtime
  `CS`/`DS`, callsite breakpoints, `DS:2074`/`DS:799f` pending request bytes,
  `DS:78c0`/`DS:799e` latched state, and `DS:79c4` active state while keeping
  the evidence `visual_claim=0`.
- Added `tools/capture_original_sound_callsite_debug.sh` plus checker and
  dry-run CTest coverage for mapped or statically pinned sound scenarios:
  `bomb_object_sound`, `bomb_place_sound`, `monster_death_sound`,
  `portal_teleport_sound`, `tile_trigger_sound`, `bonus_pickup_sound`,
  `player_damage_sound`, `player_death_sound`, `record_name_prompt_sound`,
  `record_name_commit_sound`, `post_end_flow_record_sound`, and
  `records_page_sound`. The helper writes debugger-seeded manifests, command
  plans, raw dumps, and fill-in `sound_callsite` candidate fixtures for
  `--debug-sound-callsite-oracle`.
- Tightened `--debug-autoplayer death_visuals` so the live death-route
  regression now inspects the recovered row-byte-3 state-2 visual renderer for
  frames `0x4a..0x4c`. The command pins the DS:C21E-style effect-entry base
  `104,168`, live sprites `67,68,69`, row-byte-0/1 draw offset `16,16`, old
  cursor-index sprites `74,75,76`, and hash mismatches between the two render
  paths while preserving `visual_claim=0`.
- Updated `tools/sweep_original_lane_result_routes.py` so natural `3D3F`
  route sweeps now delegate the selected C++ oracle binary to each per-route
  capture helper, report oracle command counts during dry-run planning, and
  preserve `cpp_exe` / `skip_oracle` / delegated oracle commands in the parent
  sweep manifest. The planner now also validates `--offset` aliases during
  dry-run planning, rejecting non-lane-result offsets before any capture plan is
  trusted. This brings the lane-result route planner in line with the lane-write
  route planner before the next DOSBox-capable run.
- Locked the shipped `LIVELS.SCH` embedded level words in
  `--debug-level-raw-roundtrip`: `fieldA` stays raw with `0x4000` prefix and
  payloads `5,30,54,60,102,159,65`, while `fieldB` is pinned to
  `0x0042,0x0189,0x02e3,0x01b3,0x03dc,0x0aa4,0x014a` and total `5675`.
  Added CTest coverage for `--debug-word-layer` to keep the negative
  `fieldA` candidates explicit: the low physical-word count matches `fieldB`
  on all seven levels, but the `fieldA & 0x3fff` payload matches high-word
  counts only once and high connected components zero times.
- Added `tools/summarize_lane_write_ready_results.py` plus synthetic result and
  end-to-end pipeline CTest coverage, completing the lane-write handoff from
  route-sweep promotion through ready-manifest execution into a gated result
  summary. The result summary preserves the lane-write kind/target metadata,
  validates runtime `CS`/`DS` and fixture provenance, checks run/dry-run status
  consistency, and gates executed oracle logs before any recovery claim can
  advance.
- Added `tools/run_lane_write_ready_manifest.py` and synthetic CTest coverage
  so ready natural debris-write candidates can be dry-run, oracle-checked, and
  logged from the manifest emitted by `summarize_lane_write_route_sweep.py`.
  The runner validates the `lane_write_ready_candidates` promotion shape,
  route/offset/kind/target metadata, runtime `CS`/`DS`, fixture guardrails, and
  output paths before executing any oracle.
- Added `tools/summarize_lane_write_route_sweep.py` and synthetic CTest
  coverage for lane-write sweep results. The summarizer classifies
  `3D2D`/`3EC1` candidates as ready, no-freeze, incomplete, or missing, checks
  the lane-write patch mode, scratch offset, expected kind/target, original
  runtime bytes, and required scratch fields, and can write a ready-candidate
  manifest without editing checked-in fixtures.
- Added `tools/sweep_original_lane_write_routes.py` for the next natural
  debris-side evidence pass. The guarded dry-run matrix targets
  `1000:3D2D` and `1000:3EC1` across the existing route variants, defaults to
  the playback-adjacent `late-collapse` runtime-freeze gate, records stable
  route/offset labels, and can optionally emit oracle commands for produced
  `--debug-explosion-playback-oracle` candidates.
- Added `tools/check_lane_write_route_sweep.py` plus CTest dry-run coverage so
  the lane-write batch refuses repository output, missing approvals, missing
  runtime-freeze gates, malformed routes, and invalid lane-result offsets such
  as `3D3F`. This is capture tooling only; no live C++ playback behavior
  changed.
- Recorded the 2026-05-23 Windows original-evidence blocker in
  `docs/recovery/original_evidence_blocked_windows_2026-05-23.md`: original
  assets are present and `wsl.exe` exists, but there is no default WSL distro,
  so frame capture is missing usable `bash`, `dosbox`, `xvfb-run`, and
  `xdotool`. The note is explicitly `not_original_evidence=1` /
  `visual_claim=0` and preserves the preflight, compare, and promotion-ready
  summary commands for the next WSL/cloud run.
- Added `tools/check_original_evidence_blocker_note.py` and CTest coverage so
  that blocker note stays machine-readable and cannot quietly lose the rerun
  commands or its non-evidence status.
- Extended the blocker note with the 2026-06-16 direct
  `wsl -- bash -lc 'command -v dosbox-debug'` attempt. It fails before Linux
  command execution with `WSL_E_DEFAULT_DISTRO_NOT_FOUND`, remains
  `not_original_evidence=1` / `visual_claim=0`, and is now pinned by the same
  checker.
- Added `tools/check_gran_usage_guardrail.py` to keep `GRAN.MST` as explicitly
  opaque data in the current C++ port. The checker counts all `gran_` source
  references and permits only loading, member storage, validation, and
  debug/roundtrip reporting; any new live gameplay or rendering use fails until
  original evidence proves the semantics.
- Extended the `GRAN.MST` guardrail with a synthetic self-test so the checker
  proves it rejects accidental live `gran_` gameplay/rendering references,
  missing debug-only function ranges, and docs that omit the guardrail pointer.
- Extended `--debug-gran-raw-roundtrip` and `--debug-gran` with opaque
  record-level byte fingerprints. The raw-roundtrip diagnostic now loads
  `GRAN.MST` and `GRAN.MST.json` independently and CTest requires
  `raw_json_match=1` before pinning the shipped 399-byte payload's aggregate
  `byte_sum=12560`, `weighted_sum=337318`, `nonzero_bytes=249`,
  `zero_bytes=150`, `xor=0x0c`, record sums
  `631,2230,1389,1242,1780,2720,2568`, weighted sums
  `18094,59871,40052,35568,63621,65838,54274`, nonzero counts
  `31,41,29,30,33,41,44`, and per-record XOR bytes while still treating
  `GRAN.MST` as opaque data.
- Added `tools/check_visual_claim_guardrail.py` and explicit `visual_claim=0`
  lines to the remaining state-2 DOSBox oracle fixtures. All checked-in DOSBox
  fixtures now have a declared visual claim so parser/runtime evidence cannot
  accidentally masquerade as promoted frame evidence. The checker now also
  gates any future `visual_claim=1` fixture on
  `docs/recovery/visual_claim_promotions.md`, which must name original, C++,
  comparison frame artifacts, a promotion-ready frame-compare bundle, and the
  supporting recovery note. Its CTest self-test now exercises a synthetic
  promoted fixture and verifies missing checked-in comparison artifacts and
  unready bundles are rejected.
- Added `tools/check_runtime_evidence_guardrail.py` plus
  `docs/recovery/runtime_evidence_ledger.md` for original-runtime DOSBox
  fixtures. The guardrail requires each checked-in original capture to be from
  a temp copy, carry runtime `CS`/`DS`, and remain `visual_claim=0` until
  visual-frame evidence is promoted separately. It now also requires each
  ledger entry to point at
  `docs/recovery/original_runtime_fixture_notes.md`, where the supporting note
  must name the fixture explicitly.
- Added `tools/summarize_debug_capture_ready_results.py` and synthetic coverage
  so generic debug-capture ready runs now have the same result-review gate as
  actor-dispatch and lane-result handoffs. The summarizer counts planned,
  executed, failed, and environment-preflight states and can require successful
  executed candidates before promotion. `tools/check_debug_capture_ready_pipeline.py`
  now covers the full generic batch-summary, ready-runner, and result-summary
  handoff with synthetic data.
- Added `--debug-visual-table-oracle <fixture> [--expect-error]` as the next
  visual-fidelity evidence gate. The v1 parser normalizes visual table
  fixtures with scenario/runtime metadata, translated breakpoints, actor
  animation cursor fields, `DS:c322 + 4 * frame` row bytes, sprite bank/index
  candidates, draw offsets, and effect-entry before/after state. Synthetic and
  malformed CTest fixtures currently cover the state-2 death table consumption
  path and keep `visual_claim=0`, so no live renderer behavior changed.
- Promoted the existing original state-2 DOSBox-debug stop into
  `visual_table_oracle_original_state2_runtime.txt`, a renderer-facing
  visual-table oracle fixture for actor frames `0x4a..0x4f`. It locks runtime
  `CS=01ED` / `DS=0C8F`, row addresses `DS:c44a..DS:c45e`, row bytes
  `10,10,7d,43` through `10,10,7d,48`, `DS:c21e` effect placement
  `0x0068,0x00a8` for the stopped `0x4a` frame, and CTest coverage while preserving
  `visual_claim=0`.
- Tightened the visual-table oracle so `sprite_source=row_byte3` is a validated
  relationship rather than a generic runtime draw-call label. The original
  state-2 fixture now proves row byte 3 `0x43..0x48` as the `BOMOMIMK`
  sprite-index candidate range, with malformed coverage for mismatched
  row-byte-3 sprite indices.
- Extended the state-2 runtime-frame oracle output with `row3_sequence=...`.
  The original fixture now reports `43,44,45,46,47,48` across frames
  `0x4a..0x4f`, tying the whole countdown frame range to the same row-byte-3
  sprite-candidate interpretation.
- Extended the same oracle with `row0_sequence=...`, `row1_sequence=...`, and
  `row2_sequence=...`, so the original countdown rows now lock the full raw
  shape `10,10,7d,43..48` across frames `0x4a..0x4f` before any renderer
  field names are promoted.
- Added `--debug-original-state2-visual-row-model`, a conservative C++ model
  for the original state-2 rows. It reports rows `4a:10,10,7d,43` through
  `4f:10,10,7d,48`, row-byte-3 `BOMOMIMK` sprite candidates `67..72`, and
  `visual_claim=0`; live dead-player rendering now consumes that row-byte-3
  sprite sequence and the row-byte-0/1 draw-offset candidates `16,16`, while
  the broader visual claim still waits on paired original-frame comparison.
- Added `--debug-original-state2-visual-row-assets` to verify the row-byte-3
  candidates against the loaded `BOMOMIMK` asset. It records that sprites
  `67..72` are in-bounds `16x16` candidates, captures their nonzero-pixel
  sequence `147,39,67,138,145,76`, and contrasts them with the old
  cursor-index sequence `74..79`.
- Added `--capture-state2-visual-row-preview <out_dir>` to render isolated C++
  preview frames for both the recovered row-byte-3 sequence and the old
  cursor-index sequence. The command writes twelve PPMs plus
  a manifest with hashes and remains `visual_claim=0` until original-frame
  comparison proves which presentation is faithful.
- Added `--capture-state2-visual-row-game-preview <out_dir>` with a debug-only
  cursor-index legacy render switch. It writes full gameplay-context frames for
  both the current row-byte-3 state-2 death renderer (`67..72`) and the old
  cursor renderer (`74..79`).
- Added `tools/compare_state2_visual_row_game_previews.py` and a self-checking
  CTest workflow. The helper turns the current-versus-cursor state-2 game
  previews plus an original-frame directory into a standard frame-compare bundle
  with promotion-ready labels such as `state2_current_4a` and `state2_cursor_4a`.
- Added `tools/capture_original_state2_visual_frames.sh` and contract coverage
  for the state-2 original-frame side of that comparison. The helper writes a
  manifest plus six-frame plan for `state2_death_table_consumption`, keeps the
  route labeled `debugger_seeded`, and remains `visual_claim=0` until a live
  DOSBox/debugger-seeded capture supplies the actual screenshots.
- Added `tools/capture_original_visual_table_debug.sh` for the
  `state2_death_table_consumption` follow-up capture. It mirrors the existing
  DOSBox-debug helper shape with `debugger_seeded` output, environment
  preflight recording, runtime `CS`/`DS` command-plan expansion, and a
  fill-in candidate for `--debug-visual-table-oracle`. The generic debug
  capture summary, batch summary, and ready-manifest runner now understand
  `capture=visual_table`, so promoted visual-table evidence can use the same
  review path as behavior-4 and actor/contact captures.
- Added `tools/check_visual_table_oracle_fixtures.py` and extended the optional
  original-fixture convention gate for `visual_table_oracle_original*.txt`.
  Visual-table parser fixtures now have the same fixture/CMake/source-contract
  coverage as behavior-4, actor-update, and contact-scanner runtime oracles.
- Extended the generic debug-capture ready-manifest runner coverage with a
  synthetic `capture=visual_table` candidate, so the visual-table oracle flag is
  exercised before real state-2 visual-table captures are promoted. The
  ready-result summarizer coverage now carries the same visual-table lane
  through planned/executed result manifests, and the end-to-end generic
  ready-pipeline check now promotes actor-update and visual-table candidates
  together from batch summary through oracle execution and result review.
- Extended the generic debug-capture ready pipeline with a synthetic ready
  `capture=contact_scanner_runtime` candidate. The single-capture summary,
  batch ready-manifest writer, ready-manifest runner, ready-result summarizer,
  and full batch-to-result pipeline now all prove the
  `--debug-contact-scanner-runtime-oracle` handoff before contact-scanner
  DOSBox-debug evidence is promoted.
- Extended the same generic ready pipeline with a synthetic ready
  `capture=behavior4_runtime` candidate while preserving the incomplete
  behavior-4 skeleton failure case. Batch promotion and ready-manifest runner
  coverage now exercise all four runtime oracle families:
  behavior-4, actor-update, contact-scanner, and visual-table.
- Aligned `tools/run_debug_capture_ready_manifest.py` with the actor-dispatch
  and lane-result ready runners: `--allow-missing-fixtures` is now explicitly a
  dry-run-only forensic bypass, and live generic debug-capture ready runs reject
  the flag before parsing candidate fixtures.
- Updated `docs/recovery/ready_fixture_provenance_contract.md` and its checker
  so all three ready-manifest runners must document and enforce that
  dry-run-only missing-fixture bypass rule.
- Hardened the ready-result summarizers for actor-dispatch, lane-result, and
  generic debug-capture handoffs so inconsistent manifests fail if their
  aggregate `failures=` count disagrees with per-candidate `status=error`
  records, if a known status carries an impossible return code, or if indexed
  candidate records appear outside `ready_candidates=`. They now also require
  `mode=run` to contain no planned candidates and `mode=dry_run` to contain
  only planned candidates; mismatched per-candidate oracle flags fail at parse
  time, runtime `CS`/`DS` fields must be valid four-digit segments, recorded
  commands must end with the matching oracle flag and fixture, existing
  fixtures with `runtime_cs`/`runtime_ds` must match the result metadata, and
  existing fixture `visual_claim`/`temp_copy` metadata must remain
  non-visual temp-copy evidence. Checked-in `*original*` DOSBox fixtures under
  `tests/fixtures/dosbox` must also have runtime-evidence ledger entries whose
  docs notes name the fixture before a ready-result summary can promote them.
  The ready-manifest runners now apply the same fixture provenance guardrail
  before dry-run or live oracle execution, so an unledgered original fixture is
  rejected before it can produce a result manifest. The upstream ready-manifest
  writers for debug-capture batches, actor-dispatch sweeps, and lane-result
  sweeps also validate ready fixture provenance before writing promotion
  manifests. `docs/recovery/ready_fixture_provenance_contract.md` and
  `tools/check_ready_fixture_provenance_contract.py` now pin the documented
  contract to the shared validator and all writer/runner/result-summary call
  sites. `--require-success` rejects any remaining unknown candidate statuses
  or missing executed-candidate logs instead of treating them as promotable
  evidence.
- Added `tools/check_frame_compare_workflow.py` to pin the original-vs-C++
  frame comparison bundle contract. The guardrail verifies that
  `tools/compare_original_cpp_frames.sh` still captures C++ frames, attempts
  the DOSBox-original capture, runs `tools/frame_compare.py`, leaves missing
  original labels visible, writes `frame_compare_summary.txt` and
  `manifest.txt`, and keeps generated evidence outside the repository.
- Hardened `tools/capture_original_dosbox_frames.sh` with the shared original
  evidence preflight for screenshot captures. It now records
  `environment_preflight_command`, `environment_preflight.log`, and
  `environment_preflight=ok/error/skipped` in the original-frame manifest before
  DOSBox is launched, including Windows WSL/bash blockers such as
  `wsl_bash_reason=no_default_distro`.
- Hardened `tools/compare_original_cpp_frames.sh` so original-frame capture
  failures still leave a reviewable top-level bundle. The wrapper records
  `original_capture_driver.log`, `original_capture_exit`, original manifest/log
  paths, `compare_exit`, and missing-original summary rows before returning a
  nonzero `frame_compare_bundle=error`.
- Added `tools/summarize_frame_compare_bundle.py` plus synthetic coverage for
  successful, original-capture-failed, and compare-failed bundles. The summary
  reports frame counts, missing originals, compare errors, preflight state,
  `wsl_bash_reason`, and `promotion_ready`, with `--require-promotion-ready`
  for future visual-evidence promotion gates.
- Tightened the visual-claim promotion ledger so future `visual_claim=1`
  fixtures must also name a checked-in `frame_compare_bundle` whose
  `tools/summarize_frame_compare_bundle.py` result is `promotion_ready=1`.
  The visual-claim self-test now rejects missing artifacts, unready bundles, and
  mismatched ledger entries.
- Added `tools/write_visual_claim_promotion_entry.py` plus synthetic coverage
  to emit the exact `visual_claim=1` ledger entry from a checked-in,
  promotion-ready frame-compare bundle. The writer validates fixture/docs paths,
  selects a compared frame with original/C++/diff artifacts, and rejects unready
  bundles before printing a promotion line.
- Added `tools/validate_visual_claim_promotion_candidate.py` as the read-only
  promotion checklist before real ledger edits. It confirms the current fixture
  has exactly one declared visual claim, requires a promotion-ready frame bundle,
  generates the candidate entry, and reuses the committed visual-claim guardrail
  checks against the generated line.
- Added `tools/plan_visual_claim_promotions.py` for batch review of checked-in
  visual-claim promotion candidates. The key/value manifest names each fixture,
  frame-compare bundle, docs note, and optional frame label; the planner runs
  the same dry-run checks per candidate, prints ready ledger entries, and can
  fail with `--require-all-ready` when any candidate is blocked.
- Extended the visual-claim planner with `--write-ready-entries` so a batch
  review can write only ready ledger lines to a separate review artifact without
  editing the real promotion ledger or including blocked candidates. The planner
  now explicitly refuses to use `docs/recovery/visual_claim_promotions.md` as
  that review-file target.
- Added `tools/write_visual_claim_promotion_manifest.py` so future checked-in
  visual evidence bundles can be collected into a planner manifest from explicit
  fixture/bundle/docs/label tuples. The writer validates fixture names, checked
  bundle manifests, recovery-doc paths, and refuses the real visual-claim ledger
  as an output target.
- Added `tools/check_visual_claim_promotion_workflow.py` to pin the visual
  promotion docs, summary/guardrail/writer/planner tools, and their CTest
  registrations together so future promotion workflow drift fails fast.
- Added a dedicated dry-run CTest for the pending natural forward lane-result
  probe: `--offset forward --route-step x:2.00 --route-step c:0.50` targeting
  `1000:3D3F`. This does not promote new evidence, but it keeps the next
  DOSBox/procmem route retry anchored to the documented no-freeze fixture and
  visible in the orchestrator contract.
- Added a CTest dry-run for the default lane-result route sweep matrix, locking
  the four planned natural-route probes
  `x:2.00`, `x:2.00,c:0.50`, `x:1.50,z:0.50`, and `x:2.00,m:0.35` at the
  build level before any DOSBox/procmem capture is attempted.
- Extended behavior-4 DOSBox-debug helper coverage so CMake dry-runs all three
  supported original evidence plans: level-2 spawner, level-3 spawner, and
  two-player target selection. These remain `debugger_seeded` capture plans
  with `visual_claim=0` until real DOSBox-debug transcripts are promoted.
- Extended actor-update and contact-scanner DOSBox-debug helper contracts so
  CMake names all three supported `debugger_seeded` plans:
  object-collision jump, monster-contact damage, and behavior-4 chase. These
  are still dry-run capture plans only, not promoted original runtime evidence.
- Aligned the behavior-4, actor-update, contact-scanner, and visual-table
  DOSBox-debug helper preflights with the process-memory wrappers by adding
  `--probe-wsl --require-wsl-bash-on-windows`. Failed Windows capture starts now
  preserve the current WSL blocker, such as `wsl_bash_reason=no_default_distro`,
  in the preflight log before DOSBox-debug is attempted.
- Extended the original-evidence environment checker with the observed Windows
  WSL shape where `wsl --status` succeeds but `wsl -e bash -lc true` fails with
  `WSL_E_DEFAULT_DISTRO_NOT_FOUND`. This keeps the no-default-distro blocker
  distinct from a missing `wsl.exe` or a fully failing WSL command.
- Extended actor/contact process-memory helper coverage so CMake names all nine
  supported freeze targets, from actor-update entry/exit through gate5/gate6
  and contact-scanner callsite/start/end. These remain guarded dry-run plans
  until a trusted WSL/DOSBox/procmem host captures runtime evidence.
- Added a CTest dry-run for the default actor-dispatch gate sweep, pinning the
  five-target matrix across gate5 entry/integration/exit, gate6, and the
  contact-scanner callsite before any live WSL/DOSBox/procmem run is promoted.
- Added a CTest dry-run for the default actor/contact route sweep, pinning the
  contact-scanner-start matrix across both pre-bomb and pre-route freeze timing
  and all four planned route probes.
- Added `--target-set all` to the actor-dispatch sweep planner and pinned it
  with CTest, so one dry-run command now expands all nine actor/contact
  process-memory targets before an approved live capture host is used.
- Extended actor-dispatch sweep summary coverage with a nine-target dry
  manifest, keeping downstream missing-target accounting pinned to the
  all-target planner output.
- Pinned the actor-dispatch sweep override contract: repeated `--target`
  arguments narrow the run even when `--target-set all` is present.
- Added ready-candidate summary coverage for a `contact_scanner_end`
  process-memory fixture, including the promoted
  `--debug-contact-scanner-runtime-oracle` handoff.
- Extended the actor-dispatch ready pipeline check so a ready
  `contact_scanner_end` fixture now travels end to end through summary,
  ready-manifest execution, and ready-result summarization.
- Added `tools/summarize_actor_dispatch_gate_sweep.py` and synthetic CTest
  coverage for completed actor dispatch-gate sweep manifests. The summarizer
  follows nested route-sweep manifests, counts capture statuses, reports
  observed runtime freezes, lists missing gate targets, and surfaces candidate
  fixtures for runtime-oracle normalization. It now reports
  `dispatch_gate_freezes=` event counts and unique
  `observed_dispatch_gates=` names separately from broader `observed_targets=`
  route-freeze evidence. It also labels each observed freeze with
  `dispatch_gate_candidate=`, the matching `actor_update` or `contact_scanner`
  oracle flag, and a runnable `oracle_command=` hint, plus `candidate_status=`
  readiness so skeleton fixtures are not mistaken for normalized evidence. The
  top-level summary now includes ready/incomplete/missing/none candidate counts
  for quick triage.
  Placeholder detection intentionally scans commented skeleton hints as well as
  active fixture records. `--require-ready` now exits nonzero when any observed
  freeze candidate is not promotable. `--require-dispatch-gate-freeze` exits
  nonzero when no mapped actor/contact dispatch-gate target froze.
  `--write-ready-manifest` writes a follow-up promotion manifest containing
  only ready fixtures and oracle commands, and
  `tools/run_actor_dispatch_ready_manifest.py` can dry-run or execute that
  manifest so the next WSL/DOSBox pass can validate promoted candidates without
  hand-copying summary lines. The runner now rejects missing
  fixtures and mismatched oracle/flag pairs before execution, with an explicit
  dry-run-only bypass for forensic manifest review, and can write a result
  manifest for planned or executed oracle commands. Result manifests and logs
  are refused inside the repository unless explicitly allowed.
  `tools/summarize_actor_dispatch_ready_results.py` summarizes those result
  manifests and can require successful executed oracle runs. The synthetic
  `tools/check_actor_dispatch_ready_pipeline.py` check now exercises the full
  sweep-summary, ready-runner, and result-summary handoff.
- Added `lane-result-cs-scratch` instrumentation support to
  `tools/capture_original_explosion_procmem.py` for the final lane-helper
  result writes at `1000:3D3F` and `1000:3ED3`. The runtime-only trampoline
  parks code at `CS:F200`, scratch at `CS:F280`, and captures the result byte,
  `ES:DI`, `[BP+4]`/`[BP+6]`, `[BP-0D]`, active count/index, and the
  destination byte before `mov es:[di],al`.
- Hardened that instrumentation with an original-byte guard: both temp-copy
  and runtime child-memory patching require the target bytes to be `26 88 05`
  before writing the trampoline, and manifests/candidate fixtures now record
  `freeze_expected_old_bytes` plus `freeze_old_bytes`.
- Added `--describe-freeze-patch` to the capture helper so patch bytes,
  expected original bytes, file offsets, scratch offsets, and body bytes can be
  preflighted without launching DOSBox or reading process memory.
- Added Python-backed CTest preflight coverage for
  `--describe-freeze-patch` at `1000:3D3F` and `1000:3ED3`, pinning the
  shipped file offsets, expected bytes, trampoline bytes, scratch offset, and
  body offset.
- Added a negative preflight CTest for `lane-result-cs-scratch` at wrong
  offset `1000:3D2D`; the tool now reports a clean
  `freeze_patch_description=error` line instead of a Python traceback.
- Added `tools/check_explosion_lane_result_preflight.py`, a no-DOSBox Python
  verifier that imports the capture helper and checks both lane-result patch
  descriptions, expected original bytes, exact trampoline body bytes, and the
  wrong-offset guard in one command.
- Added `tools/check_explosion_lane_result_fixtures.py`, a no-C++ fixture
  expectation checker that verifies all checked-in lane-result fixtures still
  produce their intended parser outcome: two valid synthetic fixtures and eleven
  malformed fixtures. It also verifies each fixture has matching CMake coverage
  with the intended success/error regex, and that malformed fixtures are wired
  with `--expect-error` while valid fixtures are not.
- Added `tools/check_explosion_lane_result_layout.py`, a no-build consistency
  checker that locks the lane-result scratch field order across
  `capture_original_explosion_procmem.py`, `src/main.cpp`, and the fixture
  expectation helper.
- Added `tools/check_explosion_lane_result_orchestrator.py`, a no-DOSBox CMake
  coverage checker for the lane-result capture wrapper tests. It locks the
  expected orchestrator command shapes, regex fragments, and `WILL_FAIL`
  settings for 13 capture-wrapper CTest cases plus the wrapper-output checker
  CTest hook.
- Added `tools/check_explosion_lane_result_wrapper.py`, a no-DOSBox wrapper
  output checker that runs the lane-result preflight/dry-run matrix directly,
  including both preflight forms, default, with-oracle, forward-only,
  reverse-only, raw reverse-address, mixed-order, duplicate-offset,
  timing-argument pass-through, bad-offset,
  repo-output-refusal, and missing-approval cases.
- Added `tools/capture_original_lane_result_runtime.py`, a guarded wrapper for
  the pending original `1000:3D3F`/`1000:3ED3` runtime captures. Its
  `--preflight-only` mode is safe in restricted shells; full capture still
  requires explicit process-memory and runtime-instrumentation approval. The
  wrapper accepts both `out_dir [asset_dir]` and `--asset-dir` to match the
  older capture helper workflow, and `--dry-run` prints the exact capture/oracle
  commands without launching DOSBox. Full captures write those generated
  command lines into `manifest.txt` alongside the produced candidate paths,
  selected offset labels/addresses, approvals, and timing parameters. The repeatable
  `--offset` option allows retrying only `forward` (`1000:3D3F`) or only
  `reverse` (`1000:3ED3`), while still accepting the raw `3D3F`/`3ED3` address
  forms. Dry-run/full-capture success output and manifests now report both
  `offset_labels` and normalized `offset_addresses`.
- Added `python_tool_syntax_lane_result_preflight` CTest coverage so the
  capture helper, lane-result preflight helper, fixture expectation helper,
  scratch-layout helper, orchestrator expectation helper, and lane-result
  runtime wrapper are syntax-checked before runtime oracle or DOSBox evidence
  paths run.
- Extended `--debug-explosion-playback-oracle` with
  `observed_lane_forward_result`/`observed_lane_reverse_result` and
  `lane_result_*` fields. The oracle now validates that the far destination
  equals the caller argument pointer, the output byte equals the result local,
  the expected original byte signature is present, the scratch offset is the
  capture helper's `CS:F280` block, byte-width fields stay byte-sized, and loop
  bounds are sane.
- Added synthetic valid and malformed CTest fixtures for lane-result parsing:
  `explosion_playback_oracle_lane_result_scratch_synthetic.txt`,
  `explosion_playback_oracle_lane_result_reverse_scratch_synthetic.txt`,
  `explosion_playback_oracle_lane_result_missing_target_before.txt`,
  `explosion_playback_oracle_lane_result_bad_far_pointer.txt`,
  `explosion_playback_oracle_lane_result_bad_output_local.txt`,
  `explosion_playback_oracle_lane_result_bad_expected_old_bytes.txt`,
  `explosion_playback_oracle_lane_result_expected_without_old_bytes.txt`,
  `explosion_playback_oracle_lane_result_missing_expected_old_bytes.txt`,
  `explosion_playback_oracle_lane_result_bad_scratch_offset.txt`,
  `explosion_playback_oracle_lane_result_bad_kind.txt`,
  `explosion_playback_oracle_lane_result_bad_loop_bounds.txt`,
  `explosion_playback_oracle_lane_result_bad_target_before_width.txt`, and
  `explosion_playback_oracle_lane_result_field_without_present.txt`.
- Extended the C++ explosion oracle to parse `freeze_expected_old_bytes` and
  reject fixtures whose `freeze_old_bytes` do not start with the expected
  byte sequence.
- The explosion oracle success line now emits
  `freeze_expected_old_bytes_present`, `freeze_expected_old_bytes`, and
  `freeze_old_bytes`; the forward/reverse synthetic lane-result CTest regexes
  pin `268805`.
- Promoted
  `explosion_playback_oracle_original_3ed3_lane_result_runtime.txt` from an
  approved WSL/DOSBox process-memory run. It freezes `1000:3ED3` at runtime
  `01ED:3ED3`, records the guarded original bytes `268805`, captures scratch
  output `0x00ef`, `ES:DI=18B3:3FE6`, `[BP+4]/[BP+6]=18B3:3FE6`,
  result local `0x00ef`, active count/index `1/1`, and target-before byte
  `0xde`; the fixture remains `visual_claim=0`.
- Promoted
  `explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded.txt`
  from an approved WSL/DOSBox process-memory run with labeled runtime seeding.
  The seed patch at runtime `01ED:4C96` writes `DS:655E=0xC004`, calls the
  original forward helper body at `01ED:3BB2`, returns to `01ED:4C99`, and then
  freezes `1000:3D3F` at runtime `01ED:3D3F`. The fixture records byte guard
  `268805`, scratch `01ED:F280`, result/output `0x00fa`,
  `ES:DI=0C44:78D2`, `[BP+4]/[BP+6]=0C44:78D2`, active count/index `1/1`,
  target-before byte `0xf3`, and remains `visual_claim=0`.
- Natural-route `1000:3D3F` evidence remains pending. The 2026-05-06 default,
  right-hold timing, and before-bomb patch attempts all loaded the runtime patch
  but did not hit the forward result freeze, so the promoted forward fixture is
  intentionally labeled runtime-seeded rather than full gameplay-route evidence.
- Extended the original process-memory capture route driver with repeatable
  `--route-step KEY:SECONDS` holds, preserving the old `--right-key` /
  `--right-hold-seconds` route as the default. The lane-result wrapper passes
  those route steps through and records them in manifests/candidate fixtures.
- Promoted
  `explosion_playback_oracle_original_3d3f_lane_result_route_step_no_freeze.txt`
  from a natural original-control route `x:2.00,c:0.50`. It loaded the
  `1000:3D3F` runtime patch and records byte guard `268805`, but no forward
  result freeze or lane-result scratch appeared. The chosen sample still shows
  live lane globals (`lane_update_flag=0x05`, `lane_word=0x0004`,
  `lane_target_offset=0x072c`, reverse input `0xfb`), so it is useful negative
  evidence for the natural forward-route gap.
- Added `tools/sweep_original_lane_result_routes.py`, a guarded route-sweep
  wrapper for repeated natural lane-result probes. Its dry-run mode prints all
  generated `capture_original_lane_result_runtime.py` commands, defaults to the
  current `x`, `x,c`, `x,z`, and `x,m` route set, and live capture still
  requires both process-memory/runtime-instrumentation approval flags.
- Added `tools/check_lane_result_route_sweep.py` and CTest coverage for the
  route-sweep wrapper's default route labels, custom route labels, approval
  refusal, repository-output refusal, and malformed route parsing.
- Added `tools/summarize_lane_result_route_sweep.py` and synthetic CTest
  coverage for completed lane-result route-sweep manifests. The summary follows
  child runtime manifests, classifies candidate fixtures as `ready`,
  `no_freeze`, `incomplete`, or `missing`, emits
  `--debug-explosion-playback-oracle` commands, and can write a ready-promotion
  manifest for natural `1000:3D3F` or `1000:3ED3` freezes.
- Added `tools/run_lane_result_ready_manifest.py`,
  `tools/summarize_lane_result_ready_results.py`, and an end-to-end synthetic
  lane-result ready-pipeline CTest. The runner validates the ready manifest,
  refuses repository-local logs/results by default, executes only
  `--debug-explosion-playback-oracle` candidates, and records planned or
  executed oracle results for promotion gating. Granular CTest helpers now pin
  the runner and result-summary error cases separately from the full pipeline
  check.
- Added `tools/preflight_original_evidence_environment.py` and synthetic CTest
  coverage. The preflight reports shipped asset availability and the local
  `bash`/DOSBox/`dosbox-debug`/Xvfb/`xdotool` toolchain, with require modes that
  fail before a long original-evidence sweep starts on an unprepared host.
  The WSL probe now distinguishes a present `wsl.exe` from a usable default
  Linux distro by running `wsl -e bash -lc true` and reporting
  `wsl_bash_reason=no_default_distro` for the current no-distro blocker.
  `--require-wsl-bash-on-windows` promotes that probe to a Windows-only
  `reason=wsl_bash_not_usable` failure while leaving native Linux/WSL preflights
  free to pass without a nested `wsl.exe`.
- `tools/sweep_original_lane_result_routes.py` now prints the environment
  preflight command in dry-run and runs the process-memory capture preflight
  once before any live route commands, unless explicitly skipped with
  `--skip-environment-preflight`. The route-sweep preflight includes
  `--probe-wsl --require-wsl-bash-on-windows`, so Windows dry-runs and failed
  live starts preserve the exact WSL usability blocker before a DOSBox
  process-memory batch begins. Direct
  `tools/capture_original_lane_result_runtime.py` live captures now run the
  same environment preflight and record `environment_preflight=` in their
  manifests; route sweeps pass `--skip-environment-preflight` to child direct
  captures after the top-level check succeeds.
- `tools/sweep_original_actor_contact_routes.py` and
  `tools/sweep_original_actor_dispatch_gates.py` now use the same
  process-memory environment preflight before live actor/contact capture
  sweeps, also with `--probe-wsl --require-wsl-bash-on-windows`. Dispatch-gate
  sweeps run the host check once at the top level and pass
  `--skip-environment-preflight` to child actor/contact sweeps so a single
  matrix does not repeat identical tool probes. Direct
  `tools/capture_original_actor_contact_procmem.sh` live runs also record
  `environment_preflight=` in their manifests and execute the shared preflight
  unless `LEZAC_ACTOR_CONTACT_PROCMEM_SKIP_ENVIRONMENT_PREFLIGHT=1` is set by
  an already-verified parent sweep.
- Lane-result and actor dispatch-gate sweep summaries now surface
  `environment_preflight=` state and support
  `--require-environment-preflight`, so ready-candidate promotion scripts can
  fail explicitly when a manifest came from an unverified or legacy capture
  host.
- Lane-result and actor dispatch ready-manifest runners now propagate
  `source_environment_preflight=` into result manifests and support
  `--require-source-environment-preflight`; the matching result summarizers can
  require the same field before accepting executed oracle results.
- The lane-write, lane-result, actor dispatch, and generic debug-capture
  ready-manifest runners now reject stale `candidate_N_*` fields whose index
  is outside `ready_candidates`, matching the result-summary guards so old
  evidence candidates cannot be silently ignored before oracle execution.
- The same four ready-manifest runners now reject duplicate manifest keys
  before oracle execution, preventing a later `candidate_N_fixture`,
  `runtime_cs`, `runtime_ds`, or oracle flag from silently overwriting the
  evidence metadata that was promoted for review.
- The matching ready-result summarizers now reject duplicate manifest keys as
  well, so executed oracle result summaries cannot be built from overwritten
  candidate fixture, runtime-segment, status, or command fields.
- Shared ready-result fixture validation now rejects duplicate fixture keys
  inside existing runtime evidence fixtures, preventing `runtime_cs`,
  `runtime_ds`, `visual_claim`, or `temp_copy` from being overwritten after a
  candidate manifest has already passed its own duplicate-key guard.
- Lane-result, lane-write, actor-dispatch, and debug-capture ready-result
  checks now all exercise that duplicate runtime fixture-field rejection, so
  every ready-result family proves it cannot summarize overwritten fixture
  segment metadata.
- The lane-result, lane-write, actor-dispatch, and debug-capture
  ready-manifest runner checks now exercise the same duplicate runtime
  fixture-field rejection before oracle execution.
- Runtime evidence ledger parsing now rejects duplicate original fixture
  entries, so a checked-in original fixture cannot be accepted from an
  overwritten provenance row.
- Runtime evidence ledger rows now reject duplicate fields before provenance
  validation reads them, preventing a second `visual_claim`, `evidence`, or
  `docs` token from overwriting the reviewed metadata on the same line.
- Runtime evidence ledger validation now requires
  `original_runtime_fixture_count` to match the parsed machine-readable
  fixture rows before any checked-in original fixture can be promoted through a
  ready-result path.
- Runtime evidence ledger validation now also requires a single
  `runtime_evidence_ledger=non_visual` marker, so the shared ready-result
  provenance path rejects duplicate or wrong top-level ledger kind metadata.
- `tools/check_ready_fixture_provenance_contract.py` now directly self-tests
  valid, missing, duplicate, invalid, negative, and count-mismatched runtime
  evidence ledger metadata at the shared parser layer.
- Lane-write and lane-result ready-pipeline checks now include source
  environment preflight refusal cases, so natural debris-write and forward
  result oracle batches cannot execute from a manifest whose capture sweep
  recorded `source_environment_preflight=error`.
- Actor-dispatch and generic debug-capture ready-pipeline checks now exercise
  the same strict preflight refusal paths for actor/contact/behavior4/visual
  table oracle batches before future original fixtures are promoted.
- `--debug-son-tail-field-mutation` now mutates `PROEFS.SON` bytes `+4..+5`
  across all 130 six-byte steps and proves the current recovered synthesizer
  renders identical samples for the 14 known cursor starts. The bytes stay
  preserved as raw unknown fields until original evidence assigns semantics.
- The actor-dispatch, lane-result, lane-write, and debug-capture sweep/capture
  summary readers now reject duplicate manifest keys too, extending that
  overwrite guard to the pre-promotion capture layer.
- The lane-result and actor dispatch ready-pipeline CTest helpers now exercise
  the strict preflight path end to end: sweep summary, ready manifest runner,
  and result summary all use their corresponding preflight-required flags.
- Tightened `--require-procmem-capture` to match the actual process-memory
  wrapper dependencies: direct `Xvfb`, `zutty`, and `script` are now required
  along with DOSBox-debug, `xdotool`, `python3`, and `pgrep`.
- Added the `timeout` command to the full original/debug capture preflight
  requirements because the DOSBox-debug helper scripts wrap their launches with
  `timeout`.
- Brought `tools/capture_original_behavior4_debug.sh` up to the actor/contact
  debug-helper handoff shape: it now leaves a `candidate_fixture.txt` skeleton,
  a `debugger_commands_runtime.txt` placeholder, and copies observed
  `runtime_cs`/`runtime_ds` metadata into the manifest/raw dump when a live
  DOSBox-debug run exposes registers before timing out.
- The behavior-4, actor-update, contact-scanner, and visual-table DOSBox-debug
  helpers now run the shared `--require-debug-capture` environment preflight
  before live DOSBox-debug launch, write `environment_preflight.log`, and record
  the preflight status in their manifests. Dry runs explicitly mark
  `environment_preflight=dry_run`; per-helper skip environment variables are
  reserved for already-verified forensic reruns.
- Added `tools/summarize_debug_capture.py` plus synthetic coverage so a single
  behavior-4, actor-update, contact-scanner, or visual-table DOSBox-debug
  capture directory can be triaged as ready, incomplete, missing, or
  environment-failed. The summary prints the matching runtime-oracle command and
  can require both a promotion-ready fixture and `environment_preflight=ok`.
- Added `tools/summarize_debug_capture_batch.py` plus synthetic coverage for
  whole WSL evidence batches. The batch summary recursively finds supported
  debug-capture manifests, counts ready/incomplete/missing candidates, reports
  environment-preflight and runtime-metadata totals, and can write a compact
  ready-candidates manifest for the promotable fixtures.
- Added `tools/run_debug_capture_ready_manifest.py` plus synthetic coverage so
  ready debug-capture manifests can be dry-run or executed through the matching
  runtime oracle only. The runner validates oracle/flag pairs, can require
  per-candidate `environment_preflight=ok`, writes optional logs, and emits a
  result manifest for promotion review.
- Added a key/value lane-result handoff checklist to
  `docs/recovery/dosbox_explosion_process_memory_attempt_2026-04-24.md` with
  the pending WSL preflight/capture commands, expected manifest/candidate paths,
  alias mapping, byte guard, scratch address, and promotion criteria.
- Added a deterministic `--debug-autoplayer level1_bomb_route` command.
- Extended `--debug-autoplayer` with `death_reentry`, `records_flow`, and
  `two_player_route` scenarios so state-2 reentry, record-entry saving, and
  player-2 movement/bomb controls are covered without live input.
- Added `death_visuals`, `level_transition`, `two_player_death_visuals`, and
  `two_player_progression` autoplayer scenarios. These lock the current
  row-byte-3 state-2 death renderer, split-screen state-2 effect slots, level-1
  completion into level 2, player-2 death/reentry, post-reentry bombs, and
  player-2 scoring.
- Added `portal_weapon_route`, `monster_bomb_reward`, and
  `collapse_playback_route` autoplayer scenarios. These broaden deterministic
  coverage to weapon switching through the left+right chord, medium bomb
  placement through `N`, decoded portal traversal, bomb-killed monster rewards,
  reward pickup sounds, and level-1 collapse playback duration.
- Added `monster_behavior3_multihit`, `monster_behavior4_chase`, and
  `monster_spawner_cycle` autoplayer scenarios. These extend the headless
  matrix to grounded behavior-3 walkers, behavior-4 chase movement, spawner
  slot release/respawn, and multi-hit bomb damage across live update loops.
- Added `monster_spawner_behavior4_level2`,
  `monster_spawner_behavior4_level3`, and
  `monster_behavior4_target_selection` autoplayer scenarios. These extend the
  live monster harness to actual level-2/3 behavior-4 spawner data and
  two-player nearest-target selection across alive/dead player states.
- Extended `--capture-frame-sequence` with
  `monster_spawner_behavior4_level2`,
  `monster_spawner_behavior4_level3`, and
  `monster_behavior4_target_selection`. The frame harness now exports
  deterministic behavior-4 spawn/retarget checkpoints plus manifest metadata
  for player count/dead flags and first-monster position/velocity/behavior.
- Added `--debug-behavior4-runtime-oracle <fixture> [--expect-error]` with
  synthetic and malformed DOSBox fixture coverage. The parser records
  scenario/level, runtime `CS`/`DS`, behavior-4 spawner fields, actor
  before/after position, 8.8 velocity, motion timer, target/player-dead state,
  optional `DS:` dump rows, and required anchors for the spawner loop
  `1000:7A6B..7C2C`, behavior-4 branch `1000:728C..731B`, and 8.8 integration
  `1000:73E5..741B`.
- Added `tools/capture_original_behavior4_debug.sh <out_dir> [asset_dir]
  <scenario>` for the level-2 spawner, level-3 spawner, and target-selection
  behavior-4 scenarios. It writes `manifest.txt`, `raw_debugger_dump.txt`, and
  `debugger_commands.txt`, labels current captures `debugger_seeded`, and has a
  dry-run CTest path for environments without DOSBox-debug.
- Added `tools/check_behavior4_runtime_oracle_fixtures.py` so behavior-4
  fixture expectations, CMake wiring, and the C++ oracle command/source
  contract can be validated without DOSBox or a local C++ compiler. The checker
  now keeps the fixed synthetic/malformed baseline while allowing future
  `behavior4_runtime_oracle_original*.txt` captures only when they parse as
  valid runtime evidence and have matching CTest coverage.
- Added `tools/check_optional_original_oracle_fixtures.py` so the behavior-4,
  actor-update, and contact-scanner runtime-oracle fixture lanes keep the same
  optional-original convention: original fixtures are valid-only, must have
  CTest coverage, and remain `visual_claim=0`.
- Added `tools/check_behavior4_debug_capture_helper.py` to lock the
  behavior-4 DOSBox-debug helper's supported scenarios, debugger anchors,
  manifest/raw-output contract, `debugger_seeded` docs, and CMake dry-run
  wiring without requiring `bash` or DOSBox locally.
- Restored a native Windows validation path with Visual Studio Build Tools and
  the local vcpkg SDL2 package by propagating `SDL2_LIBRARY_DIRS`, defining
  `SDL_MAIN_HANDLED`, and making the state-2 effect-placement lambdas
  MSVC-compatible. The sanitized native Debug build in `build-win-codex-vs3`
  passed 156/156 CTest tests. The bash-only behavior-4 helper dry-run is now
  registered only when `bash` is available, so the native Windows suite can run
  without a manual exclusion while still preserving the helper's CMake wiring.
- Added `tools/run_native_windows_validation.ps1` and
  `tools/check_native_windows_validation_helper.py` to make that native Windows
  validation recipe repeatable: it sanitizes duplicate `PATH`/`Path` entries,
  configures Visual Studio Build Tools with the local vcpkg SDL2 package, builds
  `build-win-codex-vs3`, and runs CTest unless `-SkipTests` is supplied.
- Added CMake install rules plus `install_layout_smoke` so an installed C++ port
  contains `lezac_cpp`, all original/JSON assets, and `SDL2.dll` on Windows, then
  validates successfully from the install prefix.
- Added `--debug-actor-update-runtime-oracle <fixture> [--expect-error]` with
  synthetic and malformed fixture coverage. The parser records scenario/level,
  runtime `CS`/`DS`, actor before/after state, contact scanner flags, tile probe
  passability/standability fields, optional `DS:` dump rows, and required
  anchors for the contact scanner `1000:5CB0..604F` and actor update
  `1000:6053..777F`. No live gameplay behavior changed from this synthetic
  parser coverage.
- Added `tools/capture_original_actor_update_debug.sh <out_dir> [asset_dir]
  <scenario>` for `object_collision_jump_live`, `monster_contact_damage_live`,
  and `monster_behavior4_chase`. It writes `manifest.txt`,
  `raw_debugger_dump.txt`, `candidate_fixture.txt`, `debugger_commands.txt`, and
  `actor_update_debug_capture.log`, labels current captures `debugger_seeded`,
  and has a dry-run CTest path for environments with `bash`. Live DOSBox-debug
  attempts now append any observed debugger prompt `runtime_cs`/`runtime_ds`
  values to both `manifest.txt` and `raw_debugger_dump.txt`, and write
  `debugger_commands_runtime.txt` with concrete runtime breakpoint/dump
  commands. The candidate fixture is intentionally a fill-in skeleton until
  original runtime fields and dump rows are captured.
- Added `tools/check_actor_update_runtime_oracle_fixtures.py` so the
  actor-update fixture set, expected malformed outcomes, CMake wiring, and C++
  oracle command/source contract can be validated without DOSBox or a compiler.
  The checker now keeps the fixed synthetic/malformed baseline while allowing
  future `actor_update_runtime_oracle_original*.txt` fixtures only if they parse
  as valid runtime evidence and have matching CTest coverage.
- Added `--debug-contact-scanner-runtime-oracle <fixture> [--expect-error]`
  with synthetic and malformed fixture coverage. This isolates the probable
  scanner window `1000:5CB0..604F` from full actor-update evidence by parsing
  subject/other actor boxes, overlap size, contact flags, and pending damage.
  `tools/check_contact_scanner_runtime_oracle_fixtures.py` validates fixture
  outcomes, CMake wiring, and the C++ source contract without DOSBox. It now
  accepts future `contact_scanner_runtime_oracle_original*.txt` fixtures under
  the same valid-oracle and CTest-coverage requirements.
- Added `tools/check_sound_callsite_oracle_fixtures.py` so sound-callsite
  synthetic/malformed fixture outcomes, CMake wiring, and the C++ oracle source
  contract are validated without launching DOSBox. The checker accepts future
  `sound_callsite_oracle_original*.txt` captures only when they parse as valid
  runtime evidence and have matching CTest coverage, and the optional-original
  convention gate now tracks sound-callsite as its fifth runtime-oracle lane.
- Added `tools/capture_original_contact_scanner_debug.sh <out_dir> [asset_dir]
  <scenario>` for `monster_contact_damage_live`, `object_collision_jump_live`,
  and `monster_behavior4_chase`. It writes scanner-only `manifest.txt`,
  `raw_debugger_dump.txt`, `candidate_fixture.txt`, `debugger_commands.txt`, and
  `contact_scanner_debug_capture.log`, labels current captures
  `debugger_seeded`, and has CMake/checker coverage for dry-run wiring. Live
  DOSBox-debug attempts now append any observed debugger prompt
  `runtime_cs`/`runtime_ds` values to both `manifest.txt` and
  `raw_debugger_dump.txt`, and write `debugger_commands_runtime.txt` with
  concrete runtime breakpoint/dump commands. The candidate fixture is
  intentionally a fill-in skeleton until original runtime fields and dump rows
  are captured.
- WSL/Xvfb/DOSBox-debug launch is unblocked in the approved WSL context. Short
  2026-05-11 temp-copy probes reached the DOSBox-debug prompt and recorded
  runtime `CS=01ED`, `DS=01DD` for both contact-scanner and actor-update helper
  paths. They still time out with DOSBox-debug exit `124` because debugger
  command submission and semantic breakpoint seeding are the remaining blocker;
  no original actor/contact runtime fixture has been promoted from these launch
  probes.
- Added `tools/capture_original_actor_contact_procmem.sh`, a guarded
  process-memory instrumentation wrapper for `actor_update_start`,
  `actor_update_end`, `actor_update_gate5`, `actor_update_gate5_integration`,
  `actor_update_gate5_exit`, `actor_update_gate6`, `contact_scanner_callsite`,
  `contact_scanner_start`, and `contact_scanner_end`. `contact_scanner_callsite`
  maps the static near call at
  `1000:6555` that targets `1000:5CB0`; the only direct near call to the scanner
  entry found in the shipped code image is at that callsite. It reuses the
  proven child DOSBox-debug process-memory scanner, requires
  `LEZAC_ACTOR_CONTACT_APPROVE_PROCMEM=1` and
  `LEZAC_ACTOR_CONTACT_APPROVE_RUNTIME_INSTRUMENTATION=1` for live runs, and
  records `visual_claim=0` because these are reachability probes rather than
  pristine gameplay-route fixtures. Direct live runs now execute the shared
  process-memory environment preflight before touching DOSBox-debug and record
  `environment_preflight=` in the manifest. It now writes
  `<target>_runtime_candidate.txt` with runtime metadata and raw route-state
  dumps, and accepts `LEZAC_ACTOR_CONTACT_ROUTE_STEPS` as comma-separated
  `key:seconds` route holds for scanner-path tuning. It can also set
  `LEZAC_ACTOR_CONTACT_RUNTIME_FREEZE_BEFORE_ROUTE=1` so the runtime patch is
  applied immediately after level start, before route movement, for helpers that
  may only execute during contact positioning. A 2026-05-11 live probe at
  `actor_update_start` froze `1000:6053` at runtime `01ED:6053`, with
  `freeze_old_bytes=5589`, `freeze_patch_bytes=ebfe`,
  `freeze_runtime_patch_applied=1`, `instrumented_freeze_observed=1`, runtime
  `CS=01ED`, and runtime `DS=0C8F`.
- Added `tools/check_actor_contact_procmem_helper.py` and CMake dry-run
  coverage so the guarded wrapper's targets, approvals, output contract, and
  docs are checked without process-memory access.
- Added live state-2 rendering keyed to the recovered `0x4a..0x4f` cursor
  range; the current live renderer consumes the original row-byte-3 sprite
  sequence `67..72` from an explicit state-2 effect entry whose x/y base
  mirrors the original DS:C21E evidence, then applies row-byte-0/1 draw offsets
  `16,16`. It remains documented as `visual_claim=0` until paired original frame
  evidence is promoted.
- Tightened the `death_visuals` autoplayer on the actual state-2 route for
  frames `0x4a..0x4c`, pinning live row-byte-3 sprites `67,68,69`, effect-entry
  base `104,168`, and draw offset `16,16` against the old cursor-index sprites
  `74,75,76`.
- Added `two_player_death_visuals` to frame-inspect split-screen state-2
  playback: player 2 advances effect-entry frames `0x4a,0x4b`, player 1 can
  enter its own `0x4a` effect entry while player 2 remains dead, and the two
  effect bases stay separate at `104,168` and `280,168`.
- Refactored the game update path so the autoplayer can drive the same movement
  helpers with injected controls instead of relying on live keyboard state.
- Changed `--capture-frame-sequence level1_bomb_route <out-dir>` to reach tile
  `(24,22)` through the autoplayer route instead of teleporting the player.
- Changed the level-1 bomb route autoplayer and frame-sequence capture to place
  the route bomb through the actual `N` key event path instead of calling the
  placement helper directly.
- Added CTest coverage for all autoplayer scenarios and for the behavior-4
  frame-sequence capture scenarios alongside the level-1 route.
- Expanded `tools/capture_original_dosbox_frames.sh` so original DOSBox
  screenshots are renamed to the C++ semantic labels and accompanied by a
  manifest with input/timing settings.
- Hardened the original DOSBox frame-capture route to use the focused
  no-window key path, two `1` taps, original player-1 right on `x`, and held
  player-1 fire on `n`. Local frame inspection now reaches level 1, shows bomb
  placement, and shows explosion playback in the original.
- Extended the guarded explosion process-memory helper to expose and record
  the same start/right/fire route controls in candidate fixture manifests.
- Extended the explosion process-memory helper with timed sample screenshots,
  `sample_summary.tsv`, selected debris/collapse/effect queue-slot detection,
  and selected-base fixture fields for later original oracle promotion.
- Added a guarded instrumented temp-copy freeze mode to the process-memory
  helper. It patches only the temporary `LEZAC.EXE` copy with `EB FE`, records
  MZ-derived file offsets, original/loaded bytes, screenshot hashes, and a
  tail-frame freeze observation flag.
- Added route-state sampling to the process-memory helper. Candidate captures
  now include `route_state_samples.tsv` and `route_state_dumps.txt` with raw
  bytes around known input/player/sound/explosion ranges so future original
  probes can be gated on runtime state instead of fixed sleeps alone.
- Added a separately approved runtime child-memory freeze mode to the same
  helper. It can defer the `EB FE` write until after bomb input and an optional
  decoded queue-score threshold, keeping the temp executable unmodified for
  state-gated reachability probes.
- Extended runtime freeze gates with decoded debris/collapse/effect nonzero
  thresholds and selected queue-base predicates, so probes can wait for visible
  playback-adjacent queue growth rather than the early post-bomb state.
- Added `--runtime-freeze-preset late-collapse` to reuse the current
  playback-adjacent gate defaults and disable timed screenshots unless
  explicitly overridden.
- Added tail-freeze confirmation screenshots to the process-memory helper so
  runs without timed sample screenshots can still detect a frozen final frame.
- Extended `--debug-explosion-playback-oracle` so fixtures can decode selected
  debris/collapse/effect bases while keeping the existing slot-zero defaults.
- Statically disassembled `1000:370e` from the original MZ image and tightened
  the explosion capture/oracle path around the proven one-based queue counters:
  debris records are selected from `0x2093 + 0x0b * DS:207e`, collapse records
  from `0x6611 + 0x0f * DS:2080`, and collapse payload fields now match the
  original flagged-word/magnitude/affected-byte offsets.
- Captured a fresh original level-1 bomb route with the corrected counter logic.
  Frame inspection confirmed visible bomb/explosion/smoke playback, and the
  live collapse record at `DS:6620` matched the deterministic C++ route for
  tile `(24,22)` with offsets `0x0a06..0x0a08`, word `0x0009`, flagged word
  `0x8009`, and affected byte count `4`.
- Extended `--debug-bomb-object-explosion-effects` output and CTest coverage to
  lock those original-matched collapse byte offsets in the C++ model.
- Widened original `DS:2090` process-memory sampling to the `DS:6610` collapse
  queue boundary, then captured a follow-up original route with counter-selected
  debris and collapse slots. The widened candidate parsed with
  `DS:207e=0x00c8`, debris base `DS:292b`, tile index `0x0540`, flagged word
  `0xc004`, lookup byte `0x67`, and collapse base `DS:6620`.
- Added sparse high-counter oracle coverage so counter-derived debris records
  can be tested without checking giant original dumps into the repository.
- Updated `AGENTS.md`, README, and recovery docs with the autoplayer, original
  DOSBox capture, and frame-inspection workflows.

## Validation

- 2026-06-15 WSL original-evidence preflight passed from the repo mount:
  `python3 tools/preflight_original_evidence_environment.py .
  --require-frame-capture --require-debug-capture` found `dosbox`,
  `dosbox-debug`, `xvfb-run`, `xdotool`, `python3`, and supporting tools.
- 2026-06-15 WSL lane-write sweep passed:
  `python3 tools/sweep_original_lane_write_routes.py
  /tmp/lezac-lane-write-natural-codex-20260615-1205 .
  --approve-procmem --approve-runtime-instrumentation --cpp-exe
  /tmp/lezac-wsl-build/lezac_cpp`. Summary reported 8 candidates, 1 observed
  freeze, and 1 ready candidate: route `x2p00_m0p35`, offset `3ec1`.
- 2026-06-15 WSL lane-result sweep passed:
  `python3 tools/sweep_original_lane_result_routes.py
  /tmp/lezac-lane-result-forward-natural-codex-20260615-1205 .
  --offset forward --approve-procmem --approve-runtime-instrumentation
  --cpp-exe /tmp/lezac-wsl-build/lezac_cpp`. Summary reported 4 candidates,
  1 observed freeze, and 1 ready candidate: route `x2p00`, offset `3d3f`.
- 2026-06-15 ready-manifest runner and result-summary gates passed for both
  new ready candidates with `--require-source-environment-preflight`,
  `--require-success`, and `--require-executed`; each oracle log returned
  `status=ok` / `returncode=0`.
- 2026-06-15 local Windows delayed state-2 life-loss validation passed with the
  cleaned `Path` MSBuild workaround: `cmake --build build-win-codex-vs3
  --config Debug --target lezac_cpp`, direct
  `--debug-player-damage-death-live` output
  `frames_to_state2=101 delayed_life_loss=1`, and focused CTest
  `ctest --test-dir build-win-codex-vs3 -C Debug -R
  "(death|state2|player_damage|monster_contact|two_player_progression|original_damage_counters)"
  --output-on-failure` passed 26/26 tests.
- 2026-06-15 full native Windows validation passed after adapting
  `bomb_fuse` to the delayed final-life path:
  `powershell -ExecutionPolicy Bypass -File tools\run_native_windows_validation.ps1
  -BuildDir build-win-codex-vs3 -Configuration Debug` configured, built, and
  reported CTest 242/242 passing.
- 2026-05-15 lane-write route-sweep checkpoint: native Windows validation
  helper passed with `-SkipTests`, then focused CTest passed 57/57 for
  `lane_write|lane_result|explosion_lane`. This covered the new lane-write
  preflight, wrapper-output, and route-sweep checks plus the existing
  lane-result/explosion oracle guardrails. `git diff --check` passed with only
  existing CRLF normalization warnings on touched text files.
- 2026-05-15 continuation: WSL was present but no Linux distribution was
  installed (`WSL_E_DEFAULT_DISTRO_NOT_FOUND`), so live DOSBox/process-memory
  capture is blocked on this host. The no-WSL continuation added the lane-write
  route-sweep summarizer instead. After refreshing the native build metadata,
  focused CTest passed 58/58 for `lane_write|lane_result|explosion_lane`.
- 2026-05-15 handoff continuation: direct Python checks passed for
  `tools/check_lane_write_ready_pipeline.py`,
  `tools/check_lane_result_ready_manifest.py`, and
  `tools/check_lane_result_ready_results.py` after making the shared ready
  runner/result summarizer prefix-configurable. After refreshing native build
  metadata again, focused CTest passed 59/59 for
  `lane_write|lane_result|explosion_lane`. Full native Windows CTest then
  passed 201/201 with `ctest --test-dir build-win-codex-vs3 -C Debug
  --output-on-failure`.
- 2026-05-11 continuation: bundled Python helper/oracle checks passed for
  `tools/check_actor_update_debug_capture_helper.py`,
  `tools/check_contact_scanner_debug_capture_helper.py`,
  `tools/check_actor_update_runtime_oracle_fixtures.py`, and
  `tools/check_contact_scanner_runtime_oracle_fixtures.py`.
- `git --git-dir=.codex-git --work-tree=. diff --check` passed; Git reported
  only existing CRLF normalization warnings for touched Markdown files.
- WSL syntax checks passed for `tools/capture_original_contact_scanner_debug.sh`
  and `tools/capture_original_actor_update_debug.sh`.
- WSL dry-runs wrote complete helper artifacts outside the repository at
  `/tmp/lezac-contact-scanner-dry-run-codex-20260511` and
  `/tmp/lezac-actor-update-dry-run-codex-20260511`.
- Short WSL/Xvfb/DOSBox-debug launch probes wrote temp-copy manifests at
  `/tmp/lezac-contact-scanner-live2-codex-20260511` and
  `/tmp/lezac-actor-update-live-codex-20260511`. Both reached the debugger
  prompt and recorded `runtime_cs=01ED`, `runtime_ds=01DD`; both timed out with
  DOSBox-debug exit `124` because debugger command submission is still pending.
- Follow-up helper dry-runs now also emit `debugger_commands_runtime.txt` as a
  placeholder, and live probes overwrite it with runtime-translated debugger
  commands when `runtime_cs` is observed. Verified live outputs at
  `/tmp/lezac-contact-runtime-command-live2-codex-20260511` and
  `/tmp/lezac-actor-runtime-command-live2-codex-20260511` contain concrete
  `BP 01ED:5CB0`, `BP 01ED:604F`, actor-update `BP 01ED:6053`/`01ED:777F`,
  and `D 01DD:...` dump commands.
- `powershell -ExecutionPolicy Bypass -File tools\run_native_windows_validation.ps1
  -BuildDir build-win-codex-vs3 -Configuration Debug` passed: configure/build
  succeeded and CTest reported 169/169 tests passing.
- After adding runtime-translated debugger command files, the same native
  validation helper passed again: configure/build succeeded and CTest reported
  169/169 tests passing.
- Focused native CTest after the artifact cleanup passed:
  `ctest --test-dir build-win-codex-vs3 -C Debug -R
  "actor_update_debug_capture_helper_expectations|contact_scanner_debug_capture_helper_expectations"
  --output-on-failure` reported 2/2 tests passing.
- Guarded process-memory wrapper smoke evidence: live WSL output under
  `/tmp/lezac-actor-6053-freeze-procmem-codex-20260511` recorded
  `instrumented_freeze_observed=1` for `1000:6053`, with matching tail-frame
  screenshots. The generated candidate remains an explosion-helper artifact and
  was not promoted as actor/contact semantic evidence.
- The repeatable wrapper was then verified at
  `/tmp/lezac-actor-contact-procmem-live-codex-20260511`; its top-level
  manifest records `target=actor_update_start`, `runtime_cs=01ED`,
  `runtime_ds=0C8F`, `freeze_runtime=01ED:6053`, `freeze_old_bytes=5589`,
  `freeze_patch_bytes=ebfe`, `freeze_runtime_patch_applied=1`, and
  `instrumented_freeze_observed=1`.
- A live `contact_scanner_start` probe at
  `/tmp/lezac-contact-scanner-start-procmem-live-codex-20260511` loaded the
  runtime patch at `01ED:5CB0` (`freeze_old_bytes=5589`,
  `freeze_patch_bytes=ebfe`, `freeze_runtime_patch_applied=1`) but did not
  freeze (`instrumented_freeze_observed=0`) on the default level-1 route. This
  is route/timing evidence only; the scanner still needs a tuned collision path.
- The process-memory sampler now includes actor/contact-oriented route dumps
  for `DS:7900` and `DS:7A00` alongside the existing `DS:79E0` player-state
  window.
- The wrapper now writes `<target>_runtime_candidate.txt` as a non-promoted
  oracle scaffold. Dry-run route tuning was verified with
  `LEZAC_ACTOR_CONTACT_ROUTE_STEPS=x:1.0,n:0.2,z:0.5`, and a live
  `actor_update_start` run at
  `/tmp/lezac-actor-contact-candidate-live-codex-20260511` produced
  `actor_update_start_runtime_candidate.txt` with runtime `CS=01ED`,
  `DS=0C8F`, freeze metadata, and repeated `DS:7900`/`DS:79E0`/`DS:7A00`
  route-state dump blocks.
- A tuned `contact_scanner_start` route
  (`LEZAC_ACTOR_CONTACT_ROUTE_STEPS=x:5.0,m:0.5,x:2.0`) at
  `/tmp/lezac-contact-scanner-route-x5m-codex-20260511` entered active level-1
  gameplay and preserved `DS:7900`/`DS:79E0`/`DS:7A00` route-state dumps, but
  still loaded the `01ED:5CB0` patch without freezing. This makes a pre-route
  freeze mode the next scanner probe rather than promoting the no-freeze route
  as semantic contact evidence.
- The matching pre-route freeze run at
  `/tmp/lezac-contact-scanner-before-route-codex-20260511` applied the
  `01ED:5CB0` patch immediately after level start
  (`freeze_runtime_before_route=1`, `freeze_runtime_patch_phase=before_route`)
  and then replayed the same `x:5.0,m:0.5,x:2.0` route. It also did not freeze,
  so the current conclusion is narrow: this level-1 movement route does not hit
  the scanner start even when the patch is applied before movement. The next
  contact-scanner probe should target a different route or validate whether
  `1000:5CB0` is the correct entry anchor for live player/monster contact.
- Added `tools/sweep_original_actor_contact_routes.py`, a guarded route-sweep
  planner/runner for `actor_update_start`, `actor_update_end`,
  `contact_scanner_start`, and `contact_scanner_end`. It expands repeated
  `--route KEY:SECONDS,...` entries across `before_bomb`, `before_route`, or
  both runtime-freeze timings, writes one manifest, and forwards approvals to
  `tools/capture_original_actor_contact_procmem.sh`. Added
  `tools/check_actor_contact_route_sweep.py` plus CTest dry-run/output coverage.
- A live `contact_scanner_start` route sweep at
  `/tmp/lezac-actor-contact-route-sweep-live-codex-20260511` ran pre-route
  probes for `x:8.00` and `x:5.00,m:0.50,x:4.00`. Both runs loaded
  `01ED:5CB0` with `runtime_cs=01ED`, `runtime_ds=0C8F`,
  `freeze_runtime_before_route=1`, and `instrumented_freeze_observed=0`.
- A matching `contact_scanner_end` pre-route probe at
  `/tmp/lezac-actor-contact-end-sweep-live-codex-20260511` loaded
  `01ED:604F` on route `x:5.00,m:0.50,x:4.00` and also did not freeze. The
  runtime bytes at that anchor were `c9c2`, so this is best treated as a
  return-tail probe rather than proof that the scanner body is unreachable.
- Added `tools/check_actor_contact_callsite_scan.py` to lock the static
  contact-scanner anchors in `LEZAC.EXE`: entry bytes `55 89` at `1000:5CB0`,
  return bytes `c9 c2 02` at `1000:604F`, the single direct near call at
  `1000:6555` (`e8 58 f7`) targeting `1000:5CB0`, and the actor-update entry
  bytes `55 89` at `1000:6053`.
- Added `tools/check_actor_contact_callsite_context.py` to pin the immediate
  control-flow context around that callsite: `1000:654E` compares the local
  byte at `[bp-31h]` with `06`, `1000:6552` skips to `1000:655B` when it does
  not match, `1000:6554..6557` performs `push bp; call 1000:5CB0`, and
  `1000:6558` jumps to the shared integration path at `1000:73E5`. This keeps
  the next live probe focused on reaching the gated branch rather than
  rediscovering the scanner entry.
- Extended that checker to cover the neighboring `05` gate at `1000:65A2`:
  when the path reaches `1000:65BD`, the branch can enter integration through
  `1000:65D7`; when it reaches `1000:65CE` and the end condition matches, it
  jumps to actor-update end `1000:777F`. A scan of direct near jumps to
  `1000:73E5` inside `1000:6053..777F` now locks the pair
  `1000:6558,1000:65D7`.
- Added process-memory wrapper targets for those gates:
  `actor_update_gate5` at `1000:65A2`, `actor_update_gate5_integration` at
  `1000:65D7`, and `actor_update_gate6` at `1000:654E`. The route-sweep helper
  accepts them too, so the next live DOSBox pass can sweep these branch gates
  directly.
- Added `tools/check_actor_update_dispatch_gates.py` to scan every
  `cmp [bp-31h], imm` gate in `1000:6053..777F`. It currently locks
  `1000:654E = 06`, `1000:65A2 = 05`, and the later `1000:7595 = 05` exit gate
  whose equal branch jumps to `1000:777F`. The late exit is exposed as the
  process-memory target `actor_update_gate5_exit`.
- Added `tools/sweep_original_actor_dispatch_gates.py`, a multi-target planner
  for the mapped actor-update gates. Its default target set is
  `actor_update_gate5`, `actor_update_gate5_integration`,
  `actor_update_gate5_exit`, `actor_update_gate6`, and
  `contact_scanner_callsite`, delegating each target to the existing guarded
  actor/contact route-sweep helper. `tools/check_actor_dispatch_gate_sweep.py`
  locks the default dry-run, custom target/timing routes, live-approval
  refusal, repo-output refusal, and malformed route handling.
- Extended `--debug-actor-update-runtime-oracle` with optional dispatch-gate
  reporting. The parser still requires the original actor/scanner start/end
  anchors, but now appends `dispatch_gates=` with any normalized breakpoints for
  `actor_update_gate5`, `actor_update_gate5_integration`,
  `actor_update_gate5_exit`, `actor_update_gate6`, and
  `contact_scanner_callsite`. Added
  `actor_update_runtime_oracle_dispatch_gates_synthetic.txt` to prove the field
  without changing live gameplay behavior.
- Updated `tools/capture_original_actor_contact_procmem.sh` candidate skeletons
  so actor-update targets list the required oracle anchors
  `1000:5CB0,1000:604F,1000:6053,1000:777F`. Dispatch-gate targets also record
  `dispatch_gate_candidate=<label>` and a `dispatch_gates=` promotion hint,
  making future process-memory captures easier to normalize into oracle
  fixtures.
- A live `contact_scanner_callsite` pre-route probe at
  `/tmp/lezac-contact-callsite-live-codex-20260511` on route
  `x:5.00,m:0.50,x:4.00` loaded `01ED:6555` with old bytes `e858`,
  `freeze_runtime_before_route=1`, `runtime_cs=01ED`, `runtime_ds=0C8F`, and
  `instrumented_freeze_observed=0`. Combined with the entry no-freeze probes,
  this points to the route not reaching the scanner callsite rather than an
  incorrect `1000:5CB0` entry byte mapping.
- Focused native CTest passed for
  `python_tool_syntax_lane_result_preflight|actor_contact_procmem_helper_expectations`
  with 2/2 tests passing. Full native validation then passed again:
  configure/build succeeded and CTest reported 170/170 tests passing.
- After adding pre-route freeze timing, focused helper validation and full
  native validation passed again: configure/build succeeded and CTest reported
  170/170 tests passing.
- After adding the actor/contact route-sweep helper, full native validation
  passed again: configure/build succeeded and CTest reported 172/172 tests
  passing.
- After adding the static callsite scan and `contact_scanner_callsite` probe
  target, full native validation passed again: configure/build succeeded and
  CTest reported 173/173 tests passing.
- After adding the static callsite-context checker, focused Python checks for
  `check_actor_contact_callsite_scan.py` and
  `check_actor_contact_callsite_context.py` passed, then
  `powershell -ExecutionPolicy Bypass -File tools\run_native_windows_validation.ps1
  -BuildDir build-win-codex-vs3 -Configuration Debug` passed:
  configure/build succeeded and CTest reported 174/174 tests passing.
- After extending the callsite-context checker to cover the neighboring `05`
  gate and both direct `1000:73E5` integration jumps, focused CTest
  `actor_contact_callsite_context` passed after reconfigure, and full native
  validation passed again: configure/build succeeded and CTest reported
  174/174 tests passing.
- After adding process-memory probe targets for the `05`/`06` actor-update
  gates, focused Python checks for `check_actor_contact_procmem_helper.py` and
  `check_actor_contact_route_sweep.py` passed, focused CTest
  `actor_contact_route_sweep_output_expectations|actor_contact_procmem_helper_expectations`
  passed after reconfigure, and full native validation passed again:
  configure/build succeeded and CTest reported 174/174 tests passing.
- After adding the dispatch-gate scan and `actor_update_gate5_exit` probe
  target, focused Python checks for `check_actor_update_dispatch_gates.py`,
  `check_actor_contact_procmem_helper.py`, and
  `check_actor_contact_route_sweep.py` passed. Focused CTest
  `actor_update_dispatch_gates|actor_contact_route_sweep_output_expectations|actor_contact_procmem_helper_expectations`
  passed after reconfigure, and full native validation passed again:
  configure/build succeeded and CTest reported 175/175 tests passing.
- After adding the actor dispatch-gate sweep planner, focused Python checks for
  `check_actor_dispatch_gate_sweep.py` and
  `sweep_original_actor_dispatch_gates.py --dry-run` passed. Focused CTest
  `python_tool_syntax_lane_result_preflight|actor_dispatch_gate_sweep_dry_run|actor_dispatch_gate_sweep_output_expectations`
  passed after reconfigure, and full native validation passed again:
  configure/build succeeded and CTest reported 177/177 tests passing.
- After extending the actor-update oracle with `dispatch_gates=`, focused
  fixture validation `check_actor_update_runtime_oracle_fixtures.py` passed with
  5 fixtures (2 valid, 3 malformed). A direct Visual Studio build hit the known
  duplicate `Path`/`PATH` MSBuild environment issue, so validation continued
  through `tools\run_native_windows_validation.ps1`; the wrapper build
  succeeded and CTest reported 178/178 tests passing.
- After adding dispatch-gate promotion hints to actor/contact process-memory
  candidate skeletons, focused helper validation
  `check_actor_contact_procmem_helper.py` passed, and full native validation
  through `tools\run_native_windows_validation.ps1` passed again:
  configure/build succeeded and CTest reported 178/178 tests passing.
- The actor dispatch-gate sweep summary now reports
  `dispatch_gate_freezes=` and `observed_dispatch_gates=` separately from
  broader route-freeze targets, with the former counting freeze events and the
  latter listing unique mapped target names. Each freeze detail carries
  `dispatch_gate_candidate=`. `--require-dispatch-gate-freeze` makes live sweep
  summaries fail when a route only froze non-dispatch probes, so future
  branch-reachability evidence cannot accidentally promote an entry/exit stop
  as a mapped actor/contact gate hit.
- A WSL-native process-memory dispatch sweep at
  `/tmp/lezac-actor-dispatch-wsl-live-codex-20260616` passed the real Ubuntu
  preflight and froze `actor_update_gate6` at runtime `01ED:654E` with
  `DS=0C8F` on both `x:2.00` and `x:5.00,m:0.50,x:2.00` before-route probes.
  `contact_scanner_callsite` still did not freeze in that focused sweep, and
  both generated gate6 candidates remain `incomplete` because they lack the
  semantic actor/contact records and breakpoints required by the runtime
  oracle. This is branch-reachability evidence only, not a promoted oracle
  fixture.
- Contact-scanner readiness now checks the same field-level shape consumed by
  `--debug-contact-scanner-runtime-oracle`: subject/other actor records must
  carry `w` and `h`, and `contact_scan` must carry `overlap_x` and
  `overlap_y`. Synthetic summary and fixture tests now reject candidates that
  have the right record names but would fail the real oracle parser.
- After adding the actor/contact process-memory wrapper and dry-run CTest,
  `powershell -ExecutionPolicy Bypass -File tools\run_native_windows_validation.ps1
  -BuildDir build-win-codex-vs3 -Configuration Debug` passed: configure/build
  succeeded and CTest reported 170/170 tests passing.
- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer level1_bomb_route` passed with route length `55`, start
  `(104,168)`, final `(186,168)`, bomb tile `(24,22)`, and route bomb
  placement through the `N` key event path.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer death_reentry` passed with state-2 countdown `60`, lives
  `2`, energy `100`, and reentry confirmed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer death_visuals` passed with state-2 visual frames
  `0x4a -> 0x4b -> 0x4c` and `visual_claim=0`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer level_transition` passed with level-1 completion after
  `101` transition frames and level 2 loaded.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer portal_weapon_route` passed on decoded portal level `3`
  with medium weapon switch, medium bomb placement, portal key `31`, and
  cooldown `30`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer records_flow` passed with temporary record score
  `999999`, level `3`, and name `bot`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_bomb_reward` passed with a bomb-killed monster,
  reward collection, and score delta `3000`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_behavior3_multihit` passed with one-pixel
  behavior-3 movement, first-hit HP `2`, second-hit kill, and reward
  collection.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_behavior4_chase` passed with behavior-4 chase
  movement `2`, timer `1`, and medium-bomb kill.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_spawner_cycle` passed with level-1 spawner slot
  reservation, immediate release on death, and deterministic respawn.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_spawner_behavior4_level2` passed with level-2
  behavior-4 spawner fields `ai0=13 ai1=271 ai2=62 hp=3` and positive `vx8`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_spawner_behavior4_level3` passed with level-3
  behavior-4 spawner fields `ai0=20 ai1=214 ai2=66 hp=4` and diagonal
  `vx8/vy8 = 178/-119`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_behavior4_target_selection` passed with initial
  player-2 targeting, retarget to player 1 when player 2 is dead, and retarget
  back to player 2 when player 1 is dead.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer collapse_playback_route` passed with collapse queue count
  `2` and playback duration `24` frames.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer two_player_route` passed with player-2 movement and one
  player-2 bomb placed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer two_player_progression` passed with player-2 reentry,
  player-2 bomb placement, and player-2 score `1000`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --capture-frame-sequence level1_bomb_route /tmp/lezac-autoplayer-frames`
  passed and wrote seven PPM frames plus `manifest.txt`; route bomb placement
  also uses the `N` key event path.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --capture-frame-sequence monster_spawner_behavior4_level2
  /tmp/lezac-capture-b4-level2` passed and wrote four PPM frames plus
  `manifest.txt` with live spawner/monster fields.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --capture-frame-sequence monster_spawner_behavior4_level3
  /tmp/lezac-capture-b4-level3` passed and wrote four PPM frames plus
  `manifest.txt` with diagonal behavior-4 spawn state.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --capture-frame-sequence monster_behavior4_target_selection
  /tmp/lezac-capture-b4-target` passed and wrote six PPM frames plus
  `manifest.txt` with player-dead flags and retarget direction changes.
- `tools/capture_cpp_frames.sh ./build/lezac_cpp
  /tmp/lezac-autoplayer-frames-wrapper` passed.
- `bash -n tools/capture_original_dosbox_frames.sh` passed. A local DOSBox run
  produced correctly named screenshots and manifest entries. Earlier visual
  inspection showed the old `--window` input path remained on the original
  menu; after switching to focused no-window input with original player-1
  controls, frame inspection confirmed level-1 gameplay, visible bomb
  placement, and visible explosion playback.
- `python3 -m py_compile tools/capture_original_explosion_procmem.py` passed.
- Bundled Windows Python syntax validation also passed with
  `C:\Users\andrz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m py_compile tools\capture_original_explosion_procmem.py`.
- Bundled Windows Python syntax validation now also covers
  `tools/check_explosion_lane_result_preflight.py`.
- `tools/check_explosion_lane_result_preflight.py` passed with the bundled
  Windows Python, both with explicit `.` asset directory and with its default
  repository-root asset directory. It verified `1000:3D3F`, `1000:3ED3`,
  expected original bytes `268805`, scratch `0xF280`, body `0xF200`, exact
  trampoline body bytes, the shared result-write tail
  `8b46f63b46f075c58a46f3c47e04268805c9c20600`, and the wrong-offset guard.
- `tools/capture_original_lane_result_runtime.py --preflight-only --asset-dir .`
  passed with the bundled Windows Python and reported
  `lane_result_capture_orchestrator=ok mode=preflight`.
- `tools/capture_original_lane_result_runtime.py --preflight-only .` also
  passed, verifying the positional asset-dir compatibility path. The CTest
  suite now covers both preflight-only forms, and the wrapper CTest regexes now
  pin `result_tail=1` plus the exact `result_tail_bytes` value so wrapper
  success cannot silently drop or weaken the static tail check.
- `tools/capture_original_lane_result_runtime.py C:\Temp\lezac-lane-result-dry-run
  . --dry-run --skip-oracle` passed and reported `offsets=2`,
  `capture_commands=2`, `oracle_commands=0`, `offset_labels=3d3f,3ed3`, and
  `offset_addresses=1000:3D3F,1000:3ED3` while printing both generated capture
  commands.
- `tools/capture_original_lane_result_runtime.py C:\Temp\lezac-lane-result-dry-run
  . --dry-run` passed and reported `oracle_commands=2`, verifying the generated
  C++ oracle command plan as well.
- `tools/capture_original_lane_result_runtime.py C:\Temp\lezac-lane-result-dry-run
  . --dry-run --skip-oracle --offset 3D3F` and the equivalent `--offset
  1000:3ED3` command both passed with one generated capture command; invalid
  `--offset 3D2D` was rejected by argument parsing.
- `tools/capture_original_lane_result_runtime.py C:\Temp\lezac-lane-result-dry-run
  . --dry-run --skip-oracle --offset forward` and the equivalent `--offset
  reverse` command both passed with one generated capture command; invalid
  `--offset sideways` was rejected by argument parsing. CTest now locks the
  single reverse-alias dry-run output as `offset_labels=3ed3` and
  `offset_addresses=1000:3ED3`.
- Repeated offset selection, such as `--offset 3D3F --offset 1000:3D3F`, now
  deduplicates to one generated capture command while preserving user-specified
  offset order for mixed captures. CTest now locks the mixed-order
  reverse-then-forward dry-run as `offset_labels=3ed3,3d3f` and
  `offset_addresses=1000:3ED3,1000:3D3F`.
- Added `explosion_lane_result_capture_orchestrator_dry_run_timing_args`, which
  locks dry-run pass-through for the route/runtime timing knobs sent to
  `tools/capture_original_explosion_procmem.py`.
- `tools/capture_original_lane_result_runtime.py C:\Temp\lezac-lane-result .`
  correctly refused runtime capture without both approval flags.
- Added CTest coverage for the orchestrator safety rails:
  `explosion_lane_result_capture_orchestrator_bad_offset`,
  `explosion_lane_result_capture_orchestrator_refuses_repo_output`, and
  `explosion_lane_result_capture_orchestrator_requires_approval`.
- `tools/check_explosion_lane_result_wrapper.py .` passed with the bundled
  Windows Python and reported `lane_result_wrapper_output=ok cases=13`,
  verifying the wrapper output matrix without DOSBox or process-memory access.
- `tools/check_explosion_lane_result_orchestrator.py` now also verifies that
  the wrapper-output checker is wired into CTest; it reports
  `lane_result_orchestrator_cmake=ok tests=15 will_fail=3`.
- `tools/check_explosion_lane_result_fixtures.py` passed with the bundled
  Windows Python and reported `lane_result_fixtures=ok files=13 valid=2
  malformed=11 cmake_tests=13`.
- A bundled Python import/assertion check passed for
  `build_freeze_patch("lane-result-cs-scratch", 0x3D3F/0x3ED3)`: both offsets
  return a three-byte near jump, scratch `0xF280`, length `0x12`, body
  `0xF200`, a freezing `EB FE` tail, expected original bytes `268805`, and
  invalid offset `0x3D2D` is rejected.
- A direct shipped-EXE byte check passed: with MZ image base `0x0770`,
  `1000:3D3F` maps to file offset `0x44AF` and `1000:3ED3` maps to
  `0x4643`; both contain `26 88 05`, matching the new patch guard. The
  preflight now also pins the surrounding static tail as loop-end compare,
  `mov al,[bp-0d]`, `les di,[bp+4]`, `mov es:[di],al`, `leave`, `ret 6`.
- `tools/capture_original_explosion_procmem.py NUL .
  --describe-freeze-patch --freeze-ghidra-offset 1000:3D3F
  --freeze-patch-mode lane-result-cs-scratch` passed and printed
  `freeze_patch_description=ok`, `file_offset=0x44af`,
  `expected_original_bytes=268805`,
  `patch_bytes=e9beb4`, `scratch_offset=0xf280`, and `body_offset=0xf200`.
- The same describe preflight for `1000:3ED3` passed with
  `file_offset=0x4643`, `expected_original_bytes=268805`,
  `patch_bytes=e92ab3`, `scratch_offset=0xf280`, and `body_offset=0xf200`.
- The equivalent CTest entries are now
  `explosion_freeze_patch_describe_lane_result_3d3f` and
  `explosion_freeze_patch_describe_lane_result_3ed3`; both passed under the
  WSL build tree on 2026-05-06.
- The wrong-offset preflight was checked directly and fails cleanly with
  `freeze_patch_description=error reason=--freeze-patch-mode
  lane-result-cs-scratch is only valid at 1000:3D3F or 1000:3ED3`.
- WSL validation was restored for the 2026-05-06 continuation:
  `cmake --build build` passed, and `ctest --test-dir build
  --output-on-failure` passed with 146/146 tests before the promoted reverse
  fixture was added.
- The first approved two-offset WSL/DOSBox process-memory run wrote captures
  under `/tmp/lezac-lane-result-runtime-20260506`. It proved the reverse
  `3ED3` route reached the runtime-child-memory freeze, but the oracle rejected
  the candidate because the fixture writer did not emit explicit
  `freeze_expected_old_bytes` / `freeze_old_bytes` keys. The capture helper now
  emits both keys in candidate fixtures, and
  `tools/check_explosion_lane_result_layout.py` verifies that writer contract.
- The repaired targeted command
  `python3 tools/capture_original_lane_result_runtime.py
  /tmp/lezac-lane-result-runtime-20260506-reverse .
  --approve-procmem --approve-runtime-instrumentation --offset reverse`
  passed end-to-end, wrote `manifest.txt`, and parsed the promoted
  `3ED3` candidate with `--debug-explosion-playback-oracle`.
- After promoting the reverse fixture, `cmake --build build`,
  `ctest --test-dir build -R lane_result --output-on-failure`, and
  `ctest --test-dir build --output-on-failure` all passed under WSL. The
  focused lane-result slice reported 36/36 tests, and the full suite reported
  147/147 tests.
- The same 2026-05-06 two-offset attempt left the forward `3D3F` candidate as
  `runtime_child_memory_patch_loaded_no_freeze_observed`; this is a route/timing
  gap, not a parser claim. Later default, right-hold timing, and before-bomb
  retries also loaded the patch without freezing.
- A labeled runtime-seeded forward retry under
  `/tmp/lezac-lane-result-forward-seeded-after-20260506` did freeze
  `1000:3D3F` and produced the promoted
  `explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded.txt`
  fixture. Natural-route forward result-write evidence remains pending.
- Route-step natural retries under
  `/tmp/lezac-lane-result-forward-routestep-x1p5-z0p5-20260506`,
  `/tmp/lezac-lane-result-forward-routestep-x2p0-c0p5-20260506`, and
  `/tmp/lezac-lane-result-forward-routestep-x2p0-m0p35-20260506` all loaded the
  `1000:3D3F` patch without freezing. The `x:2.00,c:0.50` run was promoted as
  a natural no-freeze fixture because it preserves nonzero lane-global state.
- A native PowerShell `cmake --build build` attempt was also rejected because
  the existing build tree was configured under `/mnt/c/...` and expects
  `/usr/bin/gmake`; use WSL or a fresh native build tree for full validation.
- A fresh native PowerShell configure probe failed because no C++ compiler was
  available (`No CMAKE_CXX_COMPILER could be found`). The generated
  `build-win-probe/` directory is ignored as build output because the sandbox
  blocked recursive cleanup.
- The prior `.git/index.lock: Permission denied` staging blocker was resolved
  before the lane-result checkpoint was rebased and pushed.
- `python3 tools/capture_original_explosion_procmem.py --help` passed and
  lists the route-input options.
- `cmake --build build` passed under WSL after the queue-counter oracle update.
- `ctest --test-dir build -R explosion_playback_oracle --output-on-failure`
  passed: 5/5.
- `ctest --test-dir build -R
  "damage_queues|bomb_object_explosion_effects|collapse_playback_route|frame_sequence_capture_dummy"
  --output-on-failure` passed: 4/4.
- `python3 tools/capture_original_explosion_procmem.py
  /tmp/lezac-counter-selected-20260424-codex-1 . --approve-procmem
  --mode regular --level-start-seconds 1.5 --right-hold-seconds 2.0
  --bomb-hold-seconds 0.25 --sample-seconds 2.5 --sample-interval 0.04
  --route-state-interval 0.25 --sample-screenshot-seconds 0.5,1.0,1.5,2.0`
  passed under WSL/Xvfb. Frame inspection showed the placed bomb, visible
  explosion, and later smoke/collapse playback. The generated candidate parsed
  through `--debug-explosion-playback-oracle` with `visual_claim=0`.
- `./build/lezac_cpp --debug-bomb-object-explosion-effects` passed and printed
  level-1 collapse offsets `0x0a06..0x0a08`, word `0x0009`, flagged word
  `0x8009`, and affected bytes `4`.
- `ctest --test-dir build -R
  "bomb_object_explosion_effects|damage_queues|explosion_playback_oracle"
  --output-on-failure` passed: 7/7.
- `python3 tools/capture_original_explosion_procmem.py
  /tmp/lezac-wide-debris-20260424-codex-1 . --approve-procmem --mode regular
  --level-start-seconds 1.5 --right-hold-seconds 2.0 --bomb-hold-seconds 0.25
  --sample-seconds 2.5 --sample-interval 0.04 --route-state-interval 0.5
  --sample-screenshot-seconds 1.5,2.0` passed under WSL/Xvfb. Frame inspection
  confirmed bomb, explosion, and smoke/collapse playback, and the generated
  candidate parsed with counter-selected debris base `DS:292b`.
- `ctest --test-dir build -R explosion_playback_oracle --output-on-failure`
  passed after adding sparse high-counter fixture coverage: 6/6.
- `tools/compare_original_cpp_frames.sh
  /tmp/lezac-frame-compare-improved-20260424-codex-1812 .
  level1_bomb_route` passed and wrote paired C++/original frames plus diffs.
- `python3 tools/capture_original_explosion_procmem.py
  /tmp/lezac-explosion-procmem-selected-20260424-codex-3 .
  --approve-procmem --mode regular --level-start-seconds 1.5
  --sample-seconds 5.0 --sample-interval 0.04
  --sample-screenshot-seconds 0.5,1.0,1.5,2.0,3.0
  --right-hold-seconds 2.0 --bomb-hold-seconds 0.25` passed under WSL/Xvfb.
  Visual inspection showed bomb placement, visible explosion at `1.5s`, and
  smoke playback at `2.0s`; the generated candidate decoded selected
  `DS:662F` collapse bytes through the C++ oracle with `visual_claim=0`.
- `python3 tools/capture_original_explosion_procmem.py
  /tmp/lezac-route-state-20260424-codex-1 . --approve-procmem --mode regular
  --level-start-seconds 1.5 --sample-seconds 1.0 --sample-interval 0.12
  --route-state-interval 0.25 --sample-screenshot-seconds 0.5` passed under
  WSL/Xvfb. It wrote `route_state_samples.tsv` and `route_state_dumps.txt`;
  frame inspection of `040_sample_0p50s.png` and `090_after_sampling.png`
  confirmed level-1 bomb placement and visible explosion playback. The
  generated candidate still parsed through `--debug-explosion-playback-oracle`
  with `visual_claim=0`.
- Runtime child-memory freeze probes at `1000:3A7E` and `1000:3FA6` both
  patched after bomb input at `0.160s` with route queue score `40`.
  `1000:3A7E` loaded `8b16 -> ebfe` but did not freeze and continued into
  visible explosion playback. `1000:3FA6` loaded `5589 -> ebfe` and froze, but
  frame inspection showed a pre-visible-explosion/armed-bomb state, so this is
  still reachability evidence rather than promoted playback evidence.
- A late-gated runtime child-memory freeze probe at `1000:432A` used queue
  score `150`, selected bases `DS:209e`, `DS:6620`, `DS:c22e`, and nonzero
  debris/collapse/effect counts `28/20/28`. It loaded `5589 -> ebfe` at
  `1.246s` after bomb input without timed screenshots, did not freeze, and the
  final frame inspection still showed visible playback. An earlier `432A` run
  requiring `DS:662F` correctly withheld the patch because this route selected
  `DS:6620`.
- Tuned late-collapse probes at `1000:3BB2` and `1000:3D46` both loaded
  runtime child-memory patches after queue growth and did not freeze while
  visible playback continued. `3BB2` patched at `1.286s` with score `150`;
  `3D46` patched at `1.649s` with score `110`. The first strict preset run for
  `3BB2` correctly withheld the patch because this route's effect nonzero count
  stayed below `20`, so the repeated probe lowered only that threshold to `16`.
- Tail-confirmed early runtime freeze probes mapped the dispatch path:
  `1000:75F1` and `1000:414A` froze on armed-bomb frames before visible
  playback, while `1000:370E` froze on a visible explosion frame. The `370E`
  candidate parsed through the C++ oracle with selected bases `DS:209e`,
  `DS:6611`, and `DS:c22e`, and remains instrumentation evidence with
  `visual_claim=0`.
- Instrumented temp-copy runs patched and loaded freeze loops at `1000:3A7E`,
  `1000:3BB2`, `1000:3FA6`, and `1000:432A`. `1000:3FA6` reliably froze, but
  before visible explosion playback; `1000:3A7E` produced one explosion-frame
  freeze observation but did not reproduce on the next run; `1000:3BB2` and
  `1000:432A` continued through the route. No original fixture was promoted.
- Static disassembly now maps the playback consumer bridge: `1000:45fa..4d3b`
  iterates effect/debris queue records and calls the forward/reverse lane
  passes at `1000:4c96`/`1000:4ca9`. `--debug-damage-queues` locks those
  addresses, the `1000:3a7e`/`1000:3b18` lookup helpers, one-based queue slot
  tags, first-slot lane write offsets, and collapse span weight metadata.
- Runtime child-memory probes now show `1000:4C96` can be patched after queue
  growth but is not reached by the current level-1 route, while `1000:45FA`
  freezes on a visible explosion/playback frame with selected bases `DS:209e`,
  `DS:6620`, and `DS:c22e`. A follow-up `1000:492F` probe froze on the same
  visible playback window with `DS:207e=0x00c7`, explaining the `4C96` skip:
  static code requires `DS:207e >= 0x00c8` before entering that interior path.
  Replaying the earlier high-counter route timing patched `1000:4C96` while
  `DS:207e=0x00c8` and `selected_debris_base=DS:292b`, but the frame sequence
  advanced through the tail screenshots with `instrumented_freeze_observed=0`.
  A route-tuned temp-copy patch at `1000:4B3F` then froze on the visible blast
  frame with `DS:207e=0x00c8`, proving the high-debris interior reaches the
  target-byte sample before the unresolved `4B6A`/`4C20`/`4C75` branch path.
  The helper now emits target fields; a follow-up `1000:4B61` freeze stopped
  at the target-byte gate with target offset `0x0541`, target byte `0x00`,
  word-layer value `0x0000`, and `DS:c204=0x003c`, identifying the next static
  branch as the zero-target path at `1000:4B6A`.
  The helper can now require that decoded target byte before applying a runtime
  child-memory patch; two gated `1000:4B6A` probes reached the later `DS:292b`
  route state with target byte `0x33`, so they intentionally did not patch and
  are recorded as timing evidence rather than executed-branch evidence.
  A faster gated run at
  `/tmp/lezac-4b6a-target-byte-fast-runtime-20260424-codex-1` used
  `--sample-interval 0.005` and froze `01ED:4B6A` after `1.436s`, with
  `DS:207e=0x00c8`, selected debris base `DS:292b`, target byte `0x00`, and
  word-layer value `0x0000`; frozen screenshots matched the visible blast
  frame hash. A compact original-runtime oracle fixture now covers this
  zero-target branch evidence.
  Static disassembly now maps `1000:4C75` as the `[bp-4] > 0` word gate for
  the later `4C96`/`4CA9` lane calls. A first broad `4C75`/`4C96` probe loaded
  patches too late and did not freeze; an early-gated `4C75` rerun froze at
  `01ED:4C75`. Relaxing the `4C96` gate to the durable selected-debris and
  target-byte-zero conditions then froze `01ED:4C96`, and the paired `4CA9`
  probe froze `01ED:4CA9`. Compact original-runtime fixtures now cover the
  word gate plus forward and reverse lane-call evidence. The promoted fixtures
  remain instrumentation evidence with `visual_claim=0`; no live C++ behavior
  changed from this proof yet. The `damage_queues` diagnostic now also locks
  the `4B3F`/`4B61`/`4B6A`/`4C20`/`4C64`/`4C75`/`4CAE` branch anchors and the
  `DS:659A`/`DS:655E`/`DS:2078` staging globals; see
  `docs/recovery/high_debris_lane_branch_model_2026-04-25.md` for the local
  byte dump and static model. The explosion playback oracle now emits explicit
  one-hot observed-freeze flags for `4B6A`, `4C75`, `4C96`, and `4CA9`, and
  CTest pins the expected flag for each promoted original-runtime fixture.
  The capture helper and oracle now also name post-call return anchors
  `1000:4C99` and `1000:4CAC`, so the next original probes can stop after the
  forward/reverse helper calls and preserve helper-written lane bytes. Runtime
  child-memory attempts at `4C99` were timing-sensitive, but temp-copy
  instrumentation froze both post-call anchors in the same high-counter state:
  selected debris base `DS:292B`, selected collapse base `DS:663E`, target byte
  `0x00`, first selected debris bytes
  `41 05 04 c0 26 00 1c 00 00 67 80`, and first selected collapse bytes
  `06 0a 08 0a 09 80 00 04 00 00 04 00 00 01 04`. New fixtures pin the
  `observed_effect_forward_return`/`observed_effect_reverse_return` flags.
  The refreshed capture helper now includes `DS:78C0`, and both post-call
  fixtures pin helper inputs `DS:78D2=0xF7` and `DS:78D4=0xFC`; the sampled
  staging globals are raw-zero at the freezes (`DS:2078=0x00`,
  `DS:655E=0x0000`, `DS:659A=0x0000`), so the exact lifetime of the static
  staging fields remains unresolved. A follow-up runtime-child instrumentation
  mode for `1000:4C75` now copies the live `[BP-4]` word to `CS:4C7E` before
  freezing; the promoted fixture records `instrumented_bp4_local_value=0x0003`
  with matched tail screenshots. This directly proves one positive local-word
  gate while also showing that the sampled selected word-layer summary
  (`0x0000`) can describe adjacent queue state rather than the exact loop
  iteration frozen by the patch. The C++ frame capture manifest now records
  first debris/collapse/effect queue fields per checkpoint. A WSL/Xvfb
  original-vs-C++ level-1 bundle captured all seven route labels; visual
  inspection confirmed the original reached blast/playback frames. Pixel diffs
  remain large because the C++ renderer is provisional, but the queue metadata
  exposes the next concrete mismatch: C++ records the level-1 collapse span
  `0x0A06..0x0A08`, `flagged=0x8009`, `affected=4`, `count=2` with
  `collapse0_forward=0`, `collapse0_reverse=0`, while original post-call
  fixtures preserve the same span with helper-written reverse lane byte
  `0x04`. Static disassembly of `1000:3BB2`/`1000:3D46` now has a dedicated
  `--debug-lane-helper-model` diagnostic: it locks the `[BP+4]` far input
  pointer, `[BP+8]` weight byte, one-based `DS:2078` staging loop,
  `DS:655C`/`DS:6598` inputs, `DS:65D4` tag table, `0x4E20` debris marker, and
  forward/reverse write bases `DS:6617`/`DS:2097` and
  `DS:6618`/`DS:2098`. The follow-up `--debug-lane-blend-arithmetic`
  diagnostic now locks `0920:0945` as signed 32-bit division: numerator in
  `DX:AX`, denominator in `BX:CX`, quotient in `DX:AX`, consumed lane byte in
  `AL`, truncation toward zero, and zero-divisor branch `0920:09AC` with
  `AX=0x00C8`. A 2026-04-28 runtime child-memory scratch capture now freezes
  the forward lane blender at `01ED:3CD4`, after immediate runtime patching
  and before the far division helper registers are loaded. The promoted
  `explosion_playback_oracle_original_3cd4_lane_div_scratch_runtime.txt`
  fixture records would-be `DX:AX=0xFFFF:0xFFF8`, `BX:CX=0x0000:0x0005`,
  active staging count/index `1`, matching numerator/weight locals, and live
  staging globals `DS:2078=1`, `DS:655E=0x8009`, `DS:659A=0x0A7A`. A
  2026-04-29 follow-up froze the actual forward far-call site at `01ED:3CE3`;
  the promoted
  `explosion_playback_oracle_original_3ce3_lane_div_scratch_runtime.txt`
  fixture records loaded registers `DX:AX=0x0000:0x001C`,
  `BX:CX=0x0000:0x0010`, active count/index `1`, and matching
  numerator/weight locals. Immediate reverse-helper probes at `01ED:3E68` and
  `01ED:3E77` loaded their runtime patches but did not freeze on the same
  route, so they are not promoted. A later runtime scratch probe froze the
  forward collapse writeback at `01ED:3D1B`; the promoted
  `explosion_playback_oracle_original_3d1b_lane_write_scratch_runtime.txt`
  fixture records output byte `0x01`, selected tag `0x0003`, `DI=0x002D`,
  active count/index `1`, and result local `0x01`, proving the original is
  about to write to `DS:6617 + 0x002D` with collapse stride `0x0F`. A
  follow-up proved that inline lane-write instrumentation is unsafe for
  adjacent debris writeback probes because it can overwrite the shared loop
  join at `1000:3D31`. The capture helper now uses a safe three-byte near-jump
  trampoline for lane-write probes, with runtime code at `CS:F000` and scratch
  at `CS:F080`. The promoted trampoline fixtures record a fresh `3D1B`
  forward collapse stop (`output=0x04`, `tag=0x0004`, `DI=0x003C`) and a
  `3EAF` reverse collapse stop (`output=0x00`, same tag/DI), proving both
  `DS:6617 + 0x003C` and `DS:6618 + 0x003C` for the same selected tag. Safe
  trampoline probes at `3D2D` and `3EC1` loaded but did not freeze on this
  route, so debris-side writeback still needs a different route or
  debugger-seeded setup. A later labeled runtime seed now patches the original
  `4C96`/`4CA9` call sites to write `DS:655E=0xC004` before calling the
  original helper body. Those seeded fixtures freeze forward debris writeback
  at `3D2D` (`output=0x35`, `tag=0x4EE8`, `DI=0x0898`) and reverse debris
  writeback at `3EC1` (`output=0x00`, same tag/DI), proving the debris marker
  relation `(0x4EE8 - 0x4E20) * 0x0B = 0x0898`. They are not natural-route
  evidence. The 2026-06-15 route sweep later promoted natural reverse `3EC1`,
  leaving natural forward `3D2D` as the remaining debris writeback target.
  Temp-copy lane-div
  instrumentation is intentionally rejected because the larger patch body can
  overlap DOS relocation words near the far-call operand. Live playback
  behavior is unchanged until natural forward debris-side writeback evidence
  rounds out the queue-lane model. This also explains why post-call fixtures can preserve
  helper-written lane bytes while sampled staging globals are already zero.
- `./build/lezac_cpp --debug-passable-objects` passed with
  `level1_route_clear=1`.
- `ctest --test-dir build -R "autoplayer|frame_sequence_capture"
  --output-on-failure` passed: 20/20.
- `ctest --test-dir build -R explosion_playback_oracle
  --output-on-failure` passed under WSL: 31/31.
- `ctest --test-dir build --output-on-failure` passed under WSL: 111/111.
- `./build/lezac_cpp --validate` passed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --smoke-controls` passed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-level1-frame-inspection` passed.
- Frame inspection performed on generated checkpoints
  `020_level1_tile24_aligned` and `040_level1_tile24_explosion` after converting
  temporary PPM files to PNG for local viewing.
- `git diff --check` passed.

## Remaining Top Gaps

- Confirm the low-word passable-object route and level-1 bomb-route timing
  against original `LEZAC.EXE` with DOSBox frame inspection or debugger/runtime
  evidence.
- Use the now-working original level-1 keyboard route to tie explosion
  screenshots to debugger/process-memory bytes from the relevant
  `1000:3a56..4d3b` execution window, then extend original capture beyond the
  level-1 route.
- Finish paired original-frame comparison for the recovered row-byte-3 state-2
  death renderer before promoting exact live dead-player presentation.
- Exact explosion/debris/collapse sprite playback around `1000:3a56..4d3b`
  remains blocked on frame-table/sprite semantics, but process-memory
  instrumentation has promoted original fixtures for branch reachability,
  post-call lane bytes, the `4C75` live word gate, one `3CD4` mid-helper
  lane-division setup, one `3CE3` forward divide call-site register capture,
  collapse writeback captures at `3D1B` and `3EAF`, and seeded debris
  writeback captures at `3D2D` and `3EC1`, plus final far-pointer result-write
  captures at reverse `3ED3`, seeded forward `3D3F`, natural forward `3D3F`,
  and natural reverse debris writeback at `3EC1`. Next evidence should target
  natural forward debris writeback at `3D2D` before changing live playback
  behavior.
- `PROEFS.SON` bytes `+4..+5` are now classified as preserved but
  playback-unused by the recovered `1000:0FBE..1088` tick routine and C++
  mutation diagnostics. Any source/editor meaning outside playback remains
  unknown.
- Many non-explosion sound callsites still need exact cursor/priority mapping;
  the sound-callsite oracle and DOSBox-debug capture planner are ready for
  original debugger transcripts. The remaining direct `playSound(index)`
  callers are compatibility hooks until original cursor/priority writes are
  recovered; the current static context audit rules out the name-entry,
  record-table, post-end-flow-record, collapse playback, bomb-object high-gate,
  and non-objective tile-gate candidates for those two live hooks. The live
  diagnostic now reports
  `capture_blockers=objective_pickup:rejected_static_candidates,level_complete:no_static_candidate`
  so the remaining sound evidence queue is explicit. The unresolved static
  sound diagnostic now also reports capture classes and narrows the next
  actor/contact runtime sound queue to
  `actor_contact_capture_candidates=0x5e81:contact_scanner,0x7386:actor_update`,
  keeping UI, explosion, effect-extent, and no-latch writes separate from
  same-location runtime-capture candidates.
- Exact actor update behavior around `1000:6053..777f`, especially original
  contact flags, passability thresholds, tile snapping, behavior-3 ledge/wall
  handling, and behavior-4 collision response. The synthetic actor-update oracle
  is ready; original runtime/debugger fixtures are still pending.
- The routine at `1000:5cb0..604f`, long tracked as a "probable contact
  scanner", is now identified as the level-7 boss-head brain:
  the sole call at `1000:6555` sits behind the behavior/state `06` gate,
  which only boss-head actors carry. The existing scanner-named capture
  targets and fixtures remain valid as addresses. Live actor/visual/link
  snapshots now confirm the boss load and initial placement; frame-by-frame
  confirmation of its motion/collision behavior, and of the actual
  player/monster contact model elsewhere in `1000:6053..777f`, still needs
  original evidence.
- Runtime reachability of the `DS:79b9` fallback, exact original active-player
  accounting, and exact dead-player visual playback from original frame bytes
  remain unresolved now that the delayed state-2 life-count decrement, fallback
  disassembly model, and live C++ fallback boundary are covered.
- Exact original two-player panel artwork and full death/reentry presentation
  remain unresolved. The current C++ central objective panel is covered by
  `--debug-two-player-hud-panel`, but original frame comparison is still
  required before the artwork/layout can be promoted.
- Exact original runtime consumption of impact/death/reward sprite frames
  remains unresolved. The current static candidate table is pinned by
  `--debug-monster-sprite-table-model`, but original frame/debugger evidence is
  still required before those presentation details can be promoted.
- `GRAN.MST` loader and field layout are now statically recovered
  (`--debug-gran-static-consumer-model`): it is the level-7 multi-segment
  boss actor file read by `1000:08A5` behind the `DS:0x79B7 == 7` gate, and
  the C++ port now plays the boss from that recovered model
  (`spawnLevel7Boss()`, `--debug-gran-boss-model`,
  `--debug-autoplayer boss_level7`). Native level transitions and live
  original actor/visual/link snapshots confirm its one-based table indexing,
  `+2` visual rebase, and exact initial placement. The remaining gap is exact
  frame-by-frame boss motion, collision, and presentation timing.

## Next Planned Target

Do not repeat the unchanged `forward-debris-expanded` matrix, the early
`x:2.00,c:0.50` target-byte/word-layer gates, the nearby `c` timing
lane-global gates, the now-classified `x:2.00,m:0.35` natural `3D2D` gated
retry, the follow-up helper-tag sweep routes `x:1.50,m:0.35`,
`x:2.50,m:0.35`, `x:2.00,m:0.15`, and `x:2.00,m:0.65`, or the expanded
no-freeze subset `x:1.75`, `x:2.25`, `x:2.00,c:0.25`, `x:2.00,c:0.75`, and
`x:5.00,m:0.50,x:2.00`, or the final helper-tag-open routes
`x:3.00,z:0.50,x:2.00` and `x:1.50,left:0.50,x:2.00`, or the broadened
lane-div routes `x:8.00` and `x:5.00,m:0.50,x:4.00`, or the delayed-bomb
lane-div routes `x:4.00,m:0.50,x:3.00`, `x:6.00,m:0.50,x:3.00`, and
`x:4.00,z:0.50,m:0.50,x:3.00`, or the backtrack lane-div routes
`x:4.00,Left:1.00,m:0.50,x:4.00`,
`x:6.00,Left:1.00,m:0.50,x:4.00`, and
`x:4.00,z:0.50,Left:1.00,m:0.50,x:4.00`. Also do not repeat the
behavior-4 level-3 spawner branch smoke
`monster_spawner_behavior4_level3`/`x:2.00` for `behavior4_branch_start` or
`behavior4_branch_end`; both branch patches loaded and stayed no-freeze. The
positive `m` routes
reach the high-debris
branch/forward-helper area, but the natural helper iterations observed so far
write collapse tags `0x0002` or `0x0005` at `3D1B`; the expanded subset did
not reach either helper write site, and the helper-tag-open routes also stayed
valid no-freeze for both `3D1B` and `3D2D`. The broadened lane-div pass loaded
the `3CE3` runtime patch for both long routes but produced no forward divide
freeze and no debris-marker route-state sample. The updated lane-write summarizer
classifies the prior helper-tag search as `debris_tag_candidates=0`,
`collapse_tag_candidates=2`, `max_lane_write_tag=0x0005`, and
`--require-debris-tag` fails with `reason=no_debris_tag_candidates`. The next
useful original-evidence step should broaden the route/control hypothesis
beyond this level-1 timing family or construct a seeded setup that reaches a
natural `4C96 -> 3BB2` forward-helper iteration. Use
`tools/summarize_lane_div_route_sweep.py --require-forward-divide` to prove
candidate route reachability at `1000:3CE3`, then target `1000:3D2D` only after
`tools/summarize_lane_write_route_sweep.py <manifest> --require-forward-debris-tag`
passes and, when useful, writes a
`lane_write_forward_debris_route_candidates` handoff. Otherwise return to
DOSBox frame/debugger evidence for behavior-4 movement, targeting, and respawn
timing, but do not treat the all-anchor before-route `x:2.00` behavior-4 pass
as branch evidence: it froze only `spawner_loop_start`, `integration_8_8_start`,
and `integration_8_8_end`; `behavior4_branch_start` and
`behavior4_branch_end` stayed patch-loaded no-freeze.
