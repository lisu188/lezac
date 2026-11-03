# Natural Debris Landing Clock Phase

The existing authenticated natural Level-2 fixture contains evidence stronger
than the separate controlled counter/updater calls: four actual landing
shatters inside continuous original gameplay. `natural_level2.fixture` now
requires these witnesses and frame continuity before any production replay.
Normal gameplay, existing native fixture bytes and broad fidelity flags are
unchanged. The global phase entry remains open outside this observed route.

## Native Evidence

This is a new analysis of the retained 2026-10-05 native capture, not a fresh
Level-2 recording. Its existing route starts at the menu, completes Level 1,
acknowledges results and the next introduction, and then observes 500 ordinary
Level-2 frames. The only original state seed is the existing initial Level-1
RNG seed. The production C++ replay receives input events, not native counter,
position, world, health, inventory or expected-state injections.

Every present/post pair has native frame `318 + sample`, independently of
the SDL replay tick `743 + sample`. All 1,000 boundaries retain the live table
bound and all 6,050 live 11-byte debris records, as well as the existing map,
player, RNG, HUD, palette, collapse, monster and full-RGB comparison scope.

Four records keep their physical slots and change from a non-shatter glyph
above `0x66` to `0x76` while their incoming vertical velocity exceeds `0x3C`:

| Replay Tick | Native Frame | Physical Slot | Incoming Glyph | Incoming Vy |
| --- | --- | --- | --- | --- |
| 992 | 567 | 210 | `0x68` | 66 |
| 1010 | 585 | 210 | `0x68` | 61 |
| 1020 | 595 | 212 | `0x68` | 79 |
| 1037 | 612 | 213 | `0x69` | 84 |

For every witness, `uint16_t(frame + slot) % 6` is 3. Substituting the previous
counter makes it 2, choosing the opposite branch. The incoming glyph excludes
the separate auto-shatter path, which requires glyph `<= 0x66`. The check
requires all four exact native anchors, matching physical record identity,
landing gates, live bounds, phase order and uninterrupted frame values.

Fresh REA 6.7.0 / Ghidra 12.1.4 observations on WSL byte-check seventeen
instructions covering reset, increment, native observation hooks, landing
gates and division. Direct call resolution independently verifies
`805D -> 45FA` followed by `8067 -> 5102`. The target is unchanged, the REA
session closes and the server exits normally. This static lane does not
execute the guest or establish live-frame behavior by itself.

## Sensitivity And Validation

Five Python methods pass on Linux and native Windows Python. They include
29 rejection controls for counter words at both boundaries, landing fields,
record identity, physical slot, live bound, missing boundaries and phase/tick
alignment. The existing 42 typed-field, three fixture, two invalid-bound and
five producer rejection controls remain passing and unchanged.

A fresh production C++ replay matches all 500 retained Level-2 frames,
1,000 mapped boundaries, 32,000,000 RGB pixels, 6,050 debris records,
4,151 collapse records and 1,339 bounded monster states. The original fixture
and route hashes are unchanged.

A separately compiled previous-counter fault changes only the live debris
dice expression to use `logicTick_ - 1`. It receives the same ordinary input
route from the menu. All 1,000 final clock WORDs still equal the native values,
but the existing complete comparator rejects it at sample 249, post-update:
replay tick 992, native frame 567. Physical slot 210 stays at `0x68`, where the
original and production App have `0x76`; the complete tile-plane hash differs.
The repository source and canonical assets remain unchanged by this probe.
The separately compiled next-counter fault is also rejected, one sample later
at post-update tick 993, native frame 568. Its 1,000 clock WORDs also match.
Thus both one-tick directions change real route behavior without changing
the reported frame values. These are isolated mutation probes, not shipped
production code.

## Coupled-Physics Contract Repair

Hosted Windows CI on #477 exposed a stale adjacent source contract:
`check_physics_dispatch.check_source` required the old `else if` chain and
rejected the newly declared debris-clock branch before executing the App.
The same failure reproduced locally. The repaired contract requires the
explicit isolated clock branch while preserving the complete gated
debris-before-collapse order; it does not accept an arbitrary intervening
branch or change production C++.

All twelve existing source mutations remain rejected, with two new controls
for an unconditional clock branch and replacing its real frame call with the
direct debris helper. The full 512-state, 32-scene, sixteen-step physics corpus
passes on Linux and the native Windows packaged App. Native Windows also
matches all 360 controlled debris-clock cases. The verified Windows package
is from #477 head `bf9651e59e6b717c62ea96dfd9623099cf766840`; no C++ source
changes occur in this follow-up. The failed hosted job is historical evidence
of the repaired contract, not a full-suite pass or a bypass authorization.

```sh
ctest --test-dir build -R '^(natural_level2_(original|guard)|natural_debris_phase_fixture)$' --output-on-failure
python3 -S -B tools/test_natural_debris_phase.py
```

## Limits And Negative Capture

An initial fresh continuous Level-1 bomb capture reached 297 frames and 891
pre/render/post debris observations, but had zero live debris records. Its
valid capture is retained privately and is not promoted as landing evidence.
The shipped-map scanner independently explains the miss: Level 1 has no
seedable bomb-object/above-word combinations; Level 2 has six. No counter or
world injection was added to force the target behavior.

The comparison remains instrumented/controlled native evidence, not physical
input, natural wall-clock cadence, audio waveform parity or owner acceptance.
It does not prove all actor fields, pause behavior, arbitrary clock phase
across all game flows, complete recovered-frame integration, later campaign
completion or whole-game fidelity. The independent actor-pass stability hold
and broad completion flags are unchanged.
