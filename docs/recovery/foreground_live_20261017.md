# Natural Foreground Interrupt And Glyph Work

The composed original `game:7903..7A13` operation now has natural evidence for
both changed HUD drawing and a timer interrupt during CRT delay. The earlier
natural foreground corpus contained neither path. The recovered C++ operation
itself is unchanged; this adds original-backed route coverage and strengthens
the replay harness.

## Original Windows

The unchanged original executable has SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The read-only observation host has SHA-256
`264fc86db615ea5485936d1636a122fa08d89718f0238be9e926155cf34ae38a`.
Five local RAM samples verify 43,552 relocated code bytes each. Their hashes
are retained, but raw RAM images and screenshots are not published.

- Initial frame-counter 0: original delay 16 ms, 96,517 predecode boundaries,
  one HUD call, 40 REP dispatches and 32 changes to the observed HUD regions.
  The stale objective cache values are refreshed through the real formatter
  and glyph-copy code, including the DS:2074 scratch alias.
- Frame-counter 134: original delay 8 ms, 47,988 boundaries, and one natural
  IRQ0 entry at boundary 32,893. The pending PIT event was about 5.482262 ms
  away at entry. The observer only selected this condition; it did not create
  the event or force delivery.

Continuous and restored C++ execution compare all 144,505 states, yielding
289,010 comparisons, 304 string transfers, 48 computed millisecond grants,
22 computed device callbacks and two computed IRQ deliveries across the two
replay modes. The single original IRQ per corpus is predicted independently
by the recovered clock; observed IRQ boundaries are not used to deliver it.

All general and segment registers, IF/TF/DF, owned memory, stack, BIOS state,
PSP bytes, sound state, palette and 272 indexed HUD pixels are checked at each
boundary. Original lazy arithmetic flags are not materialized at every
predecode point. Their saved stack bytes at the natural interrupt boundary
are compared as ordinary captured memory, but this is not an all-instruction
arithmetic-flags claim.

The timer follows the idle-sound branch. The only I/O event is `OUT 20h,20h`;
there are no injected port-read responses. The live harness rejects a corpus
that leaves this EOI-only profile. This does not establish active speaker or
PIT2 input behavior.

## Visual Evidence

The replay can emit its actual final C++ HUD memory and computed palette.
Independent original target pixels are kept separately in the dump. Both
Linux and native MSVC produce byte-identical dump files. The two 17x8 regions
match at both retained boundaries. The comparison images stack those regions
and label original versus C++ in the surrounding report; they are not App
frames and do not establish full-screen pixel equality.

## Validation

All 61 focused CTests pass, including the 58 preexisting checks. Native MSVC
`/std:c++latest /W4 /WX` compilation, live replay, the 96-profile palette
oracle and eight Python fixture methods pass.

Four isolated faults pass the earlier natural foreground fixture and fail the
new one: disabled IRQ eligibility, an uncommitted IRQ snapshot, wrong HUD word
copy width, and a wrong HUD scratch address. This demonstrates new coverage
in the composed natural corpus, not that all earlier subsystem tests missed
these faults. The unmodified baseline passes both corpora.

The fixture checks bind 19 shared/new producer inputs and reject all 76
changed/missing-source/output-preservation controls, corrupted fixture files,
and incomplete or discontinuous traces before publishing outputs. Existing
matching decoded outputs are not rewritten. Local CTest paths can therefore
share verified input inodes without allocating another large corpus; checks
confirm that all four shared inputs retain their modification times.

## Remaining Work

The actual App still uses its fixed-rate governed loop. This work does not
replace that scheduler, connect the reconstructed foreground memory bus to
the live owner state, or execute downstream view drawing after `7A13`.

The two features occur in separate natural windows. Natural IRQ delivery
during changed glyph copying, active IRQ1/repeat, active sound, rendering
through `7A57`, full-frame RGB comparison, full campaign behavior and owner
visual acceptance remain unproved. No whole-game or frame-level completion
claim is made. All new runs and outputs remain silent and RAM-only under the
existing storage exception. Current-head external review and full CI remain
required before merge.
