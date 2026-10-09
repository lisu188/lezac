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
JSON API. It rejects eight property mutants and executes twelve mocked CTest
cases, reproducing both the old prefixed-output false failure and its nonzero
exit false pass. The repaired policy accepts valid prefixed output and rejects
a failing checker even when its stdout contains a success marker. Mocked
processes are not original-game or production-App evidence. Full required CI
and completed current-head external review remain mandatory before merge.
