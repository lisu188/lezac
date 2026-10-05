# Ordinary Level 3 Bomb And Objective Route

The compact reference is derived only from the silent original capture of
2026-10-05. It adds 650 presentation/post-update pairs after the unchanged
3788-tick `natural_campaign` prefix. The complete production route is 4438
ticks; the combined original-backed comparison checks 3411 full 320x200 RGB
frames and 6746 mapped boundaries, including the Level 1/2 result reels.

The first Level 3 objective is collected at tick 3988. The endpoint has one
objective, 36 destroyed structures, 62 health, one reserve and inventory
`[200,17,0,0,1]`. It does not finish Level 3 or establish whole-game fidelity.

Pinned files:

- `reference.jsonl.gz`: SHA256 `243af32b37aacc54d64d5853d1da3def16f30235b86f5ecbe04711862d3bd00b`.
- `route.txt`: SHA256 `ef1dbc608c94ff670b6aae4b0bb7922063be17876009ed6110264a0ced295728`.
- `guard-input.json`: SHA256 `62e56c2e8da59632001fdfa7c13033591855b67eaf81a61f19d061e37b8b91dd`.

`guard-input.json` is a typed reconstruction from the native endpoint. It is
used only to test comparison sensitivity and never seeds the game. The guard
rejects 18 semantic/fixture changes, 10 producer changes before output creation,
and 291 typed/map/palette mutations. The excluded DAC entries 176..214 remain
an explicit negative control.

Repacking uses `tools/natural_level3_objective.py pack --capture NATIVE --out OUT`.
The packer checks all captured-file hashes, source pins, unchanged assets,
the canonical Level 1 prefix, fresh Level 2 and handoff mapped states/pixels,
fresh BIOS acknowledgments, full map extents, frame/phase sequences and the
complete native input-bank journal. It accepts no C++ data as expected values.

Full raw evidence is retained in the independently verified remote notes
`refs/notes/qa-natural-campaign-20261005-level3-native`, anchored on
`3f12dbe6625e84a675016ad609ab60aa1ac7c6f1`. Archive SHA256:
`270187c8d1b80f8b9a3cae952226e891da5679d5fcfd8ceae8db110e22aa4925`.

See [runtime scope and evidence](../../../docs/recovery/natural_level3_objective_runtime_2026-10-05.md).
