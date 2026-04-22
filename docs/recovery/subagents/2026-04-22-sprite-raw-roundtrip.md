# 2026-04-22 Sprite Raw Roundtrip Workstreams

## Subagent A - Disassembly/format mapper

- Confirmed the shipped sprite format matches the existing exporter: one count
  byte, followed by width byte, height byte, and `width * height` raw indexed
  pixels for each sprite.
- Kept the relevant draw evidence anchored to `18ac:00f4`, where zero pixels
  are transparent and palette index `0xff` remains visible.

## Subagent B - Rendering fidelity

- Recommended pinning the current transparency diagnostic with an exact CTest
  regex so the visible `0xff` behavior remains covered.
- Confirmed this branch only validates assets and transparent-pixel semantics;
  it does not change rendering behavior.

## Subagent C - Assets

- Confirmed raw bank facts:
  - `BOMOMIMK.SPR`: 91 sprites, 20,168 bytes, 19,985 pixels, 9,303 zero
    pixels, 10,682 nonzero pixels, and 104 `0xff` pixels.
  - `PROVA.SPR`: 91 sprites, 21,250 bytes, 21,067 pixels, 9,363 zero pixels,
    11,704 nonzero pixels, and 114 `0xff` pixels.
  - `FONTS.SPR`: 68 sprites, 5,425 bytes, 5,288 pixels, 2,730 zero pixels,
    2,558 nonzero pixels, and 151 `0xff` pixels.
- The aggregate fixture is 3 banks, 250 sprites, 46,843 raw bytes, 46,340 pixel
  bytes, 21,396 zero pixels, 24,944 nonzero pixels, and 369 `0xff` pixels.

## Subagent D - Verification

- Recommended a new `sprite_raw_roundtrip` CTest with a strict PASS regex.
- Recommended adding an exact PASS regex to the existing `sprite_transparency`
  CTest.

## Subagent E - Integration/docs/refactor

- Confirmed this branch starts from `origin/main` and avoids the state-2, sound,
  explosion, damage, GRAN, monster-motion, and AGENTS lanes in open draft PRs
  #23-#30.

## Integrated Decision

This slice treats sprite banks as structured original data, not just converted
JSON resources. It proves the C++ loader can reconstruct the shipped raw byte
payload for `BOMOMIMK.SPR`, `PROVA.SPR`, and `FONTS.SPR`, while separately
pinning the transparent-blit rule that only zero is transparent.
