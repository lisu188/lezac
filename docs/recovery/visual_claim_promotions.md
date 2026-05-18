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
- a supporting recovery note under `docs/recovery/`

Machine-readable promoted entries use this shape:

```text
- fixture=<name>.txt visual_claim=1 original_frame=<path> cpp_frame=<path> comparison=<path> docs=<path>
```

Current promoted visual fixtures: none. All checked-in DOSBox oracle fixtures
currently remain `visual_claim=0`.
