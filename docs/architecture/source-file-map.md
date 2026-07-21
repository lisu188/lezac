# Concrete source-file split

This document turns the module boundaries from `source-modularization.md` into a concrete C++ file and target design. The split is intentionally incremental: every extraction must compile as an independent translation unit, retain existing behavior, and keep the deterministic test contracts intact.

## Build targets

```text
lezac_core          SDL-free value types and pure algorithms
lezac_resources     asset models, binary/JSON readers, validation
lezac_sound         sound state, priority latch, audio generation
lezac_rendering     framebuffer, palette, tile, sprite, text and HUD rendering
lezac_gameplay      level state and simulation
lezac_ui            menu, records, intro, outro and pause flows
lezac_diagnostics   debug commands and deterministic inspection adapters
lezac_app           SDL ownership, input loop and subsystem orchestration
lezac_cpp           process entry point only
```

During the migration these may initially be CMake object libraries. Object libraries allow the current executable and test commands to remain unchanged while enforcing independent compilation and include boundaries.

## Target file layout

```text
src/
  main.cpp
  app/
    app.hpp
    app.cpp
    command_line.hpp
    command_line.cpp
    runtime_paths.hpp
    runtime_paths.cpp
  core/
    constants.hpp
    fixed_point.hpp
    fixed_point.cpp
    progress.hpp
    progress.cpp
    random.hpp
    random.cpp
    geometry.hpp
    types.hpp
  resources/
    models.hpp
    binary_reader.hpp
    binary_reader.cpp
    json_reader.hpp
    json_reader.cpp
    palette_loader.hpp
    palette_loader.cpp
    image_loader.hpp
    image_loader.cpp
    tile_loader.hpp
    tile_loader.cpp
    sprite_loader.hpp
    sprite_loader.cpp
    sound_loader.hpp
    sound_loader.cpp
    gran_loader.hpp
    gran_loader.cpp
    level_loader.hpp
    level_loader.cpp
    record_loader.hpp
    record_loader.cpp
    resource_set.hpp
    resource_set.cpp
  sound/
    models.hpp
    sound_engine.hpp
    sound_engine.cpp
    sound_routes.hpp
    sound_routes.cpp
  rendering/
    framebuffer.hpp
    framebuffer.cpp
    palette.hpp
    palette.cpp
    sprite_renderer.hpp
    sprite_renderer.cpp
    tile_renderer.hpp
    tile_renderer.cpp
    text_renderer.hpp
    text_renderer.cpp
    background_renderer.hpp
    background_renderer.cpp
    world_renderer.hpp
    world_renderer.cpp
    hud_renderer.hpp
    hud_renderer.cpp
  gameplay/
    models.hpp
    level_state.hpp
    level_state.cpp
    collision.hpp
    collision.cpp
    player.hpp
    player.cpp
    actors.hpp
    actors.cpp
    monsters.hpp
    monsters.cpp
    bombs.hpp
    bombs.cpp
    damage.hpp
    damage.cpp
    effects.hpp
    effects.cpp
    portals.hpp
    portals.cpp
    triggers.hpp
    triggers.cpp
    boss.hpp
    boss.cpp
    simulation.hpp
    simulation.cpp
  ui/
    models.hpp
    menu.hpp
    menu.cpp
    records.hpp
    records.cpp
    name_entry.hpp
    name_entry.cpp
    level_intro.hpp
    level_intro.cpp
    level_outro.hpp
    level_outro.cpp
    pause.hpp
    pause.cpp
    end_flow.hpp
    end_flow.cpp
  diagnostics/
    command.hpp
    command_registry.hpp
    command_registry.cpp
    resource_commands.cpp
    sound_commands.cpp
    rendering_commands.cpp
    gameplay_commands.cpp
    fidelity_commands.cpp
```

## Dependency graph

```text
core
  ^
  |
resources
  ^
  +-------------------+--------------------+
  |                   |                    |
sound             rendering            gameplay
  ^                   ^                    ^
  +-------------------+--------------------+
                      |
                     ui
                      ^
                      |
                 diagnostics
                      ^
                      |
                     app
                      ^
                      |
                    main
```

