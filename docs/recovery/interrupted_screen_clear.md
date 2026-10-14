# Interrupted Screen Clear

## Original Execution

The unchanged LEZAC executable SHA-256 remains
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Four new silent isolated runs used natural level-one scores `[0,0]` and
declared record-file fixtures. Three runs remained unpaused; a fourth ran
normally through the failure and then used one confirmed SIGSTOP diagnostic
snapshot. A fifth failed startup accessor check is retained separately.
No game instructions, process memory, gameplay, RNG, heap or clock were patched.

The installed DOSBox executable was bound by SHA-256, matching 0.74-3 source
and machine-code references from its own AH/DX and CS:IP diagnostics. Read-only
sampling checked selector/base consistency and loaded-game data, stack and
gameplay controls. Equal before/after CPU windows are useful corroboration,
not proof that an unpaused observation was atomic or instruction-aligned.

Both rank-eight runs retain the observed 13-byte handler overwrite. The saved
keyboard far target becomes `0800:0000`. Stable later samples show execution
at `0800:f699`, whose conventional-memory bytes are `ffff`, alternating with
the INT06 vector `f000:1060` and its callback/IRET sequence `fe380300cf`.
The exception stack retains `0800:f699`; the deeper keyboard chain return is
runtime CS:`114c`. BIOS ticks and subsequent game RAM/RGB snapshots stop
changing, but the emulated CPU is looping, not halted.

The keyboard interrupt saved frame identifies the interrupted instruction as
CS:`07ec`, `f3aa` (`REP STOSB`) inside rectangle fill CS:`07c5..07f7`.
Saved ES is `a000`, AX is zero, DI is 33,705, CX is 215, the row-start offset
is 33,600, and 95 rows remain. These independently read stack values agree
with the exact 33,705-pixel black prefix in both complete RGB frames. Clearing
that prefix of the prior background reconstructs all 64,000 pixels in each
case, without masks or differences. Rank-seven controls preserve the saved
handlers and continue BIOS ticks and rendering; the settled control accepts
player two's `r`.

## C++ Operation

`ScreenClear` owns progress for the full-screen specialization of that fill.
It advances by an explicit pixel-work budget, retains its palette index/color,
and exposes the next-pixel DI, row start and remaining row/column counts.
Zero budget retains the frame; resumption continues from the saved offset.
Its canonical cursor does not model row-epilogue instruction phases.

The native regression uses the existing production menu/background renderer,
then executes the resumable clear up to the independently observed DI.
Both whole frames are compared with original RGB fixtures: 128,000 pixels,
zero masks and zero tolerated differences. Pattern inputs inferred from
unobscured original pixels are fixture inputs, not aligned RNG replay.
Budget, row boundary, completion, restart, clip and indexed-pixel behavior
are checked independently of the original fixtures.

## Remaining Integration

This does not yet wire the operation into App rendering or dispatch corrupted
virtual interrupt targets. The observed work budget is supplied only by the
component test; it must not become a runtime constant. The App still needs
an original-backed input/interrupt/work scheduler, the complete render and
palette sequence, and full-App validation. Sparse RGB/CPU observations are
not a complete synchronized frame stream. Exact-head CI, external review,
campaign, audio and whole-game fidelity remain separate open gates.
