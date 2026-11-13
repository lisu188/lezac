# Controlled Full-health Boss Combat

## Evidence Scope

The original level-7 head starts with its observed life byte 1 and HP byte 10.
Unlike the earlier fatal-bomb, nonfatal-hit and largest-bomb probes, this capture
does not reduce either byte or plant a bomb next to the head. It drives ordinary
small-bomb construction through the original fire latch and observes 800
consecutive production updates, including three player deaths and fire-latch
returns to active play.

This is still a controlled scene, not a natural campaign or full-health victory.
The established seeder advances to level 7 through controlled objective writes.
At the case boundary the observer restores the observed map, player, actors,
links and visual table, clears old queues, disables spawners, sets player reserves
to 99 and energy to 100, and sets the clock/RNG to 100/0x12345678. The head's
position comes from a naturally approaching idle warmup, not a forced teleport.
During the run movement is held idle and fire is injected into DS:1B7B after
rendering; no per-tick actor, map, health, timer or RNG restoration is used.

## Original Observation

`tools/capture_original_boss_defeat.py --active-combat` uses the established
eight lifecycle/render hooks, including the measured relocated introduction
call, and checks 48 original instruction windows before capturing. The
executable is the pinned shipped `LEZAC.EXE`:

```text
7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec
```

Fire is made after sample 15 for update 16, released after sample 16, and repeated
every 24 updates. There are 33 make/break pairs and 66 ordered key records. Each
record includes the prior latch value and an explicit after-render boundary.
The observer preserves the original prepass's normalized fire byte DS:1B85.
It does not force the normalized byte or claim physical keyboard input.

The canonical second capture records 22 consumed small bombs, three input-driven
reentries, 180 dying states, 48 reentry-wait states and 48 shared fallback
increments. Player reserves decrease from 99 to 96. Small-bomb ammo decreases
from 200 to 178; weapon selection stays 1 for both players. The boss is still
alive at sample 799, with life byte 0 and HP byte 158. Those wrapped bytes are
observations, not a victory indication.

The capture wrapper independently verifies restoration of all eight hooks.
Its owned DOSBox process has a terminal return code after the established
controlled cleanup. That proves cleanup, not a natural game exit. Both original
and C++ processes use dummy audio and private/dummy video.

## Production Replay

The diagnostic `--debug-boss-active-combat-original TRACE [OUTPUT]` consumes
case-boundary observations once, applies key records at their captured
boundaries, and runs the production `updateWithControls` path continuously.
It compares player motion, animation, energy, lives, death/wait state, inventory,
weapon selection and fire latches, as well as boss/link states, ordinary bombs,
effects, flames, RNG and map changes. A post-prepass observer checks normalized
fire timing. Reduced starting boss health is rejected at the case boundary.

Canonical replay totals:

```text
samples=800 actor_states=5600 link_states=4800 effect_states=1843
bomb_states=835 shots=22 reentries=3 key_events=66
views=12 compared_pixels=569088 different_pixels=0
head_health_modified=0 seeded_bomb=0 physical_keyboard=0 whole_game_parity=0
```

The view samples are 0, 1, 15, 16, 20, 39, 59, 99, 199, 399, 599 and 799.
They compare 312x152 indexed playfields, rendered with the existing normalized
palette. This is not actual VGA DAC, complete-screen or HUD fidelity.

A separate first capture also replays all 800 updates and 12 views exactly.
It has 23 consumed bombs, three reentries, 874 bomb states and 1918 effect
states, reflecting a different observed warmup. Its raw evidence is retained
in RAM, but its original launcher was replaced by the helper's Xvfb re-exec,
leaving incomplete wrapper metadata. It is not the sealed canonical outcome.
The two captures together cover 1600 updates and 1138176 compared pixels;
only the second fixture carries independently verified hook restoration.

## Sealed Fixture And Checks

The portable fixture is
`tests/fixtures/boss_active_combat_original_level7.txt.gz`:

```text
packed SHA256 73bb51a5ce63d1d18fe98349b32fad681d24347d220a3b30ace63a06126de898
trace SHA256  887819b3b5d40c509bf749f6bd69ac98758a23b6b5eff425af26ee645d0ea3a3
```

`docs/recovery/evidence/boss_active_combat_20261001/` contains the original
capture-time metadata, nine exact executed source archives, the exact archived
C++ replay source/outcome, the producer, and a bound original/C++ sample-799
preview pair. The original metadata's `production_replay=false` is deliberately
unchanged: later replay proof lives separately in `cpp.json`. The archived C++
source records the sealed run, before the final case-boundary rejection check;
the live fixture test exercises the current production build independently.

`tools/check_boss_active_combat_evidence.py` verifies hashes, scope, captured
outcome, normalized current capture sources, input/lifecycle continuity and
indexed views. It independently binds the preview PPMs to the last indexed view.
The optional `--exe` check tests LF and CRLF and rejects 19 malformed variants,
including false provenance, missing completion, changed clock/input ownership,
key timing, ammo, latch, normalized fire, RNG, weapon selection, missing or
duplicate key events, and reduced initial boss life/HP. The last two must fail
before the first update, not incidentally at a later state comparison.

CTest adds `boss_active_combat_capture_contract`, `boss_active_combat_evidence`
and `boss_active_combat_original`. Existing boss modes and their fixtures keep
their established formats and validation. No production gameplay rule was
changed for this capture/replay extension.

## Unpromoted Diagnostics And Remaining Work

An earlier full-health experiment stopped with a stage-2 timeout after 540
samples. It used direct normalized-fire writes and lacked the complete lifecycle
hooks. Its partial trace and exact source archives remain failed evidence;
the timeout's exact original stopping point was not established, and hook
restoration was not independently verified. It is not a passing fixture.

Still open: naturally reaching and defeating the full-health boss, complete
campaign comparison, natural movement and inventory routes, two-player combat,
mixed flame masses, authentic physical-key timing, and actual VGA/HUD parity.
These controlled reentries do not close those wider requirements.
`port_functionally_complete=0` and `original_fidelity_claim=0` remain unchanged.
