# Fracture Capacity Physical Pools

The complete-pool protocol supplements the fracture-retirement fixture with
all 1,401 physical fragment records and 250 collapse records, plus one guard
record beyond each capacity. It retains the complete actor/visual/link bank
and the sound request/latch fields. It does not change production physics.

## Original Evidence

96 unmodified-original updater cases cover collapse counts 1/2/249/250,
fragment counts 0/1399/1400/1401, actor pools 0/30, and fracture in the first,
middle or both end records. Timer seeds include 0/94/255. The producer
observes 12,048 rest increments, 120 fractures/removals/actor constructor
calls, 240 fragment seeder calls and 11,928 normal writebacks.

An observed and neutral executor agree on all 1 MiB RAM and 14 registers
after every update. No instructions are patched, calls stubbed, interrupts
or hardware I/O permitted. Capacity admission is checked independently:
new fragments equal min(two per fractured block, remaining fragment slots).
Every pre-existing live fragment and both physical capacity guards remain
unchanged. Terrain, RNG, counters, full compaction output, actor banks and
sound fields are retained for raw App comparison without masks.

Each input is 26,727 bytes and each state is 26,721 bytes. The complete
comparison covers 2,565,216 state bytes plus a 16-byte framing header.
Compressed/decompressed fixture and expected-stream SHA-256 pins are
independent of the comparator. This fixture explicitly permits compressed
data below 256 KiB; all earlier fixtures retain their 128 KiB bound, and the
common 6 MiB decompressed bound remains unchanged.

## App Protocol

The existing --debug-original-fracture-retirement command accepts the new
LZFC0001 fixture framing alongside the unchanged LZFR0001 protocol. It seeds
all physical records, restores the actual actor owner, skips expected bytes,
calls the same production updater and writes LZFP0001 results. Guard records
are retained but never counted as live records. CI retains actual output,
executable hashes and comparison diagnostics for exact-head inspection.

## Boundaries

Existing fragment payloads are capacity seeds and are not advanced in this
collapse-only call; their full initial terrain ownership is not claimed.
This is not a naturally reached full-pool game state. Native CPU evidence,
source syntax and checker contracts are not compiled-App acceptance.
Linux/Windows raw outputs and full required CI remain separate delivery
gates, as do dependency integration and completed external review. No
natural-route, full contact coverage, rendered-pixel, sound-interrupt,
campaign or whole-game fidelity claim follows from this fixture.
