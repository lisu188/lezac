# Fracture Diagnostic And Collapse Checker Integration

The exact-head PR #355 full suites at
`835ea17784491c0c4300cbd1c4be6350a5ecd4d0` passed their focused physical
fracture comparisons, then failed the older complete-collapse source contract
on both Linux and Windows. Digest-verified final recovery archives retain the
two failed tests and tracebacks. The contract fails before launching the App;
this is not a failed raw output comparison or a passing full suite.

The physical-fracture diagnostic has two deliberate monster clears, one in
its common initialization and one before restoring the complete actor bank.
The older checker incorrectly requires one occurrence of every statement.

Bring forward only `tools/check_original_collapse_update.py` from PR #358
commit `b494b1551effbb28ea02b0e562d2743d489c1bc5`. It requires exactly two
monster clears and exactly one of each other required statement. All eight
original source mutations and eight initializer mutations remain. Three
additional controls independently remove the first clear, remove the second
clear, and add an extra clear. Every mutation must be rejected. The repair
does not weaken the contract to a nonzero occurrence check.

Production C++, the diagnostic itself, original fixture bytes, metadata,
generator pins and expected output remain unchanged. This narrowly repairs
the checker at the first PR where the second clear was introduced; it does
not import #356 full-pool changes or later contact physics.

Local source/helper checks and a comparison using the unchanged packaged
App are dependency-head evidence only. A new exact-head package, completed
external review and both full platform suites are still required. The old
failure remains retained, no check is waived, and no original producer,
natural-route, pixel/sound parity or whole-game completion is claimed.
All executions use dummy audio and the existing output/RAM guards remain.
