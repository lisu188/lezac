# Diagnostic Frame-Pacing Probe

This changes the emulator host only. It reads guest state and cannot be
represented as an official or bit-identical DOSBox executable. Instrumentation
can affect wall-clock key delivery; fixed emulated cycles are not that claim.

The source boundary is upstream DOSBox 0.74-3, archive SHA256
`c0d13dd7ed2ed363b68de615475781e891cd582e8162b5c3669137502222260a`, plus Ubuntu
0.74-3-5build2 distribution patches in their declared series. The patched normal
core remains byte-identical to upstream before adding the hook:
`0448bdcf6969b4dc6b925eb7c43986e2a76d0f215edcc6fb0bdc955fccd20e7b`.

Apply `normal_core_hook.patch` and copy `lezac_work_probe.h` beside
`src/cpu/core_normal.cpp`. Configure with `--disable-debug --disable-opengl` and
the existing SDL 1.2 development/runtime environment. The captured host used
GNU C++13.3, `-O2 -g -std=gnu++17`, no package installation, and preserved
release-generated Autotools files. The recovered game remains C++23. This is
build provenance, not a reproducible-host-binary claim.

The successful host SHA256 is
`b19be3dd86b5d6ee59e67ffd5c4d888069f8624b4d92499babe33f4ae168c7ef`.
Set `LEZAC_PACING_TRACE` to a new CSV path. Output is exclusively created and
capped at 10,000 records or 2 MiB. The signature at CS:01fc identifies relocated
module segments; complete code identity is verified separately by the producer.
The exit hook never reads guest memory, which may already have been freed.

The probe records selected data words and clock bytes at counter, DOS-time,
measurement, feedback and CRT-delay boundaries. `dispatch` counts normal-core
iterations, including REP continuations. `clock` is the pre-decode budget clock:

```text
PIC_Ticks * CPU_CycleMax + CPU_CycleMax - CPU_CycleLeft - CPU_Cycles
```

No IRQ work is excluded from these total frame observations. Neither dispatch
nor a semantic C++ step is assumed to equal a clock unit. No screen sampling is
synchronized with these records.

Acquire a new silent RAM-only run:

```sh
env SDL_AUDIODRIVER=dummy TMPDIR=/dev/shm PYTHONDONTWRITEBYTECODE=1 \
  python3 -B tools/frame_pacing_probe/capture.py --run new1 \
  --dosbox /dev/shm/pacing-host/src/dosbox --out /dev/shm/pacing-capture-new1
```

The standalone producer creates a private Xvfb display and clean emulator
environment. After read-only location, it waits 20 seconds and captures the
menu, presses `1`, waits four seconds and captures the intro, presses Return,
waits one second and captures gameplay, waits three and captures the middle,
waits five and captures late gameplay, then exits with host Ctrl+F9. Actual
monotonic times, checked commands, all five checkpoint hashes and terminal
status are retained in the recipe, including failure paths.

Analyze without overwriting prior evidence:

```sh
python3 -S -B tools/analyze_original_frame_pacing.py TRACE.csv \
  --recipe report.json --out NEW_REPORT.json
python3 -S -B tools/test_original_frame_pacing.py -v
```
