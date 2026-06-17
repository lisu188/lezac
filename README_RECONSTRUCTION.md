# Larax & Zaco C++ Reconstruction

This directory now contains a C++17/SDL2 source reconstruction of
`LEZAC.EXE`, the DOS shareware game released as "Larax & Zaco" 1.0 in 1996.

This is not a mechanical C decompiler output. The original is a 16-bit
Borland/Turbo Pascal MZ executable, so the port is written as maintainable C++
from Ghidra-assisted disassembly, original strings, original docs, and the
companion data files.

## Build

```sh
cmake -S . -B build
cmake --build build
```

Run from this directory so the shipped original assets are found:

```sh
./build/lezac_cpp
```

The build also copies the shipped resources beside the executable, so running
from the build output directory works. Set `LEZAC_LOAD_JSON_ASSETS=1` to force
the converted JSON compatibility resources for diagnostics.

Validate every decoded original data file without opening a window:

```sh
./build/lezac_cpp --validate
```

Smoke-test SDL window creation and menu/control handling:

```sh
./build/lezac_cpp --smoke-ui 3
./build/lezac_cpp --smoke-controls
./build/lezac_cpp --debug-input-fire-key-model
./build/lezac_cpp --debug-menu-frame-flow
./build/lezac_cpp --debug-autoplayer pause_flow
```

Dump deterministic C++ frames for comparison against original DOSBox captures:

```sh
./build/lezac_cpp --debug-autoplayer level1_bomb_route
./build/lezac_cpp --capture-frame-sequence level1_bomb_route /tmp/lezac-cpp-frames
./build/lezac_cpp --capture-frame-sequence monster_spawner_behavior4_level2 /tmp/lezac-cpp-b4-level2
./build/lezac_cpp --capture-frame-sequence monster_spawner_behavior4_level3 /tmp/lezac-cpp-b4-level3
./build/lezac_cpp --capture-frame-sequence monster_behavior4_target_selection /tmp/lezac-cpp-b4-target
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-frames level1_bomb_route
```

Run the configured validation, debug, and UI smoke tests:

```sh
ctest --test-dir build --output-on-failure
```

Export the decoded background as an indexed-color PPM preview:

```sh
./build/lezac_cpp --export-background /tmp/sfonlef.ppm
```

Dump the current bomb inventory model and export sprite contact sheets:

```sh
./build/lezac_cpp --debug-bombs
./build/lezac_cpp --debug-bonuses
./build/lezac_cpp --debug-bonus-reward-static-model
./build/lezac_cpp --debug-monster-sprite-table-model
./build/lezac_cpp --debug-fixed
./build/lezac_cpp --debug-shipped-file-manifest
./build/lezac_cpp --debug-original-asset-load
LEZAC_LOAD_ORIGINAL_ASSETS=1 ./build/lezac_cpp --validate
./build/lezac_cpp --debug-sounds
./build/lezac_cpp --debug-sound-render
./build/lezac_cpp --debug-sound-cursor-segments
./build/lezac_cpp --debug-son-raw-roundtrip
./build/lezac_cpp --debug-son-step-fields
./build/lezac_cpp --debug-sound-priority-latch
./build/lezac_cpp --debug-sound-selector-map
./build/lezac_cpp --debug-static-sound-contexts
./build/lezac_cpp --debug-remaining-sound-compat-hooks
./build/lezac_cpp --debug-player-damage-sound
./build/lezac_cpp --debug-sound-callsite-oracle tests/fixtures/dosbox/sound_callsite_oracle_synthetic.txt
LEZAC_SOUND_CALLSITE_DEBUG_DRY_RUN=1 tools/capture_original_sound_callsite_debug.sh /tmp/lezac-sound-callsite-debug . player_damage_sound
./build/lezac_cpp --debug-lane-write-static-model
./build/lezac_cpp --debug-lane-write-tag-model
./build/lezac_cpp --debug-actor-contact-static-model
./build/lezac_cpp --debug-original-damage-counters
./build/lezac_cpp --debug-level1-frame-inspection
./build/lezac_cpp --debug-autoplayer level1_bomb_route
./build/lezac_cpp --debug-autoplayer pause_flow
./build/lezac_cpp --debug-autoplayer death_reentry
./build/lezac_cpp --debug-autoplayer death_visuals
./build/lezac_cpp --debug-autoplayer level_transition
./build/lezac_cpp --debug-autoplayer portal_weapon_route
./build/lezac_cpp --debug-autoplayer records_flow
./build/lezac_cpp --debug-autoplayer monster_bomb_reward
./build/lezac_cpp --debug-autoplayer monster_behavior3_multihit
./build/lezac_cpp --debug-autoplayer monster_behavior4_chase
./build/lezac_cpp --debug-autoplayer monster_spawner_cycle
./build/lezac_cpp --debug-autoplayer monster_spawner_behavior4_level2
./build/lezac_cpp --debug-autoplayer monster_spawner_behavior4_level3
./build/lezac_cpp --debug-autoplayer monster_behavior4_target_selection
./build/lezac_cpp --debug-autoplayer collapse_playback_route
./build/lezac_cpp --debug-autoplayer two_player_route
./build/lezac_cpp --debug-autoplayer two_player_death_visuals
./build/lezac_cpp --debug-autoplayer two_player_progression
./build/lezac_cpp --debug-player-state2-death-fields
./build/lezac_cpp --debug-original-state2-return-model
./build/lezac_cpp --debug-original-state2-animation-init
./build/lezac_cpp --debug-original-state2-animation-advance
./build/lezac_cpp --debug-original-state2-visual-row-model
./build/lezac_cpp --debug-original-state2-visual-row-assets
./build/lezac_cpp --capture-state2-visual-row-preview /tmp/lezac-cpp-state2-row-preview
./build/lezac_cpp --capture-state2-visual-row-game-preview /tmp/lezac-cpp-state2-row-game-preview
LEZAC_STATE2_VISUAL_FRAME_CAPTURE_DRY_RUN=1 tools/capture_original_state2_visual_frames.sh /tmp/lezac-original-state2-visual . state2_death_table_consumption
python3 tools/compare_state2_visual_row_game_previews.py /tmp/lezac-state2-visual-compare ./build/lezac_cpp /tmp/lezac-original-state2-visual
./build/lezac_cpp --debug-state2-runtime-frame-oracle tests/fixtures/dosbox/state2_runtime_frame_oracle_synthetic.txt
./build/lezac_cpp --debug-state2-runtime-frame-oracle tests/fixtures/dosbox/state2_runtime_frame_oracle_original.txt
./build/lezac_cpp --debug-explosion-playback-oracle tests/fixtures/dosbox/explosion_playback_oracle_synthetic.txt
./build/lezac_cpp --debug-original-state2-effect-placement
./build/lezac_cpp --debug-player-state2-return-active
./build/lezac_cpp --debug-core-resource-raw-roundtrip
./build/lezac_cpp --debug-record-update /tmp/records_test.dat
./build/lezac_cpp --debug-records-raw-roundtrip
./build/lezac_cpp --debug-record-name-entry /tmp/records_name_test.dat
./build/lezac_cpp --debug-record-name-entry-cursor
./build/lezac_cpp --debug-record-name-entry-repeat /tmp/records_name_repeat_test.dat
./build/lezac_cpp --debug-record-save-failure /tmp/missing-record-dir/records.dat
./build/lezac_cpp --debug-end-flow-records /tmp/end_flow_records.dat
./build/lezac_cpp --debug-end-flow-frame-flow
./build/lezac_cpp --debug-gran
./build/lezac_cpp --debug-gran-raw-roundtrip
./build/lezac_cpp --debug-levels
./build/lezac_cpp --debug-level-raw-roundtrip
./build/lezac_cpp --debug-sprite-transparency
./build/lezac_cpp --debug-sprite-raw-roundtrip
./build/lezac_cpp --debug-sprite-layout-static-model
./build/lezac_cpp --debug-sprite-blit-contract
./build/lezac_cpp --debug-word-layer
./build/lezac_cpp --debug-spawners
./build/lezac_cpp --debug-explosions
./build/lezac_cpp --debug-damage-queues
./build/lezac_cpp --debug-monster-slots
./build/lezac_cpp --debug-monster-motion-model
./build/lezac_cpp --debug-monster-blast-damage
./build/lezac_cpp --debug-bomb-fuse
./build/lezac_cpp --debug-passable-objects
./build/lezac_cpp --debug-trigger-accounting
./build/lezac_cpp --debug-trigger-sound
./build/lezac_cpp --debug-portal-sound
./build/lezac_cpp --debug-portal-cooldowns
./build/lezac_cpp --debug-collision-pushout
./build/lezac_cpp --debug-hud-stats-live
./build/lezac_cpp --debug-two-player-hud-panel
./build/lezac_cpp --capture-frame-sequence level1_bomb_route /tmp/lezac-cpp-frames
./build/lezac_cpp --capture-frame-sequence monster_spawner_behavior4_level2 /tmp/lezac-cpp-b4-level2
./build/lezac_cpp --capture-frame-sequence monster_spawner_behavior4_level3 /tmp/lezac-cpp-b4-level3
./build/lezac_cpp --capture-frame-sequence monster_behavior4_target_selection /tmp/lezac-cpp-b4-target
./build/lezac_cpp --export-sprites BOMOMIMK.SPR /tmp/bomomimk.ppm
```

## Frame Comparison

The reconstruction can emit named 320x200 PPM frames and a `manifest.txt` for
deterministic gameplay scenarios. Current built-in frame exports cover
`level1_bomb_route`, `monster_spawner_behavior4_level2`,
`monster_spawner_behavior4_level3`, and
`monster_behavior4_target_selection`. The level-1 route sequence captures the
menu, level-1 start, the deterministic autoplayer reaching bomb tile `(24,22)`,
bomb placement, and three explosion/playback checkpoints. The behavior-4
sequences capture spawn/retarget checkpoints plus manifest metadata for player
state and first-monster position/velocity/behavior.
Runtime/debugger behavior-4 evidence is normalized with
`--debug-behavior4-runtime-oracle <fixture> [--expect-error]`. The fixture
format records scenario/level, runtime `CS`/`DS`, spawner fields, actor
before/after position and 8.8 velocity, motion timer, target/player-dead state,
and optional raw `DS:` dump rows while anchoring the transcript to
`1000:7A6B..7C2C`, `1000:728C..731B`, and `1000:73E5..741B`.
`--debug-behavior4-static-model` pins the shipped executable bytes at those
six anchor offsets and reports the same target map used by the runtime oracle
and process-memory helper. It is a static byte guardrail with `visual_claim=0`,
not proof of behavior-4 runtime semantics.
Use `tools/capture_original_behavior4_debug.sh` to stage best-effort
DOSBox-debug capture plans for `monster_spawner_behavior4_level2`,
`monster_spawner_behavior4_level3`, and `monster_behavior4_target_selection`.
It writes a `candidate_fixture.txt` skeleton and
`debugger_commands_runtime.txt`; when a live run exposes `runtime_cs` or
`runtime_ds`, the helper copies those values into the manifest/raw dump and
expands the debugger command plan to the observed runtime segment.
Because this DOSBox-debug build can reach the prompt but still fail to submit
commands, behavior-4 anchors also have a guarded process-memory fallback:

