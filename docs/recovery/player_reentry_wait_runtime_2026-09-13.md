# Shared Player-Wait Fallback

## Scope

The original now has a complete 420-rendered-frame trace across player death,
the shared no-active-player fallback, the level-7 introduction, and resumed
gameplay. This is original evidence, not a production C++ replay. The port's
180-tick per-player timeout remains incorrect and is not changed by this
evidence batch. Whole-game fidelity remains unproven.

The capture restores the observed scene only at its single case boundary,
sets head HP/lives to 0/1, places a zero-fuse kind-16 bomb at the head, seeds
RNG and clock 100, and then leaves gameplay idle. It retains player damage
and waits for the boss to approach naturally. This is a controlled encounter,
not a natural campaign or a full-health boss victory.

## Observed Lifecycle

The promoted run waits 229 natural idle updates before the case. Player death
starts at sample 15; the raw actor countdown starts at 60, and life loss is
deferred until sample 75. That expiry frame places the player at `(840,328)`,
selects descriptor 39 (decoded index 38), changes global state to 2, and
decrements lives from 99 to 98. Samples 75..303 contain 229 completed waiting
frames. Animation and motion bytes remain frozen except for the raw countdown,
which decreases from 0 through `FF1C` rather than clamping at zero.

At sample 304, before incrementing the clock from 404 to 405:

1. Main `7EF8` sees `DS:79B9=229` and actor countdown `FF1B` (-229).
2. Main `7F03` sees counter 230 (`E6`), with global player state still 2.
3. Main `2ADC` is entered with global state 1, but the actor's behavior 2,
   countdown, animation, fractions, visual entry and lives remain unchanged.
4. Main `2C72` reaches the blocking keyboard call after drawing the level
   introduction. Its actual DOSBox screenshot says `PREPARATI PER IL LIVELLO 7`.
5. The harness captures the screen, releases the hook and injects Return on
   its private Xvfb display. Main `2C77` proves the keyboard call returned.
6. The same sample reaches the render boundary with a reset tile map, seven
   boss actors, six links, no flames, active player behavior, zeroed motion
   fractions and lives still 98. The raw actor countdown is still `FF1B`.
   Cached HUD energy is 255 at this initialization render, then 100 on the
   next normal update. Counter 230 is likewise cleared on that next update.

Samples 304..419 include the initialization render and 115 subsequent normal
gameplay updates. Clock values remain consecutive through this phase change.
The initial backdrop seed is not reused as a post-restart pixel oracle; the
fixture records the original views, but no C++ post-restart image comparison
is claimed.

Static guards identify the shared condition: main `7EEA`/`7EF1` tests whether
either global player-state byte is 1; that path clears `DS:79B9`. Otherwise
`7EF8..7F2A` increments the counter, waits for 230, promotes any global states
2 to 1, and jumps to the level-init call at main `77DC` (file `7F4C`). This is
not a separate 230-tick timeout per dead player. Two-player runtime cases and
the all-out/zero-life continuation still require their own observations.

An independent prototype run also completed 420 frames. It died at sample 10,
waited at 70 and restarted at 299, again after exactly 230 increments. Earlier
300/307-frame probes lacked the initialization/keyboard hooks and timed out
outside their gameplay hooks. They were incomplete captures, not game hangs,
and have not been promoted.

## Provenance

Executable SHA256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
MZ image base is file `0770`. Actual CS/DS/SS are `01A2/0C44/18B3`.
The host-address helper's `01ED/0C8F` segments are not actual CPU registers.

