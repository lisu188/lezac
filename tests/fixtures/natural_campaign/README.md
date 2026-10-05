# Natural Level 1/2 Completion And Level 3 Entry

This is a compact native-derived regression for one Italian, one-player route.
It promotes the retained 2026-10-01 V20 original observation to a self-contained
production replay. It is not a newly recorded original run or a complete game.

The 3,788-tick input starts at the menu, uses the unchanged pinned Level 1
prefix, completes Level 2, acknowledges its results and the next intro with
separate Return events, then enters twelve Level 3 gameplay frames. Only the
original observer's initial Level 1 seed and normalized control inputs are
controlled. The C++ replay uses normal SDL input and production updates;
there are no position, world, inventory, health, objective or level injections.
Both audio and video drivers are dummy during the C++ replay.

`reference.jsonl.gz` contains 5,446 mapped boundaries and SHA256 fingerprints
of 2,761 complete 320x200 RGB presentations. Complete tile and word planes are
hashed, not truncated. The mapped projection is the existing player, HUD,
inventory, score/reel, level, RNG and palette contract. Gameplay and handoff
palette comparisons cover 217 stored entries, excluding 176..214; displayed
pixels still include every rendered color. All actor fields, physical input,
wall-clock timing, later levels and whole-game fidelity remain unverified.

Level 2 first reaches its native empty-collapse completion gate at frame 2669,
C++ tick 3094: three objectives, 243 structures, 61 percent destruction.
P1 energy is 90 and one reserve remains after a natural route death. Level 3
entry preserves that energy/reserve count and spent ammunition; objectives reset.

Expected values come only from original streams. Packing checks the pinned
original executable/assets, seven capture manifests/observer sources, every
retained native file, canonical Level 1 prefix, exact input/phase alignment,
the native completion flags/collapse count, frozen result world state, result
RNG/award and separate BIOS Return acknowledgments. No C++ output is accepted
as expected-value input. Producer snapshots are retained under
`docs/recovery/evidence/natural_campaign_20261005`.

`guard-input.json` reconstructs typed C++ projection input from one native
boundary solely for sensitivity tests. It is never used to seed the game.
The guard rejects ten fixture/semantic mutations, seven altered producer
files and 291 typed field/map/palette mutations, with a positive baseline
and an excluded-DAC negative control.

```sh
python3 -S -B tools/natural_campaign.py guard
python3 -S -B tools/natural_campaign.py replay --exe build/lezac_cpp --out /dev/shm/lezac-campaign-test
```

Each replay gets a new UUID output directory and retains the complete trace,
frames, manifest and comparison. Existing or failed evidence is not deleted.
CTest registers `natural_campaign_original` and `natural_campaign_guard`.

SHA256 identities:

- Input: `07bd49c6456b2ce77139002e230480a947219ad5b7592bea3d81296070efc3dd`.
- Guard input: `db79b0a4cdf66dc4150a1fc598f2f6797d1f4a778e2f3bf6bad0a4f0b06e705f`.
- Native Level 2 gameplay: `64829a917bcbd36b297c0da158d9984852c220550e617fc27a61fa4e5f0462e9`.
- Native Level 3 handoff: `f47daa4962c1294c315ccfa66a8d99e074721068abb159a610862d4d4889e69e`.
- Reference: `c4066a05bc486fb559afa61feff391a7617f6b3ae59743efd85856b4e0b4d2fd`.
