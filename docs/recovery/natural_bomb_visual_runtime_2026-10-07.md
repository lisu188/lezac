# Natural Bomb Visual and Collision Fields

This bounded regression covers 354 live Medium-bomb observations from the
ordinary Level 4 route. It does not establish all-actor or whole-game parity.

## Original Evidence

The original observer read a complete DS snapshot while DOSBox was stopped,
then derived its actor and visual projections from that same snapshot. Across
the retained run, 4,378 such boundaries had zero internal raw/projection byte
differences; no bytes were normalized. The bomb comparison scans 2,878 rendered
and post-update boundaries, including boundaries with no live bomb.

The native-only fixture retains each observed 38-byte actor record and its
8-byte visual record, together with tick, phase and actor-pool slot. Its expected
values contain no C++-derived state.

- `LEZAC.EXE` SHA-256: `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`
- Original Level 4 stream SHA-256: `5705203340739e378bba40e6e7794fcbf1d8a2f85a9a2ab620eaacce96ba1ea0`
- Fixture SHA-256: `c369b38f74fa2352b461b7207af02277f89fddbeabc5f06d405fa9b56198ff67`
- Full original/C++ raw evidence: Git notes ref
  `refs/notes/qa-natural-level3-20261005-level4-native-cpp-comparison-20261006-raw`,
  archive SHA-256 `e175723a9674289a1e3d77a5c7336dbd3b1854f5ac00bf35e493b35746e2c501`.
- Native-only fixture, field audit and closed controls: Git notes ref
  `refs/notes/qa-natural-level3-20261005-level4-escape-and-bomb-visual-audit-20261007-raw`,
  archive SHA-256 `109c416f5913a4ff9ace29360927b5c0db8430a87b82bae582950a3a31f345cd`.

Both raw archives were independently fetched and read back, with every member's
size and SHA-256 verified before redundant presentation dumps were retired.

## Checked Fields

The existing ordinary C++ replay matched bomb type, pixel coordinates, velocity,
fractional motion and countdown. The added audit matched the resolved collision
hotspot and all four sprite-descriptor bytes: width, height and the little-endian
pixel-payload offset. Only Medium bombs occur in this natural segment.

`natural_bomb_visual_original` checks the recovered C++ `bombHeightOffset` and
`bombProfile` mappings against the native records and loaded sprite bank. Its
wrapper pins the compressed native fixture and tests LF/CRLF input plus changed
identity, hotspot, descriptor, provenance, sequence and completion records.
It is a field-mapping regression, not a new continuous gameplay replay.

Local GNU Release validation passed all 30 selected bomb, sprite, resource and
evidence-guard tests. The new regression checked both newline formats and
rejected 16 field/input corruptions. This is not a local full-suite result;
exact-head Linux/Windows CI and package checks remain separate delivery gates.

Owner attribution, constructor inputs and opaque actor bytes remain unchecked
by this comparison. Other natural bomb types, full actor/clock/sound parity,
Level 4 completion and the complete campaign remain open. This regression
closes no broad OPEN item and changes no global completion or fidelity flag.