| Main Hook | File Offset | Observation | ES / Saved SP / BP |
| --- | --- | --- | --- |
| `7EBB` | `862B` | pre actor/link pass | `0C44 / 3FE4 / 3FFE` |
| `6813` | `6F83` | player input | heap segment / `3FA2 / 3FEE` |
| `7A57` | `81C7` | rendered playfield | `A000 / 3FE4 / 3FFE` |
| `7EF8` | `8668` | shared counter before increment | `0C44 / 3FE4 / 3FFE` |
| `7F03` | `8673` | counter 230 before promotion | `0C44 / 3FE4 / 3FFE` |
| `2ADC` | `324C` | level-init entry | `0C44 / 3FE2 / 3FFE` |
| `2C72` | `33E2` | intro drawn, before keyboard call | `0040 / 3DE0 / 3FF2` |
| `2C77` | `33E7` | keyboard call returned | `0040 / 3DE0 / 3FF2` |

The checked-in mode guards the EXE hash, 50 static windows including the
keyboard far call, its MZ relocation entry, runtime hook bytes, and the zeroed
instrumentation arena. Eight stubs occupy `F400..F7FF`; register handshaking
is at `F800`. The keyboard-call segment is relocated using the measured CS
before installation, and its relocated bytes are restored on completion.
Objects and word-plane pointers are refreshed after initialization.

Both runs used copied assets, dummy audio and private Xvfb. Exact checked-in
capture command (run from the repository, after creating the temporary asset
copy described in AGENTS.md):

```sh
env SDL_AUDIODRIVER=dummy PYTHONUNBUFFERED=1 \
  python3 tools/capture_original_boss_defeat.py --reentry-wait \
  --run-dir /tmp/lezac-boss-reentry-wait-v4 \
  --out build-codex-tmp/boss-reentry-wait-v4.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The prototype was `build-codex-tmp/capture_boss_reentry_probe.py --mass
--near-encounter`, with corresponding fresh `v3` temporary/output paths and
the same two approval flags. Both capture commands exited 0; after its final
screenshot, the seeder terminated and waited for only its owned DOSBox child.
No other WSL sessions were stopped.

Promoted fixture: `tests/fixtures/boss_reentry_wait_original_level7.txt`.
LF-normalized SHA256:
`e26aa4f34969721fecc384ba3cd9932d506789a33465845418635e4c0f876ce8`.
Intro screenshot: `tests/fixtures/boss_reentry_wait_original_intro.png`,
unchanged from `boss-reentry-wait-v4_intro_0.png`; SHA256:
`435fc2eee069e6064cfc14669c3c3b99ab9ddbbdf204c9ddd458e66b81017a22`.
The prototype trace SHA256 is
`941801aa3d4bdd8edcc15cdb2a754031173d811e646c080e96515081f29403e8`.

## Validation And Next Work

`tools/check_reentry_wait_evidence.py` checks the complete original phase
ordering, register boundaries, raw countdown, shared counter, player/life
fields, waiting sprite and placement, intro PNG hash, reset state, 22 indexed
playfield hashes and completion footer. Its self-test exercises LF/CRLF,
field corruption and incomplete/extended traces. It explicitly reports
`production_replay=0 whole_game_parity=0`; a pinned hash is not gameplay proof.
Both traces pass 1,939 corruption/truncation checks. Focused CTest runs pass
15/15 on Windows Release (23.86 seconds) and Linux (21.50 seconds), including
the new evidence/capture tests, all four boss capture contracts, existing
mass replays, and completion/visual/runtime claim guardrails.

Visual inspection covered prototype explosion/wait views 20/99, the actual
intro PNG, and resumed view 319. Separately, the existing near mass C++ replay
was rerun silently: 360 states, 30 views and 1,422,720 normalized pixels still
match. Its original/C++ sample-99 previews were inspected and independently
compared with ImageMagick (AE=0). That older 180-update-per-case replay does
not cover the newly captured fallback.

Next, replace the production per-player timeout with the shared lifecycle at
the original actor-pass boundary, preserve the raw word countdown, and replay
this complete transition without per-tick state restoration. Add P1/P2 active,
waiting and out cases, input-driven reentry, the unwinnable gate, and long-word
wrap observations. The existing standalone return model also incorrectly
promotes waiting states after one fallback increment; it needs correction,
not use as an oracle. Full intro/HUD/DAC fidelity remains separate work.
