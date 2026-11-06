# Two-Player Walk And HUD Owners

The ordinary-startup `tests/routes/two_player_walk_hud.route` selects two
players through the menu and exercises both players' movement, jump, posture
and fire controls. The retained original window is ticks 4..204: 201 complete
320x200 RGB frames and 402 presentation/post-update boundaries. One initial
RNG seed and normalized control-bank events are declared controls; there are
no later gameplay-state injections. This is not wall-clock or physical-input
timing evidence, a completed level, or whole-game fidelity.

## Recovered Differences

The previous port matches Player 1's complete record, but uses 29..36 for
Player 2's left walk. Original DS:0068..0069 is 29..35; Player 1's separate
DS:0064..0065 range is 10..17. Right-walk ranges are 2..9 and 21..28.
`619F..61B7` and `620C..6224` load the separate table entries, and
`6A96..6AC6` tests the inclusive left bounds before initializing animation.
The wrong range yields 108 actor-byte and four visual-byte differences;
only RGB frames 96 and 97 differ in this captured route.

The same capture exposes 221 differing scalar bytes at the shared WORD
DS:2072. That word is not just an allocation/tile-query result. The dirty
objective helper seeds it with 0xD028, moves left by nine after each bonus
digit, and, if destruction changed, resets it to 0xE428 and moves left after
both destruction digits. The caller skips the helper when neither display
is dirty. Score updates write the player score-table offset (0 or 46) even
when phase >= 2. Painting a running reel then writes 0xDC00 plus the physical
HUD destination and advances nine times by nine, including skipped leading
zero glyphs. A reel that becomes settled during this call is still painted.

Presentation update owners now commit these ordered writes through an
optional shared-word writer. The App supplies the physical storage writer
and reads HUD destinations from link-row-zero aliases; drawing/tracing do
not synthesize the scratch value. Existing standalone presentation callers
remain valid without a writer. This is not a unified original DS address
space, nor coverage of every remaining DS:2072 owner.

## Original Authentication

REA 6.7.0 with Ghidra 12.1.4 on WSL authenticates eight complete windows
covering player bounds/left selection, objective caller/writer/number printer,
and score caller/painter. Every loaded byte equals an independently relocated
original window; explicitly undoing each relocation reproduces the file bytes.
The session closes, server exits zero and target remains unchanged.

The original MZ is 52,384 bytes, SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Both original selectors also execute 1,024 seeded fragments with pinned
Unicorn 2.1.4. Complete memory and registers agree with/without write
observation, ordered writes reconstruct all output bytes, and independently
expected full DS bytes agree. These are bounded fragments without injected
timer/interrupt/hardware behavior, not a full original frame execution.

The original natural-route reference SHA-256 is
`6e7ef5d047720786aa6d5517ffbc5b4a7a8ba091dc1d19892e1a0dd05fc1d9d9`.
All 402 full DS snapshots and ten selected complete RAM snapshots are
privately compressed on C:, with complete archive-member readback equality.
No raw RAM, original frame payloads or screenshots are publicly uploaded.

## Validation

Both fresh GCC C++23 and native MSVC builds match all 201 RGB frames,
all 402 typed-state boundaries, and all 648,024 physical backing bytes per
platform. This includes both 38-byte player records, inactive pool tails,
visual guard rows, all eight link rows and all four scalar bytes, unmasked.
The previous binaries and failing App regressions are retained privately.

Permanent App regressions cover all 1,024 input animation cursors/directions,
physical animation writes, three objective gates, 64 score/skip/phase cases,
physical HUD destinations with WORD wrap, and draw-time preservation. A
separate unit checks complete ordered HUD writes in four objective and 192
score cases. Existing original-HUD oracle tests now also compare the shared
word, or preserve the caller's sentinel for a clean no-call case.

The focused Linux selection passes 55 tests including the original HUD
fixtures; native Windows passes 12 validation commands. The changed
presentation implementation and ordered-write unit also compile under
MSVC `/W4 /WX /permissive-`, and the native unit passes. Replaying the
unchanged ordinary-startup 18,700-tick single-player route preserves all
201 retained level-4 RGB frames and 648,024 backing bytes on both platforms.
Wider campaign,
level-7 boss, frame-pass stability, host timing and owner acceptance remain
open. Full-frame and whole-game fidelity flags stay false.
