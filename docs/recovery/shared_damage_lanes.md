# Shared Damage Lane State

## Production Mapping

`DamageLaneMemory` forwards byte reads and writes to the same retained records
used by the production game: 199 physical flame rows, 1402 fragment rows and
251 collapse rows, including dormant tails and guards. The cursor at DS:2074
is the sound engine's shared cursor. Flame masses and the seeder result byte
are also forwarded. Fragment and flame lane locals are bound to DS:78D2..78D5
for their complete updater iterations. A write to the other axis therefore
changes the caller's subsequent input.

The helper's scratch phase at DS:661E and contact/tag staging persist between
runtime calls. Unmapped bytes have persistent byte-addressed storage and are
read by subsequent lookup/weight operations, not an unread write log. The
initial 6928 low DS bytes come from the pinned executable's MZ loader image
at logical load segment 1000. `generate_initial_damage_data.py` reproduces the
generated header. This is not a natural DOS startup-state capture.

The direct fragment caller uses the recovered DS-address helper, including
the fragment tag bias. Collapse callers use a value-returning form because
their caller bytes are on SS:BP-0B/0C. Flame callers execute both original
lookups and retain their distinct 16-bit blend/write logic without adding
the impact helper's fragment tag bias. Flame timer and variant writeback uses
live retained fields after alias writes.

## Evidence

- The existing 176-case unmodified-original fixture is compared through both
  the flat helper and the production typed memory view. Every incoming DS byte
  round-trips before execution; all 11,534,336 outgoing DS bytes are compared.
  Expected bytes are not supplied to either compiled helper process.
- Independent typed-field assertions cover every record field at first,
  second, last live and guard slots. This prevents a symmetric but incorrectly
  shifted read/write adapter from passing by round-trip alone.
- Synthetic unit coverage verifies shared cursor coherence, retained queue
  tails, reverse iteration, DS caller aliases and SS-style value return.
  A missing F001 write at 0A07 is consumed as the next missing B598 contact's
  unsigned weight. This sequential unit is not claimed as original execution.
- The new 112-case original fixture advances the complete fragment updater.
  It extends the 96 physical-pool cases with sixteen nonzero incoming-phase
  cases at full admission failure. Each input independently seeds DS:661E and
  DS:0A06/0A07; each output includes these three bytes, all physical records,
  map planes, RNG/counters, the complete actor bank and sound request/latch.
  Observed and observer-free original runs agree on all 1 MiB RAM and fourteen
  registers. No original instructions or calls are patched or stubbed.
- Fixture/checker tests are separate from execution of the compiled App.
  Above the disk guard, local validation compiles only small helpers and checks
  App syntax. Exact-head Windows/Linux CI must establish actual-App comparison.

## Open Fidelity Boundaries

This is not a complete DOS address-space owner model. Unmapped actor, visual,
asset and other global addresses do not yet forward to all corresponding
production readers. Corrupted queue counts are not clamped by this view, but
production traversal beyond the physical bank is not proved equivalent to
DOS address wrapping. Stale SS seed-class bytes on inconsistent staged/map
inputs at the start of a helper call are also outside the current production proof.

The loader's logical segment does not establish natural runtime relocation or
startup state. Existing natural route, raw-prefix, visual and sound-runtime
fidelity gates remain open. Source integration and passing helper comparisons
do not establish whole-game completion or justify merging through failing CI
or without completed current-head review.

## Validation Contract Maintenance

The generated low-data verifier permits Git's LF-to-CRLF checkout conversion
only. Executable pins, MZ relocation checks, the complete generated payload and
all other text bytes remain exact. Regressions cover both newline styles,
changed data, bare CR, BOM, whitespace changes, truncation, appended data and
refusal to overwrite generated output.

