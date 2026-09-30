# Physical held-fire observation

Baseline: main after PR #244 (`a20315b2b2ec0e574e9265c2eef11bb535210278`).
Scope: real host key input and one natural level-1 death/reentry lifecycle.
This report is not frame-aligned C++ parity or whole-game completion evidence.

## Original recorder

`tools/capture_original_held_fire.py` uses a private Xvfb display, dummy audio
and a temporary unchanged copy of the pinned LEZAC.EXE. A DOS-owned 4,096-byte
resident allocation holds 16 records of 128 bytes. Guarded hooks at main-CS
`10A1` and `7A57` observe fire-key make/break IRQs and each natural update.
No gameplay or input bytes are seeded, and the main loop never waits for the
observer. IRQs are briefly masked only while writing one coherent record.

The observer checks sequence tags twice and rejects torn reads, overruns and
frame regression. It restores every attempted hook, including partial writes,
verifies original bytes, attempts both restorations even after one fails, and
resumes the owned process. The IRQ stub repairs its far return address past
the complete displaced instruction window, including during hook restoration.
Resident stubs are not erased while they might still be executing.

Completion is written only after input acknowledgment, 24 post-reentry updates,
both restorations, post-observation work and owned DOSBox process exit. Failed
or partial runs remain failed. The strict standalone checker and 16 unit tests
cover provenance, natural lifecycle, input ordering, cleanup failures,
counter/ring corruption, completion timing and forced silent child launches.

## Pinned original observations

The 2026-09-26 original traces are retained unchanged under
`tests/fixtures/held_fire_original`. Their canonical LF text hashes are:

- `hold_through.txt`:
  `68b663810727d37f1e86390cc13bb7c8bc0ba15358bda462e2c5ce02506a04df`.
- `release_repress.txt`:
  `d52c1641f72c91cc634ee4997ba78d62bf5ac282d4005c56b31e93ced470ffb9`.

Both headers record capture-source SHA-256
`1e40341e517d7b4aeee5942678dc19b72e0fe47aab30652a3327831baf63a737`,
the original executable, DOSBox, IRQ/frame stubs and resident allocation.

| Mode | Samples | Dying | Waiting | Resumed | Make IRQs | Break IRQs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Held through death | 388 | 304 | none | 364 | 337 | 1 |
| Release, then repress | 522 | 426 | 486 | 498 | 398 | 2 |

Both observe the 60-update death countdown and reserve bytes changing from
2 to 1 without a fallback restart or level change. Release/repress also proves
that fire and make IRQs remain absent through the released waiting interval,
then a new physical make triggers reentry. Final key-up is acknowledged in
both runs. The validator checks these observations rather than accepting a
successful process exit alone.

Preview images read the original 312x152 view buffer without a screenshot
hotkey. They use the shipped normalized palette and are explicitly not
frame-aligned. Raw captures and restoration receipts are preserved separately
from previews; `pins.json` keeps whole-game and frame-alignment claims false.

## C++ production-input harness

`--debug-held-fire-live` adds read-only event/update observers to the actual
SDL interactive loop. It records every governed update, including catch-up
updates, and writes active/dying/waiting/resumed 320x200 checkpoints. The
90-second diagnostic starts through the normal menu/intro without gameplay
seeding. Observer callbacks are cleared on success and exception.

`tools/test_held_fire_xdotool.py` drives physical XTEST input on a private
display and validates observed event acknowledgments, consecutive updates,
countdown, reserve lives, release/repress, final key-up and no restart. It
checks nonblank rendered checkpoints and clean child exit before publishing
a result. Errors retain an incomplete result and do not become parity claims.

The retained release/repress run at
`build-codex-tmp/held-fire-cpp-release-clock-v3-20260926` contains 526 samples:
dying 431, waiting 491 and resumed 502, with 322 SDL makes and 2 breaks.
Its 60-update countdown and lifecycle semantics match the original observation.
The start press is scheduled from the original frame-clock anchor, not the
observer's first captured sequence. The trajectories and pixels are not aligned.

## Unresolved held-through run

The retained earlier C++ run at
`build-codex-tmp/held-fire-cpp-hold-v3-20260926` reaches death at sequence 242
with the objective gate closed, then returns to the level intro after sequence
301 (the last recorded countdown is 1). It is not a successful
reentry observation. A mounted-filesystem attempt also encountered an I/O
error; its partial data is not promoted. Those original failure artifacts
remain preserved. The current harness fails immediately on a closed gate.

The separate identical normalized rapid-fire replay now matches all 297
original frames and projected states after fixing ammunition HUD timing.
That result does not explain the physical-input route failure or prove
host-typematic parity. Natural RNG/timing and objective reachability remain
the next investigation frontier; no gameplay gate is forced open to obtain
a passing capture. The live harness is deliberately not a required passing
CTest until the held-through physical case is established.

## Repeatable checks

These checks do not launch a game and passed on 2026-09-30:

```sh
env SDL_AUDIODRIVER=dummy python3 -B tools/capture_original_held_fire.py --self-check
env SDL_AUDIODRIVER=dummy python3 -B tools/test_held_fire_capture.py
env SDL_AUDIODRIVER=dummy python3 -B tools/check_held_fire_capture.py tests/fixtures/held_fire_original/hold_through.txt
env SDL_AUDIODRIVER=dummy python3 -B tools/check_held_fire_capture.py tests/fixtures/held_fire_original/release_repress.txt
```

New live captures additionally require a fresh output, a guarded temporary
run directory and both existing process-memory/runtime-instrumentation flags.
All launches, including seeder and nested children, force dummy audio.
No system volume settings are changed.
