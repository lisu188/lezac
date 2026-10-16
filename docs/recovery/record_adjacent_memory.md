# Owned Record-Adjacent Memory

## Original Observation

The unchanged executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Three isolated silent original runs used natural scores `[0,0]`, one-player
level-one startup and declared record-file fixtures. RAM was opened read-only;
there were no process-memory writes, instruction patches, gameplay/RNG/clock
seeds or process pauses. The fixture manifest pins all archive, producer,
report, full-RAM and PNG identities for 31 independently checked boundaries.

Seven zero-score rows offer rank eight. Committing `q` writes
`0000000008713a3a3a3a3a3a3a` at DS:1b5f..1b6b, leaving all seven record rows
and the saved 92-byte file unchanged. Saved INT09 data at DS:1b60 changes from
`87e900f0` to `00000008`; saved INT1C data at DS:1b64 changes from `601200f0`
to `713a3a3a`. The keyboard handler uses `pushf; lcall *[1b60]` at CS:1147..1148.

The ordinary-key run stops on a partly cleared frame and three later full RAM
samples are identical despite further keys and waits. A held-Return run also
stops before explicit release. A six-zero/final-minus-one control inserts at
rank seven, keeps neighboring handler data intact and accepts player two's
name. Exact fault IP, interrupt ordering and cycle/frame timing are unproven.

## C++ Ownership

`RecordStore` owns `RecordAdjacentMemory`; no host pointer is overwritten or
called. The compatibility object retains exactly the thirteen observed bytes
and decodes their saved far-pointer fields without casting them to pointers.
Unobserved startup bytes remain unknown, not invented BIOS addresses. Explicit
fixture seeding supplies the original initial bytes only to the native test.

An instance rank-eight commit retains the write before attempting file output.
Queue clearing, pending clearing, new end-run setup and record-table replacement
do not reset this separate lifetime. The existing static vector insertion
utility remains a table-only operation; it owns no adjacent region. Ordinary
rank-seven insertion leaves the adjacent bytes unchanged.

The shared `encodedRecordBytes` codec now supplies both DOS file output and the
adjacent write. `Record` layout, signed-score ordering, Pascal name storage,
JSON level metadata, seven-row save size and the existing retry policy remain
unchanged. Failed-save coverage checks port ownership/lifetime behavior; it is
not a new original file-failure observation.

## Validation Boundary

`record_adjacent_original` compares the complete 91-byte table and 13-byte
neighbor span at all 31 captured boundaries, 3,224 bytes per replay. Two replays
retain 62 separate saved snapshots and verify earlier evidence is unchanged.
The test also covers 324 codec cases, unknown startup state, captured and
overwritten handler decoding, invalid-record rejection, lifetime and save retry.
Both native CI jobs run the test and retain its output directory.

This adds original-backed byte-state behavior, not frame-level acceptance.
The input dispatcher does not yet execute or reject corrupted virtual handler
targets, and the renderer does not yet reproduce the original partial frame.
Do not mark the rank-eight runtime finding resolved from this storage test.
The captured RGB checkpoints are sparse and are not a complete synchronized
original/C++ frame stream. Full-App, interrupt/input timing, palette/render
progression, exact-head CI, external review and campaign fidelity remain open.
