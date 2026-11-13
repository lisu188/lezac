# Original reserve-life count

Baseline: `9a06e0bc` (main after PR #235).

## Evidence and correction

The production port used the original reserve-byte semantics during death:
zero remains playable and the next loss changes it to -1 (original byte FF).
However, new games initialized the value to three. The HUD and Level 1
comparison projection each subtracted one, concealing an extra playable life.

The unchanged original executable initializes both reserves to two:

| Original anchor | File offset | Bytes | Operation |
| --- | --- | --- | --- |
| `1000:2F5F` | `36CF` | `C6 06 EA 79 02` | `DS:79EA = 2` (P1) |
| `1000:2F64` | `36D4` | `C6 06 EB 79 02` | `DS:79EB = 2` (P2) |

Executable SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The pinned walk, bomb and objective bundles in
`tests/fixtures/level1_original` independently retain `02 02` at these offsets
in `initial-ds.bin`. Their reference bytes and pins are unchanged.

With the projection corrected to expose the raw reserve count, the baseline
walk replay fails at tick 4, present phase, `$.players[0].reserve`: original 2,
port 3. Its 41 full frames nevertheless have zero differing pixels. This is why
a screenshot match alone cannot establish the life-count behavior.

Production defaults, ordinary menu starts and post-run reset now use two
reserves. The HUD draws the stored reserve count directly; the comparator
converts -1 to FF without subtracting one. Initial HUD pixels remain unchanged.
The existing 60-tick death/countdown, zero-reserve reentry and out-player
semantics are not replaced or weakened.

## Regression scope

`reserve_life_lifecycle` starts from real menu/intro event handling, injects
fatal damage, and runs production reentry prepasses. It checks:

- one-player game over on the third death;
- two-player exhaustion in both P1-first and P2-first orders;
- no reserve loss before countdown expiry, and one loss at expiry;
- reentry at zero reserves, no reentry at -1, and no duplicate loss;
- two reserves when restarting from the end-of-run menu;
- fifteen rendered HUD checkpoints with two, one or zero reserve figures.

This is a controlled lifecycle regression, not a natural full-level route.
No player position or map is teleported/rewritten by the test. Fatal damage is
explicitly injected; it does not establish the original timing of bomb/contact
damage or full-game parity. Existing fixtures that intentionally start with
three or 99 reserves retain those explicit diagnostic values.

The original evidence guard checks the initialization instructions, the pinned
raw reserve bytes and the projection for 2, 1, 0 and -1. It also inspects the
ordinary production replay's initial health fields and rejects a projected
extra-life mutation. The end-flow record regression expects the corrected
post-run reserves rather than three.

The pinned walk, bomb and objective routes remain the visual/parity regression:
575 full 320x200 frames, 1,150 projected state comparisons and 36,800,000 pixels.
They do not include a natural three-death game-over route.

## Reproduce

All game/test processes must use dummy audio, including child processes.

```sh
env SDL_AUDIODRIVER=dummy SDL_VIDEODRIVER=dummy \
  ./build/lezac_cpp --debug-reserve-life-lifecycle /tmp/lezac-reserve-frames
env SDL_AUDIODRIVER=dummy ctest --test-dir build --output-on-failure \
  -R 'reserve_life_lifecycle|level1_original_|end_flow_records'
```

The optional frame directory contains full-frame PPMs from the controlled
lifecycle test. Original/comparable natural route frames are decoded from the
pinned bundles by `tools/level1_original.py`, never generated or painted over.
