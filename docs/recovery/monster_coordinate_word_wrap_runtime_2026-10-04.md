# Monster Signed-Coordinate Writeback

## Original Observation

The previous writeback recovery removed artificial level-bound clamps. A
separate retained 48-case probe then found 15 differences between the original
and the actual shared C++ fixed-point integrator near the positive word boundary.
That was helper-only evidence, not a production `updateMonsters()` comparison.

This recovery captures two independent complete 768-case original runs. Six
position profiles cover X-only, Y-only and simultaneous positive/negative word
boundaries: `(32760,24)`, `(24,32760)`, `(32760,32760)`, `(-32760,24)`,
`(24,-32760)` and `(-32760,-32760)`. Each profile covers kinds 1..8 and all
16 combinations of velocities `-32768`, `-256`, `0`, `32767` on both axes.
All actors use explicit shared behavior-4 seeds, hotspot 0, descriptor/cursor
40..42, fractions 165/90, HP 11, AI 14/271/75, and clock 421, with zeroed map
and word planes. The clock disables steering. These are not shipped constructors.

The original executable is SHA256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The observer verifies full instruction windows and relocation sites, reaches
one unseeded gameplay tick through physical input, and observes the selected
actor through entry `1000:7062` to exit `1000:777F`. Complete stack locals,
38-byte actor records and 8-byte visual entries are retained, including generic
damage and actual final writeback. The selected pointer and stack remain stable.
All captured pre-motion edges are zero, HP stays 11, RNG stays `0x12345678`,
and the animation counter advances to 1. Hooks and scratch are restored and
owned children close. Every run uses dummy audio and private original assets.

Both native projections reproduce the identical 24,640-byte fixture. It has
768 32-byte records after a 64-byte header, sharing the existing writeback
record format. Header magic is `LZWWv1`, with count, stride, entry/exit, original
executable SHA and instruction-window digest. Fixture SHA256 is
`585361d717dcb81ade13503fce6fe043edd1af4c3e3bf2b8a72d02dce9fa4618`;
FNV1a64 is `3ee7b0987203d3cc`.

## Failure and Correction

Diagnostic commit `9bca0ba20d52019ed0ab9a70ade4d21ca25b2aa6` adds the pinned
fixture and runs the real `updateMonsters()` once for every seed. It fails at
exactly the 240 native wrapping cases: 120 positive and 120 negative. The other
528 cases match positions, velocities, fractions, RNG, HP and animation.
The negative executable SHA256 is
`d2fb19017865abb58a96d6f82a2b7908cd33cefb7d5b00d601a85dca36b11760`.
The previous 256-case full-writeback diagnostic still passes at this commit.

The common native ADCs update word coordinate locals; final visual coordinates
are also word stores. The generic core integrator correctly exposes a 32-bit
position API, but the recovered monster path did not narrow its result.
Correction commit `081257924404aba1f4071f34bd7ef6af73d997c2` narrows both
coordinates to signed words immediately after common integration, before the
existing damage/writeback handling. Only the recovered-resolution branch
changes. Boss-motion integration, players, timed/corpse paths, terrain scans,
steering, gravity, damage, fractions and RNG are unchanged.

The corrected production replay matches all 768 cases. A core contract test
separately asserts that positive/negative boundary updates retain 32-bit
positions `32888` and `-32888`; the generic API was not narrowed. The tested
corrected executable SHA256 is
`31283646024c893c138b950f37c2e09c68535aa5a2ffb65c081917dfa1931b39`.

The shared observer now packs explicitly signed visual-coordinate seeds.
Existing positive seeds retain identical bytes. The full raw-writeback checker
accepts an explicit observer/header so both fixture families reuse the same
strict stack/actor/visual validation; the original 256-case default is unchanged.
Both older 176-case and 256-case retained archives still validate.

## Checks and Retention

Six new CTests cover production replay, pinned fixture/original windows, every
single-byte fixture mutation, 18 malformed production inputs, archive integrity
and capture self-check. The native workflow recaptures all 768 cases separately.
The local focused selection includes all 135 gates from the preceding monster
batch, these six new gates, and the generic core contract: all 142 passed.
The full platform suites and packaged executable gates remain independently
required before merging; local focused success does not replace them.

A fresh corrected-binary boss replay matches 3,200 state updates and 15 selected
original view crops, with 711,360 pixels compared and zero differences. All 15
raw PPMs are byte-identical to the prior verified replay. Checkpoint 1599 matches
the retained original/C++ previews at exactly 3x nearest-integer presentation.
The original preview is the retained October 1 controlled capture, not a fresh
natural level-7 route or complete-screen/campaign claim.

The [native archive](evidence/monster_word_wrap_20261004/README.md) retains
both complete captures, bootstrap images, raw logs, restorations, executed
source snapshots and failed-before/fixed-after diagnostics. It is 195,144 bytes,
with 29 byte-verified members and SHA256
`c4b600194b41e778a4f17809926a452b93743b77b58f05d617fe49411abd9b7a`.
The checker snapshot was executed for fixture, mutation and native validation
after fixture promotion, before archive-hash promotion. The initial extraction
version had an unpromoted fixture-hash pin and different archive bookkeeping;
it is not claimed as the byte-exact archived checker snapshot. Extraction logic
is unchanged, and the current checker independently revalidates both full raw
captures against the pinned bytes. All large local outputs stay in RAM; additional required raw logs
and frames must be durably retained before its owned keepalive ends.

## Remaining Scope

This establishes the captured full behavior-4 updates under shared seeded
profiles, including both signed coordinate boundaries. Observed zero edges
outside the map are not general out-of-map scan semantics. Other behaviors,
nonzero hotspots, shipped constructors, subsequent updates after wrapping,
player/timed/corpse coordinate boundaries, collision/damage boundaries, natural
routes and whole-game actor/campaign fidelity remain unverified. The four
OPEN items and all global completion/fidelity flags stay unchanged.
