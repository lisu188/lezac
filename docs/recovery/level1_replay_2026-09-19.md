# Level 1 event replay and first-divergence infrastructure

## Follow-up

The [2026-09-21 original full-frame recovery](level1_fullframe_2026-09-21.md)
changes production gameplay drawing to the original pre-actor boundary and
adds the explicit `cpp-pre-actors-v2` trace contract. The v1 description below
is historical; validators retain v1 support without treating it as v2.

## Scope

This batch adds a production-path C++ recording/replay tool, not a complete
Level 1 original-game oracle. The runner begins with the same load, SDL setup,
level reset and menu state as `runInteractive`. Route events select one or two
players and acknowledge the introduction through `processEvents`/`onKey`.
An explicit held-scancode snapshot feeds the existing `controlsFromKeyboard`
adapter because synthetic SDL queue events do not themselves maintain that
snapshot. `update`, `updateWithControls`, actor dispatch and `draw` remain the
production implementations. There are no per-tick position, velocity, map,
health, inventory, progress or RNG corrections.

The application-owned RNG is initialized once from the route seed, before
loading resources and generating the backdrop. Replay-only presentation time
replaces wall-clock sampling for introductions and results. Normal interactive
play still reads `SDL_GetTicks` and uses the unchanged governed loop. The
runner advances one update per route tick; it does not test wall-clock pacing,
physical keyboard IRQs, operating-system typematic timing or the SDL device's
physical keyboard state. Sound requests still execute but audio is forced to
`dummy`, and record writes are redirected into the output directory. The
shipped record data is still loaded as the initial record state.

## Commands

Build normally, then record two independent executions and compare them:

```sh
python3 tools/level1_fidelity.py record --exe build/lezac_cpp --route tests/routes/level1_input_smoke.route --out /tmp/lezac-level1-a
python3 tools/level1_fidelity.py record --exe build/lezac_cpp --route tests/routes/level1_input_smoke.route --out /tmp/lezac-level1-b
python3 tools/level1_fidelity.py validate /tmp/lezac-level1-a
python3 tools/level1_fidelity.py compare /tmp/lezac-level1-a /tmp/lezac-level1-b --out /tmp/lezac-level1-diff
```

`record` forces both SDL drivers to `dummy` and selects original, not JSON,
assets. All outputs must be new directories; existing recordings are not
overwritten. `--root` selects the source/asset directory. `--timeout` bounds
execution and defaults to 600 seconds. A failed or interrupted native capture
has no valid completion record and is not accepted as a complete bundle.

The native command is `lezac_cpp --replay-level1 ROUTE OUTPUT_DIR`. It produces
raw trace/frame files; use the Python wrapper to add the checked SHA-256
manifest and copied route needed by `validate` and `compare`.

## Input contract

The UTF-8 route begins with `LEZAC_LEVEL1_ROUTE_V1`, followed by exactly one
each of `seed`, `ticks` and `step_us`, ordered key events, then `end`.
`seed` is unsigned 32-bit; `ticks` is 1..20000; `step_us` is 1000..1000000.
The smoke route uses 40800 microseconds. Event ticks are zero-based; trace
update ticks are one-based, with tick zero reserved for the initial frame.

Events have the form `event TICK ACTION KEY`, where ACTION is `down`, `up`
or `repeat`. Ordering among events at the same tick is preserved. Releasing
or repeating a key that is not held and duplicate down events are rejected.
Blank lines and LF/CRLF are supported; comments are not part of the format.
The allowed keys are `1`, `2`, `return`, `escape`, `l`, `s`, `e`, `r`, `p`,
`z`, `x`, `m`, `n`, `c`, `left`, `right`, `up`, `down`, and `insert`.
Developer level skips and gameplay mutation controls are not accepted.

Short down/up pairs are delivered in order through the real event handler.
Their gameplay result is not assumed to equal a held input: for example,
releasing the fire key before the update clears the current production latch.

## Trace and comparison contract

The JSONL trace has an explicit header and completion footer. Each tick has
`input`, optional `after_nonplayers`, `post_update`, and `present` checkpoints.
Menu, pause and introduction ticks can omit the actor checkpoint. Sequence,
tick, clock and event agreement are checked independently against the route.

