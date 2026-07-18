# Weapon-Switch Sound Recovery and Process-Memory Evidence (2026-07-16)

## Result

The sound request at `1000:6844` is the one- and two-player weapon-switch cue.
The original counts update ticks while both horizontal controls are held. On a
later update where the chord is no longer held, a count below `5` is discarded;
a count of at least `5` requests cursor `0x0024` at priority `2`, selects the
next nonempty bomb slot, and resets the per-player counter.

The recovered C++ diagnostic is `--debug-weapon-switch-sound`; its success line
begins `weapon_switch_sound=ok` and checks the short-chord, held, release,
selection, sound-latch, and pump states.

## Static provenance

- Player setup points `DS:79BC` at `DS:79B0` for player 1 (`1000:61CC`) or
  `DS:79B1` for player 2 (`1000:6239`).
- `1000:6813..6824` adds the horizontal input flags at `DS:1B83` and
  `DS:1B84` and compares the sum with `2`.
- While both are set, `1000:6826..6837` clears the copied flags, increments the
  selected byte counter, and skips the rest of the actor update.
- On release, `1000:683A..6842` compares the counter with `5`. Counts below the
  threshold branch directly to the reset at `1000:68BD`.
- The accepted path at `1000:6844` writes `0x0024` to `DS:2074`, writes `2` to
  `DS:799F`, and calls the priority latch at `1000:165A`.
- `1000:6852..68BC` advances the player's selected bomb index modulo four and
  searches for a nonempty inventory slot. `1000:68BD..68C4` resets the counter.

`tools/check_sound_weapon_switch_context.py` locks these bytes, branch targets,
player counter pointers, the C++ mapping, tests, and documentation together.

## Runtime captures

All runs used an explicit `Ubuntu` WSL distribution, a temporary DOSBox child,
runtime-only `EB FE` instrumentation, `runtime_cs=01ED`, and `runtime_ds=0C8F`.
The focused wrapper command was equivalent to:

```powershell
wsl.exe -d Ubuntu -e env `
  LEZAC_SOUND_CALLSITE_APPROVE_PROCMEM=1 `
  LEZAC_SOUND_CALLSITE_APPROVE_RUNTIME_INSTRUMENTATION=1 `
  LEZAC_SOUND_CALLSITE_ROUTE_STEPS=z+x:1.50 `
  LEZAC_SOUND_CALLSITE_RUNTIME_FREEZE_BEFORE_ROUTE=1 `
  bash '/mnt/c/Users/andrz/OneDrive/backup/Moje dokumenty/Gry/LEZAC/tools/capture_original_sound_callsite_procmem.sh' `
  /tmp/lezac-sound-weapon-switch-live-20260716-b `
  '/mnt/c/Users/andrz/OneDrive/backup/Moje dokumenty/Gry/LEZAC' `
  actor_update_runtime_cursor_0024_sound
```

Three focused observations narrowed and then confirmed the route:

| Run | Patch | Route | Result |
| --- | --- | --- | --- |
| `...-a` | `01ED:6844` | `z+x:0.50` | Patch loaded, no freeze; blocked as `no_observed_freeze` |
| `...-b` | `01ED:6844` | `z+x:1.50` | Natural callsite freeze observed |
| `...-c` | `01ED:684F` | `z+x:1.50` | Freeze observed after request writes and before the latch call |

At the run-C frozen checkpoint, process memory contained:

```text
runtime_hold_counter=0x14
runtime_pending_cursor=0x0024
runtime_pending_priority=2
DS:2070 = b4 9d 00 00 24 00 00 00 00 00 20 66 9e 20 c7 00
DS:7990 = 00 00 00 00 00 00 00 00 00 00 00 00 00 00 0b 02
DS:79B0 = 14 00 00 32 6c 00 00 01 01 00 00 00 b0 79 8f 0c
```

The `0x14` counter records 20 held updates. The cursor and priority bytes were
already present before execution of the patched call instruction at
`1000:684F`, independently confirming the static request operands.

## Frame inspection

Run C rendered the original menu, the level-1 preparation screen, and active
gameplay. Its gameplay frame remained byte-identical after the route, bomb tap,
sampling, and tail check, which is the expected visual signature of the
instrumented freeze.

| Frame | SHA-256 | Inspection |
| --- | --- | --- |
| `000_menu.png` | `7bcf755654e3922337433e630f5951b316aa786b25714ec2eb1a0ffa61d6cc19` | Original menu visible |
| `010_level_start.png` | `057cf113551f3a3ca370a2cce431ac2bae42aeee084468cb27f10bc66ccd34e6` | Level-1 preparation screen visible |
| `020_route_position.png` | `6765e03f289fcdee5d985f703270007b71f043ebae7157a7b155fc9e68224ada` | Active gameplay frozen on chord release |
| `030_bomb_key.png` | `6765e03f289fcdee5d985f703270007b71f043ebae7157a7b155fc9e68224ada` | Identical after ignored bomb input |
| `090_after_sampling.png` | `6765e03f289fcdee5d985f703270007b71f043ebae7157a7b155fc9e68224ada` | Identical after sampling |
| `091_tail_freeze_check.png` | `6765e03f289fcdee5d985f703270007b71f043ebae7157a7b155fc9e68224ada` | Identical tail freeze confirmation |

The inspected PNGs are retained under the ignored build directory
`build-win-codex-vs3/sound-weapon-switch-live-20260716-c`. No repository oracle
fixture was promoted: run B freezes before the request writes, while run C is a
focused latch-point reachability capture rather than the normalized
sound-callsite fixture format.
