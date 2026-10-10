# Collapse Removal Endpoints

This change continues PR377's map-backed fixed movement rectangle. Removal uses
a different original traversal and must not reuse those fixed counts.

## Original Evidence

The portable `capture_original_collapse_removal.py` executes the unmodified
coupled caller at 1000:804E..806A for seven seeded scenes. Instrumented and neutral
CPUs agree on all 1MiB of RAM and 14 registers at each boundary. There are
372 map reads and 39 writes, with no instruction/call patching or hardware I/O.
The new producer reproduces all seven t140 states and fourteen full RAM images.

The fixture pins all input state, complete retained physical record/actor banks,
shared state and both 64KiB map views. The App diagnostic receives only inputs,
not expected states. Its comparison checks all 1,104,572 resulting state bytes
without masks. These are bounded seeded states, not natural campaign progress.

## Recovered Rules

The removal helper at 1000:508B compacts the physical collapse queue before
clearing matching map words. It walks a 16-bit word byte cursor with signed
endpoint comparisons, using inner and outer do/while loops. First and last
globals have already been doubled. Fracture leaves top-right in cell units;
timer-95 retirement doubles it at 5660..5665 before the call. Fracture cleanup
can therefore reach outside the movement rectangle and into retained map tails.

Sentinel words prove the extent: fracture at 1220 clears matching words at
1340, 1460 and 1820, but not 1880. Fracture at 1953 clears 2073 and 2913, but
not 2973. Wrapped right/up walks preserve their separate inside/outside sentinels.
The retirement scenes preserve matching words outside their original walk.

At 558C actor selection uses the fixed column count already derived at 5181.
At 5597..559C it normalizes the last word byte offset before subtracting the RNG
result, then wraps the resulting cell to 16 bits. Actor visual coordinates
independently confirm selected cells 0, 32748, 59, 1220 and 1953. The retirement
scenes create no actor. Constructor admission and animation parameters are unchanged.

The separate `collapse_removal.hpp` helper reproduces the signed endpoint walk
and actor arithmetic. It deliberately introduces no arbitrary traversal clamp.
Some endpoint combinations do not terminate under the original comparisons.
The unit visitor interrupts a synthetic full cycle to verify that the C++ helper
has no hidden cap; those unbounded combinations are not executed in the original
seven-scene capture or claimed as runtime acceptance.

## Validation And Limits

Standalone Linux and native MSVC tests cover signed endpoints, mixed units,
wrapped actor cells, fixed columns and a synthetic unbounded cycle. Compiled
negative controls reject unsigned/strict comparisons, wrong row units, actor
subtraction before normalization and recomputed columns. The fixture checker
replays all observed accesses and rejects malformed/corrupted outputs and source
routing changes. Historical original fixtures and producers are not rewritten.

The historical actor checker binds to the newly recovered selection call while
preserving its original metadata, constructor, admission and state comparisons.
The PR376 Windows CI failure also requires preserving the existing map-plane
fixture bytes on checkout. Its `-text` attributes do not change those bytes.

Above the disk guard, no local full App build/run or fresh screenshot is performed.
Full required CI, actual Linux/native Windows App outputs, exact-head external
review and prerequisite integration remain separate acceptance gates. Natural
later campaign/boss/two-player routes, arbitrary heap initialization, full prefix
and clock/sound fidelity remain open. Whole-game completion is not established.
