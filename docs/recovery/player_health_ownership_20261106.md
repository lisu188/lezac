# Player Health Ownership

The App now writes the reserved player-2 health byte at its gameplay owners:
new-game initialization, health bonuses, terrain damage, queued damage, death
and reentry. Level setup deliberately preserves that byte; it is not refilled
on ordinary level advance or restart. No draw/capture-time synchronization is
used. Player 1 still has typed health only: its separate raw actor record is
not part of `ActorSlots` yet.

The Hot Dog bonus also corrects an arithmetic difference. Original `6E64`
adds 33 to a BYTE before comparing with 100. Thus a seeded value of 223 wraps
to zero, rather than the previous App's integer-add result capped to 100.
The physical write keeps both intermediate writes when the wrapped result
exceeds 100, before the bonus score increment. Queued health subtraction
precedes the damage-sound request and death dispatch, as in the original.

## Original Evidence

REA 6.7.0 with Ghidra 12.1.4 on WSL verified complete instruction windows
against the immutable 52,384-byte original MZ, SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The independent MZ/loaded-image check compares every byte. None of these
windows contains a relocation. The session closed with the target unchanged.

| Window (End Exclusive) | Bytes | SHA-256 |
| --- | ---: | --- |
| `1000:2F30..2F3A` | 10 | `601a36455911b77aec29fc6befd628bcc1983def7699adf577827620d6a9edfd` |
| `1000:3131..3139` | 8 | `6baeecbadb2b36ee3050182b1ac8b1fb5b71571eeccc5aed7d6c29586acb10c8` |
| `1000:6E52..6E7E` | 44 | `05e3dc0407cb513b3f8133ab7cfadb9e5904cb8354bddae4de1e02588fa76392` |
| `1000:6FFD..7015` | 24 | `1d3c3624ccbe1fc2b72a33aaf765b4ccdbaaf7bde47146bfe881b29005f7a5de` |
| `1000:7F5C..7F79` | 29 | `fc277cd7544376166771d20e34e82bfb7a867b3e6d5d285ea21f3836cb832160` |
| `1000:7E94..7EB1` | 29 | `c853d6c0dd20507703c0f22d40d1ff2450177bd0162e6febb3ca68beca71d93b` |

Independent execution of unchanged original instructions covers 7,188 seeded
fragment cases: 4 new-game, 512 First Aid, 512 Hot Dog, 2,048 terrain,
4,096 queued-damage, 8 death and 8 reentry cases. These include every health
byte for both players, damage wrap, behavior-2 subtraction skip and reentry's
control-latch-before-health ordering. Observed and unobserved full 1 MiB memory
and registers agree; the ordered write log reconstructs the complete output.
No interrupts or hardware calls were injected. This is not execution of the
entire damage/death/HUD frame. Selected complete memory pairs are backed up
privately, not included in this change.

## Regression Evidence

Two actual-App counterexamples are retained before the fix: missing reserved
health after new-game initialization, and Hot Dog's integer-add result. The
fixed `--debug-hotdog-byte-health` checks all 256 inputs for both players,
including 66 overflowing cases. Those high-byte states are explicit fixtures,
not a claim that this route naturally reaches them.

`--debug-player-health-ownership` disables the legacy adapter and checks 5,141
observations, 330 pre-death boundaries, 1,334 ordered bonus writes and 1,536
damage-before-sound boundaries. It distinguishes new-game refill, level carry,
health/non-health bonuses, terrain and queued subtraction, dying-player skip
and reentry gates. Slot tests compare all storage after all 256 health-byte
writes and verify preservation through level reset and nonplayer retirement.

Read-only diagnostic observers check intermediate writes and score/sound
ordering. A first sound-order mutation exposed a disabled request counter in
the diagnostic; the final regression explicitly enables it and checks exact
damage/death request totals. Separately compiled App mutations now reject
collapsed bonus writes, score-before-health and sound-before-health. An
unchanged build with the same mutation compiler settings is the positive
control. Production observers are empty, and all runs use dummy audio.

Full native GCC C++23 and MSVC builds pass. Focused Linux validation includes
42 CTests, plus an overlapping 26-test player/render selection with fixture
dependencies and nine renderer mutations. Strict MSVC ownership units and
the original 1,008-operation marker comparison pass too. These focused results
do not stand in for an uncompleted hosted full suite.

## Bounded Combat Comparison

The adapter-free replay runs the unchanged ordinary-startup 18,700-tick route
with no later gameplay-state injections. In the retained level-4 combat window
18500..18700, all 201 complete RGB frames and 402 paired gameplay boundaries
match the original on native Linux and Windows.

All 31 captured actor records now match, including reserved player 2 and all
inactive tails: 473,556 bytes per platform. All 33 visual rows still match:
106,128 bytes per platform, including guard row 32. An independent checker
compares the complete pools directly against SHA-backed original DS snapshots
and rejects all 1,442 one-byte payload corruptions per platform. No field masks
or per-frame corrections are used. The pixels already matched before this
storage repair; this is not a claim of a new visual improvement.

## Remaining Limits

At this checkpoint, captured link row 0 and the shared result WORD still
differed and remained unmasked. The subsequent shared-result repair is
documented in `player_terrain_scratch_20261106.md`; link row 0 remains open.
Player 1's separate raw actor record is excluded from this storage
format. The inactive-player-2 combat window does not prove complete active
two-player record motion/animation ownership. Full frame-pass stability,
whole-campaign/level-7 boss completion, wall-clock and physical-input timing,
and owner acceptance remain open. Broad fidelity flags remain false.
