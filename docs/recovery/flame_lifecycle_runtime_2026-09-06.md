# Live Flame Lifecycle Recovery

## Scope

Seeded, continuous original-game observations for small, medium, large and
super bombs on level 1, both grounded and airborne. Each case starts in a
fresh DOSBox child and runs 65 captured non-player actor passes. State is
seeded only at the case boundary, never between samples.

The two C++ replays verify 1,040 states, comprising 7,332 live flame-record
observations, both terrain planes, debris/collapse counts, target monster
position and HP, shared actor count, the global RNG, and player position,
fixed-point velocity/fractions, energy, life count, behavior, death countdown,
idle counter and all seven animation bytes. Every state is rendered and
inspected. This is not natural-route or pixel-parity evidence.

The low-HP set follows fatal conversion without reseeding: 400 corpse states,
65 reward states and 1,530 transient-effect states. Five cases produce a
reward and three fade without one. The high-HP set additionally verifies
1,283 transient-effect states, rather than only their aggregate count.

## Provenance

- Original executable SHA-256:
  `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
- Canonical fixture: `tests/fixtures/flame_lifecycle_original.txt`.
- Fixture SHA-256 at promotion:
  `5fd3dafa136bb691d44ad9040a8673171ea6976a719af0e4bd0ff334e9e025a1`.
- Raw capture: `build-codex-tmp/flame-lifecycle-player-v5.txt`, with eight
  separate case files and screenshots beside it. Promoted without editing.
- Runtime registers in all captured markers: CS `01a2`, DS/ES `0c44`,
  SS `18b3`, saved SP `3fe4`, BP `3ffe`.
- Hooks: Ghidra `1000:7EC5` and `1000:7EEA`, runtime `01a2:7EC5` and
  `01a2:7EEA`. These stop before and after the non-player actor pass.
- Player starts at visual `(240,168)`, lives 99; spawners are disabled.
  Bomb visual position is `(336,176)` or `(336,96)`. Target monster kind 1
  has raw HP 255, corresponding to 256 damage units in the port.
- Startup/input: the existing level seeder starts level 1 in a temporary
  asset copy, with startup/intro/level-start waits of 10/8/5 seconds. The
  probe waits for an odd global frame, seeds once, then supplies no route
  input. Instrumentation affects only the disposable DOSBox process.

Capture command, after copying the shipped assets to the temporary directory:

```sh
python3 tools/capture_original_monster_damage.py --flame-lifecycle \
  --run-dir /tmp/lezac-flame-player-v5 \
  --out build-codex-tmp/flame-lifecycle-player-v5.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The tool checks 23 instruction windows, the executable copy, child-memory
read/write lengths, hook registers and case completion. The orchestrator also
requires identical provenance headers and sprite descriptors across cases.

An earlier eight-case attempt in one child timed out before the final case.
It was not promoted. A fresh isolated final case succeeded; fresh children
for every case subsequently produced the complete v3 and v5 captures. The
timeout is a capture failure, not a recovered game rule.

### Fatal Follow-Up

- Canonical fixture: `tests/fixtures/flame_fatal_lifecycle_original.txt`.
- SHA-256: `3fad9801e84d5e0e311373a2b8bb3f5bb69e56d9b9c63d4bb34bae4a8bb8932f`.
- Raw capture: `build-codex-tmp/flame-fatal-all-weapons-v8.txt`, with eight
  per-case files and PNGs beside it. Promoted byte-for-byte.
- Same executable, hooks, register values, temporary-copy workflow and
  23 instruction guards as above. The only seed change is target raw HP 3,
  equivalent to four damage units in the C++ representation.
- The preceding isolated small-ground capture is
  `build-codex-tmp/flame-small-ground-fatal-v6.txt`. It has 65 samples,
  50 corpse states and 13 reward states, without intervening writes.

