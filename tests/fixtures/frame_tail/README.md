# Original Post-Queue Tail

The frozen projection observes unchanged original instructions from 1000:806A
through the next-frame, completion, Escape, view-change or runtime-error boundary. It includes
shake/RNG, DAC updates, the countdown tile callback and its shared tile writer.
View-resize and UI/level-transition bodies remain outside this boundary.

There are 2,576 controlled cases, 688,022 dispatched original instructions,
72,808 writes and 40,752 emulated DAC output events. Detailed tracing and
stop-only code hooks agree on all 1 MiB RAM, fourteen registers and DAC events.
Ordered writes reconstruct the complete final memory image.

The matrix includes eight excluded-tile substitutions and sixteen view-change
handoffs, plus rejected size/player gates and nonzero toggle states. The first
2,412 case records are byte-identical to the earlier callback dataset. Two
independent captures agree on the complete packed and decoded projection.

LZTAIL01 contains relocated-MZ-relative initial patches, entry/end registers,
delta register traces, ordered writes and DAC events. It contains no complete
RAM image. The original MZ is independently authenticated; no call is stubbed,
instruction patched or later state injected.

The producer requires pinned Unicorn 2.1.4 and a new RAM-only output directory.
These controlled CPU cases are not natural gameplay, App integration, an
original interrupt schedule, aligned rendered frames or whole-frame fidelity.
