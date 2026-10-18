# Historical Original Iteration Work

## Timing Boundary

The frozen `frame_pacing` corpus already contains consecutive natural game
`7903` entries. These delimit complete original iterations, not merely calls to
CRT delay. `analyze_frame_iteration_work.py` authenticates the unchanged pinned
manifest, every fixture byte, original assets, capture sources and both complete
capture recipes before partitioning those intervals.

The observations are historical: this change performs new analysis of existing
original captures, not a new original run. No guest code, state, input, clock or
fixture changed. The counter-wrap control in the unit tests is synthetic.
The runs use only the recorded `1` and `Return` menu input; they are not
steady-state timing or seven-level gameplay coverage.

| Run | Complete iterations | Normal-core dispatches | Work-clock credits | Profile milliseconds, min/max/mean |
| --- | --- | --- | --- | --- |
| r2 | 147 | 47,300,383 | 54,511,720 | 57.7572 / 66.1870 / 61.8047 |
| r3 | 147 | 47,300,313 | 54,511,667 | 57.7572 / 66.1870 / 61.8046 |

Both captures use the authenticated normal-core fixed-6000 profile. Dividing
work-clock credits by 6000 gives milliseconds in that emulator profile, not
host wall time, physical CPU cycles or a hardware frame-rate claim. Dispatches
are not interchangeable with those credits: REP transfer accounting and other
normal-core scheduling work remain included. Timer and keyboard IRQ work is
included, not subtracted.

## Partition

Each complete iteration is split into `7903..79E8` (pacing) and
`79E8..next 7903` (HUD, keyboard service, rendering and gameplay). The latter is
not an isolated actor-update cost. The two parts add exactly to the complete
iteration for both dispatch counts and work-clock credits.

The post-delay part alone costs 298,564 to 301,270 credits across both runs,
about 49.761 to 50.212 profile milliseconds. Its work is not represented by the
production host loop's fixed 40.8 ms interval in `src/app/governed_loop.hpp`.
Neither the full-iteration mean nor the post-delay minimum is a replacement
constant: actual work, CRT calibration, DOS time and the feedback delay must
share a clock. Each trace's last frame entry remains explicitly unclosed;
ending at a completed delay would still not prove a completed iteration.

## Reproduction

Eight new tests pass on Linux. Native Windows passes seven and explicitly skips
the temporary-symbolic-link control because that host denies link creation.
All 18 existing pacing fixture tests and five selected CTests pass, including
the original-backed C++ counter/delay model and pacing calculation.

```sh
env PYTHONDONTWRITEBYTECODE=1 SDL_AUDIODRIVER=dummy TMPDIR=/dev/shm \
  python3 -S -B tools/analyze_frame_iteration_work.py \
  --out /dev/shm/lezac-iteration-work.json
python3 -S -B tools/test_frame_iteration_work.py -v
```

The output must be new; existing files, including symbolic links, are not
replaced. Source and tests are portable to native Windows. This analysis does
not connect the production App to the recovered work clock, recover individual
post-render instruction costs, extend campaign proof or establish whole-game
parity. The next timing recovery must retain that distinction and account for
the actual remaining work rather than introducing a nominal per-frame budget.
