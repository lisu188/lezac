# Original Software Real48 Display Observation

This recovery-only observer extends the DOS/PIC/elapsed window through the
original software Real48 display store at game:7997, stopping before game:799A
feedback. It does not change the live App loop. All original runs are silent.

```sh
python3 -B tools/frame_display_probe/build.py \
  --source /dev/shm/lezac-work-oracle-t190/dosbox-0.74-3 \
  --out /dev/shm/new-display-host
python3 -B tools/frame_display_probe/capture.py --run r1 --repo /workspace/lezac \
  --dosbox /dev/shm/new-display-host/dosbox-0.74-3/src/dosbox \
  --out /dev/shm/new-display-capture --observe-seconds 600
```

The host reuses configured products and records source/observer/binary hashes;
it is not a clean reproducible binary build. Capture selection observes the two
initial DOS controls, the first full foreground control, and near-PIT windows.
Inputs acknowledge only independently inspected menus/prompt masks. No clock,
IRQ, RNG, heap or gameplay state is seeded. Raw RAM/RGB/CPU are not atomic.

`project.py` verifies all local RAM/PNG checkpoint hashes and unchanged relocated
code bytes before projecting complete windows. A timed-out target requires
explicit `--allow-control`, and remains labeled failed with no completed-target
claim. A complete non-interrupted control is not natural-IRQ evidence.

`oracle.py` is separate controlled evidence. It executes unchanged original
software Real48 instructions for seeded CPU/memory inputs. It uses permanently
observed and never-observed engines, without memory-read hooks, and requires
their endpoints to agree. Zero denominators stop at the actual runtime-error
handoff, library:00E2, without executing the subsequent error-reporting subsystem.

```sh
python3 -B tools/frame_display_probe/oracle.py --exe /workspace/lezac/LEZAC.EXE \
  --out /dev/shm/new-display-oracle --exhaustive
```

The controlled corpus covers 256 detailed cases and every 16-bit numerator for
denominators 1, 66 and 65535. Only architecturally defined intermediate flags are
compared against Unicorn; final endpoint flags are compared in full. Pinned
DOSBox materialization of shift/MUL flags is encoded separately in C++.
