# 2026-04-22 Collision Clearance Coverage Workstreams

## Subagent A - Disassembly Mapper

- Kept `1000:6053..777f` as the unresolved original actor update and collision
  target.
- Current evidence still supports treating this slice as C++ model coverage, not
  exact original collision clearance recovery.
- Identified behavior-4 half-speed reversal as a distinct collision response
  worth pinning alongside behavior-3 stop/full-reversal behavior.

## Subagent B - Gameplay Fidelity

- Identified that the previous `--debug-collision-pushout` command only proved
  the update paths returned; it did not assert final player or monster
  non-collision.
- Recommended synthetic fixtures that force a known solid tile collision and
  verify the post-pushout footprint.
- Identified that `--debug-passable-objects` checked point passability, not the
  full player/monster corner probes or the consumed bomb-object path.

## Subagent C - Rendering/UI

- Confirmed live frame inspection is not required for this coverage slice
  because the behavior is deterministic model state rather than presentation.
- Existing SDL dummy and Xvfb/xdotool smoke tests remain the appropriate UI
  regression layer.

## Subagent D - Verification

- Recommended hardening the `collision_pushout` CTest with a
  `PASS_REGULAR_EXPRESSION` after expanding the debug output contract.

## Subagent E - Integration/Docs

- Recommended minimal documentation updates that distinguish locked C++ model
  coverage from unresolved original actor-update semantics.
- Noted likely mechanical conflicts with open recovery PRs because they share
  `CMakeLists.txt`, `src/main.cpp`, and status/docs files.

## Integrated Decision

`--debug-collision-pushout` now uses a synthetic runtime map to force
horizontal and vertical pushout for player and monster footprints. The diagnostic
asserts that both actor types finish clear of collision, that downward player
pushout sets grounded state and zeroes vertical speed, that monster horizontal
pushout bounces and vertical pushout stops, that behavior-4 collision halves
and reverses velocity while resetting the retarget timer, and that
portal/bomb-object passable tiles remain nonblocking across the sampled
footprints.
`--debug-passable-objects` now also checks a synthetic full-footprint passable
tile cluster and verifies that consuming a bomb-object tile leaves the sampled
cell non-solid.
