# Active-frame composition and pristine observer rebuild

## Scope

`FrameActiveOperation` composes the recovered foreground (`7903..7A13`) and
render caller (`7A13..7A57`) on one `TimerIrqBus`. The handoff does not charge
an extra instruction. Snapshot restoration retains the active callee and a
suspended render-time IRQ. IRQ return updates both caller and callee registers,
including a partially consumed REP. The external work clock still owns IRQ
eligibility, instruction shadows, device callbacks and REP transfer grants.

Foreground runtime errors and keyboard break output stop without entering the
renderer. Masked, nested and post-terminal timer delivery is rejected before
memory writes. Dispatch, IRQ instruction and delivery counters remain separate
from CPU work credits.

This is an experimental composition, not production App integration. Its
foreground and rendering portions have original-backed checks separately.
The fresh natural trace stops at `7A13`; it does not validate one continuous
natural foreground/render frame or an IRQ during naturally captured rendering.
The render-time IRQ tests are controlled unit tests, not new original captures.

## Original-Backed Validation

- Frozen foreground: 216,686 CPU/clock/memory comparisons through the new
  handoff, with uninterrupted and per-instruction-restored replay.
- Frozen live foreground: 289,010 comparisons, 304 string transfers, two
  predicted IRQ deliveries across both replay modes, and no later reference
  state injected into the C++ operation.
- Controlled render corpus: 26 cases, 78 replays, 6,334,308 write comparisons,
  complete initial/final memory fingerprints and six expected runtime errors.
  All nonzero player-state values retain the existing render behavior.
- Controlled IRQ suspension: caller, camera, raster, copy and partial REP;
  180 timer instructions across five cases. Every IRQ instruction snapshot is
  restored before continuing. Four compiled faults are detected: missing callee
  register restoration, wrong IRQ return IP, post-terminal IRQ acceptance and
  dispatch at zero budget.
- Five builder-preflight tests include six input-digest rejection controls,
  non-RAM output, symlink escape, existing evidence and low RAM reserve.
- GCC C++23 and native MSVC `c++latest /W4 /WX` compile the focused targets.
  Native Windows controlled-render replay passes all 78 cases/replays.
  Address/undefined-behavior sanitizer coverage passes for the continuation unit.
- All 41 selected CTests pass, including unchanged renderer/foreground corpora,
  fixture rejection controls and neighboring active-player regressions.

## Pristine Observer

`tools/active_frame_probe/build.py` restores the existing **foreground-only**
read-only observer without depending on a retained configured build tree.
It accepts only the frozen observer header. It verifies the upstream DOSBox
archive, Ubuntu descriptor and patch archive, SDL development package and SDL
runtime. It applies the documented Ubuntu patch series before checking the
existing source pins, then adds the existing normal-core observation hook,
clock hooks and device getters. No existing fixture pins are relaxed.

The SDL SDK and runtime are extracted/copied into the new RAM-only build.
Nothing is installed. The complete build environment and expected SDL image
are recorded. Release-generated Autotools files keep their bytes; timestamps
alone are refreshed. Compiled source and release-generated file hashes are
checked again after building. A terminal build report records failure as well
as success. No uninstrumented baseline binary is claimed or fabricated.

Example with externally acquired, pinned inputs:

```sh
python3 -B tools/active_frame_probe/build.py \
  --archive /dev/shm/source-cache/dosbox_0.74-3.orig.tar.gz \
  --descriptor /dev/shm/source-cache/dosbox_0.74-3-5build2.dsc \
  --distribution /dev/shm/source-cache/dosbox_0.74-3-5build2.debian.tar.xz \
  --sdl-dev /dev/shm/source-cache/libsdl1.2-dev_1.2.68-2_amd64.deb \
  --sdl-runtime /usr/lib/x86_64-linux-gnu/libSDL-1.2.so.1.2.68 \
  --probe tools/frame_foreground_live_probe/lezac_work_probe.h \
  --out /dev/shm/lezac-pristine-observer
```

The old frozen live projection verifier intentionally continues to require its
historical host/rebuild identity. A fresh pristine-host capture must be checked
under its own build report; it is not substituted into that frozen fixture.

## Fresh Natural Observation

Two pristine builds succeeded. The finalized builder then ran the unchanged
live capture producer with dummy audio, private Xvfb, one player and ordinary
keyboard input. No guest writes, state seeds, clock seeds, instruction patches
or pauses were introduced. All 14 canonical assets were unchanged, and the
43,552 relocated game-code bytes matched in all five RAM samples.

A read-only witness verified the actual child executable, complete command and
environment, and `/proc/<pid>/maps` SDL image while the child was running.
Both natural windows contained a timer IRQ; the first changed the HUD cache.
C++ foreground and active-handoff replays each passed 289,082 comparisons,
304 string transfers, 48 millisecond grants, 30 device callbacks and four
predicted IRQ deliveries across the two replay modes. The two 17x8 HUD regions
have zero indexed-pixel differences. Full-screen samples remain asynchronous
wall-clock observations, not atomic CPU/frame proof.
Native Windows active-handoff replay independently passes the same 289,082
boundary comparisons and four timer deliveries.

| Retained observation identity | SHA-256 |
| --- | --- |
| Final builder | `cb4cb754506ae65329fb01c77d49254aa6dbf12a8f301b4eec75028fd3bfadfc` |
| Final DOSBox host | `eebac5b5e9d47d102d1112c39878f12257c7ec086a5e5a39185fd76e6fbbc33b` |
| Actual mapped SDL image | `b82090085ba665c89ea70909b9018a219c42029fdf9803e7d5e17c185d6d1d72` |
| Capture recipe | `4df000ccb1ea5cecedab61986812f914997425be69d6ba2f997a8064a62bd20a` |
| Gzip CPU trace | `853606c67b9617769a49ff71052ab2a9f0bdeb08384911e9b20adb5951f430a4` |
| CPU projection | `b32f8c1a75d28506b1921c9515fd7423300253d43866d00a3b54d63391c2dc82` |
| Clock projection | `ccda0437b9ae55bcc13418670c7cd3b215fc79aa6313d2df7b91c4917dd5c000` |
| Read-only validation witness | `c0d7d6b7abc4ac479b1029b9e5da92e213370e1cfa01692d935573cccb54b20e` |

Raw captures, screenshots and build outputs remain ephemeral in RAM because
C: remains above the repository's 90% disk-use guard. They are not uploaded in
this change. Fresh original and C++ App screenshots were inspected and shown;
they differ in camera/time and are not claimed to be frame-aligned. The App
still uses its existing semantic renderer and host accumulator. Continuous
natural rendering, live allocation ownership and production integration remain
required before any whole-frame or whole-game fidelity claim.