Collapse source contracts follow the production shared memory view, contact
staging, seeder result and SS-style value-returning helper, including recovered
arithmetic and wrapped write addresses. Flame contracts follow both lookups,
their shared cursor, unsigned weight and mass reads, both arithmetic calls,
wrapped writes and live writeback. Scoped deletion mutants cannot be satisfied
by the same statements in comments, strings or unrelated functions.

These contracts complement the unchanged 9184-case collapse original fixture
and 1376256-case flame arithmetic fixture. They are not original execution or
full-update parity by themselves. The production C++ source, generated loader
header, fixtures and original producers are unchanged by this validation repair.

## Repeated Staged Targets

The contact helper's seed-class byte at SS:BP-0C is not reset between contacts.
Seeder 370E returns immediately for an already-flagged map word, preserving both
this byte and DS:79C8. Consequently, a repeated staged target uses the most
recent real seed's class, which can differ from that target's map word class.
Production now keeps one seed-class local for the entire contact blend call.
The single-contact fragment wrapper supplies the same explicit local interface.

The new 576-case original fixture calls both 3BB2 and 3D46 with a real SS caller,
not a substituted DS byte. It covers repeated fragment and collapse targets,
mixed seed classes, an intervening flagged lookup, and fragment admission at
normal, last-available and full capacities. The first real seed always defines
the local, so these outputs do not depend on the deliberately poisoned incoming
SS byte. Original execution is unpatched and unstubbed; additional observers are
neutral over all 1 MiB RAM and fourteen registers.

The fixture stores all live pool records, both map planes and the caller result.
CI compares this stream through the production App diagnostic without giving
expected bytes to the App. An extracted-method harness is a separate lightweight
local regression, not proof that the complete App or natural game ran. Incoming
stack history before the first real seed, complete collapse-updater sequences,
and natural-route reachability remain separate open requirements.

## Collapse Scanner Scratch Ownership

The original support scanner 4D3C and contact collector 4E48 clear DS:661E
before traversal and set it to one for any blocking tile, including a zero-word
blocker that cannot become a staged contact. Balance scanner 4DD3 uses the same
scratch owner. The production collapse scanner now performs these writes at
their owning operations; it does not substitute a final diagnostic value.

A scanner-only extraction uses the exact production map readers, cell iterator,
scanner lambda and physical fragment guard alias method. Across 384 isolated
4E48 calls, the old extraction differs in 324 queries, exclusively at DS:661E.
The repaired extraction matches all 5376 compared scratch/count/guard bytes.
Additional original observers are neutral across all 1 MiB RAM and fourteen
registers. This bounded component comparison is not execution of the full App.

The independently reproduced 96-case full original 5102 fixture covers both
axes, diagonal collisions, fresh fragment/collapse targets, deduplicated collapse
groups, normal/last-available/full fragment pools, retained tails, and empty/full
actor banks. Each scene is rerun with three incoming SS poison values; their
serialized results agree. This does not prove general first-seed stack history
or natural gameplay reachability. No original code or calls are patched/stubbed.

The new App command consumes an input-only LZCI0001 stream. Expected state stays
in the external checker. CI compares 2565504 output bytes without masks: both map
planes, all 1402/251 physical fragment/collapse records, RNG and counters, the
complete actor bank, sound request/latch, DS:661E and DS:0A06/0A07. Compressed
input, expected, actual and result diagnostics are retained on success/failure.
Fixture/source controls and App syntax checks are separate from the still-needed
exact-head actual-App comparison. Natural-route, visual, sound-runtime and
whole-game fidelity remain unproved.

## History Comparison CI Evidence

PR 367 Linux and Windows CI execute the complete production App, not the lightweight
component extraction. Its retained raw outputs match all 576 seed-history cases
(6157656 bytes) and all 96 full collapse-history cases (2565504 state bytes),
without masks. The tested PR merge commit has the same complete source tree as
the published head 952a720. This establishes these seeded comparison scopes,
not natural gameplay, rendering, audio timing or whole-game completion.

