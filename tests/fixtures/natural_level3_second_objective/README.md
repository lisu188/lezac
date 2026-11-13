# Ordinary Level 3 Second Objective Route

This native-only fixture extends the unchanged 4438-tick first-objective route
by 320 ordinary movement/jump frames, without another bomb. The complete route
is 4758 ticks. Its combined comparison checks 3731 whole 320x200 RGB frames,
7386 mapped boundaries and 238784000 pixels, including the Level 1/2 results.

The second pickup occurs at tick 4674, native Level 3 sample 897. The endpoint
is P1 `(229,256)`, two objectives, 36 destroyed structures, 62 health, one
reserve, score 19570 and inventory `[200,17,0,0,1]`. It does not complete Level 3.

Pinned files:

- `reference.jsonl.gz`: SHA256 `59e2518414e6a5e22cfbd5c5e11dc107cace05cbe225757ed7ddee7071fe8f81`.
- `route.txt`: SHA256 `e08ebee46583df5b40b48b0000831546ae2237c0a148a92b832d8b29f3819f33`.
- `guard-input.json`: SHA256 `3441ed6b7c616702c52d21a4f1c7b74e10e765136a383c34452ed41d82c62358`.

The reference contains only the 320-frame extension: 640 presentation/post
boundaries. Earlier campaign and first-pickup fixtures stay separate and
unchanged. The 982-frame native Level 3 stream includes the 12-frame entry,
650-frame first pickup and this 320-frame extension. Stream SHA256:
`54dad8dd40aaf54913568ea849c722faf9ba59d796f396603dea113cffd1c048`.

`tools/natural_level3_second_objective.py pack --capture NATIVE --out OUT`
checks all fourteen producer pins before output creation, file/asset hashes,
the canonical Level 1 prefix, fresh mapped/RGB Level 2 and earlier Level 3
observations, frozen result reels, BIOS Return acknowledgments, full map
extents, frame/phase sequences, RGB deltas and the complete native input-bank
journal. Expected values are never derived from C++ output. The guard input is
a typed native endpoint reconstruction used only for comparison sensitivity;
it is never injected into the game.

The guard rejects 20 semantic/fixture changes, fourteen producer changes before
output creation and 291 typed/map/palette mutations. The excluded DAC entries
176..214 remain an explicit negative control.

Raw evidence is reconstructible from independently readback-verified notes
`refs/notes/qa-natural-level3-20261005-next-pickup` and
`refs/notes/qa-natural-level3-20261005-continuation`, both anchored on
`9f6367ae72a061393d2312c90bc0766af0093fdb`. The latter supplies byte aliases
referenced by the former's inventory. All 1041 logical native capture files
were restored and individually size/hash verified before repacking.

See [runtime scope and evidence](../../../docs/recovery/natural_level3_second_objective_runtime_2026-10-05.md).
