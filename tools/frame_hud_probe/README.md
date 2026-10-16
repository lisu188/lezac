# Original HUD And Keyboard Frame Bridge

This observer follows unchanged original `game:79E8..7A13`, including the
conditional objective HUD update, palette requests, original digit rasterizer,
runtime stack checks/Move and the complete CRT/BIOS keyboard drain. Earlier
pacing and keyboard observers and fixtures remain unchanged.

`build.py --source /dev/shm/PINNED-DOSBOX --out /dev/shm/HOST` copies pinned
configured DOSBox 0.74-3 sources and build products, then adds read-only getters
and observation. `rebuild.py --host /dev/shm/HOST --retain /dev/shm/OLD-HOST`
supports incremental task-owned rebuilds after first retaining the old binary,
probe and build metadata with identity checks. Original CPU core and callback
bodies remain unchanged. Reused products are not clean-build reproducibility.

```sh
python3 -B tools/frame_hud_probe/capture.py --dosbox /dev/shm/HOST/dosbox-0.74-3/src/dosbox \
  --repo /path/to/ORIGINAL --run r1 --out /dev/shm/CAPTURE --observe-seconds 120
```

Capture uses silent, fixed-6000 normal-core gameplay and ordinary menu/Z/Left/A
input. No guest RAM, instructions, clocks, IRQs or gameplay state are seeded,
patched or paused. It retains the first complete bridge in each encountered
unchanged/word-counter/byte-counter/both-counter class. Completion requires an
unchanged class and an updated class; isolated counter paths have separate
controlled coverage, not invented natural coverage.

Besides existing CPU, stack, BIOS, sound and device observations, the trace
records 86 HUD-global bytes, 640 initial digit-atlas bytes and 272 indexed HUD
pixels. A direct host getter reads `vga.fastmem` only under the recorded VGA,
chain-four, linear-base and bank profile. It does not issue guest video reads
that could mutate emulated latch state. Raw RAM/PNG checkpoints and the exact
launch/input/host recipe remain local.

Run the projector from `tools/`:

```sh
python3 -B -m frame_hud_probe.project --capture /dev/shm/CAPTURE \
  --out /dev/shm/PROJECTION --exe /path/to/LEZAC.EXE
```

It independently rehashes raw RAM/PNG samples and checks all 43,552 relocated
original code bytes, then emits CPU and clock/device projections. Frozen
validation authenticates compressed observations and all retained sources,
including the incremental rebuild producer, but reports zero raw RAM files
verified because those files are not published.

The C++ replay drives REP transfers from the computed clock's initial state.
Later budgets, flags, IRQ positions, memory and device states are comparison
targets only. The updated-HUD window uses the retained VGA/idle/silent model.
The short unchanged window has an initially dirty render palette; its core-only
clock adapter rejects every device callback or millisecond ticker boundary.
It does not widen the production device-clock profile.

`oracle.py --exe ORIGINAL --capture CAPTURE --out /dev/shm/ORACLE` uses Unicorn
2.1.4 to execute real original HUD callees on 17 explicit controlled profiles.
There are no original-call stubs or instruction patches. A separate unobserved
engine agrees in registers and all 1 MiB of memory; only compact owned inputs
and endpoints are published. Controlled one-transfer/unlimited C++ copy modes
prove endpoint equivalence, not matching Unicorn/DOSBox dispatch counts.

The full App scheduler, entire-frame raster state, active IRQ1/repeat, dirty
palette callback effects and downstream player/render work remain incomplete.
