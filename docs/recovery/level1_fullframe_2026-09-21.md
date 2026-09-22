# Level 1 production presentation and original full-frame recovery

Baseline: main after PR #237 (`92a0cd3180ce3467f662c192d6d337c2a3b11365`).

## Recovered behavior

Fresh DOSBox observations exposed differences hidden by cropped viewport
comparisons and by post-update C++ drawing. The production governed loop and
replay now share `tickAndPresent`: active gameplay presents after the frame
counter/objective prepass and before spawning and actor updates. Menu,
introduction and paused states retain their explicit non-gameplay drawing.
This is not a one-frame offset applied by the comparison tool.

The first ordinary game start clears the reused decoding scratch buffer before
loading Level 1, rather than allowing the C++ menu-preview backdrop to supply
its tail. The original first decode has zero tail bytes; previously the port's
last map row ended with nine erroneous 176 bytes. Later level/restart buffer
reuse remains unchanged. The original initialization is independently observed,
not injected from the reference into the port.

HUD recovery adds the original nine reel offsets, decimal target selection,
8/16-byte alternating reel steps, 640-byte wrap and delayed settling marker.
Digits are drawn by contiguous reads from the original tile atlas, including
the ninth-to-zero frame that crosses the digit atlas boundary. Score changes
still originate in ordinary production gameplay.

Two-entry palette requests implement the objective-border white-to-blue fade,
including replacement, capacity rejection and settled-tail retirement order.
Initial palette entries and the initially empty ammunition well/energy track
are preserved. The active energy bar's depleted interior uses palette index 1
(blue), not the surrounding grey track. Objective destruction text follows the
30-update refresh rather than exposing new destruction immediately.

Pure reel and palette logic is in `src/core/hud.hpp`; production consumers stay
in `src/app/app.cpp`. There is no second debug-only HUD simulation.

## Original reference routes

`tests/fixtures/level1_original` contains independently captured original
bundles and `pins.json`. Each contains the unchanged input stream, compressed
lossless full frames, three raw state observations per update, the initial
64 KiB data segment, initial 60,000-byte backdrop, emulator configuration and
resident instrumentation loader. `pins.json` fixes complete file hashes and
capture source identity. The checker additionally fixes a canonical digest of
the compared observations, ordered events and full-frame hashes, excluding
runtime segment addresses and asynchronous scratch bytes.

| Route | Original updates/full frames | Compared present/post observations | Pixels |
| --- | ---: | ---: | ---: |
| `walk` | 41 | 82 | 2,624,000 |
| `bomb` | 297 | 594 | 19,008,000 |
| `objective` | 237 | 474 | 15,168,000 |
| Total | 575 | 1,150 | 36,800,000 |

Each current route matches the production replay without differing pixels or
fields in the declared projection. The objective route climbs the purple
platforms, collects the objective and remains active; it does not complete the
destruction requirement. The bomb route exercises a moving approach, a normal
bomb, explosion, terrain changes and energy loss. No route teleports the player
or modifies health, ammunition, actor identities, map cells or progress.

The compared state projection includes the active players' position, velocity,
fractional carry, animation, energy, reserve lives, selected/count inventory,
score reels, HUD palette queue, both complete map planes, objective/destruction
counts, game frame and shared RNG. Raw actor/spawner/visual bytes are retained,
but this batch does not map every actor byte to a C++ observation.

The renderer independently generates its backdrop, camera, palette, sprites,
HUD and overlays. The comparator uses every pixel of the full 320x200 RGB
frame. It does not crop, mask, translate, choose nearby frames or inject an
original backdrop/palette/state into the C++ runtime.

## Capture boundaries and provenance

Original executable SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Main-image file offsets add `0x770` to the following code offsets.

| Code offset | Preserved instruction bytes | Observation |
| --- | --- | --- |
| `77D2` | `31 c0 a3 c2 78` | New game before initialization |
| `7A13` | `80 3e e6 79 00` | Before gameplay view presentation |
| `7A57` | `c6 06 e8 79 00` | After view presentation, before actor processing |
| `8283` | `80 3e c5 79 00` | After actor/terrain/palette work, before completion branch |

The helper creates a private copy of the original files and a private Xvfb
session. It starts through real menu and introduction key events. At `77D2`
it initializes the original RNG once, accounting explicitly for the port's
390 menu-preview RNG draws. During gameplay only the ten normalized original
control-bank bytes are written in the ordered route-event sequence. This is a
controlled-seed comparison, not an uncontrolled wall-clock boot comparison.

