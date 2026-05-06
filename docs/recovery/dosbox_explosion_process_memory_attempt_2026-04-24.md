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
nonzero thresholds `10/18/20`) and disables timed screenshots unless the caller
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

Follow-up runtime child-memory probes used the same level-1 route with the
tuned late-collapse gate. Patching `1000:4C96` applied successfully, with
runtime bytes `e819 -> ebfe`, but both early and late gates continued through
visible playback without a frozen frame. Patching the enclosing update entry at
`1000:45FA` is a stronger positive: an early gate froze before visible
explosion playback, and the later gate at
`/tmp/lezac-45fa-late-runtime-20260424-codex-1` applied at `1.365s` after bomb
input with score `160`, selected bases `DS:209e`, `DS:6620`, `DS:c22e`, and
runtime bytes `5589 -> ebfe`. Frame inspection of `030_bomb_key.png`,
`090_after_sampling.png`, and `091_tail_freeze_check.png` showed the same
visible explosion/playback frame in the final two screenshots, and the matching
hashes confirmed the freeze. The generated candidate parsed through
`--debug-explosion-playback-oracle` with `visual_claim=0`.

The next branch probes explain the negative `4C96` result. Patching
`1000:492F` froze on the same visible playback frame at
`/tmp/lezac-492f-runtime-20260424-codex-1`; the oracle candidate parsed with
`DS:207e=0x00c7`, collapse count `1`, and selected bases `DS:209e`,
`DS:6620`, `DS:c22e`. Static code at `1000:4934` requires
`DS:207e >= 0x00c8` before the high-debris loop enters its interior. Probes at
`1000:4C75` and `1000:4B6A` loaded patches but did not freeze, which matches
the `0x00c7` exit-before-interior path. Therefore the current level-1 route
proves the `45FA` update entry and `492F` high-loop gate during visible
playback, but not the `4C96`/`4CA9` lane-call path.

The high-counter timing from `/tmp/lezac-wide-debris-20260424-codex-1` was then
replayed with runtime child-memory patching for `1000:4C96`:
`--level-start-seconds 1.5`, `--sample-interval 0.04`, `--sample-seconds 2.5`,
`--route-state-interval 0.5`, and `--runtime-freeze-require-debris-base
0x292b`. The default-delay rerun
`/tmp/lezac-4c96-highdebris-runtime-20260424-codex-1` did not reach the
counter-selected slot and stayed at `DS:207e=0x00c7`. The route-tuned rerun
`/tmp/lezac-4c96-highdebris-runtime-20260424-codex-2` did reach the intended
gate: the runtime patch loaded at `1.995s` after bomb input with queue score
`200`, `DS:207e=0x00c8`, selected debris base `DS:292b`, collapse base
`DS:663e`, and effect base `DS:c22e`. The selected high debris record was
`41 05 04 c0 26 00 1c 00 00 67 80`, decoded as tile index `0x0541`, flagged
word `0xc004`, forward byte `0x26`, reverse byte `0x00`, and lookup byte
`0x67`. Frame inspection of `040_sample_1p50s.png`, `041_sample_2p00s.png`,
`090_after_sampling.png`, and `091_tail_freeze_check.png` showed visible
explosion/smoke playback advancing, and the manifest recorded
`instrumented_freeze_observed=0`. A matching `1000:4CA9` run at
`/tmp/lezac-4ca9-highdebris-runtime-20260424-codex-1` did not reproduce the
`DS:292b` gate and left the runtime patch unapplied. These results narrow the
next question: `4C96` can be patched while the high-counter slot is selected,
but this route still does not prove execution of the lane-call instruction
after the patch is installed.

Static re-reading of `1000:492f..4d3b` identifies the next useful fork before
the lane calls. After the high-half loop passes the `DS:207e >= 0x00c8` gate,
`1000:4b35` checks whether the target-offset helper left a nonzero `DS:2090`.
`1000:4b3f` then computes the target byte address, `1000:4b6a` is the
zero-target branch, `1000:4c20` is the nonzero-target branch, and `1000:4c75`
is the later positive-word gate before the `4c96`/`4ca9` calls.