```sh
python3 tools/capture_original_monster_damage.py --flame-lifecycle \
  --flame-raw-hp 3 --run-dir /tmp/lezac-flame-fatal-v8 \
  --out build-codex-tmp/flame-fatal-all-weapons-v8.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The small-ground target becomes kind 0C/behavior 2 at sample 2, retains raw
HP byte 03, and starts raw countdown 25. At sample 52 it becomes kind 17,
the yellow bomb-box reward, with timer 100 and VY -200. The retained corpse
HP byte is not a live health value; the C++ semantic dead marker is HP zero.

Inspecting every transient exposed an inaccurate replay seed: airborne bomb
actors must run normal motion before expiry and preserve their explicit
hotspot 8. The resulting fade retains fraction Y 0x40, but has zero velocity.
The harness previously marked the bomb nonmoving and lost this fraction.
Gameplay constructors still derive the hotspot from their selected sprite.

## Recovered Rules

The low pool count is DS:2076, capacity 198. Eleven-byte records begin at
`DS:2093 + 11*slot` for slots 1..count; mass bytes are DS:78D5+slot. Fields
are cell word, two stale/unused bytes, signed VX/VY/fraction bytes, timer,
glyph 75 and variant. The replay deliberately excludes the uninitialized
two-byte field; all other record fields and parallel mass are compared.

Constructor `1000:3FA6`, dispatcher `414A`, integrator `3EDA`, remover `452A`
and mover `45FA` supply the implementation. Finite velocity tables preserve
the original float48 trigonometric truncation, including asymmetric values
79/109/125 rather than an ordinary rounded 80/110/126. Timers, variants and
masses are respectively 8/5/1, 9/5/1, 9/3/9 and 58/10/221. Super-bomb rays
start at four neighboring cells.

The signed-byte fraction integrator moves at most one cell per axis. The
mover visits slots in descending order, stamps glyph 75 in both propagation
and collision paths, transfers mass-weighted momentum to debris/collapse
records, decrements timer/variant bytes, and compacts retired slots. Newly
appended chain records wait until the following pass. Chain dispatch and
capacity handling are byte-derived but not exercised by these eight cases.
The separate [chain/capacity capture](flame_chain_capacity_runtime_2026-09-06.md)
now adds eight focused cases for unflagged chain tiles, full/partial pool
allocation, descending retirement and mass-array compaction.

Bomb expiry at `1000:75CB` dispatches flames and converts the same actor to
a stationary fade. It also appends 2/3/4/5 randomized particles for the four
weapons. Expiry does not immediately consume collectibles, award their
scores or apply weapon-sized damage. Monsters instead scan the pre-motion
2x2 footprint for terrain/flame damage. The small grounded bomb first
damages the target at sample 2, followed by damage totals 4, 6 and 2.

Player update `1000:6F90..7011` calls `56B6` in TL, TR, BR, BL order. Each
flame cell costs two energy units. Solid glyphs 1..4C cost two units only in
the top row. The last flame cell selects its highest matching pool slot
through `3A56`; signed ray velocities multiplied by eight overwrite the
player's velocity. Mass greater than one additionally costs mass/10 energy.
There is no invulnerability cooldown around this scan.

Death helper `1000:30A3` resets energy to 100, sets behavior 2 and countdown
60, and initializes animation 74..79 without clearing motion/fractions.
Behavior 2 (`7018`) applies gravity, floor friction and normal integration.
The state-2 countdown runs before the actor passes. The captured super-ground
player is first hit at sample 13 (energy 76), reaches death at sample 19
(countdown 59), and slides to x=238. Removing an old additional per-debris
damage approximation is necessary to match the intervening energy bytes.

The live order is non-player actors, player actors/damage drain, flames and
debris, collapse, then shake. Boss damage now reads the actual flame map;
its byte-derived scan doubles the whole damage count based on the last
matched ray mass, not a per-flash synthetic power value. The existing boss
diagnostic uses explicitly seeded flame cells; this is not a new original
boss capture.

## Verification And Limits

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-flame-lifecycle-original \
  tests/fixtures/flame_lifecycle_original.txt build-codex-tmp/flame-cpp-frames
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-flame-lifecycle-original \
  tests/fixtures/flame_fatal_lifecycle_original.txt build-codex-tmp/flame-fatal-cpp
ctest --test-dir build -R '^flame_.*lifecycle' --output-on-failure
```

