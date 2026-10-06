# Natural Level 3 Empty-Collapse Completion Gate

## Verified Scope

An ordinary-input replay starts at Level 1, completes Levels 1 and 2 and enters
Level 3. Its final 486 Level 3 presentations (ticks 8420 through 8905 inclusive)
match the original's complete 320x200 RGB frames with zero differing pixels.
The two presentation/post-update projections agree at all 972 boundaries.
No snapshots, player teleports or new gameplay-state injections are used.

The final two Medium bombs raise the destroyed-structure count from 132 to 167.
The shipped Level 3 requirements are seven objectives and 20 percent of 739
structures, rounded up to 148. Nine collected objectives already satisfy the
objective requirement. Destruction alone is insufficient while the collapse
queue remains nonempty.

The original's post-update tick 8904 has `DS:79C5=1`, `DS:79C6=1` and
`word DS:2080=1`. At tick 8905 the flags remain set and the queue becomes empty.
This is the first eligible post-update sample in the 485-frame new native
suffix, and the C++ port starts its outro on that same tick. The destruction
counter is `word DS:78C8`; `DS:78C6` is not that counter.

The endpoint retains nine objectives, 167 destroyed structures, 66 health, no
reserves, `[200,10,0,0,1]` ammunition/selection, score 43620, RNG 806698761 and
player position `(196,264)`.

## Provenance

The capture re-executes the ordinary Level 1/2 route and reproduces all 4644
earlier Level 3 presentations and 13932 native boundaries through tick 8420.
That is original-to-original prefix verification, not a newly promoted
full-prefix C++ comparison. The C++ replay executes the entire 8905-tick route
but retains and compares only its final segment.

Every new pre/presentation/post boundary retains a complete 65536-byte DOS data
segment: 1455 snapshots total. Their journal hashes, sequence numbers, input-bank
writes, player/actor/visual ranges, RNG and mapped state are validated when
packing the compact native-derived fixture. The fixture compares bounded
player lifecycle, shipped Level 3 live/corpse projections and live debris and
collapse records at 970 boundaries after the fork, in addition to mapped state
and RGB at all 972 boundaries. The two tick-8420 fork boundaries do not have
new raw DS snapshots or terrain-table comparisons. Marker projections are
checked but this suffix contains no matching score-marker observations.

The compact fixture is in `tests/fixtures/natural_level3_completion_gate`.
Compressed immutable capture producers, terminal receipt and retention proof
are in `docs/recovery/evidence/natural_level3_completion_gate_20261006`.
Raw evidence is independently retained under Git notes anchored at
`e4a7f90872c3b9ea3d089b4aa652e9b16b33d6b8`:

- `refs/notes/qa-natural-level3-20261005-double-medium-gate-original-20261006-raw`
  archive SHA256 `f635e9ab6fd42b739e791782ab5f41eb155af0508f7b9d9df56be47d016935e0`,
  109036235 bytes and 5224 members.
- `refs/notes/qa-natural-level3-20261005-double-medium-gate-original-20261006-closed-controls`
  archive SHA256 `b845c6131b80c136c54d9a242dd0074b1bc249cecfc18f508da0573a52482195`,
  309760 bytes and 39 members.

Both archives have independent remote readback, complete archive-byte and
per-member size/SHA256 verification. The original process is closed and its
temporary observer patches were restored. All capture/test audio uses dummy
SDL; no system speaker volume was changed.

## Regression

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  python3 -S -B tools/natural_level3_completion_gate.py replay \
  --exe build/lezac_cpp --out build/natural_level3_completion_gate_original_out
python3 -S -B tools/natural_level3_completion_gate.py guard
```

CTest registers `natural_level3_completion_gate_original` and
`natural_level3_completion_gate_guard`. The replay uses the production SDL
event loop, original intro wait and result reels. Its scoped scout format does
not weaken the existing full-trace campaign validators or turn the scout into
a whole-game fidelity claim. The guard rejects 28 semantic/fixture mutations,
22 immutable producer mutations and 291 typed/map/palette mutations. Every
production comparison also rejects nine mutated C++ endpoint states, including
the outro gate flag, RNG, ammunition, health, player position and terrain maps.

## Still Unverified

The original capture stops at `1000:8283` before executing the blocking results
sequence. Original Level 3 result reels, acknowledgment and Level 4 handoff have
not been compared. A separate C++-only route finishes those results, awards 2670
points (score 46290), and reaches playable Level 4 with 66 health and ammunition
`[200,10,0,0]`. Its selected weapon resets to Small during level setup; a failed
probe assertion expecting Medium was preserved as a diagnostic, not treated as
a gameplay regression or discarded.

Full actor/clock/sound byte equivalence, physical timing, later levels,
boss/ending and whole-game fidelity remain open. The original results/Level 4
handoff claim and all broad completion/fidelity flags remain false. Eligibility
at the Level 3 gate does not promote verified campaign completion from two to
three levels.
