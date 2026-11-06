# Link Row Zero Global Aliases

The first sixteen bytes of the link bank are live globals, not an unused boss
record. Boss links start at row 1; row 0 has these owners:

| Row Offset | Original Address | Owner |
| --- | --- | --- |
| 0, 1 | `DS:79EA/79EB` | Player reserve bytes |
| 2, 3 | `DS:79EC/79ED` | Cached HUD energy bytes |
| 4..5 | `DS:79EE` | Saved single-player width in eight-pixel columns |
| 6..9 | `DS:79F0/79F2` | Playfield destination words, including the four-row/four-pixel inset |
| 10..13 | `DS:79F4/79F6` | HUD column destinations, 0 and 180 |
| 14 | `DS:79F8` | Sprite-bank tag: fonts 1, gameplay 2 |
| 15 | `DS:79F9` | Boss link count, already owned by actor storage |

Named storage accessors preserve all neighboring fields and reject invalid
player/viewport indices. They do not expose boss link row 0 as an active link.
New-game initialization writes reserves, countdown expiry writes reserve loss,
level setup resets caches and HUD destinations, and successful width changes
write saved columns and playfield destinations. Ordinary level setup does not
refill the reserve bytes or reset the saved width.

The production HUD update reads its physical cache byte before comparing the
full input WORD. Its gate preserves both raw and presentation state for waiting
and out players. Presentation's painted bar remains distinct from its cached
byte. The existing three-argument API remains available to explicitly seeded
standalone diagnostics; production damage/HUD boundaries use the physical-cache
overload. There is no render/capture-time cache backfill.

The production raster reads `79F0/79F2` directly from the physical owner. It no
longer reconstructs those destinations from typed layout at every draw. An
explicit standalone view retains its declared destination without changing the
owner. A conflicting-destination regression verifies both live reads and draw
purity. Normal preview geometry remains an explicitly separate diagnostic path.

Sprite-bank tags follow intro/menu and gameplay setup. The post-run reset
callback restores the font tag after its compatibility level reset. This is
ownership of the logical cache tag, not a reconstruction of original file I/O,
allocation or sprite-bank loader lifetime; AssetCatalog still preloads assets.

## Original Evidence

REA 6.7.0/Ghidra 12.1.4 on WSL verified every byte of thirteen writing windows
against the unchanged 52,384-byte original MZ, SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Independent MZ loading and relocation checks agree. These 141 bytes contain
no relocations. The target remained unchanged and the session closed normally.

| Window (End Exclusive) | Bytes | SHA-256 |
| --- | ---: | --- |
| `2F5F..2F69` | 10 | `a917820de2f57f8f4aaca92ae25ab2058df2dcc0fd661e06013f16944f5f77f5` |
| `7CA7..7CB3` | 12 | `eece0e981286c75bd2e092413f56298015c45fe041f327a5d1d4fa049c0c9e50` |
| `2CE6..2CEF` | 9 | `39d187fef224b898a2fc82ba6c5bd7952b0abe55be51ad611245a601c3193340` |
| `7FAF..7FCA` | 27 | `867e54b464cfbb6ee3d712707866346bbbf578773fc2cc7956696078b9f7a9cd` |
| `2905..290B` | 6 | `03bb1f16b0e136b3b6bd196caf8d7de82053dba7d902f123dd5de705815d42c1` |
| `8240..8246`, `827A..8280` | 6 each | `c1e2e3069d2605d3b7232c4ab5a8948b1919e6a00201f624709f3aac3c0c5f69` |
| `298B..29A6` | 27 | `432ea68334ad01e051515ff91ba747359712ff646ab74b46bde9ae47c77be910` |
| `29CD..29D9` | 12 | `28200ab8e846e8b607f13b8b874e3d96a30b52b8191e24c83a0679763e9adae9` |
| `2B85..2B90` | 11 | `7330ed67a55c5ec03cca90e5936e1ece7d25e71d4ed26fff0a9acc595a89f7bf` |
| `2C31..2C36`, `1B54..1B59` | 5 each | `96df52e083a3088ed6d1f0b3500fe08992e20e78dc8e7fce09378575d4869d96` |
| `2CBB..2CC0` | 5 | `df939fbaf2240d3c9cfe7d3d3af71712c78f6d6944c6373f3b67f851b4b53c02` |

