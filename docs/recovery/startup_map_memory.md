# Interactive Startup Map Allocation

The original menu has no object or word map allocation. Four read-only RAM
snapshots from an unmodified original DOSBox process are retained in
`tests/fixtures/startup_map_original.bin.gz`: one settled menu observation,
the Level 1 intro, and two later running observations. The metadata fixture
records the original RAM hashes, runtime segments, pointers, capture source
hash, and evidence limitations. The original clock, RNG, heap and gameplay
state were not seeded; the process memory handle was read-only.

The original's four persistent allocations end at the future map heap base.
At the menu, both raw and normalized map pointers are zero, the heap top and
free list equal that base, and the next 128 KiB of RAM is zero. The three loaded
observations have identical complete object and word 64 KiB views, including
the decoder tails recovered in `level_rle_decoder_tail.md`.

The former C++ `runInteractive` called `resetLevel(0)` before presenting the
menu, which allocated a map. Choosing play then freed and allocated that map
again. Focused GCC and MSVC production-composition probes reproduce the extra
free's two nonzero metadata bytes: object-view offsets 1996 and 1998 contain
`0x08` and `0xF8`, where all three original loaded captures contain zero.
The direct first allocation matches the captured views byte-for-byte. These
probes establish the call-sequence discrepancy, not a full App execution.

Interactive startup now calls `resetLevel(0, false)`, preserving logical menu
preparation without allocating physical map backing. The ordinary play path
performs the first allocation. Other diagnostic reset paths and actual level
reload behavior are unchanged.

## Full App Regression

`--debug-startup-map-memory OUT [CX DX]` uses the same interactive startup and
settled-boundary diagnostic as `--debug-startup-rng`. It asserts that the menu
has no map allocation, then writes the App's complete object and word views at
intro and first presentation. The output-only observation never supplies map
bytes, expected state, or RNG updates to the App.

`tools/check_startup_map_memory.py` independently verifies all four original
RAM images, relocated original code, PSP/runtime segments, observed pointer
fields, allocation positions, zero menu carry-in and retained input buffer.
It compares both complete C++ map views with all three loaded original
observations, without masks. Two explicit clock inputs and one actual startup
clock produce six compiled boundaries and 786,432 distinct output bytes.
Eleven fixture and compiled-view corruption controls cover checksums, the
alignment-gap metadata and decoder-tail bytes.

`tools/pack_startup_map_observation.py --capture DIR --out FILE.bin.gz`
regenerates the fixture from the retained capture directory. It verifies the
original capture report, producer source and each full RAM hash before packing.
The byte-pinned binary SHA-256 is
`599d8944cdb5a926ffb414c0af6b25e319a8ee72b320f9e896b517507ed383cc`.
The metadata SHA-256 is
`849380da4752768f717c0843f81fd87246fec8077298e41963e33c5d9c0adeba`.

Focused compiler probes pass on GCC and MSVC. Fixture validation, corruption
controls, allocation-state unit checks and App syntax validation are local
checks; execution of the new full App regression is delegated to exact-head
Linux/Windows CI under the host disk guard. No local helper result is reported
as that full App regression having passed.

These are selected map-memory views, not complete C++ RAM-state parity. The
App diagnostic samples settled boundaries, not natural keyboard/menu timing.
Natural reload history, arbitrary heap fragmentation, full campaign state,
sound/runtime and frame/pixel parity remain open. Broad completion flags are
unchanged and the whole game remains incomplete.
