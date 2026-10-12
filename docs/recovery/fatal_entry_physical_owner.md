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

Initial CI at `9033ad0` stopped before the constructor/fatal steps: the older
tile-damage diagnostic independently replaced its typed monster but retained
physical actor order 1 and its HP across rows. A compiled physical-HP probe
reproduced all 455 failing case IDs on both hosts; independent physical resets
matched all 1,312 health/fatal gates. The diagnostic now resets its physical
actor storage for each row. This repair changes no production updater method;
actual-App rerun acceptance remains open until the new exact-head CI proves it.

At `125adab`, both hosts passed the 1,312-case tile replay and the actual-App
constructor replay, including all 437,400 spawner-bank bytes. Both then executed
the complete fatal-entry protocol and produced identical 6,441,996-byte output
streams. Exactly 288 state bytes differed, all at state offset 1,585: DS:79A3 in
144 kind-4 cases. No actor, visual, link, spawner, RNG, or other recorded global
byte differed. The comparison remained a failure; no masks were introduced.

Two neutral original-code replays reproduced all 3,456 boundaries and traced
384 DS:79A3 writes to `1000:5B07`. The kind-4 branch calls consume helper `5AFD`
at `7342` and `7370`, between facing selection and common collision response.
Its first cell is the cached footprint plus width; the second is that first
cell plus width+1. Only the first call may seed the cell above, and a nonzero
accumulated score/sprite sum requests cursor `0x21`, priority 1. These are not
two adjacent cells, and the second call does not seed above it.

The follow-up implements the whole observed consume branch, not only its scratch
reset. Its pure consume helper is checked against 6,400 unmodified `5AFD` calls:
all 256 glyphs, five current-word boundaries, five above-word boundaries, and
cursor wraparound. Independent runs matched full 1 MiB memory and 14 registers
per case. Raw fixture SHA-256:
`f99a8cc9e3c2a46a879ab0d2a602c325038a7d3bffb109807cbca734e68a007e`.
This contract does not itself prove the application-level seeder, sound latch,
natural-route behavior, or rendered pixels. The existing seeder and sound APIs
remain the production owners; exact-head actual-App CI is still required.

A separate 1,024-case original branch fixture covers mixed glyph pairs and
flagged current words at `732C..738F`, with full observer neutrality. Its
actual-App CTest invokes the production `consumeMonsterObjectTiles` helper and
checks 18,432 result/sound bytes plus the complete terrain planes. The native
fixture SHA-256 is
`602a9306625eaf5d21115330897e3a04099fd629bcd728a11938771204e1d11f`.
The first above-word is zero in this branch fixture, so application-level
falling-debris dispatch is not proved by it. The 6,400-case helper contract
does check the above-word eligibility boundaries independently.

CTest `fatal_entry_original` invokes `--debug-fatal-entry-original` on the real
application. It restores each case once, uses `updateOrderedActors(0)` for both
passes, and compares all 6,441,984 state bytes without masks. CI retains raw
requests, actual output, stdout, stderr, and the comparison report on failures.
Exact-head CI execution and external review remain required before acceptance
and merge. At initial publication, the full fatal-update comparison was unproven.

At `9f43929`, exact-head Linux and Windows CI both matched all 6,441,984 fatal
state bytes, without masks, and passed the 6,400-case consume helper and
1,024-case actual-App branch replay. The raw fatal output SHA-256 on both hosts
is `93ebfe626427e2ec300dc3e7c98b0d4adeda7ad442dadf3297bcd8691a6a2371`,
identical to the retained original stream. Both complete CI jobs still failed
later in `production_actor_lifecycle_app`, before the full-suite Test step.

That seeded lifecycle diagnostic set only typed spawner counters. The physical
shipped row retained cooldown zero, which the production tick decremented to
255; no constructor ran. A bounded compiled probe reproduced this mismatch
against the pinned shipped level data. The diagnostic now loads its intended
remaining/available/cooldown values into the physical spawner row. It also
seeds the physical corpse timer for its immediate-expiry scenario, after
checking that production fatal conversion initialized kind 12 and timer 25.
Production updaters, lifecycle assertions, native fixtures, and original-byte
comparisons are unchanged. At `d25f5aba`, both hosts passed the repaired actual-App
lifecycle scenario, including both full-capacity conversions. CI then failed a
source-contract assertion that searched for the first `writeCorpse` call in the
entire file; it found the diagnostic seed before the production updater. The
assertion now uses the same `updateMonsters` function boundary as the mutant
generator. Controls cover unrelated writes outside that boundary, incorrect
writeback ordering, and missing production writeback. The native animation
helper, monster/corpse actual-App replays, and compiled skip mutant passed on
both hosts at `d25f5aba`. The full-suite Test step was skipped; new exact-head
full-suite validation and external review remain required.

All runs use dummy audio. The host's disk reserve blocks local game builds,
DOSBox, and new screenshots. No natural route, rendered-pixel, sound-interrupt,
or whole-game claim follows from these seeded checks.

## First-Only Seeder Integration

A separate 896-case unmodified-original capture executes the same kind-4 branch
with both consume glyph boundaries, four current-word flag combinations, seven
first above-word boundaries, and an empty or eligible second above-word. It
includes 256 first seeder calls: 128 collapse and 128 debris constructions.
The eligible second above-word is never seeded. Each case was independently
repeated with full 1 MiB memory and 14 registers equal between observers.
No original instruction was patched, no call was stubbed, and hardware I/O was
forbidden. Raw fixture SHA-256:
`e0b7ac8a68fae110cbb112c764049335616387495747b0c07cd18ece468c9c3d`.