```sh
LEZAC_BEHAVIOR4_APPROVE_PROCMEM=1 \
LEZAC_BEHAVIOR4_APPROVE_RUNTIME_INSTRUMENTATION=1 \
  tools/capture_original_behavior4_procmem.sh \
  /tmp/lezac-behavior4-procmem . behavior4_branch_start
```

The wrapper can freeze `spawner_loop_start`, `spawner_loop_end`,
`behavior4_branch_start`, `behavior4_branch_end`, `integration_8_8_start`, or
`integration_8_8_end`, emits `behavior4_procmem` manifests plus a fill-in
candidate fixture, and keeps `visual_claim=0` until semantic behavior-4 rows
are captured and accepted by `--debug-behavior4-runtime-oracle`. Live capture
status lines include `freeze_runtime_patch_applied=` and `freeze_observed=`, so
route-sweep manifests can distinguish patch-loaded no-freeze captures directly.
Use `tools/sweep_original_behavior4_procmem_routes.py` to plan or execute a
guarded route/timing matrix around that helper. Its default dry-run covers
`behavior4_branch_start` and `integration_8_8_start` across the reviewed
behavior-4 route hypotheses with both pre-bomb and pre-route runtime-freeze
timing; add `--all-targets` only when the host is ready to spend captures on
all six anchors.
Summarize a completed sweep with
`python3 tools/summarize_behavior4_procmem_route_sweep.py <manifest>`. The
summary reports completed captures, observed freezes, patch-loaded no-freeze
candidates, total `runtime_patches_applied=`, ready/incomplete/missing
candidate counts, per-capture oracle commands, and `--require-ready`,
`--require-observed-freeze`, `--require-runtime-patch`, and
`--require-environment-preflight` gates. Add `--write-ready-manifest <path>` to
hand ready behavior-4 candidates to the generic
`tools/run_debug_capture_ready_manifest.py` oracle runner.
Three 2026-06-17 WSL smoke captures for `behavior4_branch_start` loaded the
`01ED:728C` runtime patch but did not observe a freeze: before-bomb routes
`x:2.00` and `x:5.00,m:0.50,x:2.00`, plus before-route route `x:2.00`. Each
reported `runtime_patches_applied=1`, `observed_freezes=0`,
`patched_no_freeze_candidates=1`, and `ready_candidates=0`; treat them as
negative route evidence, not promotion fixtures.
Live behavior-4, actor-update, contact-scanner, and visual-table DOSBox-debug
helpers run
`tools/preflight_original_evidence_environment.py --require-debug-capture`
before launching DOSBox-debug, record `environment_preflight=` in the manifest,
and keep the preflight output in `environment_preflight.log`. Use the matching
`LEZAC_*_DEBUG_SKIP_ENVIRONMENT_PREFLIGHT=1` variable only for intentional
forensic reruns on an already-verified host. Use
`tools/capture_original_visual_table_debug.sh <out_dir> [asset_dir]
state2_death_table_consumption` to stage the next state-2 renderer-facing
fixture for `--debug-visual-table-oracle`.
Use `tools/capture_original_state2_visual_frames.sh <out_dir> [asset_dir]
state2_death_table_consumption` for the paired original-frame bundle expected
by `tools/compare_state2_visual_row_game_previews.py`. The helper writes a
manifest and six-frame plan for `state2_game_4a..4f`, labels the route
`debugger_seeded`, and keeps `visual_claim=0` until the DOSBox/debugger-seeded
screenshots are actually captured and compared.
Checked-in original visual-table fixtures use the
`visual_table_oracle_original*.txt` naming convention so the fixture expectation
and optional-original guardrails pick them up automatically. The current
original fixture is `visual_table_oracle_original_state2_runtime.txt`,
normalized from the original state-2 runtime stop and still `visual_claim=0`.
It validates row byte 3 as the `BOMOMIMK` sprite-index candidate range
`0x43..0x48` for frames `0x4a..0x4f`. The row-model diagnostic now keeps row
bytes 0 and 1 as draw-offset candidates with raw bytes `0x10,0x10` / pixels
`16,16`, keeps row byte 2 as the stable raw constant `0x7d`, and keeps row byte
3 as the sprite-index range `0x43..0x48`; full live death/reentry art still
requires paired original-frame evidence before it can be claimed.
Summarize any one of those capture directories with
`python3 tools/summarize_debug_capture.py <capture_dir>`. The summary reports
`candidate_status=ready|incomplete|missing|none`, missing fixture fields,
placeholder markers, the preflight state, and the exact runtime-oracle command.
Add `--require-ready --require-environment-preflight` when a promotion script
should fail until the capture is backed by a completed fixture and verified
host preflight.
For a whole WSL evidence batch, use
`python3 tools/summarize_debug_capture_batch.py <batch_dir>`. It recursively
finds supported debug-capture manifests, counts ready/incomplete/missing
candidates, reports unsupported manifests, and can write a compact
ready-candidates manifest with `--write-ready-manifest <path>`.
Review or execute that manifest with
`python3 tools/run_debug_capture_ready_manifest.py <ready_manifest> --dry-run`
or omit `--dry-run` on a prepared host. The runner validates oracle/flag pairs,
can require per-candidate `environment_preflight=ok`, writes optional logs, and
can leave a result manifest for later promotion review.
Summarize that result manifest with
`python3 tools/summarize_debug_capture_ready_results.py <result_manifest>`;
use `--require-success --require-executed --require-source-environment-preflight`
before promoting generic behavior-4, actor-update, contact-scanner, or
visual-table runtime evidence. `tools/check_debug_capture_ready_pipeline.py`
exercises this full batch-summary, ready-runner, and result-summary handoff with
synthetic data.
Actor/contact update evidence is normalized with
`--debug-actor-update-runtime-oracle <fixture> [--expect-error]`. Its synthetic
fixtures cover parser behavior only: runtime captures still need to prove exact
contact scanner and actor-update behavior around `1000:5CB0..604F` and
`1000:6053..777F`. The oracle now reports optional `dispatch_gates=` evidence
when fixtures include breakpoints for the mapped gate targets. Use
`tools/capture_original_actor_update_debug.sh` to stage
best-effort DOSBox-debug capture plans for `object_collision_jump_live`,
`monster_contact_damage_live`, and `monster_behavior4_chase`; it writes a
`candidate_fixture.txt` skeleton that must be filled from runtime output before
promotion. When a live DOSBox-debug launch reaches the debugger prompt, the
helper copies observed `runtime_cs`/`runtime_ds` values into `manifest.txt` and
`raw_debugger_dump.txt`, even if command submission later times out. It also
writes `debugger_commands_runtime.txt` with concrete breakpoint/dump commands
for the observed runtime segments.
Scanner-only transcripts can also be checked with
`--debug-contact-scanner-runtime-oracle <fixture> [--expect-error]`; this keeps
`1000:5CB0..604F` overlap/contact flag evidence separate from full actor update
state when a debugger stop only captures the scanner window. Use
`tools/capture_original_contact_scanner_debug.sh` to stage the matching
DOSBox-debug plan for `monster_contact_damage_live`, `object_collision_jump_live`,
or `monster_behavior4_chase`; it writes a `candidate_fixture.txt` skeleton that
must be filled from runtime output before promotion, and it preserves prompt
`runtime_cs`/`runtime_ds` metadata plus `debugger_commands_runtime.txt` the
same way as the actor-update helper.
Because this DOSBox-debug build still does not reliably submit debugger
commands with Return, reachability probes can use the guarded process-memory
wrapper:

```sh
LEZAC_ACTOR_CONTACT_APPROVE_PROCMEM=1 \
LEZAC_ACTOR_CONTACT_APPROVE_RUNTIME_INSTRUMENTATION=1 \
  tools/capture_original_actor_contact_procmem.sh \
  /tmp/lezac-actor-contact-procmem . actor_update_start
```

The wrapper reuses the proven child-process memory scanner, patches only the
temporary DOSBox-debug child process, and records `visual_claim=0` instrumentation
evidence. Direct live runs execute the shared process-memory environment
preflight first and record `environment_preflight=` in the manifest; route and
dispatch sweeps pass `LEZAC_ACTOR_CONTACT_PROCMEM_SKIP_ENVIRONMENT_PREFLIGHT=1`
to child captures after their top-level preflight succeeds. Supported targets
are `actor_update_start`, `actor_update_end`,
`actor_update_gate5`, `actor_update_gate5_integration`,
`actor_update_gate5_exit`, `actor_update_gate6`, `contact_scanner_callsite`,
`contact_scanner_start`, and `contact_scanner_end`.
The actor/contact sound capture targets have a separate process-memory fallback
for hosts where DOSBox-debug reaches the prompt but cannot submit commands:

```sh
LEZAC_SOUND_CALLSITE_APPROVE_PROCMEM=1 \
LEZAC_SOUND_CALLSITE_APPROVE_RUNTIME_INSTRUMENTATION=1 \
  tools/capture_original_sound_callsite_procmem.sh \
  /tmp/lezac-sound-callsite-procmem . contact_scanner_runtime_sound
```

It can freeze `contact_scanner_runtime_sound` at `1000:5E81` plus the
actor-update candidates `actor_update_runtime_cursor_0024_sound` at
`1000:6844`, `actor_update_runtime_cursor_0035_sound` at `1000:6924`, and
`actor_update_runtime_cursor_0021_sound` at `1000:7386`. Each capture writes a
`sound_callsite_procmem` manifest/raw output plus a fill-in sound-callsite
candidate fixture, preserves `visual_claim=0`, and still requires a completed
`sound_callsite_oracle_original*.txt` fixture before any cursor/priority
semantic promotion.
Use the route-sweep planner before a live attempt when the contact route needs
tuning:

```sh
python3 tools/sweep_original_sound_callsite_routes.py \
  /tmp/lezac-sound-callsite-routes . --dry-run
python3 tools/sweep_original_sound_callsite_routes.py \
  /tmp/lezac-sound-callsite-routes . \
  --approve-procmem --approve-runtime-instrumentation \
  --timing before_route --route x:5.00,m:0.50,x:2.00
python3 tools/sweep_original_sound_callsite_routes.py \
  /tmp/lezac-sound-callsite-all-targets . --dry-run --all-targets \
  --timing before_route --route x:2.00,c:0.50
```

