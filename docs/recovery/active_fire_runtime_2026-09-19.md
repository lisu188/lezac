# Original Active Fire

## Scope

64 seeded original level-1 fire-block probes now replay through the production
fire decision and constructor. The port also samples fire in the governed
player update, not during SDL event dispatch. This is not whole-game parity,
a natural two-player keyboard recording, or a full-health boss victory.

Pinned fixture: `tests/fixtures/active_fire_original_level1.txt`.
Normalized LF SHA256:
`8808b7d195fd55523716cb7f83d2f0a167bb2caaa85aa4c0fb151b1cd231deba`.
Original EXE SHA256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
An independent recapture produced the same complete fixture hash.

## Observation

The helper verifies the executable hash, instruction windows and an unused
CS:F400..F611 arena, then installs two polling trampolines in an owned DOSBox
child. Registers and flags are preserved and displaced instructions replayed.
Only temporary copies are launched, under private Xvfb with
`SDL_AUDIODRIVER=dummy` inherited by every child.

```sh
env SDL_AUDIODRIVER=dummy PYTHONUNBUFFERED=1 \
  python3 tools/capture_original_active_fire.py \
  --run-dir /tmp/lezac-active-fire-verify-20260919 \
  --out build-codex-tmp/active-fire-verify-original-20260919.txt \
  --approve-procmem --approve-runtime-instrumentation
```

| Boundary | Ghidra Anchor | Runtime CS:Offset | EXE File Offset |
| --- | --- | --- | --- |
| Fire test | 1000:6BD5 | 01A2:6BD5 | 7345 |
| After fire, before terrain scan | 1000:6CB3 | 01A2:6CB3 | 7423 |

Recorded registers are CS 01A2, DS/ES 0C44, SS 18B3, SP 3FA2 and BP 3FEE.
SP is recorded after the trampoline's PUSHF/PUSHA. As in earlier captures,
the process-memory helper uses base-relative CS 01ED / DS 0C8F.

Each probe seeds normalized fire DS:1B85, both hardware latches DS:1B7B/1B80,
player identity BP-1D, selected weapon DS:1B73+player, inventory
DS:1B68+4*player, pool count DS:208D, and launch locals BP-2C/BP-2E/BP-0C/BP-0E.
The constructor result word DS:2072 begins at 5A5A, making a skipped call
distinct from failure (0000) and success (0001).

For each player and all four weapons the cases are: ordinary shot, final
round, empty selected weapon with other ammunition available, pool 30,
pool 29, no own fire, and another bomb already in the same cell. Four extra
signed-velocity/clamping cases per player complete the 64 observations.
The P2 cases deliberately substitute identity 2 in the P1 update stack;
they do not prove natural P1/P2 actor ordering. Pool-only probes seed the
count, not a complete 30-actor simulation. The same-cell probe does seed
an existing bomb actor and its matching visual at (104,168).

The helper restores probe memory before allowing the rest of the player
update to execute, and restores both hooks on exit. Its saved PNG shows
restored level-1 gameplay, not any individual seeded constructor boundary.

## Recovered Rules

- Empty selected ammunition skips the constructor, preserves both latches,
  and leaves the selected weapon unchanged. Other available types are not
  automatically selected here.
- A constructor attempt consumes both fire latches, including a pool-full
  rejection. Rejection does not consume ammunition.
- Success consumes one round but leaves an exhausted weapon selected.
- An existing bomb in the same cell does not prevent construction.
- Launch velocity uses signed truncation of VX*3/2, VY-500, and the shared
  constructor's +/-2047 clamp. Fractional accumulators start at zero.
- Fire occurs after movement/posture/jump locals are updated and before
  terrain damage and integration. New bombs begin updating next frame.

The keyboard ISR reads port 60 at 1000:10A1. It writes one for N make 31
at 10BD and Insert make 52 at 10DD; break B1/D2 writes zero at 110F/112F.
There is no repeated-make exclusion. SDL repeated gameplay fire keydowns
therefore relatch fire too. Host typematic timing is not claimed to equal
the DOS keyboard's timing; held-before-death live input still needs capture.

## Validation

`--debug-active-fire-original` checks the 64 cases' ammunition, selection,
pool count, latches, constructor outcome, bomb identity, fuse seed, launch
coordinates/velocities/fractions, owner and sprite dimensions. Original
unused/stale actor fields and descriptor pointers are retained in the pinned
evidence, not presented as a complete C++ byte-layout comparison.

Separate production event/tick checks cover deferred fire, simultaneous
P1/P2 latch consumption, empty P1 allowing P2 to fire, retained empty-ammo
input, key release before a tick, repeated makes, jump/right throw velocity,
drop-local Y, no update on the birth frame and first countdown next frame.
The fixture guard checks LF/CRLF plus 103 mutations, with silent children.

Existing input-based smoke, route and frame tests now advance a real tick
after a fire event. This shifts the deliberately seeded monster reward
routes' frame parity: two observed corpse intervals become 49 ticks instead
of 50; the super-bomb route becomes 50 instead of 49. The production corpse
timer itself was not changed, nor were original corpse/fuse/motion fixtures.

The existing independent level-7 fire-reentry trace still matches 140 states,
16 normalized 312x152 playfields and 758,784 pixels with zero differences.
Fresh replay output: `build-codex-tmp/active-fire-boss-cpp/`.
The inspected checkpoint pair is original `boss-fire-fresh-original-101.png`
and updated `active-fire-boss-cpp-101.png`, enlarged 3x nearest-neighbor.
This is a seeded boss encounter, not a new natural victory or full-VGA claim.

Further work includes continuous original keyboard routes with simultaneous
inputs and typematic behavior, held-before-death interaction, natural boss
victory/campaign progression, and the remaining renderer/gameplay gaps.

The next input audit should also verify control ownership in live two-player
play. Static normalization at 1000:6175 copies Z/X/M/N/C hardware bytes for
behavior 0 (player identity 1), while 1000:61DE copies arrow/Insert bytes for
behavior 1. The current C++ two-player movement adapter assigns arrows to P1
and Z/X/M/C to P2. The new fire-block probes do not cover that adapter.
