# Fracture Shared Cursor Write

## Confirmed Compiled Difference

The retained Windows raw output from PR #355 at
`5ba965c8b4408355a40d5f3f5c217605b537c4bc` differs from the independently
pinned original fixture in 216 of 288 cases. Every one of the 432 differing
bytes is in the two-byte shared sound/selector cursor at state offsets
7657/7658. All 2,207,232 state bytes were inspected without masks.

Actual stream SHA256:
`dbbcc0c3e71439c4456fa0820e66aef1e860c07b26c2c017c811287cf667a0e0`

Original stream SHA256:
`7a89bfbf40eed17b11749341841da5515580f6e5c386fab0783b2066dca01311`

The Windows full-pool output from PR #356 at
`59f18df3b5ad92b4168ada13b8691e4fdd9e72c2` has the same difference in
72 of 96 cases: 144 differing bytes, confined to state offsets 26714/26715.
All 2,565,216 state bytes were checked. The five preceding raw comparisons
(fatal entry, first seeder, capacity, multicell and normal retirement) still
match their original streams; the fracture-retirement stream is the same
failed stream as PR #355.

Actual full-pool stream SHA256:
`687d40b50d753c71ac737c4b6f4322fcb1ffa6fbc0328b769fc8141dd208000b`

## Original Rule and Repair

The unmodified original at `1000:501F` stores the current fractured cell
index from DI into `DS:2074` (`89 3e 74 20`). This happens for each owned cell
before its RNG draws and seeder call. The earlier magnitude write at
`1000:555A` and the fracture sound request do not establish the final cursor.
A later normal collapse record can overwrite it with that record's magnitude.

Commit the cell through `sound_.writeSharedCursor()` in the production fracture
loop, before RNG and seeding. Do not modify the expected fixtures or hide the
cursor from the comparator. No other physics or storage rule changes.

The existing two actual-App comparisons remain the functional regressions.
Additional contracts bind the original instruction, the native fixture's
216 cell-valued cursors, and the source ordering with a missing-write negative
control. Source and fixture contracts are not compiled-game acceptance.

## Delivery Boundaries

This repair is stacked on PR #356 on a new branch, leaving both previous live
Linux jobs untouched. The retained failures remain failures of their original
heads. Exact-head compiled Linux/Windows raw comparison, full CI, dependency
integration and completed external review are required before merging.

The separate 96-case moving-contact CPU probe found that contact staging at
`DS:655E` aliases the first bytes beyond the live fragment pool. That evidence
is retained separately and is not repaired or claimed covered by this change.
No natural-route, whole-campaign, rendered-pixel or sound-interrupt playback
equivalence is claimed. All local executions use dummy audio; no heavyweight
local game build or new screenshot was made above the disk reserve guard.
