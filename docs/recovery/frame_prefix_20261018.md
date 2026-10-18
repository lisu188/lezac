# Continuous Frame Prefix Composition

`FramePrefixOperation` joins `FrameActiveOperation` (`7903..7A57`),
`FrameSpawnerOperation` (`7A57..7C3D`) and `FrameWaitingOperation`
(`7C3D..7EBB`) on the same caller-owned bus. It does not copy a later actor,
HUD or renderer snapshot into that bus at a stage boundary. The full entry
accepts the existing DOS/keyboard callback bases and PSP; a separate three-
argument constructor admits the original post-render entry at `7A57`.

The actor-update boundary is an explicit `ActorUpdate` outcome before `7EBB`
executes. It is not a completed frame. End-run UI, runtime error and keyboard
break-output handoffs remain separate outcomes; unknown child work is not
stubbed. The production App is not wired to this operation or its clock yet.

## Clock And Snapshot Contract

Stage transitions consume no additional synthetic instruction or work credit.
Each grant dispatches only recovered child instructions. REP grants are passed
unchanged to the active and waiting callees, and snapshots preserve the active
child plus cumulative dispatch/IRQ counters. Zero and terminal grants are
inert. Unit controls inspect all three stage boundaries, including the last
handoff without executing any actor work.

The active and waiting stages retain their existing nested IRQ owners. The
prefix owns the timer during spawner instructions, whose suspended CS can be
the CRT library rather than game code. It pushes the actual flags/CS/IP,
restores that child's complete registers after IRET, and rejects overlapping
or detached IRQ ownership. No fixed host-frame duration is introduced.

## New Original Evidence

The new frozen corpus executes **`7A57..7EBB` continuously**, not the earlier
active stage. It pairs the existing 151 spawner profiles with the 238 waiting
profiles by index, retaining every profile at least once. This is not the full
Cartesian product. It exercises actual allocation, visual/animation setup,
Random, ammunition/reserve drawing, screen clears and placement in one window.

The original MZ image is relocated without patches. Each controlled case runs
with code/write observers and again without those observers. All 14 endpoint
registers and complete 1 MiB memory match. Ordered writes reconstruct complete
final memory, and all 43,552 game-code bytes remain unchanged. The producer
verifies the mapped pinned Unicorn 2.1.4 image, three canonical assets and all
five producer/helper sources, then rechecks sources before export. No calls
are stubbed; no interrupt is delivered and no hardware I/O is allowed.

Two independent final runs produced byte-identical manifests and gzip streams.
Only controlled seeds, register columns and ordered writes are published,
not full RAM dumps or screenshots.

| Property | Value |
| --- | --- |
| Cases / actor handoff / UI handoff / runtime error | 238 / 228 / 2 / 8 |
| Register observations / ordered writes / executed addresses | 378271 / 142437 / 836 |
| Decoded / compressed bytes | 30982063 / 2043589 |
| Decoded SHA-256 | `5cea09712a1189f1aeb8dc5617b25c3e32d52c387b7030dbfeed618a3defb830` |
| Compressed SHA-256 | `27ff6ac13c1629f233cb484778da168857ae1865329798ae70d9959ecbe96b91` |
| Manifest SHA-256 | `cc2df2a76271145e8c743b4b790a31ba8333d1e441e14e3fe7e652cda068df43` |

## Validation

The C++ test runs 2,856 original replays across instruction grants 1/2/17/4096
and REP limits 1/2/65535. It restores the whole prefix snapshot after every
grant and compares 1,552,630 boundaries, 3,973,452 dispatches, 1,034,496 string
transfers, all endpoint registers/flags, ordered writes and full memory.
Intermediate control flags are checked; intermediate arithmetic flags are not.

Eight computed IRQ cases cover outer spawner, CRT Random, animation setup,
spawner-to-waiting entry, player placement, reserve glyphs, a sprite's source
DS and rectangle clearing. These verify C++ restoration/counters, not original
IRQ scheduling. They do not turn the controlled corpus into clock evidence.

Twelve controls/mutants compile independently. Ten faults fail original replay;
the active-to-spawner handoff fault is caught only by the synthetic boundary
unit test because the new original corpus begins at `7A57`. The unchanged
control passes both lanes. The initial REP mutant exposed an unused-parameter
compile failure; its failed report is retained, and the corrected compilable
mutant reaches the behavioral rejection. Production sources remain unchanged.

All five focused prefix CTests pass, including the compiled mutation lane.
The complete replay passes GCC ASan/UBSan and native MSVC C++latest `/W4 /WX`.
Linux fixture tests pass all eight; native Windows Python passes seven with
one explicit symbolic-link permission skip. Native Windows Git preserves all
eleven fixture families / 39 files and demonstrates eleven CRLF controls.

The integrated App and selected targets build, and all 87 focused CTests pass,
including existing renderer, owner, viewport, spawner, waiting, HUD, map-plane,
state-2, pickup, mutation and natural-campaign checks.

The combined production App also passes the original-backed level-7
fire/reentry replay: 140 ticks, 16 views and 758,784 compared indexed pixels
with zero differences under its shared normalized palette policy. That replay
is seeded at the case boundary and does not execute `FramePrefixOperation`.

## Integration And Remaining Scope

The branch retains the exact reviewed #429 and #438 heads, including the
corrected #437, #434/#435 dependencies, and the merged #436 reserve work.
The only dependency-merge conflict was the cold-checkout family list; every
family and binary fixture protection is retained. No original fixture pin or
production renderer guard is relaxed.

The earlier active-window natural evidence remains component evidence. The
three-stage composition is **not yet proved by one natural `7903..7EBB`
capture**, and neither this class nor the seeded App replay establishes a
complete iteration, continuous campaign, production work-clock integration,
original IRQ schedules, live DAC timing, natural boss victory, physical-input
acceptance or whole-game parity. The actor/update tail, end-run UI and broader
runtime ownership remain required work toward the full goal.

Local source, build, expanded corpus and capture artifacts live in WSL RAM
under the existing reserve authorization. Fresh exact-head external review
and full Linux/Windows CI remain integration gates.
