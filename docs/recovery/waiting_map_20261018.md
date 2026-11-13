# Waiting Placement: Physical Map And Shared Cursor

## Production Correction

The ordinary two-player reentry prepass now reads waiting-player support cells
through its canonical `MapPlaneMemory`, including retained object tails, live
word-plane aliases and retained bytes after reallocation. The old logical-tile
check returned zero beyond `level_.tiles.size()` and lost those original reads.

Original `7E22` stores the computed support index in `DS:2074`. The App now writes
that same canonical shared cursor, owned by `SoundEngine`, before its map reads.
No sound request is invented. Signed typed coordinates are converted through an
integer before wrapping to the original visual word, avoiding an out-of-range
negative-float-to-unsigned conversion.

The production change is confined to `updateWaitingPlayerPlacement`. Diagnostic
layout seeds and copies remain outside normal gameplay.

## Original Evidence

Two independent executions of the unchanged MZ-relocated original produce
identical 320-case endpoint streams and manifests. The pinned Unicorn 2.1.4
library's actual mapping is verified. Each observed run matches an execution
without instruction/map-read observation hooks across all 1 MiB of memory and
all final registers. All 43,552 relocated code bytes remain unchanged.

Each case executes the complete `7C3D..7EBB` prepass window with no expiry or
input reentry. Thus HUD redraw and external callees are legitimately not taken;
they are not patched or stubbed. No interrupts or hardware I/O are allowed.
There are 1,035 observed physical object-byte reads at the original comparison
instructions. The map remains unchanged throughout each original execution.

Cases cover one or both waiting players, inactive players, open/closed reentry
gates, the 1..76 solid range, the asymmetric right-cell Y guard, wrapped/signed
visual coordinates, object decoder tails, live low/high word bytes and retained
heap-gap bytes after a larger allocation. The original uses an explicitly
normalized `4000:0000` object view. These are controlled map contexts, not proof
of natural heap initialization or arbitrary adjacent Pascal allocations.

The retained fixture is 11,532 bytes, with only numeric controlled inputs and
selected original endpoints, not raw RAM. Identities:

- EXE: `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
- Fixture: `430af0d6476dab271a63983a7002be74f9a6cf2fb61fddad1b1101d22ceea469`.
- Manifest: `3b08b01dddb5d14d23e07a69112567f189cc588809175a669ab8f624c5e75752`.

## Validation

The actual App, with only the new diagnostic added, failed case 0 before the
production correction. After the correction, all 320 cases pass through the
ordinary `updatePlayerReentryPrepass`, including final cursor, coordinates,
countdowns, player states, fallback counter and unchanged map vectors.

The fixture checker authenticates producer/shared source, original executable,
manifest, evidence scope and every endpoint byte. Four Python tests pass on
Linux, including 18 actual-App malformed/counterexample controls. Native Windows
passes the three provenance tests and explicitly skips the actual-App test
because no native App executable was supplied. Native Windows runtime acceptance
remains a separate CI gate.

The existing original-backed regressions pass: 54 expiry/reentry cases, the
980-sample/60-view boss guard with 130 rejection controls, zero-reserve/player-out,
and fire/reentry. A fresh fire/reentry replay compares 758,784 indexed viewport
pixels across 16 views with zero differences. The existing natural-campaign
replay and evidence guard also pass, without extending their original coverage.
Fourteen selected CTests pass. Linux and native Windows Git preserve the new
stream/manifest in actual autocrlf cold checkouts; removing protected-family
rules reproduces manifest CRLF conversion. The unrelated existing `snprintf`
warning remains.

Original indexed sample 139 and its freshly rendered C++ viewport were shown
and inspected. The historical indices were displayed with the shipped base
palette; the C++ image uses its live presentation palette. Their visible sky
color difference is not hidden or promoted to RGB/DAC parity. The original
boss trace has a seeded case boundary and is not a natural campaign victory.

```sh
cmake --build build --target lezac_cpp
ctest --test-dir build -R waiting_map --output-on-failure
ctest --test-dir build -R state2_prepass --output-on-failure
```

## Remaining Goal Work

The full original prepass instruction operation, expiry callees, HUD/end-run
presentation, IRQ/work-clock coupling and whole seven-level campaign remain
open. This corrects a concrete live ownership mismatch; it does not establish
complete frame timing, arbitrary original allocation layout or whole-game
parity. All local build and visual outputs are ephemeral RAM-only under the
approved disk guard; full Linux/Windows CI and current-head review are still
required before merging.
