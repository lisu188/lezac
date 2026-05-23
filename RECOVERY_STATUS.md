# Recovery Status

Last reviewed: 2026-05-18
Branch: `codex/gran-usage-guardrail`
Baseline: `origin/main`

## Completed This Iteration

- Added `tools/check_gran_usage_guardrail.py` to keep `GRAN.MST` as explicitly
  opaque data in the current C++ port. The checker counts all `gran_` source
  references and permits only loading, member storage, validation, and
  debug/roundtrip reporting; any new live gameplay or rendering use fails until
  original evidence proves the semantics.
- Extended the `GRAN.MST` guardrail with a synthetic self-test so the checker
  proves it rejects accidental live `gran_` gameplay/rendering references,
  missing debug-only function ranges, and docs that omit the guardrail pointer.
- Added `tools/check_visual_claim_guardrail.py` and explicit `visual_claim=0`
  lines to the remaining state-2 DOSBox oracle fixtures. All checked-in DOSBox
  fixtures now have a declared visual claim so parser/runtime evidence cannot
  accidentally masquerade as promoted frame evidence. The checker now also
  gates any future `visual_claim=1` fixture on
  `docs/recovery/visual_claim_promotions.md`, which must name original, C++,
  comparison frame artifacts, a promotion-ready frame-compare bundle, and the
  supporting recovery note. Its CTest self-test now exercises a synthetic
  promoted fixture and verifies missing checked-in comparison artifacts and
  unready bundles are rejected.
- Added `tools/check_runtime_evidence_guardrail.py` plus
  `docs/recovery/runtime_evidence_ledger.md` for original-runtime DOSBox
  fixtures. The guardrail requires each checked-in original capture to be from
  a temp copy, carry runtime `CS`/`DS`, and remain `visual_claim=0` until
  visual-frame evidence is promoted separately. It now also requires each
  ledger entry to point at
  `docs/recovery/original_runtime_fixture_notes.md`, where the supporting note
  must name the fixture explicitly.
- Added `tools/summarize_debug_capture_ready_results.py` and synthetic coverage
  so generic debug-capture ready runs now have the same result-review gate as
  actor-dispatch and lane-result handoffs. The summarizer counts planned,
  executed, failed, and environment-preflight states and can require successful
  executed candidates before promotion. `tools/check_debug_capture_ready_pipeline.py`
  now covers the full generic batch-summary, ready-runner, and result-summary
  handoff with synthetic data.
- Added `--debug-visual-table-oracle <fixture> [--expect-error]` as the next
  visual-fidelity evidence gate. The v1 parser normalizes visual table
  fixtures with scenario/runtime metadata, translated breakpoints, actor
  animation cursor fields, `DS:c322 + 4 * frame` row bytes, sprite bank/index
  candidates, draw offsets, and effect-entry before/after state. Synthetic and
  malformed CTest fixtures currently cover the state-2 death table consumption
  path and keep `visual_claim=0`, so no live renderer behavior changed.
- Added `tools/capture_original_visual_table_debug.sh` for the
  `state2_death_table_consumption` follow-up capture. It mirrors the existing
  DOSBox-debug helper shape with `debugger_seeded` output, environment
  preflight recording, runtime `CS`/`DS` command-plan expansion, and a
  fill-in candidate for `--debug-visual-table-oracle`. The generic debug
  capture summary, batch summary, and ready-manifest runner now understand
  `capture=visual_table`, so promoted visual-table evidence can use the same
  review path as behavior-4 and actor/contact captures.
- Added `tools/check_visual_table_oracle_fixtures.py` and extended the optional
  original-fixture convention gate for `visual_table_oracle_original*.txt`.
  Visual-table parser fixtures now have the same fixture/CMake/source-contract
  coverage as behavior-4, actor-update, and contact-scanner runtime oracles.
- Extended the generic debug-capture ready-manifest runner coverage with a
  synthetic `capture=visual_table` candidate, so the visual-table oracle flag is
  exercised before real state-2 visual-table captures are promoted. The
  ready-result summarizer coverage now carries the same visual-table lane
  through planned/executed result manifests, and the end-to-end generic
  ready-pipeline check now promotes actor-update and visual-table candidates
  together from batch summary through oracle execution and result review.
- Extended the generic debug-capture ready pipeline with a synthetic ready
  `capture=contact_scanner_runtime` candidate. The single-capture summary,
  batch ready-manifest writer, ready-manifest runner, ready-result summarizer,
  and full batch-to-result pipeline now all prove the
  `--debug-contact-scanner-runtime-oracle` handoff before contact-scanner
  DOSBox-debug evidence is promoted.
- Extended the same generic ready pipeline with a synthetic ready
  `capture=behavior4_runtime` candidate while preserving the incomplete
  behavior-4 skeleton failure case. Batch promotion and ready-manifest runner
  coverage now exercise all four runtime oracle families:
  behavior-4, actor-update, contact-scanner, and visual-table.
- Aligned `tools/run_debug_capture_ready_manifest.py` with the actor-dispatch
  and lane-result ready runners: `--allow-missing-fixtures` is now explicitly a
  dry-run-only forensic bypass, and live generic debug-capture ready runs reject
  the flag before parsing candidate fixtures.
- Updated `docs/recovery/ready_fixture_provenance_contract.md` and its checker
  so all three ready-manifest runners must document and enforce that
  dry-run-only missing-fixture bypass rule.
- Hardened the ready-result summarizers for actor-dispatch, lane-result, and
  generic debug-capture handoffs so inconsistent manifests fail if their
  aggregate `failures=` count disagrees with per-candidate `status=error`
  records, if a known status carries an impossible return code, or if indexed
  candidate records appear outside `ready_candidates=`. They now also require
  `mode=run` to contain no planned candidates and `mode=dry_run` to contain
  only planned candidates; mismatched per-candidate oracle flags fail at parse
  time, runtime `CS`/`DS` fields must be valid four-digit segments, recorded
  commands must end with the matching oracle flag and fixture, existing
  fixtures with `runtime_cs`/`runtime_ds` must match the result metadata, and
  existing fixture `visual_claim`/`temp_copy` metadata must remain
  non-visual temp-copy evidence. Checked-in `*original*` DOSBox fixtures under
  `tests/fixtures/dosbox` must also have runtime-evidence ledger entries whose
  docs notes name the fixture before a ready-result summary can promote them.
  The ready-manifest runners now apply the same fixture provenance guardrail
  before dry-run or live oracle execution, so an unledgered original fixture is
  rejected before it can produce a result manifest. The upstream ready-manifest
  writers for debug-capture batches, actor-dispatch sweeps, and lane-result
  sweeps also validate ready fixture provenance before writing promotion
  manifests. `docs/recovery/ready_fixture_provenance_contract.md` and
  `tools/check_ready_fixture_provenance_contract.py` now pin the documented
  contract to the shared validator and all writer/runner/result-summary call
  sites. `--require-success` rejects any remaining unknown candidate statuses
  or missing executed-candidate logs instead of treating them as promotable
  evidence.
- Added `tools/check_frame_compare_workflow.py` to pin the original-vs-C++
  frame comparison bundle contract. The guardrail verifies that
  `tools/compare_original_cpp_frames.sh` still captures C++ frames, attempts
  the DOSBox-original capture, runs `tools/frame_compare.py`, leaves missing
  original labels visible, writes `frame_compare_summary.txt` and
  `manifest.txt`, and keeps generated evidence outside the repository.
- Hardened `tools/capture_original_dosbox_frames.sh` with the shared original
  evidence preflight for screenshot captures. It now records
  `environment_preflight_command`, `environment_preflight.log`, and
  `environment_preflight=ok/error/skipped` in the original-frame manifest before
  DOSBox is launched, including Windows WSL/bash blockers such as
  `wsl_bash_reason=no_default_distro`.
- Hardened `tools/compare_original_cpp_frames.sh` so original-frame capture
  failures still leave a reviewable top-level bundle. The wrapper records
  `original_capture_driver.log`, `original_capture_exit`, original manifest/log
  paths, `compare_exit`, and missing-original summary rows before returning a
  nonzero `frame_compare_bundle=error`.
- Added `tools/summarize_frame_compare_bundle.py` plus synthetic coverage for
  successful, original-capture-failed, and compare-failed bundles. The summary
  reports frame counts, missing originals, compare errors, preflight state,
  `wsl_bash_reason`, and `promotion_ready`, with `--require-promotion-ready`
  for future visual-evidence promotion gates.
- Tightened the visual-claim promotion ledger so future `visual_claim=1`
  fixtures must also name a checked-in `frame_compare_bundle` whose
  `tools/summarize_frame_compare_bundle.py` result is `promotion_ready=1`.
  The visual-claim self-test now rejects missing artifacts, unready bundles, and
  mismatched ledger entries.
- Added `tools/write_visual_claim_promotion_entry.py` plus synthetic coverage
  to emit the exact `visual_claim=1` ledger entry from a checked-in,
  promotion-ready frame-compare bundle. The writer validates fixture/docs paths,
  selects a compared frame with original/C++/diff artifacts, and rejects unready
  bundles before printing a promotion line.
