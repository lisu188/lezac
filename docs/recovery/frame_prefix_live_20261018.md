# Fresh Natural Frame Prefix

Two continuous original windows now prove the composed `7903..7EBB` prefix,
including pacing, HUD, keyboard draining, camera/raster/VGA rendering, spawners
and waiting/reentry prepass. These are fresh original observations from one
level, not controlled guest-state seeds or a completed original iteration.

## Observation Contract

The pristine pinned DOSBox builder and owned active-observer extension are
retained. The observer accepts only endpoints `7A57` and `7EBB`; capture
`--endpoint preactors` selects the latter. Its declared endpoint is bound to
the complete, independently verified child environment. The trace parser
requires consecutive dispatches, original render entry, post-render entry and
waiting entry before accepting the longer endpoint. Wrong endpoints, missing
stages and post-render IRQs promoted to render IRQs are rejected.

The observer copies the original 1 MiB RAM and real chained-VGA backing at
the pre-decode entry/exit boundaries on the emulator thread. It does not read
VGA through latch-changing handlers or materialize lazy arithmetic flags.
CPU comparisons use the observed defined/control-flag masks. Each atomic
snapshot and all five external memory samples preserve the 43,552-byte
relocated game code. All fourteen canonical original assets remain unchanged.

Only ordinary menu/game keyboard input is used. No guest register/memory
writes, instruction patches, clock/IRQ/RNG/heap seeds, forced IRQs or process
pauses are introduced. The actual executable, full environment and mapped
SDL image are checked while the child is live. Audio is dummy. No separate
uninstrumented baseline binary or host-wall-clock equivalence is claimed.

## Continuous Replay

The CPU/clock projector authenticates capture, source, host and asset identities.
The longer projection uses a distinct `LZPFLV01` magic; the existing active-only
projection keeps `LZACTV01`. A separately compiled shared test harness selects
`FramePrefixOperation`, not a diagnostic actor-state loader.

Only initial memory, registers and clock state are inputs. All later CPU,
clock, memory and palette data are comparisons, never injected reference
states. Both ordinary execution and restoration after every dispatch pass.

| Property | Value |
| --- | --- |
| Windows / observed states | 2 / 346258 and 320613 |
| Captured IRQs / render-time IRQs | 2+1 / 1+1 |
| Post-render boundary observations | 1084 and 83 |
| Captured post-render IRQs | 0 |
| C++ comparisons across both modes | 1333742 |
| Predicted IRQ / render IRQ deliveries across both modes | 6 / 4 |
| Complete endpoint memory compared | 4194304 bytes |
| Gzip / expanded trace bytes | 12565233 / 145910583 |

The full C++ replay passes Linux and native MSVC C++latest `/W4 /WX /O2` with
the same comparisons and predicted deliveries. A Linux resource check reports
2,560,316 KiB peak resident memory, zero swaps and zero filesystem I/O. Native
execution checks a physical-memory reserve first; it is not a Windows App or
physical-device test.

Both independent final VGA/palette comparisons match all 64,000 indices and
all 256 computed colors, totaling 128,000 pixels with zero differences. Shown
paired frames are fresh atomic original endpoints on the left and C++ operation
replay on the right, not SDL screenshots of the production port. The captured
post-render stages contain no natural IRQ; the eight computed post-render IRQ
controls remain a distinct restoration proof.

The natural replay rejects five independently compiled faults: renderer
bypass, IRQ return IP, VGA destination, waiting-stage bypass and ignored REP
clock grants. The unchanged compiled control passes. Three output guards
preserve existing RAM, palette and broken-link paths. All affected recovered
headers retain their source hashes. These natural controls complement the
eleven controlled/unit prefix mutations; they are not substituted for them.

## Identities

