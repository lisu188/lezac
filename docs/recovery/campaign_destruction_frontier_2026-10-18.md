# Campaign Destruction Frontier: Level 4

The current original-backed ordinary campaign replay ends at tick 11740, with
three Level 4 objectives collected and 244 of the required 305 destructible
cells destroyed. It has not completed Level 4 or reached Level 5. Levels 1–3
remain the only verified completed campaign levels.

## Read-only frontier diagnostic

Run from the repository root:

```sh
python3 -S -B tools/campaign_destruction_frontier.py
python3 -S -B tools/campaign_destruction_frontier.py --self-test
```

`campaign_destruction_frontier` reads the committed shipped-level JSON and the
Level 4 support-column C++ guard stimulus. The guard bytes are checked against
the fingerprint in the closed original-evidence manifest, but **the guard
stimulus is not itself an original-game observation or a new native fixture**.
The original-backed comparison remains in
`natural_level4_support_column_original` and its separate evidence guards.

The shipped Level 4 contains 435 physical damage words in the domain
`1..0x3fff`; its 70-percent requirement gives 305 destroyed words. At the
retained endpoint, 191 eligible words remain, matching the C++ destruction
counter `435 - 191 = 244`. An additional 61 destroyed cells are needed for the
destruction threshold. The existing three-objective threshold has been met.

The remaining physical word cells form ten four-connected groups, with sizes
76, 65, 9, 9, 6, 6, 6, 6, 4 and 4. The two largest groups occupy inclusive
cell-coordinate bounds `x=59..94, y=31..46` and
`x=27..46, y=34..46`. They are **scouting regions**, not proven reachable
bomb-placement positions or guaranteed destruction yields. Their topology may
change during ordinary collapse and actor updates.

The diagnostic checks dimensions, shipped denominators, little-endian word
planes, physical progress consistency, and map-group coverage. Its self-test
also rejects changed progress, truncated planes, incorrect denominators,
word-domain boundary errors and horizontal row wrap. It neither writes files
nor launches the original executable or C++ game.

## Next gameplay acceptance milestone

Extend `tests/fixtures/natural_level4_support_column/route.txt` through an
ordinary-input, non-injected Level 4 continuation in an **independent new route**;
do not modify the pinned existing route or original evidence. Use the largest
remaining eligible-word regions to prioritize exploration. Acceptance requires
at least 305 destruction cells, three collected objectives, an observed
empty-collapse completion gate and completed result/Level 5 handoff in the
unchanged original executable. Only then promote a closed original-only
capture, validate a production C++ replay with matching RGB and mapped state,
and advance completed campaign coverage from 3/7 to 4/7. Continue this process
for Levels 5–7, including natural boss victory and end-game transitions.

The current code does **not** establish those acceptance conditions, whole-game
playability, full original fidelity, sound timing or complete actor-state parity.