- Added `tools/validate_visual_claim_promotion_candidate.py` as the read-only
  promotion checklist before real ledger edits. It confirms the current fixture
  has exactly one declared visual claim, requires a promotion-ready frame bundle,
  generates the candidate entry, and reuses the committed visual-claim guardrail
  checks against the generated line.
- Added `tools/plan_visual_claim_promotions.py` for batch review of checked-in
  visual-claim promotion candidates. The key/value manifest names each fixture,
  frame-compare bundle, docs note, and optional frame label; the planner runs
  the same dry-run checks per candidate, prints ready ledger entries, and can
  fail with `--require-all-ready` when any candidate is blocked.
- Added a dedicated dry-run CTest for the pending natural forward lane-result
  probe: `--offset forward --route-step x:2.00 --route-step c:0.50` targeting
  `1000:3D3F`. This does not promote new evidence, but it keeps the next
  DOSBox/procmem route retry anchored to the documented no-freeze fixture and
  visible in the orchestrator contract.
- Added a CTest dry-run for the default lane-result route sweep matrix, locking
  the four planned natural-route probes
  `x:2.00`, `x:2.00,c:0.50`, `x:1.50,z:0.50`, and `x:2.00,m:0.35` at the
  build level before any DOSBox/procmem capture is attempted.
- Extended behavior-4 DOSBox-debug helper coverage so CMake dry-runs all three
  supported original evidence plans: level-2 spawner, level-3 spawner, and
  two-player target selection. These remain `debugger_seeded` capture plans
  with `visual_claim=0` until real DOSBox-debug transcripts are promoted.
- Extended actor-update and contact-scanner DOSBox-debug helper contracts so
  CMake names all three supported `debugger_seeded` plans:
  object-collision jump, monster-contact damage, and behavior-4 chase. These
  are still dry-run capture plans only, not promoted original runtime evidence.
- Aligned the behavior-4, actor-update, contact-scanner, and visual-table
  DOSBox-debug helper preflights with the process-memory wrappers by adding
  `--probe-wsl --require-wsl-bash-on-windows`. Failed Windows capture starts now
  preserve the current WSL blocker, such as `wsl_bash_reason=no_default_distro`,
  in the preflight log before DOSBox-debug is attempted.
- Extended the original-evidence environment checker with the observed Windows
  WSL shape where `wsl --status` succeeds but `wsl -e bash -lc true` fails with
  `WSL_E_DEFAULT_DISTRO_NOT_FOUND`. This keeps the no-default-distro blocker
  distinct from a missing `wsl.exe` or a fully failing WSL command.
- Extended actor/contact process-memory helper coverage so CMake names all nine
  supported freeze targets, from actor-update entry/exit through gate5/gate6
  and contact-scanner callsite/start/end. These remain guarded dry-run plans
  until a trusted WSL/DOSBox/procmem host captures runtime evidence.
- Added a CTest dry-run for the default actor-dispatch gate sweep, pinning the
  five-target matrix across gate5 entry/integration/exit, gate6, and the
  contact-scanner callsite before any live WSL/DOSBox/procmem run is promoted.
- Added a CTest dry-run for the default actor/contact route sweep, pinning the
  contact-scanner-start matrix across both pre-bomb and pre-route freeze timing
  and all four planned route probes.
- Added `--target-set all` to the actor-dispatch sweep planner and pinned it
  with CTest, so one dry-run command now expands all nine actor/contact
  process-memory targets before an approved live capture host is used.
- Extended actor-dispatch sweep summary coverage with a nine-target dry
  manifest, keeping downstream missing-target accounting pinned to the
  all-target planner output.
- Pinned the actor-dispatch sweep override contract: repeated `--target`
  arguments narrow the run even when `--target-set all` is present.
- Added ready-candidate summary coverage for a `contact_scanner_end`
  process-memory fixture, including the promoted
  `--debug-contact-scanner-runtime-oracle` handoff.
- Extended the actor-dispatch ready pipeline check so a ready
  `contact_scanner_end` fixture now travels end to end through summary,
  ready-manifest execution, and ready-result summarization.
- Added `tools/summarize_actor_dispatch_gate_sweep.py` and synthetic CTest
  coverage for completed actor dispatch-gate sweep manifests. The summarizer
  follows nested route-sweep manifests, counts capture statuses, reports
  observed runtime freezes, lists missing gate targets, and surfaces candidate
  fixtures for runtime-oracle normalization. It now labels each observed freeze
  with the matching `actor_update` or `contact_scanner` oracle flag and a
  runnable `oracle_command=` hint, plus `candidate_status=` readiness so skeleton
  fixtures are not mistaken for normalized evidence. The top-level summary now
  includes ready/incomplete/missing/none candidate counts for quick triage.
  Placeholder detection intentionally scans commented skeleton hints as well as
  active fixture records. `--require-ready` now exits nonzero when any observed
  freeze candidate is not promotable. `--write-ready-manifest` writes a
  follow-up promotion manifest containing only ready fixtures and oracle
  commands, and `tools/run_actor_dispatch_ready_manifest.py` can dry-run or
  execute that manifest so the next WSL/DOSBox pass can validate promoted
  candidates without hand-copying summary lines. The runner now rejects missing
  fixtures and mismatched oracle/flag pairs before execution, with an explicit
  dry-run-only bypass for forensic manifest review, and can write a result
  manifest for planned or executed oracle commands. Result manifests and logs
  are refused inside the repository unless explicitly allowed.
  `tools/summarize_actor_dispatch_ready_results.py` summarizes those result
  manifests and can require successful executed oracle runs. The synthetic
  `tools/check_actor_dispatch_ready_pipeline.py` check now exercises the full
  sweep-summary, ready-runner, and result-summary handoff.
- Added `lane-result-cs-scratch` instrumentation support to
  `tools/capture_original_explosion_procmem.py` for the final lane-helper
  result writes at `1000:3D3F` and `1000:3ED3`. The runtime-only trampoline
  parks code at `CS:F200`, scratch at `CS:F280`, and captures the result byte,
  `ES:DI`, `[BP+4]`/`[BP+6]`, `[BP-0D]`, active count/index, and the
  destination byte before `mov es:[di],al`.
- Hardened that instrumentation with an original-byte guard: both temp-copy
  and runtime child-memory patching require the target bytes to be `26 88 05`
  before writing the trampoline, and manifests/candidate fixtures now record
  `freeze_expected_old_bytes` plus `freeze_old_bytes`.
- Added `--describe-freeze-patch` to the capture helper so patch bytes,
  expected original bytes, file offsets, scratch offsets, and body bytes can be
  preflighted without launching DOSBox or reading process memory.
- Added Python-backed CTest preflight coverage for
  `--describe-freeze-patch` at `1000:3D3F` and `1000:3ED3`, pinning the
  shipped file offsets, expected bytes, trampoline bytes, scratch offset, and
  body offset.
- Added a negative preflight CTest for `lane-result-cs-scratch` at wrong
  offset `1000:3D2D`; the tool now reports a clean
  `freeze_patch_description=error` line instead of a Python traceback.
- Added `tools/check_explosion_lane_result_preflight.py`, a no-DOSBox Python
  verifier that imports the capture helper and checks both lane-result patch
  descriptions, expected original bytes, exact trampoline body bytes, and the
  wrong-offset guard in one command.
- Added `tools/check_explosion_lane_result_fixtures.py`, a no-C++ fixture
  expectation checker that verifies all checked-in lane-result fixtures still
  produce their intended parser outcome: two valid synthetic fixtures and eleven
  malformed fixtures. It also verifies each fixture has matching CMake coverage
  with the intended success/error regex, and that malformed fixtures are wired
  with `--expect-error` while valid fixtures are not.
- Added `tools/check_explosion_lane_result_layout.py`, a no-build consistency
  checker that locks the lane-result scratch field order across
  `capture_original_explosion_procmem.py`, `src/main.cpp`, and the fixture
  expectation helper.
- Added `tools/check_explosion_lane_result_orchestrator.py`, a no-DOSBox CMake
  coverage checker for the lane-result capture wrapper tests. It locks the
  expected orchestrator command shapes, regex fragments, and `WILL_FAIL`
  settings for 13 capture-wrapper CTest cases plus the wrapper-output checker
  CTest hook.
- Added `tools/check_explosion_lane_result_wrapper.py`, a no-DOSBox wrapper
  output checker that runs the lane-result preflight/dry-run matrix directly,
  including both preflight forms, default, with-oracle, forward-only,
  reverse-only, raw reverse-address, mixed-order, duplicate-offset,
  timing-argument pass-through, bad-offset,
  repo-output-refusal, and missing-approval cases.
- Added `tools/capture_original_lane_result_runtime.py`, a guarded wrapper for
  the pending original `1000:3D3F`/`1000:3ED3` runtime captures. Its
  `--preflight-only` mode is safe in restricted shells; full capture still
  requires explicit process-memory and runtime-instrumentation approval. The
  wrapper accepts both `out_dir [asset_dir]` and `--asset-dir` to match the
  older capture helper workflow, and `--dry-run` prints the exact capture/oracle
  commands without launching DOSBox. Full captures write those generated
  command lines into `manifest.txt` alongside the produced candidate paths,
  selected offset labels/addresses, approvals, and timing parameters. The repeatable
  `--offset` option allows retrying only `forward` (`1000:3D3F`) or only
  `reverse` (`1000:3ED3`), while still accepting the raw `3D3F`/`3ED3` address
  forms. Dry-run/full-capture success output and manifests now report both
  `offset_labels` and normalized `offset_addresses`.
