# Original Viewport Ownership

## Production Correction

The original main caller `7A13..7A57` gates each player's camera, world drawing
and presentation calls on its global state byte (`DS:79E6/79E7`). Zero skips
that entire view. Every nonzero value, including waiting state 2 and byte 255,
enters the camera (`3587`), driver draw (`08AC:00F4`) and presentation
(`08AC:03C8`) calls. The old App renderer instead cleared and repainted both
views on every draw, even after one player was out.

`PlayerRenderView` now carries the real App state byte. Production projection
uses `originalPlayerState`, not an inference from the rendering dead flag.
`WorldPainter` clears/draws only active views. An inactive view retains its
pixel indices and ownership; palette-owned RGB pixels are refreshed against
the current palette without rerunning its camera, world or sprite drawing.
View-frame pixels now retain their original palette indices too.

Preserving a view also requires correct initialization. Original callsite
`2C7A..2C89` clears all VGA pixels after the intro. Callsite `2CF6..2CF9` runs
frame initializer `2959`, even when player state is already zero. Its interior
is NOT black: it fills player 1's frame with index 28 (grey), and player 2's
with index 12 (light red), bounded by indices 15/4. Active world presentation
later overwrites the interior, leaving three inset rows/columns visible.

`GameRenderer::initializePlayfield` now performs that explicit initialization
from `finishLevelIntro`, before backdrop generation and gameplay presentation.
Thus an already-out player on the next level retains the initialized frame,
not the previous level or intro text. Per-frame gates still preserve the
caller's prior view; there is no draw-then-restore or reference-image overlay.

## Unchanged Original Execution

`tools/render_view_gate_oracle.py` executes the unchanged shipped code in
Unicorn 2.1.4 using an authenticated natural gameplay RAM sample as backing.
The snapshot and exact capture recipe are bound to the previously published
`foreground_live` fixture. Original code relocation is verified against the
canonical EXE, with 43,552 code bytes unchanged before and after each run.

Twenty controlled gate cases cover four single-player states and the complete
two-player cross product of 0, 1, 2 and 255. The producer explicitly sets
geometry, state bytes and patterned initial VGA data. The source's backing
allocation is retained for controlled split geometry; this is not evidence
of a natural two-player heap initialization. Original camera/draw/present
callees run without stubs or instruction patches. Interrupts and all I/O are
rejected rather than supplied with recorded responses. Continuous IRQ timing
is not modeled by these controlled executions.

Two additional controlled cases execute the original clear and initialization
callsites as separate bounded blocks. Only IP is moved between those declared
blocks; this is not continuous intro execution. Both one- and two-player
configurations begin with zero state bytes. All observed/unobserved runs have
identical complete memory and registers, including final flags. The gate
corpus retains endpoint registers, call order/return addresses, write counts
and full initial/final VGA bytes. Unicorn step counts are not DOSBox work-clock
credits or proof of native instruction-cost integration.

An initial exploratory run set the wrong pitch fields and allowed a full-width
copy to cross the controlled half views. It was not promoted. The corrected
producer authenticates the geometry through actual write counts: 23,104 bytes
per active split view, zero for an inactive one; 47,424 bytes for a full view.
Both exploratory runs and their diagnostics are retained locally.

Frozen fixture data:

- Gate projection: 2,561,856 bytes, compressed 69,699 bytes.
- Gate SHA256: `7f59047942265c02406485ff426662a1997ad99a9e6225c0cf48aa96cae57473`.
- Initialization projection: 128,014 bytes, compressed 535 bytes.
- Initialization SHA256: `6c7c4f9bb7b4b256a403fc5e450f73209eda0d8ff53538d1f656e1708b577de0`.
- Manifest SHA256: `89f2c5ca2672e686fd37fa58dc6cf43bd0b4a10509cd04b501b503b72cd9da4f`.
- EXE SHA256: `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

The checker authenticates both endpoint files, both new producer modules, all
inherited capture sources/files and all fourteen canonical shipped assets
before exporting either projection. Two Python methods include 36 changed,
missing and new/existing-output controls; matching output is reused without
rewriting. Full RAM and PNG captures are not published or required by CI.

## Validation

The actual `GameRenderer`, immutable `AssetCatalog`, `PresentationState`,
`TextRenderer` and `Canvas` are used, not a formatter/gate surrogate.

- Twenty gate cases, two physically representable VGA palette modes, 512,000
  retained-pixel comparisons and 54 active-view repaint controls pass.
- Two initialization cases in two palette modes compare all 256,000 pixels,
  RGB values and index ownership, with no differences.
- The baseline produced 511,462 RGB and 511,646 ownership differences in the
  first version of the gate probe, before the palette-mode refinement.
- The actual App's six-phase diagnostic exercises the ordinary state projection,
  one out player with a moving survivor, palette updates, both out, waiting
  state 2 and a next-level initialization with player 1 already out.
- Full Linux App builds. The initial 92 focused checks pass; the final lifecycle
  follow-up passes 29 affected checks, including seven existing original-render
  fixtures, HUD, palette, two-player death/progression and completion behavior.
  Unchanged clock/IRQ component evidence is reused, not relabeled as new work.
- The pinned original walk route is rerun on the final App: 41 full frames,
  82 state observations and 2,624,000 RGB pixels match with zero differences.
- Native MSVC 14.44.35207 uses C++latest: production renderer at `/W4`, both
  new tests at `/W4 /WX`. Both corpora and two Python methods pass. Native and
  Linux final view dumps are byte-identical. Existing production warnings remain.
  A wrapper initially compared with a superseded Linux dump; the corrected
  comparison is separately recorded without changing compiled code or targets.
- Five isolated faults are detected: global clearing, stale palette RGB,
  rendering only state 1, ignoring the actual App state projection, and omitting
  next-level initialization. Source files remain unchanged by these controls.

Fresh screenshots are actual App diagnostic frames. The patterned comparison
is deliberately controlled initial VGA: original retention on the left,
production renderer on the right. Active-world pixels in that gate corpus
are not compared against the original, which has different explicit backing
inputs. No natural last-life route, full active-frame parity, instruction-work
scheduler, IRQ-during-render, sound waveform or whole-game claim is made.

The governed loop remains a fixed host accumulator, and the recovered
`FrameForegroundOperation` still returns at `7A13`. Full cadence/owner-bus
integration, remaining render instruction recovery, natural IRQ1/sound,
narrowed viewport parity and campaign-wide visual acceptance remain open.

## Storage

Local validation and captures stay in owned RAM while Windows C: is above the
90% guard. One inactive generated `pacing-device-clock.bin` was authenticated
by reconstructing it from the frozen compressed fixtures, checked for active
users and removed. Its 53,737,258 logical bytes reclaimed 53,735,424 tmpfs bytes.
All raw evidence, source fixtures, manifests, logs, binaries and source remain.
The cleanup receipt records the exact hash and restoration command; future
clock tests must reconstruct this derived input and forecast their reserve.
