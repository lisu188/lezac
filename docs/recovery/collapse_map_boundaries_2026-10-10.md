# Collapse Map Boundaries

This change continues PR376 without changing its historical fixtures or checker
bytes. It corrects collapse movement and scans using the original DOS address
expressions and fixed per-update rectangle geometry.

## Original Evidence

`capture_original_collapse_map.py` runs the unmodified original coupled caller
at 1000:804E..806A. Nineteen seeded scenes cover 34 update boundaries: logical
map tails, negative and positive word-offset wrap, adjacent shared map planes,
two-cell and square blocks, and a horizontal row crossing with support.
Instrumented and neutral CPUs agree on all 1MiB of RAM and 14 registers at every
boundary. The observer records 429 reads and 192 writes. No original instruction
or call is patched/stubbed, and hardware I/O is forbidden.

The fixture contains input state, both complete 64KiB map views, and complete
expected state plus map views after every update. It uses an empty physical
actor bank with the valid sentinel and two reserved visual slots. The earlier
investigation's all-zero bank was not a supported App input; this fresh capture
seeds the same valid bank in both original CPUs before execution.

## Recovered Rules

- Source words use a 16-bit byte cursor. Source object cells are cursor >> 1.
  Destination word offsets wrap independently from destination object cells.
  Normalizing both planes to a 32768-cell ring loses retained object writes.
- 5181..51B9 derives rectangle dimensions once. Movement translates first,
  top-right and last cells with 16-bit wrap, without recomputing those counts.
- 4EE7 prioritizes up/down traversal before left/right. Rightward square motion
  keeps rows top-to-bottom and reverses only columns; downward motion reverses
  both. The helper retains the original CX=0 LOOP iteration count.
- 4F89/4F8C/4F9D/4FA0 writes the destination word, clears the source word,
  exchanges the source object with zero, then writes the destination object.
  Each moving cell is tested live, preserving shared-plane aliases.
- Contact cells come from wrapped word byte offsets, while support columns come
  from the independently wrapped object destination cell.

All collapse map writes use the production map backing, including existing
fracture and retirement paths. This prevents direct vector indexing beyond the
logical map. It does not establish complete fracture/retirement boundary parity.

## Validation Boundaries

The checker pins the original executable, producer, dependencies, fixture,
metadata and access trace. It replays all 621 accesses against live aliasing
planes and compares every expected plane image. Its output comparator rejects
corruption across all serialized regions, invalid headers and wrong lengths.

The new input-only `--debug-original-collapse-map` command receives no expected
state. It retains backing bytes between the one or two updates in each scene.
The actual App comparison checks 5,365,064 state bytes across the 34 boundaries,
with no masks. CI runs that comparison on Linux and native Windows, independently
of the older 512-state coupled fixture. Passing fixture/source/unit checks alone
must not be reported as passing the compiled-App comparison.

Above the project disk guard, local validation is limited to standalone cursor
compilation, focused source/oracle checks, configure and App syntax-only checks.
No local full App build/run or new game screenshot is performed.

## Still Open

Arbitrary DOS heap initialization and unrelated allocations, cascaded out-of-map
seeding, fracture actor selection after coordinate wrap, and retirement's signed
endpoint traversal need separate recovery. Wrapped multi-cell scenes are only
continued for the bounded update counts recorded in the fixture. Natural
campaign/boss/two-player progression, complete prefix and clock/sound fidelity,
full required CI and current-head external review remain separate gates.

`original_fidelity_claim=false`, `sound_runtime_parity_claim=false`,
`port_functionally_complete=false`, and `whole_game_complete=false` remain.
