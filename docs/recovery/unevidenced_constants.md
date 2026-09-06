# Inventory of Unevidenced Port Values

This is the list of values the port uses that the **original has not
established** — no byte citation, no capture, or an inference from a single
observation. It exists because this project's recurring failure mode has not
been missing functionality; it has been a green test suite that verifies the
port agrees with *itself*.

Two examples show why both measurements and their interpretation need review:

- A "measured" 41-tick small-bomb fuse, read from `DS:0x74A8` record offset
  `0x1B`. That table is the level-file monster **spawner** table and the byte is
  its cooldown; tick 437 was the level-1 spawner's third cooldown-zero. The
  `bomb_fuse` ctest pinned `fuse=41` — the port's own constant echoed back — and
  passed throughout. The actual actor countdown and all four constructors
  are now covered by the [bomb fuse capture](bomb_fuse_runtime_2026-09-05.md).
- Debris **saturation** at 100 was inferred from raw table bytes without
  checking whether those slots were live. The original does retire the
  record, clearing the map flag but leaving stale tail bytes at rest=100.
  The previous `debris_motion_live` assertion that such records must survive
  was therefore wrong. The bounded
  [rest-counter capture](debris_rest_runtime_2026-09-05.md) now checks the
  original live bound, map flags, compaction and counter edge cases.

Both were found by testing the assumptions behind the accepted evidence.
So the point of this file is not documentation — it is to make the set of
unproven values **machine-checked**, so nothing can quietly join it or slip out
of it. `tools/check_unevidenced_constants.py` (ctest `unevidenced_constants`)
requires every `UNEVIDENCED` / `UNRECOVERED` / `INFERRED` marker in
`src/app/app.cpp` to carry an `@unevidenced:<tag>` and to appear here, and
every entry here to still have its marker in the source. Recovering a value
means deleting the marker and the entry together, in the same change that adds
the evidence.

**A pin that echoes one of these values pins a mechanism, not a duration.**
That distinction should be stated wherever such a pin is registered.

## Entries

- `damage_cooldown_ticks` — `kDamageCooldownTicks = 18`. The invulnerability
  window after taking damage. No byte citation and no capture fixes it. Its
  wall-clock duration changed from ~0.30 s to ~0.73 s when the live loop was
  governed, because it is a tick count that was chosen under the old 60 fps
  pacing. Echoed by the `player_state2_death_fields` and
  `player_state2_return_active` pins.

- `corpse_sprite_non_kind1` — the corpse sprite for monster kinds other than 1.
  The byte-cited table `DS:[0x0077 + kind*2 + dir]` gives kind 2 → 42,
  kind 3 → 52, kind 4 → 56, and the port uses those; what is unevidenced is
  that no death of a non-kind-1 monster has been CAPTURED, so the table read is
  trusted without a fatal-conversion runtime confirmation. The newer
  `monster_damage_original` capture verifies the nonfatal impact sprites of
  kinds 2/3/4, but does not kill those kinds.

- `bomb_direct_monster_damage` - `monsterDamageForBomb` returns weapon-sized
  damage applied immediately by `explode`. This is now refuted, not merely
  unproven: the seeded original small-bomb trace first damages two updates
  after expiry, then drains 4, 6 and 2 HP from transient flame cells. Swapping
  bomb/monster slots at the same frame parity produces the same target trace.
  `bomb_actor_order_observation` checks that evidence and explicitly reports
  `cpp_damage_claim=0`. The current synthetic bomb tests still pin port policy;
  they do not establish original explosion damage. Live flame propagation,
  timing and damage integration remain to be recovered together.

- `debris_shatter_dice_phase` — the port's `logicTick_` standing in for the
  original's `DS:78C2` in the landing-shatter dice `(frame + slot) % 6 > 2`.
  The mechanism is byte-cited; the equivalence of the two counters' PHASE is
  not, so a shatter can fire on a different tick than the original's would.

## Deliberately not listed

Values that are byte-cited or capture-backed do not belong here even when they
look arbitrary — for example the `+0x40` gravity step, the `0x7b` debris
gravity gate, the 14-tick behaviour-4 retarget period, the `ai1 = 271` velocity
range, the phase-dependent 49/50-update normal corpse lifetime and retirement
at debris rest count 100 are all
established, and each has a diagnostic that would fail if it changed.

Initial bomb pixels equaling the player's cached pixels are also established
by the constructor call and all 16
[bomb motion traces](bomb_motion_runtime_2026-09-05.md). The former
`bomb_pixel_equals_player_pixel` entry was removed with that evidence.

The player's terminal velocity `0x07FF` is explicitly present in the
player-specific gravity branch at `1000:6743..6753`, independently of monster
gravity. The former `player_terminal_velocity` entry was removed with the
[player movement recovery](player_walk_runtime_2026-09-05.md). The value is
instruction-backed; the five movement traces do not reach terminal velocity.
