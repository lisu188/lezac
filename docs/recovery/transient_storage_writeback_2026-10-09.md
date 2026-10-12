# Original-backed transient physical write-through

This batch extends the production lifecycle binding with behavior-5 transient
record writes. It does not make physical storage authoritative for every typed
actor, establish natural-route parity, or complete the game.

## Production changes

`App::spawnTransientActor` writes the initialized active animation into its
allocated physical record and reads the constructor's retained animation backup
and hotspot from that record. Full-capacity rejection reaches the allocator,
preserving its success-word behavior without consuming a birth identity.

`App::updateTransientActor` uses the shared compiled motion/animation helper,
then writes timer, velocity, fractions, active animation, and visual coordinates
before the ordered loop retires an expired actor. Stable compaction can therefore
retain the last updated bytes in the inactive tail. Untouched record bytes and
the physical animation backup remain owned by `ActorStorage`.

The original animation prologue at `1000:6156` changes visual bytes 6-7 only.
Width and height at bytes 4-5 are retained. Behavior-5 timer handling at
`1000:65A2..65D7` precedes motion at `1000:754A..7588`; terminal expiry skips
integration. Coordinates narrow to the original signed word representation.

The independent reward constructor/projection kind base is corrected from 16
to 19, matching native kinds 19-25. The production lifecycle diagnostic checks
the constructed Present's kind19. Other reward fields are not covered by the
transient fixture.

## Original evidence

`evidence/transient_storage_20261009/` retains two frozen producers, capture
reports, and the hashed original CPU and native reader sources. Each capture
executes 192 original full actor passes and 48 constructor attempts across
16 seeded cases, with 256 complete physical-table boundaries. The two compressed
request streams and two compressed expected streams are byte-identical.

Cases cover animation modes 0-3, nonzero retained backups, distinct inactive
records, reversed visual references, timers 0/1/2/64 and byte wraparound,
velocities including -32768/+32767, word-coordinate wrap, expiry, reallocation,
and full-capacity constructor rejection. Active visual dimensions deliberately
differ from the animation descriptors to expose incorrect dimension rewrites.

Every observed return matches a neutral original CPU over all 1 MiB of memory
and 14 registers. Original instructions are not patched, calls are not stubbed,
and hardware I/O is not permitted. Constructor animation bytes are an explicit
controlled seed, not evidence of a native animation initializer call.

The comparison includes all 31 physical 38-byte actor records, 33 eight-byte
visual rows, eight 16-byte link rows, and count/success scalars: 1,575 bytes per
boundary and 403,200 compared table bytes, with no masks. The fixtures are under
`tests/fixtures/transient_storage/`; compressed and raw hashes are pinned in the
stdlib checker.

## Validation and limits

The retained bounded-validation-v4 report verifies the compiled helper and the
same fixture under ASan/UBSan, with zero mismatches. Four compiled mutants are
rejected: omitted write-through, entire-descriptor rewrite, cleared retired
tail, and truncation of negative fractional carry. Checker regressions cover
hash/extent rejection, every physical area, nonzero exit, missing markers,
silent child environments, and partial output retention after timeout.

The first fixture's dimension mutant survived because its dimensions matched
the selected descriptors. That failure is retained outside the committed
fixture; the strengthened independently repeated original experiment closes
the coverage gap. No production behavior was changed to satisfy a weaker test.

Local App syntax, source ownership, GRAN guards, CMake registration, and both
host CI wiring pass. A full local App build is deferred under the disk guard.
These checks are not an actual App runtime proof.

`transient_storage_app_original` runs the real application command
`--debug-transient-storage-original INPUT OUTPUT` with the legacy adapter
disabled, validates descriptor bytes against loaded original assets, restores
only explicit case seeds, then uses the actual transient constructor and ordered
actor loop. It emits the physical owner's state without reading expected data.
CI runs it and the helper/checker contracts before the full suite on Windows
and Linux, retaining binary outputs, hashes, logs, and comparison reports.
Actual App execution and full-suite acceptance remain pending until verified
at the published head.

Other actor families, conversion entry points, rendering consumers, natural
campaign sequences, and sound runtime parity still need broader original-backed
physical ownership and acceptance. No rendered pixel or whole-game claim is made.

## CI source-contract follow-up

At initial PR342 head `be1d76b7`, the actual App and helper comparisons passed
on both Windows and Linux, with all 403,200 table bytes equal to the original.
Later CI failed in collapse actor creation because its source-text contract
still required the removed pre-allocation early return.

The follow-up changes only that contract, its expected CTest mutation count,
and documentation/evidence. It requires the actual constructor-to-allocator
call, refusal handling, full-capacity descriptor bypass, append rejection,
and success-only identity advancement. Source mutations increase from 23 to 29;
none of the previous diagnostic or collapse-route checks are removed. The
original fixture hashes, records, metadata checks, and runtime comparator remain
unchanged. Local source-contract CTests and all original oracle records pass.

The initial-head runtime evidence is retained separately from the follow-up's
pending exact-head CI. It is not relabeled as execution of a newer commit.

All processes use `SDL_AUDIODRIVER=dummy`. The isolated source and each bounded
validation root remain below the 8 MiB cap; originals, failures, and transitive
Git donor roots are preserved.
