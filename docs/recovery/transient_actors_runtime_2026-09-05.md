# Pickup Indicators, Fracture Smoke and Camera Shake

Branch: `codex/recover-pickup-transient-actors`, based on PR #208.
Scope: focused behavior-5 actors and shake RNG, not full-game fidelity.

## Original Capture

All runs used the private asset copy
`/tmp/lezac-player-posture-20260905-4jbVwK`. The launcher creates a private
Xvfb/DOSBox child and terminates it after capture. The original executable
on disk was not patched. SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

The guarded, in-memory checkpoints replay displaced instructions. The
natural route injects normalized controls, but does not seed player motion,
animation, map, collapse records or actors in the original. C++ initializes
the player and RNG once, then compares continuous production updates.

```sh
python3 tools/capture_original_player_walk.py --animation --world --transients \
  --route platform_collapse \
  --run-dir /tmp/lezac-player-posture-20260905-4jbVwK \
  --out /tmp/lezac-player-posture-20260905-4jbVwK/pickup_transients_shake.txt \
  --startup-seconds 10 --intro-seconds 8 --level-start-seconds 5 \
  --approve-procmem --approve-runtime-instrumentation

python3 tools/capture_original_collapse_steps.py \
  --run-dir /tmp/lezac-player-posture-20260905-4jbVwK \
  --out /tmp/lezac-player-posture-20260905-4jbVwK/collapse_transients_v2.txt \
  --actor-out /tmp/lezac-player-posture-20260905-4jbVwK/fracture_actor_v2.txt \
  --approve-procmem --approve-runtime-instrumentation
```

Both commands completed. An earlier natural capture, `pickup_transients.txt`,
also completed and first exposed missing shake RNG at checkpoint 46. The
second capture adds the actual shake words. The collapse tool first runs its
27 existing seeded probes, then seeds one blocked-down fracture and records
21 consecutive actor states. Harmless collapse records keep the hooks
reachable and debris is disabled between ticks; the captured actor is never
reseeded. This is isolated lifecycle evidence, not a natural fracture route.

The promoted pickup trace starts at frame 90. Its saved registers are
CS=01A2, DS=0C44, ES=3EA9, SS=18B3, saved-SP=3FA2, BP=3FEE.
Hooks are at Ghidra 1000:6064, 6813, 6B55 and 741E, translated to runtime
01A2 at the same offsets. New instruction guards include 65A2 (behavior 5),
2FAD (shared capacity), 6D88 (pickup capacity) and 806A (shake gate).
Actor records are 38 bytes at DS:1BAE + slot*38; visuals are eight bytes at
DS:C21E + actor[1]*8. DS:208D/208E hold shared/pickup counts.

## Recovered Rules

- Allocator 1000:2F9F limits non-player actors to 30. Pickup caller 6D88
  separately limits kind 0A to 14. It draws `Random(200)` after the pickup
  count gate, even if the shared allocator then fails.
- Pickups scan the cached four-cell interior clockwise. Indicator positions
  use pre-integration player X/Y plus -2 or +10 for each cell axis. Initial
  VY is `-40-Random(200)`, VX and fractions are zero, timer is 12.
- DS:001A selects one-based sprites
  `80,81,82,83,84,85,86,87,88,89,90,86` for tiles 67..72. The allocator's
  hotspot byte is `16-initial_sprite_height`. Pickup animation is disabled.
- Behavior 5 at 65A2..65D7 advances animation first, subtracts `frame&1`
  from its timer byte, deletes at zero, and otherwise integrates Y then X
  without collision or gravity. Deletion decrements the pickup count for
  kind 0A. The non-player pass at 7ECB..7EE8 precedes player calls at 7F59,
  so newly allocated pickup/fracture actors first update on the next frame.
- Fracture 558C always draws a cell backward from the group's bottom-right
  using `Random(last_column-first_column+1)`. Kind 0B is placed at that
  cell*8, has zero velocity, timer 8, and one-based animation 74..79 with
  delay 2, mode 1. Initialization occurs only after successful allocation.
- Blocked downward collapse 5388 sets shake duration 3 before bounce RNG.
  Explosion 4164 sets duration 2 for visual types greater than 1.
  At 806A..8091, each active frame draws `Random(duration*2)`, decrements
  duration, and clears the offset when it reaches zero. Camera helper 36F6
  adds DS:2098 to fine X scroll. Rendering must not consume these draws.

File offsets for these code anchors are Ghidra offset + 0x770. Read-only
disassembly used `objdump -D -b binary -mi386 -Maddr16,data16` on LEZAC.EXE.

