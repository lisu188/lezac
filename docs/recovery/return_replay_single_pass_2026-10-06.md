# Single-Pass Return Replay Verification

## Cause

The exact-head Windows CI run for PR #290 passed 649 of 650 tests. The
`natural_level3_return_original` test timed out at 600.01 seconds. Its old
comparison validated the complete trace twice: once for mapped states and
displayed pixels, then again for the 1422 added lifecycle boundaries. Each
pass also verified every trace record, input event, frame FNV fingerprint,
manifest SHA-256 and frame-path safety rule.

## Change

`natural_campaign.compare_rows` accepts an optional extra-boundary check.
It runs only after a matched boundary passes its normal mapped-state and
pixel checks. The return replay compares the original lifecycle fields in
that same validated pass. It still requires all 1422 distinct lifecycle
boundaries, the complete trace footer, and the full result-image inventory.

No fixture, route, expected hash, raw-state validator, manifest check,
comparison count or timeout changes. The full route still compares 6038
RGB frames, 12000 mapped boundaries and 386432000 pixels. Game code and
the original capture producers are unchanged.

## Regression Coverage

`campaign_boundary_checks` adds 13 focused cases covering the default
comparison report, one validated trace pass, matched present/post/result
callbacks, propagated extra-check failures, mapped and RGB mismatches,
duplicate and missing boundaries, incomplete footers, result inventories,
and duplicate/missing/mismatched lifecycle boundaries.

The focused tests pass under native Windows Python 3.11 and Linux Python.
A fresh GNU 13.3 Release build and all nine selected campaign/fixture/source
guard CTests pass, as do six selected visual/runtime evidence guards. The
native Windows return guard also retains all 84 fixture, 291 typed-field,
twelve producer, four lifecycle and fourteen opcode mutation rejections.

A fresh native-Windows production recording uses the PR #290 package at
`9f1ea8f959896006167ba75f4de9a5073bc227df`. Its C++ gameplay source files are
identical to the base `b218bf9af34735efec4611d31f718213f3f4193e`; this change
does not modify those files. The packaged executable SHA-256 is
`71dd6ed1e3c05dbdfbb82dcef762cf67a0ba440d78491773199f53a382faca27`.

Both the original verifier from that base and the changed verifier compare
the same closed Windows recording under Linux Python. Their full reports
are identical, including all frame, mapped-state, lifecycle and claim fields.
The old verifier takes 191.702 seconds and performs two fully validated trace
passes; the changed verifier takes 101.882 seconds and performs one. These
are diagnostic local measurements with a concurrent Windows verifier, not
a claim about physical game timing or every CI runner.

Fresh Windows checkpoint images at ticks 6776 and 7065 also match the retained
original PNG pixels exactly. Complete native-Windows verifier timing and
exact-head CI results are tracked separately from the Linux comparison.

## Limits

This repairs replay verification cost, not gameplay. Natural Level 3
completion, later natural campaigns, full actor fields, sound and physical
timing remain unverified. No global fidelity or whole-game completion flag
is promoted. Native-Windows local timing with RAM output through a WSL UNC
path is not a substitute for the exact-head CI test's 600-second gate.
