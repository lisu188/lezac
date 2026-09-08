# Continuous Boss Defeat Recovery

## Scope

Two original DOSBox captures each contain two 180-update cases, starting at
shared clocks 100 and 101. The observed seven-actor boss, player, links,
object/word planes and RNG are restored only at each case boundary. The head
HP/lives are set to zero, and a zero-fuse small bomb is placed at head visual
`(x+16,y+8)`. Subsequent damage, conversion, movement, fuses, explosions,
flame/map changes and cleanup are original gameplay, without per-tick state
restoration. Inputs remain idle. Both runs end on level 7 with no live actors.

The near capture waits 207 natural idle updates before taking its initial
boss snapshot. Neither run forces a boss position. This is controlled fatal
damage evidence, not a naturally won full-health fight.

## Recovered Behavior

- `1000:5BCC` selects kind-31 segments whose byte `+0x25` equals head word
  `+0x12`. The GRAN reader assigns the group's first one-based actor slot to
  those owner fields. Conversion preserves motion/fractions/visible sprites,
  changes kind to 14 and behavior to 2, and disables animation mode `+0x1B`.
- Segment timers are `40 + Random(10)` in actor order; head timer is 60.
  Later segments run as newly converted timed actors in the same actor pass.
  The head finishes the already-entered brain, including gravity/reflection.
- `1000:5A75`, called with one-based selector `0x2F`, updates the visible
  descriptor to decoded PROVA sprite 46 and changes hotspot `+0x14` to
  signed -4. It does not start a 12-frame alternate-sprite effect. The head
  damage/HP subtraction precedes gravity/reflection and keeps byte wrap.
- Behavior 2 uses the existing shared timed-actor physics. Timer subtraction
  is `clock & 1`, with expiry at zero or `0xFF` (`1000:75A7..75C8`). The
  C++ boss timer stores that original byte, unlike normal corpse timers that
  encode remaining full-rate updates.
- Kind 14 expires through the normal medium-bomb explosion path, not a
  compatibility flash. The actor becomes the normal stationary fade and
  appends three moving particles. All original actor/visual ordering survives
  conversion and stable deletion. Flame records use the existing shared
  propagation, damage and chain-reaction engine.
- `1000:75D7..75EB` uses visual `x >> 3` and `y >> 3` as the explosion origin.
  The collision-scan `x+4` bias must not be reused here. Both ordinary moving
  bombs and converted boss pieces now use the unshifted origin.
- **Correction:** the argument 1000 at `1000:5C98` is a tile-trigger key,
  passed to `1000:5740`, not a score award. That helper searches the trigger
  table at `DS:77C0` and rewrites matching object-plane tiles. At conversion,
  cells 5709, 5710, 5849, 5850, 5989 and 5990 become zero, opening the gate.
  The port invokes its existing tile-trigger helper and does not add points.
- The final death sound was already correct: cursor `003D`, priority 12.
  The trigger helper also requests cursor `0027`, priority 6 before it.

## Capture And Registers

Executable SHA256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The MZ image begins at file offset `0x770`; subtract that from raw objdump
file addresses to obtain the main-CS anchors above.

Instrumentation sites are `1000:7EBB` (pre-link/actor pass), `1000:6813`
(normalized P1 input), and `1000:7A57` (completed playfield). Actual captured
CS/DS/SS are `01A2/0C44/18B3`; their runtime addresses are therefore
`01A2:7EBB`, `01A2:6813`, and `01A2:7A57`. ES is `0C44` at pre-pass and
`A000` at render; input ES is an observed heap segment. Saved SP/BP are
`3FE4/3FFE` at pre-pass/render and `3FA2/3FEE` at input. Register blocks are
retained in every record. Helper-relative CS/DS `01ED/0C8F` use a shifted
host-memory base and are not the actual captured CPU segments.

Observed tables: actor `DS:1BAE` (38-byte stride, live slots 1..count),
visual `DS:C21E` (8-byte stride), links `DS:79FA` (six 16-byte entries),
flames `DS:2093` (11-byte stride, live slots 1..count), masses `DS:78D5+slot`,
RNG `DS:1AFE`, and clock `DS:78C2`.

