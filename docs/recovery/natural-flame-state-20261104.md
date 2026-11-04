# Natural Flame State Projection

`tools/flame_state_projection.py` decodes nine live flame fields from a complete
original DS snapshot and compares them with the existing native trace's `flames`
array. The original count is a word at `DS:2076`, capacity 198. Live slots are
one-based: eleven-byte records at `DS:2093 + 11*slot`, with parallel mass bytes at
`DS:78D5 + slot`. Slot order is significant and no records are sorted or dropped.

The declared fields are cell, signed VX/VY, signed X/Y fractions, timer, glyph,
variant and mass. The two-byte retained word at record offset +2 is intentionally
excluded because the trace does not expose it. Inactive slots, other actor
fields, complete actor records and whole DS/RAM equality are also excluded.
The C++ model preserves a `retainedWord`; that does not make it observed here.

The pure helper launches no guest, accesses no process, changes no gameplay,
constructs no original evidence and asserts no provenance or fidelity flags.
Callers must authenticate the original snapshot, route, boundary phase and native
trace independently. Missing fields, malformed shapes, out-of-domain numbers,
booleans, excess counts and unequal live records fail without clamping.

## Natural Route Audit

The private audit reuses the independently qualified Level 4 original window
described in [literal-map-observer-20261104.md](literal-map-observer-20261104.md).
It verifies every compressed DS member against the original-only audit's digest
before decoding. Expected values come only from those original snapshots, not
from the port. All 1,402 present/post-update boundaries at ticks 18100..18800
match the Linux and Windows native traces. Sixteen boundaries contain flames,
comprising 192 live record observations per platform. All nine declared fields
match. Twelve mutations of real native flame data are rejected on each platform.

The pre-existing comparison independently covers all 701 full RGB frames,
literal tile/word maps, the declared state and nine bomb fields. The new flame
audit does not rewrite that historical evidence. No new guest execution or
gameplay-state injection is used for this extension. Original initial RNG and
control-bank normalization remain disclosed by the underlying capture.

Original-only audit SHA-256:
`8cf570e33c1b2b40fba39a1440593713360c10a0087b575642e785333558b79b`.
Private flame audit SHA-256:
`9c6fe92d664efdc7a28e69c23bd903db8f0e46ed6a2c722d9337df4c89c9933c`.
The subsequently tested shared helper agrees with an independent byte-field
decode at every boundary and rejects thirteen real native mutations per
platform, additionally covering slot reordering. Its private original-only
reference SHA-256 is
`484f90d09401849a3bb98e7e3bce4b94671d209ca280a1e2d6bf9f733a031822`.
The unchanged C++ source tree remains
`8d059cdd61dce9a9af207cb7e07c879d6f843a84`.

## Regression Coverage And Limits

Synthetic tests cover the complete declared layout, one-based indexing, empty
and full-capacity pools, word-sized count rejection, signed byte boundaries,
all nine field mutations, missing/extra/reordered records, strict numeric/schema
validation, explicit exclusions and unchanged inputs. Additional parsing tests
assemble synthetic DS banks from the three existing seeded original lifecycle
fixtures, checking 1,560 samples and 10,824 live record slices. These are parsing
controls, not new natural-route or runtime observations.

All fourteen projection tests pass locally on Windows Python 3.12.14,
WSL Python 3.12.3 and the existing Windows Python 3.15.2 embedded runtime.
All ten compatibility steps pass as a combined 113-test suite on Windows/WSL
Python 3.12, and seven focused CTests pass. This does not assert completion of
hosted CI or scanners; no C++ sources change and no new C++ build is claimed.
This tool and its fixture are registered in CTest and the Python 3.12/3.15
compatibility matrix. No raw original DS, literal payloads, screenshots or private
route traces are published. Full-frame, full-actor, full-RAM, whole-game,
wall-clock and physical-input acceptance remain unproved. The audited Medium
branch earns no new destruction credit and spends the last Medium bomb; the
best resource-preserving campaign checkpoint remains tick 18100 at Level 4,
286/305 credits, 7 energy and one Medium bomb available.