The route-tuned temp-copy probe
`/tmp/lezac-4b3f-highdebris-temp-20260424-codex-1` patched `1000:4B3F` from
process start and froze on the visible explosion frame. Its candidate parsed
with `DS:207e=0x00c8`, selected debris base `DS:292b`, collapse base
`DS:662f`, effect base `DS:c22e`, and high debris bytes
`40 05 04 c0 27 00 75 00 03 67 00` (tile index `0x0540`, flagged word
`0xc004`, forward byte `0x27`, reverse byte `0x00`, lookup byte `0x67`).
Frame inspection of `041_sample_2p00s.png`, `090_after_sampling.png`, and
`091_tail_freeze_check.png` showed the same frozen blast frame, and the three
hashes matched. Route-tuned temp-copy probes at `1000:4B6A` and `1000:4C20`
did not reproduce the `DS:292b` high-counter state and did not freeze, so they
do not yet distinguish the zero-target and nonzero-target branches.

The capture helper now emits explicit high-debris target fields for chosen
samples: the signed `DS:2090` delta, target byte offset, lookup segment from
`DS:c1fe`, word-layer far pointer from `DS:6612`, `DS:c204`, sampled target
byte, and target word-layer value. A fresh `1000:4B61` temp-copy probe at
`/tmp/lezac-4b61-target-gate-20260424-codex-1` froze at the byte gate after
the target sample. It parsed with `DS:207e=0x00c8`, selected debris base
`DS:292b`, target delta `0x0001`, target offset `0x0541`, lookup segment
`0x3ef4`, target byte `0x00`, word-layer address `3f71:0a82`, word-layer value
`0x0000`, and `DS:c204=0x003c`. Static code at `1000:4b61` compares that
sampled byte with zero and jumps to `1000:4b6a` when it is zero, so this run
identifies the next branch for the frozen visible blast state as the
zero-target path. Frame inspection of `041_sample_2p00s.png`,
`090_after_sampling.png`, and `091_tail_freeze_check.png` showed the same
visible blast frame and matching hashes.

The helper now also accepts
`--runtime-freeze-require-high-debris-target-byte`, which resolves the selected
high-debris target before applying a runtime child-memory freeze patch. Two
follow-up runtime-patch probes tried to stop at the confirmed zero-target
branch, `1000:4B6A`, only when the selected high-debris slot was `DS:292b` and
the decoded target byte was `0x00`. The late-collapse run at
`/tmp/lezac-4b6a-target-byte-gated-runtime-20260424-codex-1` did not patch:
the chosen `DS:292b` sample had target offset `0x05b8`, target byte `0x33`,
and word-layer value `0x0000`. A second run without late-collapse thresholds at
`/tmp/lezac-4b6a-target-byte-gated-runtime-20260424-codex-2` also did not
patch, again selecting `DS:292b` with target byte `0x33`. These are useful
negative/timing captures: the `4B61` freeze proves a visible-blast state whose
sample chooses `4B6A`, but the current polling route reaches later `DS:292b`
states after the target byte has drifted away from zero. Do not claim executed
`4B6A` evidence yet.

A faster runtime-child probe then reproduced the narrow zero-target window:
`/tmp/lezac-4b6a-target-byte-fast-runtime-20260424-codex-1` used
`--sample-interval 0.005` and `--route-state-interval 0` with the same
`DS:292b` and target-byte `0x00` gates. It applied the runtime patch at
`1.436s` after bomb input, when `DS:207e=0x00c8`, selected debris base
`DS:292b`, selected effect base `DS:c22e`, target offset `0x0540`, target byte
`0x00`, and target word-layer value `0x0000`. The run froze at
`01ED:4B6A`, and `040_sample_1p50s.png`, `041_sample_2p00s.png`,
`090_after_sampling.png`, and `091_tail_freeze_check.png` all hashed to
`b8979bb17dff3bb459b2575104476d7e5f77332c73fee761127481ef6b204f12`,
confirming a held visible explosion frame. Its chosen post-freeze candidate
parsed with target delta `0x0001`, target offset `0x0541`, lookup segment
`0x3ea9`, word-layer pointer `3f26:0a82`, `DS:c204=0x003c`, target byte
`0x00`, and word-layer value `0x0000`. This promotes the earlier static
branch inference into original runtime evidence that the visible-blast route
executes the zero-target branch at `1000:4B6A`; it remains instrumented
process-memory evidence with `visual_claim=0`.

Static disassembly of the later high-debris lane-call area now gives the
branch shape. `1000:4c64..4c72` reads a word through the far pointer at
`DS:6612` and stores it in `[bp-4]`. `1000:4c75` compares that local with zero
and `jbe`s to `1000:4cae`; the positive side sets `DS:2078`, stores the doubled
target offset at `DS:659a`, stores the word at `DS:655e`, calls the forward
lane helper from `1000:4c96`, then ORs the word with `0x8000` and calls the
reverse lane helper from `1000:4ca9`.

