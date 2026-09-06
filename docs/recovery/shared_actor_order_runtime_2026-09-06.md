# Shared Actor Update Order

## Scope And Result

Ten seeded original level-1 cases provide 410 consecutive actor passes and
7,685 live actor/visual states. The production C++ frame update now matches
their ordered mapped fields, stable visual indices, actor/visual counts,
RNG state and byte-map deltas. Cases mix moving bombs, rewards, corpses and
behavior-5 effects, including adjacent deletions and full 30-actor pools.

The old production loop updated entire C++ type groups. It could retire an
effect before an earlier corpse attempted to allocate particles, free all
expiring bombs before either converted, and reorder random draws between
bombs and corpses. The new dispatcher visits one actor at a time in shared
construction order. Stable deletion preserves survivors' relative order;
in-place conversions retain their identity; appended particles are visited
at the tail during the same pass, not immediately during their constructor.
The typed storage remains in place. Legacy diagnostics that directly seed
unidentified actors receive explicit fallback identities before dispatch;
the new original replay seeds actual captured order instead.

This is a focused update-order recovery, not a complete actor model or a
whole-game rendering result. The renderer still groups sprites by type.
No sprite-overlap, natural-route, boss-link repair or two-player parity
claim is made.

## Original Rules

- Main CS:3358 (file 0x3ac8) deletes an actor by copying each following
  38-byte record down one slot. It does not swap the last actor into the
  deleted slot. DS:208D is the dynamic non-player count.
- The deletion helper calls driver 08AC:0594 (file 0x97c4), which shifts
  trailing 8-byte visual entries and decrements DS:C496. Actor visual
  references greater than the removed index are decremented. The static
  code also repairs both endpoints of motion links; these captures disable
  links, so that part is not runtime-verified here.
- Behavior-5 expiry calls deletion at main CS:65BF..65C4 and decrements the
  actor cursor DS:2082 at CS:65C6. The outer CS:7EC5..7EEA loop increments
  the cursor and rereads the count. Consequently, the shifted next actor
  still runs once, and newly appended actors run later in this pass.
- Bomb and corpse expiry replace their current slot with a fade or reward.
  They do not free that slot for an appended particle or update the
  replacement twice. Random draws still occur when particle allocation
  fails, as in the earlier death-transient recovery.

The first original pass makes ordering observable even at identical pool
occupancy. `corpse_front_full` starts with corpse/effect/bomb and 27 fillers;
the corpse cannot append while the later effect is still alive, and the
pass ends with 29 actors. `effect_front_full` reverses the first two slots;
expiry frees a slot before the corpse runs, so a new particle is appended
and visited, leaving 30 actors. Both end with RNG 0xe28f6d7a.

`retire_front` and `retire_back` retire two adjacent effects while preserving
the moving bomb and reward. Four additional full-pool cases mix two bombs,
two corpses, and opposite bomb/corpse order. The final two cases reverse a
moving effect/bomb/reward/corpse sequence. Each case continues for 41 passes
with no intervening gameplay-state reseeding.

## Capture Provenance

Original executable SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

`tools/capture_original_shared_actor_order.py` uses the existing temporary
DOSBox/Xvfb level seeder with surface output, no scaler, frameskip zero,
fixed 6000 CPU cycles and menu key `1`. Startup/intro/level-start waits are
10/8/5 seconds. The original executable and shipped assets are copied into
`/tmp/lezac-actor-order1`; no shipped files are patched in place.

Fifteen instruction windows are guarded both statically and at runtime.
Polling trampolines at main CS:F400/F480, using scratch F600, stop before
the actor pass at CS:7EC5 and after it at CS:7EEA. FLAGS and general registers
are saved/restored, and displaced instructions are replayed. Actual
registers are CS=01a2, DS=0c44, ES=0c44, SS=18b3, saved SP=3fe4, BP=3ffe.
The helpers' nominal CS=01ed and DS=0c8f are relative to an adjusted host
memory base, not the sampled segment registers; DS-CS remains 0x0aa2.

