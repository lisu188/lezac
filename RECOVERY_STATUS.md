# Recovery Status

Last reviewed: 2026-04-24
Branch: `codex/recovery-monster-contact-evidence`
Baseline: `origin/main`

## Completed This Iteration

- Added a deterministic `--debug-autoplayer level1_bomb_route` command.
- Extended `--debug-autoplayer` with `death_reentry`, `records_flow`, and
  `two_player_route` scenarios so state-2 reentry, record-entry saving, and
  player-2 movement/bomb controls are covered without live input.
- Added `death_visuals`, `level_transition`, and `two_player_progression`
  autoplayer scenarios. These lock provisional state-2 visual cursor playback,
  level-1 completion into level 2, player-2 death/reentry, post-reentry bombs,
  and player-2 scoring.
- Added `portal_weapon_route`, `monster_bomb_reward`, and
  `collapse_playback_route` autoplayer scenarios. These broaden deterministic
  coverage to weapon switching through the left+right chord, medium bomb
  placement through `N`, decoded portal traversal, bomb-killed monster rewards,
  reward pickup sounds, and level-1 collapse playback duration.
- Added `monster_behavior3_multihit`, `monster_behavior4_chase`, and
  `monster_spawner_cycle` autoplayer scenarios. These extend the headless
  matrix to grounded behavior-3 walkers, behavior-4 chase movement, spawner
  slot release/respawn, and multi-hit bomb damage across live update loops.
- Added `monster_spawner_behavior4_level2`,
  `monster_spawner_behavior4_level3`, and
  `monster_behavior4_target_selection` autoplayer scenarios. These extend the
  live monster harness to actual level-2/3 behavior-4 spawner data and
  two-player nearest-target selection across alive/dead player states.
- Extended `--capture-frame-sequence` with
  `monster_spawner_behavior4_level2`,
  `monster_spawner_behavior4_level3`, and
  `monster_behavior4_target_selection`. The frame harness now exports
  deterministic behavior-4 spawn/retarget checkpoints plus manifest metadata
  for player count/dead flags and first-monster position/velocity/behavior.
- Added provisional live state-2 rendering keyed to the recovered `0x4a..0x4f`
  cursor range. It is intentionally documented as `visual_claim=0` until the
  original `DS:c322` frame-table fields are fully interpreted.
- Refactored the game update path so the autoplayer can drive the same movement
  helpers with injected controls instead of relying on live keyboard state.
- Changed `--capture-frame-sequence level1_bomb_route <out-dir>` to reach tile
  `(24,22)` through the autoplayer route instead of teleporting the player.
- Changed the level-1 bomb route autoplayer and frame-sequence capture to place
  the route bomb through the actual `N` key event path instead of calling the
  placement helper directly.
- Added CTest coverage for all autoplayer scenarios and for the behavior-4
  frame-sequence capture scenarios alongside the level-1 route.
- Expanded `tools/capture_original_dosbox_frames.sh` so original DOSBox
  screenshots are renamed to the C++ semantic labels and accompanied by a
  manifest with input/timing settings.
- Hardened the original DOSBox frame-capture route to use the focused
  no-window key path, two `1` taps, original player-1 right on `x`, and held
  player-1 fire on `n`. Local frame inspection now reaches level 1, shows bomb
  placement, and shows explosion playback in the original.
- Extended the guarded explosion process-memory helper to expose and record
  the same start/right/fire route controls in candidate fixture manifests.
- Extended the explosion process-memory helper with timed sample screenshots,
  `sample_summary.tsv`, selected debris/collapse/effect queue-slot detection,
  and selected-base fixture fields for later original oracle promotion.
- Added a guarded instrumented temp-copy freeze mode to the process-memory
  helper. It patches only the temporary `LEZAC.EXE` copy with `EB FE`, records
  MZ-derived file offsets, original/loaded bytes, screenshot hashes, and a
  tail-frame freeze observation flag.
- Added route-state sampling to the process-memory helper. Candidate captures
  now include `route_state_samples.tsv` and `route_state_dumps.txt` with raw
  bytes around known input/player/sound/explosion ranges so future original
  probes can be gated on runtime state instead of fixed sleeps alone.
- Added a separately approved runtime child-memory freeze mode to the same
  helper. It can defer the `EB FE` write until after bomb input and an optional
  decoded queue-score threshold, keeping the temp executable unmodified for
  state-gated reachability probes.
