# Ammunition HUD sampling order

Baseline: main after PR #244 (`a20315b2b2ec0e574e9265c2eef11bb535210278`).

## Original behavior

Main-CS offsets are file offsets minus `0x770` in the pinned LEZAC.EXE.
The ammunition panel is painted before the state-2 refill/reentry and player
fire/weapon-switch passes, not from the final inventory of the same update.

- `7C49` checks the per-player inventory dirty byte at `DS:1B75`.
- `7C54` allows this panel update only in global player state 1.
- `7C74` calls panel helper `326E` before the reentry/player passes.
- `3283` reads the selected weapon and `329D` reads its inventory byte.
- `3327` clears the dirty byte; `332C` clamps the displayed unsigned count to 99.

PresentationState now owns separate sampled inventories for both players,
including level reset and snapshot/restore. The application samples them in
the original per-player prepass order. Rendering only reads these samples;
it does not update gameplay inventory or presentation state.

## Independent capture and regression

The unchanged 2026-09-26 original capture is pinned as
`tests/fixtures/level1_original/rapid_fire`, canonical SHA-256:
`28d7f1ba6f8164d417cf85cce910d3abbd9108469e241aeb63e40bbe7408b6f8`.
Its original capture-source SHA-256 is
`f1797c57fe6363f9e189fb2ab0b9c76d32b5d2f46305458e2ba513b1d7d18758`.
The four previously pinned route bundles are unchanged.

The route starts from the menu with controlled initial RNG seed 305441741,
uses 300 updates at 40,800 microseconds, presses N at tick 8, repeats it every
tick from 24 through 298, and releases at 299. These are normalized control-bank
events, not a physical-key timing experiment.

At ticks 270/271/272/273, the rendered raw small-bomb inventory is 101/100/99/98
and the post-update inventory is 100/99/98/97. The panel still displays 99 at
tick 273: it was painted before tick 272's player fire. It changes to 98 on
tick 274. The previous C++ replay instead showed 98 at tick 273 and differed
in 202 pixels over ticks 273 through 281, despite matching projected gameplay
state. The corrected retained replay matches all 297 full 320x200 frames,
594 projected states and 19,008,000 pixels, with zero differences.

## Validation and limits

- The original-data guard checks all seven instruction windows, the four raw
  inventory transitions and the full ammunition digit region across 272/273/274.
  All 10 guard tests, including uncropped-pixel and late-corruption rejection,
  passed on 2026-09-30 against the retained corrected Linux executable.
- Rendering tests cover independent player samples, state-2/out freeze,
  snapshot/restore, level reset and repeated-render purity.
- The existing HUD diagnostic explicitly samples inventory after directly
  preparing its diagnostic states. This does not seed production gameplay.
- A new `level1_original_rapid_fire` CTest case replays the pinned route and
  compares complete frames and the existing state projection. No comparator
  fields or pixel regions were removed or relaxed.
- The original and corrected C++ tick-273 screenshots were inspected and their
  full source pixels verified identical. Nearest-neighbor previews are 960x600.

The local Windows volume is above the repository's 90% usage threshold, so
large new local captures/builds/full-suite runs are paused. Full fresh-build
validation is delegated to the existing Linux/Windows CI jobs before merge.
This route is not physical held-fire proof or whole-game fidelity proof.
Audio waveforms and every actor-pool field remain outside the comparison;
global completion/fidelity claims stay false. See the separate physical-input
observation report for the remaining held-through frontier.