The planner emits `sound_callsite_route_sweep` manifests and forwards each
route to `tools/capture_original_sound_callsite_procmem.sh` with the matching
`LEZAC_SOUND_CALLSITE_ROUTE_STEPS` and freeze-timing environment. The default
run keeps `contact_scanner_runtime_sound` as the first queued target;
`--all-targets` expands the same route/timing matrix across all four
actor/contact sound targets and prefixes each capture label with the target
name for summary triage.
Summarize a completed sweep with
`python3 tools/summarize_sound_callsite_route_sweep.py <manifest>`. The
summary reports completed captures, observed freezes, ready/incomplete/missing
candidate counts, per-capture `--debug-sound-callsite-oracle` commands, and
`--require-ready`, `--require-observed-freeze`, and
`--require-environment-preflight` gates. Add `--write-ready-manifest <path>` to
hand ready sound-callsite candidates to
`tools/run_debug_capture_ready_manifest.py`; the generic runner and result
summary now accept `sound_callsite` with `--debug-sound-callsite-oracle`.
`tools/check_visual_claim_guardrail.py` requires every checked-in DOSBox oracle
fixture to carry an explicit `visual_claim=0` or `visual_claim=1` line so
instrumentation-only evidence cannot be promoted by omission. Promotions to
`visual_claim=1` must also be recorded in
`docs/recovery/visual_claim_promotions.md` with original, C++, comparison frame
artifacts, and a checked-in frame-compare bundle whose summary reports
`promotion_ready=1`. The guardrail self-test exercises the promoted-fixture path
so missing checked-in artifacts or unready bundles are rejected before any
fixture is promoted.
`tools/check_runtime_evidence_guardrail.py` separately tracks checked-in
original-runtime DOSBox fixtures in
`docs/recovery/runtime_evidence_ledger.md`: those captures must remain
`temp_copy=1`, carry runtime `CS`/`DS`, and stay `visual_claim=0` until a
separate visual promotion proves exact presentation. Ledger entries point to
`docs/recovery/original_runtime_fixture_notes.md`, and the checker requires the
supporting note to name the fixture explicitly.
`contact_scanner_callsite` maps the static near call at `1000:6555` that targets
`1000:5CB0`; `tools/check_actor_contact_callsite_scan.py` verifies that callsite
and the entry/return bytes against `LEZAC.EXE`.
`tools/check_actor_contact_callsite_context.py` also pins the surrounding gate:
`1000:654E` compares `[bp-31h]` with `06`, `1000:6552` skips to `1000:655B`,
and the matching path runs `push bp; call 1000:5CB0` before jumping to
`1000:73E5`. It also checks the neighboring `05` gate at `1000:65A2`, whose
live path can enter shared integration through `1000:65D7` or jump to
actor-update end `1000:777F`, plus the later `05` exit gate at `1000:7595`.
`--debug-actor-contact-static-model` mirrors those original-byte checks in the
C++ diagnostic binary: scanner entry/return, actor-update entry/return, all
three `[bp-31h]` gates, `scanner_call_count=1`, the sole scanner callsite in
the `06` gate context, and the direct integration jumps.
The wrapper writes
`<target>_runtime_candidate.txt` with the runtime metadata plus raw route-state
dumps; the candidate is a fill-in scaffold until semantic actor/contact records
are decoded. Gate-target candidates include the required actor-update anchor
set and a `dispatch_gate_candidate=<label>` hint for later `dispatch_gates=` oracle
promotion. Use `LEZAC_ACTOR_CONTACT_ROUTE_STEPS` with comma-separated
`key:seconds` holds to tune a route, for example
`LEZAC_ACTOR_CONTACT_ROUTE_STEPS=x:1.0,n:0.2,z:0.5`. Set
`LEZAC_ACTOR_CONTACT_RUNTIME_FREEZE_BEFORE_ROUTE=1` when probing helpers that
may only execute during the movement/contact route instead of after route
positioning.

Use the route-sweep helper to plan or run several guarded actor/contact probes
with one manifest. The default target is `contact_scanner_start` and the default
timing matrix covers both post-route and pre-route freeze timing. Live sweeps
run `tools/preflight_original_evidence_environment.py --probe-wsl
--require-wsl-bash-on-windows --require-procmem-capture` once before launching
captures; use `--skip-environment-preflight` only for intentional reruns on an
already-verified host. Add `--all-targets` when a focused route/timing pair
should be tried against every mapped actor/contact process-memory target in the
same low-level sweep. All-target manifests record `target=all`,
`targets=9`, `target_names=...`, and target-prefixed capture labels:

```sh
python3 tools/sweep_original_actor_contact_routes.py \
  /tmp/lezac-actor-contact-route-sweep . --dry-run
python3 tools/sweep_original_actor_contact_routes.py \
  /tmp/lezac-actor-contact-route-sweep-all . --dry-run --all-targets \
  --timing before_bomb --route x:2.00
python3 tools/sweep_original_actor_contact_routes.py \
  /tmp/lezac-actor-contact-route-sweep . \
  --target contact_scanner_start --timing before_route \
  --route x:8.00 --route x:5.00,m:0.50,x:4.00 \
  --approve-procmem --approve-runtime-instrumentation
```

Use the dispatch-gate sweep planner when the goal is to exercise every mapped
actor-update gate in one pass. Its default target set is `actor_update_gate5`,
`actor_update_gate5_integration`, `actor_update_gate5_exit`,
`actor_update_gate6`, and `contact_scanner_callsite`. The planner performs one
top-level environment preflight and passes `--skip-environment-preflight` to
child actor/contact sweeps so the same run does not repeat host checks for every
target. Use `--target-set all` to expand every process-memory target supported
by `tools/capture_original_actor_contact_procmem.sh`, including actor-update
entry/exit and contact-scanner start/end:

```sh
python3 tools/sweep_original_actor_dispatch_gates.py \
  /tmp/lezac-actor-dispatch-gates . --dry-run
python3 tools/sweep_original_actor_dispatch_gates.py \
  /tmp/lezac-actor-dispatch-gates-all . --dry-run --target-set all
python3 tools/sweep_original_actor_dispatch_gates.py \
  /tmp/lezac-actor-dispatch-gates . --timing before_route \
  --approve-procmem --approve-runtime-instrumentation
python3 tools/summarize_actor_dispatch_gate_sweep.py \
  /tmp/lezac-actor-dispatch-gates/manifest.txt
python3 tools/summarize_actor_dispatch_gate_sweep.py \
  /tmp/lezac-actor-dispatch-gates/manifest.txt \
  --write-ready-manifest /tmp/lezac-actor-dispatch-gates/ready_manifest.txt
python3 tools/run_actor_dispatch_ready_manifest.py \
  /tmp/lezac-actor-dispatch-gates/ready_manifest.txt --dry-run
python3 tools/summarize_actor_dispatch_ready_results.py \
  /tmp/lezac-actor-dispatch-gates/oracle-results.txt \
  --require-success --require-executed
```

The summary prints `environment_preflight=`, `child_environment_preflights=`,
`dispatch_gate_freezes=`, `observed_dispatch_gates=`, `ready_candidates=`,
`incomplete_candidates=`, `missing_candidates=`, `candidate_status=`,
`candidate_missing=`, `oracle=`, `oracle_flag=`, and `oracle_command=` so the
candidate fixture can be completed and routed to the matching runtime oracle
without guessing. `dispatch_gate_freezes=` counts freeze events at mapped
targets, while `observed_dispatch_gates=` lists unique mapped target names.
Detail rows include `dispatch_gate_candidate=` to separate mapped actor/contact
dispatch gates from broader route-freeze probes. Use
`candidate_placeholders=1` as a warning that a generated skeleton still has
fill-in markers in comments or active records. Use `--oracle-binary` when the
C++ executable is not `./build/lezac_cpp`, `--require-ready` when a script
should fail until all observed freeze candidates are promotable, and
`--require-dispatch-gate-freeze` when a live sweep must prove that at least one
mapped dispatch-gate target actually froze before the result is treated as
branch-reachability evidence. Contact-scanner candidates only become ready when
`subject_actor`/`other_actor` include `w` and `h`, and `contact_scan` includes
`overlap_x` and `overlap_y`, matching the real C++ oracle parser. Add
`--require-environment-preflight` when promotion should fail unless the source
sweep recorded a successful host preflight. Use `--write-ready-manifest <path>`
to emit a promotion manifest containing only ready candidate fixtures and their
oracle commands plus the source preflight status. Use
`tools/run_actor_dispatch_ready_manifest.py <path>
--dry-run` to review that handoff, or omit `--dry-run` in a prepared
WSL/native environment to execute the listed C++ oracles with per-candidate
timeouts and optional logs. Add `--require-source-environment-preflight` when
the runner or later result summary should reject ready manifests whose source
sweep did not record `source_environment_preflight=ok`. The runner validates
fixture paths and oracle/flag pairs before launching commands;
`--allow-missing-fixtures` is only for dry-run forensic review after moving
manifests between machines. Add
`--write-result-manifest <path>` to leave a key/value audit trail for planned
or executed oracle commands, including the source preflight state. Result
manifests and oracle logs are refused inside the repository unless
`--allow-repo-output` is passed deliberately.
Use `tools/summarize_actor_dispatch_ready_results.py <path>` to summarize that
audit trail, and add `--require-success --require-executed` when promotion
should fail unless every oracle actually ran and passed. The CTest helper
`tools/check_actor_dispatch_ready_pipeline.py` exercises this full handoff with
a synthetic ready candidate and fake oracle.
`tools/check_actor_contact_evidence_map.py` verifies the actor/contact recovery
handoff stays linked across docs, helper target maps, oracle flags, fixtures,
and CTest coverage.

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer level1_bomb_route
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-frames level1_bomb_route
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-b4-level2 monster_spawner_behavior4_level2
./build/lezac_cpp --debug-behavior4-static-model
./build/lezac_cpp --debug-behavior4-runtime-oracle \
  tests/fixtures/dosbox/behavior4_runtime_oracle_synthetic.txt
./build/lezac_cpp --debug-actor-update-runtime-oracle \
  tests/fixtures/dosbox/actor_update_runtime_oracle_synthetic.txt
./build/lezac_cpp --debug-contact-scanner-runtime-oracle \
  tests/fixtures/dosbox/contact_scanner_runtime_oracle_synthetic.txt
python3 tools/check_actor_update_runtime_oracle_fixtures.py \
  tests/fixtures/dosbox --cmake CMakeLists.txt --source src/main.cpp
python3 tools/check_contact_scanner_runtime_oracle_fixtures.py \
  tests/fixtures/dosbox --cmake CMakeLists.txt --source src/main.cpp
LEZAC_CONTACT_SCANNER_DEBUG_DRY_RUN=1 \
  tools/capture_original_contact_scanner_debug.sh \
  /tmp/lezac-contact-scanner-debug . monster_contact_damage_live
LEZAC_ACTOR_UPDATE_DEBUG_DRY_RUN=1 \
  tools/capture_original_actor_update_debug.sh \
  /tmp/lezac-actor-update-debug . object_collision_jump_live
LEZAC_BEHAVIOR4_DEBUG_DRY_RUN=1 \
  tools/capture_original_behavior4_debug.sh \
  /tmp/lezac-behavior4-debug . monster_behavior4_target_selection
LEZAC_BEHAVIOR4_PROCMEM_DRY_RUN=1 \
  tools/capture_original_behavior4_procmem.sh \
  /tmp/lezac-behavior4-procmem . behavior4_branch_start
python3 tools/sweep_original_behavior4_procmem_routes.py \
  /tmp/lezac-behavior4-procmem-sweep . --dry-run --all-targets \
  --timing before_bomb --route x:2.00
python3 tools/summarize_behavior4_procmem_route_sweep.py \
  /tmp/lezac-behavior4-procmem-sweep/manifest.txt \
  --require-runtime-patch --require-observed-freeze