Instrumentation lives in a separately allocated, resident 4096-byte DOS block,
not an apparently unused address inside the game's data segment. A generated
`L1ORACLE.COM` records its PSP segment and retains the allocation with DOS
INT 21h/AH=31h. Capture verifies the allocation's MCB owner and size. Each guarded
five-byte callsite uses a far call into that allocation; the trampoline saves
FLAGS/general registers, reports the caller's actual CS/DS/ES/SS/SP/BP, waits on
a monotonic stage/sequence handshake, restores registers and FLAGS, executes
the displaced instructions and returns with RETF.

The complete capture records its actual registers, resident segment/MCB,
original executable hash, capture-source hash and DOSBox executable hash.
Ghidra's analysis segment is never assumed to be the runtime segment. On exit,
the helper stops only its own child, restores and verifies the instruction
windows, and terminates that child while stopped. It does not resume a program
inside an erased trampoline. Original assets in the repository remain untouched.

A preliminary longer large-bomb capture using an earlier in-segment scratch
location failed its handshake. It was not promoted or treated as game behavior.
The resident allocation removes that unsafe scratch-placement assumption; the
41- and 297-update comparisons were repeated using the resident probes.

Original screenshots are sampled at the post-presentation hook; two identical
whole-window captures are required before accepting a frame. All frames are
losslessly stored using previous-frame XOR and zlib, with individual SHA-256
hashes. Decoding rejects oversized, short, trailing or concatenated streams.
Main code pauses while interrupts continue: this establishes the stated game
update/presentation boundaries, not uninstrumented real-time or audio timing.

## Validation and reproducibility

Existing movement, bomb, actor, palette, resource and evidence checks remain.
The first full local run found four old diagnostic assertions relying on an
immediately initialized HUD. Their fixtures now advance ordinary idle gameplay
before comparing death frames, and the seeded two-player HUD fixture advances
to the existing 30-tick refresh. Assertions remain in place; the four checks
then pass. `hud_models` directly exercises reels, fades, overflow/capacity and
retirement semantics without SDL.

`level1_original_walk`, `level1_original_bomb` and `level1_original_objective`
replay their pinned original input streams from the ordinary C++ menu and
compare full frames and state. `level1_original_guard` rejects sixteen malformed
captures, rehashed provenance changes, compressed-frame boundary violations,
unsupported UI substitution and late truncation after an earlier mismatch. A
single altered pixel at (319,199) is detected and emitted in the difference
image. The existing Level 1 replay validator accepts both its historical v1
phase contract and the explicit new pre-actor v2 contract, never mixed pairs.

Build and check pinned evidence:

```sh
ctest --test-dir build -R '^(hud_models|level1_original_.*|level1_replay)$' --output-on-failure
```

Fresh original capture and matching native replay (new output directories):

```sh
SDL_AUDIODRIVER=dummy python3 tools/level1_original.py capture --route tests/routes/level1_original_objective.route --out /tmp/lezac-original-objective --approve-procmem --approve-runtime-instrumentation
python3 tools/level1_fidelity.py record --exe build/lezac_cpp --route tests/routes/level1_original_objective.route --out /tmp/lezac-cpp-objective
python3 tools/level1_original.py compare /tmp/lezac-original-objective /tmp/lezac-cpp-objective --out /tmp/lezac-objective-diff
python3 tools/level1_original.py fingerprint /tmp/lezac-original-objective
```

Live capture requires Linux/WSL, DOSBox, Xvfb, xdotool and Pillow. Pinned fixture
replay and guards need only Python's standard library and the native runtime,
including on Windows. All child launches force dummy audio; no speaker output
or system volume changes are used.

## Remaining scope

These complete-frame matches are exact for their stated routes and controlled
conditions, not a percentage estimate for Level 1 or the whole game. Natural
objective-plus-destruction completion and the Level 2 handoff are not qualified.
A separate longer route has exposed early results entry while collapse remains
active; that recovery is not hidden by these fixtures. Whole-route death,
reentry/restart, simultaneous two-player interaction, display options, input
repeat timing and audio waveform/device output need further original evidence.

Global functional-completion and original-fidelity flags remain false.
