# Ordinary Two-Player Lifecycle Regression

Two independent ordinary-startup routes extend the earlier two-player walk
and HUD comparison. Both select two players through the menu, use one initial
RNG control and normalized control-bank inputs, and inject no later gameplay
state. All runs use dummy audio. These are not physical-input/host-timing tests.

`two_player_fire_stress.route` retains ticks 4..604. Player 1 uses movement,
jump and posture, while Player 2 also fires repeatedly. Both remain alive at
the end, with health 25 and 40. This route does not contain Player 1 fire or
establish death/reentry, despite the original private planning label.

`two_player_reentry.route` replays its full 1,204-tick prefix from the menu,
retaining ticks 604..1204. It adds Player 1 left movement with Z, actual fire
with N, jump with M, and further Player 2 firing/movement. Original full DS
observations establish Player 1 death at post-update tick 703, reserve loss
at 763 and successful reentry at 1021. Player 2 dies at 1193; its subsequent
reentry is outside this retained window and remains unproved here.

## Original Evidence

The immutable 52,384-byte MZ SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Private original reference hashes are respectively:

- `cc3e13bba3358dcd3ff12cb8b9cbdbc5c08443b551beebd4f5d21c301fe46c67`
- `22d7c8370e93d5a844ff061128962d086df03845f023bab9b816ad4139db087a`

Both captures retain stopped-child full DS snapshots at every rendered and
post-update boundary. Each state read verifies both player records and all
43,552 code-prefix bytes after independently applying MZ relocations and
restoring the four declared hook signatures in a temporary read buffer.
Owned children terminate, hooks restore and canonical assets stay unchanged.
Private compressed C: backups include selected complete RAM snapshots and
pass complete member/source readback. No raw RAM, original frame payloads
or screenshots are included in the public fixtures.

REA/Ghidra rechecks original control-bank, death-record, waiting-countdown and
reentry behavior/health writers. This static evidence is separate from the
ordinary-route runtime captures; it is not execution of a complete frame.

## Permanent Native Check

Each hash-only fixture records all 601 complete RGB-frame hashes, 1,202
typed-state projection hashes and 1,202 complete physical-backing hashes.
The backing concatenation is the 38-byte Player 1 record, 31x38 actor bank
(including Player 2), 33x8 visual rows, 8x16 link rows and four scalar bytes.
All 1,612 bytes per boundary are included, without masks or normalization.
That is 1,937,624 backing bytes checked in each window and native platform.
Inactive tails, visual guards, unused record bytes and shared HUD scratch
are included. Typed projections additionally cover map planes, RNG and HUD.

The existing actual-App owned-scout suite replays both routes, pins each whole
fixture and exact route hash, verifies canonical asset hashes, phase pairing,
record widths, frame/checkpoint counts and disabled legacy adapter, then
compares every expected hash. Both Linux and native Windows pass. The two
601-frame windows overlap at tick 604; no missing checkpoints are filled from
another run, and they are not presented as one uninterrupted native capture.
Git byte-preservation attributes protect the pinned JSON on Windows checkouts.
The retained pre-repair native Linux and Windows Apps each fail both new
window checks at the physical-backing comparison. These are real historical
binaries, not fixtures generated from the current C++ output.

## Limits

The hash fixtures cannot recreate an original frame or full RAM snapshot;
those remain in the private evidence archive. Neither window completes a
level. This does not cover every DS global, every lifecycle branch, Player 2
reentry, a full original instruction-level frame, the complete campaign,
level-7 boss parity, wall-clock input, audio waveforms or owner acceptance.
Full-frame and whole-game fidelity flags remain false.