- Added `python_tool_syntax_lane_result_preflight` CTest coverage so the
  capture helper, lane-result preflight helper, fixture expectation helper,
  scratch-layout helper, orchestrator expectation helper, and lane-result
  runtime wrapper are syntax-checked before runtime oracle or DOSBox evidence
  paths run.
- Extended `--debug-explosion-playback-oracle` with
  `observed_lane_forward_result`/`observed_lane_reverse_result` and
  `lane_result_*` fields. The oracle now validates that the far destination
  equals the caller argument pointer, the output byte equals the result local,
  the expected original byte signature is present, the scratch offset is the
  capture helper's `CS:F280` block, byte-width fields stay byte-sized, and loop
  bounds are sane.
- Added synthetic valid and malformed CTest fixtures for lane-result parsing:
  `explosion_playback_oracle_lane_result_scratch_synthetic.txt`,
  `explosion_playback_oracle_lane_result_reverse_scratch_synthetic.txt`,
  `explosion_playback_oracle_lane_result_missing_target_before.txt`,
  `explosion_playback_oracle_lane_result_bad_far_pointer.txt`,
  `explosion_playback_oracle_lane_result_bad_output_local.txt`,
  `explosion_playback_oracle_lane_result_bad_expected_old_bytes.txt`,
  `explosion_playback_oracle_lane_result_expected_without_old_bytes.txt`,
  `explosion_playback_oracle_lane_result_missing_expected_old_bytes.txt`,
  `explosion_playback_oracle_lane_result_bad_scratch_offset.txt`,
  `explosion_playback_oracle_lane_result_bad_kind.txt`,
  `explosion_playback_oracle_lane_result_bad_loop_bounds.txt`,
  `explosion_playback_oracle_lane_result_bad_target_before_width.txt`, and
  `explosion_playback_oracle_lane_result_field_without_present.txt`.
- Extended the C++ explosion oracle to parse `freeze_expected_old_bytes` and
  reject fixtures whose `freeze_old_bytes` do not start with the expected
  byte sequence.
- The explosion oracle success line now emits
  `freeze_expected_old_bytes_present`, `freeze_expected_old_bytes`, and
  `freeze_old_bytes`; the forward/reverse synthetic lane-result CTest regexes
  pin `268805`.
- Promoted
  `explosion_playback_oracle_original_3ed3_lane_result_runtime.txt` from an
  approved WSL/DOSBox process-memory run. It freezes `1000:3ED3` at runtime
  `01ED:3ED3`, records the guarded original bytes `268805`, captures scratch
  output `0x00ef`, `ES:DI=18B3:3FE6`, `[BP+4]/[BP+6]=18B3:3FE6`,
  result local `0x00ef`, active count/index `1/1`, and target-before byte
  `0xde`; the fixture remains `visual_claim=0`.
- Promoted
  `explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded.txt`
  from an approved WSL/DOSBox process-memory run with labeled runtime seeding.
  The seed patch at runtime `01ED:4C96` writes `DS:655E=0xC004`, calls the
  original forward helper body at `01ED:3BB2`, returns to `01ED:4C99`, and then
  freezes `1000:3D3F` at runtime `01ED:3D3F`. The fixture records byte guard
  `268805`, scratch `01ED:F280`, result/output `0x00fa`,
  `ES:DI=0C44:78D2`, `[BP+4]/[BP+6]=0C44:78D2`, active count/index `1/1`,
  target-before byte `0xf3`, and remains `visual_claim=0`.
- Natural-route `1000:3D3F` evidence remains pending. The 2026-05-06 default,
  right-hold timing, and before-bomb patch attempts all loaded the runtime patch
  but did not hit the forward result freeze, so the promoted forward fixture is
  intentionally labeled runtime-seeded rather than full gameplay-route evidence.
- Extended the original process-memory capture route driver with repeatable
  `--route-step KEY:SECONDS` holds, preserving the old `--right-key` /
  `--right-hold-seconds` route as the default. The lane-result wrapper passes
  those route steps through and records them in manifests/candidate fixtures.
- Promoted
  `explosion_playback_oracle_original_3d3f_lane_result_route_step_no_freeze.txt`
  from a natural original-control route `x:2.00,c:0.50`. It loaded the
  `1000:3D3F` runtime patch and records byte guard `268805`, but no forward
  result freeze or lane-result scratch appeared. The chosen sample still shows
  live lane globals (`lane_update_flag=0x05`, `lane_word=0x0004`,
  `lane_target_offset=0x072c`, reverse input `0xfb`), so it is useful negative
  evidence for the natural forward-route gap.
- Added `tools/sweep_original_lane_result_routes.py`, a guarded route-sweep
  wrapper for repeated natural lane-result probes. Its dry-run mode prints all
  generated `capture_original_lane_result_runtime.py` commands, defaults to the
  current `x`, `x,c`, `x,z`, and `x,m` route set, and live capture still
  requires both process-memory/runtime-instrumentation approval flags.
- Added `tools/check_lane_result_route_sweep.py` and CTest coverage for the
  route-sweep wrapper's default route labels, custom route labels, approval
  refusal, repository-output refusal, and malformed route parsing.
- Added `tools/summarize_lane_result_route_sweep.py` and synthetic CTest
  coverage for completed lane-result route-sweep manifests. The summary follows
  child runtime manifests, classifies candidate fixtures as `ready`,
  `no_freeze`, `incomplete`, or `missing`, emits
  `--debug-explosion-playback-oracle` commands, and can write a ready-promotion
  manifest for natural `1000:3D3F` or `1000:3ED3` freezes.
- Added `tools/run_lane_result_ready_manifest.py`,
  `tools/summarize_lane_result_ready_results.py`, and an end-to-end synthetic
  lane-result ready-pipeline CTest. The runner validates the ready manifest,
  refuses repository-local logs/results by default, executes only
  `--debug-explosion-playback-oracle` candidates, and records planned or
  executed oracle results for promotion gating. Granular CTest helpers now pin
  the runner and result-summary error cases separately from the full pipeline
  check.
- Added `tools/preflight_original_evidence_environment.py` and synthetic CTest
  coverage. The preflight reports shipped asset availability and the local
  `bash`/DOSBox/`dosbox-debug`/Xvfb/`xdotool` toolchain, with require modes that
  fail before a long original-evidence sweep starts on an unprepared host.
  The WSL probe now distinguishes a present `wsl.exe` from a usable default
  Linux distro by running `wsl -e bash -lc true` and reporting
  `wsl_bash_reason=no_default_distro` for the current no-distro blocker.
  `--require-wsl-bash-on-windows` promotes that probe to a Windows-only
  `reason=wsl_bash_not_usable` failure while leaving native Linux/WSL preflights
  free to pass without a nested `wsl.exe`.
- `tools/sweep_original_lane_result_routes.py` now prints the environment
  preflight command in dry-run and runs the process-memory capture preflight
  once before any live route commands, unless explicitly skipped with
  `--skip-environment-preflight`. The route-sweep preflight includes
  `--probe-wsl --require-wsl-bash-on-windows`, so Windows dry-runs and failed
  live starts preserve the exact WSL usability blocker before a DOSBox
  process-memory batch begins. Direct
  `tools/capture_original_lane_result_runtime.py` live captures now run the
  same environment preflight and record `environment_preflight=` in their
  manifests; route sweeps pass `--skip-environment-preflight` to child direct
  captures after the top-level check succeeds.
- `tools/sweep_original_actor_contact_routes.py` and
  `tools/sweep_original_actor_dispatch_gates.py` now use the same
  process-memory environment preflight before live actor/contact capture
  sweeps, also with `--probe-wsl --require-wsl-bash-on-windows`. Dispatch-gate
  sweeps run the host check once at the top level and pass
  `--skip-environment-preflight` to child actor/contact sweeps so a single
  matrix does not repeat identical tool probes. Direct
  `tools/capture_original_actor_contact_procmem.sh` live runs also record
  `environment_preflight=` in their manifests and execute the shared preflight
  unless `LEZAC_ACTOR_CONTACT_PROCMEM_SKIP_ENVIRONMENT_PREFLIGHT=1` is set by
  an already-verified parent sweep.
- Lane-result and actor dispatch-gate sweep summaries now surface
  `environment_preflight=` state and support
  `--require-environment-preflight`, so ready-candidate promotion scripts can
  fail explicitly when a manifest came from an unverified or legacy capture
  host.
- Lane-result and actor dispatch ready-manifest runners now propagate
  `source_environment_preflight=` into result manifests and support
  `--require-source-environment-preflight`; the matching result summarizers can
  require the same field before accepting executed oracle results.
- The lane-result and actor dispatch ready-pipeline CTest helpers now exercise
  the strict preflight path end to end: sweep summary, ready manifest runner,
  and result summary all use their corresponding preflight-required flags.
