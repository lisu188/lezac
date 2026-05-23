# Visual Claim Promotion Ledger

promotion_ledger=visual_claim

This ledger is the promotion gate for checked-in DOSBox oracle fixtures whose
`visual_claim` is raised above instrumentation-only evidence. A fixture may
stay at `visual_claim=0` when it proves runtime bytes, register state, parser
coverage, or debugger reachability without proving exact original presentation.

Promotion to `visual_claim=1` requires a checked-in ledger entry with:

- the fixture filename
- an original-frame artifact path
- a C++ frame artifact path
- a comparison or diff artifact path
- a frame-compare bundle path whose summary reports `promotion_ready=1`
- a supporting recovery note under `docs/recovery/`

Machine-readable promoted entries use this shape:

```text
- fixture=<name>.txt visual_claim=1 original_frame=<path> cpp_frame=<path> comparison=<path> frame_compare_bundle=<path> docs=<path>
```

Use the entry writer once the bundle is checked in and
`tools/summarize_frame_compare_bundle.py <bundle> --require-promotion-ready`
passes:

```sh
tools/validate_visual_claim_promotion_candidate.py \
  <fixture>.txt docs/recovery/frame_compare/<bundle> docs/recovery/<note>.md \
  --label <semantic-frame-label>

tools/write_visual_claim_promotion_entry.py \
  <fixture>.txt docs/recovery/frame_compare/<bundle> docs/recovery/<note>.md \
  --label <semantic-frame-label>
```

The validator is a read-only dry run. It requires the fixture to carry exactly
one current `visual_claim=0` or `visual_claim=1`, confirms the frame bundle is
promotion-ready, emits the candidate ledger entry, and reuses the committed
guardrail checks for artifact paths, `frame_compare_bundle`, and recovery docs
before any real ledger edit is made.

Use the batch planner when multiple checked-in bundles are ready to review:

```text
promotion=visual_claim_candidates
candidates=1
candidate_0_fixture=<fixture>.txt
candidate_0_frame_compare_bundle=docs/recovery/frame_compare/<bundle>
candidate_0_docs=docs/recovery/<note>.md
candidate_0_label=<semantic-frame-label>
```

```sh
tools/plan_visual_claim_promotions.py docs/recovery/<candidate-manifest>.txt \
  --require-all-ready
```

The planner validates every candidate with the same read-only checks and prints
the exact ledger entries for the candidates whose status is `ready`.

Current promoted visual fixtures: none. All checked-in DOSBox oracle fixtures
currently remain `visual_claim=0`.

`tools/check_visual_claim_guardrail.py --self-test` exercises a synthetic
promoted fixture and confirms the checker rejects a missing comparison artifact,
an unready frame-compare bundle, and a mismatched ledger fixture.
