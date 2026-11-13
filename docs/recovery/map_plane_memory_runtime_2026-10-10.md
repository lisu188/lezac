# Debris Map-Plane Memory

## Confirmed Divergence

PR375 CI37992182712 produced identical Linux and Windows App streams. The
first315 states match the unchanged512-state original physics reference. The
next five differ; the checker stopped with192 states unexecuted. Scene19,
step11 moves fragment41 from cell1953 to2013, past the1980-cell logical map.
The old solid clamp causes two extra RNG draws. A single original backing byte
changed from0 to1 reproduces all16 C++ states for that scene; the unmodified
original still matches its reference. This is a seeded case, not a natural
shipped-level reachability claim.

## Recovered Contract

Original debris object offsets wrap modulo65536. Word byte offsets also wrap
modulo65536, so word cells alias every32768 cells. Off-map writes persist and
are read back in later updates. The original loader allocates the byte plane
first and word plane second, each with16 extra bytes and eight-byte allocator
rounding, then aligns the usable pointers to paragraphs. In normal play an
object-tail byte can therefore alias live word-map data.

The loader frees the old planes at file 0x13FF..0x1448. Its allocation/alignment
sequence is main-code 0D60..0E0A, at file 0x14D0..0x157A. The established
tall-background captures independently check both allocation and aligned
pointers. See [Tall-Level Background Reads](tall_background_runtime_2026-09-06.md).

## Implementation

`MapPlaneMemory` retains backing bytes and resolves logical map and word-array
aliases on every read/write, so direct updates to the live arrays stay visible.
Level replacement saves both old planes and retains the FreeMem size metadata.
The intro completion path does not allocate the same map a second time.
The production debris updater uses these accessors and wraps destination-cell
writeback to16 bits.

Existing original-machine fixtures restore explicitly separated zeroed plane
segments. The diagnostic restores that topology once per initial scene, not
between continuous updates. The production updater and accessor are shared;
the different fixture topology is supplied machine state, not an expected-state
override. Historical fixture/checker/metadata bytes remain unchanged.

## New Evidence

The portable producer executes12 seeded original scenes with two uninterrupted
updates each. Ten cover logical-map exit, tail retention, object underflow and
overflow, word aliases, vertical wrapping and stationary tails. Two shared-plane
scenes verify a fragment writing into a live word byte and a live word byte
blocking the fragment. All24 boundaries agree between instrumented and neutral
executions over full1MiB RAM and14 registers. No instructions or calls are
patched, and hardware I/O is forbidden.

The compiled production accessor replays168 original memory accesses (88 reads,
80 writes) from input-only event streams. Expected read values are not supplied
to the executable. The checker compares all reads and complete final64KiB
object/word images, totaling1573100 output bytes. This is accessor evidence,
not a full-App physics comparison. Dedicated units additionally cover live
aliases, word/object wrap, map replacement and seeded-fixture isolation.

## Open Scope

Fresh512-state actual App comparisons on both native CI hosts, affected
historical oracles, full required CI and current-head external review remain
delivery gates. Arbitrary DOS heap initialization, unrelated allocations after
the word map, boss/new-game heap reuse, out-of-map cascaded seeding and the
collapse mover's logical boundary policy remain open. This is not a general
Pascal heap emulator or a whole-game fidelity claim. All runs are silent; no
local full game build or new capture is performed above the disk guard.
