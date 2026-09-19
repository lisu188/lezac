# Two-Player Keyboard Ownership

## Original Observation

The original two-player game assigns Z/X/M/N/C to player 1 and
Left/Right/Up/Insert/Down to player 2. The recovered help screen already
lists these controls. The C++ host keyboard adapter had movement and jump
ownership reversed in two-player mode, despite its fire keys being correct.

`tools/capture_original_key_ownership.py` observes real X key make/break
events through the original keyboard ISR and player normalization. It starts
two players through the menu, clears only their eight ammunition bytes to
prevent explosions, and does not seed input, player identity, position, or
velocity. The 21 single-key/chord cases have make and release phases, each
observed for both players: 84 samples over 42 consecutive gameplay frames.

The run uses a temporary copy, private Xvfb, and `SDL_AUDIODRIVER=dummy`.
The helper checks the EXE hash, static/runtime code windows and unused
instrumentation space, then restores the hooks and inventories on exit.

Original EXE SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The executable image starts at file offset `0770`.
Hooks at Ghidra `1000:616E` and `1000:6245` bracket normalization;
the observed runtime locations are `01A2:616E` and `01A2:6245`.
Every recorded post-normalization register set is CS=`01A2`, DS/ES=`0C44`,
SS=`18B3`, SP=`3FA2`, BP=`3FEE`. SP is observed after the trampoline's
PUSHF/PUSHA; these are not claimed as the uninstrumented entry registers.

The original copies `DS:1B78..1B7C` at `1000:6175` for behavior 0,
and `DS:1B7D..1B81` at `1000:61DE` for behavior 1. The common destination
`DS:1B82..1B86` is ordered jump, left, right, fire, down. The local player
identity at `SS:BP-1D` becomes 1 or 2. Hardware snapshots, normalized bytes,
38-byte actor records, 8-byte visual descriptors and registers are preserved
in `tests/fixtures/key_ownership_original_level1.txt`.

Fixture SHA-256 with normalized LF line endings:
`27fbe55858af359ddc8c4f8c01cbeaf9cd45b1ea4589c940b2aeb0b47a866ab4`.

Capture command, after copying the original shipped assets into the fresh
temporary run directory:

```sh
env SDL_AUDIODRIVER=dummy PYTHONUNBUFFERED=1 \
  python3 tools/capture_original_key_ownership.py \
  --run-dir /tmp/lezac-key-ownership-20260919 \
  --out build-codex-tmp/key-ownership-original-20260919.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The wrapper starts `seed_original_level.py` with target level 1, start key 2,
startup/intro/level-start waits of 10/8/5 seconds, and runtime state dumps.
The level was reached naturally from the two-player menu selection; no level
transition was seeded. Each case releases all ten keys, makes its specified
key/chord, checks the IRQ hardware bank, samples both normalizers, releases
all keys, and samples both normalizers again. Trampolines pause the main
routine while interrupts/input continue, so this is input ownership evidence,
not evidence for uninstrumented wall-clock input timing.

## Production Mapping And Tests

`controlsFromKeyboard` is the adapter called by the actual `update` path.
It now maps Z/X/M/C to P1 and arrows to P2. Single-player arrow convenience
aliases are preserved and tested separately, not attributed to the original.
Fire remains event-latched and consumed by the recovered active-fire/reentry
logic; it is not reconstructed from held SDL keyboard state.

`--debug-key-ownership-original` verifies provenance, case/order/frame
continuity, actual player identities and all normalized samples. It compares
the production adapter plus event-driven fire latches with the original
bytes and runs each of the 42 frames through production gameplay updates.
Only the original normalized input is compared here; the captured original
actor poses are retained as evidence, not asserted equal to C++ poses.
The fixture guard checks LF/CRLF and rejects 114 malformed/changed inputs.

`tools/test_key_ownership_xdotool.py` additionally drives a real SDL window
under private Xvfb. Its diagnostic calls `runInteractive`, which uses the
same governed loop, event handler, keyboard adapter and `update` as normal
play. Four isolated left/right cases, one opposing-player chord and two
isolated jumps verify seven actual movement cases. The other player must
remain stationary on the checked axis. No player/actor positions are seeded.
The helper checks the active audio driver is `dummy`, inspects nonblank
frames, writes a state trace, and terminates the owned child on failures.

```sh
env SDL_AUDIODRIVER=dummy xvfb-run -a \
  python3 tools/test_key_ownership_xdotool.py --exe build/lezac_cpp \
  --out build-codex-tmp/key-ownership-live-20260919
```

The first live run passed all seven cases and exited normally after 221
logic ticks. Its `opposed.ppm` checkpoint was inspected and shown alongside
the original post-probe PNG. Both are full 320x200 frames, but their times,
positions, inventory, score and camera offsets differ. This is not a
frame-aligned or pixel-parity claim.

## Validation Results

- Windows Release: 525/525 CTests passed in 590.53 seconds.
- Linux: 527/527 CTests passed in 362.05 seconds, including live X input.
- The branch was then rebased onto PR #234's source-guardrail changes.
  Game source, the new helpers and the captured fixture were unchanged.
  All affected/new checks passed again: Windows 27/27 and Linux 28/28.
  This includes the added source-guardrail self-test and another live input
  run. The complete long suites were not repeated after this tools-only
  upstream update.
- Both the pinned and independent level-7 fire/reentry traces still match
  140 states and 16 normalized views each (758,784 pixels, zero differences).
  The independent checkpoint `boss-fire-fresh-original-101.png` matches
  `key-ownership-boss-verify-101.png` exactly after equal 3x nearest-neighbor
  enlargement. These images exclude the HUD and outer VGA frame.
- All game/capture/test launches and child processes used dummy audio.

Logs are retained under `build-codex-tmp/key-ownership-{windows,linux}-full.log`
and `build-codex-tmp/key-ownership-{windows,linux}-rebase.log`.

## Remaining Scope

This fixes an interactive input ownership error that direct `FrameControls`
autoplayers could not expose. It does not prove host/DOS typematic timing,
held-before-death semantics, all simultaneous-key cases, full-health natural
boss victory, natural campaign completion or whole-game fidelity.
