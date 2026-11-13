# Reward Physical Storage Write-Through

## Scope

Continuing reward updates and in-place pickup/expiry conversions now write
their production results into `ActorSlots`. The same per-record lifecycle
helper advances inherited animation before contacts, preserves both players'
cached-kind pickup semantics and RNG order, and retains the existing App
behavior-2 motion callback. Later converted actors use the existing behavior-5
transient path. Opaque actor bytes and the stored animation backup are not
reconstructed from typed objects.

This is a staged binding of these paths, not a complete raw-record owner.
Reward allocation, corpse-to-reward selection/creation, natural spawning,
other actor families, player/world updates, pending-bonus effects, sound and
rendered fidelity are outside this fixture. In particular, the existing
constructors and corpse conversion can still leave physical fields pending
their own recovery; this batch does not claim that newly created rewards are
already raw-state faithful. No high-level completion flag changes.

## Original Evidence

The pinned unmodified `LEZAC.EXE` has SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Two independent original CPU captures execute 87 controlled cases through the
complete native shared actor pass `1000:7EBB..7EEA`. Their 4,982 boundary
streams agree exactly. Each boundary contains all 31 actor records, 33 visual
rows, eight link records, actor/visual/link counts, allocator result, RNG,
pending bonuses, contact-hit counters and alive gates: 1,585 bytes, including
unused physical tails. The full stream compares 7,896,470 state bytes.

The seeded cases cover all seven reward kinds, ordinary motion and expiry,
P1/P2/simultaneous pickup, occupied pending slots, inactive players, inherited
animation modes 0..3, both initial parities, timer values 0/1/2/255, and mixed
3-/29-/30-record pools through complete retirement with normal/reversed visual
references. There is one seed per case, followed only by continuous native
passes and an explicit frame counter. Terrain and word planes come from the
pinned Level 1 native fixture and remain unchanged.

The executor adds no code patches or call stubs and rejects interrupts and
hardware I/O. Adding write/code observers leaves all 1 MiB of memory and 14
registers equal to the same pinned executor without those added observers at
every return. Frozen producer, repeat reports and original-only semantic
validation are in `evidence/reward_storage_20261009/`.

The v1 exploratory producer used the preceding sprite descriptor; those
captures remain retained but are not promoted. v2 corrected the one-based
descriptor index but stopped large pools with live survivors. The accepted
v3 fixture extends these pools through retirement and adds timer boundaries.
Nonzero inherited reward animation is controlled input, not demonstrated
natural reachability; ordinary corpse-to-reward conversion clears its mode.

Fixtures:

| File | Compressed SHA-256 | Uncompressed SHA-256 |
| --- | --- | --- |
| requests.bin.gz | 098ef3d5b15a7819f9ea98f4e3ccbb75530ee671d55cc4e5eb268f1a81abe456 | 8a68fc46f6457f784423eca69a70978081102bffd836b09cc58b1b18cc452338 |
| expected.bin.gz | 6797216835dad9113684141b1395fc55010d036b4333d0d7575b0e23f2a69ef4 | b503b8304a767b08a0d5af3471c537f66c4393283d909afd7b7632cdfa58ba44 |

## Production Writes

`advanceBonusDrop` advances the active animation with the physical slot's
backup before its contact/behavior branches. Continuing rewards write kind,
timer, velocity/fraction words, hotspot, behavior, active animation and visual
coordinates. An animation advance changes only the visual pixel-offset word;
it does not replace width/height. Pickup and expiry use the sprite-conversion
writer, which intentionally changes all four descriptor bytes and hotspot.
The resulting transient record is written before publishing its typed family
conversion, retaining the original identity and opaque/backup bytes.

Both contact gates use the original reward type. Each newly pending bonus
consumes one RNG draw, including P2 after a P1 pickup. Pickup motion still uses
cached behavior 2 before the timer subtraction; subsequent passes use behavior
5. Expiry follows motion and the odd-frame timer subtraction, converting
results 0 or 255 to the native 18-count fade without shifting the already
written visual position. Existing stable retirement preserves inactive tails.

## Validation

The compiled helper replay matches every native output byte at all 4,982
boundaries with no masks. The ASan/UBSan replay also matches. Fifteen compiled
production-code mutants are rejected: skipped animation or writes, rewritten
dimensions, erased backup, missing sprite conversion, single-player-only or
blocked second pickup, ignored pending gates, missing cached gravity, lost
fraction, missing mode clear, wrong fade sprite/timer and unphased countdown.
Every complete mutant output is retained losslessly with raw/compressed hashes.

The shared compiled fixture reader rejects 34 malformed requests. Checker
tests cover pinned hashes, bounded decompression, unmasked opaque/scalar
comparison, source routing and nine mocked process outcomes. Those mocked
outcomes are checker contracts, not game executions. Existing storage-binding
(1,800 operations), marker (1,008 boundaries) and transient (256 boundaries)
compiled regressions still pass. Source/GRAN ownership and App syntax pass.

The actual-App command `--debug-reward-storage-original` restores state only
on S commands, disables legacy adoption, and executes `updateOrderedActors`
on U commands. It checks physical order/identity, terrain preservation and
zero legacy adoptions/retirements after each operation. Its output includes
the App's actual RNG, pending bonuses, damage counters and alive gates.
P1's complete raw record is outside this actor bank and is not claimed.

Five CTest entries are registered: helper/App original comparisons,
helper/App malformed-protocol checks, and checker tool contracts. Linux and
Windows CI run and retain them immediately after Build. Actual-App execution
and full CI are pending at initial publication; local helper/source checks
must not be presented as that runtime evidence. The existing launch-marker
visual guard remains required in CI; its 10,292,004-byte text inputs exceed
the current local reserve cap and were not materialized for this batch.

All agent-launched processes use `SDL_AUDIODRIVER=dummy`. No local game build
or DOSBox process was launched. Local source, build and evidence roots stay
below 8 MiB each. Original assets, saves, earlier captures, protected edits,
and all transitive Git object donors are preserved.