Reproduction, from the repository under WSL:

```sh
mkdir -p /tmp/lezac-boss-defeat-near-v1
cp LEZAC.EXE *.DAT *.SPR *.PAL *.SCH *.SON *.MST *.CAR *.ZBG *.DOC /tmp/lezac-boss-defeat-near-v1/
env PYTHONUNBUFFERED=1 python3 tools/capture_original_boss_defeat.py \
  --run-dir /tmp/lezac-boss-defeat-near-v1 \
  --out build-codex-tmp/boss-defeat-near-v1.txt --near-encounter \
  --approve-procmem --approve-runtime-instrumentation
```

The earlier offscreen run used `/tmp/lezac-boss-defeat-v1`, output
`build-codex-tmp/boss-defeat-v1.txt`, and the prototype
`build-codex-tmp/capture_boss_defeat_probe.py` without `--near-encounter`.
The promoted tool preserves its capture contract. Use fresh paths on rerun;
the tool refuses existing output. Both runs used temporary asset copies.

Immutable LF-normalized fixture SHA256 values:

- `tests/fixtures/boss_defeat_original_level7.txt`:
  `48d148036784c48b992cb2924d14d99b49ab8f477cd7e2f885773500c47ce8d4`
- `tests/fixtures/boss_defeat_near_original_level7.txt`:
  `0c4602d0744626c785c0c4cb34526a214bd914f2e844c2bc1e70247bcf5752c7`

## Validation

`--debug-boss-defeat-original FIXTURE [OUTPUT_DIRECTORY]` extends the existing
continuous replay and calls production `updateWithControls`. Each fixture
matches 1,361 live boss states, 1,865 fade/particle states, 1,456 flame states,
all 360 player/input/RNG/map checkpoints, and 30 views / 1,422,720 normalized
pixels. Each case reaches an empty actor and flame pool. Gate rewrites are
included in map comparison. Live visual slot identities are checked across
all deletions; post-conversion timers and animation bytes are compared.

`tools/check_boss_continuous_fixture.py --exe build/lezac_cpp --defeat`
(also with `--near`) independently checks 30 indexed SHA256 values, accepts
LF and CRLF, rejects two truncations and 108 mutations per fixture, and
verifies that no unsolicited frame files are written. CTest includes both
replays, both fixture guards and the capture-tool instruction/hash guard.

Final Linux build and all 497 CTests passed on 2026-09-08 in 111.36 seconds.
Windows Release compiled successfully. Its initial selected run passed
46/48 checks; two shell dry-run tests used the WSL Bash launcher against
Windows paths. Both passed after setting the local CMake cache's
`BASH_EXECUTABLE` to Git Bash. The shared explosion-origin fix also passed
the ordinary bomb, flame, corpse, reward and actor-order suites.

Visually inspected original and C++ near-case sample 39 (settled pieces) and
sample 99 (chained explosions). Both independently compare at AE=0 after
nearest-neighbor 3x scaling. No HUD or actual VGA DAC colors are compared;
views use the same BOMPAL/backdrop normalization as the prior boss replay.

## Still Open

The fixtures do not establish full-health natural victory, nonfatal boss
damage cycles, all flame-mass branches, boss combat with player death/reentry,
two-player combat or whole-game fidelity. The word plane is an initial
environmental seed, not a per-tick writeback oracle. Raw globals and reserved
actor/flame bytes are provenance unless explicitly mapped above.

The later [nonfatal-hit recovery](boss_impact_runtime_2026-09-08.md) adds
continuous small-bomb damage cases with a surviving head, fixing link Y
coordinates after the signed hotspot change. Its narrower scope and the
remaining combat questions are documented separately.

After defeat, no boss actor consumes links. The original keeps updating and
remapping unused visual-link bookkeeping; those post-defeat link bytes are
retained but not semantically replayed. Only the 24 active link states per
fixture before conversion are counted. This limit does not relax the
existing 7,200-state active-motion link checks. `whole_game_parity=0` remains.