State observations cover both players' motion, fractional carry, animation,
displayed descriptors, health, inventory, cooldowns and waiting state; the
mutable tile/word maps; objectives; shared RNG and allocation order; typed
actors, flames, debris, collapse and spawners; palette and backdrop fingerprint;
and UI/reentry/results state and the sound latch. These observations are a
versioned diagnostic projection, not an assertion that every private field or
future behavior is captured. In particular, later-level boss observations,
waveform/device state and full record-entry state are not part of this schema.

Every `initial` and `present` checkpoint writes a full 320x200 RGB PPM, including
the HUD and overlays. Comparison checks actual RGB bytes as well as the trace
fingerprints and file digests; FNV collisions do not establish frame equality.
The manifest pins the executable, copied route, trace, frames and eleven input
assets with SHA-256 and records the available source revision/dirty state.
Those hashes establish bundle integrity, not a signature or an independently
trusted original-game recording. A manifest does not prove that a binary was
built from its stated checkout; preserve the build log and revision separately.

The first-divergence report names the sequence, tick, phase and field path.
Map/palette hex differences identify the first differing byte. A report
directory also receives the corresponding full reference, candidate and
absolute-difference PPMs, even when the first mismatch was state rather than
pixels. Both traces are validated to their terminal records: an early
mismatch does not conceal later truncation or a missing frame. An optional
actor-phase difference is reported as a divergence, not a parser failure.

Exit codes are 0 for a valid recording/bundle or equal comparison, 1 for a
valid but divergent comparison, and 2 for invalid input/evidence or execution
failure. Unknown schemas, original-source impersonation, unsupported parity
claims, unsafe paths, corrupt digests, missing frames, reordered checkpoints,
duplicate JSON fields, malformed routes and inconsistent counts are rejected.

## Validation

`ctest --test-dir build -R '^level1_replay$' --output-on-failure` runs the
production integration suite. It executes two independent 180-tick recordings:
714 checkpoints, 181 full frames and 11,584,000 compared pixels. The smoke route
covers menu/intro input, movement, repeated fire, pause/resume, jump, backdrop
and viewport controls. It does not complete Level 1.

The new runner also replays five historical original control streams by
converting their normalized inputs to physical key names and beginning each
C++ run through the normal menu/intro path. All 445 original X/Y, VX/VY and
fractional-carry samples match without initializing the player from a captured
state. The existing fixture bytes are pinned with SHA-256, allowing only
LF/CRLF normalization. Original evidence and its limitations are documented in
[player movement recovery](player_walk_runtime_2026-09-05.md). This batch does
not independently recapture the DOS original; it verifies a new event-driven
consumer of that existing motion evidence. It does not compare original
animation, timing, HUD, audio or full frames for these five streams.

Additional tests cover two-player ownership, a same-tick fire tap, replay
clock arithmetic, source-asset preservation, malformed routes, provenance
mutations, state/phase divergence, late truncation and a one-pixel mutation
at the bottom-right corner outside the main playfield. The latter must report
exactly one differing pixel and produce the three comparison images.

## Remaining qualification work

The schema deliberately declares `source=cpp` and
`phase_model=cpp-post-update-v1`. The original presents at a different recovered
boundary; its images cannot simply be relabeled into this phase model. A new
original capture adapter must establish explicit phase correspondence,
reproducible initialization and instrumentation limits before cross-runtime
full-frame comparison is allowed.

`level1_route_complete` is a narrow port-route observation: a Level 1 results
state was followed by active, unpaused Level 2 with no intro/outro. It is not
original-evidence qualification. The smoke route reports false. Both
`original_fidelity_claim` and `port_functionally_complete` remain false,
including for future routes that reach that handoff.

Next: record a natural successful original Level 1 route, supply a validated
original-phase adapter, replay the same events, and fix the first divergence.
Complete original-frame agreement, natural Level 1 victory, death/reentry and
restart routes, two-player completion, and sound waveform qualification remain
open. No global completion or fidelity guardrail is weakened by this batch.
