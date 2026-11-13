# Live Foreground Boundaries

This read-only observer extends the natural `game:7903..7A13` evidence with
two fast-gate windows: an initial stale HUD cache, then a short original CRT
delay containing an already-pending PIT event. It does not patch instructions,
seed guest state, pause the process or arm an interrupt.

Only the selector/controller are separate from the previous foreground probe.
Clock/PIT/device getters, input-route recognition and binary codecs are shared
unchanged. Their exact hashes are retained alongside the new observer hashes.
`rebuild.py` replaces only the owned host's selector and retains the previous
binary, header and build report before rebuilding.

`capture.py` uses a private Xvfb display and dummy audio. It waits for the first
traced window to finish before sending the ordinary Z hold, avoiding input
arriving during expensive observation. `trace.py` requires actual HUD entry,
REP dispatch and natural IRQ entry. `project.py` verifies original executable
relocation, canonical asset hashes and five retained local RAM samples before
using the shared binary codecs.

The live replay accepts the observed idle-keyboard, idle-sound profile. Its
only I/O event is the derived PIC EOI write; it uses no recorded port-read
responses. Active IRQ1/repeat and active speaker/PIT2 input are not established.

`render_hud.py` visualizes actual C++ replay-buffer dumps beside independently
observed original pixels. Two 17x8 regions are stacked for inspection. These
are same-boundary HUD comparisons, not full App screenshots or whole-frame
parity evidence.
