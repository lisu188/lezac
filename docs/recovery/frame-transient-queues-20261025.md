# Original Frame Transient Queue Caller

## Boundary

`FrameTransientQueuesOperation` executes the eight original caller instructions
from `804E` through `8067`, stopping before `806A`. It selects the existing
`45FA` spark/debris updater and `5102` collapse updater using the original
unsigned comparisons against DS:2076, DS:207E (200), and DS:2080. CALL writes
the actual near return word to shared SS; child RET, register changes, queue
compaction, and stack cleanup are computed rather than replaced by endpoint
state. The bridge retains the mid-frame SP, BP, game segment, and ID mask.

The operation supports bounded instruction grants, partial REP copies,
snapshot restoration, and computed timer interruption. It validates caller
instruction counts by PC, child identity and ordering, root stack ownership,
terminal state, and dispatch/timer/byte counter conservation. Counters alone
are not an authentication mechanism for arbitrary fabricated historical state.

## Independent Original Corpus

`tools/frame_transient_queues_oracle.py` runs canonical, unmodified MZ code in
the pinned Unicorn 2.1.4 library. It does not execute the C++ candidate. Each
controlled case is repeated with and without observers; all registers and the
complete 1 MiB result must agree. Ordered writes must reconstruct that entire
result, and code must remain unchanged. No original calls are stubbed, no
instructions patched, no interrupts delivered, and no hardware I/O occurs.
The emitted projection contains compact initial inputs, computed register
traces, and ordered writes, not a full guest memory image.

The 3,973 cases contain 1,142 spark/debris profiles, 2,551 collapse profiles,
256 coupled profiles with both updater calls, and 24 targeted non-last debris
retirements. The retirement cases force `458D` compaction and the actual
parent SS loop-word decrement, both alone and before collapse processing.
All eight caller instructions and all four call patterns are observed:

| Pattern | Cases |
| --- | ---: |
| Neither updater | 3 |
| Spark/debris only | 989 |
| Collapse only | 2,390 |
| Both in original order | 591 |

Original execution computes 3,383,388 instructions and 542,433 ordered writes.
Outcomes are 3,965 frame-tail arrivals, six runtime errors, and two divide
errors. Of 27 native-derived initial profiles, 26 retain independent standalone
endpoint cross-checks. The remaining profile now executes `45FA` first, so its
changed collapse input is deliberately not compared to an incompatible old
standalone endpoint. All 24 retirement cases and every 128th case retain dense
traces, totaling 55 dense cases.

Frozen files:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `manifest.json` | See file | `a341604bb80d817d4418793b6098d527d863ff9bdc97feed476523c17436376d` |
| `oracle.bin.gz` | 550,419 | `501ca71c2ce0467b1e7522fdfe178b1109c6843c1bfcdec25b9c55ed870dfd2f` |
| Decoded projection | 16,781,046 | `ae3d8d4ec1be48a6d486a2fbee989ce26061d4e72780dd573b5f24d3cae5deb5` |

The checker binds four assets and seven producer sources, the mapped Unicorn
library, proof scope, counts, and compressed/decoded payloads. Modified,
deleted, unreadable, protected-output, hardlink, and export/report overlap
controls preserve source inputs and failed reports.

## Replay Controls

The C++ consumer runs six schedules per original case: instruction budgets
1, 17, and 4,096 crossed with copy grants 1 and 65,535. It restores every
consumed grant and compares original call selection, outcome, complete endpoint
registers/flags, ordered writes, and all memory. Caller trace rows compare all
flags; borrowed helper intermediates retain the documented undefined-arithmetic
flag mask. There are 23,838 replays, 79,665 register comparisons, 24,235 exact
caller-flag checks, 20,287,353 dispatches, and 43,838 state rejection controls.
The standalone unit adds 575 state rejections at eight caller boundaries and
three real CALL entries.

Computed timer controls cover 21 original-corpus boundaries and 10 unit
boundaries. They check resumption and grant-schedule equivalence, not an
independent original timer trace. Nine zero/oversized/partial-copy controls
cover `456B`, `45CE`, and `50BE`, including IRQ after a one-byte partial copy.

Fourteen compiled faults cover both queue thresholds, the debris equality
boundary, collapse selection, both actual CALLs, completed counters, restored
caller registers, error propagation, SP/BP ownership, PC-count binding,
counter conservation, and CMP parity. Each must compile and fail a controlled
unit or original-replay assertion; compilation failures are not detections.
The unchanged spark/debris and collapse mutation suites also exercise the
backward-compatible generic mutation runner used by this new suite.

The checked-in projection is reproducible without running the C++ candidate:

```sh
PYTHONPATH=/path/to/pinned-unicorn-2.1.4 python3 tools/frame_transient_queues_oracle.py \
  --repo "$PWD" --out /dev/shm/lezac-fresh-frame-queue-oracle
```

The destination must be fresh and RAM-backed. A second generation in this
recovery run reproduced both frozen files byte-for-byte. Frozen-corpus CTests
do not require Unicorn or a local DOSBox installation.

Validation on 2026-10-25 passed strict GCC and MSVC unit/original replay,
AddressSanitizer/UndefinedBehaviorSanitizer unit/original replay, and 25 focused
CTests across all four dependency kernels and the new bridge. The cold Git
checkout test covered 34 frozen families and 34 CRLF negative controls. Source
guardrails covered 174 mapped sources. All seven fixture tests passed on Linux;
Windows passed six and explicitly skipped the unsupported WSL-UNC hardlink
operation. Native MSVC retained `/W4 /WX`; its initial test-only alias-shadowing
and bool/integer comparison warnings were fixed without relaxing flags.

A fresh silent existing-App boss replay passed 3,200 samples, 15 views, and
711,360 compared pixels with zero differences, including defeat at sample
1,714 and cleanup at 1,833. Fresh views 1,599 and 2,399 were byte-identical to
authenticated retained original PPMs. This is only existing-App regression
evidence and does not expand the kernel's scope below.

## Scope And Remaining Work

This is a controlled original-backed caller/composition kernel, not a natural
DOSBox route, live App integration, whole-frame proof, or whole-game parity.
The existing `FrameActorPassOperation` intermittent-replay hold is independent
and remains open. This bridge does not clear that hold or wire the new updater
path into the interactive application. Existing App screenshots and boss
replays cannot establish visual fidelity of a kernel the App does not use.

All work and validation are RAM-backed under the current disk-capacity guard.
Audio remains disabled. Full core dumps and full guest RAM are not published.
