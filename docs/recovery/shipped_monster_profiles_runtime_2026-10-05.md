# Shipped Monster Constructor And Trajectory Evidence

This batch validates all 15 spawner profiles in the shipped `LIVELS.SCH`
through native construction and continuous actor motion. It changes no
production gameplay behavior. The four broad recovery items remain OPEN;
`port_functionally_complete=0`, `original_fidelity_claim=0` and `visual_claim=0`
remain unchanged. All processes and their children use dummy audio.

## Native Observation

The observer reads the 15 original 30-byte records directly from the shipped
level bank, retaining their level, slot and file offset. The profiles cover
Levels 1..6, kinds 1..4 and behaviors 3/4. Level 7 has no ordinary spawner;
its GRAN.MST boss is outside this experiment.

Each profile runs with seeds `0`, `0x12345678` and `0xFFFFFFFF`. The actual
native spawner loop performs allocation, four parameter/health RNG draws,
animation construction, budget/allowance consumption and countdown reload.
The new actor then receives 64 consecutive native updates, with no per-tick
actor or RNG reseeding. Native player processing continues between passes.
The observer pauses the routine while interrupts continue; wall-clock and
physical keyboard fidelity are not asserted.

The experiment is controlled, not a natural route. Each shipped record is
relocated to visual position `(336,105)` in a neutral Level 1 room with a
floor, ceiling and side walls. Enabled/allowance/countdown bytes are set to
`1`; the remaining profile fields, including budget, kinds, behavior, AI
ranges, health range, animation delay and reload period, stay shipped values.
Initial player entry records, positions, reserves and health are reset for
each case. Seed zero starts P1 nearby; the other seeds start P1 far away.
P2 is inactive. Both visual records are retained, not treated as verified
two-player gameplay.

Verified hooks are `1000:7A6B` before the spawner loop, `1000:7C3D` after
construction and `1000:7EEA` after the monster pass. Relocated runtime
instruction windows are checked before installation. Trampolines preserve
registers, flags and stale stack bytes. Original hooks and scratch bytes are
restored and read back before the owned child is terminated. The guarded
executable SHA256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

Two independent complete captures produce an identical 659,772-byte fixture:
`tests/fixtures/shipped_monster_profiles_original.bin`, SHA256
`b1c71fb54958a9cac974c30813ba55c157ff50cdb5bfa33688a97ab0cbfe79ea`,
FNV-1a64 `be9d74b942656b0b`. It retains the descriptor table, room tiles,
shipped records, before/constructor states and every pre/post tick boundary,
including raw actors, visuals, spawners, player target views and registers.

## C++ Replay

`--debug-shipped-monster-profiles` uses production `updateMonsterSpawners()`
to construct the actor from the original profile, not from a captured actor
seed. It then runs production `updateMonsters()` for 64 continuous updates,
with the production countdown pass on subsequent ticks. Only player target
coordinates and state are supplied exogenously each tick; the monster, AI
parameters and shared RNG remain continuous.

All 45 constructors and 2,880 updates match identity, behavior, ownership,
health, hotspot, coordinates, velocity, both fractional words, AI parameters,
animation cursor/range/counter/delay/mode/step, visible sprite descriptor,
spawner budget/allowance/countdown and shared RNG. The native descriptor table
is checked against every decoded SPR frame's dimensions and cumulative pixel
offset, and each captured descriptor is checked against the sprite selected
by the real renderer. This is not a
comparison of every opaque actor byte or of every player/world field.
The native constructors confirm hotspot zero for shipped kinds 2..4;
kind 1 remains six. Other kinds' natural construction is not established.

Size and fingerprint guards precede resource loading and SDL initialization.
Sixteen truncated, trailing and byte-mutated inputs are rejected by the actual
compiled diagnostic. Five new CTests cover replay, fixture, corruption guard,
retained archive and original instruction self-check. A fresh native CI job
repeats the entire observation and requires byte equality with the fixture.
All 65 focused actor/contact/spawner/behavior-4/ledge tests passed locally.
Full platform gates are still required for delivery.

```sh
env SDL_AUDIODRIVER=dummy SDL_VIDEODRIVER=dummy \
  ./build/lezac_cpp --debug-shipped-monster-profiles \
  tests/fixtures/shipped_monster_profiles_original.bin
python3 tools/check_shipped_monster_profile_fixture.py --archive
```

## Retention And Limits

`evidence/shipped_monster_profiles_20261005/native-captures.tar.gz` is
910,681 bytes, SHA256
`76d4ef3eafb84dd3cce9af20c317f4aee5eca546c9774ca57d805725a38694fa`.
Its 160 regular files contain 7,587,092 uncompressed bytes, including both
complete native captures, successful producer snapshots, both incomplete
captures and the preceding merge's exact-head Windows/Linux CI logs. Every
archive member was read back and byte/hash checked against its source.
The member manifest is retained beside the archive. The archive CTest
re-extracts both complete captures in memory and requires the pinned fixture
bytes; it also requires the incomplete capture receipts and rows to remain.

The first capture failed to reach its next spawner boundary after 31 complete
cases (1,984 updates), while reusing player actor state between cases. Its
missing final boundary is not promoted to a diagnosed gameplay result.
The attempted repair used health 255, which is
invalid: the original compares the unsigned post-subtraction health with 200
at `1000:7FA0..7FAC` and enters death above that boundary. The corrected
capture restores the whole entry record with legal health 100. Failed runs
remain evidence of harness failure, not successful game comparisons. Their
older producer source was not snapshotted before editing, so it is not
claimed as retained executable provenance; their incomplete outputs and
errors are preserved. The second run retains 61 updates and a final data
segment showing P1 in state 2. Both successful producer sources are retained and
verified. An initial shell-quoting failure occurred before focused CTest
execution; the subsequent Python argument-array invocation ran all 65 tests.

The first full local suite was invalidated by rebuilding its executable while
existing boss mutation guards were repeatedly launching it. Three guards
reported `PermissionError` on the binary at link time, not game comparison
failures; 632 tests passed and the generic UI test was explicitly skipped.
The failed log is retained. A complete fresh suite against a frozen build is
required; neither these failures nor the original comparison gates are bypassed.

Original and C++ profile-12 screenshots are retained in this directory.
They are actor-replay inspection only: native player animation, HUD and the
inactive P2 viewport are not reproduced by this diagnostic, so these images
are not pixel parity. This batch does not prove actual level geometry,
natural spawn timing, natural campaign trajectories, physical controls,
other actor kinds, damage/death/reward lifecycle, full pool interactions or
whole-game acceptance.
