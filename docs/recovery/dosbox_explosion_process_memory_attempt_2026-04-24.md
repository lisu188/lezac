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

For explicitly labeled instrumentation runs, the helper accepts:

```sh
python3 tools/capture_original_explosion_procmem.py \
  /tmp/lezac-original-explosion-freeze . \
  --approve-procmem --approve-instrumentation \
  --freeze-ghidra-offset 1000:3A7E
```

This patches only the temporary copy of `LEZAC.EXE`, replacing two bytes at
`MZ_header_paragraphs * 16 + ghidra_offset` with `EB FE`. The manifest records
the Ghidra/runtime address, file offset, original bytes, patch bytes, loaded
runtime bytes, screenshot hashes, and whether a repeated tail screenshot
suggested a visible freeze. These runs are not pristine original evidence; use
them only to prove that a target address is reached by a route.

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

The helper now also writes `route_state_samples.tsv` and
`route_state_dumps.txt`. These files sample narrow runtime ranges around known
route and player state bytes (`DS:1b70`, `DS:78c0`, `DS:7990`, `DS:79e0`),
the explosion queues (`DS:2090`, `DS:6610`, `DS:c1e0`, `DS:c21e`), and the
state-2 frame table area (`DS:c320`). A short validation capture at
`/tmp/lezac-route-state-20260424-codex-1` reached level 1, placed a bomb, and
showed visible explosion playback in `090_after_sampling.png`; its route-state
rows show `active_players_79b8=1` after level start and rising queue/effect
nonzero counts by the final sample. These route-state artifacts are raw
evidence for hardening future timing gates, not promoted gameplay semantics by
themselves.

The same helper can also defer `EB FE` freeze instrumentation until after the
bomb route reaches a runtime condition. This mode writes only to the child
DOSBox process memory, requires `--approve-runtime-instrumentation`, and keeps
the temp executable unmodified. Two state-gated probes used
`--runtime-freeze-after-bomb-seconds 0.10 --runtime-freeze-min-queue-score 40`:

```text
1000:3A7E  child-memory patch applied at 0.160s after bomb input,
           old runtime bytes 8b16 -> ebfe; no freeze was observed, and the
           route continued into visible explosion playback.
1000:3FA6  child-memory patch applied at 0.160s after bomb input,
           old runtime bytes 5589 -> ebfe; freeze observed, but the inspected
           final frame remained pre-visible-explosion/armed-bomb state.
```

This confirms the runtime patch path works and makes the earlier `3FA6`
pre-explosion result more precise. It still does not promote original explosion
playback evidence because the freeze is before visible playback, and `3A7E`
was not reached after the gated patch.

The runtime gate now also supports decoded queue predicates such as nonzero
debris/collapse/effect byte counts and selected queue bases. A later `432A`
probe first required selected collapse base `DS:662F`, but the route selected
`DS:6620`, so the helper correctly withheld the patch. Rerunning with
`--runtime-freeze-require-collapse-base 0x6620`,
`--runtime-freeze-min-queue-score 100`,
`--runtime-freeze-min-debris-nonzero 10`,
`--runtime-freeze-min-collapse-nonzero 20`, and
`--runtime-freeze-min-effect-nonzero 20` applied the patch at `1.246s` after
bomb input with score `150`, selected bases `DS:209e`, `DS:6620`, and
`DS:c22e`, and loaded bytes `5589 -> ebfe` at `1000:432A`. No freeze was
observed and the final inspected frame still showed visible playback, so
`432A` is not the active playback stop for this route/window. Timed
screenshots inside the sampling loop can delay patching; late-freeze probes
should usually use `--sample-screenshot-seconds ''` and rely on the final frame
plus manifest hashes unless intermediate screenshots are the point of the run.

To make these probes repeatable, `--runtime-freeze-preset late-collapse` now
sets the late queue-growth gates (`score >= 100`, debris/collapse/effect
nonzero thresholds `10/20/20`) and disables timed screenshots unless the caller
explicitly overrides the screenshot list. A `1000:3BB2` run showed that the
default effect threshold can still be too strict for some routes, so the tuned
probe used `--runtime-freeze-min-effect-nonzero 16`. With that override,
`3BB2` patched at `1.286s` after bomb input with score `150`, selected bases
`DS:209e`, `DS:6620`, `DS:c22e`, loaded bytes `5589 -> ebfe`, and did not
freeze while visible playback continued. The sibling reverse-pass probe at
`1000:3D46` patched at `1.649s` with score `110`, loaded `5589 -> ebfe`, and
also did not freeze while visible playback continued. These are useful
late-window negatives for the level-1 route, not fixture-promoting stops.

The helper now captures a second tail screenshot after `090_after_sampling`;
matching `090`/`091_tail_freeze_check` hashes are used as the freeze signal
when timed sample screenshots are disabled. With that confirmation in place,
early post-bomb runtime patches mapped the dispatch chain:

```text
1000:75F1  patch applied at 0.121s, old 2d0c -> ebfe; freeze confirmed on an
           armed-bomb frame before visible explosion playback.
1000:414A  patch applied at 0.121s, old 5589 -> ebfe; freeze confirmed on an
           armed-bomb frame before visible explosion playback.
1000:370E  patch applied at 0.121s, old 5589 -> ebfe; freeze confirmed on a
           visible explosion frame, with selected bases DS:209e, DS:6611,
           DS:c22e and score 60.
```

This is the first runtime-freeze result in this series that is both tied to an
address and visually inside the explosion frame window. It still remains
instrumentation evidence and `visual_claim=0`; the next promotion step needs
the exact bytes and disassembly around the `370E` stop interpreted against the
effect/debris/collapse queues.

## Static `1000:370E` Follow-Up