The application command `--debug-monster-object-seeder-original` restores only
the ten input bytes for each case and invokes production consumption/seeding.
It writes all 5,360,768 result bytes for an independent checker: both complete
terrain planes, queue counts, the first 11-byte debris and 15-byte collapse
records, scratch/result/request/latch bytes, DS:79C8, and sound-request count.
No state byte is masked. The complete expected output stream SHA-256 is
`7ed60f56e6050d1c02c7dd03360f17359306cff1141d5d046b26699743604250`.

DS:79C8 now has an explicit production owner. Successful queue insertion writes
one, capacity rejection writes zero, and already-flagged words preserve its
previous value. The seeded branch starts this byte at `0xA5`, so cases that do
not invoke the seeder distinguish preservation from a guessed boolean result.
The fixture uses available queue capacity and single distinct-word collapse
geometry; it does not prove full-capacity or multi-cell seeder integration.
Actual-App acceptance for this fixture remains unproven until exact-head CI
executes and the independent complete-byte comparison passes. Python checker
contract tests establish tooling behavior only, not C++ gameplay parity.

```text
raw_prefix_guard_status=failed
sound_runtime_parity_claim=false
original_fidelity_claim=false
port.functionally_complete=false
whole_game_complete=false
```

## Seeder Capacity and Retained Queue Storage

The `370E` seeder's current-head recovery now keeps inactive debris/collapse
records when the live count is cleared, decremented, or compacted. Live iteration
still visits only the active prefix, in the existing order. Insertion overwrites
the next physical record; a rejected insertion leaves it intact. The optional
caller-owned class byte is written before either capacity check, but flagged-word
rejection preserves both that byte and `DS:79C8`.

`seeder_capacity_original.bin.gz` contains 448 independently repeated executions
of the unmodified original, with full 1 MiB memory and 14 registers compared per
case. Inputs cover seven nonzero word classes, debris counts 199/1599/1600/1601,
collapse counts 0/249/250/251, and four previous result bytes. Of these, 128 insert,
128 reject for capacity, and 192 reject flagged words. Both candidate records are
salted before execution; 640 rejected candidate records retain every byte.

The actual-App diagnostic calls production `queueTileDamage` and serializes both
complete terrain planes, both counts, the exact pre-call candidate records, the
result byte and caller-owned class byte. It seeds inputs and salt constants only,
never expected output. The checker independently compares all 2,675,456 state
bytes without masks and retains raw output, failure details and executable pins.
The previous 896-case consume/seeder diagnostic also reads retained records now;
its original zeroed candidate state is explicitly initialized as fixture input.

Fixture SHA-256 (gzip):
`4d09cf11c69273c53df39ea8d2649659592022e5d62d4dfb5488f3c4a017b63a`.
Fixture SHA-256 (raw):
`403fa355373eb72a5cffa191692836c6c305024d9c21e9cf87bd301c0cfb547e`.
Expected output SHA-256:
`8b3a2daab47d116f1ffea0a8f4bc81db13332f335beac706967e743d6a374858`.

Local queue/fixture/checker tests are not actual-App acceptance. Current-head
Linux/Windows output comparisons and full CI remain separate delivery gates.
This boundary fixture does not establish complete physical-bank equivalence,
multi-cell collapse geometry, natural-route behavior, rendered parity, sound
interrupt parity, or whole-game completion. The zero-word direct caller state
remains outside this fixture; the existing C++ zero-word guard is unchanged.

## Multi-Cell Seeder Integration

The same actual-App seeder diagnostic now accepts the complete input terrain
planes for 384 unmodified-original cases: 16 layouts, four low-word boundary
values and six signed velocity pairs. Layouts include connected edges, diagonal
expansion, disconnected islands, hollow/irregular regions and a 153-cell block.
Both available collapse-counter boundaries (0 and 249), two debris counters and
four previous result bytes are covered. Each original case is independently
repeated with full 1 MiB memory and 14 registers compared, without instruction
patches, stubs or hardware I/O.

The existing production geometry owner matches all 1,522,560 recorded word-plane,
bounding-offset and affected-byte bytes. The cases flag 7,152 cells in total;
24 cases wrap the byte-sized affected count. Velocity magnitudes include 255
and 256, retaining the full original word. This owner-only proof is not App
acceptance: the new App checker must independently compare all 2,293,248 state
bytes, including both complete terrain planes, both queue counts, both salted
candidate records and the result/class bytes. The existing capacity protocol is
retained through the shared diagnostic implementation.

Multi-cell fixture SHA-256 (gzip):
`1a6982b697f781921c34255dd89137bb577fbe74f8170211e18f878cae6560eb`.
Multi-cell fixture SHA-256 (raw):
`a75c151aa445fe8af4980ce55ac96842abc1430a6085547c35c4227726eb94bb`.
Expected App output SHA-256:
`f62479bc246f175396365df766ff71bab202a1497569d35153b4d8e06b31954e`.

These seeded boundary cases do not establish complete physical-bank equivalence,
natural-route or campaign behavior, rendered parity, sound-interrupt parity or
whole-game completion. Actual-App host comparisons, required full CI, dependency
delivery and current-head external review remain separate gates.
