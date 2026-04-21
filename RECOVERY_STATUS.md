# Recovery Status

Last reviewed: 2026-04-21
Branch: `codex/sound-latch-recovery`
Baseline: `f7927e1` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly, gameplay, rendering
  and audio, verification, and integration/docs.
- Re-disassembled the bomb-object scan around `1000:6cb3..6e3f`: it clears
  `DS:2074` and `DS:79ab`, scans the four bomb footprint offsets, marks
  consumed object tiles above `0x6c`, and queues a priority-`3` sound request
  after the scan.
- Routed C++ bomb-object destruction through the recovered request: cursor
  `0x0000` for default consumed object tiles, cursor `0x0012` when any consumed
  object tile is above `0x6c`.
- Preserved the original priority interaction: the priority-`3` object cue
  remains lower than an already-latched explosion direct-sweep cue.
- Added `--debug-bomb-object-sound` and CTest coverage for the default/high
  object cursors and explosion-priority suppression.
- Updated README, Ghidra notes, and a new subagent note with the address range,
  evidence, implementation mapping, validation, and remaining unknowns.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed, with a host clock-skew warning after linking.
- `ctest --test-dir build --output-on-failure` passed: 24/24.
- `ctest --test-dir build --output-on-failure -R bomb_object_sound` passed.
- `./build/lezac_cpp --validate` passed.
- `./build/lezac_cpp --debug-bomb-object-sound` passed.
- `./build/lezac_cpp --debug-explosions` passed.
- `./build/lezac_cpp --debug-bomb-fuse` passed.
- `./build/lezac_cpp --debug-passable-objects` passed.
- `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-ui 3` passed.
- `timeout 10s env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp --smoke-controls` passed.
- `git diff --check` passed.

## Remaining Top Gaps

- Exact actor update behavior around `1000:6053..777f`, especially monster AI
  and object/terrain interactions.
- Exact non-explosion `PROEFS.SON` semantics for bytes `+4..+5` in each
  six-byte step, plus mapping of the remaining non-explosion callsites to
  `DS:2074`/`DS:799f` and event labels.
- Exact post-game presentation details beyond the recovered strings and record
  prompt order: cursor drawing, key wait timing, and completed-game flag side
  effects.
- Explosion, debris, and collapse sprite playback around `1000:3a56..4d3b`;
  current gameplay carries the mapped records but still renders simplified
  effects.
- `GRAN.MST` field semantics.

## Next Planned Target

Broaden the surrounding disassembly for the remaining `1000:165a` callsites,
especially the candidate objective pickup branch near `1000:4b2c..4b32` and
portal/trigger branch near `1000:7381..738c`, before replacing provisional
`playSound(index)` compatibility hooks.
