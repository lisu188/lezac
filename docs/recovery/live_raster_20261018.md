# Live Recovered World Renderer

The normal `GameRenderer::drawGame` and `drawWorldView` paths now execute
`FrameRenderOperation`, the recovered original `7A13..7A57` camera/raster/VGA
caller. This replaces semantic world painting for normal play. The old painter
remains only behind the two explicit provisional state-2 preview modes.

## Owners And Lifetime

`WorldRaster` belongs to `GameRenderer`. It owns persistent driver context,
known tile/mask bytes, a 65,537-byte raster buffer, a bounded 128-byte stack and
VGA overscan backing. Immutable sprite pixels are packed once at first draw:
the actual App constructs its renderer before loading the asset catalog.
Copy and move are disabled so cached pointers cannot outlive their storage.

The App passes the existing `MapPlaneMemory` and `ActorSlots::state()` by
read-only pointer. The driver borrows non-player visual rows directly, retaining
their physical order, latched dimensions and pixel offsets. It does not rebuild
those rows from monster/effect vectors or allocate actor identities. Player
rows still come from the existing typed player render state. This does not
establish complete physical player-descriptor ownership.

Production requires both live owners. Standalone frozen fixtures and older
explicitly seeded App diagnostics opt into `seededDiagnostic`; only that mode
may project a visual table from typed diagnostic actors or use a bounded map
without a physical owner. There is no implicit production fallback.

Camera globals, view gates and late VGA destinations are supplied to the
recovered caller. The current raster pitch and latched backdrop pitch remain
separate, including the negative row delta after a split-view survivor resizes.
The original production tile base is `DS:7F74`, as retained in the existing
render-boundary fixtures, not the deliberately controlled `0036` input used by
the generic raster instruction corpus. Mask reads use the original `2136`
displacement from that tile base.

Backdrop reads borrow the live map allocation after the retained eight-byte
gap, including decoder tails and object/word aliases. The new physical-address
read accepts the adjacent byte at offset `10000`; it does not truncate a word's
high-byte address to the segment start. This is distinct from ordinary 16-bit
map-cell addressing. The driver writes VGA indices directly into the existing
canvas, preserving gated views and the surrounding frame/HUD.

`lastCompletedWorldRasterWork` reports instruction dispatches, transferred words
and whether physical visual rows were used. These observations are checked at
the public renderer entry point. They are not CPU work-clock credits.

## Evidence

The original viewport-width, view-gate, initialization and survivor fixtures
pass through the recovered caller. The 60 width cases still match 3,072,000
pixels with zero differences; the 44 original width controls remain unchanged.
The App's original render-boundary checks also pass for single, split and tall
level-3/4/5/6 views, including backdrop/map-alias probes.

The dedicated owner regression covers deferred asset loading, mandatory
production owners, physical records absent from the typed vectors, deliberately
latched five-by-three dimensions, live coordinate and tile changes, non-wrapped
adjacent map/backdrop bytes and explicit rejection of unknown sprite heap and
tile-mask data reads. Five compiled mutations are rejected: physical-row bypass, wrapped adjacent
map byte, wrong VGA destination and bypassing the recovered caller in
`GameRenderer`, plus zero-filling undefined data. Actual source files remain
unchanged by mutation testing.

The Linux App builds successfully. All 53 focused actual-App gameplay, lifecycle,
startup, ownership, mutation and original-render tests pass. The live Xvfb/SDL physical
key test passes with dummy audio. Native MSVC C++latest `/W4 /WX /O2` builds and
runs the owner regression and its non-SDL dependencies. GCC C++23 ASan/UBSan
passes the owner regression at debug optimization. The initial optimized GCC
sanitizer build stopped on a `std::regex` dependency warning under `-Werror`;
no warning was suppressed to obtain the debug sanitizer result.

Fresh C++ level-7 fight frames were inspected at ticks 140 and 220. Paired
viewport PNGs compare a frozen controlled original reference with freshly
rendered C++ pixels. They are not fresh original DOSBox captures or aligned
original/C++ boss replay. All expanded fixtures, builds, logs and images are
RAM-only under the existing disk guard; none are published in this change.

## Remaining Fidelity Work

The App still uses its existing host-driven frame scheduling. This change does
not connect `FrameActiveOperation`, CPU-work pacing or render-time timer IRQ
delivery to the interactive loop. Existing low-level natural active-window
proof is separate from this production integration.

Driver data outside the recovered context and tile/mask bytes, and sprite heap
reads outside the packed bank, are rejected explicitly. Arbitrary DS aliases,
allocator-neighbor contents and full raster allocation history are not proven.
The existing computed backdrop color policy is retained; this does not establish
a complete single-owner DAC/palette lifecycle. Full campaign, input, sound,
timing and whole-game equivalence remain unproven.

Full Linux/Windows CI and current-head external review remain merge gates.

