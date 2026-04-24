# DOSBox Explosion Process-Memory Attempt - 2026-04-24

## Goal

Capture original runtime bytes for the unresolved explosion/debris/collapse
window around `1000:3a56..4d3b` after the interactive `dosbox-debug` prompt
again failed to submit commands with Return.

## Method

The user explicitly approved process-memory scanning. All runs used temporary
DOSBox copies outside the repository and read `/proc/<pid>/mem` only from the
child DOSBox or DOSBox-debug process started for the capture.

The new helper is:

```sh
python3 tools/capture_original_explosion_procmem.py \
  /tmp/lezac-original-explosion-procmem . --approve-procmem
```

It copies the original assets to a temporary run directory, launches DOSBox
under Xvfb, captures screenshots with Ctrl-F5, samples only the known recovery
ranges, and writes `explosion_playback_oracle_original_candidate.txt` plus a
manifest in the requested output directory. Candidate output must be inspected
before any fixture is promoted into `tests/fixtures/dosbox`.

The helper also writes `sample_summary.tsv` and optional timed screenshots
during the post-bomb sampling window. The summary decodes candidate
debris/collapse/effect slots and records the selected addresses as
`selected_debris_base`, `selected_collapse_base`, and `selected_effect_base`
when useful data is not in slot zero.

## Working Evidence

- `dosbox-debug` launched through `DEBUG LEZAC.EXE` still reaches the entry
  stop with `CS=01ED`, `DS=01DD`, `IP=7783`.
- Searching the child process for the entry byte signature located the loaded
  LEZAC image once, allowing an emulated physical-memory base to be derived.
- Searching for the original data string `larax e zaco versione` confirmed the
  gameplay data segment as `DS=0C8F`; the string begins at `DS:008B`.
- F5 continues execution only when sent to the debugger terminal window, not
  the SDL game window.
- Under the debugger-launched game, the menu start key needs a focused
  no-window `xdotool key 1` path and often a second tap.
- Player-1 right movement in this environment is reliable through the original
  `X` key, while arrow Right did not move the player during debugger runs.
- Embedded original strings confirm the player-1 controls as left `z`, right
  `x`, down `c`, jump `m`, and fire `n`.

## Failed/Unpromoted Evidence

No original explosion fixture was promoted.

Frame inspection showed the earlier timed samples either remained on the menu
or reached level 1 without placing a visible bomb at the intended `(24,22)`
route position. Dense process-memory samples therefore captured stable data
bytes, not proven stops inside `1000:414a`, `1000:370e`, or
`1000:3a7e..3d46`.

Observed scratch outputs included:

```text
/tmp/lezac-procmem-explosion-capture
/tmp/lezac-procmem-explosion-dense3
/tmp/lezac-debug-x-route-tune
/tmp/lezac-debug-bomb-key-methods
/tmp/lezac-regular-procmem-route2
```

The most useful visual finding was:

```text
debugger route:
  double key 1 -> leaves menu
  X hold       -> moves player right
  N/Space/Control_R test frames did not prove visible bomb placement
```

`tools/capture_original_dosbox_frames.sh` and
`tools/capture_original_explosion_procmem.py` now record the start/right/fire
keys they used in their manifests. The current default route uses the focused
no-window key path, two `1` taps, `x` for player-1 right, and `n` for player-1
fire with a short held scancode.

Follow-up frame capture with those defaults reached level 1 and produced the
semantic route frames. Visual inspection confirmed gameplay at
`020_level1_tile24_aligned`, a visible placed bomb at `030_level1_tile24_bomb`,
and visible explosion playback by `060_level1_tile24_playback_12`.

A later process-memory run using the same route and timed sample screenshots
captured visible explosion playback at `1.5s` and smoke playback at `2.0s`
after the bomb input. The generated candidate selected `DS:662F` as the best
collapse slot and decoded it through the C++ oracle, proving that the selected
slot machinery works on original bytes.

This is useful route evidence, but it is still not enough to promote an
explosion runtime oracle fixture by itself; the unresolved fixture still needs
runtime bytes or debugger/process-memory samples tied to the relevant
`1000:3a56..4d3b` execution window. The process-memory samples do not prove a
breakpoint stop inside the playback routines, and the sampled effect table
still needs exact semantic interpretation.

## Next Step

Use the now-working route with a clearly labeled instrumented temporary copy
that freezes after a target address is reached, or with a debugger session that
can submit breakpoint commands. Only promote
`explosion_playback_oracle_original.txt` after screenshots show the intended
bomb/object event and the sampled bytes prove the relevant runtime window was
reached.