The same fast target-byte-gated route was used to probe that static branch.
The first broad `4C75` and `4C96` runs loaded runtime patches but did not
freeze, because they patched after the sampled state had already advanced. An
early-gated `4C75` rerun added `--runtime-freeze-require-collapse-base 0x6611`;
it patched `1000:4C75` after `1.564s` with `DS:207e=0x00c8`, selected debris
base `DS:292b`, selected collapse base `DS:6611`, target offset `0x0540`,
target byte `0x00`, and sampled word-layer value `0x0000`, then froze at
`01ED:4C75`. Its post-freeze chosen candidate parsed with selected collapse
base `DS:663e`, target delta `0x0078`, target offset `0x05b9`, target byte
`0x00`, and word-layer value `0x0000`; `090_after_sampling.png` and
`091_tail_freeze_check.png` both hashed to
`af350ff9bcd0815c1814eea3ae5393b425e77f0938afd6286059e34a184b5231`.

A strict `4C96` rerun with the same collapse-base gate did not arm, because
that run reached selected debris base `DS:292b` later with selected collapse
base `DS:663e` instead of `DS:6611`. A relaxed rerun at
`/tmp/lezac-4c96-zero-target-fast-runtime-20260424-codex-3` required only
selected debris base `DS:292b` and high-debris target byte `0x00`; it patched
`1000:4C96` after `1.576s` with `DS:207e=0x00c8`, selected collapse base
`DS:6611`, target offset `0x0540`, target byte `0x00`, and sampled word-layer
value `0x0000`, then froze at `01ED:4C96`. Its post-freeze chosen candidate
parsed with selected collapse base `DS:663e`, target delta `0x0078`, target
offset `0x05b9`, target byte `0x00`, and word-layer value `0x0000`;
`090_after_sampling.png` and `091_tail_freeze_check.png` both hashed to
`8f89d267aebcf5f01af32a3c6b3d3916adf0c9246519baea5b7cfe4f4e06cd2f`.

The paired
`/tmp/lezac-4ca9-zero-target-fast-runtime-20260424-codex-1` patched
`1000:4CA9` after `1.576s`, when `DS:207e=0x00c8`, selected debris base
`DS:292b`, selected collapse base `DS:6611`, target offset `0x0540`, target
byte `0x00`, and word-layer value `0x0000`; it froze at `01ED:4CA9`. The
post-freeze chosen candidate parsed with selected collapse base `DS:663e`,
target delta `0x0078`, target offset `0x05b9`, target byte `0x00`, and
word-layer value `0x0000`. `090_after_sampling.png` and
`091_tail_freeze_check.png` both hashed to
`044cead2cc765001150eb117ca5e4f84444c23e854d7531140530ecdcd20c3c6`,
confirming the held debris/cloud playback frame. This proves the captured
zero-target route can reach the word gate at `1000:4C75` plus the forward and
reverse lane-call sites at `1000:4C96` and `1000:4CA9`. The helper-selected
`high_debris_word_layer` field is a sampled queue summary, not a capture of
the live `[bp-4]` local at the frozen instruction; by static control flow,
reaching `4C96` and `4CA9` means that some live iteration took the
positive-word side through the `4C75` gate.

This is useful branch evidence, but it is still not enough to change live C++
sprite playback semantics by itself. The promoted oracle fixture should remain
limited to proving the sampled runtime bytes and `4B6A`/`4C75`/`4C96`/`4CA9`
branch execution. The `45FA`/`4B6A`/`4C75`/`4C96`/`4CA9` freezes prove entry
into the effect/debris update path during visible playback, but they are still
instrumented process-memory evidence rather than debugger breakpoint stops, and
the sampled effect table still needs exact semantic interpretation.

A 2026-04-28 continuation added a narrower lane-division scratch mode for the
forward/reverse lane blenders. Temp-copy attempts at `1000:3CE3` and
`1000:3CD4` did not produce valid evidence because the larger patch body
overlaps a relocated far-call segment word in the DOS-loaded image. The helper
therefore rejects `--freeze-patch-mode lane-div-cs-scratch` unless runtime
child-memory instrumentation is explicitly approved.

