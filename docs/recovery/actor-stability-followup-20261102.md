# Actor Stability Follow-Up

## Fidelity Still Fails

The latest nine-test focused CTest run passes seven and fails two:
`frame_actor_pass_original` and its CLI positive control. The current GCC
C++23 `-O1` model reproduced the entry ID-toggle profile error, not merely the
historical ELF. This is retained failure evidence, not a green validation run.
The original fixture, filtered replay and diagnostic tests still pass.

A later historical observation also captures `Pass trace exceeded endpoint`
before unwinding. Another targeted run reports case 656, row 14969, at
`1920:0975`, with CX `0200` instead of `0000`. No original fidelity, full-frame,
App-integration or overall completion flag changes. The root cause is unknown.

## Failure-File Preservation

The Windows failure on base PR #469 was in `test_broken_link_is_preserved`:
exclusive creation did not raise `FileExistsError` on the dangling link.
The writer now checks the destination with `lstat()` before retaining the
existing exclusive-create operation. Existing files, links and directories
are rejected; a failed stat does not proceed to file creation. The bounded
JSON format and hash-only handling of complete guest memory are unchanged.

A new early-rejection regression fails against the old writer and passes with
the fix. Fourteen writer tests pass on Linux. Native Windows runs twelve and
skips the two symlink-creation checks because the RAM UNC share denies native
link creation. A separate attempt with Linux-created links cannot supply that
proof either: Windows does not recognize those links on this share. It is a
fixture-adapter failure, not a passing Windows symlink test. The hosted Windows
test remains the acceptance gate for that platform-specific behavior.

## Original Provenance

Two independent, complete original captures use the patched writer, unchanged
producer and canonical MZ, Unicorn 2.1.4 and the verified mapped native library.
Their complete manifests, compressed projections and checkpoint catalogs agree
byte for byte. The compressed projection also equals the existing frozen file.

| Artifact | SHA-256 |
| --- | --- |
| Uncompressed 35,707,847-byte projection | 799531ca906973fc9f0b619855e42898aa5eb876b4086641cc6b637eb63a40d3 |
| Compressed 8,758,898-byte projection | 956e37149058c02aeb3519af0448e0ce5f906a08cdc8a3b52144596ea59e4307 |
| Checkpoint catalog | a71da337ca2a5851396c783a140885752b7b198ff469520fda77e3bbce82a4be |
| New manifest | ab6f2c004150b858be47d2fd76e27aff20006303ffe0f2c1cac228bd2bb4f596 |
| Patched failure-writer source | 3151b22c1cac49cdd022b100e6e78283868d8c66096146452a83645d7e4ed883 |

Comparing the old and new manifests shows exactly one changed source entry:
`oracle_failure_report.py`. All other metadata is unchanged. The frozen gzip
is not rewritten, and no full guest RAM or core is exported. The checker now
pins the newly captured manifest rather than accepting arbitrary source drift.

## Review Findings

PR #472 review at `c078c4aca768e23291628ff888f7241cf08cf297` identified two
actionable findings. Both have fail-before/pass-after controls:

- `discussion_r4447778150`: the exec-based GDB handoff could leave a replay
  stopped if symbol validation failed before attach. The old behavior was
  reproduced and the verified owned orphan was explicitly killed. The parent
  now stays alive, runs GDB as a child, and always kills/reaps its replay in
  `finally`, including collector startup, timeout and validation failures.
  Valid and deliberately mismatched DWARF controls confirm cleanup. Preload
  handoff success and failure also have explicit cleanup regressions.
- `discussion_r4447778162`: an unexpected own-launch inferior stop previously
  wrote its diagnostic report and returned exit 0. A controlled breakpoint at
  `main` reproduces that branch. The same control now retains `unexpected_stop`
  evidence, kills the inferior and returns exit 1. It is a synthetic diagnostic
  control, not a natural game crash.

The replay grants debugger access only to its supervising parent and that
parent's descendants through `PR_SET_PTRACER`. This permits sibling GDB attach
without changing system-wide ptrace settings, in accordance with the
[kernel's Yama documentation](https://docs.kernel.org/admin-guide/LSM/Yama.html).
The permission grant is host diagnostic instrumentation, explicitly recorded
in the parent report; the ordinary control does not use it.

## Targeted Operand Capture

The historical ELF has separate inlined validation sites in
`ActorUpdate.interruptInProgress` and `ActorUpdate.registers`. Hardware slots
now cover both failure branches, at `3ABF4` and `8ACF9`, as well as the two
exception-constructor PLTs. A validation-only mode disables the constructor
slots so other exceptions cannot prevent the requested branch observation.
Uncaptured failures remain recorded, and a campaign that observes failures
without a target capture returns failure, not bounded non-reproduction.

The two branch profiles retain four game/id ownership pairs plus one variant
tag, 33 bytes of host metadata, with the register state before exception
allocation. The second profile has the same verified stack layout shifted by
16 bytes. The stop RIP must match the selected pinned hardware slot. These
profiles are specific to the exact historical ELF; optimized DWARF remains
advisory and no causal fix is inferred from it.

## Validation Boundaries

- Fourteen bounded-writer tests pass on Linux.
- Fifteen diagnostic-report tests pass, including supervisor cleanup on both
  preload collector outcomes and rejection of an incomplete targeted campaign.
- Eight supervisor tests pass for receipt admission, output bounds, timeout,
  collector failure and the process-scoped permission grant.
- The current ASan/UBSan build completes all 876 cases / 7,884 schedules,
  10,432,263 comparisons and 29,521,980 dispatches without a reported sanitizer
  error. This does not prove absence of undefined behavior or explain the
  unsanitized failures.
- The unsanitized focused suite remains 7/9, with full replay and its positive
  CLI control failing. These failures are not replaced by the sanitizer pass.
- Native Windows writer checks remain twelve passed / two unavailable;
  Windows CI for the new source is still required.

The causal regression and production fix remain outstanding. These diagnostic
and evidence-retention repairs must not clear the actor-pass or dependent
full-frame integration hold.

The [machine-readable follow-up receipt](actor-stability-followup-20261102.json)
retains both passing and failing scopes. The final validation-only campaign
completed sixteen attempts, observed the case-656 mismatch above, did not
capture the requested branch, and returned exit 1 with
`other_failures_without_target_capture`. It is not a clean stability run.
