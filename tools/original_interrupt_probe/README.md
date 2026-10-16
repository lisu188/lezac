# Original Interrupt Probe

This recovery-only normal-core probe reads guest state before decode. It does
not write guest registers, guest RAM, instruction bytes or device ports. It
records selected registers, IF/TF/DF, 64 stack bytes, eight opcode bytes,
13 record-adjacent bytes, BIOS ticks and the emulator work clock. Arithmetic
flags are lazy in this host and are deliberately not claimed.

## Host Boundary

The configured baseline is the earlier DOSBox 0.74-3 recovery host, ELF SHA-256
`4d8eaba9db5e3f733b49c35f191eff98f1f5730035f7374c5c703693a080c8ac`.
Its upstream archive SHA-256 is
`c0d13dd7ed2ed363b68de615475781e891cd582e8162b5c3669137502222260a`;
Ubuntu 0.74-3-5build2 distribution patches and existing SDL 1.2 development
files were used. The baseline's normal-core source has the three-line
`normal_core_hook.patch` already applied and SHA-256
`4aa44efa8c6d8788f23d6bcc29d24beb4a4123d3e442b51f03a03bdbdf8c6516`.
The unmodified upstream normal-core source SHA-256 is
`0448bdcf6969b4dc6b925eb7c43986e2a76d0f215edcc6fb0bdc955fccd20e7b`.

`build.py` copies that configured tree and its existing products into a new
RAM directory, replaces only the observation header and rebuilds with `make`.
The captured tool uses GNU C++13.3, `-O2 -g -std=gnu++17`; the game remains C++23.
Optional OpenGL/SDL_net/SDL_sound paths are disabled. No packages are installed.
The existing SDK stays external and read-only. This is a pinned partial host
rebuild, not a clean reproducible-ELF claim. Debug paths can affect the ELF hash.

```sh
env TMPDIR=/dev/shm python3 -B tools/original_interrupt_probe/build.py \
  --source /dev/shm/lezac-work-oracle-t190/dosbox-0.74-3 \
  --out /dev/shm/NEW-IRQ-HOST
```

The observed corrected host ELF SHA-256 is
`b2ecf617bea4c1b31ba7da8845b31f448bd0018c6ba60d6fe37fff8d9de9d5a3`.
The analyzer accepts this exact observation profile; a different host requires
explicit new provenance and profile validation, not relabeling old fixtures.

## Capture

Use a new output directory for every attempt. The producer runs a private
Xvfb display, disables autorepeat and all audible output, copies shipped assets,
and seeds only the isolated record file. Rank eight uses seven zero scores;
the rank-seven control uses six zeros and a final minus-one score.
Every shipped asset is checked against the canonical size/hash contract before
creating output or launching DOSBox. The exact verified bytes are copied, and
the shared contract source and its hash are retained with each capture.

```sh
env SDL_AUDIODRIVER=dummy TMPDIR=/dev/shm python3 -B \
  tools/original_interrupt_probe/capture.py --case rank8 --run rank8r1 \
  --dosbox /dev/shm/NEW-IRQ-HOST/dosbox-0.74-3/src/dosbox \
  --out /dev/shm/NEW-IRQ-CAPTURE
```

The exact command/environment, checked xdotool argv and times, eight game-key
events, ten PNG/RAM observations, full-code checks and every failure are retained
in `report.json`. No process pause or gameplay/RNG/heap/clock seed is used.
Host Ctrl+F9 is the final shutdown command, not a declared in-game key event.

The probe limits its trace to 4,096 rows/2 MiB and VGA snapshots to four.
The work clock is emulator fixed-cycle accounting, not hardware cycles or
natural wall time. Direct host VGA reads follow the verified chained mapping
`((i & ~3) << 2) + (i & 3)`, requiring M_VGA, compatible chain four and mask 255.
They avoid guest VGA read-latch side effects. Each binary stores 64,000 indices
and 768 raw DAC bytes. Screen PNGs are asynchronous; they are not relabeled as
simultaneous with the probe.

## Analysis

```sh
python3 -B tools/original_interrupt_probe/analyze.py \
  --trace /dev/shm/NEW-IRQ-CAPTURE/guest-irq.csv \
  --recipe /dev/shm/NEW-IRQ-CAPTURE/report.json \
  --capture-root /dev/shm/NEW-IRQ-CAPTURE --out /dev/shm/NEW-IRQ-REPORT.json
```

Without `--capture-root`, only the compact CPU/stack trace and recipe are
validated; `vga_files_verified=false` remains explicit. Pixel verification needs
the raw capture and Pillow. Ordinary CI uses only the Python standard library
and does not claim to replay omitted RAM, VGA or PNG content.
All geometry-command results must identify the bound window, 320-by-200 pixels
and a complete rectangle within the private 1024-by-768 display.
