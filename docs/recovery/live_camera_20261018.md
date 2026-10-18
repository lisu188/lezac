# Live Renderer Camera Integration

`GameRenderer` now calls the recovered `FrameCameraOperation` through
`rendering/world_camera.hpp` instead of its geometric `std::clamp` approximation.
This is the actual `WorldPainter::drawWorldView` path used by the App, including
split views and the retained viewport layout after a player's elimination.

The adapter supplies the live coordinates, map dimensions, viewport center,
coarse limits and shake word. It retains original signed visual coordinates,
signed division, coarse and fine offsets, map-index arithmetic and 16-bit shake
addition. The viewport center is rounded to eight pixels, including odd column
counts, as verified by the original width-control fixture. The map offset is
returned without discarding it, although the semantic tile painter does not yet
consume that offset directly.

The camera owns an 80-byte bounded local Pascal stack and its five result words.
It supplies the real recovered stack-check instructions with a valid owned
caller. Reads and writes outside the declared context or stack are rejected.
There is no 1 MiB diagnostic RAM image and no snapshot/copy of the level, actor
vectors, map allocation, backdrop or palette. Rendering still borrows these
live owners through its existing read-only view.

## Validation

- Successful frozen original camera cases: 1,873; all 9,365 result words match
  through the same adapter used by the renderer. The three controlled CRT
  failure cases remain covered by the existing low-level operation test, not
  by the adapter's deliberately valid owned stack.
- Existing camera coverage remains 1,876 cases, 7,504 resumable replays and
  438,001 register comparisons, with the documented intermediate arithmetic-flag
  exclusions unchanged.
- All 60 original viewport-width render cases compare the adapter's five words
  directly with the original endpoints, then compare 3,072,000 rendered pixels
  with zero differences. The 44 width controls also remain unchanged.
- Linux App build succeeds. Seventeen camera, viewport and rendering-ownership
  CTests pass, followed by 36 actual-App, render-boundary, original camera
  mutation, startup-map and frame-sequence checks. These are focused checks,
  not a full local suite.
- The source-ownership inventory includes the live header under rendering;
  the source guardrail self-test passes after that required registration.
- Native MSVC C++latest `/W4 /WX /O2` passes both the unit controls and all
  original-backed camera comparisons. Strict GCC C++23 with AddressSanitizer
  and UndefinedBehaviorSanitizer also passes the original corpus.
- Fresh silent C++ level-7 fight captures were inspected at ticks 140 and 220.
  They are deterministic App harness frames, not manual input or aligned
  original/C++ boss replay. Paired viewport images compare a frozen controlled
  original reference with fresh C++ rendering, not a fresh DOSBox run.

All local build products, expanded fixtures, logs and images are RAM-only while
C: remains above the repository's 90% disk guard. Images and expanded fixtures
are not added to this PR. The pre-existing App `snprintf` diagnostic warning is
unchanged. Full Linux/Windows CI and current-head external review are separate
merge gates.

## Remaining Work

The subsequent [live recovered world renderer](live_raster_20261018.md) now runs
the camera as part of `FrameRenderOperation` on the normal App drawing path.
The remaining-work description below records the isolated camera change's scope;
the raster note describes the current integration and its remaining limits.

This integrates the camera, not the complete recovered raster/copy caller or
work-clock scheduler. The rest of `WorldPainter` remains semantic. Live wrapped
map-plane reads, original sprite descriptor ownership and persistent raster/VGA
buffers still need integration before claiming the original render caller is
the App's production path. Controlled camera and viewport agreement is not
campaign, sound, input, timing or whole-game fidelity.
