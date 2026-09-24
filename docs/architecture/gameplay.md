# Gameplay ownership and replay boundaries

`GameSession` coordinates the recovered tick order. It composes four owners:

- `LevelWorld` owns the current level, progress counters and clock. It implements
  tile and word lookup, collision scans, object-cell predicates and completion
  queries.
- `PlayerRoster` owns both player slots, inventories, scores, damage and reentry
  state. It implements slot selection, state-2 cursor advancement, damage-counter
  gates and the independent player motion primitives.
- `ActorSystem` owns spawners, monsters, boss links, bombs, rewards and transient
  actors. It implements shared capacity, stable actor ordering and adoption.
- `TerrainEffects` owns flame, debris, collapse and visual-effect queues. It
  implements queue seeding, damage-phase lookup, visual expiry and camera shake.

Only `GameSession` is a friend of these owners. This internal collaboration keeps
cross-owner updates at their original boundaries. Public owner snapshots are
const. `GameSession::view()` is a cheap const projection; `snapshot()` returns an
owned copy. No mutable player, vector, map or scalar reference leaves the session.

The shared non-player pass remains one ordered scheduler. It preserves stable
deletion, same-pass tail appends, in-place conversions and the common 30-slot
limit. Per-type behavior is in the corresponding session translation units;
replacing this pass with independent per-type loops would change gameplay.

## Production application integration

The application owns one `core::TurboRandom` and injects it, the immutable
`AssetCatalog`, and the `SoundEngine` into `GameSession`. Presentation generation
and level-intro/outro randomness borrow that same stream. All seed reset sites
remain explicit.

The application installs synchronous `GameplayHooks` for UI gates, level and
end-run transitions, palette updates and sound pumping. `beforeReset` clears the
intro/outro and pause state; `mapSizeChanged` calls
`PresentationState::beginLevel`. `tick()` calls the hooks at the recovered
boundaries, including the second UI gate after the reentry prepass.

Production input uses `setFireLatch`, `prepareNewGame`, `clearScores`,
`resetReserveLives`, `reset` and `awardScore`. The UI's prepare-new-game and
clear-score actions remain separate to retain their existing order.

To begin a level:

1. Call `beginLevelSelection(index, menu, decodePlane)`. The decoder callback
   delegates to `PresentationState::decodeLevelPlane`, preserving the shared
   compressed-input tail.
2. Generate the intro pattern with the shared random stream and start `LevelFlow`
   at the existing clock sample.
3. If `view().levelRestartPromoted_` is set, notify the `intro_wait` boundary.
4. On acknowledgement call `finishLevelSetup(intro.levelIndex)`, then rebuild the
   backdrop with the same random stream. The session preserves the tick clock,
   both reentry countdowns and the shared fallback counter across the reset.

The completion hook calls `advanceCompletionState(interactive)`. Its result is
`None`, `UpdateOutro`, `NextLevel` or `EndRun`; the UI performs that transition
synchronously. Outro score callbacks use `awardScore` before the corresponding
random sound decision. Completion's compatibility sound and 100-tick gate remain
inside the session.

Rendering calls `renderActorOrder()` at the former draw preparation boundary and
passes const values from `view()` to the renderer. This preserves the historical
adoption of directly seeded actors before sorting the separate visual order.

Production code does not use `GameplayReplay` or `restoreFixture`.

## Diagnostic replay

`diagnostics::GameplayReplay` owns a `GameplayFixture` value. Its field names match
the legacy diagnostics so those bodies can move without changing their printed
contracts or their seed boundaries. Each helper call imports the fixture through
`restoreFixture`, executes the same private helper as production, and reconciles
the result into the owned copy. Vector reconciliation preserves references to
surviving fixture slots when the operation does not require reallocation.

Mutable arguments are represented by `ReplayTarget<T>`: an explicit slot and
index, or an owned detached value. Runtime references are resolved only inside
`GameSession`; returned references are translated back into the adapter's owned
fixture. Repeated detached arguments of the same type carry a request-local alias
identity, so helpers retain their original reference aliasing and write order.
Invalid alias identities and aliases on owned slots are rejected before execution.
Detached result references are rejected. There is no mutable callback
into runtime state and no friendship with diagnostics or the application.

Read-only actor and reentry observers receive `const GameplayView&`. The launch
marker fixture's old mutating observer is a typed `AfterActorPassAction` instead.
It is consumed once after the ordered actor pass and before the observer/player
pass, and claims actor order at that boundary. Thus fillers do not advance in the
pass that precedes their injection.

`gameplay_owned_fixture_api` checks copy isolation, detached versus slot replay
arguments, fixture-reference stability and phase-action ordering. Existing
original-backed and deterministic route fixtures remain the behavior evidence.
