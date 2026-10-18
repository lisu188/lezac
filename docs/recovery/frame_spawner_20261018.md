# Resumable Post-Render Spawner Caller

## Recovered Execution

`FrameSpawnerOperation` executes original game `7A57..7C3D`: the four per-frame
byte resets, physical spawner iteration, actor allocator, visual construction,
four Random calls and animation initialization. It preserves the original
stack, registers, byte/word aliases and write order on a caller-owned bus.
Its snapshot contains CPU execution state, not copies of actor/spawner banks.
It stops before the waiting-player prepass at `7C3D`.

The operation includes the reached original code in game `2F9F`, game `06AB`,
graphics `08AC:0517`, runtime `0920:04DF`, and runtime `0920:13A8/13F7`.
Those calls are not semantic stubs or fixed work estimates. The allocator's
nonzero-velocity clamp branches are implemented but not reached by this caller,
which pushes zero velocities; this corpus does not prove those unused branches.

## Original Evidence

The oracle MZ-relocates the unchanged shipped executable, SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`, and
verifies the actual mapped Unicorn 2.1.4 library. No instruction patches, call
stubs, delivered interrupts or hardware I/O are permitted. Controlled inputs
include salted opaque actor/visual/stack bytes and synthetic descriptors;
they are not natural gameplay states or original RAM captures.

Two independently generated finalized corpora have identical manifests and
compressed bytes. For each case, execution without instruction/write observation
hooks matches the observed execution across all 1 MiB of memory and all final
registers. The ordered write log independently reconstructs that complete final
memory. All 43,552 relocated code bytes remain unchanged.

| Check | Result |
| --- | --- |
| Controlled cases | 151 |
| Original CPU register boundaries | 61,987 |
| Reached original instruction addresses | 344 |
| C++ grant/snapshot replays | 604, with grants 1, 2, 17 and 4096 |
| Checked replay boundaries | 97,248 |
| Replayed dispatched instructions | 247,344 |
| Original stack-error endpoints | Two cases |
| C++ final registers, flags, ordered writes and complete memory | All match |
| Native MSVC | `c++latest /W4 /WX /O2`, unit and full replay pass |
| Sanitizers | Complete replay passes ASan and UBSan |
| Compiled counterexamples | Six rejected; unmodified control passes |

Instruction traces compare every register and control flag. Intermediate
arithmetic flags, including undefined flags, are not claimed; all endpoint
flags are compared. This is not yet original DOSBox work-clock/IRQ proof.

Coverage includes four RNG seeds, 0/1/2/8 spawner rows, a raw 255-row blocked
loop, free-running countdown wrap, budget/slot/enabled gates, actor counts
0/29/30, visual counts 0/2/31/32/33/255, zero/unit/FFFF random ranges, wrapping
AI base words, byte HP overflow and stack-floor failures. Visual row 32 keeps
its actual data aliases rather than normalizing them into a bounded typed pool.

## Portable Regression

`tests/fixtures/frame_spawner/` contains only controlled input slices, register
traces, ordered writes and metadata, not full RAM or screenshots. Its compressed
stream is 291,067 bytes; decoded size is 2,436,580 bytes. Frozen identities:

- Manifest: `d977e00bd3755b31832634fbc213977fa9da8c09c5f4cf8c531a72659decc7d2`.
- Compressed stream: `cc136c8adbe7f6e253dec24d9190733d65e44d59fff0450840ebc5fae82f06ca`.
- Decoded stream: `5dc0739f0167599e7c535b5d71a87975f87c039a3e18413b99539f1271fb27f4`.

The exporter authenticates the exact manifest, producer/shared source, original
executable and bounded stream. Repeated identical exports preserve bytes and
timestamps; mismatches, input aliases and live/broken symbolic links are never
overwritten. Mutation preflight rejects a different corpus before invoking a
compiler and retains each compiled variant's logs and result.
The existing native-Git cold-checkout regression now includes this family and
reproduces the CRLF failure when the protected-family rules are removed.

```sh
cmake --build build --target lezac_frame_spawner_test
ctest --test-dir build -R frame_spawner --output-on-failure
```

The original generator requires the repository-pinned Unicorn wheel and a new
RAM output directory:

```sh
env SDL_AUDIODRIVER=dummy PYTHONDONTWRITEBYTECODE=1 TMPDIR=/dev/shm \
  python3 -B tools/frame_spawner_oracle.py --repo . --out /dev/shm/spawner-original
```

## Remaining Goal Work

The new operation is not yet connected to normal `App::updateMonsterSpawners`.
Production still uses its independently original-backed semantic owner path.
No new visual, natural input, active interrupt or whole-game timing proof is
claimed. The remaining post-render prepass and gameplay dispatch must be
recovered/composed, then connected to the canonical App memory and shared clock.
The full-game goal remains incomplete; a passing controlled corpus is not a
substitute for continuous original-backed gameplay and seven-level completion.