- Tightened `--require-procmem-capture` to match the actual process-memory
  wrapper dependencies: direct `Xvfb`, `zutty`, and `script` are now required
  along with DOSBox-debug, `xdotool`, `python3`, and `pgrep`.
- Added the `timeout` command to the full original/debug capture preflight
  requirements because the DOSBox-debug helper scripts wrap their launches with
  `timeout`.
- Brought `tools/capture_original_behavior4_debug.sh` up to the actor/contact
  debug-helper handoff shape: it now leaves a `candidate_fixture.txt` skeleton,
  a `debugger_commands_runtime.txt` placeholder, and copies observed
  `runtime_cs`/`runtime_ds` metadata into the manifest/raw dump when a live
  DOSBox-debug run exposes registers before timing out.
- The behavior-4, actor-update, contact-scanner, and visual-table DOSBox-debug
  helpers now run the shared `--require-debug-capture` environment preflight
  before live DOSBox-debug launch, write `environment_preflight.log`, and record
  the preflight status in their manifests. Dry runs explicitly mark
  `environment_preflight=dry_run`; per-helper skip environment variables are
  reserved for already-verified forensic reruns.
- Added `tools/summarize_debug_capture.py` plus synthetic coverage so a single
  behavior-4, actor-update, contact-scanner, or visual-table DOSBox-debug
  capture directory can be triaged as ready, incomplete, missing, or
  environment-failed. The summary prints the matching runtime-oracle command and
  can require both a promotion-ready fixture and `environment_preflight=ok`.
- Added `tools/summarize_debug_capture_batch.py` plus synthetic coverage for
  whole WSL evidence batches. The batch summary recursively finds supported
  debug-capture manifests, counts ready/incomplete/missing candidates, reports
  environment-preflight and runtime-metadata totals, and can write a compact
  ready-candidates manifest for the promotable fixtures.
- Added `tools/run_debug_capture_ready_manifest.py` plus synthetic coverage so
  ready debug-capture manifests can be dry-run or executed through the matching
  runtime oracle only. The runner validates oracle/flag pairs, can require
  per-candidate `environment_preflight=ok`, writes optional logs, and emits a
  result manifest for promotion review.
- Added a key/value lane-result handoff checklist to
  `docs/recovery/dosbox_explosion_process_memory_attempt_2026-04-24.md` with
  the pending WSL preflight/capture commands, expected manifest/candidate paths,
  alias mapping, byte guard, scratch address, and promotion criteria.
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
- Added `--debug-behavior4-runtime-oracle <fixture> [--expect-error]` with
  synthetic and malformed DOSBox fixture coverage. The parser records
  scenario/level, runtime `CS`/`DS`, behavior-4 spawner fields, actor
  before/after position, 8.8 velocity, motion timer, target/player-dead state,
  optional `DS:` dump rows, and required anchors for the spawner loop
  `1000:7A6B..7C2C`, behavior-4 branch `1000:728C..731B`, and 8.8 integration
  `1000:73E5..741B`.
- Added `tools/capture_original_behavior4_debug.sh <out_dir> [asset_dir]
  <scenario>` for the level-2 spawner, level-3 spawner, and target-selection
  behavior-4 scenarios. It writes `manifest.txt`, `raw_debugger_dump.txt`, and
  `debugger_commands.txt`, labels current captures `debugger_seeded`, and has a
  dry-run CTest path for environments without DOSBox-debug.
- Added `tools/check_behavior4_runtime_oracle_fixtures.py` so behavior-4
  fixture expectations, CMake wiring, and the C++ oracle command/source
  contract can be validated without DOSBox or a local C++ compiler. The checker
  now keeps the fixed synthetic/malformed baseline while allowing future
  `behavior4_runtime_oracle_original*.txt` captures only when they parse as
  valid runtime evidence and have matching CTest coverage.
- Added `tools/check_optional_original_oracle_fixtures.py` so the behavior-4,
  actor-update, and contact-scanner runtime-oracle fixture lanes keep the same
  optional-original convention: original fixtures are valid-only, must have
  CTest coverage, and remain `visual_claim=0`.
- Added `tools/check_behavior4_debug_capture_helper.py` to lock the
  behavior-4 DOSBox-debug helper's supported scenarios, debugger anchors,
  manifest/raw-output contract, `debugger_seeded` docs, and CMake dry-run
  wiring without requiring `bash` or DOSBox locally.
- Restored a native Windows validation path with Visual Studio Build Tools and
  the local vcpkg SDL2 package by propagating `SDL2_LIBRARY_DIRS`, defining
  `SDL_MAIN_HANDLED`, and making the state-2 effect-placement lambdas
  MSVC-compatible. The sanitized native Debug build in `build-win-codex-vs3`
  passed 156/156 CTest tests. The bash-only behavior-4 helper dry-run is now
  registered only when `bash` is available, so the native Windows suite can run
  without a manual exclusion while still preserving the helper's CMake wiring.
- Added `tools/run_native_windows_validation.ps1` and
  `tools/check_native_windows_validation_helper.py` to make that native Windows
  validation recipe repeatable: it sanitizes duplicate `PATH`/`Path` entries,
  configures Visual Studio Build Tools with the local vcpkg SDL2 package, builds
  `build-win-codex-vs3`, and runs CTest unless `-SkipTests` is supplied.
- Added `--debug-actor-update-runtime-oracle <fixture> [--expect-error]` with
  synthetic and malformed fixture coverage. The parser records scenario/level,
  runtime `CS`/`DS`, actor before/after state, contact scanner flags, tile probe
  passability/standability fields, optional `DS:` dump rows, and required
  anchors for the contact scanner `1000:5CB0..604F` and actor update
  `1000:6053..777F`. No live gameplay behavior changed from this synthetic
  parser coverage.
- Added `tools/capture_original_actor_update_debug.sh <out_dir> [asset_dir]
  <scenario>` for `object_collision_jump_live`, `monster_contact_damage_live`,
  and `monster_behavior4_chase`. It writes `manifest.txt`,
  `raw_debugger_dump.txt`, `candidate_fixture.txt`, `debugger_commands.txt`, and
  `actor_update_debug_capture.log`, labels current captures `debugger_seeded`,
  and has a dry-run CTest path for environments with `bash`. Live DOSBox-debug
  attempts now append any observed debugger prompt `runtime_cs`/`runtime_ds`
  values to both `manifest.txt` and `raw_debugger_dump.txt`, and write
  `debugger_commands_runtime.txt` with concrete runtime breakpoint/dump
  commands. The candidate fixture is intentionally a fill-in skeleton until
  original runtime fields and dump rows are captured.
- Added `tools/check_actor_update_runtime_oracle_fixtures.py` so the
  actor-update fixture set, expected malformed outcomes, CMake wiring, and C++
  oracle command/source contract can be validated without DOSBox or a compiler.
  The checker now keeps the fixed synthetic/malformed baseline while allowing
  future `actor_update_runtime_oracle_original*.txt` fixtures only if they parse
  as valid runtime evidence and have matching CTest coverage.
- Added `--debug-contact-scanner-runtime-oracle <fixture> [--expect-error]`
  with synthetic and malformed fixture coverage. This isolates the probable
  scanner window `1000:5CB0..604F` from full actor-update evidence by parsing
  subject/other actor boxes, overlap size, contact flags, and pending damage.
  `tools/check_contact_scanner_runtime_oracle_fixtures.py` validates fixture
  outcomes, CMake wiring, and the C++ source contract without DOSBox. It now
  accepts future `contact_scanner_runtime_oracle_original*.txt` fixtures under
  the same valid-oracle and CTest-coverage requirements.
- Added `tools/capture_original_contact_scanner_debug.sh <out_dir> [asset_dir]
  <scenario>` for `monster_contact_damage_live`, `object_collision_jump_live`,
  and `monster_behavior4_chase`. It writes scanner-only `manifest.txt`,
  `raw_debugger_dump.txt`, `candidate_fixture.txt`, `debugger_commands.txt`, and
  `contact_scanner_debug_capture.log`, labels current captures
  `debugger_seeded`, and has CMake/checker coverage for dry-run wiring. Live
  DOSBox-debug attempts now append any observed debugger prompt
  `runtime_cs`/`runtime_ds` values to both `manifest.txt` and
  `raw_debugger_dump.txt`, and write `debugger_commands_runtime.txt` with
  concrete runtime breakpoint/dump commands. The candidate fixture is
  intentionally a fill-in skeleton until original runtime fields and dump rows
  are captured.
- WSL/Xvfb/DOSBox-debug launch is unblocked in the approved WSL context. Short
  2026-05-11 temp-copy probes reached the DOSBox-debug prompt and recorded
  runtime `CS=01ED`, `DS=01DD` for both contact-scanner and actor-update helper
  paths. They still time out with DOSBox-debug exit `124` because debugger
  command submission and semantic breakpoint seeding are the remaining blocker;
  no original actor/contact runtime fixture has been promoted from these launch
  probes.