python3 tools/summarize_behavior4_procmem_route_sweep.py \
  /tmp/lezac-behavior4-procmem-sweep/manifest.txt \
  --require-ready --write-ready-manifest /tmp/lezac-behavior4-ready.txt
python3 tools/sweep_original_sound_callsite_routes.py \
  /tmp/lezac-sound-callsite-routes . --dry-run \
  --target actor_update_runtime_cursor_0035_sound \
  --timing before_route --route x:2.00,c:0.50
python3 tools/summarize_sound_callsite_route_sweep.py \
  /tmp/lezac-sound-callsite-routes/manifest.txt \
  --require-observed-freeze
python3 tools/summarize_sound_callsite_route_sweep.py \
  /tmp/lezac-sound-callsite-routes/manifest.txt \
  --require-ready --write-ready-manifest /tmp/lezac-sound-callsite-ready.txt
python3 tools/run_debug_capture_ready_manifest.py \
  /tmp/lezac-behavior4-ready.txt --dry-run
python3 tools/run_debug_capture_ready_manifest.py \
  /tmp/lezac-sound-callsite-ready.txt --dry-run
```

Actor/contact fixture checkers keep the synthetic/malformed parser fixtures
fixed, but they also accept future
`actor_update_runtime_oracle_original*.txt` and
`contact_scanner_runtime_oracle_original*.txt` captures when those fixtures
parse successfully and have matching CTest coverage. Checked-in original
fixtures are still governed by the runtime evidence ledger and stay
`visual_claim=0` until visual evidence is promoted separately.
The behavior-4 fixture checker follows the same convention for future
`behavior4_runtime_oracle_original*.txt` captures.
The visual-table fixture checker does the same for
`visual_table_oracle_original*.txt` captures; the current checked-in original
fixture is `visual_table_oracle_original_state2_runtime.txt`, normalized from
the original state-2 runtime stop and still `visual_claim=0`. It validates
`sprite_source=row_byte3` for the captured state-2 table rows `0x4a..0x4f`
without promoting the live renderer.
The sound-callsite checker accepts future `sound_callsite_oracle_original*.txt`
captures under the same valid-oracle and CTest-coverage rule.
`tools/check_optional_original_oracle_fixtures.py` keeps these five runtime
oracle lanes aligned so future original fixtures remain valid-only, covered by
CTest, and explicitly `visual_claim=0`.

Original-game captures are best-effort because DOSBox timing, focus, and
keyboard injection vary by environment. The current DOSBox screenshot driver is
still route-specific: it runs `LEZAC.EXE` from a temporary copy under
DOSBox/Xvfb, uses DOSBox's Ctrl-F5 screenshot command at matching level-1 route
checkpoints, renames the screenshots to the same semantic labels used by the
C++ route sequence, and writes `manifest.txt` and `original_capture.log` next
to the screenshots:

```sh
tools/capture_original_dosbox_frames.sh /tmp/lezac-original-frames .
```

Always inspect the resulting original frames before comparing them. If local
DOSBox input stays on the menu or misses a checkpoint, rerun with adjusted
`LEZAC_ORIGINAL_STARTUP_SECONDS`, `LEZAC_ORIGINAL_START_KEY`,
`LEZAC_ORIGINAL_START_TEXT`, or `LEZAC_ORIGINAL_ROUTE_RIGHT_SECONDS`.

Compare paired frames with:

```sh
tools/frame_compare.py \
  /tmp/lezac-cpp-frames/010_level1_start.ppm \
  /tmp/lezac-original-frames/<dosbox-screenshot>.png \
  --diff /tmp/lezac-frame-diff.ppm
```

`tools/frame_compare.py` reads PPM/PNM and uncompressed BMP files without extra
dependencies. If Pillow is installed, it can also read DOSBox PNG screenshots.
When one frame is an integer-scaled version of the other, such as DOSBox
640x400 screenshots compared with 320x200 C++ frames, the larger frame is
downscaled automatically before metrics are computed.
For exact oracle work, compare semantic checkpoints rather than elapsed frame
numbers.

On Windows, the native validation helper configures the local Visual Studio
Build Tools plus the vcpkg SDL2 package and removes duplicate `PATH`/`Path`
environment entries before invoking MSBuild:

```powershell
powershell -ExecutionPolicy Bypass -File tools/run_native_windows_validation.ps1 `
  -BuildDir build-win-codex-vs3 -Configuration Debug
```

The helper copies the validated vcpkg `SDL2.dll` next to the generated
`lezac_cpp.exe` after the build and prints `runnable_exe=...`; launch that path
directly on Windows to avoid missing-runtime-DLL dialogs.
The CMake install target now stages the executable, `SDL2.dll` on Windows, and
all original/JSON assets into one runnable directory:

```sh
cmake --install build-win-codex-vs3 --config Debug --prefix /tmp/lezac-install
```

CTest `install_layout_smoke` exercises that install layout and runs
`lezac_cpp --validate` from the installed directory.

Before running original DOSBox or process-memory captures on a new host, use the
environment preflight to verify assets and capture tools:

```sh
python3 tools/preflight_original_evidence_environment.py . --probe-wsl
python3 tools/preflight_original_evidence_environment.py . --require-original-capture
python3 tools/preflight_original_evidence_environment.py . --require-procmem-capture
```

The non-require mode reports missing tools without failing. The require modes
fail fast when the matching DOSBox/Xvfb/xdotool toolchain or the shipped asset
files are missing, so long route sweeps do not start on an unprepared machine.
`--probe-wsl` reports both `wsl_probe` and `wsl_bash_probe`; a host with
`wsl.exe` installed but no default Linux distribution reports
`wsl_bash_reason=no_default_distro`, which blocks original DOSBox/debugger
capture until a distro with the capture tools is installed.
`--require-wsl-bash-on-windows` turns that probe into a Windows-only failure
when `wsl -e bash -lc true` cannot start; native Linux/WSL hosts ignore the
requirement.
The debugger capture modes include the `timeout` command used by the
DOSBox-debug shell helpers. The process-memory mode follows the actual debug
wrapper dependency set: `bash`, DOSBox, DOSBox-debug, direct `Xvfb`, `xdotool`,
`python3`, `pgrep`, `zutty`, and `script`.

For explosion/debris/collapse process-memory probes, preflight freeze patches
before running DOSBox. This verifies the shipped `LEZAC.EXE` file offset,
expected original bytes, trampoline bytes, and scratch/body addresses without
launching DOSBox or reading `/proc/<pid>/mem`:

```sh
python3 tools/check_explosion_lane_result_preflight.py .
python3 tools/check_explosion_lane_result_wrapper.py .
python3 tools/capture_original_lane_write_runtime.py --preflight-only
python3 tools/capture_original_lane_write_runtime.py /tmp/lezac-lane-write-runtime . \
  --dry-run --skip-oracle
python3 tools/sweep_original_lane_write_routes.py /tmp/lezac-lane-write-route-sweep . \
  --dry-run --skip-oracle \
  --route x:2.00,c:0.50 --route x:1.50,z:0.50
python3 tools/summarize_lane_write_route_sweep.py \
  /tmp/lezac-lane-write-route-sweep/manifest.txt \
  --require-ready \
  --write-ready-manifest /tmp/lezac-lane-write-route-sweep/ready_manifest.txt
python3 tools/run_lane_write_ready_manifest.py \
  /tmp/lezac-lane-write-route-sweep/ready_manifest.txt --dry-run
python3 tools/run_lane_write_ready_manifest.py \
  /tmp/lezac-lane-write-route-sweep/ready_manifest.txt \
  --log-dir /tmp/lezac-lane-write-route-sweep/logs \
  --write-result-manifest /tmp/lezac-lane-write-route-sweep/result_manifest.txt
python3 tools/summarize_lane_write_ready_results.py \
  /tmp/lezac-lane-write-route-sweep/result_manifest.txt \
  --require-success --require-executed
python3 tools/capture_original_lane_result_runtime.py --preflight-only
python3 tools/capture_original_lane_result_runtime.py /tmp/lezac-lane-result-runtime . \
  --dry-run --skip-oracle
python3 tools/capture_original_lane_result_runtime.py /tmp/lezac-lane-result-runtime . \
  --dry-run --skip-oracle --offset forward
python3 tools/capture_original_lane_result_runtime.py /tmp/lezac-lane-result-runtime . \
  --dry-run --skip-oracle --offset reverse

python3 tools/capture_original_lane_result_runtime.py /tmp/lezac-lane-result-runtime . \
  --dry-run --skip-oracle --offset forward \
  --route-step x:2.00 --route-step c:0.50

python3 tools/sweep_original_lane_result_routes.py /tmp/lezac-lane-result-route-sweep . \
  --dry-run --skip-oracle \
  --route x:2.00,c:0.50 --route x:1.50,z:0.50
python3 tools/sweep_original_lane_result_routes.py /tmp/lezac-lane-result-route-sweep . \
  --dry-run --cpp-exe ./build/lezac_cpp --offset forward
python3 tools/summarize_lane_result_route_sweep.py \
  /tmp/lezac-lane-result-route-sweep/manifest.txt
python3 tools/summarize_lane_result_route_sweep.py \
  /tmp/lezac-lane-result-route-sweep/manifest.txt \
  --require-ready \
  --write-ready-manifest /tmp/lezac-lane-result-route-sweep/ready_manifest.txt
python3 tools/run_lane_result_ready_manifest.py \
  /tmp/lezac-lane-result-route-sweep/ready_manifest.txt --dry-run
python3 tools/run_lane_result_ready_manifest.py \
  /tmp/lezac-lane-result-route-sweep/ready_manifest.txt \
  --log-dir /tmp/lezac-lane-result-route-sweep/logs \
  --write-result-manifest /tmp/lezac-lane-result-route-sweep/result_manifest.txt
python3 tools/summarize_lane_result_ready_results.py \
  /tmp/lezac-lane-result-route-sweep/result_manifest.txt \
  --require-success --require-executed

python3 tools/capture_original_explosion_procmem.py /tmp/lezac-preflight . \
  --describe-freeze-patch \
  --freeze-ghidra-offset 1000:3D3F \
  --freeze-patch-mode lane-result-cs-scratch
```

