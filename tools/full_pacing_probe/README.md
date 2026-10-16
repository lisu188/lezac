# Original Full-Pacing Observer

This read-only host observer selects original game `7903..79E8` windows that
include the counter gate, DOS GetTime, software Real48 display calculation,
adaptive delay feedback, sample carry and CRT.Delay return. It does not observe
the subsequent HUD refresh or key handling. The selection uses current guest
delay/calibration and the observed PIT deadline without changing either.

`build.py` reuses the pinned DOSBox 0.74-3 build and applies host-only probes.
`capture.py` runs silent, fixed-6000 normal-core gameplay through ordinary input.
It records at most two windows in bounded gzip CSV. `trace.py` streams and checks
the terminal marker, contiguous dispatches and observed timer entries. It never
loads the complete expanded CSV into memory.

Run the projector as a module from `tools/`:

```sh
python3 -B -m full_pacing_probe.project --capture /dev/shm/capture \
  --out /dev/shm/projection --exe /path/to/LEZAC.EXE
```

The projector verifies the retained raw RAM/PNG hashes and original relocated
code before emitting CPU input. The frozen fixture checker does not have raw
RAM files and explicitly reports zero raw RAM files verified. It authenticates
the compact capture and source identities, then reconstructs the same CPU
projection. Observed IRQ boundaries are declared external inputs. This is not
a coupled PIC/PIT or whole-game frame-timing proof.

`oracle.py` independently executes original game/Real48/CRT bytes under Unicorn
2.1.4 for controlled counter, feedback and complete-fragment inputs. DOS kernel
execution is replaced by an explicitly declared time/control-stack/PSP provider;
the C++ profile supplies 326 kernel/stub dispatches. No original game or CRT
call is stubbed. A permanently observed engine and separate unobserved engine
agree on complete-fragment endpoints. No memory-read hooks are installed.

The counter oracle uses exact 8/9-instruction budgets because a reused Unicorn
translation block can run across a changed stop address. Feedback uses a
separate engine with a fixed stop address. Failed earlier producers remain in
the local RAM evidence directories rather than being promoted to fixtures.

The retained first capture has a legacy `trace_clock` description mentioning
atomic callback boundaries. Its authoritative `callback_boundary_probe=false`
and probe source show these boundaries are disabled; the frozen manifest and
recovery report explicitly record that metadata defect. The recipe is not
rewritten after capture.
