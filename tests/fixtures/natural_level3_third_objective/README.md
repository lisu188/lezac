# Ordinary Level 3 Third Objective Route

This native-only fixture adds 500 ordinary movement/jump frames and one Medium
bomb after the unchanged 4758-tick second-objective route. The complete route
is 5258 ticks. Its combined comparison checks 4231 whole 320x200 RGB frames,
8386 mapped boundaries and 270784000 pixels, including Level 1/2 results.

The third pickup occurs at tick 5092, native Level 3 sample 1315. The endpoint
is P1 `(383,192)`, three objectives, 36 destroyed structures, 46 health, one
reserve, score 21120 and inventory `[200,16,0,0,1]`. It does not complete Level 3.

Pinned files:

- `reference.jsonl.gz`: SHA256 `be3355def8eb01d72cf938f7ff750553242eb124ce17de4ee99175940eb106cc`.
- `route.txt`: SHA256 `569c5bcde405df0578d86c1f0e25d6a9a3d2fee787477e146875a9dfe5804ce0`.
- `guard-input.json`: SHA256 `52f81f7ab25ceceb2c9bbf417af65d8b0e5e5d71d6a5c40c1404d498890318c6`.

The reference contains only the 500-frame extension: 1000 presentation/post
boundaries. Earlier campaign and first/second-pickup fixtures remain separate
and unchanged. The fresh 1482-frame native Level 3 stream includes the earlier
982-frame prefix and this extension. Stream SHA256:
`a59a3f4598a82f213f06656093c384916fd47d027b0b92ec359d5280a9a311f9`.

`tools/natural_level3_third_objective.py pack --capture NATIVE --out OUT`
checks all twelve producer pins before creating output, file/asset hashes,
canonical Level 1 input, fresh mapped/RGB Level 2 and earlier Level 3 samples,
frozen result reels, BIOS Return acknowledgments, full map extents, phase/frame
sequences, RGB deltas and every native input-bank write. Expected values never
come from C++ output. The native-only typed guard endpoint tests projection
sensitivity; it is never injected into gameplay.

Guards reject 22 semantic/fixture changes, twelve producer changes before
output creation and 291 typed/map/palette mutations. Boundary reordering and
changed endpoint score are explicit cases. Excluded DAC entries 176..214
remain an explicit negative control.

Raw evidence is reconstructible from independently readback-verified notes
`refs/notes/qa-natural-level3-20261005-second-objective-regression`, anchored on
`1b5fd909b4b9750da90530420de1265ef0864167`. The archive's logical inventory
records byte aliases within that same archive. All 1539 logical native files
were restored and individually size/hash verified before packing.

See [runtime scope and evidence](../../../docs/recovery/natural_level3_third_objective_runtime_2026-10-05.md).
