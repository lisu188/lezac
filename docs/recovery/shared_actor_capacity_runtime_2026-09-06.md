# Shared Actor Capacity

## Scope And Result

Two original DOSBox captures cover 16 seeded allocation boundaries: all four
weapons with 0/29/30 existing effects, three corresponding monster-spawner
cases, and a full-pool case whose first effect expires later that frame.
There are ten successful allocations and six rejections. The C++ production
paths now reproduce the captured counts, inventory, RNG, spawner budget and
cooldown, unchanged existing actor/visual records, and mapped fields and
sprite descriptors of newly constructed bombs and monsters.

The production spawner pass now runs before state-2 and non-player updates,
as in the original. A full pool rejects spawning before an effect frees a
slot later in the same frame. This closes a concrete ordering defect, not
the wider shared actor dispatch/compaction problem.

These are seeded level-1 boundary probes. They do not establish natural-route,
two-player, audio-timing, or whole-game visual parity.

## Original Rules

- Main CS:2F9F (file 0x370f) is the shared non-player constructor. The byte
  DS:208D counts a maximum of 30 records at DS:1BAE + slot * 38. Slot zero is
  outside this non-player allocation. Main CS:2FAD checks the limit; failure
  writes word DS:2072 = 0. Success increments the count, assigns the next
  visual index from DS:C496, and calls the original visual constructor.
- Bomb placement calls that helper at CS:6C5B and tests DS:2072 at CS:6C5E.
  Only success decrements inventory and sets the player's fire flag. The
  captured P1 inventory is DS:1B6C..1B6F, selection DS:1B74, fire DS:1B76.
  In all four full-pool cases the inventory remains 9/9/9/9, the fire flag
  remains zero, and both actor and visual counts remain 30 and 32.
- The spawner loop is CS:7A6B..7C3D. Its countdown decrements before gates;
  a ready enabled spawner reloads before calling the shared constructor at
  CS:7B28. Failure preserves that reload but does not spend budget/live
  allowance or consume the four AI/HP random draws. These captures use
  countdown 1, reload 90, budget 7, allowance 2, and RNG seed 0x12345678.
  Success yields budget 6, allowance 1, RNG 0xf25cf394. Failure leaves
  budget/allowance/RNG unchanged, with countdown 90 in both cases.
- The spawner pass precedes CS:7C89 state-2 handling and the dynamic actor
  loop at CS:7EC5..7EEA. In `spawner_pool30_expiring`, frame 91 starts with
  30 effects, the first with timer 1. Allocation fails at 30. The later
  odd-frame effect update retires that actor; the next rendered checkpoint
  has 29 actors. C++ also exercises this case through `updateWithControls`,
  not only a direct spawner-helper call.

## Capture Provenance

Executable SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

The temporary copies run under private Xvfb with the existing level seeder,
DOSBox surface output, frameskip zero, no scaler and fixed 6000 CPU cycles.
Menu key `1` and startup/intro/level-start/results waits 10/8/5/10 seconds are
used. No executable or shipped asset is patched on disk.

`tools/capture_original_shared_capacity.py` validates eight instruction
windows and saves/restores FLAGS and general registers in polling
trampolines. Bomb hooks are CS:6C0A and CS:6CA9; spawner hooks are CS:7A6B
and CS:7C3D. Both modes capture a screenshot at the next CS:7A57 render
checkpoint. Bomb cases use real N-key down/up input to enter the original
placement path, then explicitly seed weapon, inventory and pool occupancy.
They do not test upstream input gates against an already full pool.

Actual captured registers are CS=01a2, DS=0c44 and SS=18b3. Bomb saved
SP/BP are 3fa2/3fee; spawner saved SP/BP are 3fe4/3ffe. ES changes from
a000 to DS during the spawner pass. Tool constants 01ed/0c8f describe
addresses relative to the seeder's adjusted host-memory base, not the
actual segment registers. The segment difference remains 0x0aa2. The first
attempt incorrectly required the nominal constants as actual registers;
both attempts failed that guard before producing fixtures. The corrected
capture translates stack addresses using the sampled CS/SS pair.

