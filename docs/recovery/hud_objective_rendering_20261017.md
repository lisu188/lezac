# Production HUD Objective Formatting

## Corrected Behavior

The production `GameRenderer::drawHud` used to clamp both remaining-objective
counts to 99. The original `313D..3181` instead emits exactly two low decimal
positions, right to left. Therefore 100 paints `00`, and 32767 paints `67`.
The objective-specific path now copies all 64 bytes per CARO digit, like
`1156`; ammunition, score reels and icon transparency are unchanged.

Bonus arithmetic also differs from a host integer comparison. `31CF..31D6`
store the low word of required-minus-collected, and `31DA` tests that word as
signed. A nonpositive result paints zero and latches completion. This is NOT
a signed 32-bit subtraction followed by clamping: required 32768/current 1
leaves 32767, and required 0/current 65535 leaves 1. Destruction operands are
zero-extended bytes (`3218..3240`). The production renderer and completion
flags share these width-preserving computations in `core/hud.hpp`.

`PresentationState` still evaluates completion only on dirty objective paths,
retains completion latches until level reset, and samples destruction only at
the original frame-word modulo-30 boundary. Host integer counters are reduced
to their original WORD/BYTE widths before caching. The bonus is the top row
(y166); destruction is the bottom row (y182).

## Independent Original Evidence

The existing frozen `frame_hud` oracle includes 17 unchanged-original cases;
14 are forward, nonfatal inputs applicable to the App renderer. DF=1 and the
original fatal-error route are not claimed as App presentation behavior.

`tools/hud_objective_oracle.py` independently executes 17 further controlled
profiles under Unicorn 2.1.4. They cover low-word subtraction wrap, destruction
requirements 100/101/255, unchanged caches and previously latched completion.
No original calls are stubbed or instructions patched. Observed/unobserved
runs have identical complete memory and registers, including endpoint flags;
43552 relocated code bytes remain unchanged in every run. The digit font is
authenticated through the existing original capture fixture and verified
byte-for-byte against production CARO tiles 121..130 by the rendering test.

Only compact endpoint evidence is published, not full RAM or screenshots:

- `tests/fixtures/hud_objective/oracle.bin.gz`: 2276 bytes, decoded 28453 bytes.
- Decoded SHA256: `11a90f1fd2c2673849c5f628d0b4e2202e675af85c7747778500efdb40c39330`.
- Original EXE SHA256: `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
- Frozen manifest SHA256: `4c2ccaa5f88cff8905da49e25205c0800bf4e7f51c478e21ba17208bd060a7f7`.

The checker authenticates the complete frozen manifest, endpoints, producer,
shared oracle module and original-font checker before publishing output.
Two Python methods include 24 changed/missing-input controls for absent and
existing outputs; rejection never creates or replaces the decoded oracle.
CI does not require Unicorn, raw RAM, or launching the original executable.

## Production Validation

`hud_objective_original_test.cpp` uses the real immutable `AssetCatalog`,
`PresentationState`, `Canvas`, `TextRenderer` and `GameRenderer`. It is not a
standalone formatter surrogate. Both one- and two-player layouts are checked,
with native-width, positive-widened and negative-widened host counters.
It checks original completion flags and dirty caches, non-sampling ticks,
modulo-30 sampling, indexed-pixel ownership and both 8x8 digit rectangles.
The one-pixel gutter is excluded: the App repaints the full panel while the
original glyph call deliberately leaves that gutter alone.

- Existing original corpus: 14 cases, 84 draws, 13056 digit-pixel checks.
- New boundary corpus: 17 cases, 102 draws, 21504 digit-pixel checks.
- Baseline App reproduced 276 differing pixels and four differing flags on
  the earlier corpus, and 692 pixels/eight flags on the new corpus, before
  adding widened-input repetitions. Both corrected corpora have zero differences.
- Full Linux App build succeeds. 76 focused CTests cover the new fixtures,
  prior foreground/clock/IRQ/HUD proofs, resources, render-state ownership,
  clear/fill behavior, actual-App HUD stats, both layouts and completion gate.
- Native MSVC 14.44.35207 uses C++latest: production modules at `/W4`, new test
  at `/W4 /WX`. Linux and Windows RGB/index dump bytes match exactly. An initial
  all-production `/WX` attempt exposed pre-existing conversion/unused-local
  warnings; those diagnostics are retained, not represented as a clean build.
- Three isolated faults are detected: restoring the 99 clamp, using signed
  32-bit subtraction, and clearing the completion latch. The latter two pass
  the earlier corpus but fail the new boundary corpus.

Fresh silent App captures cover all seven level starts and six level-7 boss
fight checkpoints. They are deterministic diagnostic states, not natural
campaign completion or original-frame alignment. Original-controlled digit
crops are shown beside actual production renderer pixels, separately from
these full App captures. All local artifacts remain in task-owned RAM because
the Windows volume is above the repository disk guard.

## Scope

This corrects an actual App rendering/completion mismatch. It does not replace
the governed wall-clock loop, integrate the recovered foreground owner bus,
recover later renderer boundaries, prove active IRQ1/sound interactions, or
establish whole-frame/campaign parity or owner visual acceptance. The overall
reverse-engineering goal remains open.