Unchanged original fragments execute 6,466 controlled cases: reserve setup and
all 512 player/reserve decrements, cache reset, 5,120 cache BYTE/WORD comparisons,
saved width and both resize stores, twenty single-view destinations, split/HUD
destinations and sprite-tag stores. Observed and unobserved complete 1 MiB
memory and registers agree. Ordered writes reconstruct the entire output, which
also equals independently modeled complete expected memory. Original code is
unchanged; interrupts and hardware I/O are rejected. These are writing fragments,
not execution of the complete startup, HUD painter or sprite loader.

The actual loaded Unicorn 2.1.4 library mapping is checked against SHA-256
`ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c`.
Selected complete original memories and raw receipts are backed up privately.

## Native And App Checks

GCC and strict MSVC storage tests emit the same 239,250-byte stream as the
original fragments, with whole-length, SHA-256 and byte equality:
`c3270387a5c24182a871f11f857cddb7dd09155ad6d2a3a8b4fbe2428bf62af0`.
Records include declared inputs and complete before/after alias rows. The C++
test separately verifies all actor, visual, link, count and result storage is
preserved outside each write, using nonzero surrounding payloads. Six invalid
index controls leave the complete state unchanged. A repeated native run seals
the unit source, all headers, compiler and output identities.

`--debug-link-alias-ownership` exercises actual App initialization, both player
counts, all twenty widths and resize gates, six reserve losses with duplicate
expiry guards, 5,120 physical-cache comparisons against deliberately conflicting
typed caches, four inactive gates, level carry and the post-run menu callback.
The legacy actor adapter is disabled. Three separately compiled App faults are
detected: missing reserve write, typed-cache projection and inactive cache write.
An unchanged O0 build passes with the same compiler settings.

The real renderer initially failed when the physical viewport destination
conflicted with typed layout. Its corrected test compares the shifted view and
checks that the owner is unchanged. Ten renderer fault controls cover this new
read path as well as existing physical visuals, map, camera and driver ownership.
The descriptor control is now scoped to its original branch; a first multiline
selector failed on a CRLF checkout. That failed run is retained. Normalizing
only the temporary mutant text fixes the selector without editing production
sources. The earlier App ownership failure and the post-run bank-tag failure
are retained as separate source/binary counterexamples too.

Final full GCC C++23 and native MSVC App builds pass. Validation includes 45
focused Linux CTests, 14 Windows commands, an overlapping 26-test Linux
player/render selection with ten renderer mutations, five strict MSVC owner
commands and source guards. Full hosted CI is a separate, potentially pending
lane and is not implied by these focused local results. All launches are muted.

## Captured Storage Milestone

Fresh final-source Linux and Windows replays run the full ordinary-startup
18,700-tick prefix without later gameplay-state injections. In retained level-4
window 18500..18700, all 201 full RGB frames and 402 paired gameplay boundaries
match the original. Every serialized physical-storage field now matches without
masks: 31 actor rows, 33 visual rows, eight link rows and four scalar bytes per
boundary, totaling 632,748 bytes per platform. This includes inactive actor/link
tails, the visual guard and all sixteen row-zero aliases. The previous 4,020
link-row differences are gone. Independent direct-DS verification pins each
original snapshot and final native executable, and rejects all 1,574 single-byte
payload corruptions per platform. Pixels already matched before this repair.

## Remaining Scope

The serialized actor bank starts at player 2; player 1's separate raw actor is
not included. This inactive-player-2 combat window does not prove complete
active two-player physical records or every boss link trajectory. Unified DS
ownership, original loader lifetime, whole-frame stability, complete campaign
and level-7 boss acceptance, wall-clock/physical-input timing and owner
acceptance remain incomplete. Broad whole-storage, full-frame and whole-game
fidelity flags remain false. No raw RAM, DS slices or screenshots are published
with this change.
