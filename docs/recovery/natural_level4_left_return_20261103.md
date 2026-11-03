# Original Level 4 Left Return

The original game completes the ordinary-input Small/Medium escape and returns
across the upper bridge to the far-left side. This is an alternate continuation
from the previously verified tick-13040 bridge anchor, not an extension of the
different tick-13800 right-side escape route.

The original-only reference covers every frame from C++ tick 13040 through
14800 inclusive: 1,761 complete 320x200 RGB frames and 3,522 present/post-update
observations. The native frame offset remains 1623. Level 1 menu startup, the
three result/intro handoffs, initial RNG control and normalized ordinary control
bank inputs are retained. No terrain, inventory, health, player-position or
progress state was injected.

At tick 14800 the original player is at `[13,344]`, stationary, with six energy,
zero reserve lives, inventory `[198,3,0,0,1]`, score 51890, and RNG 363217051.
The destruction count remains 261 of the 305-cell threshold. Forty-four more
cells are needed; this does not establish level-four completion or level-five
entry.

## Evidence and Storage

The unchanged 52,384-byte executable has SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Actual DOSBox executable, launch arguments, working directory, window geometry,
configuration, loader, canonical assets and silent audio environment were bound
to the live process. The owned guest closed and all observation hooks were
restored. This is not physical-keyboard or wall-clock acceptance.

To retain the entire interval within the current RAM reserve, the observer
writes losslessly compressed DS snapshots and boundary JSON records directly.
Each member is decoded and compared with its complete pre-compression bytes
before its readback receipt is emitted. The packer independently rechecks all
7,056 members, including the earlier transition/entry checkpoints, and
independently re-decodes all 3,522 new DS boundaries. PNG fingerprints must match
the live observer's receipt. The reader reconstructs each boundary record and
checks its complete original byte length and SHA-256 against the storage log.

Raw DS snapshots remain RAM-only, even in compressed form, and are not claimed
durably retained or published. The committed reference contains projected
observations and RGB fingerprints, not raw DS or full guest RAM. Tile/word heap
planes and palette remain outside the independent DS-only re-decode; their
observed projections and full RGB frames are compared separately.

Six actual storage-helper tests cover full-byte round trips, existing-output
preservation, path escape, reserve exhaustion, bad decoding and failed readback.
Ten fixture/parser test methods include altered reference/phase/sequence data,
live/storage receipt mutations, recipe/scope changes, pinned-byte corruption,
synthetic parser controls and failed/timed-out child report preservation.
Two C++ records are mutation stimuli only; 28 typed changes are rejected without
rewriting the original-only expected bytes.

## REA and Limits

Fresh REA 6.7.0 with Ghidra 12.1.4 on WSL decoded sixteen selected original
instructions in `1000:6F90..7011`, including the signed flame-byte loads and
three-bit shifts supplying player X/Y impulses. Both selected direct calls
resolved, every instruction's bytes matched the unchanged MZ image, and the
REA server/session closed successfully. Advisory decompilation is not the
runtime oracle.

The regression compares the declared mapped/lifecycle/monster/marker/terrain
projection and complete RGB output. It does not claim every actor field, an
uninstrumented original session, whole-game fidelity, or clearance of the held
actor-pass stability findings. All captures and replays are silent.

The three CTests are `natural_level4_left_return_original`,
`natural_level4_left_return_guard`, and `natural_level4_left_return_fixture`.
The Python 3.12/3.15 Linux/Windows compatibility matrix includes the new fixture
suite. Full local C++ comparison uses bounded, nonoverlapping replay windows
with identical ordinary-input prefixes and authenticated original expectations;
this controls RAM usage without omitting any frame in the reference interval.

## Local Validation

- The pinned GCC 13.3 C++23 App matches all 1,761 frames, 3,522 projected
  boundaries and 112,704,000 pixels with zero differences. Fifteen bounded
  captures replay the complete ordinary-input history from startup and cover
  the interval without overlaps or gaps.
- The pinned native MSVC App separately matches the final 81 frames and 162
  boundaries, totaling 5,184,000 pixels. Its actual loaded SDL2.dll path and
  SHA-256 were observed in the live Windows process. This Windows lane does
  not claim observation of the preceding 1,680 frames.
- Ten new fixture/parser test methods pass on Linux Python 3.12. The new suite
  plus adjacent bridge and collapse suites pass 37 tests on each of actual
  native Windows Python 3.12.14 and 3.15.2.
- A fresh CMake/Ninja configuration and seven focused CTests pass. The
  single-launch full-window CTest is wired for CI; locally, the equivalent
  complete interval was validated using the bounded captures above because
  its uncompressed single-run artifacts would exceed the task's RAM reserve.

No C++ source or gameplay behavior changes in this delivery. The validated
C++ source tree is `8d059cdd61dce9a9af207cb7e07c879d6f843a84`. Hosted checks
remain a separate validation lane and are not inferred from these local results.
