# Owned Actor Storage Scout

`--replay-level1-owned-scout ROUTE OUTPUT_DIR START_TICK` runs the existing
deterministic SDL-event replay with the historical actor-seeding adapter
disabled. It accepts the same optional `--original-intro-wait`, `--result-reels`
and `--result-typing` flags as `--replay-level1-scout`. The latter two still
require `--original-intro-wait` first. Existing replay commands are unchanged.

The name refers to production-owned **storage**, not an interactive-loop,
physical-input, wall-clock, original-fidelity or whole-game acceptance claim.
Replay still supplies the route's seed, scheduled time and SDL input events.
Ordinary gameplay constructs the actors; capture never reconciles, repairs,
backfills or restores them from typed state.

## Artifacts

The normal candidate `trace.jsonl` gains two explicit header fields only in
this new mode: `actor_storage_mode: "production-owned"` and
`legacy_actor_seed_adapter: false`. Existing strict readers that do not opt
into these fields reject it. No existing validator is relaxed by this change.

The separate `actor_storage.jsonl` uses schema
`lezac.actor-storage.scout.v1`. Its header records the route fingerprint,
capture start, layouts, reserved slot and inactive-tail/guard inclusion. Each
retained checkpoint has the same `seq`, `tick` and `phase` as the normal trace,
plus:

- `count`, `visual_count` and `success`: the literal storage scalars.
- `orders`: active nonplayer identities, in physical slots 1 through `count`.
- `actors_hex`: all 31 records, 38 bytes each, including reserved player 2
  in slot 0 and the inactive tail. Player 1's separate actor record is not
  part of this storage object.
- `visuals_hex`: all 33 rows, 8 bytes each. Row 32 is guard memory; its last
  four bytes alias descriptor 0 in the original address model.
- `links_hex`: all eight link rows, 16 bytes each, including inactive rows.

Hex fields are lowercase, row-major byte strings. Each checkpoint exports
1,570 backing bytes without filtering fields. The complete footer records the
retained checkpoint count. Failed output is not a completed capture. Both
streams keep `candidate_only: true` and `original_fidelity_claim: false`.

## Current Limits

The first private, original-backed level-4 combat comparison found matching
typed gameplay observations but raw-record and rendered-frame differences
with the adapter disabled. The bomb construction, motion/countdown write-back
and expiry conversion gaps are now repaired; see
[the bounded recovery evidence](recovery/bomb_owned_writeback_20261106.md).
Reserved-player, inactive visual, link-bank and shared-result differences
remain open.
This command exposes those differences; it does not assert raw storage parity
or correct them during capture. Private original snapshots and comparison
artifacts are not included in this change.
