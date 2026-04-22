# 2026-04-22 Sprite Blit Contract Workstreams

## Subagent A - Rendering/disassembly mapper

- Confirmed `18ac:00f4` remains the primary rendering anchor for the sprite
  transparent blit contract.
- The original rule is zero-only transparency: source palette index `0` is
  transparent, while palette index `0xff` is visible and must be copied.

## Subagent B - Rendering fidelity

- Recommended a synthetic blit test instead of relying only on shipped-bank
  `0xff` pixel counts.
- The new diagnostic draws a 4x2 synthetic indexed sprite through the actual
  `drawSprite()` path over a prefilled framebuffer.

## Subagent C - Assets/UI

- Recommended using synthetic sprite pixels for the direct renderer contract,
  while keeping the existing `sprite_transparency` shipped-asset count as the
  asset-side guard.
- No live UI behavior changes were made, so the existing SDL dummy and
  Xvfb/xdotool smoke tests remain the frame coverage for this slice.

## Subagent D - Verification

- Recommended adding `sprite_blit_contract` next to `sprite_transparency` in
  CTest.
- The test pins the exact output:
  `sprite_blit_contract=ok width=4 height=2 drawn=6 skipped_zero=2 ff_visible=2 bg_preserved=2 outside_preserved=2`.

## Subagent E - Integration/docs/refactor

- Confirmed this branch starts from `origin/main` and avoids the state-2, sound,
  explosion, damage, GRAN, monster-motion, sprite-raw-roundtrip, and AGENTS
  lanes in open draft PRs #23-#31.

## Integrated Decision

This slice directly tests the renderer contract behind the existing asset
transparency counts. It proves `drawSprite()` leaves source `0` pixels
untouched, writes nonzero indexed pixels through the palette, preserves pixels
outside the sprite bounds, and treats `0xff` as visible.