- Added `tools/capture_original_actor_contact_procmem.sh`, a guarded
  process-memory instrumentation wrapper for `actor_update_start`,
  `actor_update_end`, `actor_update_gate5`, `actor_update_gate5_integration`,
  `actor_update_gate5_exit`, `actor_update_gate6`, `contact_scanner_callsite`,
  `contact_scanner_start`, and `contact_scanner_end`. `contact_scanner_callsite`
  maps the static near call at
  `1000:6555` that targets `1000:5CB0`; the only direct near call to the scanner
  entry found in the shipped code image is at that callsite. It reuses the
  proven child DOSBox-debug process-memory scanner, requires
  `LEZAC_ACTOR_CONTACT_APPROVE_PROCMEM=1` and
  `LEZAC_ACTOR_CONTACT_APPROVE_RUNTIME_INSTRUMENTATION=1` for live runs, and
  records `visual_claim=0` because these are reachability probes rather than
  pristine gameplay-route fixtures. Direct live runs now execute the shared
  process-memory environment preflight before touching DOSBox-debug and record
  `environment_preflight=` in the manifest. It now writes
  `<target>_runtime_candidate.txt` with runtime metadata and raw route-state
  dumps, and accepts `LEZAC_ACTOR_CONTACT_ROUTE_STEPS` as comma-separated
  `key:seconds` route holds for scanner-path tuning. It can also set
  `LEZAC_ACTOR_CONTACT_RUNTIME_FREEZE_BEFORE_ROUTE=1` so the runtime patch is
  applied immediately after level start, before route movement, for helpers that
  may only execute during contact positioning. A 2026-05-11 live probe at
  `actor_update_start` froze `1000:6053` at runtime `01ED:6053`, with
  `freeze_old_bytes=5589`, `freeze_patch_bytes=ebfe`,
  `freeze_runtime_patch_applied=1`, `instrumented_freeze_observed=1`, runtime
  `CS=01ED`, and runtime `DS=0C8F`.
- Added `tools/check_actor_contact_procmem_helper.py` and CMake dry-run
  coverage so the guarded wrapper's targets, approvals, output contract, and
  docs are checked without process-memory access.
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

- 2026-05-15 lane-write route-sweep checkpoint: native Windows validation
  helper passed with `-SkipTests`, then focused CTest passed 57/57 for
  `lane_write|lane_result|explosion_lane`. This covered the new lane-write
  preflight, wrapper-output, and route-sweep checks plus the existing
  lane-result/explosion oracle guardrails. `git diff --check` passed with only
  existing CRLF normalization warnings on touched text files.
- 2026-05-15 continuation: WSL was present but no Linux distribution was
  installed (`WSL_E_DEFAULT_DISTRO_NOT_FOUND`), so live DOSBox/process-memory
  capture is blocked on this host. The no-WSL continuation added the lane-write
  route-sweep summarizer instead. After refreshing the native build metadata,
  focused CTest passed 58/58 for `lane_write|lane_result|explosion_lane`.
- 2026-05-15 handoff continuation: direct Python checks passed for
  `tools/check_lane_write_ready_pipeline.py`,
  `tools/check_lane_result_ready_manifest.py`, and
  `tools/check_lane_result_ready_results.py` after making the shared ready
  runner/result summarizer prefix-configurable. After refreshing native build
  metadata again, focused CTest passed 59/59 for
  `lane_write|lane_result|explosion_lane`. Full native Windows CTest then
  passed 201/201 with `ctest --test-dir build-win-codex-vs3 -C Debug
  --output-on-failure`.
- 2026-05-11 continuation: bundled Python helper/oracle checks passed for
  `tools/check_actor_update_debug_capture_helper.py`,
  `tools/check_contact_scanner_debug_capture_helper.py`,
  `tools/check_actor_update_runtime_oracle_fixtures.py`, and
  `tools/check_contact_scanner_runtime_oracle_fixtures.py`.
- `git --git-dir=.codex-git --work-tree=. diff --check` passed; Git reported
  only existing CRLF normalization warnings for touched Markdown files.
- WSL syntax checks passed for `tools/capture_original_contact_scanner_debug.sh`
  and `tools/capture_original_actor_update_debug.sh`.
- WSL dry-runs wrote complete helper artifacts outside the repository at
  `/tmp/lezac-contact-scanner-dry-run-codex-20260511` and
  `/tmp/lezac-actor-update-dry-run-codex-20260511`.
- Short WSL/Xvfb/DOSBox-debug launch probes wrote temp-copy manifests at
  `/tmp/lezac-contact-scanner-live2-codex-20260511` and
  `/tmp/lezac-actor-update-live-codex-20260511`. Both reached the debugger
  prompt and recorded `runtime_cs=01ED`, `runtime_ds=01DD`; both timed out with
  DOSBox-debug exit `124` because debugger command submission is still pending.
- Follow-up helper dry-runs now also emit `debugger_commands_runtime.txt` as a
  placeholder, and live probes overwrite it with runtime-translated debugger
  commands when `runtime_cs` is observed. Verified live outputs at
  `/tmp/lezac-contact-runtime-command-live2-codex-20260511` and
  `/tmp/lezac-actor-runtime-command-live2-codex-20260511` contain concrete
  `BP 01ED:5CB0`, `BP 01ED:604F`, actor-update `BP 01ED:6053`/`01ED:777F`,
  and `D 01DD:...` dump commands.
- `powershell -ExecutionPolicy Bypass -File tools\run_native_windows_validation.ps1
  -BuildDir build-win-codex-vs3 -Configuration Debug` passed: configure/build
  succeeded and CTest reported 169/169 tests passing.
- After adding runtime-translated debugger command files, the same native
  validation helper passed again: configure/build succeeded and CTest reported
  169/169 tests passing.
- Focused native CTest after the artifact cleanup passed:
  `ctest --test-dir build-win-codex-vs3 -C Debug -R
  "actor_update_debug_capture_helper_expectations|contact_scanner_debug_capture_helper_expectations"
  --output-on-failure` reported 2/2 tests passing.
- Guarded process-memory wrapper smoke evidence: live WSL output under
  `/tmp/lezac-actor-6053-freeze-procmem-codex-20260511` recorded
  `instrumented_freeze_observed=1` for `1000:6053`, with matching tail-frame
  screenshots. The generated candidate remains an explosion-helper artifact and
  was not promoted as actor/contact semantic evidence.
- The repeatable wrapper was then verified at
  `/tmp/lezac-actor-contact-procmem-live-codex-20260511`; its top-level
  manifest records `target=actor_update_start`, `runtime_cs=01ED`,
  `runtime_ds=0C8F`, `freeze_runtime=01ED:6053`, `freeze_old_bytes=5589`,
  `freeze_patch_bytes=ebfe`, `freeze_runtime_patch_applied=1`, and
  `instrumented_freeze_observed=1`.
- A live `contact_scanner_start` probe at
  `/tmp/lezac-contact-scanner-start-procmem-live-codex-20260511` loaded the
  runtime patch at `01ED:5CB0` (`freeze_old_bytes=5589`,
  `freeze_patch_bytes=ebfe`, `freeze_runtime_patch_applied=1`) but did not
  freeze (`instrumented_freeze_observed=0`) on the default level-1 route. This
  is route/timing evidence only; the scanner still needs a tuned collision path.
- The process-memory sampler now includes actor/contact-oriented route dumps
  for `DS:7900` and `DS:7A00` alongside the existing `DS:79E0` player-state
  window.
- The wrapper now writes `<target>_runtime_candidate.txt` as a non-promoted
  oracle scaffold. Dry-run route tuning was verified with
  `LEZAC_ACTOR_CONTACT_ROUTE_STEPS=x:1.0,n:0.2,z:0.5`, and a live
  `actor_update_start` run at
  `/tmp/lezac-actor-contact-candidate-live-codex-20260511` produced
  `actor_update_start_runtime_candidate.txt` with runtime `CS=01ED`,
  `DS=0C8F`, freeze metadata, and repeated `DS:7900`/`DS:79E0`/`DS:7A00`
  route-state dump blocks.
- A tuned `contact_scanner_start` route
  (`LEZAC_ACTOR_CONTACT_ROUTE_STEPS=x:5.0,m:0.5,x:2.0`) at
  `/tmp/lezac-contact-scanner-route-x5m-codex-20260511` entered active level-1
  gameplay and preserved `DS:7900`/`DS:79E0`/`DS:7A00` route-state dumps, but
  still loaded the `01ED:5CB0` patch without freezing. This makes a pre-route
  freeze mode the next scanner probe rather than promoting the no-freeze route
  as semantic contact evidence.
- The matching pre-route freeze run at
  `/tmp/lezac-contact-scanner-before-route-codex-20260511` applied the
  `01ED:5CB0` patch immediately after level start
  (`freeze_runtime_before_route=1`, `freeze_runtime_patch_phase=before_route`)
  and then replayed the same `x:5.0,m:0.5,x:2.0` route. It also did not freeze,
  so the current conclusion is narrow: this level-1 movement route does not hit
  the scanner start even when the patch is applied before movement. The next
  contact-scanner probe should target a different route or validate whether
  `1000:5CB0` is the correct entry anchor for live player/monster contact.
