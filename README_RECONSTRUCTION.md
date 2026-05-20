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

Run from this directory so the converted JSON resources are found:

```sh
./build/lezac_cpp
```

Validate every decoded original data file without opening a window:

```sh
./build/lezac_cpp --validate
```

Smoke-test SDL window creation and menu/control handling:

```sh
./build/lezac_cpp --smoke-ui 3
./build/lezac_cpp --smoke-controls
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
./build/lezac_cpp --debug-fixed
./build/lezac_cpp --debug-sounds
./build/lezac_cpp --debug-sound-render
./build/lezac_cpp --debug-sound-cursor-segments
./build/lezac_cpp --debug-son-raw-roundtrip
./build/lezac_cpp --debug-son-step-fields
./build/lezac_cpp --debug-sound-priority-latch
./build/lezac_cpp --debug-sound-selector-map
./build/lezac_cpp --debug-player-damage-sound
./build/lezac_cpp --debug-original-damage-counters
./build/lezac_cpp --debug-level1-frame-inspection
./build/lezac_cpp --debug-autoplayer level1_bomb_route
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
./build/lezac_cpp --debug-autoplayer two_player_progression
./build/lezac_cpp --debug-player-state2-death-fields
./build/lezac_cpp --debug-original-state2-return-model
./build/lezac_cpp --debug-original-state2-animation-init
./build/lezac_cpp --debug-original-state2-animation-advance
./build/lezac_cpp --debug-state2-runtime-frame-oracle tests/fixtures/dosbox/state2_runtime_frame_oracle_synthetic.txt
./build/lezac_cpp --debug-state2-runtime-frame-oracle tests/fixtures/dosbox/state2_runtime_frame_oracle_original.txt
./build/lezac_cpp --debug-explosion-playback-oracle tests/fixtures/dosbox/explosion_playback_oracle_synthetic.txt
./build/lezac_cpp --debug-original-state2-effect-placement
./build/lezac_cpp --debug-player-state2-return-active
./build/lezac_cpp --debug-record-update /tmp/records_test.dat
./build/lezac_cpp --debug-record-name-entry /tmp/records_name_test.dat
./build/lezac_cpp --debug-record-save-failure /tmp/missing-record-dir/records.dat
./build/lezac_cpp --debug-end-flow-records /tmp/end_flow_records.dat
./build/lezac_cpp --debug-gran
./build/lezac_cpp --debug-gran-raw-roundtrip
./build/lezac_cpp --debug-levels
./build/lezac_cpp --debug-level-raw-roundtrip
./build/lezac_cpp --debug-sprite-transparency
./build/lezac_cpp --debug-sprite-raw-roundtrip
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
Use `tools/capture_original_behavior4_debug.sh` to stage best-effort
DOSBox-debug capture plans for `monster_spawner_behavior4_level2`,
`monster_spawner_behavior4_level3`, and `monster_behavior4_target_selection`.
It writes a `candidate_fixture.txt` skeleton and
`debugger_commands_runtime.txt`; when a live run exposes `runtime_cs` or
`runtime_ds`, the helper copies those values into the manifest/raw dump and
expands the debugger command plan to the observed runtime segment.
Live behavior-4, actor-update, and contact-scanner DOSBox-debug helpers run
`tools/preflight_original_evidence_environment.py --require-debug-capture`
before launching DOSBox-debug, record `environment_preflight=` in the manifest,
and keep the preflight output in `environment_preflight.log`. Use the matching
`LEZAC_*_DEBUG_SKIP_ENVIRONMENT_PREFLIGHT=1` variable only for intentional
forensic reruns on an already-verified host.
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
before promoting generic behavior-4, actor-update, or contact-scanner runtime
evidence. `tools/check_debug_capture_ready_pipeline.py` exercises this full
batch-summary, ready-runner, and result-summary handoff with synthetic data.
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
`tools/check_visual_claim_guardrail.py` requires every checked-in DOSBox oracle
fixture to carry an explicit `visual_claim=0` or `visual_claim=1` line so
instrumentation-only evidence cannot be promoted by omission. Promotions to
`visual_claim=1` must also be recorded in
`docs/recovery/visual_claim_promotions.md` with original, C++, and comparison
frame artifacts. The guardrail self-test exercises the promoted-fixture path so
missing checked-in artifacts are rejected before any fixture is promoted.
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
The wrapper writes
`<target>_runtime_candidate.txt` with the runtime metadata plus raw route-state
dumps; the candidate is a fill-in scaffold until semantic actor/contact records
are decoded. Gate-target candidates include the required actor-update anchor
set and a `dispatch_gate_candidate` hint for later `dispatch_gates=` oracle
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
already-verified host:

```sh
python3 tools/sweep_original_actor_contact_routes.py \
  /tmp/lezac-actor-contact-route-sweep . --dry-run
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
target:

```sh
python3 tools/sweep_original_actor_dispatch_gates.py \
  /tmp/lezac-actor-dispatch-gates . --dry-run
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
`ready_candidates=`, `incomplete_candidates=`, `missing_candidates=`,
`candidate_status=`, `candidate_missing=`, `oracle=`, `oracle_flag=`, and
`oracle_command=` so the candidate fixture can be completed and routed to the
matching runtime oracle without guessing. Use
`candidate_placeholders=1` as a warning that a generated skeleton still has
fill-in markers in comments or active records. Use `--oracle-binary` when the C++
executable is not
`./build/lezac_cpp`, and `--require-ready` when a script should fail until all
observed freeze candidates are promotable. Add
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

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer level1_bomb_route
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-frames level1_bomb_route
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-b4-level2 monster_spawner_behavior4_level2
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
`tools/check_optional_original_oracle_fixtures.py` keeps these three runtime
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
one command line per route. Live route sweeps run
`tools/preflight_original_evidence_environment.py --probe-wsl
--require-wsl-bash-on-windows --require-procmem-capture` once before launching
any route, so Windows hosts that have `wsl.exe` but no usable default distro
fail with the same `wsl_bash_reason` reported by the standalone preflight; use
`--skip-environment-preflight` only for intentional forensic reruns on
already-verified hosts. Route sweeps pass `--skip-environment-preflight` to the
child direct lane-result captures so a batch performs one host check at the top
level. Use
`tools/summarize_lane_result_route_sweep.py` on
the completed sweep manifest to classify each candidate as `ready`, `no_freeze`,
`incomplete`, or `missing`, and to emit the matching
`--debug-explosion-playback-oracle` command. Add `--require-ready` when a
capture pass should fail unless at least one natural lane-result freeze is ready
for promotion; add `--require-environment-preflight` when that promotion should
also require the sweep's host preflight to be recorded as `ok`.
`tools/run_lane_result_ready_manifest.py` then dry-runs or executes only the
ready oracle candidates, writes optional per-candidate logs, and can leave a
result manifest for
`tools/summarize_lane_result_ready_results.py --require-success
--require-executed --require-source-environment-preflight`. The runner accepts
the same `--require-source-environment-preflight` guard before planning or
executing oracle commands. Result manifests and logs are refused inside the
repository unless `--allow-repo-output` is passed deliberately. The synthetic
CTest helpers `tools/check_lane_result_ready_manifest.py`,
`tools/check_lane_result_ready_results.py`, and
`tools/check_lane_result_ready_pipeline.py` cover the handoff without requiring
DOSBox.
The checked-in original result-write fixtures are
`tests/fixtures/dosbox/explosion_playback_oracle_original_3ed3_lane_result_runtime.txt`
for the reverse helper and
`tests/fixtures/dosbox/explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded.txt`
for the forward helper under labeled runtime seeding. The natural right/down
route fixture
`tests/fixtures/dosbox/explosion_playback_oracle_original_3d3f_lane_result_route_step_no_freeze.txt`
records a live `x:2.00,c:0.50` no-freeze run with lane globals present.
Natural-route forward `3D3F` evidence remains pending because the current
default/timing/route-step probes load the patch but do not reach that freeze.

## Implemented

- VGA palette loading from `BOMPAL.PAL` and `SFONLEF.ZBG`.
- `SFONLEF.ZBG` PCX-style RLE background decoding as a 321x388 image.
- `CARO.CAR` 132-tile 8x8 tile bank loading.
- `FONTS.SPR`, `PROVA.SPR`, and `BOMOMIMK.SPR` sprite-bank loading.
- Text rendering from the original `FONTS.SPR` glyph sprites.
- `RECS.DAT` high-score parsing as score, reached level, and colon-padded
  8-byte player name.
- `PROEFS.SON` parsing as a fixed-size sound-effect bank and `GRAN.MST`
  parsing as seven fixed-size opaque records.
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
  trigger rules.
- A playable one-player reconstruction loop using original maps and graphics:
  movement, jumping, objective collection, bomb placement, tile destruction,
  score, start positions, teleports, tile triggers, monster spawning, basic
  behavior-specific monster movement/damage, documented monster reward drops,
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
  background and one-player playfield-width controls.
- A first playable two-player reconstruction pass with separate start markers,
  separate controls, split camera views, a central objective panel, per-player
  bomb inventories/HUD/score state, zero-life player-out handling, shared
  objectives, player-2 bomb placement through the `N` fire key, and queued
  per-player high-score prompts at end of run.
- High-score table serialization back to the converted `RECS.DAT.json` resource
  format, name entry for new records with original-evidence letters/space,
  Backspace, and Enter handling, and validation coverage that writes only to
  temporary test files.
- Game-over and completed-game end states using strings recovered from
  `1000:1b14..1d42`, with final-level completion entering the completed-game
  path instead of wrapping directly into level 1.
- `PROEFS.SON` payload bytes are preserved as the original 130 six-byte
  playback steps. Non-direct sound synthesis now advances by the recovered
  `DS:78c0` cursor, honors the `0x7530` stop sentinel, and applies the
  gate/period bytes used by `1000:0fbe..1088`. Bomb explosion requests use the
  recovered direct-sweep cursors and the original `1000:165a` priority latch,
  bomb-object destruction queues the recovered priority-`3` object cue, portal
  transfer queues cursor `0x001a` at priority `4`, tile-trigger activation
  queues cursor `0x0027` at priority `6`, bonus pickup audio queues cursor
  `0x0008` at priority `5`, accepted player damage queues cursor `0x002d` at
  priority `4`, and player death/life-loss queues cursor `0x0056` at priority
  `5` while restoring the player energy byte to `100`. Live player damage now
  accumulates per-player damage bytes and drains them once per update pass,
  matching the recovered `DS:79e8`/`DS:79e9` model and original unsigned byte
  underflow death check rather than a modern one-hit cooldown gate. Manual
  reentry/restart still waits for the recovered state-2 `0x003c` countdown
  before returning a player to active control. The state-2 death/reentry
  animation initializer is now documented as the seven-byte `actor + 0x16`
  cursor populated by `1000:06ab`, and the
  actor update model locks the `1000:6053` counter, wrap, ping-pong, and
  mode-3 backup behavior. The runtime-frame oracle parses saved DOSBox debugger
  dumps for `DS:006a`, `DS:006c`, `DS:006d`, the `DS:c322..c324` frame table,
  and `DS:c21e` effect-entry words without making a visual claim, and reports
  each captured frame-table row in deterministic raw-byte form. A real temp-copy
  `dosbox-debug` capture stopped at runtime `01ED:7C89` now locks one original
  state-2 countdown sample: `DS=0C8F`, death cursor `0x45`, frame range
  `0x4a..0x4f`, and effect entry 0 position `0x0068,0x00a8`.
  `--debug-son-step-fields` exposes each recovered six-byte sound step as
  `period_word`, `gate_tick`, `period_ticks`, `unknown4`, and `unknown5` while
  keeping bytes `+4..+5` explicitly uninterpreted. The
  return-placement model tracks the `DS:c21e + 8 * actor[+0x01]` effect-entry
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
  `PROEFS.SON`. Field diagnostics preserve bytes `+4..+5` as raw unknowns, and
  their semantic meaning plus many non-explosion callsite-to-event mappings
  remain unresolved.
- Two-player split-screen is playable with independent bomb inventories, scores,
  and record prompts, but exact original panel artwork and reentry presentation
  remain approximate.
- High scores are persisted with original-evidence name-entry keys
  (letters/space, Backspace, Enter), but exact cursor drawing, typematic repeat,
  and name-entry presentation remain approximate.
- Bomb fuse timing, 2x2 footprint, player blast damage, monster hit-point
  blast damage, visual selectors, actor sprite indices, word-layer damage
  gating, bomb-object passability after explosion, and queued debris/collapse
  metadata now follow the `1000:414a`/`1000:370e`/expiration analysis. Active
  collapse/debris records
  now queue into the same per-player damage counters as monster contact and
  bomb blasts, but exact sprite playback and delayed state-2 life-count
  decrement remain simplified. The `actor + 0x16` state-2 cursor, cursor
  advancement rules, and `DS:c21e` placement math are locked as deterministic
  models. The live renderer now has provisional state-2 visual playback keyed
  to the recovered `0x4a..0x4f` cursor range and tested by
  `--debug-autoplayer death_visuals`, but it still reports `visual_claim=0`
  because the original frame-table field interpretation is not fully mapped.

See [docs/GHIDRA_NOTES.md](docs/GHIDRA_NOTES.md) for addresses and disassembly
anchors used in the reconstruction.
