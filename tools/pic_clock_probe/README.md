# Read-Only PIC/PIT Observation

The recovery-only observer exports normal-core budgets, PIC state, PIT0 phase,
and bounded queue identities without modifying guest CPU/register/memory state.
See `docs/recovery/pic_work_clock_20261016.md` for evidence and limitations.

Build from the pinned, configured baseline host:

```sh
python3 -B tools/pic_clock_probe/build.py \
  --source /dev/shm/lezac-work-oracle-t190/dosbox-0.74-3 \
  --out /dev/shm/new-pic-host
```

The builder reuses configured products and records source/patch/binary hashes.
It does not establish a clean reproducible binary build. Capture in a private
Xvfb, with a canonical source checkout and a fresh RAM output directory:

```sh
python3 -B tools/pic_clock_probe/capture.py --run r2 --repo /workspace/lezac \
  --dosbox /dev/shm/new-pic-host/dosbox-0.74-3/src/dosbox \
  --out /dev/shm/new-pic-observation --observe-seconds 600
```

Every input command is recorded. A completed target requires an actual IRQ0
entry inside a full-memory DOS window and a subsequent caller return. Timeout,
unknown screens, failed commands, missing terminal markers, and changed assets
are not success. The input route never interprets a stationary frame counter
alone as a prompt, and it sends at most twelve recognized prompt inputs.

`project.py` creates local projections from a completed capture and verifies
its retained raw RAM/PNG checkpoint hashes. The frozen checker instead accepts
only exact repository fixture identities, without claiming raw-file validation:

```sh
python3 -S -B tools/check_pic_work_clock_fixture.py \
  --cpu-projection /dev/shm/pic-cpu.bin --clock-projection /dev/shm/pic-clock.bin
```
