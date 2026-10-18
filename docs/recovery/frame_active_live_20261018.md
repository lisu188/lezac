# Continuous Natural Active-Window Proof

## What Is Proven

Two naturally reached original level-one windows now run continuously from
game `7903` through `7A57`: pacing, HUD, keyboard drain, camera, world raster
and final VGA copy. Each window includes an original timer IRQ during rendering.
The C++ `FrameActiveOperation` uses only each atomic initial memory image and
initial device-clock state as inputs. Later CPU, memory, IRQ-index or clock
reference states are never injected into execution.

Both uninterrupted and per-instruction snapshot-restored replays pass:

| Check | Result |
| --- | --- |
| Original observed boundaries | 665,711 across two windows |
| Replayed CPU/clock/device comparisons | 1,331,422 across both replay modes |
| Computed IRQ deliveries | Four across both modes, all during rendering |
| Final memory | Complete 1 MiB image matches for each window in both modes |
| VGA and RGB | Both 320x200 images have zero differing pixels |
| Native Windows | MSVC `c++latest /W4 /WX` build and complete replay pass |
| Sanitizers | Complete replay passes ASan and UBSan |
| Compiled counterexamples | Render bypass, wrong IRQ return IP and wrong VGA destination are rejected |

Every observed instruction address, eight instruction bytes, general register
and control flag is checked. The PIC/PIT, device queue and palette state are
compared at every boundary. Arithmetic flags remain lazy in the original
observer, so this is not a new proof of every intermediate arithmetic or
undefined flag. Existing controlled original-backed component tests remain
separate evidence for complete endpoint flags.

## Read-Only Observation

The separate `tools/frame_active_live_probe/` pipeline retains the frozen
foreground tools unchanged. It extends a successfully rebuilt pristine-source
observer and preserves the previous instrumented binary, source and report.
All compiler-input bytes are verified before and after rebuilding. The normal
core observation hook and frozen device getters retain their pinned identity.

At the pre-decode entry and exit boundary the observer copies the 1 MiB guest
RAM backing and overlays the actual 64 KiB VGA fast-memory backing. The VGA
getter accepts only the known chained-VGA mapping. It copies memory directly,
not through VGA read handlers, so it does not modify read latches. These are
atomic CPU/memory endpoints on the original emulator thread. Separate SDL
screenshots remain asynchronous wall-clock observations.

The actual child executable, complete environment and mapped SDL image are
verified during capture. All 14 canonical original assets remain unchanged;
43,552 relocated code bytes are verified in each atomic snapshot and each
external RAM sample. No guest writes, instruction patches, clock seeds,
gameplay seeds, forced IRQs or pause commands are used.

The selector observes an initial stale-HUD window, then an idle-keyboard-device
and idle-sound candidate after ordinary input has finished. It chooses a PIT
event naturally due after the delay, but only a trace that actually contains a
render-time IRQ proves that coverage. Up to four candidates are allowed. The
replay supports the resulting no-port-read, timer-EOI-only profile; it does not
replay a recorded I/O script.

## Trace Bounds And Retention

The first attempt reached the endpoint of window one but hit its trace-size
guard during window two. Its failed report, partial trace and atomic snapshots
were retained separately. It was not promoted or silently resumed as success.

The successful observer uses versioned sparse CSV: an unchanged field is
represented by `~`, while the parser reconstructs the exact previous field.
Every entry is complete. Missing predecessors, wrong format markers, missing
terminal markers and dispatch gaps are rejected. This preserves all observed
values while avoiding repeated long memory fields. The record and size guards
remain one million records and 1 GiB of encoded expanded CSV.

The completed trace is 12,529,380 gzip bytes and 145,632,448 expanded encoded
bytes. The projector retains explicit failed reports, rejects existing output
directories and never labels a partial failure as successful. Ten Python
controls pass on Linux; seven format controls pass on native Windows, with
three Linux-only projector controls explicitly skipped there. All 36 selected
CTests pass, including the unchanged foreground/render corpora and fixture
rejection tests. No recovered runtime source changed in this proof step.