The `forward` alias maps to Ghidra `1000:3D3F`, and `reverse` maps to
`1000:3ED3`; the raw `3D3F`/`3ED3` forms are still accepted for direct
address-based retries. Dry-run summaries and full-capture manifests report the
selected `offset_labels` and normalized `offset_addresses` so single-probe
retries are visible in the log header. Direct lane-result live captures also
run the shared process-memory environment preflight before touching DOSBox and
record `environment_preflight=` in their manifest; use
`--skip-environment-preflight` only when an outer sweep has already verified
the host.
For route variation, repeat `--route-step KEY:SECONDS`; omitted route steps keep
the historical default of holding player-1 right (`x`) for
`--right-hold-seconds`. Use `tools/sweep_original_lane_result_routes.py` to
plan or run repeated natural-route probes while preserving one manifest and
one command line per route. CTest pins the historical natural forward
route-step probe as `explosion_lane_result_capture_orchestrator_dry_run_natural_forward`
so future route work keeps the `x:2.00,c:0.50` forward `3D3F` retry visible
beside the promoted `x:2.00` natural capture. Live route sweeps run
`tools/preflight_original_evidence_environment.py --probe-wsl
--require-wsl-bash-on-windows --require-procmem-capture` once before launching
any route, so Windows hosts that have `wsl.exe` but no usable default distro
fail with the same `wsl_bash_reason` reported by the standalone preflight; use
`--skip-environment-preflight` only for intentional forensic reruns on
already-verified hosts. Route sweeps pass `--skip-environment-preflight` to the
child direct lane-result captures so a batch performs one host check at the top
level. Pass `--cpp-exe <lezac_cpp>` and omit `--skip-oracle` when the dry-run or
live sweep should also record the follow-up `--debug-explosion-playback-oracle`
commands for each candidate. Use
`tools/summarize_lane_result_route_sweep.py` on
the completed sweep manifest to classify each candidate as `ready`, `no_freeze`,
`incomplete`, or `missing`, and to emit the matching
`--debug-explosion-playback-oracle` command. Add `--require-ready` when a
capture pass should fail unless at least one natural lane-result or lane-write
freeze is ready for promotion; add `--require-environment-preflight` when that
promotion should also require the sweep's host preflight to be recorded as `ok`.
`tools/run_lane_result_ready_manifest.py` and
`tools/run_lane_write_ready_manifest.py` then dry-run or execute only the ready
oracle candidates, write optional per-candidate logs, and can leave a result
manifest for `tools/summarize_lane_result_ready_results.py` or
`tools/summarize_lane_write_ready_results.py` with
`--require-success --require-executed --require-source-environment-preflight`.
The runners accept the same `--require-source-environment-preflight` guard
before planning or executing oracle commands. Result manifests and logs are
refused inside the repository unless `--allow-repo-output` is passed
deliberately. The synthetic CTest helpers
`tools/check_lane_result_ready_manifest.py`,
`tools/check_lane_result_ready_results.py`,
`tools/check_lane_result_ready_pipeline.py`, and
`tools/check_lane_write_ready_pipeline.py` cover the handoff without requiring
DOSBox.
`tools/check_explosion_evidence_map.py` keeps the explosion/playback recovery
handoff linked across the capture helpers, lane-result promotion tools,
oracle fixtures, C++ output fields, docs, and CTest wiring.
The checked-in original result-write fixtures are
`tests/fixtures/dosbox/explosion_playback_oracle_original_3ed3_lane_result_runtime.txt`
for the reverse helper and
`tests/fixtures/dosbox/explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded.txt`
for the forward helper under labeled runtime seeding.
`tests/fixtures/dosbox/explosion_playback_oracle_original_3d3f_lane_result_runtime_natural.txt`
now captures natural route `x:2.00` reaching the forward `3D3F` result write
without runtime seeding, and
`tests/fixtures/dosbox/explosion_playback_oracle_original_3ec1_lane_write_runtime_natural.txt`
captures natural route `x:2.00,m:0.35` reaching reverse debris writeback
`3EC1` without runtime seeding. The natural right/down route fixture
`tests/fixtures/dosbox/explosion_playback_oracle_original_3d3f_lane_result_route_step_no_freeze.txt`
records a live `x:2.00,c:0.50` no-freeze run with lane globals present.
Natural forward debris writeback at `3D2D` remains the next lane-write evidence
target before live queue playback changes. The reviewed forward-debris matrix
has already produced ten valid `no_freeze` candidates, so do not repeat it as
the next step:

```sh
python3 tools/sweep_original_lane_write_routes.py \
  /tmp/lezac-lane-write-forward-expanded . \
  --route-preset forward-debris-expanded --offset forward-debris \
  --approve-procmem --approve-runtime-instrumentation \
  --cpp-exe ./build/lezac_cpp --continue-on-oracle-error
```

Use `--continue-on-oracle-error` when the DOSBox/process-memory host can run
captures but the C++ oracle binary is unavailable from that host. The sweep
then records `oracle_error` lines in the manifest and preserves candidate
fixtures for a later `--debug-explosion-playback-oracle` pass with a rebuilt
Linux oracle or the native Windows executable.

The 2026-06-15 local WSL pass of that unchanged matrix completed ten natural
`3D2D` captures, and the native Windows oracle parsed them as valid
`no_freeze` candidates. Do not repeat the same matrix blindly. If the same
host split is used again, run the summarizer from Windows; it translates
`/mnt/c/...` manifest paths back to `C:\...` paths. Two narrower retries on
route `x:2.00,c:0.50` are also negative evidence: a `0x01` target-byte gate
never loaded the runtime patch (`no_patch`), and a later observed-state gate
`2941/665c/c22e` plus target byte `0xde` loaded the patch at `4.452` seconds
but still did not freeze or capture the natural lane write. A 2026-06-16
word-layer-gated retry for `209e/6620/c22e` plus target byte `0x00` also
remained negative evidence: the selected sample had word-layer value `0x0000`,
so the stricter `0x0005` gate did not apply the patch and the summary reported
one `no_patch` candidate. Follow-up 2026-06-16 retries proved that the early
target-byte/word-layer state can be instrumented when the debris threshold is
lowered to the observed seven nonzero bytes: the runtime patch applied at
elapsed `0.000` with selected debris base `0x2093`, but the original still did
not freeze or hit natural forward-debris writeback at `1000:3D2D`.

Do not repeat that early-state gate. A later-state gate based on lane globals
observed in the sample table has also been tried. The first run used
`--runtime-freeze-min-queue-score 0x80` under WSL `/tmp`; the matching
lane-global rows only reached score `0x78`, so the runtime patch did not apply,
and the Windows `.exe` oracle could not open the `/tmp` candidate path. The
corrected Windows-temp run used this shape:

```sh
python3 tools/sweep_original_lane_write_routes.py \
  /mnt/c/Users/andrz/AppData/Local/Temp/lezac-lane-write-forward-lane-globals-q78 . \
  --route x:2.00,c:0.50 --offset forward-debris \
  --runtime-freeze-preset none \
  --runtime-freeze-min-queue-score 0x78 \
  --runtime-freeze-min-debris-nonzero 0x20 \
  --runtime-freeze-min-collapse-nonzero 0x01 \
  --runtime-freeze-min-effect-nonzero 0x10 \
  --runtime-freeze-require-collapse-base 0x663e \
  --runtime-freeze-require-effect-base 0xc22e \
  --runtime-freeze-require-lane-update-flag 0x01 \
  --runtime-freeze-require-lane-word-global-value 0x8002 \
  --runtime-freeze-require-lane-target-offset-global-value 0x07be \
  --approve-procmem --approve-runtime-instrumentation \
  --cpp-exe ./build-win-codex-vs3/Debug/lezac_cpp.exe --continue-on-oracle-error
```

It wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-lane-globals-q78-1781610284`,
patched at `2.854s` after the bomb with selected bases `209e/663e/c22e`,
lane globals `0x01/0x8002/0x07be`, queue score `0x78`, debris nonzero `0x3c`,
collapse nonzero `0x27`, and effect nonzero `0x1c`, but still did not freeze or
hit natural forward-debris writeback. The native oracle parsed the candidate,
and the route summary classifies it as valid `no_freeze` evidence with
`missing_offsets=3d2d`. Do not repeat this exact lane-global gate; the next
`1000:3D2D` attempt needs a route/timing change or debugger/control-flow
question that explains why the patched state still misses the forward debris
write.

A follow-up route/timing sweep changed that variable and still remained
negative evidence. It wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-lane-global-route-variants-1781610807`
for routes `x:1.85,c:0.50`, `x:2.15,c:0.50`, `x:2.00,c:0.35`,
`x:2.00,c:0.65`, and `x:2.00,z:0.35`. The native oracle parsed all five
candidates. Three stayed `no_patch`; `x:2.00,c:0.35` patched at `3.614s` and
`x:2.00,c:0.65` patched at `2.970s`, both at selected bases `209e/663e/c22e`
with lane globals `0x01/0x8002/0x07be`, but neither froze nor hit the natural
forward-debris write. The summary is `ready_candidates=0`,
`no_patch_candidates=3`, `no_freeze_candidates=2`, `missing_offsets=3d2d`.
Do not spend the next pass on nearby lane-global timing tweaks; answer the
control-flow question around where the natural route diverges before
`1000:3D2D`.

Direct control-flow probes at the two patching timings narrow that question.
The q78 lane-global `1000:4C96` loop-patch run wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-lane-global-4c96-probe-1781611559`:
`x:2.00,c:0.35` patched at `2.769s` and `x:2.00,c:0.65` patched at `3.607s`
with selected bases `209e/663e/c22e` and lane globals `0x01/0x8002/0x07be`,
but the native oracle saw no freeze, no forward-helper call, and no lane write.
The paired `1000:4C75` bp4-scratch run wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-lane-global-4c75-probe-1781611676`:
the same timings patched at `2.680s` and `2.708s`, recorded scratch site
`01ED:4C7E` / old bytes `2001`, and still saw no freeze, high-word gate, or
bp4 local. Treat this narrowly: once the late lane-global predicate installed
the probes, neither `4C75` nor `4C96` was reached again in the sampled/tail
window. The next useful probe should arm earlier or inspect an upstream branch,
not retry adjacent lane-global durations.

Earlier branch-window probes classify those two timing variants more sharply.
For `x:2.00,c:0.35`, a selected-base `1000:4C75` bp4-scratch run at
`C:\Users\andrz\AppData\Local\Temp\lezac-early-4c75-selected-base-1781613438`
armed at `2.002s` with bases `209e/663e/c22e` and lane globals
`0x00/0x0002/0x07bc`, while the matching `1000:4B3F` run at
`C:\Users\andrz\AppData\Local\Temp\lezac-early-4b3f-selected-base-1781613513`
armed at `2.045s`; neither froze. Timed `4C75` probes at `after_bomb=1.0`,
`after_bomb=0.0`, and `before_bomb` also loaded patches with the early
`2093/6620/c22e` state and saw no high-word-gate hit. Before-bomb `4B3F`
probes for both `x:2.00,c:0.35`
(`C:\Users\andrz\AppData\Local\Temp\lezac-early-4b3f-before-bomb-1781613826`)
and `x:2.00,c:0.65`
(`C:\Users\andrz\AppData\Local\Temp\lezac-early-4b3f-before-bomb-c0p65-1781613903`)
also loaded without freezing. Treat the two `c` timings as late sampled-state
evidence, not natural `3D2D` branch-execution candidates. The next useful route
work should first prove `4B3F`/`4C75`/`4C96` reachability for the candidate
route, then target `1000:3D2D`.

Use `tools/sweep_original_branch_anchor_routes.py` for that classification
step instead of hand-assembling one-off `4B3F`/`4C75`/`4C96` commands. Its
default dry-run matrix probes those three anchors before the bomb tap across
`x:2.00`, `x:2.00,c:0.35`, `x:2.00,c:0.65`, and `x:2.00,m:0.35`:

```sh
python3 tools/sweep_original_branch_anchor_routes.py \
  /tmp/lezac-branch-anchor-route-sweep . --dry-run --skip-oracle
python3 tools/summarize_branch_anchor_route_sweep.py \
  /tmp/lezac-branch-anchor-route-sweep/manifest.txt \
  --require-route-with-targets high_debris_word_gate,effect_forward_pass_call \
  --write-route-manifest /tmp/lezac-branch-anchor-routes.txt
python3 tools/sweep_original_lane_write_routes.py \
  /tmp/lezac-lane-write-from-branch-routes . \
  --route-manifest /tmp/lezac-branch-anchor-routes.txt \
  --offset forward-debris --dry-run --skip-oracle
```

For a focused live classification after reviewing the dry run, use the same
tool with `--approve-procmem --approve-runtime-instrumentation`, optionally
adding `--timing selected_base`, `--timing after_bomb`, or repeated `--route`
arguments.
Summarize completed sweeps with
`tools/summarize_branch_anchor_route_sweep.py`. It reports per-candidate
`ready`/`no_patch`/`no_freeze`/`incomplete` status, `observed_targets=`,
`observed_routes=`, route-level `route_hits=`, optional `bp4_local_value=`,
and gates for `--require-target`, `--require-route-with-targets`, and
`--require-environment-preflight`. With `--write-route-manifest`, matching
route steps are emitted as `branch_anchor_route_candidates`; the lane-write
sweep accepts that handoff with `--route-manifest`. This is a reachability
classifier only; a natural `1000:3D2D` lane-write capture still needs the later
`tools/summarize_lane_write_route_sweep.py --require-forward-debris-tag` gate
before promotion.

The first live classifier pass wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-branch-anchor-default-1781615578`.
It showed that `x:2.00,m:0.35` is the useful candidate route: the default
matrix froze `1000:4C75` and `1000:4C96`, while the focused all-anchor bundle
`C:\Users\andrz\AppData\Local\Temp\lezac-branch-anchor-m-all-1781616282`
froze `1000:492F`, `1000:4B3F`, `1000:4B61`, `1000:4B6A`, `1000:4C75`, and
`1000:4C96`, but not `1000:4C20` or `1000:4CA9`. The matching natural
`1000:3D2D` retry at
`C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-m-route-1781616090`
applied its runtime patch with selected bases `2941/665c/c22e`, target byte
`0xde`, and lane globals `0x00/0x0004/0x072c`, but summarized as
`no_freeze` with `missing_offsets=3d2d`. That made the helper call/return or
lane-helper interior between the proven `4C96` call and the missing `3D2D`
writeback the next question; do not rerun this same route gate unchanged.

That helper-path follow-up now exists. The `4C99` return capture
`C:\Users\andrz\AppData\Local\Temp\lezac-helper-path-4c99-m-route-1781617322`
proved the `4C96 -> 3BB2` call returns on this route. The `3CE3` divide capture
`C:\Users\andrz\AppData\Local\Temp\lezac-helper-path-3ce3-m-route-1781617440`
froze one active forward helper item with numerator `0xffff:0xfff3` and weight
`0x0021`. The `3D1B` write capture
`C:\Users\andrz\AppData\Local\Temp\lezac-helper-path-3d1b-m-route-1781617379`
froze a forward collapse write with tag `0x0002`, `DI=0x001e`, and output
`0x0000`. Because the active tag is below the debris marker base `0x4e20`,
this route explains the missing `3D2D` as a collapse-tag helper iteration. The
next natural `3D2D` attempt should first prove a forward-helper debris marker
tag, then target the debris writeback.

Use the lane-div route classifier to batch future helper-interior checks before
writeback probes:

```sh
python3 tools/sweep_original_lane_div_routes.py \
  /tmp/lezac-lane-div-route-sweep . --dry-run --skip-oracle \
  --route x:2.00,m:0.35 --offset forward-divide
python3 tools/summarize_lane_div_route_sweep.py \
  /tmp/lezac-lane-div-route-sweep/manifest.txt \
  --require-forward-divide \
  --write-forward-route-manifest /tmp/lezac-lane-div-forward-routes.txt
python3 tools/sweep_original_lane_write_routes.py \
  /tmp/lezac-lane-write-from-lane-div-routes . \
  --route-manifest /tmp/lezac-lane-div-forward-routes.txt \
  --offset forward-collapse --offset forward-debris --dry-run --skip-oracle
```

The lane-div summary reports ready/no-patch/no-freeze/incomplete/missing
candidates plus `forward_divide_candidates=` and writes
`lane_div_forward_route_candidates` only after a route reaches the forward
divide call at `1000:3CE3`. This still does not prove debris writeback; it
only narrows which routes deserve the later `3D1B`/`3D2D` scratch probes.
For new route families, prefer the stricter route-state handoff when
`route_state_samples.tsv` is available:

```sh
python3 tools/summarize_lane_div_route_sweep.py \
  /tmp/lezac-lane-div-route-sweep/manifest.txt \
  --require-forward-divide --require-route-state-debris-marker \
  --write-forward-debris-route-manifest /tmp/lezac-lane-div-forward-debris-routes.txt
python3 tools/sweep_original_lane_write_routes.py \
  /tmp/lezac-lane-write-from-lane-div-forward-debris-routes . \
  --route-manifest /tmp/lezac-lane-div-forward-debris-routes.txt \
  --offset forward-debris --dry-run --skip-oracle
```

That manifest is emitted as `lane_div_forward_debris_route_candidates` and is
accepted by the lane-write sweep. It proves only that the route reached the
forward divide and sampled a `0x4e20`-or-higher lane word in route-state data;
the natural `1000:3D2D` writeback still needs its own ready fixture before
promotion.

A follow-up helper-tag sweep at
`C:\Users\andrz\AppData\Local\Temp\lezac-forward-helper-tag-search-1781617957`
tested nearby `m` timing routes against `1000:3D1B` and `1000:3D2D`. It found
two more ready `3D1B` captures, both forward collapse writes with tag `0x0005`,
`DI=0x004b`, and output `0x0000`; all paired `3D2D` candidates were valid
no-freeze captures. The inspected tail frames stayed in level-1 playback, so
the next search should avoid these collapse-tag route variants and instead
look for a helper iteration whose scratch tag is at or above `0x4e20`.

The expanded-route subset
`C:\Users\andrz\AppData\Local\Temp\lezac-forward-helper-expanded-tag-subset-1781622932`
tested `x:1.75`, `x:2.25`, `x:2.00,c:0.25`, `x:2.00,c:0.75`, and
`x:5.00,m:0.50,x:2.00` against both `3D1B` and `3D2D`; all ten candidates
patched and parsed as valid no-freeze fixtures. The inspected tail frames
stayed in level-1 playback, so these routes should be treated as pruned unless
a new predicate changes the capture timing or setup.

For reproducibility, the final level-1 helper-tag route pair is encoded in the
focused preset instead of requiring the whole expanded matrix:

```sh
python3 tools/sweep_original_lane_write_routes.py \
  /tmp/lezac-forward-helper-tag-open . \
  --route-preset forward-helper-tag-open \
  --offset forward-collapse --offset forward-debris \
  --runtime-freeze-preset none --runtime-freeze-before-bomb \
  --approve-procmem --approve-runtime-instrumentation \
  --cpp-exe ./build-win-codex-vs3/Debug/lezac_cpp.exe --continue-on-oracle-error