- Added `tools/sweep_original_actor_contact_routes.py`, a guarded route-sweep
  planner/runner for `actor_update_start`, `actor_update_end`,
  `contact_scanner_start`, and `contact_scanner_end`. It expands repeated
  `--route KEY:SECONDS,...` entries across `before_bomb`, `before_route`, or
  both runtime-freeze timings, writes one manifest, and forwards approvals to
  `tools/capture_original_actor_contact_procmem.sh`. Added
  `tools/check_actor_contact_route_sweep.py` plus CTest dry-run/output coverage.
- A live `contact_scanner_start` route sweep at
  `/tmp/lezac-actor-contact-route-sweep-live-codex-20260511` ran pre-route
  probes for `x:8.00` and `x:5.00,m:0.50,x:4.00`. Both runs loaded
  `01ED:5CB0` with `runtime_cs=01ED`, `runtime_ds=0C8F`,
  `freeze_runtime_before_route=1`, and `instrumented_freeze_observed=0`.
- A matching `contact_scanner_end` pre-route probe at
  `/tmp/lezac-actor-contact-end-sweep-live-codex-20260511` loaded
  `01ED:604F` on route `x:5.00,m:0.50,x:4.00` and also did not freeze. The
  runtime bytes at that anchor were `c9c2`, so this is best treated as a
  return-tail probe rather than proof that the scanner body is unreachable.
- Added `tools/check_actor_contact_callsite_scan.py` to lock the static
  contact-scanner anchors in `LEZAC.EXE`: entry bytes `55 89` at `1000:5CB0`,
  return bytes `c9 c2 02` at `1000:604F`, the single direct near call at
  `1000:6555` (`e8 58 f7`) targeting `1000:5CB0`, and the actor-update entry
  bytes `55 89` at `1000:6053`.
- Added `tools/check_actor_contact_callsite_context.py` to pin the immediate
  control-flow context around that callsite: `1000:654E` compares the local
  byte at `[bp-31h]` with `06`, `1000:6552` skips to `1000:655B` when it does
  not match, `1000:6554..6557` performs `push bp; call 1000:5CB0`, and
  `1000:6558` jumps to the shared integration path at `1000:73E5`. This keeps
  the next live probe focused on reaching the gated branch rather than
  rediscovering the scanner entry.
- Extended that checker to cover the neighboring `05` gate at `1000:65A2`:
  when the path reaches `1000:65BD`, the branch can enter integration through
  `1000:65D7`; when it reaches `1000:65CE` and the end condition matches, it
  jumps to actor-update end `1000:777F`. A scan of direct near jumps to
  `1000:73E5` inside `1000:6053..777F` now locks the pair
  `1000:6558,1000:65D7`.
- Added process-memory wrapper targets for those gates:
  `actor_update_gate5` at `1000:65A2`, `actor_update_gate5_integration` at
  `1000:65D7`, and `actor_update_gate6` at `1000:654E`. The route-sweep helper
  accepts them too, so the next live DOSBox pass can sweep these branch gates
  directly.
- Added `tools/check_actor_update_dispatch_gates.py` to scan every
  `cmp [bp-31h], imm` gate in `1000:6053..777F`. It currently locks
  `1000:654E = 06`, `1000:65A2 = 05`, and the later `1000:7595 = 05` exit gate
  whose equal branch jumps to `1000:777F`. The late exit is exposed as the
  process-memory target `actor_update_gate5_exit`.
- Added `tools/sweep_original_actor_dispatch_gates.py`, a multi-target planner
  for the mapped actor-update gates. Its default target set is
  `actor_update_gate5`, `actor_update_gate5_integration`,
  `actor_update_gate5_exit`, `actor_update_gate6`, and
  `contact_scanner_callsite`, delegating each target to the existing guarded
  actor/contact route-sweep helper. `tools/check_actor_dispatch_gate_sweep.py`
  locks the default dry-run, custom target/timing routes, live-approval
  refusal, repo-output refusal, and malformed route handling.
- Extended `--debug-actor-update-runtime-oracle` with optional dispatch-gate
  reporting. The parser still requires the original actor/scanner start/end
  anchors, but now appends `dispatch_gates=` with any normalized breakpoints for
  `actor_update_gate5`, `actor_update_gate5_integration`,
  `actor_update_gate5_exit`, `actor_update_gate6`, and
  `contact_scanner_callsite`. Added
  `actor_update_runtime_oracle_dispatch_gates_synthetic.txt` to prove the field
  without changing live gameplay behavior.
- Updated `tools/capture_original_actor_contact_procmem.sh` candidate skeletons
  so actor-update targets list the required oracle anchors
  `1000:5CB0,1000:604F,1000:6053,1000:777F`. Dispatch-gate targets also record
  `dispatch_gate_candidate=<label>` and a `dispatch_gates=` promotion hint,
  making future process-memory captures easier to normalize into oracle
  fixtures.
- A live `contact_scanner_callsite` pre-route probe at
  `/tmp/lezac-contact-callsite-live-codex-20260511` on route
  `x:5.00,m:0.50,x:4.00` loaded `01ED:6555` with old bytes `e858`,
  `freeze_runtime_before_route=1`, `runtime_cs=01ED`, `runtime_ds=0C8F`, and
  `instrumented_freeze_observed=0`. Combined with the entry no-freeze probes,
  this points to the route not reaching the scanner callsite rather than an
  incorrect `1000:5CB0` entry byte mapping.
- Focused native CTest passed for
  `python_tool_syntax_lane_result_preflight|actor_contact_procmem_helper_expectations`
  with 2/2 tests passing. Full native validation then passed again:
  configure/build succeeded and CTest reported 170/170 tests passing.
- After adding pre-route freeze timing, focused helper validation and full
  native validation passed again: configure/build succeeded and CTest reported
  170/170 tests passing.
- After adding the actor/contact route-sweep helper, full native validation
  passed again: configure/build succeeded and CTest reported 172/172 tests
  passing.
- After adding the static callsite scan and `contact_scanner_callsite` probe
  target, full native validation passed again: configure/build succeeded and
  CTest reported 173/173 tests passing.
- After adding the static callsite-context checker, focused Python checks for
  `check_actor_contact_callsite_scan.py` and
  `check_actor_contact_callsite_context.py` passed, then
  `powershell -ExecutionPolicy Bypass -File tools\run_native_windows_validation.ps1
  -BuildDir build-win-codex-vs3 -Configuration Debug` passed:
  configure/build succeeded and CTest reported 174/174 tests passing.
- After extending the callsite-context checker to cover the neighboring `05`
  gate and both direct `1000:73E5` integration jumps, focused CTest
  `actor_contact_callsite_context` passed after reconfigure, and full native
  validation passed again: configure/build succeeded and CTest reported
  174/174 tests passing.
- After adding process-memory probe targets for the `05`/`06` actor-update
  gates, focused Python checks for `check_actor_contact_procmem_helper.py` and
  `check_actor_contact_route_sweep.py` passed, focused CTest
  `actor_contact_route_sweep_output_expectations|actor_contact_procmem_helper_expectations`
  passed after reconfigure, and full native validation passed again:
  configure/build succeeded and CTest reported 174/174 tests passing.
- After adding the dispatch-gate scan and `actor_update_gate5_exit` probe
  target, focused Python checks for `check_actor_update_dispatch_gates.py`,
  `check_actor_contact_procmem_helper.py`, and
  `check_actor_contact_route_sweep.py` passed. Focused CTest
  `actor_update_dispatch_gates|actor_contact_route_sweep_output_expectations|actor_contact_procmem_helper_expectations`
  passed after reconfigure, and full native validation passed again:
  configure/build succeeded and CTest reported 175/175 tests passing.
- After adding the actor dispatch-gate sweep planner, focused Python checks for
  `check_actor_dispatch_gate_sweep.py` and
  `sweep_original_actor_dispatch_gates.py --dry-run` passed. Focused CTest
  `python_tool_syntax_lane_result_preflight|actor_dispatch_gate_sweep_dry_run|actor_dispatch_gate_sweep_output_expectations`
  passed after reconfigure, and full native validation passed again:
  configure/build succeeded and CTest reported 177/177 tests passing.
- After extending the actor-update oracle with `dispatch_gates=`, focused
  fixture validation `check_actor_update_runtime_oracle_fixtures.py` passed with
  5 fixtures (2 valid, 3 malformed). A direct Visual Studio build hit the known
  duplicate `Path`/`PATH` MSBuild environment issue, so validation continued
  through `tools\run_native_windows_validation.ps1`; the wrapper build
  succeeded and CTest reported 178/178 tests passing.
- After adding dispatch-gate promotion hints to actor/contact process-memory
  candidate skeletons, focused helper validation
  `check_actor_contact_procmem_helper.py` passed, and full native validation
  through `tools\run_native_windows_validation.ps1` passed again:
  configure/build succeeded and CTest reported 178/178 tests passing.
- After adding the actor/contact process-memory wrapper and dry-run CTest,
  `powershell -ExecutionPolicy Bypass -File tools\run_native_windows_validation.ps1
  -BuildDir build-win-codex-vs3 -Configuration Debug` passed: configure/build
  succeeded and CTest reported 170/170 tests passing.
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
- Bundled Windows Python syntax validation also passed with
  `C:\Users\andrz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m py_compile tools\capture_original_explosion_procmem.py`.
