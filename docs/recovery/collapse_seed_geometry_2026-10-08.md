# Original Collapse Seeding Geometry

## Corrected Rule

`1000:370E` does not find a four-neighbor connected component. Its low-word
branch expands a rectangle from the seed by testing all four perimeter edges
before applying any expansion. It then flags every matching word inside the
resulting rectangle, including diagonal contacts and enclosed disconnected
islands. The prior C++ flood fill could leave these cells outside the new
collapse record and give it different bounds and mass.

`gameplay::seedCollapseWordGroup` now implements the original simultaneous
edge expansion, 16-bit byte offsets and signed scan comparisons. Production
`queueTileDamage` consumes its word-plane writes, bounds and selected cells.
The caller's capacity gate, velocity initialization and optional object-plane
handling are unchanged. The function is a production helper, not test-only code.

## Original Execution

`tools/capture_original_collapse_seed_geometry.py` loads the hash-pinned
original executable with all 468 MZ relocations and executes the complete
seeder and Pascal stack check. It requires normal CS/IP/SP return boundaries,
rejects unexpected interrupts/hardware I/O, and neither patches original
instructions nor stubs calls. Expected output records come from actual
original memory: bounds, marked-cell count, mass byte and complete word plane.

The 1,124-case fixture contains:

- 40 synthetic shapes in four orientations, including diagonal chains and
  a ring enclosing a detached same-key center.
- Four map-corner cases.
- 540 components from the unchanged shipped maps, all of which agree with
  the old four-neighbor geometry.
- 540 controlled-clearing variants of those shipped maps. These are explicit
  fixture mutations, not naturally played routes.

The old four-neighbor model differs in 168 cases: 12 synthetic and 156
controlled-clearing variants. An eight-neighbor flood is also insufficient:
the original can include disconnected same-key cells enclosed by the rectangle.

The fixture and metadata pin the original executable, `LIVELS.SCH`, original
instruction window, decoder, generator and input/output digests. The optional
capture dependency is Unicorn 2.1.4; production and CI do not depend on it.
Reproduction uses exclusive output creation to preserve earlier evidence:

```sh
env SDL_AUDIODRIVER=dummy python3 tools/capture_original_collapse_seed_geometry.py \
  --exe LEZAC.EXE --levels LIVELS.SCH --unicorn-path /path/to/unicorn-2.1.4 \
  --out /path/to/empty/collapse_seed_geometry_original.bin.gz \
  --metadata /path/to/empty/collapse_seed_geometry_original.json
```

## Compiled Regression

The compiled probe calls the same header implementation used by production.
The comparator checks every bound, count, mass and word-plane output byte.
It also requires two compiled negative controls (four/eight-neighbor floods),
rejects an output mutation, and checks six production consumer mutations.
CI runs the focused tests before the unchanged full platform suite and package
validation. Source checks alone do not establish the compiled comparison.

## Limits

This is controlled original helper execution, not a natural DOSBox timing or
campaign capture. Controlled clearing does not prove a natural trigger route.
The compiled comparison does not cover all seeder record bytes, allocator
scratch globals, arbitrary unallocated memory, the complete collapse update,
sprite playback or actor/two-player fidelity. Original-fidelity and whole-game
completion claims remain false, and later campaign completion remains open.
