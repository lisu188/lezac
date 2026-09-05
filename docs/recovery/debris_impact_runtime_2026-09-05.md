# Seeded Original Debris Impacts

## Scope

The production blocked-move path now calls the single-target equivalents of
`1000:3BB2` (X) and `1000:3D46` (Y). These helpers average signed lane bytes
with truncation toward zero, weighting the caller and debris target by 1
and a collapse target by its unsigned `+0x0E` byte. Both caller and selected
target receive the result. X can seed a new target; Y then resolves its
flagged word. New fragments are processed later in the same ascending pass.

This is **seeded original runtime evidence**, not a natural bomb-route
replay or an exact visual-parity claim. The natural forward-writeback item
remains open. Its historical fixture has not been rewritten to imply that
it contains the missing arithmetic inputs.

## Capture

```sh
python3 tools/capture_original_debris_impacts.py \
  --run-dir /tmp/lezac-debris-impacts-20260905 \
  --out /tmp/lezac-debris-impacts-20260905/collisions.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The run directory contains temporary copies of the shipped assets. The
script uses a private Xvfb display and the existing level seeder's original
level-1 start sequence: two `1` taps after six seconds, then an intro `1`
after three seconds and a 1.5-second gameplay wait. No original asset is
modified. DOSBox uses fixed 6000 cycles and surface output.

Guarded jumps at `1000:492F` and `1000:4D3A` stop immediately before and
after loop 2. CS scratch trampolines record actual registers and publish a
stop marker. Only the loop boundaries are instrumented; the mover, seeder,
matchers and blend instructions run unchanged. Host-side code changes are
made with the child stopped. Data inputs are written while the emulated
game waits at the entry marker. An explicit starter record makes the
otherwise-empty update eligible.
The wait instructions are immutable and released through a data flag;
an earlier rewrite-in-place wait loop occasionally skipped a measurement
and was replaced. The capture rejects an unchanged caller record.

The measured runtime registers are `CS=01A2`, `DS=0C44`, `ES=0C44`,
`SS=18B3`, `SP=3FD8`, `BP=3FF2` at both boundaries in the captured cases.
Thus the stops are `01A2:492F` and `01A2:4D3A`. The older seeder's signature
locator uses nominal `01ED`/`0C8F` segments; the capture calibrates the true
memory base from measured CS before following the map's far pointers.
The fixture stores raw register bytes, input/output records, local object
and word planes, tick, RNG, and the executable SHA-256.

Initial attempts failed to reach the stop with an empty queue, then exposed
the nominal-versus-measured segment difference. A subsequent attempt with
uncalibrated far map pointers was discarded. No failing attempt was
promoted into the fixture.

## Confirmed Behavior

- Existing debris: post-friction X values `49` and `-20` become `14`;
  Y values `-40` and `20` become `-10` on both records.
- Negative rounding: `(-49 + 20) / 2` becomes `-14`, not `-15`.
- Sub-unit results truncate to zero on both axes.
- A collapse weight of `255` is unsigned: X becomes `-19`, Y becomes `19`.
- A collapse weight of `14` exercises a different divisor and signed sum.
- A new debris target starts at zero, receives `(24,-20)`, and integrates
  those values in its sub-accumulators later in the same pass.
- A new one-cell collapse has weight `2`, receives `(16,-13)`, and keeps
  its original `0x60` glyph while its word changes from `0009` to `8009`.
- Duplicate debris keys select the newest matching record, even when the
  occupied destination corresponds to an older matching record.
- A positive-Y collision exercises the two bounce RNG draws before the
  weighted average: post-friction X `49` receives kick `-6`, then averages
  with `-20` to produce `11`; Y becomes `10`. The replay compares the
  resulting RNG state too.

## Validation And Limits

`--debug-debris-impacts tests/fixtures/debris_impacts_original.txt [frame-dir]`
replays one **production** `updateDebrisRecords()` call per original case.
It compares every byte represented by each 11-byte debris record, collapse
bounds/key/lanes/weight, both local map planes and the RNG state. It also
renders and checks a nonuniform frame for each case; an optional directory
receives PPM artifacts for inspection. Collapse bytes not yet represented
by the port are not claimed as covered.

The original post-probe screenshot was inspected: level-1 terrain, player,
platforms and HUD render normally. It is a run-health frame taken after
resuming, not a screenshot of the instrumented collision itself. C++ frame
inspection is likewise a rendering sanity check, not pixel parity with DOS.

Validation on 2026-09-05: all 416 CTest cases passed, with the Xvfb UI smoke
run separately from dummy SDL. Two repeat captures reproduced all nine
input/output record sets, local map planes and RNG states. The C++ replay
compared 16 complete debris records and three collapse results and
inspected nine frames. `new_debris` and `new_collapse` frame artifacts were
also visually reviewed; the final case's framebuffer hash is
`f04af41acb7a681b`. Generated artifacts and their SHA-256/record manifest
are under `build-codex-tmp/debris-impact-frames/`.

Other explosion callers retain their existing early glyph marking; only
collision seeding is changed here. Stale flagged cells with no matching
port record return without a table write, a reconstruction safety guard
not an original malformed-state claim. Multi-target helpers, capacity
failure memory effects, full collapse playback and natural route parity
remain follow-up work.