- Bundled Windows Python syntax validation now also covers
  `tools/check_explosion_lane_result_preflight.py`.
- `tools/check_explosion_lane_result_preflight.py` passed with the bundled
  Windows Python, both with explicit `.` asset directory and with its default
  repository-root asset directory. It verified `1000:3D3F`, `1000:3ED3`,
  expected original bytes `268805`, scratch `0xF280`, body `0xF200`, exact
  trampoline body bytes, the shared result-write tail
  `8b46f63b46f075c58a46f3c47e04268805c9c20600`, and the wrong-offset guard.
- `tools/capture_original_lane_result_runtime.py --preflight-only --asset-dir .`
  passed with the bundled Windows Python and reported
  `lane_result_capture_orchestrator=ok mode=preflight`.
- `tools/capture_original_lane_result_runtime.py --preflight-only .` also
  passed, verifying the positional asset-dir compatibility path. The CTest
  suite now covers both preflight-only forms, and the wrapper CTest regexes now
  pin `result_tail=1` plus the exact `result_tail_bytes` value so wrapper
  success cannot silently drop or weaken the static tail check.
- `tools/capture_original_lane_result_runtime.py C:\Temp\lezac-lane-result-dry-run
  . --dry-run --skip-oracle` passed and reported `offsets=2`,
  `capture_commands=2`, `oracle_commands=0`, `offset_labels=3d3f,3ed3`, and
  `offset_addresses=1000:3D3F,1000:3ED3` while printing both generated capture
  commands.
- `tools/capture_original_lane_result_runtime.py C:\Temp\lezac-lane-result-dry-run
  . --dry-run` passed and reported `oracle_commands=2`, verifying the generated
  C++ oracle command plan as well.
- `tools/capture_original_lane_result_runtime.py C:\Temp\lezac-lane-result-dry-run
  . --dry-run --skip-oracle --offset 3D3F` and the equivalent `--offset
  1000:3ED3` command both passed with one generated capture command; invalid
  `--offset 3D2D` was rejected by argument parsing.
- `tools/capture_original_lane_result_runtime.py C:\Temp\lezac-lane-result-dry-run
  . --dry-run --skip-oracle --offset forward` and the equivalent `--offset
  reverse` command both passed with one generated capture command; invalid
  `--offset sideways` was rejected by argument parsing. CTest now locks the
  single reverse-alias dry-run output as `offset_labels=3ed3` and
  `offset_addresses=1000:3ED3`.
- Repeated offset selection, such as `--offset 3D3F --offset 1000:3D3F`, now
  deduplicates to one generated capture command while preserving user-specified
  offset order for mixed captures. CTest now locks the mixed-order
  reverse-then-forward dry-run as `offset_labels=3ed3,3d3f` and
  `offset_addresses=1000:3ED3,1000:3D3F`.
- Added `explosion_lane_result_capture_orchestrator_dry_run_timing_args`, which
  locks dry-run pass-through for the route/runtime timing knobs sent to
  `tools/capture_original_explosion_procmem.py`.
- `tools/capture_original_lane_result_runtime.py C:\Temp\lezac-lane-result .`
  correctly refused runtime capture without both approval flags.
- Added CTest coverage for the orchestrator safety rails:
  `explosion_lane_result_capture_orchestrator_bad_offset`,
  `explosion_lane_result_capture_orchestrator_refuses_repo_output`, and
  `explosion_lane_result_capture_orchestrator_requires_approval`.
- `tools/check_explosion_lane_result_wrapper.py .` passed with the bundled
  Windows Python and reported `lane_result_wrapper_output=ok cases=13`,
  verifying the wrapper output matrix without DOSBox or process-memory access.
- `tools/check_explosion_lane_result_orchestrator.py` now also verifies that
  the wrapper-output checker is wired into CTest; it reports
  `lane_result_orchestrator_cmake=ok tests=15 will_fail=3`.
- `tools/check_explosion_lane_result_fixtures.py` passed with the bundled
  Windows Python and reported `lane_result_fixtures=ok files=13 valid=2
  malformed=11 cmake_tests=13`.
- A bundled Python import/assertion check passed for
  `build_freeze_patch("lane-result-cs-scratch", 0x3D3F/0x3ED3)`: both offsets
  return a three-byte near jump, scratch `0xF280`, length `0x12`, body
  `0xF200`, a freezing `EB FE` tail, expected original bytes `268805`, and
  invalid offset `0x3D2D` is rejected.
- A direct shipped-EXE byte check passed: with MZ image base `0x0770`,
  `1000:3D3F` maps to file offset `0x44AF` and `1000:3ED3` maps to
  `0x4643`; both contain `26 88 05`, matching the new patch guard. The
  preflight now also pins the surrounding static tail as loop-end compare,
  `mov al,[bp-0d]`, `les di,[bp+4]`, `mov es:[di],al`, `leave`, `ret 6`.
- `tools/capture_original_explosion_procmem.py NUL .
  --describe-freeze-patch --freeze-ghidra-offset 1000:3D3F
  --freeze-patch-mode lane-result-cs-scratch` passed and printed
  `freeze_patch_description=ok`, `file_offset=0x44af`,
  `expected_original_bytes=268805`,
  `patch_bytes=e9beb4`, `scratch_offset=0xf280`, and `body_offset=0xf200`.
- The same describe preflight for `1000:3ED3` passed with
  `file_offset=0x4643`, `expected_original_bytes=268805`,
  `patch_bytes=e92ab3`, `scratch_offset=0xf280`, and `body_offset=0xf200`.
- The equivalent CTest entries are now
  `explosion_freeze_patch_describe_lane_result_3d3f` and
  `explosion_freeze_patch_describe_lane_result_3ed3`; both passed under the
  WSL build tree on 2026-05-06.
- The wrong-offset preflight was checked directly and fails cleanly with
  `freeze_patch_description=error reason=--freeze-patch-mode
  lane-result-cs-scratch is only valid at 1000:3D3F or 1000:3ED3`.
- WSL validation was restored for the 2026-05-06 continuation:
  `cmake --build build` passed, and `ctest --test-dir build
  --output-on-failure` passed with 146/146 tests before the promoted reverse
  fixture was added.
- The first approved two-offset WSL/DOSBox process-memory run wrote captures
  under `/tmp/lezac-lane-result-runtime-20260506`. It proved the reverse
  `3ED3` route reached the runtime-child-memory freeze, but the oracle rejected
  the candidate because the fixture writer did not emit explicit
  `freeze_expected_old_bytes` / `freeze_old_bytes` keys. The capture helper now
  emits both keys in candidate fixtures, and
  `tools/check_explosion_lane_result_layout.py` verifies that writer contract.
- The repaired targeted command
  `python3 tools/capture_original_lane_result_runtime.py
  /tmp/lezac-lane-result-runtime-20260506-reverse .
  --approve-procmem --approve-runtime-instrumentation --offset reverse`
  passed end-to-end, wrote `manifest.txt`, and parsed the promoted
  `3ED3` candidate with `--debug-explosion-playback-oracle`.
- After promoting the reverse fixture, `cmake --build build`,
  `ctest --test-dir build -R lane_result --output-on-failure`, and
  `ctest --test-dir build --output-on-failure` all passed under WSL. The
  focused lane-result slice reported 36/36 tests, and the full suite reported
  147/147 tests.
- The same 2026-05-06 two-offset attempt left the forward `3D3F` candidate as
  `runtime_child_memory_patch_loaded_no_freeze_observed`; this is a route/timing
  gap, not a parser claim. Later default, right-hold timing, and before-bomb
  retries also loaded the patch without freezing.
- A labeled runtime-seeded forward retry under
  `/tmp/lezac-lane-result-forward-seeded-after-20260506` did freeze
  `1000:3D3F` and produced the promoted
  `explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded.txt`
  fixture. Natural-route forward result-write evidence remains pending.
- Route-step natural retries under
  `/tmp/lezac-lane-result-forward-routestep-x1p5-z0p5-20260506`,
  `/tmp/lezac-lane-result-forward-routestep-x2p0-c0p5-20260506`, and
  `/tmp/lezac-lane-result-forward-routestep-x2p0-m0p35-20260506` all loaded the
  `1000:3D3F` patch without freezing. The `x:2.00,c:0.50` run was promoted as
  a natural no-freeze fixture because it preserves nonzero lane-global state.
- A native PowerShell `cmake --build build` attempt was also rejected because
  the existing build tree was configured under `/mnt/c/...` and expects
  `/usr/bin/gmake`; use WSL or a fresh native build tree for full validation.
- A fresh native PowerShell configure probe failed because no C++ compiler was
  available (`No CMAKE_CXX_COMPILER could be found`). The generated
  `build-win-probe/` directory is ignored as build output because the sandbox
  blocked recursive cleanup.
