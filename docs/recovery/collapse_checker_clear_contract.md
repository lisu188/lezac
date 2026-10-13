# Collapse Checker Clear Contract

## Terminal CI Finding

PR #357 at `3ab27d0e718b5dba9ab3d83a6f68bc67f3d4d7bd` passes the
complete physical fracture comparisons on Linux and Windows, including all
4,772,448 fracture-state bytes per host and five preceding original streams.
Its later `Complete collapse updater regressions` step fails before launching
the executable: the checker expects one `monsters_.clear()` in the diagnostic,
while the physical-fracture branch adds a second clear.

Both terminal logs are preserved. This is a checker source-contract failure,
not evidence that the 2,395-case compiled comparison passed or failed.

## Scoped Repair

Keep all eight required statements, but make their expected occurrence counts
explicit. Require exactly two monster clears and exactly one occurrence of each
other statement. Retain the original eight source mutations and eight
initializer mutations. Add controls that independently remove either clear and
add an extra clear; all three must fail. Do not replace equality with a weaker
nonzero/presence check.

No production C++, native generator, original fixture, expected output or
metadata pin is changed. The two existing CTests retain their original output
prefixes; the self-check additionally reports `clear_occurrence_mutants=3`.

## Repaired Checker Validation

The repaired checker completes against the unchanged PR357 packaged Linux
executable: all 2,395 cases and 2,052,567 raw output bytes match the original,
and its output-corruption negative control is rejected. The independent raw
comparison has actual and expected SHA256
`b8784c1803a7c49f53084a7468c822b9e42cfcc5eabc98221540db556a6b6b20`.
This is compiled dependency-head evidence, not a new-head build or full CI.

Windows and WSL pass the repaired source/oracle checks and 62 focused checker
contracts. Fourteen focused local CTests pass. All executions use dummy audio;
no heavyweight local game build, DOSBox session or new screenshot was run
above the disk guard.

## Independent Contact Frontier

The retained 96-case original contact fixture was run against the exact PR357
packaged Linux executable, SHA256
`bb85dbe3120f8219fb842688a406ea278e58a89220e9fee4fc7c623579d896e2`.
All 2,565,216 state bytes were compared. The 144 differences in 72 cases are
confined to the first two debris-guard bytes (state offsets 21363/21364), which
alias original contact staging at `DS:655E`. Every other output byte matches.

Actual contact stream SHA256:
`13a29c5717df3222d1e5240b714fecac730b1e5f053531b040f072f3e0fff186`

Original contact stream SHA256:
`aa7eff66ab2542f12532951eb1e1e160815e101687ecc618ae9013682a558e0a`

That production storage difference remains open. This source-contract repair
does not hide it or claim natural gameplay, sound-interrupt, rendered-pixel or
whole-game equivalence. Exact-head full CI, dependency integration and completed
external review remain separate delivery requirements.
