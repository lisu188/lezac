# Byte-addressed damage lane recovery

The C++ helpers in `src/gameplay/damage_lane_bytes.hpp` recover the shared DS
operations in original routines `1000:3A7E`, `3B18`, `3BB2`, and `3D46`.
They are not yet integrated with App's typed queues. PR362's direct-fragment
production mismatch therefore remains open. This is a recovery foundation,
not a production repair or a whole-game fidelity claim.

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

Reproduce the original fixture with the pinned Unicorn 2.1.4 runtime:

```sh
env SDL_AUDIODRIVER=dummy PYTHONDONTWRITEBYTECODE=1 \
  python3 tools/capture_original_damage_lane_bytes.py --root . \
  --out /tmp/lezac-lane-bytes-original \
  --unicorn-path /path/to/pinned/unicorn
```

Run the compiled recovery checks:

```sh
cmake --build build --target lezac_damage_lane_bytes_test
ctest --test-dir build --output-on-failure -R '^damage_lane_bytes_'
```

## Remaining Integration

App needs a shared byte-addressed view that forwards known aliases into the
physical queues, sound cursor, phase scratch, and other modeled banks, and
retains out-of-bank writes. A separate shadow buffer with no reads by affected
subsystems is not a complete alias model. Current pure diagnostic lookups must
remain distinct from original runtime mutations. Integration must preserve the
original seeder behavior and rerun all affected raw App comparisons, including
the retained both-host PR362 failures and nonzero prior-phase histories.

Natural routes, rendered pixels, sound-runtime parity, full DOS memory coverage,
and whole-game completeness are not established by this fixture. The historical
raw-prefix guard remains failed.
