# Physical Player Records

`ActorStorage::State::player1` owns the separate 38-byte record at original
`DS:1B88`. Player 2 remains in `actors[0]` at `DS:1BAE`; the verified nonplayer
bank, stable allocation identities and compaction offsets are unchanged.
Named player writers select either record and reject indices outside 0..1.
This is record backing, not a unified original DS address space.

Level setup initializes kind, visual reference, motion/fraction/drop words,
hotspot, behavior and active animation for both players. It preserves idle,
countdown, backup animation, health and unused bytes. The start-marker locator
separately clears idle for an active player. Only the new-game path refills
both health bytes; ordinary level changes retain them.

Actual App owners commit health, active/backup animation, idle and drop state,
the death behavior/countdown, waiting decrements and reentry behavior. Motion
integration commits positions first, then zero-extended fraction WORDs and
velocity WORDs, as in `7557..758C`. Thus integration clears the fraction high
bytes even when the record was seeded with nonzero bytes. Drawing and tracing
do not rebuild either player record from typed state.

## Original Evidence

REA 6.7.0 with Ghidra 12.1.4 on WSL verifies complete writer windows against
the immutable 52,384-byte original MZ. Its SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Independent loading/relocation checks compare every byte in each selected
window. Sessions close with the target unchanged. The original record lies
beyond initialized file bytes; its initial RAM contents are not inferred from
the executable file or from supplementary linear disassembly.

The authenticated windows cover `2D91..2E0B` setup, `7557..758C` motion
writeback, `30F6..3139` death, `6A4A..6A7B` drop state, `6B71..6BD5` idle,
`7C77..7CA7` countdown and `7E94..7EB1` reentry health. The separate reentry
behavior branch and shared initialization helper are also checked directly.

Unchanged original instructions execute 2,304 seeded fragments: 256 two-player
setup cases and 512 each for motion, death, waiting and reentry. Complete
1 MiB memory and registers agree with and without the write observer. Ordered
writes reconstruct the complete output; independently expected full DS bytes
agree, including all untouched bytes. No timer, interrupt or hardware behavior
is injected. These are bounded fragments, not complete frame/startup execution.

The pinned Unicorn 2.1.4 library is verified at its actual loaded mapping:
`ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c`.
Selected complete initial/final memories and compact original record streams
are privately compressed; none is committed or publicly uploaded.

## Native Regressions

The generated GCC and strict MSVC record streams each match every original
byte, complete length and SHA-256: 357,128 bytes,
`edd44a7fb6b23a555900f465f0489f37a7314c92490631ff1d79f7246ebe1f95`.
The permanent unit checks every other storage field against nonzero seeded
payloads and rejects nine invalid-index calls without any change.

`--debug-player-record-ownership` checks real App setup, 512 integrated motion
cases, posture/backup animation, draw-time preservation, death, waiting,
reentry and level carry for both players, with the legacy adapter disabled.
The missing new-game Player 1 health write is retained as an actual failing
App source/binary before the owner integration. Compiled owner omissions are
checked separately from the unchanged O0 positive control.

Full GCC C++23 and MSVC App builds pass. The existing 45-test focused Linux
selection and 14 Windows validation commands pass, alongside the new storage
and App tests. Trace coverage now includes a nonzero Player 1 record, and the
trace unit checks all 1,608 record bytes per sample plus read-only behavior.
Hosted full CI is a separate lane and is not inferred from these checks.

## Ordinary Combat Comparison

Both native ports run the ordinary-startup 18,700-tick replay with no later
gameplay-state injections. In the retained level-4 window 18500..18700, all
201 complete RGB frames and 402 paired boundaries match the original.

All 38 Player 1 bytes match at every boundary: 15,276 additional bytes per
platform. The already-matching 31-row actor bank, 33 visual rows, eight link
rows and four scalar bytes remain equal. The combined direct-DS comparison
checks 648,024 bytes per platform without masks, including inactive tails,
guard rows and unused player bytes. All 1,612 single-byte payload corruptions
at a selected full boundary are rejected. Pixels already matched before this
record repair; this is an internal-state milestone, not a visual improvement.

Owned-storage trace output gains additive `player1_hex` and
`separate_player1_layout` fields. Existing 31-row `actors_hex` and layout
semantics remain unchanged. The observer emits physical backing as-is.

## Remaining Scope

The inactive Player 2 in this combat window does not establish complete
ordinary active two-player state parity. Seeded owner regressions do exercise
both players, but do not replace wider natural routes. Frame-pass stability,
unrepresented shared globals, full campaign/level-7 boss coverage, wall-clock
and physical-input timing, and owner acceptance remain open. Full-frame and
whole-game fidelity flags stay false.
