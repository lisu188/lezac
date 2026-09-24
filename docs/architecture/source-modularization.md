# Source modularization plan

The runtime and diagnostics currently share the large `src/app/app.cpp` class;
`src/main.cpp` includes that implementation. Core primitives and several resource
codecs already compile independently. Complete the extraction incrementally,
preserving recovered behavior and its evidence.

## Class ownership

| Area | Classes and responsibilities |
|---|---|
| Application | `App` composes subsystems; `SdlRuntime` manages SDL lifetime and `InputMapper` translates input. |
| Resources | `AssetCatalog` owns immutable assets; format-specific codecs preserve binary and JSON behavior. |
| Sound | `SoundEngine` owns synthesis and the priority latch; `SdlAudioOutput` owns queued device output. |
| Rendering | `GameRenderer`, `Canvas`, text and HUD helpers compose frames; `PresentationState` owns runtime palette/backdrop data; `SdlDisplay` owns display handles. |
| UI | `UiController` owns menu/pause/name entry; `LevelFlow` owns intro/outro presentation; `RecordStore` owns persistence. |
| Gameplay | `GameSession` coordinates `LevelWorld`, `PlayerRoster`, `ActorSystem` and `TerrainEffects`. |
| Diagnostics | `CommandRegistry` dispatches existing commands; subsystem handlers and `ScenarioRunner` inspect, replay and capture through public APIs. |

Keep plain value records and pure decoding/arithmetic functions. Do not introduce
entity inheritance, ECS, a deferred event bus or a universal mutable context.
One application-owned `TurboRandom` is borrowed by all existing consumers,
including backdrop generation and intro/outro effects; preserve its consumption
order and reset sites. Injected clocks preserve existing sampling boundaries.

`LevelWorld` owns mutable tiles/words, objectives, portals/triggers and collision.
`PlayerRoster` owns both players and shared reentry state. `ActorSystem` retains
typed containers under one scheduler, a shared 30-slot capacity, birth order and
independent visual-order keys. `TerrainEffects` owns flames, debris and collapse.
Actor/debris appends can run in the same pass; preserve in-place transformations,
numeric widths, signed wrapping, and player-one-before-player-two processing.
Level reset preserves run-level lives and scores.

Before drawing, explicitly prepare actor ordering at the existing adoption
boundary, then render through const views. Do not normalize fixtures early.
Backdrop simulated overflow deliberately reads padding and live map bytes;
runtime palette state is separate from immutable asset data. `PresentationState`
also owns score reels, HUD readiness, objective palette fades and the sampled
destruction percentage. Objective preparation runs after the logic tick increment,
then the frame is presented before actor updates. Reels advance after damage
counters drain; fades advance after camera shake and before the red palette.
Level reset clears HUD readiness/fades and restores the captured initial HUD
palette while retaining score reels; a new run clears the reels separately.
These lifecycle operations are explicit, and repeated rendering cannot advance
any of them. Sound priority
requests resolve synchronously and pumping retains its current tick boundary.

Diagnostics use read snapshots, explicit typed fixture/replay operations and
named phase observers. Separate read-only observations from phase-targeted replay
mutations, including actor injection between non-player and player updates.
Move each diagnostic family with its subsystem instead of granting private access.

## Target layout

```text
src/
  app/
    app.cpp
    app.hpp
    main.cpp
  gameplay/
    actors.cpp
    actors.hpp
    bombs.cpp
    bombs.hpp
    boss.cpp
    boss.hpp
    collision.cpp
    collision.hpp
    level.cpp
    level.hpp
  rendering/
    renderer.cpp
    renderer.hpp
    hud.cpp
    hud.hpp
    sprites.cpp
    sprites.hpp
  resources/
    binary_reader.cpp
    binary_reader.hpp
    loaders.cpp
    loaders.hpp
    models.hpp
  sound/
    sound_engine.cpp
    sound_engine.hpp
    sound_models.hpp
  ui/
    menu.cpp
    menu.hpp
    records.cpp
    records.hpp
    level_intro.cpp
    level_intro.hpp
  diagnostics/
    command_registry.cpp
    command_registry.hpp
    diagnostics.cpp
    diagnostics.hpp
  core/
    constants.hpp
    fixed_point.hpp
    types.hpp
```

## Dependency direction

Dependencies must point inward in this order:

```text
core <- resources <- sound/rendering/gameplay/ui <- app <- main
                                      ^
                                      |
                                diagnostics
```

Rules:

- `core` has no SDL dependency.
- `resources` performs decoding only and does not mutate gameplay state.
- `sound`, `rendering`, `gameplay`, and `ui` may depend on `core` and resource models, but not on `App`.
- `diagnostics` calls public subsystem APIs and must not use private implementation fields.
- `app` owns orchestration and the SDL event loop.
- `main.cpp` only parses process-level startup state and invokes `App`.

## Extraction sequence

Each phase must preserve the configured CTest count and output contracts.

0. Establish a fresh test/CLI/frame baseline and migrate source-aware checks to explicit ownership and qualified methods without weakening predicates.
1. Extract remaining POD models, constants, byte readers, fixed-point helpers, and pure utility functions; retain existing core/resource modules.
2. Extract original/JSON resource loaders and resource validation.
3. Extract sound models, playback state, priority latch, synthesis, and queued SDL audio output.
4. Extract sprite, tile, background, palette, text, HUD, and frame rendering.
5. Extract menus, records, name entry, setup, pause, intro, and end-flow UI.
6. Extract level state, players, actors, monsters, bombs, explosions, collapse, portals, and boss logic.
7. Replace the diagnostic command chain with a registry of named handlers.
8. Reduce `App` to orchestration and move the executable entry point to `src/app/main.cpp`.

## Review constraints

- One subsystem per PR.
- No behaviour changes in extraction PRs.
- No renamed constants or changed numeric types unless backed by a separate test.
- Moved code should remain byte-for-byte identical where practical.
- Every PR must run the full CTest suite.
- Preserve CLI arguments/defaults/output, asset selection, install layout and capture manifests. Compare deterministic before/after C++ frames pixel-for-pixel and inspect actual frames; this does not establish additional original-game fidelity.
- Run all games, captures and test children silently with `SDL_AUDIODRIVER=dummy`.
- Source-aware checks use an explicit ownership map; diagnostic copies must not satisfy production requirements. Mutation tests cover removed/unauthorized consumers and lost/duplicated evidence annotations.
- Keep test declarations in CMakeLists.txt while evidence readers inspect that file. Optional tool availability can affect configured test counts; establish the baseline separately per platform.
- Public interfaces should expose domain types rather than raw pointers into `App`.
- SDL handles remain owned by rendering/audio infrastructure and use RAII wrappers before crossing module boundaries.

## Completion criteria

The modularization is complete when:

- no production source file exceeds 2,500 lines;
- `src/app/main.cpp` contains no game logic;
- diagnostics compile separately from the runtime subsystem implementations;
- resource parsing and fixed-point helpers have direct unit tests;
- all existing deterministic and fidelity tests retain their names and expected output;
- Linux and Windows CI build every translation unit independently.
