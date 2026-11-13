# Corpse Animation Before Dispatch

This extends PR #337 at `157db1ba75d8b07f7568dca2bcc2f62569f973f9`.
It does not replace that PR's pending exact-head review or CI requirements.

## Production Repair

The shared animation prologue at original `1000:6078..615A` runs before
behavior dispatch. The C++ `updateMonsters` path previously returned from
behavior 2 before calling that prologue. Both ordinary corpses and boss
debris therefore skipped it. The repair moves the existing production
advance and diagnostic observer before the corpse branch, after the same
order/alive filters. Living-monster behavior and the GRAN loader are unchanged.

Natural fatal conversion normally disables animation. Nonzero corpse modes
in this regression are explicitly seeded, not evidence of a natural route.
The change also preserves the original mode-3 backup restoration at the
shared boundary; it does not establish production physical-slot inheritance.

## Original Evidence

The existing producer now accepts explicit actor kind and behavior options.
The original executable and called instructions remain unmodified. For kind
12 and kind 30, both with behavior 2, 53 cases each execute 12 consecutive
original animation prologues. Each kind has an independent repeated capture.
Every recorded active cursor, descriptor write, instruction count, full
1 MiB memory digest, and 14-register observation agrees between repeats.
Observed and unobserved executions also agree over all memory and registers
after every boundary. There are 1,272 unique boundaries, repeated once,
10 backup restorations and 413 descriptor-write boundaries per kind/run.

All four generated fixtures are byte-identical to the already pinned
`tests/fixtures/monster_animation_original.txt` (SHA-256
`5cb198b666f4cca3c0167ef595e4472b908bc7a1cfbdb58d5c63eb363309ddf1`).
No new fixture expectation is invented from C++ output.

The four reports and exact executor source are retained in
`docs/recovery/evidence/corpse_animation_prologue_20261009/`.
Reproduce each original capture with dummy audio and Unicorn 2.1.4:

```sh
env SDL_AUDIODRIVER=dummy python3 -B tools/capture_original_monster_animation.py \
  --root . --out /tmp/new-original-corpse-capture \
  --actor-kind 12 --actor-behavior 2
```

Use kind 30 for boss debris, a new output root for each repeat, and
`--unicorn-path` only when required by the local dependency installation.
The observation range ends before behavior dispatch. It proves the shared
prologue's inputs/outputs for corpse-tagged records, not a full corpse tick.

The retained T82 full actor-pass captures additionally establish actual
ordering: in `delayed_mode3`, the first two complete original actor passes
write the animation bytes at `1000:6088..6137` (with the seven-byte restore
at `1920:091F`) before corpse motion at `1000:7568..7588` and the timer write
at `1000:75B0`. Their resulting active bytes and descriptor words equal the
first two `mode3_upper` prologue observations. These are earlier captures,
not newly recorded whole-tick or natural-gameplay evidence.

## Compiled App Regressions

`corpse_animation_original_app` runs the actual `App::updateMonsters` path
for 106 cases and 1,272 updates. Its observer stops immediately after the
shared prologue and verifies that corpse motion, fractions, timer, kind and
behavior have not yet been dispatched. The existing strict fixture reader
checks all seven active and backup bytes, advance decisions and visible
sprite indexes. The living-monster and GRAN regressions remain enabled.

`corpse_animation_skip_mutant` compiles the complete App with only the old
production prologue placement restored. The new diagnostic is unchanged.
It must return 1 with `monster animation production boundary not reached`;
any unrelated failure or success is rejected. Source/generated-source hashes,
stdout, stderr and per-attempt results are retained by CI on both hosts.
Eight stdlib tool contracts test generation and fail-closed checker behavior;
their mocked executions are not App runtime proof.

Run the focused suite after a testing-enabled build:

```sh
env SDL_AUDIODRIVER=dummy SDL_VIDEODRIVER=dummy ctest --test-dir build \
  --output-on-failure -R '^(corpse_animation_|monster_animation_|gran_usage_guardrail)'
```

Local validation is bounded to source guards, syntax, fixture/helper tests,
tool contracts and CMake registration because the Windows backing volume is
above its 90-percent guard. Hosted compiled-App results must be inspected
separately. Full corpse motion/expiry, raw actor ownership, natural campaign
coverage, sound fidelity and whole-game completion remain open. No broad
fidelity/completion flag is promoted.