The follow-up static dump used the MZ image base `0x770` and disassembled from
file offset `0x770 + 0x370e = 0x3e7e`:

```sh
dd if=LEZAC.EXE of=/tmp/lezac-static/range_370e_3a6d.bin \
  bs=1 skip=$((0x770+0x370e)) count=$((0x360))
objdump -D -b binary -m i8086 --adjust-vma=0x370e \
  /tmp/lezac-static/range_370e_3a6d.bin
```

That dump confirms `1000:370e` is the tile damage queue helper reached during
the visible explosion route, not a direct playback renderer. It reads the word
layer through the far pointer at `DS:6612`, ignores already damaged words, and
branches at `0x4000`.

The high-word path increments `DS:207e` before writing a debris record at
`0x2093 + 0x0b * DS:207e`; therefore the first original-written debris record is
`DS:209e`. The low-word path increments `DS:2080` before writing a collapse
record at `0x6611 + 0x0f * DS:2080`; therefore the first original-written
collapse record is `DS:6620`. The collapse record stores the flagged word at
`+4`, the two argument bytes at `+6/+7`, a word `abs(arg0) + abs(arg1)` at
`+0a`, and affected byte count at `+0e`.

The capture helper and C++ oracle now understand these queue counters. New
candidate captures record `debris_queue_count`, `collapse_queue_count`, and
whether the selected bases came from counters or scoring; the oracle can derive
`DS:209e`/`DS:6620` from dumped `DS:2070` bytes even when a fixture omits
explicit selected bases.

A fresh regular DOSBox process-memory capture at
`/tmp/lezac-counter-selected-20260424-codex-1` used the corrected helper and
reached the same inspected level-1 route. Frame inspection of
`030_bomb_key.png`, `042_sample_1p50s.png`, `043_sample_2p00s.png`, and
`090_after_sampling.png` showed the placed bomb, visible explosion, and
smoke/collapse playback. The generated candidate parsed through the C++ oracle
with `visual_claim=0`.

The useful promoted fact from that run is the first live collapse record:
`DS:2080=1`, selected base `DS:6620`, `start=0x0a06`, `end=0x0a08`,
`word=0x0009`, `flagged=0x8009`, and affected byte count `0x04`. The
deterministic C++ `--debug-bomb-object-explosion-effects` route now prints and
CTest-locks the same byte offsets for level 1 tile `(24,22)`. The same run left
`DS:207e=0x00c7`, outside the short `DS:2090` dump window, so debris selection
is still explicitly labeled as scoring-derived rather than counter-derived.

The helper now widens `DS:2090` reads up to the `DS:6610` collapse queue
boundary and keeps `DS:6610` at a wider `0x60` bytes. A follow-up capture at
`/tmp/lezac-wide-debris-20260424-codex-1` used the same inspected level-1 route
and produced counter-selected debris and collapse bases in one candidate:
`DS:207e=0x00c8`, debris base `DS:292b`, tile index `0x0540`, flagged word
`0xc004`, lookup byte `0x67`, and `DS:2080=1`, collapse base `DS:6620`.
Frame inspection of `030_bomb_key.png`, `040_sample_1p50s.png`,
`041_sample_2p00s.png`, and `090_after_sampling.png` again showed bomb,
explosion, and smoke/collapse playback. The checked-in
`explosion_playback_oracle_sparse_count` fixture is synthetic coverage for this
high-counter sparse-dump parsing shape; the original widened candidate remains
outside the repo with `visual_claim=0`.

Instrumented temporary-copy freeze attempts then tested several playback-window
anchors:

```text
1000:3A7E  patch loaded at file 0x41ee, old 8b16 -> ebfe.
           One run visually froze on an explosion frame, but the next rerun
           continued into smoke, so this is useful but not stable enough to
           promote.
1000:3BB2  patch loaded at file 0x4322, old 5589 -> ebfe; route continued.
1000:3FA6  patch loaded at file 0x4716, old 5589 -> ebfe; freeze observed,
           but on an armed-bomb frame before visible explosion playback.
1000:432A  patch loaded at file 0x4a9a, old 5589 -> ebfe; route continued.
```

Static disassembly after those attempts narrowed the playback consumer model.
`1000:3bb2` and `1000:3d46` are still the forward/reverse lane blenders, but
`1000:45fa..4d3b` is the longer effect/debris queue update pass that actually
calls them at `1000:4c96` and `1000:4ca9`. It copies the blended bytes back
into collapse records at `+6/+7` or debris records at `+4/+5`, uses collapse
record byte `+0e` as the span weight, tags high-half debris slots by adding
`0x4e20`, and removes queue entries through `1000:452a`/`1000:458d`.
`1000:3fa6` constructs the 11-byte effect records, while `1000:414a` selects
the four dispatcher profiles and sound cursors (`0xea74`, `0xea7e`, `0xea88`,
`0xeace`). The C++ `damage_queues` diagnostic now locks these static addresses
and first-slot write offsets as metadata coverage.

This is useful route evidence, but it is still not enough to promote an
explosion runtime oracle fixture by itself; the unresolved fixture still needs
runtime bytes or debugger/process-memory samples tied to the relevant
`1000:3a56..4d3b` execution window. The process-memory samples do not prove a
breakpoint stop inside the playback routines, and the sampled effect table
still needs exact semantic interpretation.

## Next Step

Use the now-working route with a clearly labeled instrumented temporary copy
that freezes after a target address is reached, or with a debugger session that
can submit breakpoint commands. Prefer gating those attempts on route-state
rows, such as level loaded, player-control state, and nonzero explosion queue
growth, instead of fixed sleeps alone. Only promote
`explosion_playback_oracle_original.txt` after screenshots show the intended
bomb/object event and the sampled bytes prove the relevant runtime window was
reached.