Both jobs nevertheless report both CTests as failed because their success regex
is anchored before an earlier retained-artifact path line. These two Python
checkers already validate the App marker, process status and every expected
byte before returning success. Their CTests now rely on that strict exit status
and retain the existing timeouts, environment and commands. A PASS regex is not
used because CTest explicitly ignores the process exit code when it is set.

A separate regression reads the real configured registrations through CTest's
JSON API. It rejects twelve property mutants and executes eighteen mocked CTest
cases, reproducing both the old prefixed-output false failure and its nonzero
exit false pass. The repaired policy accepts valid prefixed output and rejects
a failing checker even when its stdout contains a success marker. Mocked
processes are not original-game or production-App evidence. Full required CI
and completed current-head external review remain mandatory before merge.

## Single-Record Support History

The previous 96 complete-updater scenes process a supported older record last,
so every final DS:661E value is one. A second independently reproduced original
5102 fixture starts with exactly one live record: four widths (2, 3, 6, 7), two
heights (1, 3), four initial support layouts (centered, left-edge, right-edge,
none), and three horizontal velocities (-15, 0, 15). Some scenes contain interior
holes, balance-scan walls, fresh objects above, and timer-94 or byte-255 history.
Initial support labels do not claim that support survives horizontal movement.
The existing input-only App command accepts this fixture without a game change.

The original visits 96 support scans, 32 balance scans, 48 seed calls and eight
timer removals. Final scratch is zero in 68 cases and one in 28. All three stack
poisons produce the same serialized output in every scene. Hooked and unhooked
execution agree over all 1 MiB RAM and fourteen registers; original code and
calls remain unmodified. The pinned count-2 data restorer is reused by changing
only its restoration input count, then restoring requested DS:2080=1 before
any original code executes. This adapter is recorded in the pinned metadata.

Both fixture profiles use the same strict checker and complete 26724-byte state
format. Metadata, producer dependencies and raw/compressed streams are pinned;
cross-profile fixture substitution is rejected. CI runs the 96 support cases
through the real production App, retains input/expected/actual streams on
success or failure, and compares every serialized byte without masks. Local
fixture, checker and CTest controls are not proof that the compiled App passed
this new matrix. Exact-source-tree Linux/Windows App evidence, full required CI
and current-head external review remain pending. Natural reachability, visual
and audio-runtime fidelity, and whole-game completion remain unproved.

The focused CI step and later full suite execute these original comparisons
twice. The earlier fixed-directory checkers refuse the second invocation before
launching the App. All three profiles reproduce this failure with mocked
children. Each checker now creates a unique attempt directory under the same
retained root, leaving prior success/failure bundles and legacy files intact.
A separate regression executes fifteen mocked attempts across the three
profiles (success, mismatch, nonzero exit, timeout, success) and rechecks every
earlier file hash after each attempt. These are failure-retention controls, not
game comparisons. The eight-MiB retained-root reserve still applies.

### Fixture Checkout Transport

PR369 Linux passes its focused comparisons. Its Windows job rejects the new
support metadata pin before running those comparisons: the new JSON fixture
was missing the neighboring fixtures' byte-preserving Git attributes. The
follow-up marks only the new JSON and gzip fixture as `-text`; original bytes,
pins, producer, checker and game code remain unchanged.

A real Git checkout regression covers LF and CRLF configurations, verifies both
fixture hashes and effective attributes, and retains three negative controls:
missing metadata rule, forced metadata text conversion, and forced gzip text
conversion. The missing-rule checkout reproduces exact LF-to-CRLF metadata
conversion while parsed JSON remains identical. Byte pinning is preserved,
not weakened to semantic comparison. These are Git transport controls, not
original-game or compiled-App evidence. Complete required CI and review remain
pending.

## Repeated Collapse Boundaries

