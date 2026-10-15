# Byte-addressed damage lane recovery

The C++ helpers in `src/gameplay/damage_lane_bytes.hpp` recover the shared DS
operations in original routines `1000:3A7E`, `3B18`, `3BB2`, and `3D46`.
`DamageLaneMemory` now integrates these operations with App's live typed debris,
collapse, and flame queues, shared sound cursor, seeder result, and caller-axis
bytes. `blendDebrisImpactLane` uses this adapter for direct-fragment impacts;
`blendCollapseContacts` preserves the collapse caller's separate stack-value
contract. Unmapped bytes persist between calls so modeled low-data writes can
affect subsequent lookups. This is a production repair of the modeled aliases,
not a complete DOS memory model or a whole-game fidelity claim.

Lookup searches newest-first. A flagged miss preserves both the shared cursor
at `DS:2074` and the signed neighbor phase byte at `DS:661E`. Unflagged lookup
clears only the phase. Impact handling adds the fragment tag bias with 16-bit
wrap, stages writeback tags, averages signed phases with unsigned byte weights,
then writes each staged address and the caller byte. Admission failure returns
without caller writeback. Successful admission contributes weight but not the
retained neighbor phase. Seeding is supplied by the memory owner.

A missing `F001` fragment becomes tag `3E21`, not an invalid C++ queue index.
Forward/reverse writeback wraps to `DS:0A06` / `DS:0A07`. The original CPU capture
observes these writes without patching instructions, stubbing calls, or masking
output. Both the initial and final entire 64 KiB DS images are retained per case.
The observed and observer-free runs agree on all 1 MiB RAM bytes and 14 registers.

## Evidence

The pinned compressed fixture contains 176 cases: 128 lookups and 48 impacts.
It includes empty/full pools, oldest/newest and duplicate identities, missing
collapse and fragment identities, positive/negative stale phases, unsigned
weights, repeated contacts and the 30-contact boundary. All impacts use flagged
contacts; the fixture does not exercise the original seeder. Six synthetic C++
unit branches cover the callback contract separately and are not original-backed
seeder evidence.

`check_damage_lane_bytes.py` passes only metadata and incoming DS bytes to the
compiled helper executable. Expected images stay in the checker, never in the
native process. Every output DS byte is compared without normalization:
11,534,336 bytes per host. The diagnostic never runs App, SDL, or a game loop.
The live typed-memory probe is checked against the same original DS images;
this helper evidence remains separate from execution of the production App.

Fresh Linux package evidence at integration head
`aaf38ea6a354fdee3021541d4834675ab2111516` separately exercises the actual App.
All 96 direct-fragment cases and 2,565,216 state bytes match the original, closing
the reproduced old-head PR362 failure of 150 bytes beginning with cursor `AB12`
instead of `4EE8`. All 112 history cases and 2,993,088 state bytes also match,
including nonzero prior phase and low-data history. Both comparisons use no
masks, independently poison supplied expected states, and reject four malformed
headers. The inherited App comparisons pass at that same head. These results
do not substitute for exact-head full Linux/Windows CI and external review, or
for fresh package validation after a follow-up push.

Reproduce the original fixture with the pinned Unicorn 2.1.4 runtime:

```sh
env SDL_AUDIODRIVER=dummy PYTHONDONTWRITEBYTECODE=1 \
  python3 tools/capture_original_damage_lane_bytes.py --root . \
  --out /tmp/lezac-lane-bytes-original \
  --unicorn-path /path/to/pinned/unicorn
```

Run the compiled recovery checks:

```sh
cmake --build build --target lezac_damage_lane_bytes_test lezac_damage_lane_memory_test
ctest --test-dir build --output-on-failure -R '^damage_lane_(bytes_|memory_)'
ctest --test-dir build --output-on-failure -R '^(debris_contact_pools_original|damage_lane_history_original)$'
```

## Remaining Validation

The modeled App integration is complete, but each delivery head still requires
full Linux/Windows CI, actual-App package comparisons, and a completed external
review. Historical failing streams remain retained evidence, not current-head
acceptance. Pure diagnostic lookups remain distinct from original runtime
mutations. Known queue/global aliases are live references; the persistent
unmapped byte buffer does not establish coherence with every DOS actor, asset,
map, or stack address outside those owners.

Natural routes, full flame-update equivalence, rendered pixels, sound-runtime
parity, full DOS memory coverage, and whole-game completeness are not established
by these fixtures. The historical raw-prefix guard remains failed.
