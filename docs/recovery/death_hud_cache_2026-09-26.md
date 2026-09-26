# Death-state HUD energy cache

Baseline: main after PR #242 (`1d840eef396c8ef6f8f90ecc2c1d719364fbe894`).

## Original behavior

The original actor energy, cached HUD byte and painted bar are separate state.
Main-CS offsets below are file offsets minus `0x770` in the pinned executable.

- `7F40` gates the player actor/HUD pass on global player state 1.
- `7F97..7F9D` copies zero-extended actor energy to scratch word `DS:2074`.
- On fatal damage, `30D9` leaves the remaining-objective count in that word,
  while `3134` resets the separate actor energy byte to 100.
- `7FB3..7FC6` compares the whole scratch word against the zero-extended cached
  byte at `DS:79EC/79ED`, then stores the low byte on change.
- `568A` returns without painting if the unsigned word is above 100. Otherwise
  it paints that many palette-14 pixels, followed by palette-1 pixels, in the
  100-pixel row at y165. It does not clamp values to 100.
- The per-level reset sets the cached byte to FF; the initial bar remains grey
  until the first valid paint. Waiting/out players do not update this cache.

`core::HudEnergyBar` preserves the byte/word comparison, last painted fill and
initial unpainted state. PresentationState owns, resets and snapshots both
players' caches. The production damage boundary supplies the original scratch
value; rendering only reads the resulting presentation state.

The Level 1 trace now exports the effective state-2 animation cursor while dead,
as the original actor bytes do, and derives its energy-cache initialization flag
from the actual cache. No comparator fields or pixel regions were excluded.

## Independent retained capture

The unchanged original bundle was captured on 2026-09-24 and is now pinned as
`tests/fixtures/level1_original/held_fire`. Canonical SHA-256:
`29fc2da3226326443e8990f85be601bbdb4acf693fc5bef09d8e50737484252f`.
The existing walk, bomb and objective fixture bytes/pins are unchanged.

The route enters from the menu, holds normalized N input from tick 8 with
ten-tick repeats, and releases at tick 498. It runs 500 ticks with the controlled
initial RNG seed 305441741 and no gameplay teleports. The 497 gameplay frames
include deaths at post-update ticks 274/359/444 and reentries at 334/419.

The first death frames (275/360/445) have actor energy 100 but cached/painted
energy 1, the remaining-objective count. Later dying frames display 100.
The prior retained port comparison failed on animation and 17,303 HUD pixels.
The corrected replay matches all 497 full 320x200 frames, 994 projected states
and 31,808,000 pixels, with zero differing pixels or projected state fields.

## Validation

- The original-data guard pins seven instruction windows and nine lifecycle
  checkpoints, and checks every energy-bar pixel across all 497 original frames.
- Core tests cover 0/1/100/101/200/255/256/257/65535, low-byte aliasing and the
  distinction between cache changes and actual painting.
- Rendering tests cover two independent bars, waiting/out gates, snapshot
  restoration, level reset, initial grey rows and repeated-render purity.
- The live HUD diagnostic now checks actual 73- and 21-pixel energy fills.
- Final focused Linux CTest run: 11/11 passed. The four original routes total
  1,072 full frames, 2,144 projected states and 68,608,000 pixels without differences.
- Silent-launcher guard: 16 child and 16 grandchild cases, no games started.
  All compiled test/replay launches use dummy SDL audio and video.
- Real original/port screenshots at ticks 275 and 300 were inspected from the
  retained comparison; both pairs have identical full-frame source pixels.

These are normalized control-bank inputs, not host typematic or physical-key
proof. The last captured state is still dying with countdown 4, not terminal
game over. Audio waveforms and every raw actor-pool field are not compared.
Whole-game completion and original fidelity remain unproven; existing global
claim flags remain false. The separate physical held-fire recorder remains WIP.