Each existing filler is an explicitly seeded behavior-5 effect, with no
animation or motion, sprite descriptor 80 and timer 240 (except the one
timer-1 expiry probe). Their grid positions make occupancy visible. P1
launch state is (104,168), velocity zero. Original spawner data is retained
apart from the declared gate/countdown seeds. Pool count, visual count,
RNG, inventory, selection, fire flag, registers, all spawner bytes and all
live 38-byte actors plus 8-byte visuals are recorded before and after.

Commands, after copying shipped assets into the named temporary directory:

```sh
python3 tools/capture_original_shared_capacity.py --mode bomb \
  --run-dir /tmp/lezac-cap-bomb2 \
  --out build-codex-tmp/shared-capacity-bomb-v2.txt \
  --approve-procmem --approve-runtime-instrumentation
python3 tools/capture_original_shared_capacity.py --mode spawner \
  --run-dir /tmp/lezac-cap-spawner3 \
  --out build-codex-tmp/shared-capacity-spawner-v3.txt \
  --approve-procmem --approve-runtime-instrumentation
```

Promoted unchanged captures:

- `tests/fixtures/shared_capacity_bomb_original.txt`, SHA-256
  `ff86eb9de5bb95355e18e5ead64aa359a155d0a2f3ed5b66e5edb1019efefe27`.
- `tests/fixtures/shared_capacity_spawner_original.txt`, SHA-256
  `91a763af3b4a56f3bc88bd651b1ea576be403c6a9b3f956ff4f04def1294b7f9`.

## Validation And Frames

The pre-fix bomb and spawner replays each fail at their first 30-slot case
with `actor count mismatch`. The corrected production paths pass 12 bomb
and four spawner cases. The expiry probe also checks the production frame
order, preserving budget, allowance and RNG while retiring one effect.
The existing 466-test suite passes in 106.38 seconds; log:
`build-codex-tmp/shared-capacity-baseline-tests.log`.

Five new CTests include both fixture replays, both capture self-check modes,
and a guard that pins the captures, accepts LF/CRLF, rejects two truncations
and 64 deliberate state/record/coverage mutations, and checks that replay
does not create unrequested PPM files.
The expanded 471-test suite passes in 104.91 seconds, including interactive
Xvfb checks; log: `build-codex-tmp/shared-capacity-full-tests.log`.

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-shared-capacity-original tests/fixtures/shared_capacity_bomb_original.txt \
  build-codex-tmp/shared-capacity-bomb-cpp-v1
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-shared-capacity-original tests/fixtures/shared_capacity_spawner_original.txt \
  build-codex-tmp/shared-capacity-spawner-cpp-v1
```

Original screenshots are `shared-capacity-bomb-v2_<case>.png` and
`shared-capacity-spawner-v3_<case>.png` in `build-codex-tmp`. C++ writes
constructor-state PPMs and manifests with count, frame, RNG and frame hash.
The expiry case additionally exports its post-update 29-actor checkpoint.
The paired full-pool bomb images were inspected and shown to the user.
The original image is the next rendered frame; C++ is the immediate
constructor checkpoint. Background, palette and HUD differences remain
visible. No pixel-parity claim is made for these screenshots.

## Remaining Work

The port still groups most actor updates by C++ type rather than original
slot order. Shared deletion/compaction, same-pass appended entries, mixed
reward/corpse transitions, launch-marker allocation failure and bonus-rain
allocation require further original probes. The port's same-tile bomb veto
also remains unverified; this capture seeds occupancy only after upstream
input gates. In-place corpse-to-reward/fade conversions must not be treated
as new allocations. End-to-end natural routes and two-player interactions
remain open. The goal is not functionally complete.
