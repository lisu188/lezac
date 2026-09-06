# Flame Chain And Capacity Evidence

## Scope

Eight seeded original-game cases now verify chain construction, the 198-record
low-pool limit, descending processing, retirement and compaction. Each case
runs 65 uninterrupted actor passes in a fresh DOSBox child. The C++ replay
matches all 520 states, 3,492 flame-record observations, both terrain planes,
736 transient-effect states, target/player state and RNG, and renders every
checkpoint. It seeds 970 pre-existing records across the eight cases.

The existing production implementation matches these cases; this change adds
runtime evidence and regression coverage, not a new damage approximation.
It does not prove natural routes or pixel parity.

## Provenance

- Executable SHA-256:
  `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
- Canonical fixture: `tests/fixtures/flame_stress_lifecycle_original.txt`.
- Fixture SHA-256 at promotion (LF):
  `f11409ed60a4376c16349898c699b1b724ddd4081f0a34b5d7f4c015bbfc430a`.
- Raw combined capture: `build-codex-tmp/flame-stress-v2.txt`, with eight
  per-case TXT files and PNGs beside it. Promoted without editing.
- Original registers: CS `01a2`, DS/ES `0c44`, SS `18b3`, saved SP `3fe4`,
  BP `3ffe`. Hooks are Ghidra `1000:7EC5` / `1000:7EEA`, runtime
  `01a2:7EC5` / `01a2:7EEA`, before/after the non-player actor pass.
- The temporary-copy level seeder uses startup/intro/level-start waits of
  10/8/5 seconds. It seeds at an odd global frame and supplies no route input.
- Player visual position `(240,168)`, lives 99, spawners disabled. A kind-1
  monster with raw HP 255 starts at `(336,94)`, and a one-update small bomb at
  `(336,96)`. These match the prior airborne flame seed.
- Extra initial records and terrain writes are recorded explicitly on each
  case row. All writes occur at the initial case boundary, never between
  samples. Instrumentation is confined to the disposable DOSBox process.

Capture command after copying the shipped assets to the temporary directory:

```sh
python3 tools/capture_original_monster_damage.py --flame-stress \
  --run-dir /tmp/lezac-flame-stress-v2 \
  --out build-codex-tmp/flame-stress-v2.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The tool checks 28 original instruction windows: the prior 23 plus chain
dispatch `468E`, tile clearing `46B5`, constructor call `46D2`, low-pool
compaction `454B`, and timer/variant update `48E0`. The capacity comparison
at `403B` is already in the original 23. Runtime bytes are checked before
installing the hooks. The isolated initial trial is
`build-codex-tmp/flame-chain-clear-v1.txt`.

## Cases And Results

All names below have prefix `small_air_`. Cell 642 is `(42,10)` on the
60-column map, and the chain cell is 643. The moving seed has VX 79,
fraction X 64, timer 8 and mass 1, except where retirement is intentional.
Stationary capacity seeds vary their fractions, timers 2/3/4 and masses
1/9/221, so shifting records and the parallel mass array is observable.

| Case | Initial Pool | Counts At Samples 0..4 | Record Observations |
| --- | ---: | --- | ---: |
| chain_clear | 1 | 9,17,17,17,17 | 136 |
| chain_word | 1 | 9,17,17,17,17 | 136 |
| chain_retire | 1 | 9,16,16,16,16 | 129 |
| capacity_190 | 190 | 198,198,134,71,8 | 633 |
| capacity_191 | 191 | 198,198,134,70,7 | 628 |
| capacity_198 | 198 | 198,198,132,66,0 | 594 |
| chain_full | 190 | 198,198,135,72,9 | 639 |
| chain_reuse | 198 | 198,197,131,66,1 | 597 |

`chain_word` starts with unflagged word 1 under glyph 66; both are cleared.
`chain_retire` uses timer 1 for the incoming ray, proving that appended rays
survive its removal and retain their initial timer 8 until the next pass.

`chain_full` fills the remaining eight slots with the bomb's rays before the
chain scan. The chain tile is still consumed, but no new records are added.
`chain_reuse` starts full: slot 198 expires before moving slot 197 is visited.
Exactly one new ray is admitted, then slot 197 also retires. The new ray is
shifted down with its mass byte intact and is not advanced again that pass.

These observations agree with the instruction order: the constructor checks
capacity per record, the mover snapshots the initial high slot and descends,
and `452A` shifts all later live records and their mass bytes on removal.

## Validation And Limits

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-flame-lifecycle-original \
  tests/fixtures/flame_stress_lifecycle_original.txt build-codex-tmp/flame-stress-cpp
ctest --test-dir build -R '^flame_stress_lifecycle' --output-on-failure
```

The fixture checker tests LF/CRLF, missing completion, and 14 mutations.
The new mutations target seed mass/terrain, premature advancement of appended
rays, chain consumption at capacity, overflow and mass-array compaction.
All expected continuation bytes come from the unedited original capture.

Final local validation passed 451/451 tests in 26.75 seconds under Xvfb,
including the interactive UI check and all eight flame tests. Full log:
`build-codex-tmp/flame-stress-final-tests.log`. `git diff --check` passes.
The pre-existing snprintf warning in `debugDebrisShatterPlayback` is unchanged.

Frame sets are `build-codex-tmp/flame-chain-clear-cpp-v1/` and
`build-codex-tmp/flame-stress-cpp-v2/`. Original/C++ sample-4 pairs for
`chain_clear` and `chain_reuse` were inspected and shown to the user. The
original may display a previous render while stopped at the actor hook;
camera, effects and HUD differences remain. There is no pixel-parity claim.

Remaining scope includes flagged-word chain interactions with live debris or
collapse records, larger-weapon capacity boundaries, natural chain routes,
two-player flame interactions, shared actor-pool edge cases, and complete
render-phase alignment. Passing this fixture is not whole-game completion.
