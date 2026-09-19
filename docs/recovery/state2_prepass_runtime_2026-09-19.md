# Original Waiting-State Prepass

## Scope

This batch compares 54 seeded original level-1 prepasses with the C++ production
prepass. It does not claim natural progression, complete VGA/HUD equality, or
whole-game completion. The game goal remains open.

Pinned evidence: `tests/fixtures/state2_prepass_original_level1.txt`.
Normalized LF SHA256:
`bf65110c9ce3621102c0b0c3681973b2665a23ade5a3735cf8ad7e48c1eb4fc5`.
Original executable SHA256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

## Capture

The original executable and shipped assets were copied to
`/tmp/lezac-state2-prepass-both-20260919`. The checked-in capture helper uses a
private Xvfb display, explicitly sets `SDL_AUDIODRIVER=dummy`, and starts an
owned DOSBox debugger child through the existing level seeder:

```sh
env SDL_AUDIODRIVER=dummy PYTHONUNBUFFERED=1 \
  python3 tools/capture_original_state2_prepass.py \
  --run-dir /tmp/lezac-state2-prepass-both-20260919 \
  --out build-codex-tmp/state2-prepass-both-original-20260919.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The helper verifies the EXE hash, static/runtime instruction windows, and an
unused 0x212-byte instrumentation arena. It installs two temporary hooks and
restores them before returning. The observed stage boundaries are:

| Boundary | Ghidra Anchor | Runtime CS:Offset | EXE File Offset |
| --- | --- | --- | --- |
| Before P1/P2 prepass | 1000:7C3D | 01A2:7C3D | 83AD |
| After P1/P2 prepass | 1000:7EBB | 01A2:7EBB | 862B |

The existing process-memory helper's base convention uses CS 01ED / DS 0C8F;
captured CPU registers are CS 01A2, DS 0C44, SS 18B3, SP 3FE4, BP 3FFE.
ES is 0C44 after actor/visual accesses or 3EA9 after the final map read.
SP/BP are recorded inside the temporary trampoline. Every case records the
six registers. The map is 60x33. The far pointer DS:C1E0 aliases the object
plane addressed by DS:C1FE in this run; the helper checks that alias before
writing the two probe cells.

Each case seeds one player and leaves the other global player state inactive.
P1/P2 actor addresses are DS:1B88/1BAE, visuals C21E/C226, inventory 1B6C/1B70,
state bytes 79E6/79E7 and reserves 79EA/79EB. Both fire latches are seeded with
the requested key value. The shared gate is DS:79CA and fallback byte 79B9.
The actor's animation/backup fields are retained from the loaded original
player template; this is deliberately a boundary probe rather than a natural
death animation. Each observation is made before the non-player actor pass.

## Recovered Rules

- The raw countdown decrements as a 16-bit word even during waiting. Zero
  wraps to FFFF; FFF0 becomes FFEF. A raw countdown of two remains dying after
  one pass: no placement, inventory restoration or fire return occurs yet.
- On expiry, reserve 1 becomes 0, the start marker is restored, the idle byte
  is zeroed, and the waiting descriptor pointer becomes entry 39. P1 starts
  at (104,168); P2 at (280,168) in level 1.
- Inventory bytes 0..2 are raised to minima 100, 10 and 2 at expiry only.
  Above-minimum values and the fourth byte remain unchanged. The production
  unit check also keeps the selected weapon unchanged.
- The scan index is `(((uint16(y+7)>>3)+1)*width+(x>>3)) mod 65536`.
  A left tile in 1..76 decrements Y without a lower-bound test. Otherwise a
  right tile in 1..76 decrements Y only when unsigned Y > 24. Open and 77+
  cells do not move the waiting visual. Y=0 under a left solid wraps to FFFF.
- Placement runs before fire handling but is not a fire predicate. A solid
  cell and a permitted key return the actor to behavior 0 (P1) or 1 (P2),
  set global state 1, set energy 100, and clear both hardware fire latches.
- A closed gate prevents return and writes fallback 229 while retaining the
  hardware key bytes. On expiry it also sets both descriptor dimensions to
  one, without replacing the waiting sprite pointer.
- A gate of one still permits return when the seeded object plane contains
  no objective tiles. The prepass consumes a latch, not a fresh map count.

Static evidence supplies the latch's lifetime: EXE 327A initializes DS:79CA
to one; the death helper at 1000:30A3 counts remaining objective tiles, adds
the collected count, compares the required total, then writes that same byte
at EXE 385A/3861. The prepass only reads it at EXE 850E/853A. The shared C++
gate is reset on level initialization and written on either player's death.
Production unit coverage changes the objective map after death in both
directions and checks that waiting does not recompute the gate.

## Production Mapping and Validation

`updatePlayerReentryPrepass` is called by ordinary `updateWithControls` and by
the new fixture replay. `updateReentry` applies expiry inventory/descriptor
updates and calls `updateWaitingPlayerPlacement`; `tryReenterPlayer` consumes
the shared gate. The 1x1 descriptor is retained in `Player::singlePixelSprite`
and cleared only when gameplay selects a new descriptor. Its renderer consumes
the first sprite byte with normal transparency.

The replay checks selected-player motion, fractions, idle/drop/countdown,
behavior, animation/backup, energy, visual descriptor, inventory, both global
states, reserve, gate, shared counter and both fire latches. Opaque actor bytes
are required to remain equal to the seed, not claimed as newly recovered
fields. The fixture guard pins the trace hash, checks LF/CRLF, and rejects 206
mutations across states, descriptors, registers, inventory and record structure.

The previous standalone placement model moved through empty cells and treated
solid placement as a fire blocker; both conclusions are contradicted by the
original probe. Its replacement calls the production placement helper. The
old return model's invented effect/placement readiness predicates are removed;
the replacement uses actual death, countdown and reentry helpers.

Validation entry points:

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-state2-prepass-original \
  tests/fixtures/state2_prepass_original_level1.txt
python3 tools/check_state2_prepass_fixture.py --exe ./build/lezac_cpp
python3 tools/capture_original_state2_prepass.py --self-check
```

