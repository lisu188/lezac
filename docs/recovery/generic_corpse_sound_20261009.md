# Generic Corpse And Boss Sound Ownership

The generic tile-damage conversion at original `1000:74BB..7517` does not
request sound. The cursor `0x003d`, priority 12 request at `1000:5C9E` is in
the separate boss-death chain starting at `1000:5BCC`. Its existing C++ boss
call remains; the extra request in `enterMonsterDeath` is removed.

## Original Evidence

Two independent executions of unmodified `LEZAC.EXE` instructions cover
1,152 controlled seeds, 2,304 actor passes and 3,456 complete storage
boundaries of 1,864 bytes each. They include 960 impacts, 192 nonfatal hits
and 768 fatal entries for kinds 1..8, behaviors 3/4, both frame parities,
three horizontal velocities, stored HP 0/1/255, animation modes 0..3 and
spawner availability 0/1/254/255. No sound-latch request routine or RNG call
is reached in the captured tile-damage updates. These are seeded cases,
not natural campaign routes.

The independent validator checks exact impact/fatal partial writes and
generic target writeback. All 6,441,984 complete-state bytes match between
executions with no masks. Eighteen semantic input controls are rejected;
these controls are not compiled C++ mutants.

Pinned evidence:

- Original executable SHA-256:
  `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
- Expected stream, raw SHA-256:
  `93ebfe626427e2ec300dc3e7c98b0d4adeda7ad442dadf3297bcd8691a6a2371`.
- Expected stream, deterministic gzip SHA-256:
  `202e4b6f0d511ccf7bfaac26ab82d245be23a5530421f19f8781874b97bcc50c`.
- Independent validator SHA-256:
  `7c971706dd3d65ad679ee5b8bffa34e648c411ac9fbb5a8dbdc86f19c72605bd`.
- Retained original execution roots:
  `/tmp/lezac-fatal-entry-original-20261009-t96` and
  `/tmp/lezac-fatal-entry-repeat-20261009-t96`.
- Retained passing validator root:
  `/tmp/lezac-fatal-entry-validation-20261009-t96-v2`.

The first validator attempt incorrectly used descriptor width for hotspot
Y. Its failure and source are retained. Inspection of `1000:5A75..5AFA`
established that hotspot Y is `16 - descriptor[1]` (height); correcting that
field produced the passing validation without weakening comparisons.

## Production Regressions

`monster_tile_damage_original` checks 1,312 existing original-backed cases
through `updateMonsters`, including 96 fatal hits. It now also verifies
unchanged request cursor/priority and unchanged latch for idle, accepting
active and rejecting active-priority seeds. Request fields are checked
because they change even when priority rejection leaves the latch intact.

`monster_death_sound` checks that direct generic conversion does not submit
a request, then invokes the actual `bossDeathChain` and verifies its retained
cursor/priority and pump behavior. Both tests run as focused Linux/Windows
CI steps before the full suite, with their logs retained separately.

Local syntax and any extracted-function probes are not whole-App runtime
proof. Exact-head Linux/Windows CI results must be inspected separately.
No sound ISR, rendered audio, visual parity, natural constructor, campaign
or whole-game completion claim follows from this repair. Generic live-actor
physical write-through and raw spawner ownership remain separate open work.
