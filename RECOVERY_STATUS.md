# Recovery Status

Last reviewed: 2026-04-21
Branch: `codex/state2-runtime-frame-oracle-original-fixture`
Baseline: `ee67978` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for debugger/disassembly mapping,
  gameplay fidelity, rendering/assets, verification, and integration/docs.
- Created a new branch from updated `origin/main`; PR #23 remains open as a
  separate oracle-hardening PR and is not required by this branch.
- Ran baseline build, full CTest, and asset validation before editing.
- Captured a real temp-copy `dosbox-debug` stop from `LEZAC.EXE` using
  `TERM=xterm-256color`, `xvfb-run`, `DEBUG LEZAC.EXE`, PTY debugger commands,
  and xdotool game input.
- Started a one-player game, placed a bomb with `N`, and stopped at runtime
  `01ED:7C89`, the original state-2 countdown path.
- Added `tests/fixtures/dosbox/state2_runtime_frame_oracle_original.txt` with
  runtime `CS=01ED`, `DS=0C8F`, translated breakpoints, `DS:0060`,
  `DS:C21E`, and `DS:C440` memory dumps.
- Registered `state2_runtime_frame_oracle_original` in CTest. The fixture
  validates death cursor `0x45`, frame range `0x4a..0x4f`,
  `first_entry_addr=0xc44a`, first row `10,10,7d,43`, last row
  `10,10,7d,48`, and effect entry 0 `0x0068,0x00a8`, with `visual_claim=0`.
- Updated README and Ghidra notes to describe the original capture while still
  blocking live dead-player rendering on frame-table interpretation and visual
  consumption evidence.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- Baseline `ctest --test-dir build --output-on-failure` passed: 36/36 before
  editing.
- `ctest --test-dir build --output-on-failure -R "state2_runtime_frame_oracle|state2_animation_advance_model|state2_effect_placement_model|player_state2_return_active|original_state2_return_model"` passed: 7/7.
- `ctest --test-dir build --output-on-failure` passed: 37/37.
- `./build/lezac_cpp --validate` passed.
- `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-ui 3` passed.
- `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-controls` passed.
- `git diff --check` passed.

## Remaining Top Gaps

- Interpret the captured state-2 frame-table bytes and confirm the visual
  consumption path before wiring live dead-player rendering.
- Capture additional original stops at `1000:3108`, `1000:6148`, and
  `1000:7ddf`; this fixture stopped at `1000:7c89` with all breakpoints
  translated but does not prove every path was hit.
- Exact actor update behavior around `1000:6053..777f`, especially monster AI,
  object/terrain interactions, and mode-specific animation side effects.
- Exact non-explosion `PROEFS.SON` semantics for bytes `+4..+5` in each
  six-byte step, plus mapping of remaining sound callsites to events.
- Exact original continuous-contact damage cadence, delayed state-2 life-count
  decrement, `DS:79b9` fallback behavior, and active-player accounting edge
  cases.
- Exact two-player panel artwork and full death/reentry presentation.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`.
- `GRAN.MST` field semantics.

## Next Planned Target

Disassemble and/or dump the `1000:6053..6156` frame-table consumer around the
captured `0x4a..0x4f` range. Determine whether the true table row begins at
`DS:c322 + 4 * frame` or an adjacent field inside the same metadata record,
then add a named debug model for the frame-table field layout before changing
live dead-player rendering.
