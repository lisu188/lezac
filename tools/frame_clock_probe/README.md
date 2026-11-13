# Read-Only Frame-Clock Caller Observation

The recovery-only observer exports normal-core budgets, PIC state, PIT0 phase,
and bounded queue identities without modifying guest CPU/register/memory state.
It also records the eleven foreground timing bytes through game:7966.
See `docs/recovery/frame_clock_caller_20261016.md` for evidence and limitations.

Build from the pinned, configured baseline host:

```sh
python3 -B tools/frame_clock_probe/build.py \
  --source /dev/shm/lezac-work-oracle-t190/dosbox-0.74-3 \
  --out /dev/shm/new-frame-clock-host
```

The builder reuses configured products and records source/patch/binary hashes.
It does not establish a clean reproducible binary build. Capture in a private
Xvfb, with a canonical source checkout and a fresh RAM output directory:

```sh
python3 -B tools/frame_clock_probe/capture.py --run r3 --repo /workspace/lezac \
  --dosbox /dev/shm/new-frame-clock-host/dosbox-0.74-3/src/dosbox \
  --out /dev/shm/new-frame-clock-observation --observe-seconds 600
```

Every input command is recorded. A completed target requires an actual IRQ0
entry inside a full-memory DOS-to-foreground window through the elapsed store. Timeout,
unknown screens, failed commands, missing terminal markers, and changed assets
are not success. The input route never interprets a stationary frame counter
alone as a prompt, and it sends at most twelve recognized prompt inputs.

`project.py` creates local projections from a completed capture and verifies
its retained raw RAM/PNG checkpoint hashes. The frozen checker instead accepts
only exact repository fixture identities, without claiming raw-file validation:

```sh
python3 -B tools/frame_clock_probe/project.py \
  --capture /dev/shm/new-frame-clock-observation --exe /workspace/lezac/LEZAC.EXE \
  --out /dev/shm/new-frame-clock-projection
python3 -S -B tools/check_frame_clock_fixture.py \
  --cpu-projection /dev/shm/frame-cpu.bin --clock-projection /dev/shm/frame-pic.bin
```

`oracle.py` is a separate controlled Unicorn instruction oracle. It seeds input
registers and memory explicitly, executes the unchanged 29-instruction arithmetic
phase, and makes no natural-gameplay claim. `check_frame_elapsed_oracle.py`
authenticates its compact frozen endpoint corpus without requiring Unicorn.
