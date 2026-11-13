# Python 3.15 Recovery Harness Compatibility

## Observed Failure

The Windows full suite for actor-pass head
cb633d68f24370b75307295fcc0b45e1cc62020a failed three existing harness checks:
boss_extended_combat_evidence, boss_extended_combat_original and
collapse_history_repetition_contract. Job 120051351337 selected hosted
Python 3.15.1 for CTest, despite installing a separate MSYS Python 3.14.
The AST checks reported "AST field mismatch"; the repetition check reported
"repeat-run controls exceed the retained reserve". Its source bytes match
main b590e6f. These failures are not waived or attributed to the C++ recovery.

## Causes And Fixes

The frozen observer AST was produced by Python 3.12.3. Python 3.15 adds an
is_lazy field to Import and ImportFrom nodes; ordinary eager imports use 0.
The decoder now supplies that value only when the runtime has the field and
the frozen record omitted it. Existing fields are not overwritten. Unknown
fields, missing required fields and a forged lazy import still fail. Complete
decoded-AST versus authenticated observer-source binding remains enabled.

Python 3.15 also lowers gzip's default compression level from 9 to 6. The
collapse diagnostic writers now explicitly request level 9 and mtime 0,
retaining the earlier compression policy. Neither decoded fixture streams,
comparison logic, captured evidence nor the 8 MiB retained-output limit changes.
The repeated harness invocation still preserves all earlier report/file hashes.

Official references:

- https://docs.python.org/3.15/library/ast.html#imports
- https://docs.python.org/3.15/library/gzip.html#gzip.compress

## Regression Scope

Six standard-library tests cover the native AST schema, simulated 3.15 eager
imports, lazy-import rejection, unknown-field rejection, missing-field rejection,
and two complete repeated mocked-diagnostic invocations under the new gzip
default. The compression control observes all 90 compression calls, requires
explicit level 9, checks both successful report sets, checks earlier evidence
hashes and retains the unchanged aggregate 8 MiB bound.

On local Python 3.12, the unmodified code reproduces both reported error texts;
the fixed code passes all six controls. These schema/default simulations are
not an execution of the actual Python 3.15 runtime. A dedicated Linux/Windows
matrix runs the same six tests on actual Python 3.12 and 3.15, in addition to
the registered full-suite CTest. Current-head CI and review remain merge gates.

The six controls also pass with the bundled native Windows Python 3.12 runtime.
Fresh sealed-boss validation and the existing App's complete controlled replay
pass: 3,200 samples, 15 view comparisons, both newline forms and all 16 negative
mutations. The source guard passes 20 controls over 167 mapped sources. Frozen
evidence, assets and fixture hashes remain unchanged during validation.

This changes only evidence readers/writers and their validation. No C++ game
instruction body, original asset, frozen fixture, pixel comparison, gameplay
threshold or fidelity claim is changed. All local validation remains RAM-only
and silent under the owner's disk-pressure exception.
