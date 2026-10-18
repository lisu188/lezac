# Original Per-Player Render Caller

## Recovered Boundary

`FrameRenderOperation` executes the original `game:7A13..7A57` caller and its
camera, world-raster and VGA-copy callees on one `TimerIrqBus`. It composes the
operations recovered in #421, #422 and #423. The integration branch retains the
camera and copy commits as ancestors rather than replacing them with copies.

All eighteen caller instructions are preserved. `DS:79E6/79E7 == 0` skips the
entire corresponding view; every nonzero state enters the camera, raster and
copy calls, including waiting state 2 and byte 255. Coordinates come from the
first two visual records. Near Pascal argument cleanup and far-call stack
pushes retain their original order. Each view's destination, `DS:79F0/79F2`, is
written to `DS:C1F4` after rasterization and immediately before its VGA copy.
Both views share memory, including camera scratch and the offscreen buffer.

Snapshots retain the active callee, complete registers, dispatch and transfer
counts, and the running/returned/runtime-error outcome. A zero budget dispatches
nothing; completed operations do not mutate again. Camera stack-check failures
stop at the original CRT error entry `0920:00E2`, before executing that handler.

Dispatch and REP grants are resumability controls, not CPU work-clock credits.
Unicorn reports an additional zero-CX code callback after a nonempty REP. The
oracle records these observed callbacks separately, and the single-word replay
compares its dispatch count with that explicit adjustment. This does not alter
memory, register, flag or transfer expectations and does not establish native
instruction-cost timing.

## Original Evidence

The producer executes unchanged relocated original code with Unicorn 2.1.4.
The actual mapped library is verified as SHA256
`ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c`.
The repository's hash-pinned wheel requirements are used. All original code
bytes remain unchanged before and after execution; no callees are stubbed.
Interrupts and port I/O are rejected, not supplied with recorded responses.

The 26 controlled profiles include:

- Four full-width state cases and the complete split-view cross product of
  states 0, 1, 2 and 255.
- Backdrop modes 0, 1, 2 and 255, both direction-flag states, negative and extreme
  signed coordinates, camera clamps, and odd/wrapping buffer offsets.
- Stack-check error exits for each player's camera.

Inputs use real tile and sprite pixels, with explicitly generated map, backdrop,
heap layout, descriptors and initial VGA data. The raw sprite bank contains 91
frames; this corpus selects the same thirteen distinct frames cycled by the
22 controlled descriptors as the raster inputs. It is not a natural campaign
capture or proof that all sprite frames are drawn.

Every profile has a completely unobserved control run with neither code nor
write hooks. Complete 1 MiB memory and all endpoint registers/flags match the
observed run. The observed corpus covers 524 instruction addresses, including
all eighteen caller instructions, and records 2,111,436 ordered write events.

Frozen projection:

- Raw bytes: 14,783,106; gzip bytes: 4,503,189.
- Projection SHA256: `24a7be8639b3fabc5958945bc85842242ec4db10cc8da30512e87d383df4e2ea`.
- Manifest SHA256: `bfa8b74cf80e4932f3ca5ffff257919a6772cca8a7ac7043a9927de034d5f5c9`.
- EXE SHA256: `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

Only the compact generated write projection and manifest are versioned. No full
RAM images or PNG captures are published. The checker authenticates the four
canonical assets, four producer/input sources, manifest and compressed/decoded
projection before exporting. Frozen bytes are protected from Git EOL conversion;
the cold-checkout test includes this fourth fixture family.

## Validation

- 78 C++ replays use instruction/REP-word grants `(1,1)`, `(17,3)` and
  `(4096,65535)`, rebuilding from snapshots after every grant. All 6,334,308
  write events match in address, width, value and order, with identical endpoint
  registers/flags, transfer counts and six replayed runtime-error outcomes.
- Quick full-memory fingerprints are checked for every replay. Separately,
  SHA256 of all 26 initial and 26 final complete memory dumps from the wide-grant
  replay matches the original producer: 52 images, 54,525,952 bytes. Dump files
  remain RAM-only and are not fixtures. Other grants have the same exact write
  trace and deterministic initial backing.
- Strict GCC C++23 and native MSVC `c++latest /W4 /WX` builds pass. ASan and UBSan
  pass the unit and entire original-backed replay corpus.
- 21 focused CTests pass across the caller, camera, raster, copy and cold-checkout
  families. The source guardrail self-test passes 19 controls with 134 mapped
  sources. The full Linux App build passes; production App code is unchanged by
  this component. That build retains an existing diagnostic `snprintf` warning;
  the new operation and replay test pass their separate strict-warning builds.
- Four independently compiled faults are detected: state-1-only gating, wrong
  second-view destination, missing late destination store and wrong camera
  argument. Original sources remain unchanged. Mutation reruns retain prior logs.
- 81 fixture rejection controls cover changed/deleted/renamed/unreadable assets,
  sources and frozen files, with new or existing exports, plus a foreign existing
  export. Failure reports and existing bytes are preserved. These also pass under
  native Windows Python. Native Windows Git cold checkout passes all four family
  controls, including deliberate CRLF failures when protection rules are removed.

Fresh original/C++ images from controlled split case 9 were inspected with the
canonical VGA palette. All 64,000 indices match. Patterned retained areas are
intentional initial VGA, not a display defect or a natural gameplay screenshot.

## Remaining Integration

This completes the bounded render caller, not the game. `FrameForegroundOperation`
still ends at `7A13`. The new caller is not yet connected to the production App
renderer, live allocation/actor tables or instruction-work scheduler. App still
uses the existing semantic renderer and fixed host accumulator.

Next work must compose foreground through rendering on the owner bus, account
for legal IRQ boundaries and REP interruption, wire actual resource allocations,
and validate natural full frames with palette and sound/device timing. Campaign
coverage, narrowed-view acceptance, sustained play and whole-game fidelity remain
separate requirements. All whole-frame, natural-capture and work-clock claims in
this fixture remain false. Undefined intermediate flags retain the component
conventions; no new per-instruction equivalence claim is made for them.

All new builds, diagnostics and images stayed in WSL RAM under the approved
disk-pressure constraint. Games and child processes used dummy audio. The dirty
canonical checkout, original assets and local `AGENTS.md` were not changed.
