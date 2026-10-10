# Settled Game Over Presentation

This restores the settled, zero-score Game Over screen reached by natural
Escape in the original game. It does not establish whole-game fidelity,
end-run typing timing, record-entry ordering, or completed-game presentation.

## Executable Evidence

The unmodified `LEZAC.EXE` SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Its MZ image begins at file `0x0770`; the addresses below are code-segment
offsets, not file offsets.

- `1B23` calls `01FC`, the same pattern routine used by level intros.
- `01FC..030A` draws 320 by 200 pixels, choosing palette indices 176 through
  182. It draws horizontal/vertical increments with `Random(80)+1`, then
  `0139..01F9` draws three `Random(20)` starts and three `Random(30)` deltas.
  The eight draws share the gameplay RNG and must not be repeated by painting.
- `1B63..1B86` sends `game over` to text routine `146A`: 11-pixel cells,
  y=77, final glyph color 31, shadow color 25, five-column color trail.
- `1BC9..1BF3` advances y by 20 and draws the localized final-score heading
  with 11-pixel cells, final glyph color 244 and shadow 25.
- `1BF4..1CF7` advances y by 24 and inspects both player score longs. Only
  positive signed values are shown. Each displayed line uses 9-pixel cells
  and advances y by 11. Its text is the localized player label, player digit,
  the original `; ` separator (rendered as `: `), and the decimal score.
- The heading/player strings are DS:098A/0A8A in Italian and DS:168A/178A
  in English. `1CF8` waits for a key; there is no extra title or menu prompt.

The existing intro background renderer and level-result text-trail renderer
are reused. The recovered pattern is generated once at each Game Over entry,
including natural Escape; painting is RNG-free. Other menu pages and the
current end-run control flow are unchanged.

## Original Pixel Oracles

Two native 320x200 PNG captures came from the soundless, unmodified DOSBox
observation documented by `abort_map_original.json` and
`abort_map_memory.md`. Capture labels are `game-over-after-escape-1` and
`game-over-after-escape-2`; neither gameplay nor RNG/clock state was injected.
Their RGB bytes are committed as `end_screen_1.rgb` and `end_screen_2.rgb`.
Capture and RGB hashes, pattern inputs, and palette colors are recorded in
`end_screen_original.json`. PNG decoding used Pillow, without resizing or
color conversion beyond RGB decoding.

Pattern inputs were uniquely determined from the first row among the 80 by
80 legal increment pairs. The reconstructed background was then checked
against all 53,440 pixels outside the two text rows. This exclusion is only
for input inference. The C++ regression compares all 64,000 pixels of each
complete rendered frame, including text, shadows, and background, with no
masks or tolerances. The observed patterns are fixture inputs, never runtime
constants or whole-game RNG alignment claims.

`end_screen_original` also checks repeated painting, both localized score
layouts, zero and signed-boundary scores, and the shared pattern generator's
eight-call contract. `abort_map_original` exercises actual App Escape entry,
checks exactly eight RNG state advances and RNG-free redraws, and retains
the original complete-map lifetime checks. CI preserves focused frame dumps
before the longer full suite. Only the two zero-score settled screens have
original-backed complete-frame pixel comparisons in this change.
