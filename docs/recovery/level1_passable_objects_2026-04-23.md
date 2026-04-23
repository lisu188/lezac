# 2026-04-23 Level 1 Passable Object Route

## Problem

The level 1 route from player 1's start marker toward the documented
bomb-object area at tile `(24,22)` was blocked by the collision model before
the player could reach the object group. Holding right from the start stopped at
approximately `x=124`, where the 12x16 player footprint touched the vertical
object column at map column `17`.

## Evidence

- Level 1 starts player 1 at pixel `(104,168)`.
- The blocking column at map `x=17`, `y=17..22` contains visual object tiles
  such as `0x15`, `0x5d`, `0x60`, and `0x63` with word-layer key `0x0001`.
- The nearby level 1 bomb-object route includes other low-word object panels,
  such as word keys `0x0009` and `0x000a` over tile ids `0x50` and `0x52`.
- The far-right level 1 floor markers at `x=53..57`, `y=23` use high word-layer
  values around `0x7fbd..0x7fc1`; those must not become passable just because
  the word layer is nonzero.
- The prior tile-only passability rule allowed only portal tile `0x45` and
  bomb-object tiles `0x67..0x72`, so low-word object groups still blocked
  movement.

## Implemented Model

`solidPixel` now delegates to a cell-aware passability helper. A cell is
nonblocking when either:

- the tile id is already a known passable object (`0x45` or `0x67..0x72`), or
- the decoded word-layer value is a nonzero, undamaged low physical-object word
  (`word < 0x4000`).

High word-layer cells stay solid unless their tile id is already a known
passable object. This keeps the level 1 high-word floor markers from turning
into holes while allowing the start-route object columns and panels to be
traversed.

## Verification

`--debug-passable-objects` now locks:

- decoded portal and bomb-object tiles are passable,
- ordinary destruction-progress tiles remain solid,
- a synthetic full player/monster footprint over passable object tiles is
  clear,
- consumed bomb-object tiles stay clear,
- level 1 cell `(17,22)` is passable by low-word object classification,
- level 1 high-word floor marker `(53,23)` remains solid,
- holding right from the level 1 start advances beyond the formerly blocked
  object column.

This is still a C++ gameplay-model rule. Exact original collision/passability
inside `1000:6053..777f` remains an open disassembly/runtime target.
