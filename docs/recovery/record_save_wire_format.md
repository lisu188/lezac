# Original Record Save Bytes

The DOS record file is a count byte followed by 13-byte entries: a four-byte
score and a Pascal string[8]. The byte after the score is the padded name
length, not a gameplay level. Names occupy eight character bytes and use
`:` for spaces and unused slots.

## Evidence

The original executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Code addresses below are offsets within CS; add `0x770` for file offsets.

- `1845` is the name-entry/insertion routine. At `1AAB..1ABF`, it copies the
  eight-character Pascal string to entry offset 4, then writes the score to
  entry offsets 0 through 3.
- The save routine at `16CA` writes count 7, then each entry as four score
  bytes followed by nine bytes beginning at offset 4 (`173A..175F`).
- A soundless original run started level 1 normally, using an isolated
  seven-entry zero-score record file. Exactly one declared four-byte score
  fixture write set player 1 to 100. No instructions, clock, RNG, heap or
  presentation state were patched, and no process pauses were used.
- Gameplay Escape displayed Game Over. A fresh Return reached rank-one
  name entry. Entering `a` and Return produced the committed 92-byte
  `record_save_original.dat`: first entry score 100, byte `08`, then
  `a:::::::`, followed by six unchanged zero-score entries.
- Gameplay level was independently observed as 1. The saved byte is 8,
  disproving the previous serializer's level interpretation. Provenance,
  executable/producer hashes and explicit fixture scope are in
  `record_save_original.json`.

The save oracle SHA-256 is
`6fd3546b9d29987bdb43daff33e0cdf29a1fbc59934c959366d58e231a748f0d`.
Raw RAM snapshots, screenshots, inputs, the complete producer and both
record-file observations remain retained in the local recovery evidence.
This is an instrumented score-boundary observation, not natural score
acquisition or a campaign playthrough.

## Regression Scope

The raw serializer now writes the encoded name length. The existing helper
always returns eight padded character bytes. Five port metadata levels
(`1`, `0`, `7`, `8`, `255`) must each produce exactly the complete original
92-byte file, with no masks or tolerated differences. JSON save/load must
still preserve each level value. This changes raw output compatibility
without changing the public `Record` layout or the JSON metadata contract.

The pre-fix serializer differs from the original oracle at byte 5 for the
observed level-one case. CI runs the original-save and resource-codec tests
early on Linux and Windows and preserves their output files.

## Remaining Fidelity Work

The raw reader still exposes the length byte through the legacy
`Record::level` member. Generated JSON metadata and the records-page level
label retain that historical interpretation. Their migration, actual name
length decoding, records-page rendering and full name-entry presentation
are not completed here.

Game Over typing, record-entry ordering and cutoff equality are separate
open contracts. A zero-cutoff observation displayed rank 8 for a zero score,
then wrote beyond the seven-record table on commit and stopped making
observable progress. That diagnostic is preserved; it is not a successful
second-player traversal or a whole-game parity claim. Broad fidelity and
completion flags remain false.
