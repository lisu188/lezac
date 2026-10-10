# Original Record Entry

## Original Evidence

The original executable is SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
CS addresses below become file offsets by adding `0x770`.

A silent DOSBox run used an isolated copy of all 14 shipped assets. Only its
record file was replaced: seven signed scores of -1, length eight, and
`below:::`. Normal level-one startup and gameplay produced score zero, followed
by Escape, Game Over, and Return. No process memory writes, instruction patches,
gameplay state seeds, clock/RNG/heap seeds or process pauses were used.

Player one entered `a`, Space, `b`, Backspace, `c`, Return. Player two's prompt
then appeared despite one-player mode; `z`, Return returned to the initial
main-menu pixels. Saved tables are committed as complete 92-byte fixtures.
The saved names are `a c:::::` and `z:::::::`: entered spaces are not colons.
Backspace restored the complete prior `a ` frame.

The producer initially expected `a:c:::::` and therefore reported failure.
Its report and diagnostics remain unchanged. The independent regrade checks
all 13 complete 1 MiB RAM snapshots, their relocated 43,552 code bytes per
sample, screenshots, 40 cursor-burst PNGs, canonical asset pins, and three
complete record tables. `record_entry_original.json` records the original
failure, report hash, independent result and fixture hashes. All 40 cursor
frames have identical pixels. RAM and image reads were not atomic.

## Recovered Presentation

`1845..1AD6` generates a new procedural background and requests sound
`0078/p11`. It scans records backward, passing only scores strictly below the
new signed score; equal scores retain their earlier position.

The four Italian strings are unconditional, including when English is selected.
They use the small font with eleven-pixel cells, color 31, shadow 25, and
Y positions 10, 21, 32 and 43. They show the player, insertion rank, record
congratulation and name prompt, not a level or final-score label.

`1962` frames a fixed field at (122,58), size 76x13, border color 7 and fill 8.
`197E` draws eight padded characters at (124,60), nine-pixel cells, foreground
77 and shadow 55 at offset (+1,+1). Raw `:` padding uses the period glyph.
There is no separately painted active-slot highlight. Text edits clear the
affected cell before repainting. Each entry background consumes eight shared
RNG calls; redraws and edits consume none.

The input loop uppercases a key for the letter/space check, then lowercases
accepted input. It accepts at most eight characters. Backspace resets the
previous slot to `:`. Only Return leaves the loop; Escape, digits and other
keys are ignored. Accepted characters additionally request `0000` at priority
`new cursor position`; that sound behavior is not yet implemented here.

## Regression Scope

The production renderer is compared against eight complete original 320x200
RGB frames, in both language settings: 1,024,000 pixels, no masks, no tolerated
differences. Background parameters are inferred from unobscured original
pixels; this is not naturally aligned RNG replay. Input tests exercise the
production UI controller's ignored keys, space, cap, backspace, Escape,
Return and one background preparation. Codec reconstruction compares both
complete saved tables, 184 bytes, and preserves literal spaces through JSON.
It deliberately does not claim the original zero-score queue was replayed.

The new font-face override is internal presentation state. Default behavior
for previously recovered Game Over and records pages is retained and checked
against their existing complete RGB fixtures. CI runs the actual App's existing
name-entry, cursor and repeat diagnostics early on both platforms, in addition
to the new component pixel test, and retains frames on failure.

## Remaining Fidelity Work

The acknowledgement, both-score-slot processing, signed cutoff/insertion,
zero-score pending ownership and direct Main return are now exercised through
the production controller and record store; see `end_run_record_flow.md`.
Exact typing/key-buffer timing and character sound requests remain open.
The old zero-cutoff equality observation reached unsafe rank eight and wrote
beyond the seven-entry original table; that failure is retained and is not
reproduced as unsafe host memory access. Full application CI, external review,
dependency delivery, sound/runtime fidelity and whole-game completion remain
separate gates. Broad completion and fidelity flags remain false.
