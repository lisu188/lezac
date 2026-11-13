# CRT Keyboard Observation

This separate observer follows the unchanged original CRT KeyPressed and ReadKey
calls reached naturally from the game at `game:7A00` and `game:7A09`. The earlier
pacing observer and frozen fixtures are not modified. `build.py` copies pinned
DOSBox 0.74-3 sources and existing build products, adds read-only observation and
records source, observer, patch, getter and executable identities. Reused build
products are not a clean-build reproducibility claim. The original CPU core and
BIOS INT16 handler bodies remain unchanged.

`capture.py --dosbox HOST --repo ORIGINAL --run r1 --out /dev/shm/CAPTURE` launches the
original silently under a fixed-6000 normal core. It uses ordinary menu input,
a held Z key, Left, and a later A tap; it performs no process-memory writes,
guest instruction patches, pauses, clock seeds or gameplay seeds. Six bounded
call categories distinguish empty, available and pending-byte KeyPressed from
normal, extended and pending-byte ReadKey. Each window records the original
20-byte CB_INT16 stub, registers, control flags, stack, BIOS ring, CRT globals,
sound globals and relevant existing clock observations. The raw capture retains
five RAM/PNG checkpoints, the exact input/launch recipe and terminal markers.

Run the projector from `tools/`:

```sh
python3 -B -m crt_keyboard_probe.project --capture /dev/shm/CAPTURE \
  --out /dev/shm/PROJECTION --exe /path/to/LEZAC.EXE
```

It independently verifies raw RAM/PNG identities and all 43,552 relocated
original code bytes before emitting the CPU projection. Projection is not C++
execution proof. Frozen-fixture checking authenticates retained sources and
compressed data but reports `raw_ram_files_verified=0`, since raw RAM is not
published. The current corpus has no observed IRQ entry; separate timer boundary
unit tests are not natural keyboard/IRQ timing proof.

Two independent generators add bounded evidence:

```sh
python3 -B tools/crt_keyboard_probe/build_classifier.py \
  --source /path/to/pinned/src/ints/bios_keyboard.cpp --out /dev/shm/CLASSIFIER
python3 -B tools/crt_keyboard_probe/pending_oracle.py \
  --exe /path/to/LEZAC.EXE --out /dev/shm/PENDING
```

The first extracts the exact pinned original `IsEnhancedKey` function and
executes all 65,536 words in a native driver. This is original-source classifier
execution, not whole BIOS handler execution. The second uses Unicorn 2.1.4 to
execute unchanged relocated original CRT pending-byte paths and the real
CheckBreak near call for all 255 nonzero carry bytes in both functions. No BIOS
provider, interrupt calls, original-call stubs or instruction patches are used.
A separate unobserved emulator agrees with all 510 full endpoint states.

The C++ operation deliberately stops at CheckBreak's console-output handoff.
Active IRQ1/repeat production, console/INT23 termination, the game's keyboard
drain/HUD tail, production App cadence and whole-frame parity remain outside
this recovered stage.