- Extended runtime freeze gates with decoded debris/collapse/effect nonzero
  thresholds and selected queue-base predicates, so probes can wait for visible
  playback-adjacent queue growth rather than the early post-bomb state.
- Added `--runtime-freeze-preset late-collapse` to reuse the current
  playback-adjacent gate defaults and disable timed screenshots unless
  explicitly overridden.
- Added tail-freeze confirmation screenshots to the process-memory helper so
  runs without timed sample screenshots can still detect a frozen final frame.
- Extended `--debug-explosion-playback-oracle` so fixtures can decode selected
  debris/collapse/effect bases while keeping the existing slot-zero defaults.
- Statically disassembled `1000:370e` from the original MZ image and tightened
  the explosion capture/oracle path around the proven one-based queue counters:
  debris records are selected from `0x2093 + 0x0b * DS:207e`, collapse records
  from `0x6611 + 0x0f * DS:2080`, and collapse payload fields now match the
  original flagged-word/magnitude/affected-byte offsets.
- Captured a fresh original level-1 bomb route with the corrected counter logic.
  Frame inspection confirmed visible bomb/explosion/smoke playback, and the
  live collapse record at `DS:6620` matched the deterministic C++ route for
  tile `(24,22)` with offsets `0x0a06..0x0a08`, word `0x0009`, flagged word
  `0x8009`, and affected byte count `4`.
- Extended `--debug-bomb-object-explosion-effects` output and CTest coverage to
  lock those original-matched collapse byte offsets in the C++ model.
- Widened original `DS:2090` process-memory sampling to the `DS:6610` collapse
  queue boundary, then captured a follow-up original route with counter-selected
  debris and collapse slots. The widened candidate parsed with
  `DS:207e=0x00c8`, debris base `DS:292b`, tile index `0x0540`, flagged word
  `0xc004`, lookup byte `0x67`, and collapse base `DS:6620`.
- Added sparse high-counter oracle coverage so counter-derived debris records
  can be tested without checking giant original dumps into the repository.
- Updated `AGENTS.md`, README, and recovery docs with the autoplayer, original
  DOSBox capture, and frame-inspection workflows.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer level1_bomb_route` passed with route length `55`, start
  `(104,168)`, final `(186,168)`, bomb tile `(24,22)`, and route bomb
  placement through the `N` key event path.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer death_reentry` passed with state-2 countdown `60`, lives
  `2`, energy `100`, and reentry confirmed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer death_visuals` passed with state-2 visual frames
  `0x4a -> 0x4b -> 0x4c` and `visual_claim=0`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer level_transition` passed with level-1 completion after
  `101` transition frames and level 2 loaded.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer portal_weapon_route` passed on decoded portal level `3`
  with medium weapon switch, medium bomb placement, portal key `31`, and
  cooldown `30`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer records_flow` passed with temporary record score
  `999999`, level `3`, and name `bot`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_bomb_reward` passed with a bomb-killed monster,
  reward collection, and score delta `3000`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_behavior3_multihit` passed with one-pixel
  behavior-3 movement, first-hit HP `2`, second-hit kill, and reward
  collection.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_behavior4_chase` passed with behavior-4 chase
  movement `2`, timer `1`, and medium-bomb kill.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_spawner_cycle` passed with level-1 spawner slot
  reservation, immediate release on death, and deterministic respawn.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_spawner_behavior4_level2` passed with level-2
  behavior-4 spawner fields `ai0=13 ai1=271 ai2=62 hp=3` and positive `vx8`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_spawner_behavior4_level3` passed with level-3
  behavior-4 spawner fields `ai0=20 ai1=214 ai2=66 hp=4` and diagonal
  `vx8/vy8 = 178/-119`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer monster_behavior4_target_selection` passed with initial
  player-2 targeting, retarget to player 1 when player 2 is dead, and retarget
  back to player 2 when player 1 is dead.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer collapse_playback_route` passed with collapse queue count
  `2` and playback duration `24` frames.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer two_player_route` passed with player-2 movement and one
  player-2 bomb placed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer two_player_progression` passed with player-2 reentry,
  player-2 bomb placement, and player-2 score `1000`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --capture-frame-sequence level1_bomb_route /tmp/lezac-autoplayer-frames`
  passed and wrote seven PPM frames plus `manifest.txt`; route bomb placement
  also uses the `N` key event path.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --capture-frame-sequence monster_spawner_behavior4_level2
  /tmp/lezac-capture-b4-level2` passed and wrote four PPM frames plus
  `manifest.txt` with live spawner/monster fields.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --capture-frame-sequence monster_spawner_behavior4_level3
  /tmp/lezac-capture-b4-level3` passed and wrote four PPM frames plus
  `manifest.txt` with diagonal behavior-4 spawn state.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --capture-frame-sequence monster_behavior4_target_selection
  /tmp/lezac-capture-b4-target` passed and wrote six PPM frames plus
  `manifest.txt` with player-dead flags and retarget direction changes.
