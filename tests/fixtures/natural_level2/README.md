# Natural Level 2 Route

This bounded fixture follows the pinned ordinary Level 1 completion, results,
typing and Level 2 handoff. It adds 500 Level 2 frames, driven only by the
retained key-event route and the existing single initial RNG seed. It does
not complete Level 2 or collect an objective.

`reference.jsonl.gz` contains 1,000 native present/post boundaries, both full
map-plane SHA-256 values, the existing mapped player/HUD/palette/RNG state,
every field of each live 11-byte debris and 15-byte collapse record, and the
bounded active-monster projection. Each present boundary pins all 64,000 RGB
pixels by SHA-256. Inactive table tails are excluded using the native live
bounds. The original monster records remain in the retained raw archive;
this fixture compares identity/spawner link, position/hotspot, motion/fraction
words, AI words, animation and HP, not every actor field or descriptor.

- Reference SHA-256: `c8bc377adb3dc8942273566874b9b6cbacd5b75b7c076c142dacdee54c0b8bf3`
- Route SHA-256: `53b82b21f7357d0eb5a46d457e1de30687b7572e12328659e2295a3404220d1e`
- Reference size: 95,373 bytes.
- Native extension frames: 318..817; C++ replay ticks: 743..1242.
- Observations: 6,050 debris records, 4,151 collapse records, 1,339 monster states.
- Audio driver: `dummy` for the original, C++ port and children.

Run the portable regression from the repository asset directory:

```sh
python3 -S -B tools/natural_level2.py replay --exe /absolute/path/lezac_cpp --out /new/output/root
python3 -S -B tools/natural_level2.py guard
```

Replays use a new UUID-named directory without deleting earlier output.
The guard checks live-bound exclusion, signed decoding, all compared typed C++
table fields, malformed fixture rejection and immutable source evidence. Five
modified producer/configuration/provenance cases must fail before the packer
creates output. The packer pins both retained producer sources before assigning
its natural-input provenance.
See [runtime scope and provenance](../../../docs/recovery/natural_level2_runtime_2026-10-05.md).
