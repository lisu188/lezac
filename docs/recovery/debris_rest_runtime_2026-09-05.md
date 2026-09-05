# Original Debris Rest Retirement

## Correction

The original removes a live debris record when its rest byte equals 100
after the conditional byte increment. It clears bit `0x8000` in the **map
word**, leaves the object glyph in place, shifts later records down and
continues with the shifted record in the same tick. It does not clear the
inactive tail of the record table.

The previous saturation model was wrong. Both older level-2 samplers scanned
80 slots regardless of `DS:207E`, and the reduced shatter fixture dropped
that live-bound field. A raw slot persisting at rest=100 with its record
word still flagged was misinterpreted as a live fragment. The original
bounded capture reproduces that persistent rest/flag pattern after retirement.
Historical raw rows are preserved; the saturation interpretation is
explicitly withdrawn. The natural samplers now respect the validated live
bound and label their rows `live_records_only=true`.

## Capture

```sh
python3 tools/capture_original_debris_impacts.py --suite rest \
  --run-dir /tmp/lezac-debris-impacts-20260905 \
  --out /tmp/lezac-debris-impacts-20260905/rest.txt \
  --approve-procmem --approve-runtime-instrumentation
```

This uses the same temporary original asset copy, private Xvfb display,
fixed 6000-cycle DOSBox and guarded loop boundaries described in
[the impact capture](debris_impact_runtime_2026-09-05.md). The original
physics instructions are unchanged. An extra static window pins
`1000:4CEF..4D05`, covering the increment and equality branch. Inputs are
explicitly seeded, not natural-route evidence.

Measured stops: `CS=01A2`, `DS=0C44`, `SS=18B3`, `SP=3FD8`, `BP=3FF2`;
Ghidra `1000:492F` and `1000:4D3A` are runtime `01A2:492F` and `01A2:4D3A`.
ES is `0C44` at entry. It is `3F26`, the word-plane segment, after the
single/blocked/double retirement cases, and `0C44` after the other cases.
Raw register bytes, map cells, live bounds and the first inactive tail
record are stored in `tests/fixtures/debris_rest_original.txt`.

## Results

| Probe | Original Result |
| --- | --- |
| Supported rest=98 | Rest becomes 99; one live record remains. |
| Supported rest=99 | Live bound drops from 200 to 199 (empty). Map `C001` becomes `4001`; glyph `60` stays. |
| Seeded rest=100 | Rest becomes 101 and survives, proving equality rather than `>=`. |
| Seeded rest=255 | The byte wraps to 0 and survives. |
| Airborne rest=99 | Gravity resets rest before the no-step increment: rest=1, vy=4. |
| Free move at rest=99 | The fragment moves, stamps both planes and resets rest to 0. |
| Blocked move at rest=99 | The blocked tick counts as rest and retires the record. |
| First of two retires | The successor shifts into slot 200 and integrates vx=9 in that same tick. |
| Both records at rest=99 | Both retire in one pass; neither is skipped after shifting. |

The decisive single-record bytes are:

```text
before live_slot=200 record=c70401c000000000636000
after  live_slot=199 records=none
after  inactive_tail=c70401c000000000646000
map[1223]: object=60, word C001 -> 4001
```

Thus the stale record's `+8` byte is `64` and its `+2` word is still `C001`,
even though **no live record remains** and the map flag has been cleared.
The artificial 100/255 cases pin byte semantics, not normally reachable
long-lived records. All nine cases leave the RNG state unchanged.

## Regression Coverage

`--debug-debris-rest tests/fixtures/debris_rest_original.txt [frame-dir]`
replays the production mover and compares live counts, complete surviving
11-byte records, local object/word planes and RNG. It explicitly excludes
the inactive tail in the retirement case and renders nine nonuniform
frames. The long debris route checks real retirement with retained glyphs
instead of requiring indefinite survival. Exact explosion/collapse visual
parity and complete natural collision routes remain open.

The repeated original run reproduced all nine record/map/RNG/live-bound/tail
results. The earlier nine impact cases were also re-captured unchanged after
the harness extension. C++ `rest_99` and `rest_99_shift` frame artifacts were
visually inspected: retired glyphs remain visible and the surrounding level
and HUD render normally. All nine frames passed nonuniform-pixel inspection;
the final framebuffer hash is `2f5e22ad2bea1f0b`. Generated PPM files and a
SHA-256 manifest with live bounds and tail metadata are in
`build-codex-tmp/debris-rest-frames/`. This is rendering sanity evidence, not
an original-to-port pixel-parity claim.

Local validation on 2026-09-05 covered all 418 CTest cases, with Xvfb UI
smoke run separately from dummy SDL. The shared decoder tests cover captured
stale tails, the full live range beyond the old 80-slot limit, invalid
bounds and truncated snapshots. Both natural sampler modules were also
import-checked to confirm they use that shared decoder.
