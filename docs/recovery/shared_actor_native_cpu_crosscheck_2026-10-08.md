# Native Mixed Actor CPU Cross-Check

## Scope And Result

Unmodified original instructions now reproduce the ten retained seeded
mixed-actor cases in `tests/fixtures/shared_actor_order_original.txt`.
The comparison covers 410 consecutive actor passes, 7,685 complete 38-byte
actor records and 8-byte visual records, actor/visual counts, four RNG bytes,
and all 1,980 byte-map cells at every captured post-actor boundary.
All 1,167,770 compared bytes match. The fixture is unchanged; normalized-LF
SHA-256 is `765b724713778f7fa86e7df8fe7812de9e40b029cf85b46bc6e25ed9ecdd6e4e`.

This extends the optional original-machine-code oracle beyond isolated bomb
motion into stable deletion, adjacent retirements, corpse/bomb conversions,
failed allocation in full 30-actor pools, RNG ordering, and same-pass appends.
The existing [production C++ replay](shared_actor_order_runtime_2026-09-06.md)
compares mapped fields. This new result compares complete native records
with original CPU execution, not with compiled C++ raw-record output.
It is not a new native capture, natural route, frame/pixel comparison,
post-pass word-plane comparison, physical timing result, or whole-game claim.

## Execution Boundaries

The runner uses `original_bomb_cpu.py` and requires its native bomb-motion
prerequisite report. The original executable, levels, descriptor fixture,
helper/checker hashes and all sixteen prerequisite native traces are pinned
by that executor and prerequisite validation. Unicorn 2.1.4 remains optional;
normal builds and the two added CTests use only the Python standard library.
The runner selects the executor explicitly from `--root/tools`, reads and hashes
its source once, and compiles that same buffer directly. Existing cached module
objects, timestamp-valid `.pyc` files and dependency-path shadowing do not select
executor code. Its prerequisite validator and checker are also loaded directly
from source. Recorded identities remain those of the executed buffers if files
are subsequently replaced. This is separate from the native fixture checks.
The report producer itself bootstraps execution from one source buffer and
records that executed buffer's digest before analysis. Replacement of its file
does not change the report identity; an unbound imported producer fails closed.
The executor/prerequisite tools are tracked in this branch through merged
PR330. The live command uses these repository-local sources by default;
only the optional Unicorn package and a fresh prerequisite report are external.

The MZ image is relocated normally, with no original instruction patches,
call stubs or permitted hardware I/O. Initial setup executes original
CS:293d..2949 to initialize the record-table bases and CS:2852..2858 to
initialize the visual-table pointer DS:C1FC. The latter is required by the
driver's stable visual deletion helper. Both ranges have verified return
boundaries and their expected pointer writes are checked.

Each case restores exactly the producer's active actor/visual seeds, map
planes, counts, RNG and selected globals. Unused tails and other globals
are not reset between cases, matching the retained producer's sequencing.
Each sample executes CS:7ebb..7eea: motion links, if present, then the complete
dynamic non-player actor loop. The comparison occurs at native CS:7eea.
After comparing, CS:804e..806a executes the original flame/collapse work
needed before the next sample. The frame value advances as recorded.
Players, drawing, keyboard/interrupt timing and the rest of the game loop
are not executed by this bounded runner.

Three failed setup reports remain retained. The first two lacked the
visual-table initialization and failed on the first surviving bomb's
vertical motion. Initializing only the record-table bases was insufficient.
The third passed 166 samples before failing byte-map comparison because
post-actor flame work had been omitted. These are diagnosed oracle setup
failures, not production-game regressions; expected native bytes were not
changed to make the comparison pass.

## Commands And Guards

Offline contract, without optional packages:

```sh
python3 -S -B tools/check_original_shared_actor_native.py --self-check
python3 -S -B tools/test_original_shared_actor_native_contract.py
```

Bounded original CPU analysis, after producing a current native prerequisite:

```sh
env SDL_AUDIODRIVER=dummy PYTHONDONTWRITEBYTECODE=1 \
  python3 -B tools/check_original_shared_actor_native.py \
  --native-report /path/to/native-bomb-report.json \
  --unicorn-path /path/to/unicorn-2.1.4 \
  --out /path/to/fresh-shared-actor-report.json
```

Twenty-three stdlib-only regressions pass on Windows and WSL. They exercise
LF/CRLF fixtures, truncation/mutation/extra-record rejection, byte and length
mismatches, optimized-Python rejection, failure retention, and refusal to
overwrite existing evidence. CLI failures are retained with traceback and
the active case/sample where available. Prerequisite bytes are read once,
hashed before decoding, then validated from that same buffer; rejected or
malformed prerequisites retain their immutable identity. A changing-input
negative control verifies validation and attribution use the same read.
Producer replacement and unbound-source controls verify the running generator
retains its executed-buffer identity without a late file read.
Ordinary CTest does not execute the
optional CPU comparison. Large local builds and fresh native game captures
were not run while the unchanged disk-reserve guard was closed.

Remaining work includes naturally reached mixed pools, living monsters,
boss links and interactions, all allocation callers, compiled C++ complete
record correspondence, and campaign/visual/audio fidelity. Existing broad
completion flags remain false and overall completion percentage is unknown.
