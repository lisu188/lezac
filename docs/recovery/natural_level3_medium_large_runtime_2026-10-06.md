# Natural Level 3 Medium/Large Overlap

## Verified window

A separate ordinary-input branch after the original-verified tick-8100
checkpoint releases a Medium bomb at tick 8111 and a Large bomb at tick 8121.
Both are released at player position 274,248 with zero horizontal velocity.
This reverses the order of the earlier Large-first attack; it is not an
extension of the tick-8750 branch. The earlier input prefix is unchanged.

The original and C++ versions both reach nine objectives and 132 destroyed
tiles at tick 8420, with health 66, zero stored reserves, 12 Medium bombs,
no Large bombs and score 43620. The empty Large selection remains selected,
as in the original. Destruction increases from 110 to 132 on this branch,
18 beyond the earlier original-backed 114-tile frontier.

Level 3 requires seven objectives and 148 destroyed physical-damage cells.
The objective requirement is already satisfied, but 16 more destroyed cells
and a natural completion transition remain. A collapse record is still active
at the endpoint. This is not Level 3 completion or whole-game fidelity.

- 321 complete 320x200 RGB presentations match with zero differing pixels,
  including the shared fork frame and 320 new frames.
- 642 present/post-update mapped boundaries match, including both map planes,
  player motion, ammunition, score, counters, palette and RNG.
- All 960 new complete 64 KiB native DS boundary snapshots are retained.
- The compared live debris/collapse records and bounded monster, lifecycle
  and score-marker projections match throughout the suffix.
- Eight mapped-state mutations are rejected.
- A separate endpoint check rejects 24 mutations: each of eleven compared
  collapse fields and the active count changed independently in native and
  C++ inputs. This covers offsets, flagged word, lanes, subpixel values,
  argument magnitude, flags, rest ticks and affected bytes for one active
  record, not every actor byte or every collapse scenario.

The fresh original run follows the established ordinary campaign from Level 1
through the natural Level 2 finish. Its 4,324 existing Level 3 prefix frames
and 12,972 sampled prefix boundaries repeat the previous original capture.
That is original-to-original prefix verification; the new C++ comparison is
limited to the 321-frame window above. Both versions were visually inspected
at tick 8420, and their retained paired previews have identical RGB bytes.

## Pinned inputs

Captured C++ source head: `e4a7f90872c3b9ea3d089b4aa652e9b16b33d6b8`.
The later reward-pickup sound-source guard repair does not change gameplay.

Compiled C++ executable SHA-256:
`e1c95b811de11b1be1b0651448570a6f5736e3b6e39a5e34d2571aa14eee18d3`.

Route SHA-256:
`b769afc25fa1284d67fa0f67ed9619e57a67046606babb402111e0d164354134`.

C++ trace SHA-256:
`b2bf5b11bdf5334718c8ca6893daeb5654e4644e41fa80ddede38cd1f2d3b018`.

Original stream SHA-256:
`a1b38d1e8c1d60932c0fa05decb6453cf3c2fb599495e884bc93357d91efc632`.

New raw DS stream SHA-256:
`dddc3d6c760c0711acf608352d4e95f5f4d1cf82ffc6915c738357c97f3653f6`.

Final RNG: `3197421319`. Final tile-plane SHA-256:
`8c0054cd82850dae9ee855ccd1c252cf43025ccf4b8d3e5ce26389ddf725740c`.
Final word-plane SHA-256:
`e3217e16d8c4511410978726887d4b9e5e619b1eb93c647110e3208e90cdb61b`.

## Independent retention

The complete original attempt, controls, route, producer sources and captured
C++ executable are retained under
`refs/notes/qa-natural-level3-20261005-medium-large-original-20261006-raw`.
Its 4,746-member archive is 98,755,711 bytes, SHA-256
`ee744606f3fe7bce6bfcc8c4b7e5c774ae94fd45fe77dd45418467061919b2e6`.
Notes commit: `93212ab9700f41292e6433beda0ace07aab954f6`.

Actual terminal controls, including the keeper closure after raw retention,
are separately retained under
`refs/notes/qa-natural-level3-20261005-medium-large-original-20261006-closed-controls`.
Its 47-member archive is 290,907 bytes, SHA-256
`bfbccf6891e33348c1c4d300a1f3a08193f8bec1324f84e7cd975778eced533f`.
Notes commit: `8fafc515602c06a1078bc2d3d82982005dae8651`.

The C++ scout's raw output and controls were independently retained first
under `refs/notes/qa-natural-level3-20261005-medium-large-overlap-20261006-cpp-raw-and-controls`.
That 464-member archive is 8,078,913 bytes, SHA-256
`44c69d9bcb63bbd8ee17c84df3ea3aa5b85f6fa20cf2cbb61ef43d408ad20680`.
All three archives have whole-archive byte readback, every-member size/hash
readback and fresh remote notes/tree-anchor verification.

## Limits

All game, capture and test processes use dummy audio. The original runs on a
private Xvfb display and the C++ replay uses dummy video. No new gameplay-state
injections were added. Complete raw DS bytes are preserved, but this comparison
does not claim equality of every raw actor, clock or sound byte, audible sound,
physical timing, full-prefix C++ fidelity, Level 3 completion or later levels.
All four broad OPEN items and whole-game completion/fidelity flags stay open.