The subsequent exporter-family audit and repair are recorded in
`frame_export_aliases_20261018.md`. Six shared path-alias tests cover all four
exporters in this tree, and native Windows verifies all four pre-created
hardlink pairs without changing bytes or timestamps. Replay RAM/palette dumps
also reject existing entries and broken symbolic links before opening files;
three direct preservation controls pass, as does native Windows reuse of an
existing output prefix with all four prior files preserved.

## Reproduction

First build the pristine foreground observer using the pinned inputs documented
in `frame_active_20261018.md`, then extend that owned RAM host:

```sh
python3 -B tools/frame_active_live_probe/rebuild.py \
  --host /dev/shm/lezac-observer --retain /dev/shm/lezac-observer-before-active
env SDL_AUDIODRIVER=dummy python3 -B tools/frame_active_live_probe/capture.py \
  --run activeproof --repo . \
  --dosbox /dev/shm/lezac-observer/dosbox-0.74-3/src/dosbox \
  --out /dev/shm/lezac-active-capture --observe-seconds 120
python3 -B tools/frame_active_live_probe/project.py \
  --capture /dev/shm/lezac-active-capture --repo . --out /dev/shm/lezac-active-projection
cmake --build build --target lezac_frame_active_live_test
env SDL_AUDIODRIVER=dummy ./build/lezac_frame_active_live_test \
  /dev/shm/lezac-active-projection/cpu.bin /dev/shm/lezac-active-projection/clock.bin \
  /dev/shm/lezac-active-projection/cpp
python3 -B tools/frame_active_live_probe/render.py \
  --capture /dev/shm/lezac-active-capture --cpp /dev/shm/lezac-active-projection/cpp \
  --out /dev/shm/lezac-active-comparison
```

The final images compare actual original VGA indices and original palette with
the C++ operation's final VGA memory and independently computed palette. They
are not production-App screenshots. Natural state counts may vary between
captures; no counter or future reference state is used to force the result.

## Recorded Identities

| Artifact | SHA-256 |
| --- | --- |
| Active observer | `d51e46bd76556e76c04af88c0a7e7aade11a5b45cf13e17502f907d2ecf0a36f` |
| Actual SDL image | `b82090085ba665c89ea70909b9018a219c42029fdf9803e7d5e17c185d6d1d72` |
| Capture recipe | `8e6d645b46a671bf6e2a06656fd4fd9df015d954088ac63c78f9104d2a49b802` |
| Gzip sparse trace | `214db6ca7e510bb6cda25986e4b95688608415be0918507f466fe65bbda3fc63` |
| CPU projection | `d1e8da0418e6f24a2b4003820926b7f9bee324f2da05c5ca088451cc0601bb39` |
| Clock projection | `99b96b55a100c271079e7077301f932fad5e907df2fff2d828dde35aed662e73` |
| Window 1 initial RAM | `69c023352d38c5f8373d6bb7ce5f9866ba482d39d412ba22064772b814393c24` |
| Window 1 final RAM | `779239a97912f55a49f8aaf77a482ef69bea1c5b63a3a0dba0cd3848a89e8ab1` |
| Window 2 initial RAM | `03b8e36a1616881630e9d80227a7710586bc227129f3956f5c9ef01a2c07f201` |
| Window 2 final RAM | `4a600121560041e708f988b5dd49c43588bf324502b51585cf5343d78f44c5a4` |
| Window 1 RGB | `377f1b88c58976e86eee55f255c5dbec3516e67e4bed4a5960db63be9da9093d` |
| Window 2 RGB | `e01bb31698f0504a335651dee2d6bde9056551f5d687fa02960c521c07c549e0` |

## Remaining Goal Work

This proves two continuous active windows in one level, not a whole gameplay
iteration, continuous campaign, physical-device timing or owner acceptance.
Actor updates outside `7903..7A57`, active sound-device cases, input transitions
and the seven-level campaign still require broader original-backed proof.

The production App still uses its semantic renderer and host accumulator. The
next integration work must connect recovered operations to real allocation and
actor ownership, without routing live ticks through diagnostic snapshot copies.
Current raw RAM, traces and images remain ephemeral in RAM because C: is above
the repository disk guard. This change publishes source and evidence notes,
not full RAM or screenshots. A compact portable natural-window regression is
still needed; the new live harness is compiled in CI, but these raw natural
captures are not a frozen CI corpus. The full game goal remains incomplete.
