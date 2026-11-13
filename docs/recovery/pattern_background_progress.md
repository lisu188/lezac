# Resumable pattern background

The original CS:01fc..030a routine clears the screen, initializes a seven-color
palette, and writes the 320-by-200 background in row-major order. Its horizontal
fraction update, optional row adjustment, and destination write are separate
observable states. A pixel count alone does not describe an interrupted row.

`PatternFill` retains those three semantic stages, the destination, signed
fraction, unsigned phase, and owned pattern inputs. GameRenderer uses this
operation for the existing complete menu and level-intro paths. Its partial
advance methods are also exercised through the actual App, Canvas and frame
inspector. No host pointers are reconstructed from original data.

The row wave is the truncated eight-times value of the original six-byte sine
table at DS:7bda. The 128 integer values are stable across all eleven new RAM
samples. Using that table removes a platform floating-point dependency from
production rendering; the previous floating-point implementation remains an
independent compatibility oracle in the native test.

## Original Evidence

A fresh silent, unpatched original run uses the authoritative executable
SHA-256 `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`,
normal-core DOSBox with fixed 6000 cycles, and the declared rank-eight record
file fixture. It uses no process pauses, memory writes, instruction patches,
or gameplay, RNG, clock or heap seeds. All eleven full RAM samples independently
verify 43,552 unchanged relocated code bytes, and all eleven PNGs are checked.

The seven RGB colors are read directly from DOSBox's DAC object. GDB reads
types and static addresses from the official matching debug package, without
attaching to the game. The build ID is
`791468b55d0528327548359d5679af3e487e830c`; the installed binary fingerprint is
checked before the read-only observation. Colors are not fitted from the PNG.

Three complete RGB checkpoints contain colored prefixes of 2,259, 13,216 and
27,525 pixels and an entirely black remainder. The independent original-backed
reconstruction and the actual C++ App match all 192,000 pixels without masks.
The compact fixture publishes inputs, cursor facts and full-RGB SHA-256 values,
not new full RAM images, PNGs or RGB payloads.

Separate RAM samples establish cursor states at destination 4,678 after a write,
16,373 before a write, and 30,400 after the horizontal update but before the row
adjustment. RAM, DAC, CPU windows and screenshots are not atomic or instruction
aligned. The RGB prefix and RAM destination are deliberately not equated.

## Validation And Limits

The native test compares all 6,400 original horizontal/vertical parameter pairs
against the prior renderer, totaling 409,600,000 pixels. It covers nine budgets,
zero work, restarts, semantic-stage resumes, the three original cursor states,
and six invalid-input controls. ASan and UBSan cover the new operation, Canvas,
and native test over the same complete domain.

The actual-App checker runs twice, verifying six complete RGB hashes and six
original cursor states while preserving first-run evidence. Its own regressions
reject 21 fixture mutations, five complete-frame corruptions, a missing native
marker, and a failed second invocation without replacing the first frames.

A compiled control collapses the horizontal and row stages. All three RGB
frames still match, but the native stage test and actual-App cursor replay both
reject it. The correct implementation is restored and the binary is identical
to its pre-control copy. Thirty-seven focused CTests pass, including existing
record/end-screen RGB oracles, intro contracts, render boundaries and live
physical-key ownership. All launches use dummy audio; local artifacts stay in
the isolated RAM workspace. An initial pre-fix unstarted-fill build was
terminated, and its failure log is retained separately.

These are renderer-progress and actual-App fixture proofs, not a complete frame
stream or a natural input replay. The production interactive loop still needs
original-backed work-clock/IRQ dispatch, clear-to-fill RNG ordering, typing
delays and corrupted-handler execution. In particular, the open rank-eight
finding on merged PR #388 is not closed by this change. Full-game, campaign,
audio and owner visual acceptance remain unproven.
