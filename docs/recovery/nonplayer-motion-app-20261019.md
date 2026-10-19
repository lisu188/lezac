# Original Nonplayer Pre-Terrain Motion in the App

## Boundary

The actorMotionPrefix API executes recovered original 1000:7018..732C
instructions on an owned 4 KiB stack. It returns before terrain consumption,
common collision response, coordinate/fraction integration and actor writeback.
The existing App owners still perform those operations exactly once.
Boss behavior 5/6 retains its dispatch. The player behavior-0 path before this
boundary is not recovered by this change.

The adapter borrows the existing original-initialized animation bytes at
DS:0058..0257. It preserves selector zero and the full byte-selector domain,
rather than substituting kind-based frame ranges. Typed and physical actor
animation update without changing the visible-frame latch. Existing owners of
DS:C1E8, DS:2072, DS:2074, RNG and the shared tick supply input and output.
Actor velocity words remain under the later writeback owner.

Production monster motion and behavior-2 timed motion now use this adapter.
The approximate gravity, floor response, random steering, speed normalization
and facing sequence is no longer the live monster path. Historical isolated
helper diagnostics remain, but are not proof of production execution.

## Independent Original Evidence

Two independent executions of the unchanged pinned MZ produced identical
compact projections:

- Executable SHA-256:
  7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec.
- Projection: 6,569 rows, 4,296,170 bytes, SHA-256
  bde513f8fcd3ea59200697887afa9630ac90e099d93a6b91e633c8a3d63150e6.
- Frozen manifest SHA-256:
  f65a6adad669a4e301ba40c05c5ff14468c161e682e114c24f120036e9296acc.
- Gzip: 192,433 bytes, SHA-256
  8e0c439726fbc436c2d6a6967b255a97b1a4d6260799970d9113ff3af9a84a05.

The producer authenticates the full parent corpus and entry/exit registers,
then independently observes the original prefix. Direct cases use controlled
initial memory. The 54 continuous actor cases and 54 real caller cases execute
from 6053/7EBB without later state injection. Complete memory and endpoint
registers match observed versus unobserved execution; ordered writes reconstruct
memory and original code bytes are unchanged.

The typed API matches all 6,569 rows and 6,120,333 dispatched instructions,
including RNG, animation, locals, shared scratch and 30 zero-period divide
faults. Strict GCC, native MSVC /W4 /WX and ASan/UBSan replay the same corpus.
Nine compiled boundary faults are rejected. Fixture authentication and
tamper/retention controls run on Linux and native Windows. Cold Git checkouts
preserve bytes and reproduce CRLF corruption when the protection rule is removed.

## Actual App Comparison

The --debug-nonplayer-motion-original command invokes updateMonsterMotion,
the same method used by updateMonsters. It admits 4,230 behavior-3/4 rows,
including 36 real caller cases, and explicitly excludes 2,339 other behaviors.
The core test covers every row.

The preserved baseline App disagreed on 3,807 admitted rows. Its executable
SHA-256 was 40ab4506aa16335c2b16ac2582c507fd6e512c5e6a4a60220d92499ba9605cd6
and source SHA-256 was
5c91a6c37939bb344479e1eea571aace8e5011f1a08cac6d2e38ce8f0162a192.
The new path matches all admitted rows, including physical animation, visible
latch, RNG, shared scratch and 30 divide faults.

The steering diagnostic invokes the production prefix, including off-gate and
zero-period controls. A zero period no longer silently skips division:
already-produced changes are applied and the unrecovered runtime fault is
reported. The original error handler is not simulated.

Three older diagnostics omitted animation selectors while expecting a kind
fallback. Their seeds now retain shipped constructor selectors or copy bytes
3/4 from the original fixture. Original expected outputs, selector-zero
behavior and comparison assertions remain unchanged.

## Remaining Limits

This is controlled boundary replay, not natural campaign or full-frame proof.
The existing target owner still selects by wide Manhattan distance. Original
extreme-word target selection, inactive-player stack locals and the full
pre-prefix player path remain separate work. The API uses a normalized private
stack and fixed original floor word 0x0200; 14 unusual parent stack/floor profiles
are explicitly excluded.

No IRQ schedule is delivered and instruction counts are not charged through
the production work clock yet. Common terrain/integration, natural routes,
physical input, long runs and aligned frame/pixel timing need independent
acceptance. Soundless frame-harness captures are regression evidence, not owner
visual approval or pixel parity.
