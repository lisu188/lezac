# Gameplay ownership

`GameSession` owns the live gameplay fixture. Its commands handle input, level
transitions, the recovered tick sequence and render preparation. `view()` and
render projections expose const references to that state. An explicit
`snapshot()` returns a detached value; `restoreFixture()` imports a value.
Neither operation is part of ordinary input, updates or drawing.

`diagnostics::GameplayReplay` owns a separate fixture. Existing diagnostic
commands retain their field and helper contracts against that owned copy.
They do not obtain a mutable player, vector, map or scalar reference from the
live session. Changing their fixture has no effect on live play.

Both final classes privately inherit the protected `GameplayOperations`
implementation. Its 233 operation bodies were relocated from current-main
`dcc3352eaefc0c449b34220f9a6143404fbb08dc`, preserving their recovered instruction,
allocation and callback boundaries. A diagnostic run therefore executes the
same implementation against independent state rather than copying a live
session before and after every helper. The operation base cannot be copied or
moved because its internal aliases must remain bound to its own fixture.
The large fixture is privately allocated to avoid adding its buffers to the
application's stack frame.

The complete value includes `ActorSlots`, `MonsterSpawnerStorage`,
`MapPlaneMemory`, retained flame/debris/collapse queues, damage lanes, logical
actors, player state and RNG. The physical allocator's inactive tails, identity
bindings and map-heap metadata remain present. They are not reconstructed from
typed actor vectors during normal play.

UI, presentation, audio, immutable assets and clock services retain their
separate owners. The session borrows them through `GameplayServices` at the
existing call boundaries. Callbacks and references remain valid for both
operation owners' lifetimes. The application is noncopyable, and the borrowed
services are constructed before its sessions.

## Application boundary

Ordinary `run()` selects `GameSession` before startup. Event processing sends
fire latches and physical portal-down bank releases to that owner. Keyboard
normalization reads its player count; drawing consumes its const world and HUD
projections. The detached diagnostic fixture is not synchronized during this
path.

Interactive diagnostics also execute the real live session. Their explicitly
requested setup and after-tick/event observations use detached snapshot copies
outside an active gameplay iterator. In-tick death logging reads a const view
at that precise boundary; it does not restore a snapshot during a live update.
Diagnostic stop predicates that inspect player movement likewise read the
active const view.

## Regression checks

`gameplay_owned_fixture_api` compares the entire owned value, including hidden
physical state, across 540 live/replay ticks, input commands, level reloads,
callback observations, RNG and rendered pixels. Const defaulted equality
operators compare fields and containers without inspecting padding. Negative
controls distinguish inactive queue/actor tails, map allocation metadata and
actor identity bindings. Compile-time checks reject copying, moving and public
conversion to the protected operation base.

`gameplay_live_no_fixture_bridge` exercises the ordinary application entry,
queued SDL menu/fire events, updates and rendering. It deliberately poisons the
detached fixture, then requires live ticks, unchanged poison, actual live
render-view addresses and zero diagnostic snapshot/restore calls. It is an SDL
event probe, not a claim of human keyboard acceptance.

The GRAN ownership guard identifies the actual shared operation consumer and
its borrowed immutable catalog. Separate negative controls reject public
inheritance, mutable live fixture access, diagnostic friendship and alias
lifetime weakening. Existing original-backed, physical-key and rendered-route
checks retain their distinct acceptance scopes.

Source recovery contracts resolve the manifest-owned operation definitions and
exclude only verified application forwarding bodies. Missing, forged,
duplicated or unowned boundaries are rejected. Existing statement and mutation
checks still inspect the recovered bodies. Frozen original producers and
their pinned checker dependencies remain unchanged.

The four native regression mutants compile altered operation implementations
against the same application object as the normal executable. They retain
their existing rejection checks for actor identity, corpse animation phase,
reward RNG ordering and sprite-bank selection.
