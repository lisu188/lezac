# Generic Monster Fatal-Entry Storage

This batch depends on PR #348, commit
`8bc65da673c53da97082386103994594575d6d18`. It extends physical ownership from
construction and corpse playback into the generic monster's active update and
fatal transition. It does not establish whole-game fidelity or completion.

## Production Changes

- Preserve the full nine-row, 30-byte spawner bank. Tick and consume its byte
  counters directly; publish typed counters from the owned rows.
- Encode loaded spawner resources without losing any of their 30 bytes.
- Write active animation and motion changes through the existing actor owner.
- Apply impact descriptors and signed-byte damage to physical records. Fatal
  conversion preserves the stored health byte, source, backup, and opaque data.
- Release the physical source row once, with byte wraparound, without replacing
  inactive rows. Legacy seeded diagnostics remain explicitly separate.

## Original Evidence

The salted constructor capture contains 1,620 native cases across all 15 shipped
profiles, ready and blocked gates, capacity exhaustion, multiple source rows,
and independent repeat executions. This batch extends its actual-App replay
to compare every spawner byte, not just typed counters.

The fatal-entry capture contains 1,152 seeded cases and 2,304 continuous actor
passes. Each of its 3,456 boundaries stores 1,864 bytes: complete actor, visual,
and link tables; counts and shared result; RNG and player gates; reward scratch;
sound request and accepted latch; the complete spawner bank; signed damage.
The original instructions were neither patched nor stubbed. Observed and
unobserved executions matched over the full 1 MiB memory and 14 registers;
the independent repeat produced identical pinned streams.

Pinned fatal-entry request gzip SHA-256:
`87208a5c381d47e4645d7f868b2ad85b49543d036ae50a80a0625bd969f6ef0a`.
Pinned expected-state gzip SHA-256:
`202e4b6f0d511ccf7bfaac26ab82d245be23a5530421f19f8781874b97bcc50c`.

## Validation Boundaries

Local bounded validation matched 2,551,500 actor-storage bytes, 437,400 spawner
bytes, and 8,100 RNG/roll bytes in the source-extracted constructor. All 13
compiled fault variants were rejected; ASan/UBSan passed. These are not an
actual-App runtime claim.

The new fatal-entry schema roundtripped all 1,152 initial states exactly and
rejected 16 malformed streams. Spawner units cover 7,680 codec roundtrips,
2,304 releases, 24,576 timer/gate combinations, and invalid sources. Fake-runner
checker tests verify failure retention only, not gameplay parity.

CTest `fatal_entry_original` invokes `--debug-fatal-entry-original` on the real
application. It restores each case once, uses `updateOrderedActors(0)` for both
passes, and compares all 6,441,984 state bytes without masks. CI retains raw
requests, actual output, stdout, stderr, and the comparison report on failures.
Exact-head CI execution and external review remain required before acceptance
and merge. At publication, the full fatal-update comparison is unproven.

All runs use dummy audio. The host's disk reserve blocks local game builds,
DOSBox, and new screenshots. No natural route, rendered-pixel, sound-interrupt,
or whole-game claim follows from these seeded checks.

```text
raw_prefix_guard_status=failed
sound_runtime_parity_claim=false
original_fidelity_claim=false
port.functionally_complete=false
whole_game_complete=false
```
