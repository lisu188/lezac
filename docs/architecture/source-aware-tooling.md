# Source-aware tooling during modularization

Static guardrails, recovery evidence checks, and oracle fixture validators must inspect the source file that owns the implementation being verified. They must not assume that production code remains in `src/main.cpp`.

During the current compatibility stage:

- process entry remains in `src/main.cpp`;
- the legacy `App` implementation lives in `src/app/app.cpp`;
- independently extracted core code lives under `src/core/`;
- source-inspection scripts that verify `App` declarations, command dispatch, constants, or debug helpers must read `src/app/app.cpp`;
- tests for extracted modules should compile and invoke those modules directly.

As more modules are extracted, source-aware tools should accept an explicit source path or source manifest rather than adding new hardcoded paths. A checker that spans multiple subsystems should read each owning file separately and report the owner associated with a missing contract.

Graphical tests also need an explicit video backend. CI runs most deterministic tests with `SDL_VIDEODRIVER=dummy`, but Xvfb tests require `SDL_VIDEODRIVER=x11`; the individual CTest command must override the inherited global environment.

These rules keep recovery guardrails useful throughout the split instead of coupling them to a historical file layout.