Rules:

- `core` contains no SDL, file-system, JSON, rendering or game-state dependency.
- `resources` returns immutable decoded models and never renders or mutates simulation state.
- `sound`, `rendering` and `gameplay` do not depend on `App`.
- `ui` coordinates rendering-facing view models but does not update actor physics.
- `diagnostics` uses public subsystem APIs and explicit snapshots; it must not become a friend of every implementation class.
- `app` is the composition root. It owns SDL handles, the event loop, clocks and subsystem instances.
- `main.cpp` parses process-level arguments, constructs `App`, invokes one operation and maps exceptions to the process exit code.

## State ownership

The current monolith mixes durable resources, mutable simulation state, rendering state and diagnostics in one `App` object. The final ownership model is:

```text
App
  ResourceSet resources
  SoundEngine sound
  Renderer renderer
  Simulation simulation
  UiController ui
  DiagnosticRegistry diagnostics
```

`Simulation` owns players, actors, monsters, bombs, explosions, level mutation, scores and gameplay RNG. `Renderer` receives read-only snapshots. `UiController` owns menu/record/intro/outro state. Diagnostics receive references to explicit public interfaces rather than the complete `App` object.

## Interface rules

- Headers expose domain values, references, spans or immutable views; never pointers into unrelated subsystem internals.
- No header includes `SDL.h` unless the type directly owns an SDL object.
- Prefer forward declarations in public headers and concrete includes in `.cpp` files.
- Keep recovered numeric types exact. A split must not silently change `uint8_t`, `uint16_t`, signed fixed-point values or overflow behavior.
- Pure helpers move before stateful code. A source move must not be combined with renaming, cleanup or algorithm changes.
- Temporary compatibility adapters are allowed, but including a `.cpp` file is not an acceptable final boundary.

## Incremental extraction sequence

### PR 1: core progress helpers

Create the first independently compiled production source file by extracting destruction and physical-damage progress predicates into `core/progress.hpp/.cpp`. Keep call sites unchanged through narrow namespace imports. Update CMake so `src/main.cpp` and `src/core/progress.cpp` compile separately.

### PR 2: core fixed-point and RNG

Move fixed-point integration, clamping and the Turbo Pascal RNG into `core/fixed_point.*` and `core/random.*`. Add direct unit tests with the existing reference vectors.

### PR 3: resource value models

Move `Rgb`, palette/image/tile/sprite/sound/level/record/GRAN value types into `resources/models.hpp`. No loader logic moves yet.

### PR 4: binary readers and resource loaders

Extract byte readers first, then one loader family per commit. Build `lezac_resources` independently and retain every raw-roundtrip diagnostic.

### PR 5: sound engine

Move sound models, selector mapping, priority latch, audio callback and route constants. SDL audio ownership remains in the sound implementation.

### PR 6: rendering primitives

Extract framebuffer/pixel operations, palette conversion, tile/sprite/text rendering and background composition. Rendering consumes resource models and immutable gameplay snapshots.

### PR 7: HUD and UI flows

Move HUD rendering, menu, records, name entry, pause, level intro, level outro and end flow. Keep input interpretation in app until UI interfaces are stable.

### PR 8: gameplay simulation

Move level state, collision, players, actors, monsters, bombs, damage, effects, portals, triggers and boss logic. Split by cohesive state ownership, not by arbitrary line count.

### PR 9: diagnostics registry

Replace the process-level command chain with named command handlers grouped by subsystem. Existing command names and output strings remain unchanged.

### PR 10: final app boundary

Stop including `app.cpp`. Expose `App` through `app.hpp`, compile `app.cpp` independently, and reduce `main.cpp` to argument parsing and exception-to-exit-code translation.

## Review and completion gates

Every extraction PR must satisfy all of the following:

- Linux and Windows compile every new translation unit independently.
- The full CTest suite passes with unchanged test names and output contracts.
- No production `.cpp` file exceeds 2,500 lines at completion.
- No circular target dependency is introduced.
- No new global mutable state is introduced to avoid passing dependencies.
- Moved code remains textually identical where practical.
- Behavioral changes, type changes and naming cleanup are submitted separately.
