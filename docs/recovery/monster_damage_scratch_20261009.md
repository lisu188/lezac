# Monster Damage Shared Scratch

Private integration work, depending on the raw fatal-storage primitives.
The full fatal-entry physical-state path is not ready for publication.

## Production Ownership

The generic kinds 1..8 path in `App::updateMonsters` uses the recovered
top-left, top-right, bottom-right, bottom-left damage query. It writes the
last flame cell to `ActorSlots` shared result (`DS:2072`), the pre-motion
footprint cell to `SoundEngine` shared cursor (`DS:2074`), and the signed
damage byte (`DS:661E`) to persistent App state. These writes happen for
no-impact queries too. Corpse-only passes do not clear the damage byte.

`SoundEngine::writeSharedCursor` does not submit a request, change its
selector, or change the accepted latch. Request-attempt counting is
explicitly opt-in and uses a single bounded counter at the central latch
entry. Rejected requests count too; fixture restores and shared scratch
writes do not. Existing compatibility-hook tracing is unchanged.

The existing 1,312-case App tile-damage diagnostic checks request attempts
separately from scratch contents. Its three latch profiles remain idle,
active priority 5, and active signed priority 0x80. Scratch expectations
in that diagnostic are derived from its inputs and tile cells, not new
native fields in its older typed-state fixture. The boss-chain sound
regression is unchanged.

## Bounded Validation

The complete production sound module passes 131,072 priority cases and
131,072 shared cursor writes. Tests cover disabled-by-default counting,
both accepted and rejected requests, fixture restoration, counter reset,
and unchanged request selector and accepted latch after scratch writes.

A source-extracted block from the production App query path matches
all three native scratch values for 1,536 retained original queries,
repeated under three latch profiles: 4,608 comparisons, including 576
no-impact native queries. The input SHA-256 is
`d62624d48a325faff6fb7e6bc2e0536417fe38b5e2ff8ad57f112f0bad52b589`.
This probe uses the actual sound module and actor storage but mocks the
damage callback; it is not a complete App update or fatal-entry replay.

Eight compiled controls are rejected, including a rejected sound request
whose cursor and selector are subsequently hidden by valid scratch writes.
Production App syntax, source guardrails, affected CTest registration,
and the standalone sound CTest pass. ASan/UBSan covers both the sound test
and extracted query probe. No full local game build or screenshot is made.

Two earlier producer failures are retained: an incorrect fixture-header
name, then an extraction assertion that prohibited the cursor-deletion
negative control. Neither failure required changing production behavior.
The passing producer was further checked with explicitly sequenced word
reads and sanitizer coverage for the query probe; all earlier outputs
remain retained.

## Remaining Proof

Connect natural constructor fields, active animation and motion writeback,
fatal partial writes, and one-time byte-wrapped spawner release. Add the
complete fatal-entry protocol and compare all 6,441,984 full-update App
bytes against the retained original stream on Linux and Windows. Require
current full CI, completed exact-head external review and dependency gates
before merging. Natural routes, rendering, sound ISR, full campaign and
whole-game fidelity remain unproved.
