# Physical Cascade Seeding

## Recovered Behavior

The original coupled debris/collapse caller can invoke `1000:370E` with a cell
outside the logical 60-by-33 level. The seeder converts that cell into a 16-bit
word offset before using the map backing storage. For example, above-cell
subtraction from cell 40 produces cell 65516, whose wrapped word address is
cell 32748. Clamping this to the logical level loses a real cascade.

`queuePhysicalTileDamage` preserves that address conversion and uses
`MapPlaneMemory` for key reads, object reads and flag writes. Collapse geometry
uses the same physical callbacks. The existing `queueTileDamage` entry remains
a bounded logical-coordinate adapter for ordinary tile requests. This does
not change admission capacity, retained seeder results, record tails, phase
arguments, collapse traversal order or ascending live-bound debris iteration.

The rectangle algorithm still expands matching perimeter edges simultaneously
and flags matching words inside the resulting rectangle. It is not replaced
with four- or eight-neighbor flood fill.

## Original Evidence

`capture_original_outside_map_seeding.py` captures twelve seeded boundaries
through the unmodified original coupled caller. Cases include fracture seeds
inside and beyond the logical map, above and blocked collapse contacts,
already-flagged rejection, debris consumption and motion, wrapped above-cell
addresses, and same-pass appended debris. Eleven cases enter the original
seeder; the flagged control does not.

The fixture retains complete physical state and both 64-KiB map backing
planes: 157796 output bytes per case, 1893552 bytes total. Its event stream
contains 268 reads and 43 writes. Observed and neutral executions match over
the complete 1-MiB memory image and fourteen registers. Original instructions
are not patched, calls are not stubbed, and hardware I/O is forbidden.

The portable capture reproduces all twelve independent probe inputs, outputs
and twenty-four full memory images byte for byte. A prior exploratory debris
input used an animating glyph instead of the intended consumption glyph; that
failed input and its diagnostics remain preserved outside the published
fixture.

## Validation Boundaries

Focused Linux and native MSVC helper validation passes, including all 1124
historical original geometry cases. Three physical-addressing mutants and
two compiled flood-fill mutants are rejected. The new checker rejects fifteen
output/protocol corruptions and eleven source-contract mutations. Existing
contact, retirement, map, debris, actor and physics checks remain covered.

CTest adds `collapse_physical_seed_unit`, `collapse_physical_seed_fixture`,
`collapse_physical_seed_checker` and `collapse_physical_seed_original`.
Linux and Windows CI compare the input-only production App output against
all twelve complete original states without masks and retain diagnostics.

At publication, these new full-App comparisons and required CI are pending.
Helper checks, source checks and seeded original captures do not prove natural
campaign reachability, rendered fidelity, sound runtime parity or whole-game
completion. All execution is silent, and no new gameplay screenshots are
claimed by this change.
