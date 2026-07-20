# Source modularization plan

`src/main.cpp` currently contains resource decoding, sound, rendering, UI, gameplay simulation, diagnostics, and the executable entry point in one translation unit. A direct mechanical split would create a large, difficult-to-review change and would make fidelity regressions hard to isolate. The decomposition must therefore be incremental and test-preserving.

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

1. Extract POD models, constants, byte readers, fixed-point helpers, and pure utility functions.
2. Extract original/JSON resource loaders and resource validation.
3. Extract sound models, playback state, priority latch, and audio callback.
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
