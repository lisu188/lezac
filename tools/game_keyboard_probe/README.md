# Game Keyboard Drain Observation

This observer follows the complete unchanged original `game:7A00..7A13` loop,
including its far CRT KeyPressed/ReadKey calls and pinned BIOS INT16 callback.
It records one complete window for each initially empty, ASCII and extended-key
queue class. The preceding conditional HUD update is outside these windows.
The retained CRT-only and pacing observers/fixtures are unchanged.

`build.py --source /dev/shm/PINNED-DOSBOX --out /dev/shm/HOST` copies pinned
configured DOSBox 0.74-3 sources and existing build products, then adds read-only
observation. Original CPU-core and BIOS-handler bodies are unchanged. Source,
patch, observer, getter and host hashes are recorded. Reusing build products
does not establish clean-build reproducibility.

```sh
python3 -B tools/game_keyboard_probe/capture.py --dosbox /dev/shm/HOST/dosbox-0.74-3/src/dosbox \
  --repo /path/to/ORIGINAL --run r1 --out /dev/shm/CAPTURE --observe-seconds 120
```

The run is silent, fixed-6000 normal-core gameplay. Ordinary menu input, Z hold,
Left and A input reach the windows; no guest instructions, RAM, clock/IRQ state
or gameplay state are patched or seeded. The bounded trace records registers,
control flags, stack, BIOS ring, CRT pending/break bytes, last-key byte DS:2058,
sound globals and existing clock observations. The exact launch/input recipe,
terminal marker and five raw RAM/PNG checkpoints are retained locally.

Run the projector from `tools/`:

```sh
python3 -B -m game_keyboard_probe.project --capture /dev/shm/CAPTURE \
  --out /dev/shm/PROJECTION --exe /path/to/LEZAC.EXE
```

It independently verifies raw sample hashes and all 43,552 relocated original
code bytes before emitting the CPU projection. Projection is not C++ execution
proof. The permanent frozen fixture excludes raw RAM and PNG payloads, and its
checker explicitly reports `raw_ram_files_verified=0`.

The three current windows contain 130 states and no observed IRQ0 entry.
Snapshot/restore replay compares later states but never injects them. The
separate timer-boundary unit tests do not prove natural IRQ eligibility.
Active IRQ1/repeat production, the HUD prelude, downstream player/render work,
production App integration and full frame/pixel fidelity remain incomplete.