A portable original-only producer extends all 96 single-record support scenes
through eight consecutive boundaries. The original memory image is not reset
between these calls. All 768 input/output pairs retain the full physical pools,
actor bank, sound bytes and three lane-history bytes. There are 712 active
updater calls and 56 empty-queue skips. The latter follow the pinned caller
instructions at 1000:8060-806A, which call 5102 only when DS:2080 is nonzero.
Hooked and unhooked continuous execution agree over all 1 MiB RAM and fourteen
registers. Independently restored original images reproduce every serialized
output; the first boundary of each scene matches the earlier support fixture.

The exported compressed/raw fixture and full-RAM hash chain reproduce the
initial continuity probe exactly. Its metadata pins the producer and all reused
executor, reader, restorer, imported-helper and support-fixture dependencies.
The checker verifies the ordered inherited state and original input/expected
stream hashes before splitting the observations into eight 96-case batches.
Only input state reaches the App. Each batch retains exact input, expected and
actual gzip streams; earlier attempts and partial failures remain intact.

The input-only diagnostic now accepts an empty collapse queue. Its other
physical-storage modes still reject zero live records. No gameplay updater
rule changes. CTest requires strict checker exit status; both host workflows
run and retain this new comparison before the full suite. Checker mutations
cover the diagnostic gate, provenance claims, fixture bytes, ordering, inherited
state, output corruption and a failure after three successful batches.

These are seeded repeated-state transitions. The App restores each boundary
independently, so this is not proof of an unbroken C++ campaign, complete hidden
state, sound runtime, visual fidelity or general first-seed stack history.
PR371's focused artifacts independently verify all four matrices on Linux and
Windows: 1536 cases and 31812696 state bytes per host, without masks or
mismatches. This includes all 768 continuity boundaries and 20524032 new state
bytes per host. Both jobs tested merge commit 3c1ea65829b0d31f836f2ab5084d36a8a8d57640;
its complete tree 4d9d37c5d882557bfb1cace3a0ab075debc0e3cf equals published
head 6e6a2a078132a80f08fa95f4b18e46793432f831. Artifacts 11640537571 (Linux)
and 11639968507 (Windows) retain every input, expected and actual stream.
An independent native Windows readback reconstructs and compares all original
streams. Full required CI and current-head external review remain mandatory
before merge.

## Continuous C++ Collapse Updates

The separate `--debug-original-collapse-continuous` diagnostic restores each
scene once, then performs eight production collapse updates without restoring
queues, map bytes, actor storage, sound state or lane-history bytes between
boundaries. Only the tick advances. Empty queues skip the helper, following the
pinned original caller. No production updater rule changes.

The checker reuses the pinned original repeated-boundary fixture. Each of eight
batches sends twelve initial scenes, not intermediate or expected states, and
receives all 96 intermediate results. All 768 original observations are retained
in the comparison. Each input, actual-output and retained root remains below
eight MiB. Existing diagnostic formats and comparisons remain unchanged.

Source controls reject resets or input ingestion inside the repeated-update
loop. Mocked-child controls cover repeated success and later-batch mismatch,
nonzero exit, stderr, wrong output marker and timeout, preserving exact partial
streams and every earlier attempt. These controls are not compiled-App evidence.
Both host workflows execute and retain the new strict CTest comparison.

Actual continuous-App parity remains pending until the new exact-source-tree CI
artifacts are independently checked. Even a match proves only these seeded
collapse-update sequences, not full game ticks, natural campaign reachability,
visual fidelity, sound-runtime equivalence or whole-game completion.

PR372 now has independently verified Linux and Windows artifacts for the
unbroken mode. All 96 scenes and 768 intermediate states match the original,
including 20524032 new state bytes per host. Together with the earlier matrices,
2304 comparisons and 52336728 state bytes match per host without masks or
differences. Tested merge 93d8d0d389b3455b23d05f001f8d2bf2806843de has the same
complete tree b2518ea10a9cafd1b666708bc5d0bf54bdd6c1cc as published head
d34bc30c1e0598d912cc741348f7109209ba4c7c. Focused artifacts 11641806746 (Linux)
and 11642655318 (Windows) retain every raw stream in lossless gzip form.
Native Windows independently reconstructed and compared all original streams.
Full required CI and current-head external review are separate pending gates.