- `tools/capture_cpp_frames.sh ./build/lezac_cpp
  /tmp/lezac-autoplayer-frames-wrapper` passed.
- `bash -n tools/capture_original_dosbox_frames.sh` passed. A local DOSBox run
  produced correctly named screenshots and manifest entries. Earlier visual
  inspection showed the old `--window` input path remained on the original
  menu; after switching to focused no-window input with original player-1
  controls, frame inspection confirmed level-1 gameplay, visible bomb
  placement, and visible explosion playback.
- `python3 -m py_compile tools/capture_original_explosion_procmem.py` passed.
- `python3 tools/capture_original_explosion_procmem.py --help` passed and
  lists the route-input options.
- `cmake --build build` passed under WSL after the queue-counter oracle update.
- `ctest --test-dir build -R explosion_playback_oracle --output-on-failure`
  passed: 5/5.
- `ctest --test-dir build -R
  "damage_queues|bomb_object_explosion_effects|collapse_playback_route|frame_sequence_capture_dummy"
  --output-on-failure` passed: 4/4.
- `python3 tools/capture_original_explosion_procmem.py
  /tmp/lezac-counter-selected-20260424-codex-1 . --approve-procmem
  --mode regular --level-start-seconds 1.5 --right-hold-seconds 2.0
  --bomb-hold-seconds 0.25 --sample-seconds 2.5 --sample-interval 0.04
  --route-state-interval 0.25 --sample-screenshot-seconds 0.5,1.0,1.5,2.0`
  passed under WSL/Xvfb. Frame inspection showed the placed bomb, visible
  explosion, and later smoke/collapse playback. The generated candidate parsed
  through `--debug-explosion-playback-oracle` with `visual_claim=0`.
- `./build/lezac_cpp --debug-bomb-object-explosion-effects` passed and printed
  level-1 collapse offsets `0x0a06..0x0a08`, word `0x0009`, flagged word
  `0x8009`, and affected bytes `4`.
- `ctest --test-dir build -R
  "bomb_object_explosion_effects|damage_queues|explosion_playback_oracle"
  --output-on-failure` passed: 7/7.
- `python3 tools/capture_original_explosion_procmem.py
  /tmp/lezac-wide-debris-20260424-codex-1 . --approve-procmem --mode regular
  --level-start-seconds 1.5 --right-hold-seconds 2.0 --bomb-hold-seconds 0.25
  --sample-seconds 2.5 --sample-interval 0.04 --route-state-interval 0.5
  --sample-screenshot-seconds 1.5,2.0` passed under WSL/Xvfb. Frame inspection
  confirmed bomb, explosion, and smoke/collapse playback, and the generated
  candidate parsed with counter-selected debris base `DS:292b`.
- `ctest --test-dir build -R explosion_playback_oracle --output-on-failure`
  passed after adding sparse high-counter fixture coverage: 6/6.
- `tools/compare_original_cpp_frames.sh
  /tmp/lezac-frame-compare-improved-20260424-codex-1812 .
  level1_bomb_route` passed and wrote paired C++/original frames plus diffs.
- `python3 tools/capture_original_explosion_procmem.py
  /tmp/lezac-explosion-procmem-selected-20260424-codex-3 .
  --approve-procmem --mode regular --level-start-seconds 1.5
  --sample-seconds 5.0 --sample-interval 0.04
  --sample-screenshot-seconds 0.5,1.0,1.5,2.0,3.0
  --right-hold-seconds 2.0 --bomb-hold-seconds 0.25` passed under WSL/Xvfb.
  Visual inspection showed bomb placement, visible explosion at `1.5s`, and
  smoke playback at `2.0s`; the generated candidate decoded selected
  `DS:662F` collapse bytes through the C++ oracle with `visual_claim=0`.
