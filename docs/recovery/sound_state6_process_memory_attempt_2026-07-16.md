# State-6 Sound Callsite and Process-Memory Attempt (2026-07-16)

## Scope and evidence class

This pass investigated the immediate sound request at `1000:5E81` without
promoting a natural gameplay or visual claim. The process-memory run used a
temporary DOSBox child, patched the child code at runtime, and kept
`visual_claim=0`. Its candidate remains blocked. Static reconstruction then
identified the actor-mode gate and every shipped constructor source that can
feed it.

## Host and command

The Windows-side generic WSL probe reported
`wsl_bash_reason=no_default_distro`. `wsl.exe -l -q` still listed `Ubuntu`, and
an explicit named-distro probe found `bash`, `python3`, `dosbox`,
`dosbox-debug`, `xvfb-run`, `xdotool`, `pgrep`, `zutty`, `script`, and `Xvfb`.
The live attempt therefore used the named distro directly:

```powershell
wsl.exe -d Ubuntu -e env `
  LEZAC_SOUND_CALLSITE_APPROVE_PROCMEM=1 `
  LEZAC_SOUND_CALLSITE_APPROVE_RUNTIME_INSTRUMENTATION=1 `
  LEZAC_SOUND_CALLSITE_ROUTE_STEPS=x:2.00 `
  LEZAC_SOUND_CALLSITE_RUNTIME_FREEZE_BEFORE_ROUTE=1 `
  bash '/mnt/c/Users/andrz/OneDrive/backup/Moje dokumenty/Gry/LEZAC/tools/capture_original_sound_callsite_procmem.sh' `
  /tmp/lezac-sound-contact-live-20260716-a `
  '/mnt/c/Users/andrz/OneDrive/backup/Moje dokumenty/Gry/LEZAC' `
  contact_scanner_runtime_sound
```

The wrapper's in-distro environment preflight passed. The run copy was under
`/tmp/lezac-sound-contact-live-20260716-a/procmem/run`. The underlying field
`instrumented_temp_copy=0` describes the patch method: the patch was applied to
the runtime child rather than to the copied executable. The candidate itself
correctly records `temp_copy=1` and `instrumented_runtime_child_memory=1`.

## Runtime result

The wrapper resolved `runtime_cs=01ED`, `runtime_ds=0C8F`, and target
`01ED:5E81`. It read original bytes `c706`, wrote loop bytes `ebfe`, and read
back `ebfe74206900c606`, so `freeze_runtime_patch_applied=1`. The route never
executed the patched address:

```text
instrumented_freeze_observed=0
promotion_status=blocked
promotion_blocker=no_observed_freeze
```

No `sound_callsite_oracle_original*.txt` fixture was created or promoted.

## Frame inspection

The six PNGs were copied to the ignored build tree for inspection. The menu,
level-1 intro, active level route, bomb/effect state, and post-sampling gameplay
all rendered. The tail frame was captured during teardown and is not used as
behavior evidence.

| Frame | SHA-256 | Inspection |
| --- | --- | --- |
| `000_menu.png` | `7bcf755654e3922337433e630f5951b316aa786b25714ec2eb1a0ffa61d6cc19` | Original menu visible |
| `010_level_start.png` | `c358f8c2b94bc40f8aecd36db963bef58893896489031287d66a09ca5986bd4f` | Level-1 intro visible |
| `020_route_position.png` | `b4d9d00415267bc55bad28dfa02af17c6fe3a39ed2e318c4f37a2dd190269afb` | Active gameplay after rightward route |
| `030_bomb_key.png` | `e3d09ca152dd347973091caeb146a080fde83f2b032f17533bcda5aceade6529` | Bomb/effect route visible |
| `090_after_sampling.png` | `596a0440544358fb480e9ee091b1e8202c459e6a53cde4ac4d83dda4be1a797b` | Gameplay continued; no freeze |
| `091_tail_freeze_check.png` | `cc5fecea44ea519713ffad58f555df30d5991cf7041cab2edead59e66e6f0ead` | Teardown frame; excluded from claims |

The route-state manifest also kept player modes at `0` and `1`; it supplied no
actor mode `6`.

## Static reconstruction

`tools/check_sound_state6_context.py` verifies these facts directly against the
MZ load image and raw/exported level data:

- `1000:615D` loads actor byte `+0x15` into local `[bp-31h]`.
- `1000:654E` compares that value with `6`. Only equality executes
  `push bp; call 1000:5CB0` at `1000:6555`.
- Inside the scanner, `1000:5E59` divides `DS:78C2` by `29` and rejects a
  nonzero remainder. It then calls the random helper with bound `100`, requires
  the result to exceed `70`, and rejects odd `DS:78C2` values. The deterministic
  tick predicates therefore coincide every `lcm(29, 2) = 58` ticks.
- The accepted path writes cursor `0x0069` to `DS:2074`, priority `4` to
  `DS:799F`, and calls the latch at `1000:165A`.
- Actor construction at `1000:2F9F` stores its first stack byte into actor
  `+0x15`. Its six immediate callers supply mode `5` five times and mode `2`
  once. The seventh caller at `1000:7B28` copies spawner byte `+0x1A`.
- Raw `LIVELS.SCH` and `src/LIVELS.SCH.json` agree on 15 shipped spawners:
  nine use mode `3` and six use mode `4`. None uses mode `6`.
- All direct immediate writes to actor `+0x15` use only `0`, `1`, `2`, or `5`;
  the constructor is the sole direct dynamic store found in the load image.

The narrow static conclusion is that mode 6 is a dormant engine path for the
shipped level data. This is recorded as
`state6_capture_blocker=shipped_actor_modes_exclude_6`. It does not claim that
an intentionally instrumented seed could not execute the branch.

## Queue decision

The natural runtime queue now reports
`first_target=actor_update_runtime_cursor_0024_sound` and
`route_classes=natural:3,runtime_seeded:1`. The `1000:5E81` target remains
available as `seeded_only`, with blocker `shipped_actor_modes_exclude_6`, but it
is no longer the default natural route sweep. A future mode-6 run must label the
actor-byte mutation as runtime-seeded evidence and must not be promoted as
natural shipped gameplay.
