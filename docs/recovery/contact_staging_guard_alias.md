# Contact Staging Guard Alias

## Original Storage Rule

The last admitted fragment is physical record 1400; the following retained
record starts at `DS:655E` (`292B + 1401 * 11`). The original contact collector
at `1000:4ECD` writes each unique nonzero contact word to `655E + 2 * index`
and its target offset at `1000:4ED1`. It scans own cells in row-major order and
does not clear unused staging words. The first six words therefore overlap all
eleven guard bytes; the high byte of word six is outside the guard.

Movement and above-cell seeding invoke this collector. Support (`4D3C`) and
sideways balance (`4DD3`) scans do not. The single-fragment impact caller also
writes the first word before each lane helper (`4C8C` and `4C9F`), including
before a potentially failing seeder admission.

## Production Mapping

`writeContactWordGuardAlias` updates the typed retained record without changing
the live queue count: tile index, flagged word, velocity pair, subfraction pair,
rest/lookup pair, and the final auxiliary byte. Full contact words remain in
the existing contact vector for lane processing. This is the overlapping guard
mapping, not a complete DOS data-segment memory model.

Only collecting scans write this alias, before appending a newly unique word.
Duplicate contacts and zero-word hard blockers do not append. Non-collecting
support/balance scans leave the guard unchanged, and short contact lists retain
the untouched tail bytes. The direct debris-impact path stages before seeding.
No diagnostic installs expected outputs or masks guard bytes.

## Unmodified-Original Evidence

Two independent complete-state matrices use the existing 96-case
`LZFC0001`/`LZFP0001` diagnostic protocol. Each compares 2,565,216 state bytes,
including 1,402 physical fragment records, 251 collapse records, the complete
1,575-byte actor bank and seven sound fields.

- Moving-pool matrix: four directions, hard/fragment/collapse/unflagged targets,
  three fragment/collapse capacity configurations, and actor pools 0/30.
- Multi-contact matrix: four directions, one through six edge contacts, unique
  and duplicate words, hard blockers and stationary support-only checks. Actor
  pools alternate 0/30. All eleven guard-byte write offsets are observed.

Both producers execute unmodified original instructions without stubs,
interrupts or hardware I/O. Observed and neutral executions match all 1 MiB of
RAM and fourteen registers. They are seeded CPU probes, not natural gameplay.

Before this repair, the exact PR357 packaged Linux executable differs only in
the guard: 144 bytes in 72 moving-pool cases and 212 bytes in 48 multi-contact
cases. Every other compared byte matches. Failed raw streams are retained.

Original expected stream SHA256 values:

- Moving pools: `aa7eff66ab2542f12532951eb1e1e160815e101687ecc618ae9013682a558e0a`
- Multi-contact: `cd42a242dd437c02719633e4b4661559e2da2fb139c27ad74fa8806973afc74a`

## Validation Boundaries

Both portable producers regenerate their fixtures, expected streams and full-RAM
repeat hashes exactly. The extracted production alias helper compiles separately
and matches all 192 original guard results (2,112 bytes), without admitting a
live queue entry. This proves the typed helper mapping, not whole-App execution.
C++ syntax, source guardrails, 71 focused checker tests, twelve corpse contracts
and seventeen focused local CTests pass. The new CI group registers 29 tests,
including both complete raw contact comparisons.

Each fixture has independent compressed/raw/output pins. Only the 468,635-byte
moving-pool fixture receives an explicit 512 KiB compressed allowance; the
shared default remains 128 KiB. Tests reject changes to every guard byte,
adjacent state, source role/mapping, execution marker and fixture limits.

Exact-head compiled comparisons and full Linux/Windows CI remain required.
The disk guard prohibits a heavyweight local game build, DOSBox or new capture.
All executions and children use dummy audio. External review and dependency
integration remain merge gates. No natural-route, rendered-pixel,
sound-interrupt or whole-game parity is claimed.