## Multi-Record Contact Histories

The pinned two-record lane matrix supplies all 96 initial scenes: 36 debris,
12 collapse, 36 alternating and 12 collapse-group layouts. A new original-only
producer advances each image through eight unbroken collapse updates. Every
first boundary matches the earlier lane fixture. All 768 calls remain active;
the observer records 1269 visits to seeder 370E, 102 visits to 557B and 18 visits
to 566C. No original instruction or call is patched, and hardware I/O is
forbidden. Hooked/unhooked images agree over all 1 MiB RAM and fourteen registers;
freshly restored original images reproduce every full serialized output.

The complete fixture, producer dependencies, original visit counts and all
input/expected bytes are pinned. The raw fixture hash is
68a6338076fd0ca5be29670f7ba1118b3f0f837f94750379c7d3507b6285221b;
the full-RAM observation chain is
31148833160e4ff28a31a6ab0dd387307de4bc0208ad3df21b5d1206a40a6a31.
Both restored-boundary and unbroken-App modes compare all 768 observations in
eight bounded batches. The latter receives only the twelve initial scenes per
batch. Existing profiles and all production game source remain unchanged.

Both host workflows retain these two new matrices in separate focused artifacts
to keep independent downloads bounded. New CTest registrations retain strict
exit status, and byte-preserving Git attributes cover the JSON and gzip files.
The new producer retains RAM, serialized state and registers for a first failed
boundary. These are seeded original-only observations until exact-source-tree
App outputs are independently checked; they do not establish complete game
ticks, natural campaign reachability, general first-seed stack ownership,
visual/audio runtime fidelity or whole-game completion.

## Coupled Debris And Collapse Dispatch

The original caller at 1000:804E-806A gates debris/sparks 45FA before collapse
5102. A portable producer advances 32 initial lane scenes through sixteen
unbroken executions of those unmodified caller instructions. Spark count stays
zero throughout this matrix. All 512 full serialized boundaries reproduce from
fresh original images, and every first boundary matches the pinned lane fixture.
Hooked and unhooked runs agree over all 1 MiB RAM and fourteen registers; no
original call is stubbed and hardware I/O remains forbidden.

The original visits 45FA at 474 boundaries and 5102 at all 512. A counterfactual
which enters the unchanged caller at 8060 skips the preceding debris pass. Its
output differs at 474 boundaries, including tiles at 336, physical collapse
storage at 65, RNG at 85 and sound-request state at fifteen. This distinguishes
the coupled phase sequence from collapse-only evidence without changing either
original updater. The raw coupled fixture hash is
faecb105bbdc961a411ce700845e4c3c15ce2534fd73c983082d6405031bfcee.

The new `--debug-original-physics-dispatch` diagnostic restores four initial
scenes per batch, then performs sixteen gated debris-then-collapse passes without
restoring intermediate state. Eight batches return every original boundary.
Only initial input bytes reach the App; no expected or intermediate states are
passed to it. Every byte of the 26724-byte output state is compared without masks.
Production updater code and all previous diagnostic modes remain unchanged.

The checker pins provenance, dimensions, input inheritance and complete streams,
and retains lossless input/expected/actual bytes on success or partial failure.
Controls reject phase reversal, missing gates, resets, input ingestion inside
the repeated loop, forged scope, corrupted outputs and later-batch failures.
Both host workflows run strict CTest comparisons and preserve focused artifacts.
Local source and mocked-child checks are not compiled-App parity. Exact-source
Linux/Windows App comparison, full required CI and current-head external review
remain pending. These seeded phase sequences do not include earlier actor/player
passes or later clock/presentation work and do not establish full game ticks,
natural campaign reachability, visual/audio fidelity or whole-game completion.