| Artifact | SHA-256 |
| --- | --- |
| Pristine observer before extension | `76886723670473d1db592cb7083aa856abc593aaa4a89af57fae923018a14d9c` |
| Extended observer | `a7d94a3c36618b456356c190415d70c9193c2c543899bac02e4d32d1fe2ef224` |
| Actual SDL image | `b82090085ba665c89ea70909b9018a219c42029fdf9803e7d5e17c185d6d1d72` |
| Capture recipe | `c99d6ab62ce3351a736f0f34df3d6b09ff8b8f53edc5fba0727df3d0c52ad908` |
| Gzip trace | `c07912d38d36d1bdfc4d327575dc92972c2a69ae151e55f2420773eeb7fd3712` |
| Expanded trace | `df6f7423b322e5200ec70df93333f423f6a33d4b23a4495b4b584068f0b3d2c8` |
| CPU projection | `b376421bf031873349d307e0d418f4380ae90b7538f88075332b91d10da9ad61` |
| Clock projection | `40db4eddc6ec6a8183dc28f30632cecb23a786a4b7ba3d19974908cefb1c3a55` |
| Window 1 initial / final RAM | `86dafd8bc1b10ea90b500f19ae546337e33d84ac6f07663fb8cd848609f09299` / `b267ed1c885232f4483783514ce46ae568b898ae436a0b80311f4cf68f98ae0d` |
| Window 2 initial / final RAM | `807897fedc113cbf48e2e9a6ed743e6573a3b0986b221168103c81b6d41ead05` / `2b61ef96583c47ad84bd8a607c11a880168281b112023923810e6c5ce63b3be8` |
| Window 1 / 2 RGB | `4e417a192993c2a4e0bd98fc4bd6cb0d048401dea9529593a4d7bfd7fd8a57fe` / `a61ff4ef973fcd52e6cec2795bcbc66bce50cc0b36e3e8e1f793347bef6f82b3` |

## Reproduction And Limits

Build the pinned pristine host as documented in `frame_active_20261018.md`,
then extend it with `tools/frame_active_live_probe/rebuild.py`, retaining the
previous identity. Use new output paths for each step:

```sh
env TMPDIR=/dev/shm SDL_AUDIODRIVER=dummy python3 -B \
  tools/frame_active_live_probe/capture.py --run prefixproof --repo . \
  --dosbox /dev/shm/observer/dosbox-0.74-3/src/dosbox \
  --out /dev/shm/prefix-capture --observe-seconds 120 --endpoint preactors
python3 -B tools/frame_active_live_probe/project.py --repo . \
  --capture /dev/shm/prefix-capture --out /dev/shm/prefix-projection
cmake --build build --target lezac_frame_prefix_live_test
build/lezac_frame_prefix_live_test /dev/shm/prefix-projection/cpu.bin \
  /dev/shm/prefix-projection/clock.bin /dev/shm/prefix-projection/cpp
python3 -B tools/frame_active_live_probe/render.py \
  --capture /dev/shm/prefix-capture --cpp /dev/shm/prefix-projection/cpp \
  --out /dev/shm/prefix-comparison
python3 -B tools/test_active_live_mutations.py --cxx g++ --prefix \
  --cpu /dev/shm/prefix-projection/cpu.bin \
  --clock /dev/shm/prefix-projection/clock.bin --out /dev/shm/prefix-mutations
```

Across the integrated and observer validation runs, 89 distinct focused CTests
pass. Thirteen format/provenance tests pass on Linux. Native Windows passes ten with
three explicit Linux-only projector skips. This source publishes the observer,
replayer, controls and hashes, not the full RAM, trace or PNG captures. They
remain ephemeral in RAM while C: exceeds the reserve threshold. The live test
target compiles in CI; a compact portable natural-prefix regression is still
missing. The frozen controlled post-render corpus is a separate CI contract.

This does not execute the actor/update tail after `7EBB`, complete the end-run
UI, integrate the instruction clock into the interactive App, cover continuous
seven-level play or arbitrary input/sound/device states, prove complete DAC
life cycles or physical timing, or establish whole-game parity. Those remain
requirements of the full recovery goal.
