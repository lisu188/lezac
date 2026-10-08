# Original Bomb Actor Lifetimes And Preserved Bytes

## Result

The complete original actor updater was independently checked against all
16 retained DOSBox bomb-motion traces: 2,304 updates and 106,720 compared
actor/visual bytes, with no differences. Constructor comparison includes all
38 actor bytes and all eight visual bytes. Update comparison uses the same
full records at `1000:75B4`, before expiry processing. Every updater call,
including the final expiry call, then executes to its original return.
Post-explosion maps and effects are not independently recorded by those
native fixtures and are not claimed equal to native captures.

The validated executor then ran 96 controlled poisoned-slot lifetimes:
four weapons, both countdown parities, two input-velocity pairs, shipped
Level 1 or an explicitly empty map, and three previous-slot byte patterns.
This covers 13,872 complete updates and 96 complete expiry paths. None of
the 18 non-animation bytes preserved by placement was read, and all 32
three-pattern groups matched outside those preserved bytes.

Positive controls require reads of the actor's kind, visual index, timer,
velocity, fractions, hotspot, behavior and animation fields. In each case,
memory-observed and unobserved execution agree on all 1 MiB of mapped
memory, the complete pre-expiry timeline, instruction counts, return
registers and FLAGS. Original instructions are not patched, original calls
are not stubbed, and interrupts/hardware I/O are rejected.

## Why The Caller Matters

The constructor at `1000:2F9F` deliberately leaves some previous-slot bytes
untouched. That alone does not establish a gameplay bug. The bomb caller
at `1000:6C25..6CB3` initializes all seven animation bytes after successful
allocation. The successful placed bomb therefore has a stopped cursor;
full-pool refusal skips that initialization and preserves existing actors.

The non-animation preserved offsets are `3..5`, `14..19`, and `29..37`.
They were not consumed by the controlled bomb lifetimes above. This is not
proof that they are unused by other actor kinds or constructor callers.
For example, the launch-pad caller at `1000:695F` clears animation mode
only after successful allocation; the pickup caller has different
full-pool tail-initialization behavior. Do not generalize constructor-only
write footprints into a shared lifecycle rule.

## Reproduction

The analysis tools require optional Unicorn 2.1.4, as do the other original
CPU capture tools. It is not a game/runtime dependency or a requirement of
the fixture/CLI contract self-check. Use an existing analysis environment:

```sh
env SDL_AUDIODRIVER=dummy PYTHONDONTWRITEBYTECODE=1 \
  python3 -B tools/check_original_bomb_native.py \
  --out /tmp/lezac-bomb-native.json --unicorn-path /path/to/unicorn

env SDL_AUDIODRIVER=dummy PYTHONDONTWRITEBYTECODE=1 \
  python3 -B tools/capture_original_bomb_lifetime.py \
  --native-report /tmp/lezac-bomb-native.json \
  --out /tmp/lezac-bomb-lifetime.json --unicorn-path /path/to/unicorn

python3 -S -B tools/check_original_bomb_native.py --self-check
```

Use fresh output filenames. The reports are retained on comparison or
execution failure. Original executable, level data and native descriptors
are hash-pinned. The 16 native traces are also pinned; sparse checkouts may
read their exact committed blobs instead of materializing them. The native
cross-check must match the executor source hash before the lifetime probe
will accept it.

The lifetime probe fails closed if any preserved byte is read or a stale
pattern changes state outside those bytes. Eight standard-library contract
regressions cover LF/CRLF fixtures, trace corruption/truncation, unregistered
traces, and clean/contradictory lifetime outcomes without importing Unicorn.

## Boundaries

These tools execute original machine code; they do not compile or compare
the C++ port. The ordinary native traces cross-check the executor, not the
natural reachability of poisoned slots. Controlled lifetimes use one placed
bomb; mixed pools, arbitrary callers, all levels and original hardware
timing remain separate recovery work. The empty-map probe explicitly has
zero-filled map segments. Native post-explosion map/effect parity is open.

No production gameplay behavior or broad fidelity/completion claim changes
here. Natural Levels 1..3 remain the only completed campaign routes; Level 4
onward and the complete boss/campaign remain open. The raw-prefix guard and
overall reverse-engineering percentage are unchanged.