- `python3 tools/capture_original_explosion_procmem.py
  /tmp/lezac-route-state-20260424-codex-1 . --approve-procmem --mode regular
  --level-start-seconds 1.5 --sample-seconds 1.0 --sample-interval 0.12
  --route-state-interval 0.25 --sample-screenshot-seconds 0.5` passed under
  WSL/Xvfb. It wrote `route_state_samples.tsv` and `route_state_dumps.txt`;
  frame inspection of `040_sample_0p50s.png` and `090_after_sampling.png`
  confirmed level-1 bomb placement and visible explosion playback. The
  generated candidate still parsed through `--debug-explosion-playback-oracle`
  with `visual_claim=0`.
- Runtime child-memory freeze probes at `1000:3A7E` and `1000:3FA6` both
  patched after bomb input at `0.160s` with route queue score `40`.
  `1000:3A7E` loaded `8b16 -> ebfe` but did not freeze and continued into
  visible explosion playback. `1000:3FA6` loaded `5589 -> ebfe` and froze, but
  frame inspection showed a pre-visible-explosion/armed-bomb state, so this is
  still reachability evidence rather than promoted playback evidence.
- A late-gated runtime child-memory freeze probe at `1000:432A` used queue
  score `150`, selected bases `DS:209e`, `DS:6620`, `DS:c22e`, and nonzero
  debris/collapse/effect counts `28/20/28`. It loaded `5589 -> ebfe` at
  `1.246s` after bomb input without timed screenshots, did not freeze, and the
  final frame inspection still showed visible playback. An earlier `432A` run
  requiring `DS:662F` correctly withheld the patch because this route selected
  `DS:6620`.
- Tuned late-collapse probes at `1000:3BB2` and `1000:3D46` both loaded
  runtime child-memory patches after queue growth and did not freeze while
  visible playback continued. `3BB2` patched at `1.286s` with score `150`;
  `3D46` patched at `1.649s` with score `110`. The first strict preset run for
  `3BB2` correctly withheld the patch because this route's effect nonzero count
  stayed below `20`, so the repeated probe lowered only that threshold to `16`.
- Tail-confirmed early runtime freeze probes mapped the dispatch path:
  `1000:75F1` and `1000:414A` froze on armed-bomb frames before visible
  playback, while `1000:370E` froze on a visible explosion frame. The `370E`
  candidate parsed through the C++ oracle with selected bases `DS:209e`,
  `DS:6611`, and `DS:c22e`, and remains instrumentation evidence with
  `visual_claim=0`.
- Instrumented temp-copy runs patched and loaded freeze loops at `1000:3A7E`,
  `1000:3BB2`, `1000:3FA6`, and `1000:432A`. `1000:3FA6` reliably froze, but
  before visible explosion playback; `1000:3A7E` produced one explosion-frame
  freeze observation but did not reproduce on the next run; `1000:3BB2` and
  `1000:432A` continued through the route. No original fixture was promoted.
- Static disassembly now maps the playback consumer bridge: `1000:45fa..4d3b`
  iterates effect/debris queue records and calls the forward/reverse lane
  passes at `1000:4c96`/`1000:4ca9`. `--debug-damage-queues` locks those
  addresses, the `1000:3a7e`/`1000:3b18` lookup helpers, one-based queue slot
  tags, first-slot lane write offsets, and collapse span weight metadata.