Using immediate runtime patching after bomb input, the route froze at
`01ED:3CD4` and promoted
`explosion_playback_oracle_original_3cd4_lane_div_scratch_runtime.txt`. The
scratch block at `CS:3D24` records one live forward-helper setup with
`DX:AX=0xFFFF:0xFFF8`, `BX:CX=0x0000:0x0005`, active staging count/index
`1`, and matching `[BP-8]`, `[BP-4]`, and `[BP-2]` locals. The sampled lane
globals at the same stop are `DS:2078=1`, `DS:655E=0x8009`, and
`DS:659A=0x0A7A`. This promotes the signed lane-division setup to original
runtime evidence, while still leaving exact sprite playback semantics as
`visual_claim=0`.

The same immediate runtime approach then froze the actual forward far-call site
at `01ED:3CE3` and promoted
`explosion_playback_oracle_original_3ce3_lane_div_scratch_runtime.txt`. That
scratch block records already-loaded division registers
`DX:AX=0x0000:0x001C`, `BX:CX=0x0000:0x0010`, active count/index `1`, and
matching numerator/weight locals. Immediate reverse-helper probes at
`01ED:3E68` and `01ED:3E77` loaded the runtime patches but did not freeze on
this route; those captures remain failed reachability attempts and are not
promoted.

The writeback probe then targeted `1000:3D1B`, the forward collapse-lane
store. A plain two-byte freeze loop proved the route reaches the instruction,
but the oracle rejected it until the offset was promoted into the known
breakpoint set. The follow-up `lane-write-cs-scratch` runtime patch froze
`01ED:3D1B` and promoted
`explosion_playback_oracle_original_3d1b_lane_write_scratch_runtime.txt`.
That scratch block records output byte `0x01`, selected tag `0x0003`,
`DI=0x002D`, active count/index `1`, and result local `0x01`. The tag-to-DI
relationship matches the original collapse stride exactly:
`0x0003 * 0x0F = 0x002D`, so the original is about to write to
`DS:6617 + 0x002D`.

A follow-up targeted the paired debris store at `1000:3D2D` and exposed an
instrumentation hazard: the inline scratch body overwrote the shared writeback
join at `1000:3D31`, so the collapse path could jump into the instrumentation
body and create a false debris-side scratch record. The tooling now uses a safe
lane-write trampoline: a three-byte near jump at the probed instruction, a
runtime body at `CS:F000`, and scratch bytes at `CS:F080`.

With that safer patch, the same route re-captured positive collapse writeback
evidence at `1000:3D1B` (`output=0x04`, `tag=0x0004`, `DI=0x003C`) and added
positive reverse collapse evidence at `1000:3EAF` (`output=0x00`, same tag and
DI). Both preserve the collapse stride relation `0x0004 * 0x0F = 0x003C`.
Safe trampoline probes at `1000:3D2D` and `1000:3EC1` loaded but did not freeze
on this route, so debris-side writeback remains a reachability problem rather
than proven original behavior.

The next pass added a clearly labeled runtime seed at the original helper call
sites. For `3D2D`, the seed patches `4C96` to set `DS:655E=0xC004` and then
call the original forward helper. For `3EC1`, the seed patches `4CA9` in the
same way before calling the original reverse helper. These fixtures are not
natural-route evidence, but both freeze the original debris writebacks with
selected tag `0x4EE8` and `DI=0x0898`, proving the debris marker/stride
calculation `(0x4EE8 - 0x4E20) * 0x0B`.

A 2026-04-30 parser/tooling checkpoint added `lane-result-cs-scratch` for the
final helper result writes at `1000:3D3F` and `1000:3ED3`. The mode uses a
runtime-only near-jump trampoline with body `CS:F200` and scratch `CS:F280`,
capturing the result byte, `ES:DI`, `[BP+4]`/`[BP+6]`, `[BP-0D]`, active
count/index, and the destination byte before `mov es:[di],al`. The helper
refuses to patch unless the target bytes are `26 88 05`, and manifests record
that expectation as `freeze_expected_old_bytes`. A 2026-05-06 follow-up fixed
the candidate writer so promoted fixtures also carry explicit
`freeze_expected_old_bytes` and `freeze_old_bytes` keys, not only the long
`instrumentation=` line. The checked-in coverage now includes synthetic parser
fixtures, one original reverse result-write fixture
`explosion_playback_oracle_original_3ed3_lane_result_runtime.txt`, and one
labeled runtime-seeded forward result-write fixture
`explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded.txt`. A
natural right/down route-step fixture,
`explosion_playback_oracle_original_3d3f_lane_result_route_step_no_freeze.txt`,
records `x:2.00,c:0.50` loading the `1000:3D3F` patch without a forward result
freeze while live lane globals were present. The default/timing-variant and
route-step routes loaded the `1000:3D3F` patch but did not hit the forward
result freeze, so natural-route forward result-write evidence remains pending.
The no-DOSBox preflight also checks the shared static tail at both anchors:
loop-end compare, `mov al,[bp-0d]`, `les di,[bp+4]`, `mov es:[di],al`,
`leave`, and `ret 6`. Its status line carries the exact tail as
`result_tail_bytes=8b46f63b46f075c58a46f3c47e04268805c9c20600`.

