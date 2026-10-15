# Complete Shipped-Profile Native Record Cross-Check

This diagnostic executes the unmodified original spawner and shared actor
code against the retained shipped-profile native fixture. All 45 constructors
and 2,880 continuous updates match. No production C++ behavior changes, new
native captures, natural campaign acceptance or broad fidelity claims follow.

## Evidence And Execution

The independently retained native fixture is
`tests/fixtures/shipped_monster_profiles_original.bin`, SHA256
`b1c71fb54958a9cac974c30813ba55c157ff50cdb5bfa33688a97ab0cbfe79ea`.
Its provenance, two agreeing native captures, failed-run retention and existing
C++ field replay are documented in
[the shipped-profile recovery](shipped_monster_profiles_runtime_2026-10-05.md).

The 15 shipped profiles cover Levels 1..6, kinds 1..4 and behaviors 3/4.
Each has three RNG seeds and 64 continuous actor updates in the original
controlled 60-by-33 room. Original actor and RNG state are never reloaded from
expected post-update records; the spawner constructor produces the actor.
Only the native player visual targets and active-state flags are exogenous.

The optional runner uses Unicorn 2.1.4 with the existing `original_bomb_cpu.py`
loader. The pinned original MZ image receives its 468 normal relocations.
No original instructions or calls are patched or stubbed. Interrupts and
hardware I/O are rejected. The complete current native bomb cross-check
prerequisite is required: 16 traces, 2,304 updates, 106,720 bytes, current
executor/checker hashes and all trace identities. Its bytes are read once and
hashed before parsing and validation, including on rejected inputs.
The executor, prerequisite checker and validator are tracked in this branch
through merged PR330. The default-root live command needs only the optional
Unicorn package and a fresh prerequisite report outside the repository.
The runner selects the executor explicitly from `--root/tools`, hashes its
source once and directly compiles that same buffer. Cached module objects,
timestamp-valid `.pyc` files and dependency-path shadowing do not select the
executor. The prerequisite validator and checker also execute directly from
source, and report identities describe those executed buffers rather than
later file contents.
The report producer likewise bootstraps execution from one source buffer and
records that buffer's digest before analysis. File replacement cannot change
the running producer's identity, and unbound imported producers fail closed.

Each case restores initial CPU/memory state and supplies the original observer's
controlled map, zero word plane, legal player health/reserves, spawner record,
counts, frame and RNG. Original startup ranges `CS:293d..2949` and
`CS:2852..2858` initialize motion and visual table pointers. The actual
`CS:7a6b..7c3d` spawner loop runs for construction and subsequent countdowns;
`CS:7ebb..7eea` executes the actor pass. Every range must reach its exact
return boundary within a bounded instruction count.

At each constructor and pre/post actor boundary, the runner compares the full
38-byte actor, 8-byte visual and 30-byte spawner records, four RNG bytes, two
frame bytes and actor/visual counts. The 5,805 checked boundaries compare
487,620 bytes with no differences, executing 1,856,423 original instructions.
The player records/flags in the 112-byte native state are inputs, not compared
outputs; native capture registers are not claimed as emulator register parity.

## Portable Checks

The self-check and twenty-three contract tests require only Python's standard
library, not Unicorn or the optional original CPU helper. They reject fixture
and shipped-bank mutation, truncation/trailing bytes, optimized Python and
unequal record lengths. They verify failed/malformed prerequisite retention,
single-buffer attribution, actual imported-executor identity, rejection of
unvalidated executors, stale bytecode bypass, single-read source attribution,
identity after source replacement, producer replacement/unbound identity and
refusal to overwrite existing reports.

```sh
python3 -S -B tools/check_original_shipped_profile_native.py --self-check
python3 -S -B tools/test_original_shipped_profile_native_contract.py
env SDL_AUDIODRIVER=dummy python3 -B \
  tools/check_original_shipped_profile_native.py \
  --native-report /absolute/path/to/current-bomb-native-report.json \
  --unicorn-path /absolute/path/to/unicorn-2.1.4 \
  --out /absolute/path/to/new-profile-crosscheck.json
```

## Limits

This result adds complete raw-record original CPU correspondence to the
existing retained native and selected-field C++ evidence. It does not establish
compiled C++ equality for every opaque actor byte. Player processing, complete
world/map effects, actual level geometry, natural spawning, mixed-pool
allocation, boss links, physical timing, rendered pixels and sound remain
outside the comparison. The Level 7 boss has no ordinary spawner profile here.
Whole-game completion and original/visual/sound fidelity flags stay false.
