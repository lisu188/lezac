# Collapse Fracture Actor Creation

The complete collapse oracle previously executed actor constructors but did not
compare their records. This separate fixture adds the resulting 38-byte actor
and 8-byte visual records without changing the legacy generator or fixture.

## Original Evidence

`capture_original_collapse_actors.py` executes unmodified relocated `LEZAC.EXE`
instructions from `1000:5102` through return, including constructors at
`1000:2F9F`, visual allocation and animation initialization. No original call
is stubbed. The four record-table initializer instructions are also executed,
and both return and initializer boundaries are checked.

The 2,476 cases comprise:

- All 2,395 legacy cases, with every existing map, live damage record, RNG,
  destruction counter and next-fragment output byte independently reproduced.
- One direct crosscheck against the retained native fracture-actor capture:
  the complete actor, visual record and creation RNG match.
- Eighty two-fracture cases covering initial pools of 0, 1, 28, 29 and 30 actors,
  four frame phases and four RNG seeds, including zero and all-one seeds.

There are 1,822 compared actor states and 414 successful admissions. The
original constructor is entered 462 times, including full-pool refusals.
Existing actor and visual records are checked unchanged. New actors are
compared in creation order, not sorted by position or kind.

The constructor's byte at actor offset 1 is the visual slot, not the actor
pool index. The controlled room reserves visual slots 1 and 2 and starts
allocation at 3, matching the native capture. With existing actors the next
visual slot advances independently from the actor count.

## C++ Comparison

`--debug-original-collapse-actors` routes through the production
`updateCollapseRecords()` and `spawnTransientActor()` methods. The diagnostic
seeds only incoming controlled actors, then serializes actual resulting
state. Visual dimensions and pixel offsets come from the port's own loaded
SPR bank, not from expected output records. The old debris and collapse
protocols remain unchanged.

`check_original_collapse_actors.py` pins provenance and validates every record,
then compares the complete compiled output without normalization. Six output
controls cover RNG, actor count, kind, animation, placement and descriptors.
Twenty-three source mutations exercise diagnostic routing and production
constructor/capacity calls. These source checks are not compiled parity.

Real probe failures retain input, expected output, actual output if present,
stdout/stderr, command, replay command and expected case boundaries under
`build/collapse-actor-failures/`. Ten mocked probe modes and nine comparator
cases test retention separately from game execution. Both CI platforms run
the focused compiled check before the full suite and retain failure artifacts.

Local original-CPU, fixture, source and mocked-diagnostic checks are available.
Local heavy C++ builds are capacity-blocked; exact-head hosted compiled and
full-suite validation are required before merge.

## Limits

Unused actor slots are deliberately clean. The C++ diagnostic reconstructs
their zero opaque bytes; this does not prove inheritance from retired/stale
slots or a general raw-actor serializer. Initial actors here are kind 0x0b,
not all mixed actor kinds. The updater is seeded, not a natural campaign route.
Visual-table bytes are checked, not rendered pixel parity. Sound state, physical
timing, broader actor lifecycle and whole-game fidelity remain unproved.

`natural_gameplay=false`, `visual_parity_claim=false`,
`stale_slot_claim=false`, and `whole_game_complete=false` remain explicit.