Pending WSL capture commands:

```sh
python3 tools/check_explosion_lane_result_preflight.py .
python3 tools/check_explosion_lane_result_wrapper.py .
python3 tools/capture_original_lane_result_runtime.py --preflight-only
python3 tools/capture_original_lane_result_runtime.py \
  /tmp/lezac-lane-result-runtime . \
  --dry-run --skip-oracle
python3 tools/capture_original_lane_result_runtime.py \
  /tmp/lezac-lane-result-runtime . \
  --dry-run --skip-oracle --offset forward
python3 tools/capture_original_lane_result_runtime.py \
  /tmp/lezac-lane-result-runtime . \
  --dry-run --skip-oracle --offset reverse

python3 tools/capture_original_lane_result_runtime.py \
  /tmp/lezac-lane-result-runtime . \
  --approve-procmem --approve-runtime-instrumentation

python3 tools/capture_original_explosion_procmem.py /tmp/lezac-preflight . \
  --describe-freeze-patch \
  --freeze-ghidra-offset 1000:3D3F \
  --freeze-patch-mode lane-result-cs-scratch
python3 tools/capture_original_explosion_procmem.py /tmp/lezac-preflight . \
  --describe-freeze-patch \
  --freeze-ghidra-offset 1000:3ED3 \
  --freeze-patch-mode lane-result-cs-scratch

python3 tools/capture_original_explosion_procmem.py \
  /tmp/lezac-lane-result-3d3f-runtime . \
  --approve-procmem --mode regular \
  --freeze-ghidra-offset 1000:3D3F \
  --freeze-patch-mode lane-result-cs-scratch \
  --approve-instrumentation --approve-runtime-instrumentation \
  --runtime-freeze-after-bomb-seconds 0.0 \
  --level-start-seconds 1.5 --right-hold-seconds 2.0 \
  --sample-seconds 5.0 --sample-interval 0.005 \
  --route-state-interval 0 --tail-freeze-check-seconds 0.75
./build/lezac_cpp --debug-explosion-playback-oracle \
  /tmp/lezac-lane-result-3d3f-runtime/explosion_playback_oracle_original_candidate.txt

python3 tools/capture_original_explosion_procmem.py \
  /tmp/lezac-lane-result-3ed3-runtime . \
  --approve-procmem --mode regular \
  --freeze-ghidra-offset 1000:3ED3 \
  --freeze-patch-mode lane-result-cs-scratch \
  --approve-instrumentation --approve-runtime-instrumentation \
  --runtime-freeze-after-bomb-seconds 0.0 \
  --level-start-seconds 1.5 --right-hold-seconds 2.0 \
  --sample-seconds 5.0 --sample-interval 0.005 \
  --route-state-interval 0 --tail-freeze-check-seconds 0.75
./build/lezac_cpp --debug-explosion-playback-oracle \
  /tmp/lezac-lane-result-3ed3-runtime/explosion_playback_oracle_original_candidate.txt
```

The wrapper aliases `--offset forward` and `--offset reverse` select the
`1000:3D3F` and `1000:3ED3` final result-write probes respectively; raw
`3D3F`/`3ED3` forms remain accepted for address-level retry notes. Dry-run
output and full-capture manifests include both `offset_labels=...` and
`offset_addresses=...` so targeted reruns can be audited from the first status
line; successful full captures also print the manifest path.

Lane-result handoff checklist:

