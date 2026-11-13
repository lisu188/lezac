# Above-Cell Contact Staging

The collapse updater's above-cell scan at `1000:4E48` stages distinct nonzero
contact words at `DS:655E`. Horizontal movement seeds above when flag `0x80`
is clear. Downward movement sets that flag and seeds above only when it was
clear. Flagged words are collected but not seeded again. The first 11 staging
bytes overlap the retained debris guard, as in the existing movement matrix.

The new original-backed fixture covers 96 complete updates: 72 active cases
across left/right/down motion, widths 1-6, unique collapse words, repeated
collapse words, fragment words and already-flagged words; 18 flag-gated cases;
and six stationary controls. Actor pools alternate between 0 and 30 slots.
The original executes 354 seeder calls, 30 fractures, 30 actor-constructor
entries and two timer removals. Existing fragments are not advanced.

Each case compares all 26,721 state bytes, including all 1,402 retained debris
records, 251 retained collapse records, the complete 1,575-byte actor bank,
both level planes, RNG/destruction counters and seven sound/shared bytes.
Observed and unobserved original runs agree across the complete 1 MiB memory
image and 14 registers. No original instructions are patched, calls stubbed,
or hardware I/O permitted.

The exact PR #360 packaged Linux App matches all 96 cases and 2,565,216 state
bytes without masks. Its output SHA-256 is
`fd41f3c8446c9d13c32a0f920f00b38dee0a31721e68e43632144dd1be7a2074`.
This is compiled dependency-head evidence, not exact new-head acceptance.
No production C++ change is needed for this matrix.

Reproduce the original fixture with dummy audio and Unicorn 2.1.4:

```sh
env SDL_AUDIODRIVER=dummy SDL_VIDEODRIVER=dummy python3 -B \
  tools/capture_original_above_contact_staging.py --root . \
  --out-directory /tmp/lezac-above-original --unicorn-path /path/to/unicorn
```

The regression suite pins the full fixture, checks de-duplication and stale
guard-tail preservation, tests seeder phases and flag gates, and rejects raw
output corruption throughout the physical state. CI retains the full actual
outputs, comparison diagnostics and packed input fixture on both hosts.
Controlled initial state is not a naturally reached route, complete DOS data
segment, rendered-pixel comparison, sound-interrupt parity or whole-game proof.