```

The completed no-sample run
`C:\Users\andrz\AppData\Local\Temp\lezac-forward-helper-tag-open-nosamples-1781623828`
used that preset with `--route-state-interval 0` after a sampled attempt hit a
`/proc/<pid>/mem` permission error. It produced four valid no-freeze fixtures:
both remaining routes missed both `3D1B` and `3D2D`, and the inspected route
and tail frames stayed in live level-1 playback.

`tools/summarize_lane_write_route_sweep.py` now classifies ready lane-write
scratch tags as `collapse` or `debris` relative to the `0x4e20` debris-marker
base. The prior helper-tag search at
`C:\Users\andrz\AppData\Local\Temp\lezac-forward-helper-tag-search-1781617957`
now summarizes as `debris_tag_candidates=0`, `collapse_tag_candidates=2`, and
`max_lane_write_tag=0x0005`; `--require-debris-tag` fails on that manifest with
`reason=no_debris_tag_candidates`. Use
`tools/summarize_lane_write_route_sweep.py <manifest-or-dir> --require-forward-debris-tag`
as the stricter gate before spending a natural `1000:3D2D` capture on a newly
found helper-tag route. The broader `--require-debris-tag` still accepts
reverse debris evidence such as `3EC1`; the remaining gap needs the forward
debris write specifically. When that stricter gate passes, add
`--write-forward-debris-route-manifest /tmp/lezac-forward-debris-routes.txt`
and feed the resulting `lane_write_forward_debris_route_candidates` file back
to `tools/sweep_original_lane_write_routes.py --route-manifest` for focused
follow-up probes.

For no-freeze route searches, the same summary also reads each candidate's
`route_state_samples.tsv` when present. New captures include
`lane_update_flag_value`, `lane_word_global_value`,
`lane_target_offset_global_value`, and effect input globals in that TSV, and
the summary reports `route_state_debris_marker_candidates=` plus
`max_route_state_lane_word_global=`. Use
`--require-route-state-debris-marker` as a pre-writeback search gate when a
new route family should first prove that it sampled a lane word at or above the
`0x4e20` debris-marker base. This remains route-state triage, not a promoted
natural `3D2D` fixture.

The sweep wrapper now translates `/mnt/<drive>/...` candidate paths when a WSL
run invokes a Windows `.exe` oracle, so that host split can parse candidates in
the same pass instead of leaving `oracle_error` records for path-only reasons.

`--debug-lane-write-static-model` pins the shipped executable bytes behind
that plan: forward/reverse collapse stores at `1000:3D1B`/`1000:3EAF`,
forward/reverse debris stores at `1000:3D2D`/`1000:3EC1`, the `0x4E20`
debris marker base, `0x0B` debris stride, and the shared far-result write tail.
`--debug-lane-write-tag-model` bridges those stores to the recovered tag
arithmetic without changing gameplay: collapse tags map directly to
`DI=0x0f*tag`, debris tags subtract `0x4e20` before `DI=0x0b*slot`, and the
diagnostic pins representative writes for collapse tags `0x0002`/`0x0005` and
debris tags `0x4e21`/`0x4ee8`. It remains a C++ arithmetic/model check with
`original_capture_claim=0`, not a natural `1000:3D2D` runtime observation.

## Implemented

- `--debug-shipped-file-manifest` pins the 14 shipped original files used as
  conversion/disassembly evidence, including `LEZAC.EXE` size `52384`, MZ
  image base `0x0770`, image size `50480`, and aggregate byte fingerprints.
  It also scans the executable image for the original lowercase runtime
  filename anchors: ten unique names and 15 references, including
  `proefs.son` at `1000:0626`, `gran.mst` at `1000:2AD4`, and `livels.sch` at
  `1000:2EF3`.
- The runtime loader now defaults to the shipped binary files. Set
  `LEZAC_LOAD_JSON_ASSETS=1` or `LEZAC_LOAD_ORIGINAL_ASSETS=0` to force the JSON
  compatibility path. `--debug-original-asset-load` compares both paths across
  palettes, background, tiles, sprites, records, `PROEFS.SON`, `GRAN.MST`, and
  all seven levels.
- VGA palette loading from `BOMPAL.PAL` and `SFONLEF.ZBG`.
- `SFONLEF.ZBG` PCX-style RLE background decoding as a 321x388 image.
- `CARO.CAR` 132-tile 8x8 tile bank loading.
  `--debug-core-resource-raw-roundtrip` verifies those three original binary
  files against the converted JSON resources, including the background RLE
  expansion to 124,548 pixels and the 8,448-byte CARO tile payload.
- `FONTS.SPR`, `PROVA.SPR`, and `BOMOMIMK.SPR` sprite-bank loading. The
  `--debug-sprite-layout-static-model` diagnostic pins the original raw
  count/header/payload walk for all three banks, including exact per-bank byte
  counts and no trailing data.
- Text rendering from the original `FONTS.SPR` glyph sprites.
- `RECS.DAT` high-score parsing as score, reached level, and colon-padded
  8-byte player name. `--debug-records-raw-roundtrip` pins the shipped binary
  table against the converted JSON: seven 13-byte records, top score `541200`,
  cutoff `474930`, score sum `3508890`, and colon-padded `aga:::::` names.
- `PROEFS.SON` parsing as a fixed-size sound-effect bank and `GRAN.MST`
  parsing as seven fixed-size opaque records. The GRAN roundtrip now loads the
  shipped raw file and converted JSON independently, reports
  `raw_json_match=1`, and pins record-level byte fingerprints for later
  comparison while keeping every field semantic unresolved. The shipped
  executable references the file through the lowercase `gran.mst` string at
  `1000:2AD4`, but no decoded live consumer has been recovered yet.
  `tools/check_gran_usage_guardrail.py` keeps `GRAN.MST` limited to loading,
  validation, byte-preserving roundtrip/debug output, and stored opaque records
  until original evidence proves a live gameplay or rendering use.
- Runtime-evidence bookkeeping for checked-in original DOSBox fixtures.
  `tools/check_runtime_evidence_guardrail.py` pins the
  `docs/recovery/runtime_evidence_ledger.md` entries to `temp_copy=1`,
  runtime `CS`/`DS`, and `visual_claim=0` so debugger evidence cannot be
  confused with promoted visual-frame evidence. Supporting notes live in
  `docs/recovery/original_runtime_fixture_notes.md`.
- `LIVELS.SCH` seven-level parsing with the Ghidra-confirmed 3-byte level RLE,
  decoded word layer, monster spawner records, portal/start records, and tile
  trigger rules. The raw-level roundtrip also pins the shipped embedded
  `fieldA`/`fieldB` words, treats `fieldB` as the low physical-word damage
  denominator, and keeps `fieldA` unresolved with aggregate negative-candidate
  coverage in `--debug-word-layer`. `--debug-level-completion-denominator`
  verifies live completion thresholds for all seven levels against
  `ceil(requiredDestruction * fieldB / 100)`.
- A playable one-player reconstruction loop using original maps and graphics:
  movement, jumping, objective collection, bomb placement, tile destruction,
  score, start positions, teleports, tile triggers, monster spawning, basic
  behavior-specific monster movement/damage, documented monster reward drops,
  static bonus-score table evidence from `LEZAC.EXE` via
  `--debug-bonus-reward-static-model`, current monster sprite table candidate
  coverage via `--debug-monster-sprite-table-model`,
  spawner live-slot return after monster death animation removal,
  bomb-power damage against monster hit points,
  four-slot bomb inventory/switching, original bomb actor sprites, player
  animation, active structure hazard damage, bomb blast player damage,
  post-hit damage cooldown, level progression, and records/menu display.
  Deterministic debug coverage exercises the current cell-aware passable-object
  classification, including the level-1 low-word object route, level-1
  autoplayer bomb route, death/reentry, record-entry, two-player movement/bomb
  checkpoints, frame-harness checkpoints, and player/monster collision pushout
  model.
- Menu subpages for info, instructions, and records, plus original-documented
  background and one-player playfield-width controls. `--debug-menu-frame-flow`
  frame-inspects distinct main/info/instructions/records pages, the records
  page sound request, visible gameplay background toggling, game start,
  return-to-menu, and menu-exit paths under dummy SDL.
  `--debug-autoplayer pause_flow` locks the current-port pause toggle with
  frame inspection, frozen logic/bomb/input state while paused, resume, and
  escape-to-menu behavior; this remains `original_pause_claim=0` pending
  original-game observation.
- A first playable two-player reconstruction pass with separate start markers,
  separate controls, split camera views, a central objective panel, per-player
  bomb inventories/HUD/score state, zero-life player-out handling, shared
  objectives, original-evidence fire keys (`N` for player 1 and keypad
  `0`/Insert for player 2), and queued per-player high-score prompts at end of
  run, including re-checking player 2 against the updated table after player 1
  inserts a qualifying record.
- High-score table serialization back to original binary `RECS.DAT` format by
  default, with JSON compatibility retained for `.json` diagnostics. Name
  entry for new records follows original-evidence letters/space, Backspace,
  Enter handling, eight-character truncation, and colon-padded storage, with
  validation coverage that writes only to temporary test files.
  `tools/check_record_flow_evidence_map.py` keeps the record-entry/end-flow
  handoff tied to `RECS.DAT` structure, debug commands, CTest output contracts,
  and the disassembly anchors before cursor/typematic presentation is refined.
  `--debug-record-entry-static-model` also pins the original
  `1000:1845..1ad6` byte model for the eight-colon empty template, 13-byte
  record stride, 8-byte name copy, dword score write, and Backspace/Enter
  checks.
  Record prompting uses the recovered strict seventh-place cutoff, re-checks
  queued two-player scores after each insertion, and preserves pending name
  entry state across a failed save so the same record can be retried.
- Game-over and completed-game end states using strings recovered from
  `1000:1b14..1d42`, with final-level completion entering the completed-game
  path instead of wrapping directly into level 1. `--debug-end-flow-static-model`
  pins the dispatcher bytes for mode strings, the completed-game flag, per-player
  score pointers, seventh-record cutoff comparison, and record-entry call.
  `--debug-end-flow-frame-flow` frame-inspects the current game-over and
  completed-game pages, including final-score visibility, natural final-level
  completion, and confirm-to-menu score clearing.
- `PROEFS.SON` payload bytes are preserved as the original 130 six-byte
  playback steps. Non-direct sound synthesis now advances by the recovered
  `DS:78c0` cursor, honors the `0x7530` stop sentinel, and applies the
  gate/period bytes used by `1000:0fbe..1088`. `--debug-sound-loader-static-model`
  pins the original `1000:0630..06aa` loader bytes that read the `0x0082`
  count and then load `0x82 * 6` payload bytes through `DS:79c0`. Bomb explosion
  requests use the
  recovered direct-sweep cursors and the original `1000:165a` priority latch,
  with `--debug-sound-latch-static-model` pinning the latch bytes, branch
  targets, priority comparison, and accepted-request copies in `LEZAC.EXE`,
  bomb placement queues the recovered direct-sweep cursor `0xea74` at priority
  `3`, bomb-object destruction queues the recovered priority-`3` object cue,
  monster death/reward queues cursor `0x003d` at priority `12`, portal
  transfer queues cursor `0x001a` at priority `4`, tile-trigger activation
  queues cursor `0x0027` at priority `6`, bonus pickup audio queues cursor
  `0x0008` at priority `5`, accepted player damage queues cursor `0x002d` at
  priority `4`, and player death/life-loss queues cursor `0x0056` at priority
  `5` while restoring the player energy byte to `100`.
  Sound-callsite evidence
  now has a normalized `--debug-sound-callsite-oracle <fixture> [--expect-error]`
  path for original debugger stops around `1000:165a`: fixtures record
  runtime `CS`/`DS`, callsite and latch breakpoints, `DS:2074` pending cursor,
  `DS:799f` pending priority, `DS:78c0` current cursor, `DS:799e` current
  priority, and `DS:79c4` active flag while staying `visual_claim=0`.
  `tools/capture_original_sound_callsite_debug.sh <out_dir> [asset_dir]
  <scenario>` stages debugger-seeded manifests and candidate fixtures for
  `bomb_object_sound`, `bomb_place_sound`, `monster_death_sound`,
  `portal_teleport_sound`, `tile_trigger_sound`, `bonus_pickup_sound`,
  `player_damage_sound`, `player_death_sound`, `record_name_prompt_sound`,
  `record_name_commit_sound`, `post_end_flow_record_sound`, and
  `records_page_sound`. It also stages the actor/contact runtime queue as
  capture-only fixtures:
  `contact_scanner_runtime_sound`, `actor_update_runtime_cursor_0024_sound`,
  `actor_update_runtime_cursor_0035_sound`, and
  `actor_update_runtime_cursor_0021_sound`, with manifests marked
  `capture_class=actor_contact_runtime` and the static region preserved as
  `contact_scanner` or `actor_update`.
  If DOSBox-debug times out after reaching the debugger prompt, the helper keeps
  the failure non-promotable but now reports `reason=dosbox_debug_timeout` and
  includes any observed runtime `CS`/`DS` values plus the translated runtime
  command plan. A 2026-06-16 WSL run for `records_page_sound` reached
  `runtime_cs=01ED` and `runtime_ds=01DD`, then wrote breakpoints for
  `01ED:2083` and `01ED:165A` and dumps under `01DD:*` before timing out.
  `--debug-static-sound-requests` pins all 27 static immediate writes to
  `DS:2074` in the shipped executable so the remaining
  `playCompatibilitySound` routes cannot be confused with original
  cursor/priority mappings. It also reports
  `remaining_compat_hooks=objective_pickup,level_complete` and the rejected
  objective-sound candidates
  `0x4b2c:collapse_playback,0x6d75:bomb_object_high_gate,0x6924:non_objective_tile_gate`,
  keeping the collapse playback branch, the bomb-object high gate, and the
  non-objective tile gate out of the objective-pickup mapping until new
  original evidence proves otherwise. `--debug-remaining-sound-compat-hooks`
  exercises the live C++ objective-pickup and level-complete paths and reports
  `capture_blockers=objective_pickup:rejected_static_candidates,level_complete:no_static_candidate`
  plus `latch_preserved=1` and `original_cursor_priority_claim=0`, proving
  only that those named compatibility hooks still funnel to the intended
  compatibility indices without mutating a seeded recovered latch, and naming
  why the DOSBox sound-callsite helper must not stage them as original
  cursor/priority captures yet. `--debug-static-sound-unresolved-contexts`
  also pins the exact byte windows for those 12 unresolved writes and separates
  their local request shapes: nine local latch calls, six inline priorities,
  two preceding priorities, four no-local-priority cases, three no-latch cases,
  and two `0x2710` cursor writes. It now also buckets the unresolved writes by
  static code region:
  `record_ui:2`, `pre_new_game_setup:1`, `explosion_playback:2`,
  `effect_extent_scan:2`, `contact_scanner:1`, `actor_update:3`, and
  `post_actor_update_no_latch:1`. It also prints capture classes and the
  actor/contact runtime queue
  `actor_contact_capture_candidates=0x5e81:contact_scanner,0x6844:actor_update,0x6924:actor_update,0x7386:actor_update`;
  these region labels are static byte-context facts, not live cue promotions.
  `--debug-sound-runtime-capture-queue` narrows that handoff to the four
  actor/contact runtime sound scenarios, rechecks their shipped byte windows,
  and marks `contact_scanner_runtime_sound` (`1000:5e81`, cursor `0x0069`,
  priority `4`) as the first runtime target while keeping
  `sound_runtime_capture_queue=ok` at `original_cursor_priority_claim=0`. Its
  output now names `tools/capture_original_sound_callsite_procmem.sh` as the
  runtime helper, `tools/sweep_original_sound_callsite_routes.py` as the route
  planner, and the live approval flags
  `LEZAC_SOUND_CALLSITE_APPROVE_PROCMEM` plus
  `LEZAC_SOUND_CALLSITE_APPROVE_RUNTIME_INSTRUMENTATION`.
  `tools/capture_original_sound_callsite_procmem.sh` mirrors all four
  actor/contact runtime targets through the process-memory freeze path; live
  runs require `LEZAC_SOUND_CALLSITE_APPROVE_PROCMEM=1` and
  `LEZAC_SOUND_CALLSITE_APPROVE_RUNTIME_INSTRUMENTATION=1`, emit
  `sound_callsite_procmem`, and generate a non-promoted candidate fixture for
  later oracle normalization. `tools/sweep_original_sound_callsite_routes.py`
  dry-runs or executes the same helper across route/timing hypotheses and
  records `sound_callsite_route_sweep` manifests for future live evidence.
  `tools/summarize_sound_callsite_route_sweep.py` triages those manifests into
  completed capture counts, observed-freeze counts, ready/incomplete/missing
  candidate counts, per-capture `--debug-sound-callsite-oracle` commands, and
  optional `debug_capture_ready_candidates` manifests for the generic ready
  runner.
  `--debug-static-sound-contexts` separately
  pins the original bytes and nearby strings that place `0x1857`, `0x1a44`,
  `0x1d9c`, `0x202d`, and `0x2083` in name-entry/record UI regions rather than
  in the `1000:1b14..1d42` completed-game dispatcher, so the current
  level-complete hook also stays explicitly unresolved. The first two
  name-entry writes are now live: high-score prompt opens with cursor `0x0078`
  at priority `11`, and Enter commits with cursor `0x0008` at priority `11`.
  `--debug-record-name-sound` pins both requests through the recovered latch.
  The main-menu records-page transition now also queues the `1000:2083`
  `punteggi migliori` sound, cursor `0x0024` at priority `2`, while the
  cursor-only `1000:202d` record-table write remains staged.
  Live player damage now
  accumulates per-player damage bytes and drains them once per update pass,
  matching the recovered `DS:79e8`/`DS:79e9` model and original unsigned byte
  underflow death check rather than a modern one-hit cooldown gate.
  `tools/check_sound_callsite_map.py` keeps those six recovered non-explosion
  cue claims tied to `docs/GHIDRA_NOTES.md`, `src/main.cpp`, and CTest names.
  Fatal
  damage now keeps the visible life count unchanged while the recovered
  state-2 `0x003c` countdown runs, then consumes the pending life before
  manual reentry or restart can proceed. `--debug-autoplayer death_reentry`
  now covers both shipped-manual choices after fatal damage: pressing fire
  reenters a still-winnable level,
  while waiting restarts the level; it also verifies that an unwinnable level
  blocks early fire and restarts instead.
  The state-2 death/reentry
  animation initializer is now documented as the seven-byte `actor + 0x16`
  cursor populated by `1000:06ab`, and the
  actor update model locks the `1000:6053` counter, wrap, ping-pong, and
  mode-3 backup behavior. The runtime-frame oracle parses saved DOSBox debugger
  dumps for `DS:006a`, `DS:006c`, `DS:006d`, the `DS:c322..c324` frame table,
  and `DS:c21e` effect-entry words without making a visual claim, and reports
  each captured frame-table row in deterministic raw-byte form. A real temp-copy
  `dosbox-debug` capture stopped at runtime `01ED:7C89` now locks one original
  state-2 countdown sample: `DS=0C8F`, death cursor `0x45`, frame range
  `0x4a..0x4f`, row-byte sequences `10,10,10,10,10,10`,
  `10,10,10,10,10,10`, `7d,7d,7d,7d,7d,7d`,
  `43,44,45,46,47,48`, and effect entry 0 position `0x0068,0x00a8`.
  `tools/check_visual_state2_evidence_map.py` keeps this death/reentry visual
  handoff tied to source, fixtures, CTest, and the unresolved `visual_claim=0`
  documentation before any future renderer promotion.
  `--debug-original-state2-visual-row-model` mirrors that row range as a
  conservative C++ model, including the row-byte-3 `BOMOMIMK` sprite-index
  candidates `67..72`, the row-byte-0/1 draw-offset candidates
  `0x10,0x10` / `16,16`, the stable row-byte-2 constant `0x7d`, and
  `visual_claim=0`.
  `--debug-original-state2-visual-row-assets` verifies those candidates against
  the loaded sprite bank, reports their dimensions, nonzero-pixel counts, and
  bounding boxes, and contrasts them with the old cursor-index sequence
  `74..79`. Live state-2 death rendering now uses an explicit DS:C21E-style
  effect-entry base, then applies the recovered row-byte-3 sprites `67..72` and
  row-byte-0/1 draw-offset candidates `16,16`; this improves the C++ port but
  still keeps the separate visual-claim promotion workflow at `visual_claim=0`
  until paired original screenshots are promoted.
  `--capture-state2-visual-row-preview <out_dir>` writes isolated PPM previews
  for both sequences plus a `manifest.txt`, so later original-frame comparison
  can target the recovered row-byte-3 candidates directly. The companion
  `--capture-state2-visual-row-game-preview <out_dir>` writes full gameplay
  frame previews for the current effect-entry row-byte-3 renderer and a
  debug-only legacy cursor-index renderer.
  `tools/compare_state2_visual_row_game_previews.py` builds a standard
  frame-compare bundle from those previews and an original-frame directory, with
  labels such as `state2_current_4a` and `state2_cursor_4a`. The live
  `--debug-autoplayer death_visuals` route verifies frames `0x4a..0x4c` now
  render live sprites `67..69` from effect-entry base `104,168` with draw
  offset `16,16` and differ from the old cursor-index sprites `74..76`, while
  still keeping `visual_claim=0`.
  `--debug-original-state2-return-model` now also locks the static
  `1000:7ef8..7f2a` fallback model: no active players increments the
  `DS:79b9` counter and promotes status byte `2` to `1` without doing the
  normal actor-state or energy restore. The live
  `--debug-player-state2-return-active` guard now separately proves that the
  current C++ two-player path leaves player 2 out after a final-life countdown,
  blocks manual reentry, keeps player 1 active, and reaches game over only
  after player 1 also loses the final life. It reports
  `live_fallback_shortcut=0` and `original_reachability=0`, so this remains a
  C++ regression boundary rather than proof that the static fallback is reached
  in the original runtime.
  `--debug-son-step-fields` exposes each recovered six-byte sound step as
  `period_word`, `gate_tick`, `period_ticks`, `tail4`, and `tail5`. Bytes
  `+4..+5` are preserved from the shipped bank but are playback-unused in the
  recovered `1000:0FBE..1088` tick window. The
  `--debug-son-tail-field-mutation` diagnostic mutates those two tail bytes for
  every shipped step and verifies rendered samples for the known cursor starts
  are unchanged, matching the recovered tick window that does not read them.
  The return-placement model tracks the `DS:c21e + 8 * actor[+0x01]` effect-entry
  descent and blocking checks. Explosion/debris/collapse diagnostics now lock
  the recovered dispatcher selector/state/sound-offset table, queued
  debris/collapse payload fields, and bomb-object passability/routing side
  effects without claiming exact original sprite playback.

## Still Approximate

- Monster spawners now create active enemies with original-style 8.8 motion, and
  debug coverage locks the current collision/passability model, but
  behavior-specific AI and exact original collision clearance remain implemented
  hypotheses pending deeper reconstruction of the actor update routine around
  `1000:6053`.
- PC speaker sound effects now use a recovered request/priority latch,
  direct-sweep path for bomb explosions, and six-byte cursor stepping for
  `PROEFS.SON`. `--debug-sound-tick-static-model` pins the original
  `1000:0FBE..1088` tick routine's cursor stride, direct-sweep branch, stop
  sentinel, and table reads: word offset `+0`, byte offset `+2`, byte offset
  `+3`, with no checked read of tail bytes `+4..+5`. Field diagnostics preserve
  those tail bytes as raw data, and mutation coverage proves the current
  synthesizer ignores them, so their playback effect is recovered as unused.
  Any source/editor meaning outside playback plus many non-explosion
  callsite-to-event mappings remain unresolved. Remaining live compatibility
  sound routes now go through `playCompatibilitySound(...)`, which deliberately
  funnels to `playSound(index)` only until original cursor/priority writes are
  recovered.
- Two-player split-screen is playable with independent bomb inventories, scores,
  record prompts, and a central objective/progress panel that is covered by
  `--debug-two-player-hud-panel`. `--debug-autoplayer two_player_death_visuals`
  frame-inspects independent state-2 effect-entry slots for both players, but
  exact original panel artwork and reentry presentation remain approximate.
- High scores are persisted with original-evidence name-entry keys
  (letters/space, Backspace, Enter), the recovered eight-character cap, and
  colon-padded storage. Empty submissions now preserve the original eight-colon
  raw template and decode as `nessuno`. The name-entry renderer now highlights
  the current input slot and `--debug-record-name-entry-cursor` frame-inspects
  cursor movement after typing and Backspace. SDL repeat keydown events now
  repeat letters/space and Backspace while ignoring repeated Enter/Escape;
  exact original repeat timing and presentation remain approximate.
- Bomb fuse timing, 2x2 footprint, player blast damage, monster hit-point
  blast damage, visual selectors, actor sprite indices, word-layer damage
  gating, bomb-object passability after explosion, and queued debris/collapse
  metadata now follow the `1000:414a`/`1000:370e`/expiration analysis. Active
  collapse/debris records
  now queue into the same per-player damage counters as monster contact and
  bomb blasts. The delayed state-2 life-count decrement now follows the
  recovered `+0x10 = 0x003c` countdown in live damage, monster contact, and
  reentry diagnostics. Exact sprite playback remains approximate: the
  `actor + 0x16` state-2 cursor, cursor advancement rules, and `DS:c21e`
  placement math are locked as deterministic models, and the live renderer now
  consumes an explicit DS:C21E-style effect-entry base, the recovered row-byte-3
  `BOMOMIMK` sprite sequence `67..72`, and row-byte-0/1 draw offsets `16,16`
  for the `0x4a..0x4f` state-2 frame range.
  `--debug-autoplayer death_visuals` verifies the live row-byte-3 sprites
  `67..69`, effect-entry base `104,168`, and draw offset `16,16` against the
  debug-only legacy cursor-index contrast path `74..76`. It still reports
  `visual_claim=0` because paired original-frame comparison has not promoted
  exact presentation.

See [docs/GHIDRA_NOTES.md](docs/GHIDRA_NOTES.md) for addresses and disassembly
anchors used in the reconstruction.
