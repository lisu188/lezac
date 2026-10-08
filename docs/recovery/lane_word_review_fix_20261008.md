# Raw lane-word review correction

Historical PR 112 finding:
https://github.com/lisu188/lezac/pull/112#discussion_r3425951116

Both route-sweep summaries used the selected-record tag base `0x4e20` to
classify raw `lane_word_global_value` samples. This admitted flagged collapse
word `0x8009` into debris route triage.

The original `LEZAC.EXE` lookup at `1000:3A7E` tests damage bit `0x8000`, masks
it, and compares the remaining type/index word with `0x4000`. Its 20-byte
prefix at image offset `0x0770 + 0x3a7e` is pinned by the regression:

```text
8b167420f7c20080744889d025ff7f3d00407345
```

Consequently only raw `0xc000..0xffff` samples indicate damaged debris.
`0x8000..0xbfff` indicate damaged collapse; unflagged and out-of-word samples
must not qualify. Selected-record tags still use `0x4e20`, unchanged.

`tools/check_lane_word_classification.py` checks 16 boundary/malformed samples,
all 65,536 raw words in positive and negative groups in both summarizers,
and 12 CLI acceptance/rejection cases. In particular, the lane-div handoff
must not create a debris route manifest for a collapse-only sample, while
`0xc004` and `0xffff` retain the positive handoff. The existing 21 lane-div
and 22 lane-write summary scenarios remain unchanged.

The regression failed before the fix with `0x8009` counted as debris. It is
registered in CTest and runs before compilation on Linux and Windows CI.
These synthetic tests and original-byte binding are classification evidence,
not new original captures, natural forward `3D2D` execution, or whole-game parity.
