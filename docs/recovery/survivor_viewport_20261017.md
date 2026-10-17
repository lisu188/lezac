# Survivor Viewport Lifecycle

## Recovered Behavior

Original DS:79B8 counts players whose reserve lives have not underflowed, not
configured input slots and not only global-state-1 actors. The 7C3D..7EBB actor
pass decrements the reserve byte at the death countdown boundary. A transition
from 1 to 0 enters waiting state 2 and retains both viewports. A transition
from 0 to FF eliminates that player and, when one remains, 7CD3..7CE9 clears
only the eliminated physical 160x160 half. The HUD is untouched.

Elimination does not immediately collapse the view geometry. Pitch remains
160 and the surviving frame keeps its old colors. E is ignored at that pitch;
R changes it to 168, centres both destination pointers, and paints a white/grey
frame. Further R events reach 240 or 320 in eight-pixel steps. The configured
two input slots remain intact, including P2 fire ownership.

The next-level geometry block 2BE4..2BF9 uses the selected width when one
player remains. The gradient block 08AC:00BC..00F0 fills 60,000 bytes using that
pitch, including byte wrap; 77E4..77F4 latches it for rendering. Resizing alone
does not repack the old backdrop. Frames are painted at setup/resize boundaries,
not during every world redraw.

Production now owns a small `ViewportLayout` independently of configured
player slots and reserve lives. The renderer borrows it, the UI queries the
remaining-player capability, and level setup regenerates the backdrop with the
current pitch. Existing standalone render diagnostics derive initial geometry
when no layout is supplied; all use the same world draw path.

## Original Evidence

`tools/survivor_viewport_oracle.py` executes unchanged original code and callees
with Unicorn 2.1.4. The executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Its starting RAM is the authenticated natural foreground `gameplay-middle`
sample, bound to the frozen parent sources, recipe and all 14 canonical assets.
All 43,552 relocated code bytes before DS are checked before and after each
endpoint. Complete 1 MiB RAM, registers and flags match with and without the
observer at every endpoint. No instruction is patched or call stubbed;
interrupts and IN/OUT are rejected.

Eight profiles cover either eliminated player at widths 168, 240 and 320, plus
both 1-to-0 reserve boundaries. Each has ten stages: geometry, initial draw,
life loss, retained survivor draw, ignored E, R reframe, reframed draw, next-level
frame, backdrop regeneration and a draw with the new backdrop.

The frozen compressed projection is 118,458 bytes, with SHA-256
`b65173c4dbea8fb34608ce4de3d653a18b1fe9101cf557ca8529366235caed1b`.
Its 5,665,280 decoded bytes have SHA-256
`ac133f9a396ce34e0a65ff3991dd620d10d8842bf7541767d1206310a5aa54eb`.
Manifest SHA-256 is
`0e973a8164c0563f5cc7b34ed5782849152593918d327edcdbe79bd28d38f3d9`.
An independent second execution reproduces all three files byte-for-byte.
Full RAM captures, screenshots and failed exploratory evidence remain private;
the committed fixture contains compact indexed endpoints and declared inputs.

## Validation

The production renderer replay checks 3,686,400 playfield pixels across 72
painted stages with zero differences, plus 307,200 retained-HUD assertions.
The actual App command `--debug-survivor-viewport-original` checks the same
pixels using its real damage and reentry helpers: no transition for 59 ticks,
then life loss on tick 60. SDL E/R events and future repeats exercise actual App
event filtering. The command also runs the next-level pipeline and verifies
the pitch latch, configured slots and survivor fire ownership.

The full Linux App builds and all 51 selected CTests pass. Coverage includes
single/split/tall original rendering, retained-view ownership, width bounds,
HUD and palette, menu flows, two-player death/progression, reentry/wait/boss
contracts, resources and source guardrails. The frozen checker passes two
Python methods with 88 changed/missing/new/existing-output rejection controls.

Native MSVC 14.44.35207 compiles five production translation units at /W4;
five component tests compile at /W4 /WX and pass. The new checker and rejection
tests pass on Windows. Verified unchanged dependency objects are reused.
The Linux and native survivor RGB dumps are byte-identical. This is component
replay, not a full native Windows App build; unrelated production warnings
remain.

Six isolated mutations are detected: clearing the wrong half (644,352 bad
pixels), omitting the renderer clear (460,800), using configured slots to gate
width controls, repainting split frames on every draw (475,960), forcing
backdrop pitch to 160, and omitting the clear in the actual App (460,800).
Production sources remain unchanged by the mutation runs. One exploratory
mutation did not compile because it called a non-const renderer method through
a const reference; it was retained and replaced by a compiling frame-paint
mutation, not counted as a detected behavioral fault.

The final physical-key/Xvfb movement suite is not repeated: its retained raw
frames would exceed the remaining 90-percent RAM reserve after refreshing the
source-bound original evidence. No new physical-key or full Windows App claim
is made from the normalized SDL event test.

A fresh actual-App walk matches the pinned original across 41 full frames,
82 projected states and 2,624,000 pixels. Its existing controlled RNG,
normalized-input, paused-original-main and partial actor projection limits
remain unchanged. Representative original/replay pairs and actual-App captures
were inspected, including eliminated halves and centred survivor frames.

## Remaining Limits

The original producer seeds the death state and timer, supplies a declared
near-call stack argument, and transfers between explicit original blocks.
The App test executes the real 60-tick helper, but does not establish a natural
moving/death route. Repeated R keys are reinjected before each original handler;
original keyboard queuing, phase and host typematic timing are not proved.

Next-level original evidence covers geometry/frame and gradient/latch blocks,
not the complete decoder/startup or city RNG generation. Palette I/O is
explicitly excluded and RGB comparison uses the existing normalized palette.
Original eliminated visual X=10000 is observed, but the complete collision/
visual parking ownership is not recovered or compared by the App test.

Original elimination also adds six to DS:78CC. That observation is not a claim
that full App cadence/owner-bus integration is recovered. Natural interrupt
delivery, IRQ1, sound waveform parity, campaign-wide synchronization and owner
visual acceptance remain incomplete. No whole-game fidelity claim is made.
