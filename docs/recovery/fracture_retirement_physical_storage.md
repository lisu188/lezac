# Fracture Retirement Physical Storage

The original collapse updater increments the physical rest byte at 1000:5530
and mutates flags during motion/support checks. At 555A and 556E it writes
the current magnitude to DS:2074 and the magnitude difference to DS:2072.
Fracture then branches at 5571, constructs debris and an actor, and removes
the record at 55FD. It never reaches the normal motion-field writeback at
5602..5651. Compaction preserves the inactive tail.

The production updater now commits flags/rest and the shared scratch writes
before that branch, while retaining full motion writeback only for the normal
path. In particular, fracture must not copy locally integrated fractions or
new velocities into a retired physical record.

## Original Evidence

The portable producer executes the pinned, relocated original without patched
instructions, stubbed calls or hardware I/O. Its 288 cases cover one/two live
records, all nonempty fracture masks, timers 0/94/255, flags 0/83, ticks 0/2,
two random seeds, actor pools 0/29/30 and accepted/rejected sound priorities.
It observes 360 fractures, 720 debris seeder calls, 360 actor constructor
calls, 360 removals and 144 normal writebacks. An observed and a neutral
executor agree on all 1 MiB RAM and 14 registers after every case.

Each expected state contains 7,664 bytes: RNG/counts/destroyed/next fragment,
both complete 60x33 terrain layers, five physical debris records, five
physical collapse records, the complete 1,575-byte actor/visual/link bank
including shared result, and seven sound request/latch bytes. Salted inactive
slots and guard rows are included without masks. The full comparison is
2,207,232 state bytes, excluding its 16-byte framing header.

The diagnostic seeds only request bytes, skips expected state bytes, calls
the actual production updater, and serializes its owners. Typed actor orders
must match physical storage without legacy adoption/retirement. The checker
pins the original executable, compressed fixture, decompressed fixture and
expected output independently; it retains actual bytes and executable hashes.

## Validation Boundaries

Fixture/checker contracts, original CPU evidence and source syntax are not
actual-App acceptance. Exact-head Linux/Windows raw output and full CI must
be inspected separately. Source-order negative controls are not observed
pre-fix compiled-App failures. All execution uses dummy audio. Above the
disk guard there is no heavyweight local game build or new screenshot.

This seeded fixture does not prove naturally reached fracture behavior,
full-capacity debris/collapse banks, sound interrupt playback, rendered-pixel
parity, campaign completion or whole-game fidelity. Delivery remains stacked
on the normal-retirement fix and requires dependency integration and review.

## Reviewed-Stack Cursor Repair

The retained Linux and Windows failures at original PR #355 head
`5ba965c8b4408355a40d5f3f5c217605b537c4bc` were rechecked against the pinned
original fixture. Both complete streams differ in exactly 432 bytes across
216 cases, exclusively at shared-cursor state offsets 7657/7658. Across the
full 2,207,232-byte state comparison, every other byte matches without masks.
The archived actual stream
SHA-256 is `dbbcc0c3e71439c4456fa0820e66aef1e860c07b26c2c017c811287cf667a0e0`;
the original stream SHA-256 is
`7a89bfbf40eed17b11749341841da5515580f6e5c386fab0783b2066dca01311`.
This is a verified historical compiled-App failure, not a fresh pre-fix run.

The narrow repair and three regressions are brought forward from PR #357
commit `3ab27d0e718b5dba9ab3d83a6f68bc67f3d4d7bd`, without the unrelated
full-pool diagnostic changes from #356. Original instruction `1000:501F`
(`89 3e 74 20`) writes the fractured cell to the shared cursor before RNG and
the seeder. The production loop now performs that write. The regressions
bind the original instruction, all 216 native cell cursors and source ordering
with a missing-write control. Expected fixtures and comparison masks are
unchanged. Fresh exact-head App output, both full platform suites, prerequisite
delivery and external review remain independent requirements.
