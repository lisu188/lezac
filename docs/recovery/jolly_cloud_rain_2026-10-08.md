# JollyCloud Map Rain Recovery

## Original Rule

The former four immediate Present/Diamond rewards were invented behavior.
The original grants score and sets a shared rain countdown instead.

- `1000:6E7E..6E8A` (file `75EE..75FA`) handles pending bonus 4. The branch
  writes `DS:79B2 = 46` without allocating a reward or drawing random values.
  A controlled original-code grant probe changes countdown 9 to 46; the only
  changed byte in the full data segment is `79B2`.
- Level initialization clears the countdown at `1000:2BC3` (file `3333`).
- `1000:81BF..81CD` decrements a nonzero countdown and calls the producer.
  The final decrement from 1 to 0 still produces an attempt. Zero at entry
  consumes no random value. This call follows the actor/player and terrain
  passes, so new falling records first move on the next frame.
- `1000:3F27..3FA5` chooses `width + Random(width)`, always map row 1.
  An occupied object byte ends the attempt after that single draw.
- An empty cell consumes `103 + Random(9)`. If that tile equals the level's
  objective tile, it is incremented. The producer writes the tile and the
  current `DS:78C4` word, then increments the word and calls `1000:370E` with
  zero velocities and the map cell index.
- The high-word seeder admits slots 200..1600, or 1,401 falling records.
  Saturation does not undo the tile, marker, countdown, or RNG writes; only
  the record allocation and the word's `8000` flag are withheld.
- Rain does not allocate an entry in the shared 30-actor pool.

## Retained Original Evidence

`tests/fixtures/jolly_cloud_original.json.gz` contains eight controlled,
continuous original-instruction trajectories, totaling 293 post-call samples.
Each trajectory receives its initial state once. Original instructions are
not patched, original calls are not stubbed, and hardware I/O is forbidden.
The original actor and visual storage remain unchanged in these captures.

Cases cover empty/occupied/alternating rows, the last available debris slot,
a saturated table, widths 32 and 114, width 1 with marker `7FFF`, and a zero
countdown. Every sample retains both map planes and the complete raw debris
table. A read-only hook also retains the map/scalars at entry to the original
seeder. The compiled comparison uses post-call states and active records;
it does not claim inactive record-storage equivalence.

Pinned identities:

- Original executable: `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
- Packed fixture (95,864 bytes): `29fd9d904aae7907290c2bb02743e05409b028f470336c03892d745533ac1678`.
- Raw JSON (9,995,096 bytes): `7d8f208f3f413f07842db75a0c0dfebaec325602c03bff6d3f66ad762e8be2a3`.
- Executed capture source: `72860f1921bbe3104b1db665abf99a2324c002c5c1bca07e898af7d059535c32`.
- Executed CPU helper source: `fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c`.

The capture generator and CPU helper were each executed from their attributed
single-read source buffer, without cached-bytecode imports. The generator is
retained as `capture-cloud-original-v3-t69.py` in this task's visualization
directory; capture reports/fixtures are retained under
`build-codex-tmp/physical-storage-integration-work-20261008-t67/`.
Fresh original capture is not a fresh-clone command in this batch: it depends
on the separately retained CPU-helper checkout and Unicorn dependency.
The checked-in comparison below needs only Python's standard library and
the compiled target. It verifies original executable and code-window identity
and both compressed/decompressed fixture identity before invoking the target.

## Production Wiring And Validation

`gameplay/jolly_cloud_rain.hpp` owns the recovered producer.
`gameplay/falling_fragment.hpp` extracts the existing high-word seeder and
unchanged record fields for reuse by both App and the standalone compiled probe.
App's `updateBonusRain()` uses these production paths, after `updateFlashes()`
and before palette/completion processing. Grant re-arms the shared timer;
`resetLevel()` clears it. The former four-reward producer is removed.

```sh
cmake --build build --target lezac_jolly_cloud_rain_test
env SDL_AUDIODRIVER=dummy ctest --test-dir build --output-on-failure \
  -R '^jolly_cloud_(core_original|checker_contracts)$'
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ctest --test-dir build --output-on-failure -R '^jolly_cloud_'
```

Local bounded compiled comparison matches all 293 samples and 1,664,782 bytes:
timer, RNG, next marker, complete tile/word planes and every active 11-byte
debris record. Seven compiled mutants are rejected: early final exit, wrong
row, extra RNG on blockage, missing objective exclusion, early/late capacity,
and wrong carried tile. Failure inputs, expected/actual outputs and stderr are
retained with hashes rather than overwritten.

The 17 stdlib checker contracts pass on WSL with the compiled protocol check;
Windows passes the 16 noncompiled contracts with that one test explicitly
skipped. App passes local syntax-only compilation. Local full game builds and
new native DOSBox captures are deferred under the Windows disk guard.

Hosted Linux/Windows validation is a separate delivery gate, not established
by the local helper result. The App probe runs its actual rain/queue paths
with a full shared actor pool. The lifecycle diagnostic exercises real
`updateWithControls()` calls, shared P1/P2 rearming, level reset, menu/pause/
intro/results holds, final decrement, zero-countdown RNG hold, and next-frame
movement. CI runs these and existing bonus/debris-order regressions early,
retaining both focused and final diagnostics.

## Still Open

These are controlled producer calls, not natural JollyCloud selection,
pickup or full campaign trajectories. The lifecycle tests verify port wiring,
not a native full-frame rain replay. Mixed explosions/collapse, arbitrary
marker wraps, full actor storage, physical cadence, rain VGA/RGB presentation,
sound parity and all-level completion remain open. No screenshot or broad
completion/fidelity flag is promoted by this batch.
