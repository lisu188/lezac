# Ready Fixture Provenance Contract

ready_fixture_provenance_contract=1

This note defines the provenance rule for a ready fixture: an oracle fixture
candidate that can move from a sweep or debug-capture writer, through a
ready-manifest runner, into a ready-result summary. The rule is deliberately
narrow. Promotion through this path proves that runtime oracle evidence is
well-formed and traceable; it does not prove visual equivalence and does not
justify live gameplay changes by itself.

## Required Fixture Metadata

Any existing ready fixture with runtime metadata must agree with the manifest or
result record that references it:

- `runtime_cs` and `runtime_ds` are four-digit hexadecimal runtime segments.
- `visual_claim=0` is required for runtime ready evidence.
- `temp_copy=1` is required for original DOSBox captures.
- Manifest/result `runtime_cs` and `runtime_ds` values must match any fixture
  `runtime_cs` and `runtime_ds` fields that are already present.

Checked-in original fixtures are stricter. Any fixture under
`tests/fixtures/dosbox` whose filename contains `original` must have an entry in
`docs/recovery/runtime_evidence_ledger.md`. The ledger must declare
`runtime_evidence_ledger=non_visual`, and its `original_runtime_fixture_count`
must match the machine-readable `fixture=` entry count. Each ledger entry and
each field in that entry must be unique, keep
`visual_claim=0`, use `evidence=runtime_cs_runtime_ds_temp_copy`, and point to a
note under `docs/recovery/original_runtime_fixture_notes.md` or another recovery
doc that explicitly names the fixture. A future `visual_claim=1` promotion must
go through `docs/recovery/visual_claim_promotions.md` with original, C++,
comparison-frame artifacts, and a checked-in frame-compare bundle whose
`tools/summarize_frame_compare_bundle.py` output reports `promotion_ready=1`.

## Enforced Stages

The same provenance rule is enforced at all ready-fixture handoff points:

- Writers:
  - `tools/summarize_debug_capture_batch.py`
  - `tools/summarize_actor_dispatch_gate_sweep.py`
  - `tools/summarize_lane_result_route_sweep.py`
  - `tools/summarize_lane_write_route_sweep.py`
- Ready-manifest runners:
  - `tools/run_debug_capture_ready_manifest.py`
  - `tools/run_actor_dispatch_ready_manifest.py`
  - `tools/run_lane_result_ready_manifest.py`
  - `tools/run_lane_write_ready_manifest.py`
- Ready-result summaries:
  - `tools/summarize_debug_capture_ready_results.py`
  - `tools/summarize_actor_dispatch_ready_results.py`
  - `tools/summarize_lane_result_ready_results.py`
  - `tools/summarize_lane_write_ready_results.py`

All stages call `tools/ready_result_fixture_guardrails.py`, which owns
`parse_runtime_segment_value` and `validate_runtime_fixture_evidence`. The
contract check in `tools/check_ready_fixture_provenance_contract.py` keeps this
documentation, the shared validator, and those twelve call sites in sync.

`--allow-missing-fixtures` is a dry-run-only forensic bypass for reviewing stale
or partial manifests. Live ready-manifest runs must reject that flag before
candidate execution, so missing fixtures cannot be promoted by accident.
