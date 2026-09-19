# Shared Death Lifecycle Recovery

## Scope

This follows the original-only [PR #229 observation](player_reentry_wait_runtime_2026-09-13.md).
Three original level-7 traces now run through the production C++ update path,
with scene restoration only at the case boundary, not on each update. They
cover 980 consecutive states, 60 normalized 312x152 playfields and 2,845,440
pixels with no differences. Two separate 320x200 introduction images match
as well. These are controlled largest-bomb encounters, not natural campaign
play or full-health boss victories. Whole-game fidelity remains unproven.

| Original Fixture | Updates | Views | Observed Transition |
| --- | ---: | ---: | --- |
| `boss_reentry_wait_original_level7.txt` | 420 | 22 | Death 15, waiting 75, restart 304; reserve 99 -> 98 |
| `boss_zero_reserve_original_level7.txt` | 420 | 22 | Death 18, waiting 78, restart 307; reserve 1 -> 0, active count stays 1 |
| `boss_fire_reentry_original_level7.txt` | 140 | 16 | Fire latch written after prepass 100; active again at 101, no restart |

## Recovered Production Rules

- Actor death countdown starts at 60 and decrements as a 16-bit word. It
  wraps while waiting; the bounded death-animation phase is separate.
- Expiry decrements the reserve byte. Zero is valid; FF is out. The C++
  representation uses -1 for FF, including rendering and outro eligibility.
- After the non-player actor pass, either global player state 1 clears the
  shared counter. Otherwise it increments; 230 promotes waiting states and
  enters level initialization. This is not a per-player timeout.
- The level introduction blocks for a key. Escape acknowledges it, as does
  Return. Actor reinitialization happens after acknowledgement, retaining
  the shared clock, raw countdown and counter until the next normal update.
- The introduction consumes eight RNG steps; subsequent background generation
  consumes 390. The first captured restart retains actor countdown FF1B.
- Fire-key reentry follows the death prepass, preserves motion, fractions,
  animation and the raw countdown, restores energy to 100 and adds no
  cooldown. The input fixture retains FFE8 throughout resumed active play.
- Main `7E9D`/`7EA2` (file `860D`/`8612`) clears both fire latches after a
  successful return, before processing P2. Deterministic controls use those
  same latches. Native SDL tests cover an early key release and simultaneous
  P1/P2 presses; these tests are not a two-player original runtime capture.
- The GRAN loader copies link outputs at +11/+13 before their first update.
  Animation-set zero retains the raw cursor bytes. Nonzero sets initialize
  the cursor and counter separately from the visible descriptor.

## Compressed Map Tail

The original map reader performs both compressed-plane reads into DS:C498,
the background buffer. File `15A4`/`1600` (main `0E34`/`0E90`) overwrites the
prefix only. Decoder `082D:0000`, file `8A40..8B4E`, stops by requested output
length, not encoded input length; its inclusive writes retain overlap.

Level 7 starts at file offset 36128, with compressed lengths 2421 and 2451.
Its tile payload defines 7271 of the requested 7280 cells. During the captured
restart, the last nine cells become B1 from retained background bytes beyond
the overwritten prefix. Production initialization now decodes through that
retained buffer, then rebuilds the backdrop after the intro. No fixture tail
is inserted at restart. All 7280 map cells match on every replayed update.
This does not establish all-level initial-load memory fidelity.
Binary-loaded levels retain their compressed planes in memory. JSON-loaded
levels keep their already-decoded maps; `ui_controls_json_dummy` exercises
start, restart, transitions and reentry from the JSON-only `src` directory.

## Provenance And Reproduction

Original executable SHA256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Actual CS/DS/SS: `01A2/0C44/18B3`; image base: file `0770`.
The eight lifecycle hooks, registers, relocation-aware keyboard call, arena
guards and temporary-copy method are documented in the preceding observation.
All captures use private Xvfb and `SDL_AUDIODRIVER=dummy`, including children.

The normal trace comes from the checked-in `--reentry-wait` mode. The new
zero-reserve and fire traces were recorded with ignored prototypes
`boss-zero-reserve-v1` and `boss-reentry-key-v1`; their controls are now exposed
as mutually exclusive `--zero-reserve` and `--fire-reentry` modes in
`tools/capture_original_boss_defeat.py`. Capture self-checks validate their
50 guarded instruction windows without launching the original. A fresh live
`--fire-reentry` capture also completed using `/tmp/lezac-shared-fire-reentry-v2`
and output `build-codex-tmp/boss-fire-reentry-promoted-cli-v2.txt`, with the same
two approval flags, dummy audio and a private Xvfb display. Its SHA256 is
`ee5bd792500f3b2edacc46e6a94b0c28c29b0a80e0ed0ffa6df05643637f8722`.
It has 27 waiting updates (rather than the pinned fixture's 24), with raw
countdown FFE5 after reentry. Replay assertions derive this count from the
observed continuous lifecycle, not a hard-coded startup timing. A live rerun
of the promoted zero-reserve CLI is still separate from its prototype evidence.

```sh
env SDL_AUDIODRIVER=dummy python3 tools/capture_original_boss_defeat.py \
  --zero-reserve --self-check
env SDL_AUDIODRIVER=dummy python3 tools/capture_original_boss_defeat.py \
  --fire-reentry --self-check
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-boss-reentry-original tests/fixtures/boss_reentry_wait_original_level7.txt
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-boss-zero-reserve-original tests/fixtures/boss_zero_reserve_original_level7.txt
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-boss-fire-reentry-original tests/fixtures/boss_fire_reentry_original_level7.txt
env SDL_AUDIODRIVER=dummy python3 tools/check_boss_reentry_fixture.py --exe ./build/lezac_cpp
```

LF-normalized fixture SHA256 values, in table order:

```text
e26aa4f34969721fecc384ba3cd9932d506789a33465845418635e4c0f876ce8
defd26902afec04e0fa1c407b780bd3326d0d9f6b3e57e370861e83d0794febd
9aca04234b9f4e7562825f4257f35ac7d080b91ffb6600606598ac0a9470c7fb
```

The fixture guard pins original trace hashes, indexed playfield hashes, two
intro PNGs and two independently matched C++ intro PPMs. It exercises both
LF and CRLF and rejects 130 lifecycle/input/actor corruptions or incomplete
traces. The original-only evidence validator remains separate and truthfully
reports `production_replay=0`; production replay is proved by the new tests.
The replay validates the active player's state, all seven boss records,
six links, effects/flames, map, RNG and sampled pixels. Inactive P2 bytes and
saved registers are provenance, not a simulation of the original CPU.

Visual inspection includes paired boss sample 20, paired fire-reentry sample
101, and the complete restart introductions. ImageMagick AE comparisons
confirmed the paired views and introductions independently of replay totals.
Playfield views use normalized palette colors, not full live VGA/HUD output.

## Validation

Both local toolchains build successfully. Full regression runs during this
batch passed 514/514 Windows tests (666.89 seconds) and 515/515 Linux tests
(325.26 seconds). The latter includes the repaired windowed key sequence,
which explicitly acknowledges each level introduction. An earlier Windows
run interrupted by a full disk and the earlier missing-acknowledgement Linux
failure are not counted as passing results.

After review, 102/102 Windows checks passed (380.52 seconds), including the
compressed-plane storage change. The final Linux selection passed 77/77
(102.16 seconds), including the new JSON-only controls case and the generalized
fire-reentry end assertion. The fresh original CLI capture independently
replayed 140 states, 287 effect states and 16 normalized views with no
differences on both toolchains. The final Windows selection then passed 6/6
(133.46 seconds), including JSON controls and all 130 fixture corruptions.
New CTest totals are 515 Windows and 516 Linux; these counts are
regression coverage, not an overall game-completion percentage.

## Remaining Work

The latched DS:79CA gate, per-frame waiting placement scan and inventory
minimums still need production recovery and original probes. The old
standalone effect-placement diagnostic has incorrect predicates and is not
an oracle. Two-player runtime reentry/out combinations, holding fire before
death, all-out progression, long raw-word rollover, natural full-health boss
victory, unrestricted campaign progression and full VGA/HUD parity remain
open. Passing this batch does not supply a defensible whole-game percentage.

Static follow-up anchors rechecked in the original: file `3831..3861` counts
remaining objective tiles, adds DS:2088, compares DS:2086 and writes the shared
DS:79CA gate at death. File `849A..84E3` applies inventory minima 100/10/2 at
countdown expiry. File `8573..85E0` moves waiting visual Y up one when the
left tile is in 1..76, or the right tile is in 1..76 and Y > 24. These precise
conditions differ from the old standalone effect-placement diagnostic and
need original boundary probes before broader lifecycle claims.
