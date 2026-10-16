# Diagnostic Normal-Core Probe

This probe is for original-game recovery only. It changes the emulator host and
must never be described as an official, bit-identical DOSBox run. It reads guest
state but does not write guest registers or memory. Instrumentation overhead can
affect host wall-clock input delivery even with fixed emulated cycles.

## Source And Build Boundary

The captured host uses upstream DOSBox 0.74-3 archive SHA256
`c0d13dd7ed2ed363b68de615475781e891cd582e8162b5c3669137502222260a`,
with Ubuntu `0.74-3-5build2` distribution patches in their declared series.
Those patches leave `src/cpu/core_normal.cpp` byte-identical to upstream, SHA256
`0448bdcf6969b4dc6b925eb7c43986e2a76d0f215edcc6fb0bdc955fccd20e7b`.
Archive, distribution descriptor, patch archive, SDL headers/runtime, and final
host hashes are recorded in the fixture manifest.

Copy `lezac_work_probe.h` beside `src/cpu/core_normal.cpp` and apply
`normal_core_hook.patch` to that verified source. Configure with
`--disable-debug --disable-opengl` and the existing SDL 1.2 runtime. The observed
tool build used GNU C++13.3, `-O2 -g -std=gnu++17`; the game project remains C++23.
OpenGL is not used by these surface-rendered observations. SDL_net and SDL_sound
development libraries were unavailable and those optional paths were disabled.

The local release-generated Autotools files were preserved byte-for-byte and
their timestamps refreshed. The only changed Autotools input was the official
distribution patch's correction of one diagnostic spelling in `acinclude.m4`.
No Autotools regeneration or package installation was performed. This explains
the build environment; it is not a reproducible-build claim for the host ELF.

## Observation Contract

Set `LEZAC_WORK_TRACE` to a new, exclusively owned CSV path in RAM. The probe
uses exclusive file creation, limits output to 22,000 records or 6 MiB, and
emits a clean `end` marker through `atexit`. Exit DOSBox normally, for example
with its host Ctrl+F9 command, so buffered rows are retained. The analyzer
rejects caps, missing end markers, unpaired IRQs, and incomplete fill samples.

Use `core=normal`, `cycles=fixed 6000`, software surface output and
`SDL_AUDIODRIVER=dummy`. Also disable DOSBox mixer/speaker/MIDI outputs.
The initial module signature is checked at `CS:01fc`; IRQ8/IRQ9 vector targets
are cached at that point. The trace scope ends before restoration or replacement
of those vectors. Verify the complete relocated guest code separately: the
signature alone is not whole-executable identity proof.

`dispatch` counts normal-core iterations, including possible REP continuations.
`clock` is sampled before decode as:

```text
PIC_Ticks * CPU_CycleMax + CPU_CycleMax - CPU_CycleLeft - CPU_Cycles
```

The `exclusive_*` fields remove observed IRQ8/IRQ9 handler work. They are not
wall-clock durations. CRT calls are recognized by entry and exact CS/IP/SS/SP
return tuple. Frame locals are valid only when `frame_valid` is one, including
the final `CS:0309` boundary before `LEAVE`. VGA presentation and external RAM
reads are not synchronized to these host probe records.

Replay a retained trace with:

```sh
python3 -S -B tools/analyze_original_work_clock.py TRACE.csv.gz NEW_REPORT.json --recipe RECIPE.json
python3 -S -B tools/test_original_work_clock.py -v
```

The analyzer never overwrites an existing report. The fixtures establish bounded
CPU-work facts only; live C++ scheduling and full frame-level fidelity still need
independent original-backed runtime validation.
Recipe mode binds the recorded trace size and SHA256 to the uncompressed bytes
actually analyzed and checks the declared execution contract and marker segments.
It rejects cross-run recipe/trace combinations. `capture_recipe_verified=true`
authenticates only an exact retained compact or complete recipe identity. New
reports may satisfy `capture_execution_contract_valid` without authenticating
their checkpoint metadata; `capture_recipe_verified` and
`capture_checkpoint_metadata_authenticated` are then false. Raw RAM/PNG files
are not supplied to this analyzer, so `raw_checkpoint_files_verified` is false
even when the saved metadata identity is authenticated.

Acquire a fresh, fully audited run after building the pinned host:

```sh
python3 -B tools/original_work_probe/capture.py --run r3 \
  --dosbox /dev/shm/lezac-work-oracle-t190/dosbox-0.74-3/src/dosbox \
  --out /dev/shm/lezac-work-clock-t190-r3
```

Use a new output path and run label for every attempt. The producer creates a
private Xvfb display, records the complete clean emulator environment, and drives
the exact seven-checkpoint route: wait 20 seconds, capture menu, `1`, wait four,
capture intro, Return, wait one, capture gameplay, Escape, wait five, capture
Game Over, `1`, wait fifteen, capture record prompt, `q`, wait 0.2, capture typed
name, Return, wait three, capture post-commit, then host Ctrl+F9. Recorded monotonic
before/after times and checked xdotool argv in each `*-recipe.json` are the actual
observations, not promises of instruction-aligned or atomic input delivery.
The initial read-only guest locator scan precedes the 20-second wait. Every
capture verifies unchanged relocated code and preserves its diagnostics in RAM.