- The prior `.git/index.lock: Permission denied` staging blocker was resolved
  before the lane-result checkpoint was rebased and pushed.
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
  changed from this proof yet. The `damage_queues` diagnostic now also locks
  the `4B3F`/`4B61`/`4B6A`/`4C20`/`4C64`/`4C75`/`4CAE` branch anchors and the
  `DS:659A`/`DS:655E`/`DS:2078` staging globals; see
  `docs/recovery/high_debris_lane_branch_model_2026-04-25.md` for the local
  byte dump and static model. The explosion playback oracle now emits explicit
  one-hot observed-freeze flags for `4B6A`, `4C75`, `4C96`, and `4CA9`, and
  CTest pins the expected flag for each promoted original-runtime fixture.
  The capture helper and oracle now also name post-call return anchors
  `1000:4C99` and `1000:4CAC`, so the next original probes can stop after the
  forward/reverse helper calls and preserve helper-written lane bytes. Runtime
  child-memory attempts at `4C99` were timing-sensitive, but temp-copy
  instrumentation froze both post-call anchors in the same high-counter state:
  selected debris base `DS:292B`, selected collapse base `DS:663E`, target byte
  `0x00`, first selected debris bytes
  `41 05 04 c0 26 00 1c 00 00 67 80`, and first selected collapse bytes
  `06 0a 08 0a 09 80 00 04 00 00 04 00 00 01 04`. New fixtures pin the
  `observed_effect_forward_return`/`observed_effect_reverse_return` flags.
  The refreshed capture helper now includes `DS:78C0`, and both post-call
  fixtures pin helper inputs `DS:78D2=0xF7` and `DS:78D4=0xFC`; the sampled
  staging globals are raw-zero at the freezes (`DS:2078=0x00`,
  `DS:655E=0x0000`, `DS:659A=0x0000`), so the exact lifetime of the static
  staging fields remains unresolved. A follow-up runtime-child instrumentation
  mode for `1000:4C75` now copies the live `[BP-4]` word to `CS:4C7E` before
  freezing; the promoted fixture records `instrumented_bp4_local_value=0x0003`
  with matched tail screenshots. This directly proves one positive local-word
  gate while also showing that the sampled selected word-layer summary
  (`0x0000`) can describe adjacent queue state rather than the exact loop
  iteration frozen by the patch. The C++ frame capture manifest now records
  first debris/collapse/effect queue fields per checkpoint. A WSL/Xvfb
  original-vs-C++ level-1 bundle captured all seven route labels; visual
  inspection confirmed the original reached blast/playback frames. Pixel diffs
  remain large because the C++ renderer is provisional, but the queue metadata
  exposes the next concrete mismatch: C++ records the level-1 collapse span
  `0x0A06..0x0A08`, `flagged=0x8009`, `affected=4`, `count=2` with
  `collapse0_forward=0`, `collapse0_reverse=0`, while original post-call
  fixtures preserve the same span with helper-written reverse lane byte
  `0x04`. Static disassembly of `1000:3BB2`/`1000:3D46` now has a dedicated
  `--debug-lane-helper-model` diagnostic: it locks the `[BP+4]` far input
  pointer, `[BP+8]` weight byte, one-based `DS:2078` staging loop,
  `DS:655C`/`DS:6598` inputs, `DS:65D4` tag table, `0x4E20` debris marker, and
  forward/reverse write bases `DS:6617`/`DS:2097` and
  `DS:6618`/`DS:2098`. The follow-up `--debug-lane-blend-arithmetic`
  diagnostic now locks `0920:0945` as signed 32-bit division: numerator in
  `DX:AX`, denominator in `BX:CX`, quotient in `DX:AX`, consumed lane byte in
  `AL`, truncation toward zero, and zero-divisor branch `0920:09AC` with
  `AX=0x00C8`. A 2026-04-28 runtime child-memory scratch capture now freezes
  the forward lane blender at `01ED:3CD4`, after immediate runtime patching
  and before the far division helper registers are loaded. The promoted
  `explosion_playback_oracle_original_3cd4_lane_div_scratch_runtime.txt`
  fixture records would-be `DX:AX=0xFFFF:0xFFF8`, `BX:CX=0x0000:0x0005`,
  active staging count/index `1`, matching numerator/weight locals, and live
  staging globals `DS:2078=1`, `DS:655E=0x8009`, `DS:659A=0x0A7A`. A
  2026-04-29 follow-up froze the actual forward far-call site at `01ED:3CE3`;
  the promoted
  `explosion_playback_oracle_original_3ce3_lane_div_scratch_runtime.txt`
  fixture records loaded registers `DX:AX=0x0000:0x001C`,
  `BX:CX=0x0000:0x0010`, active count/index `1`, and matching
  numerator/weight locals. Immediate reverse-helper probes at `01ED:3E68` and
  `01ED:3E77` loaded their runtime patches but did not freeze on the same
  route, so they are not promoted. A later runtime scratch probe froze the
  forward collapse writeback at `01ED:3D1B`; the promoted
  `explosion_playback_oracle_original_3d1b_lane_write_scratch_runtime.txt`
  fixture records output byte `0x01`, selected tag `0x0003`, `DI=0x002D`,
  active count/index `1`, and result local `0x01`, proving the original is
  about to write to `DS:6617 + 0x002D` with collapse stride `0x0F`. A
  follow-up proved that inline lane-write instrumentation is unsafe for
  adjacent debris writeback probes because it can overwrite the shared loop
  join at `1000:3D31`. The capture helper now uses a safe three-byte near-jump
  trampoline for lane-write probes, with runtime code at `CS:F000` and scratch
  at `CS:F080`. The promoted trampoline fixtures record a fresh `3D1B`
  forward collapse stop (`output=0x04`, `tag=0x0004`, `DI=0x003C`) and a
  `3EAF` reverse collapse stop (`output=0x00`, same tag/DI), proving both
  `DS:6617 + 0x003C` and `DS:6618 + 0x003C` for the same selected tag. Safe
  trampoline probes at `3D2D` and `3EC1` loaded but did not freeze on this
  route, so debris-side writeback still needs a different route or
  debugger-seeded setup. A later labeled runtime seed now patches the original
  `4C96`/`4CA9` call sites to write `DS:655E=0xC004` before calling the
  original helper body. Those seeded fixtures freeze forward debris writeback
  at `3D2D` (`output=0x35`, `tag=0x4EE8`, `DI=0x0898`) and reverse debris
  writeback at `3EC1` (`output=0x00`, same tag/DI), proving the debris marker
  relation `(0x4EE8 - 0x4E20) * 0x0B = 0x0898`. They are not natural-route
  evidence; natural debris reachability remains open. Temp-copy lane-div
  instrumentation is intentionally rejected because the larger patch body can
  overlap DOS relocation words near the far-call operand. Live playback
  behavior is unchanged until natural debris-side writeback evidence rounds out
  the queue-lane model. This also explains why post-call fixtures can preserve
  helper-written lane bytes while sampled staging globals are already zero.
- `./build/lezac_cpp --debug-passable-objects` passed with
  `level1_route_clear=1`.
- `ctest --test-dir build -R "autoplayer|frame_sequence_capture"
  --output-on-failure` passed: 20/20.
- `ctest --test-dir build -R explosion_playback_oracle
  --output-on-failure` passed under WSL: 31/31.
- `ctest --test-dir build --output-on-failure` passed under WSL: 111/111.
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
  remains blocked on frame-table/sprite semantics, but process-memory
  instrumentation has promoted original fixtures for branch reachability,
  post-call lane bytes, the `4C75` live word gate, one `3CD4` mid-helper
  lane-division setup, one `3CE3` forward divide call-site register capture,
  collapse writeback captures at `3D1B` and `3EAF`, and seeded debris
  writeback captures at `3D2D` and `3EC1`, plus final far-pointer result-write
  captures at reverse `3ED3` and seeded forward `3D3F`. Next evidence should
  target natural debris-side writeback and natural forward `3D3F` before
  changing live playback behavior.
- Semantic meaning of `PROEFS.SON` bytes `+4..+5` remains unknown; current
  diagnostics preserve them as raw fields only.
- Many non-explosion sound callsites still need exact cursor/priority mapping.
- Exact actor update behavior around `1000:6053..777f`, especially original
  contact flags, passability thresholds, tile snapping, behavior-3 ledge/wall
  handling, and behavior-4 collision response. The synthetic actor-update oracle
  is ready; original runtime/debugger fixtures are still pending.
- The probable contact scanner around `1000:5cb0..604f` has both scanner-only
  and actor-update fixture targets, but still needs cross-reference mapping and
  runtime confirmation before the C++ clearance model can be called
  original-faithful.
- Exact state-2 life-count decrement, `DS:79b9` fallback behavior,
  active-player accounting edge cases, and exact dead-player visual playback
  from original frame bytes.
- Exact two-player panel artwork and full death/reentry presentation.
- Exact sprite frame tables for impact/death/reward frames remain unresolved.
- `GRAN.MST` field semantics remain unknown; consolidation only locks file
  shape, raw/json byte preservation, and a conservative byte-profile diagnostic
  for future loader/runtime comparisons.

## Next Planned Target

Use the reliable original level-1 route to finish explosion/debris/collapse
lane writeback evidence, then return to DOSBox frame/debugger evidence for
behavior-4 movement, targeting, and respawn timing.
