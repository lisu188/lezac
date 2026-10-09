# Physical Spawner Construction

This batch recovers the post-allocation writes in the shipped monster spawner
constructor. It does not establish complete monster-updater, natural-route,
visual, sound-runtime, or whole-game parity.

## Original Evidence

Unmodified `LEZAC.EXE` instructions `1000:7A6B..7C3D` were executed with the
retained MZ-relocating Unicorn 2.1.4 loader. No instruction patches, call stubs,
interrupts, or hardware I/O were permitted. Two independent 1,620-case captures
produced identical fixture streams, full-memory post-state hashes, register
hashes, and write-site observations. Each observed execution matched an
observer-free execution across all 1 MiB of memory and 14 registers.

Coverage includes all 15 shipped profiles, three RNG seeds, two salted physical
storage patterns, source rows 1..4, actor counts 0/29/30, and six blocking gates.
There were 1,080 allocator attempts, 720 successes, 2,880 original RNG calls,
and zero original sound requests. A further cross-check matched 45 retained
DOSBox constructors across 3,240 constructor-written actor, visual, spawner,
and RNG bytes. The older fixture's normalized inactive snapshots are not used
as proof of untouched storage.

The compressed fixture is
`tests/fixtures/spawner_construction_storage_original.bin.gz`:

- Raw size: 6,055,944 bytes; state size: 1,867 bytes.
- Raw SHA256: `0b1a2ed9cb58c87e981f587f82ff88e6eab1730103084308877dceddaa3e07df`.
- Compressed SHA256: `2c6ab90501a9dbb28d4b377789a9cca4d6b016c2669c1a8bef8e02fa8240d0da`.
- EXE SHA256: `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
- Levels SHA256: `d8b553871014108515d6af05b0853de8ccc22e4d3e44d63533ba1167fdc8c7b2`.

## Production Changes

The spawner path now attempts allocation before drawing random values, retains
failed-allocation scratch results, admits only enabled byte 1, and updates the
DS:79A3 initial-sprite/reward-roll alias. Successful construction writes the raw
AI words, animation selectors, active animation, stored HP byte, and source
reference through `ActorSlots`. Opaque byte 5 and backup bytes 29..35 survive.
The typed HP remains one greater than the stored original byte.

## Validation Boundaries

The source-extracted production constructor matched all 1,620 native cases:
2,551,500 physical actor/visual/link/count/result bytes plus 8,100 RNG/roll bytes.
Fifteen compiled mutation controls were rejected. ASan/UBSan, full App syntax,
and source guardrails passed. This is not a compiled whole-App runtime result.

`--debug-spawner-construction-storage` adds a strict real-App replay with legacy
actor projection disabled. Its CTest checker runs a positive replay and rejects
ten malformed fixtures. Real-App runtime acceptance remains pending until the
compiled executable passes this test in CI. The diagnostic compares physical
actor storage, RNG/roll, typed spawner counters, identities, and absence of sound
requests. It does not claim a production-owned physical spawner bank or loop
cursor. Those bindings and the full fatal-entry updater comparison remain open.

All processes use dummy audio. No game build, DOSBox launch, or screenshot was
performed locally because the Windows backing volume remains above its 90%
disk guard. Existing assets, dirty canonical files, Git donors, and evidence
were preserved.
