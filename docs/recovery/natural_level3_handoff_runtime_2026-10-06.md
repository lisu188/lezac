# Natural Level 3 Results And Level 4 Handoff

## Scope

The ordinary one-player route now has original-backed Level 3 completion,
results and Level 4 entry. The earlier Level 1/2 and Level 3 completion-gate
regressions remain independent. This regression executes the complete input
route from Level 1 through tick 9450, while retaining C++ gameplay checkpoints
from tick 8905. It does not claim comparison of every earlier C++ checkpoint.

`natural_level3_handoff_original` compares 90 complete 320x200 RGB frames and
120 mapped boundaries: the gate presentation/update, 58 Level 3 result-loop
frames, acknowledgement, Level 4 intro, and 29 playable Level 4 frames. The
results also check the one-draw-per-loop RNG cadence. The retained 148 full
64-KiB native DS snapshots support 117 bounded terrain projections, but do not
establish complete actor, clock or sound byte parity.

The campaign milestone is completion coverage for three of seven levels on
this composed ordinary-input route, approximately 43 percent. This is not a
weighted percentage of all reverse engineering. Level 4 entry is not Level 4
completion. Later levels, the final boss/ending, natural two-player campaigns,
wall-clock timing and full-state fidelity remain unverified. All broad
completion/fidelity flags and the four high-level OPEN items remain unchanged.

## Original Observation

The observer repeats all 5129 ordinary Level 3 samples and 15387 mapped
boundaries against the previously retained native gate run. The gameplay
prefix, input-bank journal, shipped executable and assets are unchanged. At
the empty-collapse gate, both native completion flags are set, nine objectives
are collected, 167 structures are destroyed, and no collapse entries remain.

It then observes the native results routine at its resident stage-5 boundary,
followed by stage-7 acknowledgement and stage-6 Level 4 intro. Each Return is
queued into an independently verified empty BIOS keyboard queue. No player,
map, actor, score or ammunition state is injected at the handoff.

The results award 2670 points, taking the score from 43620 to 46290. The route
retains 66 health, zero reserve lives and ammunition `[200,10,0,0]`. The Level 4
setup resets the selected weapon to Small; the earlier C++ scout's failed
expectation that it stayed Medium is preserved as a producer failure, not
silently rewritten. At tick 9450, the player is at `[248,360]`, with no Level 4
objectives or structures credited and RNG state `1561739296`.

All original and C++ launches use `SDL_AUDIODRIVER=dummy`. The original uses
its private Xvfb display; the C++ regression uses dummy SDL video.

## Provenance

The fixture is projected only from original-game state, DAC and RGB captures.
It is not reconstructed from C++ trace values. The producer/evidence guard
pins twelve control artifacts and eleven capture artifacts, including frozen
observer sources, the actual terminal receipts, raw journal and independently
read-back retention proofs. Both original capture and its owned keeper are
closed; native code patches were restored before terminal success.

Raw native evidence is retained under
`refs/notes/qa-natural-level3-20261005-level3-results-handoff-original-20261006-raw`.
The archive has 5316 members, 99930636 bytes and SHA-256
`f158d6356c335b1837f2efce168c687f304df45df7d79b527f4a9efa7f97054d`.
Actual closed controls are retained separately under
`refs/notes/qa-natural-level3-20261005-level3-results-handoff-original-20261006-closed-controls`,
with archive SHA-256
`857ec5e55f314f15f2c0838b47634b8e8d76a8abba71acf29258a4335b296d64`.
Both notes collections are anchored to
`e4a7f90872c3b9ea3d089b4aa652e9b16b33d6b8` and were checked by fresh remote
readback, all member sizes/hashes and exact notes-tree anchors.

The separate snapshot-coherence audit is also retained and byte-pinned. It
compares all 148 projected native snapshots with their paired raw DS data,
including all 90 bytes of `DS:79A0..79F9`, both player records and visuals.
Eleven differing byte observations occur during results: one at `DS:79A1`
and ten at `DS:79C4`. Player records and visuals have no differences. No byte
is normalized. These addresses are listed in the recovered sound-tick model,
but that mapping does not establish synchronized runtime behavior or justify
discarding the mismatch. An atomic native snapshot and timing-aware sound
comparison remain follow-up requirements for full raw-state fidelity.

The fixture reference SHA-256 is
`d97f4783a5af10afc521ec1c2c09cfcd22784a116879869e87645f032f86a05d`.
The ordinary route SHA-256 is
`f283afd6e746f43f972dc4721139dc18e1526dd801b99168b75704737771e09f`.

## Regression

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  python3 -S -B tools/natural_level3_handoff.py replay \
  --exe build/lezac_cpp --out /dev/shm/lezac-level3-handoff-check
python3 -S -B tools/natural_level3_handoff.py guard
ctest --test-dir build -R '^natural_level3_handoff_' --output-on-failure
```

The replay rejects altered score, RNG, health/reserves, ammunition, selected
weapon, position, maps and acknowledgement/intro/playability flags at four
critical C++ boundaries. The evidence guard rejects altered fixture claims,
sample ordering, producer bytes and truncated/corrupted reference bytes;
the existing mapped-state guard also covers 291 typed field mutations.
There are 24 fixture/claim mutations, 25 producer/audit mutations and 43
additional C++ boundary mutations. The pinned negative coherence finding
must remain present while the corresponding full-state claim is false.

Level-specific monster checks use explicitly supplied shipped profile sets.
The shared projection helper keeps its original Level 3 defaults, preserving
the earlier gate regression's behavior and scope.
