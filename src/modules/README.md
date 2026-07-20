# Module ownership

This directory is the landing area for incremental extractions from `src/main.cpp`.

| Module | Owns | Must not own |
|---|---|---|
| `core` | constants, fixed-point arithmetic, shared value types | SDL objects, file I/O, gameplay state |
| `resources` | binary/JSON decoding and immutable resource models | rendering, audio playback, gameplay mutation |
| `sound` | decoded sound state, priority latch, audio generation | menu or actor decisions |
| `rendering` | palettes, tiles, sprites, frame composition, HUD drawing | simulation updates |
| `ui` | menus, records, name entry, pause, level intro, end flow | actor physics or resource parsing |
| `gameplay` | levels, players, actors, bombs, monsters, collision, boss | SDL event-loop ownership |
| `diagnostics` | command handlers and deterministic inspection adapters | private cross-module field access |
| `app` | SDL lifetime, event loop, subsystem orchestration | decoding or domain algorithms |

New extraction PRs should create conventional `.hpp` and `.cpp` pairs beneath `src/<module>/`. Avoid umbrella headers and avoid moving unrelated declarations merely to reduce line count.

The authoritative extraction order, dependency direction, review constraints, and completion criteria are documented in `docs/architecture/source-modularization.md`.
