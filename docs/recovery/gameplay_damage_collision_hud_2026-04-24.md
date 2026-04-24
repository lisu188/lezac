# Gameplay Damage, Object Jump, And HUD Pass

This slice responds to live-play issues where bombs felt unreliable against
monsters, player HP was hard to observe, passable object cells could not be used
as jump support, and the HUD was too easy to miss.

Evidence workflow:

- Ran C++ and original level-1 frame captures under WSL/Xvfb with
  `tools/compare_original_cpp_frames.sh /tmp/lezac-fix-frame-compare .`.
- The helper produced paired C++/original frames, diffs, manifests, and
  `frame_compare_summary.txt`. Pixel diffs remain large because the C++ renderer
  is still approximate, so this pass treats them as semantic route evidence.
- Existing disassembly notes still anchor damage counters at `1000:7f68..7f8f`,
  monster death at `1000:74a6..7513`, and collision/passability as part of the
  wider unresolved actor-update window `1000:6053..777f`.

Implemented live-model fixes:

- Expired bombs now detonate before monster movement in each C++ update frame,
  so a monster already inside the blast footprint cannot step out before the
  fuse resolves.
- Passable bomb/low-word object cells remain pass-through for the level-1 route,
  but now provide jump support when the player's feet are on them.
- The HUD now draws a visible stats band with HP meter, lives, selected bomb,
  bomb counts, score, and progress instead of relying only on compact text.

Regression coverage:

- `--debug-monster-bomb-kill-live` locks same-frame bomb-vs-moving-monster
  damage, death-state entry, reward presence, and death actor removal.
- `--debug-player-damage-death-live` locks live hazard HP drain through the
  recovered damage-counter path until a life is consumed and reentry completes.
- `--debug-monster-contact-damage-live` locks integrated monster-contact
  pending damage accumulation, once-per-drain hurt sound behavior, state-2
  energy preservation, fatal underflow death dispatch, and visible HUD change.
- `--debug-object-collision-jump-live` locks object-cell jump support while
  preserving the level-1 bomb route.
- `--debug-hud-stats-live` frame-inspects the HUD band, HP meter, bomb icons,
  and stat-change redraw behavior.
