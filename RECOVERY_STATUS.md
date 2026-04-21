# Recovery Status

Last reviewed: 2026-04-21
Branch: `codex/sound-latch-recovery`
Baseline: `f7927e1` / `origin/main`

## Completed This Iteration

- Spawned five focused recovery subagents for disassembly, gameplay, rendering
  and audio, verification, and integration/docs.
- Broadened disassembly around remaining `1000:165a` sound-latch candidates.
  The `1000:4b2c..4b32` candidate is inside debris/collapse playback, so it was
  not treated as an objective-pickup mapping.
- Re-disassembled the tile-trigger helper at `1000:5740..586e`: it masks the
  trigger key, saves/restores `DS:2074`, queues cursor `0x0027` at priority
  `6`, then scans 14-byte trigger rewrite records.
- Re-disassembled the portal helper at `1000:5999..5a72`: it scans 7-byte
  portal records for the word-layer key, copies destination coordinates, and
  queues cursor `0x001a` at priority `4`.
- Routed successful C++ tile-trigger activation through the recovered
  request with `requestTileTriggerSound`.
- Routed successful C++ portal transfer through the recovered request with
  `requestPortalTeleportSound`.
- Added `--debug-trigger-sound`, `--debug-portal-sound`, and CTest coverage
  that drives real tiles `0x72` and `0x45` through `updatePortalsAndTriggers`,
  then verifies latched and pumped cursor/priority.
- Updated README, Ghidra notes, and a new subagent note with the address range,
  evidence, implementation mapping, validation, and remaining unknowns.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `ctest --test-dir build --output-on-failure` passed: 26/26.
- `ctest --test-dir build --output-on-failure -R "trigger_sound|portal_sound|portal_cooldowns|trigger_accounting"` passed.
- `./build/lezac_cpp --validate` passed.
- `./build/lezac_cpp --debug-trigger-sound` passed.
- `./build/lezac_cpp --debug-portal-sound` passed.
- `./build/lezac_cpp --debug-trigger-accounting` passed.
- `./build/lezac_cpp --debug-portal-cooldowns` passed.
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

Map the next highest-confidence sound-latch window by proving both the raw
`DS:2074` / `DS:799f` writes and the surrounding gameplay state transition.
The player hit/damage path at `1000:7f84..7f8f` is a better next target than
the rejected `1000:4b2c` debris/collapse candidate, but it needs careful
alignment with the reconstructed damage cooldown semantics before replacing a
compatibility hook.