## Partial Pickup Fixture Boundary

The first full Linux CI run of PR #429 failed only `pickup_landing_original`:
the driver rejected unknown `DS:E06A` data. A local debugger reproduced the
read at original driver `019B`, after map cell 4604 yielded `FF`. This was not
a missing mask for a shipped tile. The seeded diagnostic restored only the
player/local map and indicator lifetimes, omitting the debris record required
to consume the pickup's temporary marker before a normal render boundary.

The diagnostic now renders an explicitly actor-only creation preview, with
no whole-world claim, while retaining all original actor comparisons. See
the pickup landing recovery note for the exact boundary. Unknown data remains
an error in both production and seeded rendering. The new owner assertion and
fifth compiled mutation ensure this integration does not hide the failure by
inventing zero bytes. The failing CI record is preserved; a new current-head
CI and external review must pass before merge.

The repair passes 24 selected CTests, including the formerly failing pickup
test and its five corrupt-fixture controls, five live-owner compiled mutations,
the low-level original raster corpus and its four compiled mutations, original
width/gate/survivor checks, boss fire/reentry, state-2 prepass, and natural
campaign replay/guard. Native MSVC C++latest `/W4 /WX /O2` also passes the
expanded owner regression. A fresh silent boss replay still compares 758,784
indexed pixels over 16 views with zero differences. No new full local suite,
native Windows actual-App build, natural boss victory or RGB/DAC capture is
claimed by this repair.

## Full CI Job Budget

The subsequent Linux job `117686097802` reached original-backed campaign test
1,036 of 1,053 before GitHub cancelled it at the configured 90-minute job
limit. The annotation explicitly reports `1h30m0s`; this is not a completed
full-suite result. Its preceding tests include completed level-4 original
replays, with the third-objective replay taking 149.39 seconds under the
recovered production raster.

The Linux job budget is now 150 minutes and the Windows budget 180 minutes,
both still bounded. Test commands, test selection, assertions, per-test CTest
timeouts, failure retention and production rendering are unchanged. A parsed
YAML comparison against current main differs only in those two job budgets.
Integration retains the new main-branch campaign scout registration. Every
C++ source byte remains identical to the prior `4ee294d` renderer head.
The integrated Linux App and selected targets build, and all 43 focused
renderer, original CPU, ownership, mutation, checkout and scout checks pass.

This scheduling allowance does not turn the cancelled run into a pass. Fresh
full Linux/Windows CI and exact-head review remain required before merging.

## Reserve-HUD Main Integration

After #436 merged, the only conflicts were the frozen-fixture attributes and
cold-checkout family list. Both the raster and reserve-HUD protections are
retained. CMake keeps both complete test families. The integrated App, original
raster replay and reserve-HUD targets build; all 22 selected raster/owner,
compiled mutation, reserve-HUD, pickup, state-2, boss-reentry and cold-checkout
checks pass. The reserve production changes are retained from current main,
not replaced by the older renderer branch. This new merge head requires a
fresh external review and full CI; the earlier clean review covers `f9cfa4a`.

## Independent Camera Ownership

Review of integration PR #439 at `886d3f3` found that standalone `drawWorldView`
replaced player 1's visual coordinates with the requested camera coordinates.
With nearby players, selecting player 2 therefore rendered player 2 twice and
omitted player 1. The owner regression reproduced this before the repair.

Standalone rendering now enters the recovered near-Pascal camera callee at
`1000:3587` with its own X/Y stack arguments and return address `7A25`. The
unchanged caller then executes the original raster/copy continuation through
`7A57`. Neither player visual row is changed. The full-game caller still starts
at `7A13`; this adapter does not claim to execute the caller's skipped argument
pushes, or to bind an interactive instruction work clock.

Two independent runs of the unchanged original instructions produce identical
24-case controlled corpora. They cover both player cameras, an independent
camera and a copied player-2 camera, three viewport rectangles, and background
enabled/disabled. The observed/unobserved complete 1 MiB memory and all 14
endpoint registers agree; ordered writes reconstruct memory, all 43,552 code
bytes remain unchanged and both player visual rows are preserved. No guest
patch, stub, interrupt or I/O is used. This is not a natural gameplay capture.

The public C++ `GameRenderer::drawWorldView` with live map and physical visual
owners matches all 1,536,000 indexed pixels. Compiled mutations reintroducing
the row-zero overwrite and pointer-identity camera selection are rejected.
The seven owner mutations preserve the production sources. Native MSVC
C++latest `/W4 /WX /O2` passes the expanded owner regression. The compact frozen
corpus includes authenticated assets/producer bytes, bounded decompression,
failed-report/output-retention controls and autocrlf cold-checkout protection.

Raw original memory and screenshot files remain RAM-only. The displayed pair
uses a shared normalized palette; it is not a live DAC equivalence claim.
Fresh current-head review and full Linux/Windows CI remain merge gates.
