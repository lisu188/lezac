# Direct Fragment Contact Physical Pools

This fixture executes the unmodified original fragment updater at `1000:45FA`.
It covers 96 seeded cases: four directions, four target types (flagged fragment,
flagged collapse, new fragment, and hard zero-word blocker), initial fragment
counts 2/1400/1401, and actor counts 0/30.

Each 26,721-byte expected state includes RNG/counters, both complete 60x33
level planes, all 1,402 physical fragment and 251 collapse records, the
1,575-byte actor bank, and seven sound/shared bytes. No comparison masks apply.
The inactive records and physical guard records are intentionally retained.

## Original Observation

The producer observes direct contact writes at `1000:4C8C` and `1000:4C9F`.
Every nonhard case writes the raw target word and then its flagged form to the
first guard word; the remaining nine guard bytes stay unchanged. Hard blockers
preserve all eleven guard bytes. Guard staging also occurs when a full fragment
pool rejects admission.

The observed and unobserved executions agree on all 1 MiB of RAM and 14
registers for every case. No original instructions are patched, original calls
stubbed, or hardware I/O allowed. The complete RAM hash chain is
`78e25bd45915939859fe4ee188b2b22dacc645a580e6c2f176edd3eba3a4b0c0`.

The raw fixture SHA-256 is
`cfff186bced8419ebbb8cd5951b91e9503764e6836a44775ab9e9e733732f073`;
its comparison stream SHA-256 is
`1ddf2a88c9c1fea2b2d794409c82aa0c9f6b6135fe93b07dcab3477ecd3c862a`.
Its compressed allowance is fixture-specific (768 KiB); shared defaults are
unchanged.

## Compiled Comparison

`--debug-original-debris-contact-pools` restores complete physical pools and
calls production `updateDebrisRecords()`. It skips expected fixture bytes
before executing the updater and does not install them as application state.
The existing collapse/fracture diagnostic selectors retain their behavior.
The checker requires the distinct fragment execution marker and exact raw
stream equality; both CI hosts retain comparison output even on failure.

Local fixture/source/mutation checks do not establish compiled App parity.
The disk guard defers the new compiled comparison to exact-head CI. This is
seeded routine evidence, not a natural route, rendering, sound-interrupt, or
whole-game fidelity claim. Existing incomplete port claims remain unchanged.

To reproduce the original fixture with Unicorn 2.1.4:

```sh
env SDL_AUDIODRIVER=dummy SDL_VIDEODRIVER=dummy PYTHONDONTWRITEBYTECODE=1 \
  python3 -B tools/capture_original_debris_contact_pools.py --root . \
  --out-directory /tmp/lezac-direct-fragment-evidence --unicorn-path /path/to/unicorn
```