All five flame tests pass: both continuous replays, capture guards, LF/CRLF,
missing completion and eight/ten field mutations for high/fatal HP. Added
mutations cover transient timers, corpse countdown and reward kind.
Optional frame output includes
PPMs and a CSV manifest of state, RNG and frame hashes. Replay without an
output directory must not write frames.

Original/C++ small-ground sample 4 and super-ground sample 36 were inspected
and shown to the user. DOSBox presents a previous rendered frame while the
hook is stopped; HUD and terrain presentation differences remain visible.
The player animation cursor is compared, but immediate death-descriptor
presentation, all rendered pixels and cached HUD energy bytes are not.

Fatal small-ground sample 64 and super-ground sample 20 were also inspected
and shown as labeled original/C++ pairs. The latter pair is
`build-codex-tmp/flame-fatal-all-weapons-v8_super_ground_super_ground_020.png`
and `build-codex-tmp/flame-fatal-super-ground-20-cpp.png`; the complete C++
frame set is `build-codex-tmp/flame-fatal-all-cpp-v8/`.

The reward, behavior-3 multihit, behavior-4 chase, spawner and super-bomb
diagnostics now advance live updates until flame contact. They do not
restore instant weapon-sized hits. Particle RNG draws precede the reward;
the level-1 reward route also retains terrain RNG draws and now produces a
yellow bomb box worth 3,000, not the old forced present. The isolated
super-bomb probe uses a one-pixel/tick walker so the moving corpse and reward
remain visible, and reaches fatal damage after 14 updates.

Impact-sprite direction cases are explicitly synthetic damage unit probes.
The old polling sprite-consumption observation is still validated in full,
but its synthetic instant-bomb replay was removed. It now invokes the
continuous fatal fixture for production damage, corpse, reward and effect
checks, explicitly without polling phase alignment. Collection is tested by
the live autoplayer, not claimed for the continuous original fixture.

Do not restore the refuted production behavior or change original expected
bytes to satisfy legacy diagnostics. The unused production-side
`monsterDamageForBomb` helper remains only for the separately marked
`monster_blast_damage` unit diagnostic. Natural routes,
chain reaction/capacity cases, broader mixed actor-pool ordering, two-player
flame interactions, and full death/reentry presentation remain follow-up
work. Passing these 1,040 states is not a whole-game completion percentage.

Initial full integration run: 437/446 tests passed in 48.68 seconds, including
the interactive Xvfb test and all three new flame tests. Nine failures remain:
monster reward frame capture/autoplayer, behavior-3 multihit, behavior-4 chase,
spawner cycle, impact sprites and its newline wrapper, live bomb kill, and
the old sprite-consumption evidence diagnostic. Full log:
`build-codex-tmp/flame-player-integration-second-full.log`. The earlier
16-failure run is preserved
as `build-codex-tmp/flame-player-integration-tests.log`.

The fatal-integration follow-up passed 447/448 in 25.71 seconds, resolving
all nine failures above. Its only failure was an uncertainty-inventory
marker missing the uppercase keyword required by the checker; the marker
has been corrected without removing the outstanding entry. Log:
`build-codex-tmp/flame-fatal-integration-full-tests.log`.

Final local validation: 448/448 tests passed in 24.88 seconds under Xvfb,
including the interactive UI check and all five flame tests. Full log:
`build-codex-tmp/flame-fatal-integration-full-passing.log`. `git diff --check`
also passes. The pre-existing `debugDebrisShatterPlayback` snprintf warning
is unchanged.
