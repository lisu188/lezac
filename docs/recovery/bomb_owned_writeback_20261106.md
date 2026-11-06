# Owned Bomb Write-Back

The adapter-free scout exposed a production-storage gap hidden by the old
typed rendering path. The bomb's typed motion and timer advanced, but its
physical record and visual coordinates stayed at their constructor values.
Placement also retained an earlier actor's active animation; expiry did not
convert the owned slot or replace its full descriptor until a later update.

## Original Code

REA 6.7 with Ghidra 12.1.4 on WSL independently checked these complete windows
against the immutable 52,384-byte original MZ:

| Window | Bytes | Original File SHA-256 |
| --- | ---: | --- |
| `1000:2F9F..30A3` (end exclusive) | 260 | `189d417a54fa3c7eacec479279164257d6f6f6a8277b84927d08d0fb6324411c` |
| `1000:6C00..6CB8` (end exclusive) | 184 | `56a33471b834656500fce95a157d929c9f67505572395fa22b4dc05a656f58ee` |
| `1000:75A7..766D` (end exclusive) | 198 | `e7b6054a082e90ede3db62e98695140804ae91891563056b2d84f20bd0b2a8d2` |

The constructor contains two relocated far-call operands. The check parsed
the original MZ relocation table independently, verified Ghidra's complete
reported relocation set, compared the loaded bytes, then explicitly undid
those relocations and compared every original file byte. The original was
unchanged; the analysis session closed successfully. This was static code
inspection, not game execution or whole-program equivalence.

Successful fire calls animation initialization with four zero arguments at
`6C65..6C7B`, producing the stopped active animation with step 1. It leaves
the backup and other opaque bytes intact. The timed branch changes the raw
counter at `75A7..75B0`. Expiry changes kind, mode, timer, velocity, descriptor
and animation at `7604..766A`, before the particle constructors; the common
motion/coordinate write-back follows them.

## Production Changes

- Successful placement initializes only the active animation, not the backup.
- Live updates write the owned motion, fractional words, visual coordinates
  and original byte countdown. Expiring motion stays deferred until conversion.
- Expiry converts the same owned record and installs the full fade descriptor
  before constructing particles, then performs the common write-back.
- Two older seeded diagnostics now explicitly allocate their bomb slots before
  invoking conversion. Production ownership checks are not bypassed.

## Regression Evidence

The new constructor and physical write-back checks fail on the unfixed App
and pass after the change. The existing original-backed timed fixture now
compares all 38 actor bytes and all eight visual bytes for its 592 bomb cases,
with the legacy seed adapter disabled for those updates. The production
lifecycle regression covers all four bomb types at both starting parities,
with 32 live updates, expiry, deliberately nonzero inherited backing and
inactive-tail preservation. Existing full-capacity conversion checks remain.

A private ordinary-startup replay of the complete 18,700-tick route retained
the level-4 combat window `18500..18700`: all 201 complete RGB frames and
402 paired gameplay boundaries match the original on native Linux and Windows.
All 778 active nonplayer whole-record comparisons match. The earlier failing
captures and their 75 differing RGB frames are retained privately, not
rewritten. Original snapshots, binary slices and screenshots are not published.

## Remaining Limits

This bounded combat window is not whole-campaign, level-7 boss, wall-clock,
physical-input or owner-acceptance proof. Reserved player 2, inactive visual,
link-bank and shared-result differences remain visible in the full storage
capture. Whole storage/frame equivalence and the earlier frame-pass stability
hold remain open; the capture's original-fidelity flags stay false.
