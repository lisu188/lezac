# Natural reentry objective context

Base: main `3c79e3ec71154f0e53784b22d6e254df6c337c06` (PR #247).
Scope: read-only evidence for natural level-1 physical held-fire routes.
No gameplay gate, RNG seed, input byte or objective is forced to obtain reentry.
This is not a whole-game completion or frame-aligned parity claim.

## Exact death boundary

The pinned original EXE's file `3831..3865`, main-CS `30C1..30F5`, scans
the tile plane, stores the remaining objective count at `DS:2074`, adds
`DS:2088` (collected), compares unsigned with `DS:2086` (required), and
writes the shared gate at `DS:79CA`. The next five bytes at main-CS `30F6`
are `8a460430e4`, before the player death-state writes.

The optional `--objective-context` recorder uses schema `held_fire_irq_v4`
and a guarded third hook at `30F6`. It retains the exact death frame, RNG,
collected/required/remaining counts, objective tile, gate and player marker.
The normal frame hook independently counts current objective tiles and reads
the current RNG and counters. It never calls the game's RNG or writes tiles.
The original's word addition is checked with its 16-bit wrap semantics.

The extension fits in the previously unused tail of the existing 128-byte
ring record. The 4,096-byte resident allocation and 16 slots do not grow.
Registers, flags, DS and ES are preserved. Both recording hooks briefly
mask IRQs; the main loop does not wait for the host observer. All attempted
hooks are restored and verified, including failed installations.

Default v3 recording and both pinned v3 traces retain their exact stub
identities. The strict checker accepts v4 only with its extra fields, third
stub hash, death-boundary consistency and three restoration receipts.
Synthetic validator tests are not new original-game observations.

The C++ production-input diagnostic now records menu RNG, per-update
objective context and a read-only callback immediately after the production
death gate is latched. Its existing return-model regression checks both
players and both gate values, one callback per death and unchanged RNG.
The physical harness preserves this context even in an incomplete result,
and records executable, observer-source, harness and original-trace hashes.

## Fresh original closed-gate observation

RAM run: `/dev/shm/lezac-held-fire-objectives-original-hold-b-20260930`.
Canonical trace SHA-256:
`78b656f53d419e6b215ceeaa851ed3923ff6e67f70eba5c8a448533e46fabf2e`.

There are 320 raw observations. The first observed RNG is `3293956326`;
this is not the startup clock seed. At sequence 216, the remaining objective
count changes from one to zero while collected stays zero and required is
one. Death is first sampled at sequence 236 / frame 322. The exact death
hook records frame 321, RNG `2517949230`, collected zero, remaining zero,
required one, objective tile 108, player one and gate zero.

The 295-row prefix through countdown is independently checked with the
objective-context validator. At sequence 296 / frame 382, the player is
initialized again, the objective returns, gate resets to one and fallback
is 230. This is a restart, not successful reentry. All three original hook
restoration receipts are present. The strict lifecycle capture correctly
remains failed; its missing completion marker is not repaired or promoted.

This establishes that natural held fire can close the objective gate in
the original too. A closed C++ gate alone is therefore insufficient evidence
of a production bug. It does not prove equal RNG, trajectory, destruction
timing, input-repeat timing or restart presentation in the two versions.
Fresh C++ physical runs must be assessed using their own exact boundary.

An earlier recorder test failed because the independent tile scan clobbered
BX, which held the ring commit address. The scan now saves/restores BX and
a regression assertion covers that instruction window. The earlier failed
run remains at `/dev/shm/lezac-held-fire-objectives-original-hold-20260930`.

## Checks and limits

The 24 Python guard tests pass on WSL and native Windows. They cover legacy
pins, v4 parsing, context bounds, exact versus later counts, read-only C++
trace summaries, partial installs and restoration. Both recorder self-checks
also pass. A v4 self-check is registered separately in CTest.

The first fresh C++ physical capture recorded a closed gate at frame 432:
collected zero, remaining zero, required one and boundary RNG `2137609202`.
Its incomplete result correctly retains those counts. It also exposed a
readiness race: input could dismiss the menu before the first governed
observer tick. The menu snapshot is now flushed before the ready signal,
and the context validator rejects missing or invalid startup-menu RNG.
The earlier run's null menu seed remains null, not retroactively inferred.

Full builds and suites run in remote CI because the Windows backing volume
is above the project's 90 percent usage threshold. Live captures use RAM,
private Xvfb and forced dummy audio; no system volume setting changes.
Passing diagnostics does not establish a repeatable successful physical
route, natural full-campaign fidelity or completion of the reconstruction.
