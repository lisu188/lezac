# Level 4 Ordinary-Input Continuation Scout

The current closed original-only Level 4 regression ends at route tick 11740 with
three objectives, 244 destroyed physical damage cells and four Medium bombs.
Original Level 4 completion and Level 5 entry remain unverified.

This exploratory tool produces three candidate ordinary-input continuations
without changing the pinned input prefix, assets, actor state, RNG or original
comparison fixtures. It takes the current source route from
`tests/fixtures/natural_level4_support_column/route.txt`, authenticates its
hash and the closed evidence's C++ guard stimulus, and appends only later key
events. Candidate programs use the retained one-player Z/X movement keys, N
fire and the opposite movement key for retreat.

The default candidate moves right for 36 ticks, fires once, retreats left and
observes through tick 12240. Alternate `right_short_medium` and
`left_short_medium` sequences are available for later experiments.

## Commands

```sh
python3 -S -B tools/campaign_level4_continuation_scout.py self-test
python3 -S -B tools/campaign_level4_continuation_scout.py replay \
  --exe build/lezac_cpp --out /dev/shm/lezac-level4-continuation \
  --pattern right_long_medium
```

The output includes the generated route, silent replay evidence, a bounded JSON
summary and one final C++ PPM when present. For the default candidate,
the CI branch-specific Linux step runs the same program and uploads only the
summary, last frame and child exit status. It does not publish full captures.

The parser authenticates the unchanged C++ tick-11740 state against the pinned
guard stimulus **and the complete original-backed projected player, actor, and
terrain state**. It verifies the actual route, all input/time boundaries, each
ordered checkpoint, the full presentation/post-update count and the replay
footer. Selected captured RGB buffers are checked against their reported FNV
fingerprints. Twelve focused regression tests include corrupted routes, changed
player state, invalid checkpoint state, invalid phase transitions, and omitted
checkpoint/frame rejection. The summary reports additional destruction, minimum health, completion-gate
candidates and any **C++-only** Level 5 entry. The alternate-route follow-up
also retains bounded per-tick observations near bomb placement and when active
bomb count, ammunition, health, destruction, or flames change. These observations
include player positions, bounded bomb/flame/effect projections, and counts and
samples of word-plane changes relative to the authenticated starting checkpoint.
They do not publish complete guest RAM or entire gameplay traces. Their purpose is to
identify why a candidate destroys no eligible structure before selecting
further movement and placement inputs.

**No output of this scout establishes original behavior.** A positive candidate
must be reproduced against unchanged `LEZAC.EXE` with read-only,
atomic original snapshots, completion after the empty-collapse gate, results
acknowledgment and Level 5 handoff before it can advance campaign coverage.
No synthetic route is promoted to an original-evidence fixture. A candidate
can also produce zero additional destruction or lead to player death; both
outcomes are legitimate exploratory findings. The existing 3/7 campaign
coverage and broad completion/fidelity flags remain unchanged.