- Runtime child-memory probes now show `1000:4C96` can be patched after queue
  growth but is not reached by the current level-1 route, while `1000:45FA`
  freezes on a visible explosion/playback frame with selected bases `DS:209e`,
  `DS:6620`, and `DS:c22e`. A follow-up `1000:492F` probe froze on the same
  visible playback window with `DS:207e=0x00c7`, explaining the `4C96` skip:
  static code requires `DS:207e >= 0x00c8` before entering that interior path.
  Replaying the earlier high-counter route timing patched `1000:4C96` while
  `DS:207e=0x00c8` and `selected_debris_base=DS:292b`, but the frame sequence
  advanced through the tail screenshots with `instrumented_freeze_observed=0`.
  A route-tuned temp-copy patch at `1000:4B3F` then froze on the visible blast
  frame with `DS:207e=0x00c8`, proving the high-debris interior reaches the
  target-byte sample before the unresolved `4B6A`/`4C20`/`4C75` branch path.
  The helper now emits target fields; a follow-up `1000:4B61` freeze stopped
  at the target-byte gate with target offset `0x0541`, target byte `0x00`,
  word-layer value `0x0000`, and `DS:c204=0x003c`, identifying the next static
  branch as the zero-target path at `1000:4B6A`.
  The helper can now require that decoded target byte before applying a runtime
  child-memory patch; two gated `1000:4B6A` probes reached the later `DS:292b`
  route state with target byte `0x33`, so they intentionally did not patch and
  are recorded as timing evidence rather than executed-branch evidence.
  A faster gated run at
  `/tmp/lezac-4b6a-target-byte-fast-runtime-20260424-codex-1` used
  `--sample-interval 0.005` and froze `01ED:4B6A` after `1.436s`, with
  `DS:207e=0x00c8`, selected debris base `DS:292b`, target byte `0x00`, and
  word-layer value `0x0000`; frozen screenshots matched the visible blast
  frame hash. A compact original-runtime oracle fixture now covers this
  zero-target branch evidence.
  Static disassembly now maps `1000:4C75` as the `[bp-4] > 0` word gate for
  the later `4C96`/`4CA9` lane calls. A first broad `4C75`/`4C96` probe loaded
  patches too late and did not freeze; an early-gated `4C75` rerun froze at
  `01ED:4C75`. Relaxing the `4C96` gate to the durable selected-debris and
  target-byte-zero conditions then froze `01ED:4C96`, and the paired `4CA9`
  probe froze `01ED:4CA9`. Compact original-runtime fixtures now cover the
  word gate plus forward and reverse lane-call evidence. The promoted fixtures
  remain instrumentation evidence with `visual_claim=0`; no live C++ behavior
  changed from this proof yet.
- `./build/lezac_cpp --debug-passable-objects` passed with
  `level1_route_clear=1`.
- `ctest --test-dir build -R "autoplayer|frame_sequence_capture"
  --output-on-failure` passed: 20/20.
- `ctest --test-dir build --output-on-failure` passed under WSL: 84/84.
- `./build/lezac_cpp --validate` passed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --smoke-controls` passed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-level1-frame-inspection` passed.
- Frame inspection performed on generated checkpoints
  `020_level1_tile24_aligned` and `040_level1_tile24_explosion` after converting
  temporary PPM files to PNG for local viewing.
- `git diff --check` passed.

## Remaining Top Gaps

- Confirm the low-word passable-object route and level-1 bomb-route timing
  against original `LEZAC.EXE` with DOSBox frame inspection or debugger/runtime
  evidence.
- Use the now-working original level-1 keyboard route to tie explosion
  screenshots to debugger/process-memory bytes from the relevant
  `1000:3a56..4d3b` execution window, then extend original capture beyond the
  level-1 route.
- Interpret captured state-2 frame-table bytes and confirm the exact visual
  consumption path for the provisional live dead-player renderer.
- Exact explosion/debris/collapse sprite playback around `1000:3a56..4d3b`
  remains blocked on live debugger bytes or an instrumented freeze proving a
  stable stop inside the playback window. Process-memory sampling and
  instrumentation now capture useful original queue bytes and route reachability
  signals, but no promoted fixture yet.
- Semantic meaning of `PROEFS.SON` bytes `+4..+5` remains unknown; current
  diagnostics preserve them as raw fields only.
- Many non-explosion sound callsites still need exact cursor/priority mapping.
- Exact actor update behavior around `1000:6053..777f`, especially original
  contact flags, passability thresholds, tile snapping, behavior-3 ledge/wall
  handling, and behavior-4 collision response.
- The probable contact scanner around `1000:5cb0..604f` needs naming,
  cross-reference mapping, and runtime confirmation before the C++ clearance
  model can be called original-faithful.
- Exact state-2 life-count decrement, `DS:79b9` fallback behavior,
  active-player accounting edge cases, and exact dead-player visual playback
  from original frame bytes.
- Exact two-player panel artwork and full death/reentry presentation.
- Exact sprite frame tables for impact/death/reward frames remain unresolved.
- `GRAN.MST` field semantics remain unknown; consolidation only locks file
  shape and raw/json byte preservation.

## Next Planned Target

Use the reliable original level-1 route to capture explosion/debris/collapse
runtime bytes, then return to DOSBox frame/debugger evidence for behavior-4
movement, targeting, and respawn timing.
