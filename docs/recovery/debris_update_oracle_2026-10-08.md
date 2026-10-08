# Complete Debris Updater Oracle

The optional `capture_original_debris_update.py` executes original `1000:45FA`
with spark count explicitly zero. This runs the complete debris pass, including
its real matcher, blend, seeder, removal, sound-latch and Pascal RNG calls. No
instructions are patched and no calls are stubbed. Normal CS/IP/SP return is
required; unexpected interrupts or hardware I/O fail the capture.

## Independent Native Cross-Check

Before generating new cases, the executor independently reproduces all 18
retained DOSBox collision and retirement cases. It compares complete live
11-byte debris and 15-byte collapse records, selected captured map cells and
RNG. The historical capture does not provide the whole initial map outside its
controlled region, so complete native map equivalence is not claimed.

## Expanded Controlled Cases

The 1,061-case fixture contains 18 native cross-checks, 288 airborne and 288
supported motion cases, 45 shatter/retirement cases, 256 debris contacts, 160
collapse contacts, and six same-pass cascades. Velocities and sub-accumulators
include signed-byte extremes. Controlled collapse mass includes zero and high
unsigned bytes; these are explicit test states, not natural-reachability claims.

The original executes 373 forward and 373 reverse blend calls, 230 writes at
each debris writeback site, 422 RNG calls, 214 sound-latch calls, eight seeder
calls and 28 removals. Maximum execution is 1,589 instructions per case.

The fixture retains the complete input/output object and word planes, every
live debris/collapse record byte, counts and RNG. Metadata pins executable,
shipped levels, decoder, generator, native fixtures, relocated image,
instruction window, and fixture/input/output digests. Reproduction is exclusive:

```sh
env SDL_AUDIODRIVER=dummy python3 tools/capture_original_debris_update.py \
  --exe LEZAC.EXE --levels LIVELS.SCH --native-fixtures-dir tests/fixtures \
  --unicorn-path /path/to/unicorn-2.1.4 \
  --out /path/to/empty/debris_update_original.bin.gz \
  --metadata /path/to/empty/debris_update_original.json
```

## Production Comparison

`--debug-original-debris-update INPUT OUTPUT` deserializes explicit case-boundary
states, calls the actual `App::updateDebrisRecords`, and serializes all compared
fields without rendering or an alternate movement model. The checker compares
every output byte, rejects an output mutation, and checks six source-routing
mutations. CI runs this before its unchanged complete suites on both platforms.
Any failed input, reference and C++ output are retained and uploaded before
later steps. Source/oracle checks alone do not establish compiled parity.

The collapse-seeding correction from #311 is a prerequisite for the diagonal
low-word cascade case. Its running source and checks remain untouched.

## Limits

This is controlled CPU execution and case-boundary production replay, not a new
native capture or complete natural collision/campaign replay. The spark pass is
empty by setup. Sound state, timer cadence, presentation, arbitrary memory,
unused table tails, actors, two-player interaction and full collapse updates
are outside this comparison. All broad original-fidelity and whole-game flags
remain false. In particular, this does not close the natural `3D2D` route item.
