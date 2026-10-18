# Generic Corpse Routing Guard

The full Linux and Windows jobs for integration #442 at `70fbb3c` failed in
the complete corpse-storage step, before running the complete remaining suite:
`https://github.com/lisu188/lezac/actions/runs/39158699298`.
The original failures are retained. Local execution reproduced nine failing
mock-contract subcases and the routing error.

The checker required generic animation, generic corpse motion, physical
writeback and reward conversion in that order. It found writeback by the first
occurrence of the method name `actorSlots_.writeCorpse` anywhere in
`updateMonsters`. The original-backed boss ownership repair added a distinct
boss-debris write earlier in that function. The generic corpse path itself
still calls its motion helper before its own exact writeback and conversion;
the checker was comparing two different branches.

The repair uses the already-required complete generic writeback call prefix
for the order comparison. It does not add an exemption, change production
dispatch, alter a fixture or skip any test. A new control verifies the valid
boss write precedes generic motion, then moves the actual generic writeback
before its motion and requires rejection. Existing missing-call, diagnostic
bypass, terrain, timer, execution-marker and unmasked-byte controls remain.

Five Python tests pass on Linux and native Windows. A fresh complete Linux App
and helper build passes all five exact corpse CTests, including both original
lanes (3,252 operations and 5,180,436 compared bytes per lane), both protocol
lanes and checker controls. All original fixtures and production C++ bytes
are unchanged. All launches use dummy audio/video; outputs remain RAM-only.

These are bounded corpse-storage and checker proofs. The fixed integration
still requires review of its new head and both full hosted platform suites;
the earlier clean review and failed jobs are not carried forward as approval.
