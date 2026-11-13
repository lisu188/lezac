# Controlled Full-health Boss Defeat

## Scope

This extends the [800-update combat evidence](boss_active_combat_runtime_2026-10-01.md)
with a separate 3,200-update original capture. The original head begins with
life byte 1 and HP byte 10, without reduced head health or a planted bomb.
Ordinary small-bomb shots eventually trigger the fatal chain; all seven boss
actors become moving kind-14 bombs and subsequently explode. The continuous
C++ production replay matches the entire sequence and its later destruction.

This is a controlled boss defeat, not a naturally completed campaign, complete
level-7 victory, physical-key test or full-screen VGA/HUD comparison. The same
established seeder advances through controlled objective writes to level 7.
At the case boundary the observer restores the observed map, player, actor,
link and visual state, disables spawners, sets player reserves/energy to 99/100
and seeds clock/RNG to 100/0x12345678. It observes the head's idle approach,
holds movement idle and injects the fire latch after rendering. There is no
per-tick restoration of actors, health, maps, RNG or timers. This new warmup
differs from the earlier capture; their first 800 updates are not identical.

## Original Evidence

The pinned original executable SHA256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The observer is a versioned AST derivative of the unchanged
`tools/capture_original_boss_defeat.py`: only its checkout root, sample count,
view schedule, self-check summary and provenance label change. The evidence
checker restores these five parameters and compares the AST to the archived
template. The 48 instruction-window checks and eight lifecycle/render hooks
remain the existing original observation path.

The capture records 133 make/break pairs, 266 ordered key records, 96 consumed
small bombs, ten fire-latch reentries, 600 dying updates and 140 reentry-wait
updates. Ammo decreases from 200 to 104 and player reserves from 99 to 89.
Shared fallback increments match all 140 wait updates; no level restart occurs.
The mapped normalized fire byte is observed after the original prepass, not
forced. Fire-latch injection does not exercise physical SDL keyboard ownership.

At sample 1,713 the head is still kind 30, life byte 0, HP byte 1. At sample
1,714 it becomes kind 14 with timer 60 and HP byte 255. All six linked segments
convert in the same update, with observed timers 43, 44, 41, 41, 40 and 43.
Their motion, half-rate fuse countdowns, RNG changes, explosion effects and map
deltas continue without another state seed. At sample 1,833 no converted boss
bomb remains. The last sample is 3,199, well beyond the defeat and cleanup.

The original wrapper independently verifies restoration of all eight hooks.
Its owned DOSBox process terminates with code 0 after established controlled
cleanup; this does not prove that the game naturally exited. Exact source
archives and initial hashes for all fourteen copied assets are retained.

## Production Replay

```sh
env SDL_AUDIODRIVER=dummy SDL_VIDEODRIVER=dummy \
  ./build/lezac_cpp --debug-boss-extended-combat-original TRACE OUTPUT
```

The diagnostic seeds only the case boundary, applies the observed key events
at their captured after-render boundaries, and calls production
`updateWithControls` for every update. It compares player state, inventory,
fire timing, boss/link motion and animation, ordinary bombs, transient effects,
flames, RNG, map changes and captured views. The production defeat and final
boss-bomb cleanup are explicitly required and reported:

```text
samples=3200 actor_states=12615 link_states=10284 effect_states=9465
bomb_states=3721 shots=96 reentries=10 key_events=266
views=15 compared_pixels=711360 different_pixels=0
player_dying_states=600 player_waiting_states=140 shared_counter_steps=140
defeat_sample=1714 cleanup_sample=1833
head_health_modified=0 seeded_bomb=0 physical_keyboard=0 whole_game_parity=0
```

The first diagnostic attempt stopped at sample 1,793 on a redundant assertion
that effect visual slots equal actor indices plus two. The original record
at actor index 5 has visual slot 3: converted boss actors retain their visual
order when replaced by effects. The existing sorted visual-slot comparison
already validates every entry, so the diagnostic now uses that comparison for
active combat, as it already did for the seeded-bomb probes. The complete
transient state comparison remains required. No production gameplay rule was
changed. The failed source, binary hash and outcome remain failed evidence.

Views are sampled at 0, 1, 15, 16, 20, 39, 59, 99, 199, 399, 599, 799, 1599,
2399 and 3199. The comparison covers 312x152 indexed playfields using the
existing normalized palette, not the actual VGA DAC or HUD. Three bound
original/C++ preview pairs cover combat, post-defeat destruction and the end.
Unused stale link bookkeeping after defeat is still not a replay claim.

## Sealed Fixture

`tests/fixtures/boss_extended_combat_original_level7.txt.gz`:

```text
packed SHA256 e8083b198c9039fd537f8a423575e8846ccd6cb9697b1d90bc6e5dfb0ce259d7
trace SHA256  1e5425c095ac833b577647d63b6aebd3a8803fbc6eef348ac7903f951ee27ce9
```

The evidence directory `docs/recovery/evidence/boss_extended_combat_20261001/`
contains unchanged capture-time metadata, ten exact executed source archives,
the archived passing C++ source/outcome, failed diagnostic evidence, bound
preview PPMs/PNGs and exact evidence producers. `original.json` still says
`production_replay=false`; the later passing proof is separate in `cpp.json`.

The exact executed observer uses Python 3.12 f-string grammar. A separately
hash-bound, data-only AST representation lets older Python versions inspect
the same tree without rewriting or executing the archived code. Python 3.12+
also reparses the exact source and compares it to that record. Both native
Python 3.10 and Linux Python 3.12 validate the sealed evidence.

`boss_extended_combat_evidence` validates hashes, scope, source parameters,
capture/replay outcomes, continuity, defeat/cleanup and indexed preview binds.
`boss_extended_combat_original` tests LF/CRLF production replays and rejects
sixteen malformed variants, including reduced starting health, changed fatal
conversion/timer, wrong retained visual slot, wrong effect timer, RNG,
post-defeat map, inventory and incomplete coverage. The original 800-update
fixture, capture helper and its nineteen mutation checks are unchanged.

## Remaining Work

Natural campaign and full level-7 completion, normal reserves and inventory,
movement-based combat, two-player interaction, physical keyboard timing,
mixed flame masses and actual VGA/HUD fidelity remain separate requirements.
`port_functionally_complete=0` and `original_fidelity_claim=0` remain unchanged.
