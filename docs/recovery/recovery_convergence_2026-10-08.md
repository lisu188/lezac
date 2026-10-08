# Current-Main Recovery Convergence

## Integration Scope

This branch starts at main `0a4c3286dfaa461f7c031ed1ae8e061db498126d`,
which contains the reviewed, fully tested constructor-velocity recovery from
PR #326. It combines the exact reviewed heads of:

- PR #327, `b2b059d1a4767dbacb156e05f631a04aeba36ab2`: complete original
  debris/collapse/contact execution, clean-slot collapse actor creation,
  signed-WORD flame contact and the historical PPM raster-boundary repair.
- PR #325, `95a15452c3d1649069f43769bee9bbde4fa54bd2`: executed-original
  sound interrupt/priority recovery, persistent sound clocks, bounded
  catch-up and elapsed-time-consistent live-test deadlines.
- PR #328, `cb4deeca1021977cccb0f880779ea416d2b2f5e2`: unconditional pickup
  tail-animation initialization after a constructor attempt, including
  full-pool refusal, plus its independent original-byte comparison.

Parent branches and their live CI heads remain unchanged. Parent review and
CI results are evidence for the individual trees, not proof of this combined
tree. PR #325 and #326 full suites had completed before preparation;
PR #327/#328 full-suite runs were still live. No CI was manually cancelled
or restarted, and no branch was deleted.

## Conflict Review

Git merged all C++ changes without textual conflicts. Manual conflict
resolutions are limited to `.gitattributes`, CI and the high-level status
document. They retain both sides: hash-pinned fixture attributes, every
parent test registration, every early regression step, separate artifact
names and all evidence limitations. Fifty-nine inherited files are
byte-identical to their reviewed parents. For each of the three merge
stages, Git's independently recomputed merge tree differs from the saved
merge commit only in the three manually resolved metadata paths. All C++
blobs, including the combined App, match that automatic merge output;
the working production C++ still matches the final saved merge exactly.

The integration additionally runs `sound_interrupt` and
`sound_interrupt_original` before the long full suite, and retains final
sound diagnostics afterward. Focused and final sound, constructor,
pickup and collapse evidence have distinct artifact names. Final uploads
run unconditionally and include CTest success/failure logs, so a later
full-suite failure cannot hide the earlier diagnostic output.

Bounded local verification preserves every parent CTest registration,
every parsed CI step and all fixture attributes. Eighty structured CI
mutations are rejected, including missing/early/success-only uploads,
wrong artifact names/uploaders, omitted paths, delayed original sound
checks and non-dummy audio/video settings. Twenty-four oracle, source,
mutation and mocked-failure checks pass, along with the 78-file source
ownership inventory, changed Python syntax and diff checks. These are
source/fixture checks, not compiled or natural-gameplay evidence.

## Required Combined-Tree Proof

Before merge, require fresh Windows and Linux compilation, all focused
original-backed checks, complete suites and extracted-package checks on
this exact head. Inspect formal reviews, inline threads and conversation
comments including bots after pushes/rebases and immediately before merge.
Historical PR #36 PPM, #112 lane-word, #308 sound catch-up, #318 diagnostic
retention and #324 live-deadline findings must remain fixed in the combined
code. PR #243's separate modularization adapter finding is not included
or claimed fixed by this monolithic integration.

Verify that current main has not changed and that the prospective merge
tree equals the tested tree. If main advances, validate a fresh integration
without modifying or restarting any confirmed-live parent CI head.

## Evidence Boundaries

Unchanged disk and tmpfs reserves prohibit local heavy builds and native
captures. Bounded local source/provenance, fixture, mutation and mocked
failure checks are not compiled, visual or natural-gameplay proof.
Controlled original CPU execution does not establish natural full-pool
pickups, arbitrary inherited animated bombs, mixed/stale actor slots,
original hardware sound timing or complete campaigns. Package startup
frames are startup-only evidence. All execution remains silent with
`SDL_AUDIODRIVER=dummy`.

Only Levels 1..3 have verified natural completion routes. Level 4 onward,
the full boss/campaign, raw-prefix guard and broad original fidelity remain
open. Aggregate reverse-engineering completion is unknown; no broad
completion or fidelity flag is changed by this integration.