At each case boundary the captured initial byte/word maps are restored.
The frame counter is seeded to 101, RNG to 0x12345678, P1 to (240,168),
lives to 99 and energy to 100. P2, spawners, motion links, collapse and
flame/debris work are disabled or emptied. The first two visual slots stay
reserved for players; each non-player actor receives the next visual slot.
All 38-byte actor records and 8-byte visual rows are explicit seeds.
Velocity, fractional carry, countdown, animation and descriptor seeds are
recorded in the fixture and in `seed_actor`. Screenshots are captured while
stopped, without altering actor state between successive passes.

Command after copying the shipped assets into the temporary directory:

```sh
env PYTHONUNBUFFERED=1 python3 tools/capture_original_shared_actor_order.py \
  --run-dir /tmp/lezac-actor-order1 \
  --out build-codex-tmp/shared-actor-order-v1.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The successful capture is promoted unchanged to
`tests/fixtures/shared_actor_order_original.txt`. Normalized LF SHA-256:
`765b724713778f7fa86e7df8fe7812de9e40b029cf85b46bc6e25ed9ecdd6e4e`.

## Validation And Frames

The replay seeds once per case and runs `updateWithControls` continuously.
Its observer compares after the non-player pass, before players and flames.
Effects compare all seven animation bytes plus mapped motion/lifecycle
fields. Bombs, corpses and rewards compare kind, behavior, timer, hotspot,
X/Y, VX/VY, both fractional carries and the selected four-byte descriptor.
Ordered visual-slot indices, total counts, RNG and byte-map changes are
checked on every sample. It does not claim to compare every unused actor
byte or the post-pass word plane.

Three new CTests cover the replay, offline capture-instruction contract,
and fixture guard. The guard pins the source, accepts LF/CRLF, rejects two
truncations and 79 deliberate mutations, and checks for unrequested output.
Mutation cases include reordered actors, altered counts/motion/descriptors,
RNG at multiple case boundaries, invalid registers/provenance, missing or
duplicate ticks, extra fields and trailing records after completion.

The initial 471-test run passed 470 tests; the launch-pad source-context
guard still expected the old no-argument helper signature. It now checks
the ordered helper signature and the production dispatch call. Its existing
gameplay and invisible-marker checks passed without changing expectations.
The focused four-test rerun passes in 63.17 seconds. All 474 tests in the
expanded suite, including interactive Xvfb checks, pass in 124.97 seconds;
log: `build-codex-tmp/shared-order-full-tests.log`.

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-shared-actor-order-original tests/fixtures/shared_actor_order_original.txt \
  build-codex-tmp/shared-actor-order-cpp-v2
```

C++ exports 40 full-screen PPMs and a manifest containing case, sample,
frame, actor count, RNG and frame hash. Original screenshots use
`shared-actor-order-v1_<case>_<sample>.png`. Since the original is stopped
after an actor pass but before that state's display, original samples
1/10/30/40 are compared with C++ states 0/9/29/39. These are comparable
semantic checkpoints, not pixel-alignment assertions.

The `effect_front_full` initial pair was inspected and shown to the user;
the `two_bombs_full` later pair was also inspected. The `mixed_forward`
initial pair was inspected and shown separately. Actor positions look
comparable there, but upper-platform tiles, skyline geometry and the HUD's
display of the seeded 99 lives differ. The actor-pass replay does not verify
all subsequent work before display. The screenshots do not establish pixel
parity, draw overlap order, or complete post-actor frame timing.

## Remaining Work

Sprite ordering needs an original overlapping-visual fixture. Mixed living
monster and boss interactions, motion-link compaction, other allocation
paths (including launch/portal failure), reward collection and the port's
unverified bonus-rain behavior need further recovery. Complete natural
bomb/collapse routes, two-player interactions, HUD phase and collision
edge cases remain open. There is no evidence-based overall completion
percentage, and the port remains functionally incomplete.
