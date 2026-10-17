# Complete Foreground Fragment

The recovered C++23 `FrameForegroundOperation` composes the original
`game:7903..7A13` fragment on one memory bus. Pacing, DOS GetTime, software
Real48 display, CRT delay, HUD prelude and BIOS keyboard drain keep their
existing resumable operations. The handoff at `79E8` consumes no synthetic
instruction. DOS and keyboard callback bases remain separate.

## Original Evidence

The retained `t209-r4` observation used the unchanged original executable
SHA-256 `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`
and read-only DOSBox instrumentation. Five local RAM samples verified 43,552
relocated original code bytes each. Their hashes are retained; full RAM images
and screenshots are not published in the fixture.

Two complete natural windows contain 95,864 and 12,479 CPU boundaries. The
first crosses a VGA vertical callback with pending palette work; the second
executes the periodic timing calculation. Continuous and snapshot-restored
replay compare all 108,343 states, giving 216,686 comparisons, 36 computed
millisecond grants and 18 computed device callbacks across both passes.
Later CPU, memory, queue and palette observations are comparison targets only.
Natural predecode comparisons cover all general/segment registers and the
IF/TF/DF control flags. Lazy arithmetic flags are not materialized by the
observer and are not claimed as fully compared by this corpus.

The palette model follows unchanged DOSBox `Check_Palette` behavior: clear
previous modified flags when dirty, preserve an empty pending range, compare
native RGB32 mappings against the LUT, mark actual differences, and reset a
processed range. Its software-surface profile requires full 8-bit channels,
an active unlocked non-blit backend, and idle-update coherence. Unsupported
formats, losses, surface locks and backend states are rejected.

An independent source-function oracle extracts unchanged `Check_Palette` and
`GFX_GetRGB` bodies from pinned DOSBox 0.74-3 sources and executes native SDL
mapping. Ninety-six controlled profiles cover six RGB byte orders, optional
opaque alpha, dirty cleanup, empty/single/full/partial ranges, unchanged LUT
entries and preexisting modified flags. Tests perform 384 callback checks and
23 unsupported-profile rejection controls. These are function-level results,
not execution of the entire original host.

## Retained Failures

The first two captures missed the pending-palette window and failed their
coverage target. The third reached both windows but included scripted key
input while tracing was still running; projection rejected its unknown device
callback. All three are retained locally. The final route defers the ordinary
Z hold until the initial observed palette window completes. It does not pause
the guest, seed gameplay, patch instructions or write process memory.

An initial implementation confused the observed frameskip counter with the
unobserved renderer full-frame flag. Original replay rejected the first dirty
palette callback. The corrected model leaves the frameskip counter at zero
and does not claim to recover the renderer full-frame flag.

## Validation

All 58 focused CTests pass, including the 53 existing pacing, clock, HUD,
keyboard and source-ownership checks. Native MSVC `/std:c++latest /W4 /WX`
compilation, original replay, palette oracle, four fixture tests and two SDL
runtime-identity tests pass with
all temporary output in RAM. Eight isolated palette/foreground mutations are
detected; the baseline passes both replay probes. Source ownership covers 124
production files and all 19 guard controls pass.

These local checks do not replace current-head external review or the full
Linux/Windows GitHub suites. No actual-App foreground integration build or
new candidate-App screenshot is claimed.

## SDL Runtime Review

The first external review identified a real loader-provenance gap: `-L` pins
link-time selection but does not select the library loaded by the executed
oracle. A retained external-SDK regression reproduces this mismatch with a
distinct, identity-marked copy of the SDL image. Without a loader pin the
process selects the system image; the corrected producer selects the SDK
image and verifies its identity. The original SDK is unchanged by that test.

The corrected driver reports the actual image containing `SDL_MapRGB` through
`dladdr`. The producer uses complete build/run environments, supplies the SDK
loader directory explicitly, excludes inherited preload overrides, and checks
the resolved runtime path and hash against the expected SDK image. Missing,
ambiguous, unreadable, changed and mismatched identities fail closed.

The pinned SDK in the real capture environment aliases the system SDL image;
the corrected observation confirms its hash is
`b82090085ba665c89ea70909b9018a219c42029fdf9803e7d5e17c185d6d1d72`.
The regenerated 96-case oracle remains byte-identical. C++, original natural
observations and all decoded projection bytes are unchanged; only producer
provenance, regression coverage and the frozen manifest are updated.

## Limits

The natural windows contain no delivered timer IRQs and no changed-HUD glyph
copies. Earlier interruptible pacing, HUD and keyboard fixtures still exercise
those paths separately. Their tests must remain passing. This corpus cannot
establish composition under active IRQ1, host wall-clock fidelity, downstream
execution after `7A13`, RGB full-frame equality, or whole-game parity.

The operation is not integrated into the actual App loop. The historical C++
App screenshots are presentation baselines, not screenshots of this new
operation. Original screenshots are asynchronous to RAM/CPU observations.
`original_fidelity_claim=0`, `visual_claim=0`, and whole-game completion remain
unchanged.