```text
lane_result_status=reverse_original_runtime_capture_promoted_forward_seeded_promoted_natural_forward_pending
lane_result_blocker=natural forward 3D3F default/timing/before-bomb routes loaded patch but did not freeze
lane_result_preflight=python3 tools/check_explosion_lane_result_preflight.py .
lane_result_wrapper_output_check=python3 tools/check_explosion_lane_result_wrapper.py .
lane_result_wrapper_dry_run=python3 tools/capture_original_lane_result_runtime.py /tmp/lezac-lane-result-runtime . --dry-run --skip-oracle
lane_result_wrapper_capture=python3 tools/capture_original_lane_result_runtime.py /tmp/lezac-lane-result-runtime . --approve-procmem --approve-runtime-instrumentation
lane_result_reverse_capture=python3 tools/capture_original_lane_result_runtime.py /tmp/lezac-lane-result-runtime-20260506-reverse . --approve-procmem --approve-runtime-instrumentation --offset reverse
lane_result_forward_seeded_capture=python3 tools/capture_original_explosion_procmem.py /tmp/lezac-lane-result-forward-seeded-after-20260506 . --approve-procmem --mode regular --freeze-ghidra-offset 1000:3D3F --freeze-patch-mode lane-result-cs-scratch --approve-instrumentation --approve-runtime-instrumentation --runtime-freeze-after-bomb-seconds 0.0 --runtime-seed-debris-writeback --level-start-seconds 1.5 --right-hold-seconds 2.0 --sample-seconds 5.0 --sample-interval 0.005 --route-state-interval 0 --tail-freeze-check-seconds 0.75
lane_result_forward_route_step_capture=python3 tools/capture_original_lane_result_runtime.py /tmp/lezac-lane-result-forward-routestep-x2p0-c0p5-20260506 . --approve-procmem --approve-runtime-instrumentation --offset forward --route-step x:2.00 --route-step c:0.50 --sample-seconds 5.0 --sample-interval 0.005 --route-state-interval 0 --tail-freeze-check-seconds 0.75
lane_result_forward_alias=forward -> 1000:3D3F -> expected_old_bytes=268805 -> scratch=CS:F280
lane_result_reverse_alias=reverse -> 1000:3ED3 -> expected_old_bytes=268805 -> scratch=CS:F280
lane_result_forward_seeded_fixture=tests/fixtures/dosbox/explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded.txt
lane_result_forward_seeded_runtime=CS:IP 01ED:3D3F DS=0C8F seed_call=01ED:4C96 seed_helper=01ED:3BB2 scratch=01ED:F280 output=00fa far=0C44:78D2 target_before=f3 visual_claim=0
lane_result_forward_route_step_fixture=tests/fixtures/dosbox/explosion_playback_oracle_original_3d3f_lane_result_route_step_no_freeze.txt
lane_result_forward_route_step_runtime=route=x:2.00,c:0.50 CS=01ED DS=0C8F freeze=0 scratch=0 lane_flag=05 lane_word=0004 lane_target=072c reverse_input=fb visual_claim=0
lane_result_reverse_fixture=tests/fixtures/dosbox/explosion_playback_oracle_original_3ed3_lane_result_runtime.txt
lane_result_reverse_runtime=CS:IP 01ED:3ED3 DS=0C8F scratch=01ED:F280 output=00ef far=18B3:3FE6 target_before=de
lane_result_offset_addresses=default 1000:3D3F,1000:3ED3; reverse,forward 1000:3ED3,1000:3D3F
lane_result_static_tail=8b46f63b46f075c58a46f3c47e04268805c9c20600
lane_result_expected_manifest=/tmp/lezac-lane-result-runtime/manifest.txt
lane_result_expected_forward_candidate=/tmp/lezac-lane-result-runtime/3d3f/explosion_playback_oracle_original_candidate.txt
lane_result_expected_reverse_candidate=/tmp/lezac-lane-result-runtime/3ed3/explosion_playback_oracle_original_candidate.txt
lane_result_acceptance=promote only candidates that parse with --debug-explosion-playback-oracle and visual_claim remains 0
```

## Next Step

Use the now-working `45FA`/`492F`/`4B3F`/`4B61`/`4B6A`/`4C75`/`4C96`/`4CA9`
visible-playback freezes plus the lane-helper/writeback fixtures to find a
natural debris-side writeback route/timing gate. Prefer safe runtime
trampolines for mid-helper writeback captures, including the new
`3D3F`/`3ED3` final result-write probes, and keep promoted fixtures explicit
about `visual_claim=0` until frame-table/sprite semantics are proven.