## Compared State

The natural fixture has 144 consecutive motion, input, animation, map,
collapse, RNG and shake checkpoints. Pickup at sample 33/frame 123 is live
at 24 checkpoints. At entry sample 46/frame 136, shake bytes are
`010002000100` (offset 1, remaining 2, active 1), then `000001000100`, then
zero. The RNG is seeded once from entry frame 90 (`DC6A725C`).

The fracture fixture creates its actor at frame 114 with timer 8, position
(184,160), sprite 74 and cursor `4a4a4f02020101`. It advances to sprite 75
on the next tick, displays all six sprites, and is removed at frame 129.
There are 15 live states within 21 checkpoints; creation RNG is E28F6D7A.

Actor comparison covers kind, timer, behavior, signed velocities, fraction
words, hotspot, all seven animation bytes, X/Y and all four sprite descriptor
bytes. It does not assert stale unused actor bytes or identical visual-slot
allocation. The natural map boundary remains one initial tile and six words
outside the defined compressed payload; no original tail is injected.

Fixture SHA-256 values (raw promoted LF files):

- `pickup_transients_original/platform_collapse.txt`:
  `a07a190e97c93ccb32810c8c3eb6135957c0e25d5a5d76d7b31b87662598c5fe`
- `pickup_transients_original/platform_collapse.tiles.bin`:
  `6d27363a3381e8faadf247ad8188427cab5a09987f28fe20494520ed12b1973c`
- `pickup_transients_original/platform_collapse.words.bin`:
  `6712e35b68639ad85ed0ab81d6b836b71300e635eedf826f94ef62535d29ba6b`
- `fracture_actor_original.txt`:
  `8604621c87c91e23bbe02f66cedfb312fd95b2c5a5cc429b0eca37872345f55e`

## Validation and Visual Inspection

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-pickup-transients-original tests/fixtures/pickup_transients_original \
  build-codex-tmp/pickup-transients-final
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-fracture-actor-original tests/fixtures/fracture_actor_original.txt \
  build-codex-tmp/fracture-actor-frames
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-transient-actor-limits
```

These replays pass. The capacity diagnostic covers clockwise placement,
pickup limits 13/14, shared limit 30, RNG gates, pause, reset, and rendering
without RNG consumption. Its limit claims are static-contract tests, not
original runtime capacity probes. The initial full suite exposed three
old medium/super-bomb tests assuming no RNG draws during shake. Their setup
seed now advances `3AA9A995 -> 956923EA -> 90E25B93`, preserving the original
corpse/reward fixture seed and subsequent reward checks. All six focused
tests pass after this correction.

Final validation: the full 430-case CTest run passed 429 tests and skipped
the interactive test under dummy SDL (66.00 seconds). Running
`env -u SDL_VIDEODRIVER -u SDL_AUDIODRIVER ctest --test-dir build --output-on-failure -R '^ui_xdotool_xvfb$'`
passed the remaining UI test (5.04 seconds). The full log is preserved at
`build-codex-tmp/transient-full-tests-passing.log`. `git diff --check` passes.
The existing `debugDebrisShatterPlayback` snprintf compiler warning remains
unrelated to this batch.

Original pickup screenshot `pickup_transients_043.png` and C++ replay
`platform_collapse_43.ppm` were inspected and shown to the user. The yellow
50 indicator is visible above the player; drawing it after players avoids
occlusion. Original `fracture_actor_v2_005.png` and C++ `fracture_actor_5.ppm`
were also inspected and shown. The white puff uses the shipped sprites.
Screenshots are comparable states, not frame-aligned pixel-parity evidence;
camera framing and HUD/ammunition differ in the seeded fracture setup.

## Remaining Limits

- Shared allocation order is not yet represented by one C++ pool. The new
  transient guard counts modeled collections; other producers still have
  their existing allocation policies.
- Original pickup allocation failure still zero-initializes the last
  actor's animation before checking success. This edge case is not modeled;
  the fracture caller correctly gates initialization on success.
- Global bomb, spawner, monster and player ordering is not closed by moving
  transient updates before players. Shake rendering timing across arbitrary
  interactions and two-player views still needs original comparison.
- Irregular collapse groups, contact/crush semantics, broader natural bomb
  progression and the decoder tail remain open. Existing historical debris
  retirement claims also need reconciliation with current implementation.
- `port_functionally_complete=0` and `original_fidelity_claim=0` remain set.