The independent level-7 fire trace from the prior batch also passed after
these changes: 140 updates, 16 normalized 312x152 views, 758,784 pixels,
zero differences. Original and current C++ frame 101 were inspected at 3x
nearest-neighbor scale and compared with ImageMagick AE=0. The original trace
is `build-codex-tmp/boss-fire-reentry-promoted-cli-v2.txt`, SHA256
`ee5bd792500f3b2edacc46e6a94b0c28c29b0a80e0ed0ffa6df05643637f8722`.
Current replay images are in `build-codex-tmp/state2-prepass-boss-fire-cpp`.
That regression image is not a screenshot of each newly seeded level-1 case.

An independent rerun with the finalized helper also completed and replayed
all 54 cases on both Windows and Linux. It starts from original idle byte 86
instead of the pinned capture's 85 and preserves/resets it at the same
boundaries. Output: `build-codex-tmp/state2-prepass-verify-original-20260919.txt`,
SHA256 `808f0812961172c864ad3f792dc96e93c36ca1aa42126b64ce9cdf3356dc18ad`.
The full Linux suite passed 520/520 tests in 397.02 seconds, including the
windowed Xvfb route. Windows passed the original replay, 206-mutation guard,
and focused death/reentry checks before the full-suite delivery run.

## Remaining Work

The new capture does not exercise two simultaneously waiting original players,
a naturally latched key held before death, an entire 65536-update wait, or
arbitrary reads beyond the allocated map plane. The C++ out-of-plane scan
currently returns zero rather than emulating adjacent DOS memory. Per-probe
original render-boundary images, especially the 1x1 descriptor, remain a
separate visual verification task. Natural full-health boss victory, complete
campaign progression, broader original input semantics and full VGA/HUD
comparison are still required for the complete-game goal.
