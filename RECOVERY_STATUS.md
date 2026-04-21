# Recovery Status

Last reviewed: 2026-04-21
Branch: `codex/passable-bomb-controls`
Baseline: `ee67978` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly mapping, gameplay
  fidelity, rendering/audio/assets, verification, and integration/docs.
- Confirmed the baseline build and test suite passed before changes.
- Replaced the live cooldown-gated damage path with recovered per-player damage
  counters. Monster contact, active debris/collapse hazards, and bomb blasts
  now queue bytes for player 1/player 2 and drain them once per update pass,
  matching the documented `DS:79e8`/`DS:79e9` model.
- Preserved original sound ordering for fatal damage: the priority-`4` hurt cue
  is requested for a nonzero damage byte, then the priority-`5` death cue
  replaces it through the existing latch when unsigned byte subtraction wraps.
- Added live-path coverage to `--debug-original-damage-counters`, including
  multi-hit player 1/player 2 drains, underflow death dispatch, and state-2
  hurt-without-energy-subtract behavior.
- Added `--debug-level1-frame-inspection`, a dummy-SDL frame inspection command
  that starts level 1, validates the HUD/world/player frame regions, places a
  bomb with `N`, verifies the bomb/explosion/completion frames change, and
  advances to level 2.
- Added CTest coverage for the level-1 frame inspection command and refreshed
  the agent testing rule to require frame evidence for UI/rendering/DOSBox
  testing whenever possible.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `ctest --test-dir build --output-on-failure -R "level1_frame_inspection|player_damage_sound|original_damage_counters|ui_controls_dummy|bomb_fuse|monster_blast_damage|collision_pushout"` passed: 7/7.
- `ctest --test-dir build --output-on-failure` passed: 37/37.
- `./build/lezac_cpp --validate` passed.
- `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-ui 3` passed.
- `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-controls` passed.
- `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --debug-level1-frame-inspection` passed.
- `git diff --check` passed.

## Open Draft PRs / Integration Queue

- #23 `codex/state2-runtime-frame-oracle-hardening`: state-2 oracle hardening.
- #24 `codex/state2-runtime-frame-oracle-original-fixture`: original state-2
  runtime fixture.
- #25 `codex/proefs-son-field-diagnostics`: sound step field diagnostics.
- #26 `codex/explosion-debug-coverage`: explosion metadata/debug coverage.
- #27 `codex/dosbox-explosion-capture`: explosion playback oracle harness and
  DOSBox capture attempt notes.

These drafts overlap mostly in README, Ghidra notes, CMake, `src/main.cpp`, and
this status file. Rebase this branch after any of them lands.

## Remaining Top Gaps

- Exact actor update behavior around `1000:6053..777f`, especially monster AI,
  object/terrain interactions, and mode-specific animation side effects.
- Exact non-explosion `PROEFS.SON` semantics for bytes `+4..+5` in each
  six-byte step, plus mapping of remaining sound callsites to events.
- Exact state-2 life-count decrement, `DS:79b9` fallback behavior, active-player
  accounting edge cases, and live dead-player visual playback from original
  frame bytes.
- Exact two-player panel artwork and full death/reentry presentation.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`.
- `GRAN.MST` field semantics.

## Next Planned Target

Continue through the actor update window around `1000:6053..777f`. The next
small evidence-backed candidates are monster behavior `3`/`4` collision and AI
details, or the `PROEFS.SON` `+4..+5` unused-field invariant if avoiding overlap
with the open explosion/state-2 PRs is more important.
