# Natural Level 3 Corrected Ammunition Continuation

## Verified window

An ordinary-input extension from route tick 8100 to 8750 uses the recovered
reward-pickup phases without changing the previous input prefix. It spends one
Large bomb, cycles through Small to Medium, and releases two Medium bombs.
The original and C++ versions both finish with nine objectives, 114 destroyed
tiles, health 66, zero stored reserves, 11 Medium bombs and no Large bombs.
The selected weapon remains Medium. Level 3 requires 148 destroyed tiles and
its remaining objectives; this route does not finish the level.

- 651 full 320x200 RGB presentations match with zero differing pixels.
- 1,302 present/post-update mapped boundaries match, including both map planes,
  player motion, ammunition, score, objective/destruction counters and RNG.
- The new original suffix retains 1,950 complete 64 KiB DS boundary records.
- Bounded live/corpse actors and live debris/collapse projections also match.
- Eight mutations reject changed ammunition, health, RNG, position,
  destruction count and both map planes.

The fresh original run follows ordinary input from Level 1, through the natural
Level 2 finish, to this Level 3 endpoint. Its 4,324 existing Level 3 prefix
frames and 12,972 sampled prefix boundaries reproduce the prior original
capture exactly. That is original-to-original prefix verification; the new
C++ comparison is limited to the 651-frame window above.

## Pinned inputs

Source head: `e4a7f90872c3b9ea3d089b4aa652e9b16b33d6b8`.
The later sound-guard repair changes no gameplay source bytes.

Compiled C++ executable SHA-256:
`e1c95b811de11b1be1b0651448570a6f5736e3b6e39a5e34d2571aa14eee18d3`.

Route SHA-256:
`4bc3f86ebfe6f88716a06f84721011616b9776a3210b663ef58bc58a41853ec5`.

Original stream SHA-256:
`0fe4d1736a7c2152f16dc6fafd2ae5e94782d0f372aaf9f3b8ecaebf01e960bb`.

Raw suffix DS SHA-256:
`c4eec6b7e13a8ae6244c224ae911fa5d9548d6a816ed4c3924a070ca03450e70`.

C++ trace SHA-256:
`276e58dc59819d7c9b7f9e859ea2c7dd3ef04954bb015bf036a7d9656a97d1b2`.

Final RNG is `3764104504`; final player position is `(28,272)` and score is
`43620`. The compiled route is a continuous production replay with ordinary
key events, not a restored memory fork or per-tick state injection.

## Retained evidence

The original raw archive has 5,093 members and 111,364,474 bytes, SHA-256
`3b72b757b2a9e9aa596213421e8da9765f9f3f807faa7e3b8c52b58ab2492d2c`.
It is independently retained with full archive/member readback under
`refs/notes/qa-natural-level3-20261005-corrected-ammo-original-20261006-raw`
and its two chunk refs, anchored at the source head above. Closed controls are
retained under
`refs/notes/qa-natural-level3-20261005-corrected-ammo-original-20261006-closed-controls`.
The C++ candidate's earlier raw retention is recorded under
`refs/notes/qa-natural-level3-20261005-corrected-ammo-one-large-20261006-cpp-raw`.

Local control files, failed-reader diagnostics, actual terminal receipts and
paired previews are in
`build-codex-tmp/level3-corrected-ammo-original-work-20261006/`.
The first comparison reader matched the gameplay window, then incorrectly
tested map mutations against the debris/collapse projection. The preserved
second reader changes only that mutation target to the existing map-state
comparison and uses a separate preview directory. Neither capture was rerun,
no comparison predicate was relaxed, and all eight mutation checks pass.

## Limits

All launched processes use dummy audio. This does not establish audible sound
parity, physical timing, full-prefix C++ parity, all actor/raw bytes, natural
two-player completion, Level 3 completion, later-level completion or whole-game
fidelity. All broad completion/fidelity flags and OPEN items remain unchanged.
