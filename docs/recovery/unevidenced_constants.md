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
  passed throughout.
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

- `player_terminal_velocity` — `kPlayerTerminalVelocity8 = 0x07ff`. The
  player's falling terminal velocity. The `+0x40` per-tick gravity step IS
  measured (`tests/fixtures/route_timing_original_level1.txt`), and the clamp is
  carried over by analogy from the original's actor gravity
  (`1000:7028`/`702C`), whose step matches. But no capture reaches terminal
  velocity — the deepest observed fall peaks at `vy = 704` — so the clamp VALUE
  is an inference from the actor path, not a measurement of the player path.

- `bomb_fuse_durations` — `BombProfile::fuseTicks = 41`. See the note above:
  the previous "measurement" was a misread spawner cooldown. No bomb countdown
  seed has been located in the image; the only `dec byte es:[di+0x1b]` in the
  binary belongs to the monster spawner loop. This value only preserves the
  port's long-standing wall-clock duration.

- `bomb_fuse_profile_table` — the Small/Medium/Large/Super fuses
  (`41/61/82/410`) in `bombProfile()`. Same status as above; the three
  non-small values additionally have no measurement of any kind behind their
  ratios.

- `bomb_pixel_equals_player_pixel` — the identification of a placed bomb
  actor's pixel position with the dropping player's pixel position. Inferred
  from ONE consistent point: player pixel (200,308) → base 3724 →
  post-walk `DS:C1E8` = 3925, exactly as measured. A second capture at a
  different pixel phase would settle it.

- `corpse_sprite_non_kind1` — the corpse sprite for monster kinds other than 1.
  The byte-cited table `DS:[0x0077 + kind*2 + dir]` gives kind 2 → 42,
  kind 3 → 52, kind 4 → 56, and the port uses those; what is unevidenced is
  that no death of a non-kind-1 monster has been CAPTURED, so the table read is
  trusted without a runtime confirmation of the kind-1 sort that
  `monster_impact_sprites` provides.

- `debris_shatter_dice_phase` — the port's `logicTick_` standing in for the
  original's `DS:78C2` in the landing-shatter dice `(frame + slot) % 6 > 2`.
  The mechanism is byte-cited; the equivalence of the two counters' PHASE is
  not, so a shatter can fire on a different tick than the original's would.

## Deliberately not listed

Values that are byte-cited or capture-backed do not belong here even when they
look arbitrary — for example the `+0x40` gravity step, the `0x7b` debris
gravity gate, the 14-tick behaviour-4 retarget period, the `ai1 = 271` velocity
range, the 49-tick corpse hold and the 100-tick debris rest ceiling are all
established, and each has a diagnostic that would fail if it changed.
