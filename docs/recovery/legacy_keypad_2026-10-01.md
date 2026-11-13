# Legacy Reader Keypad Recovery

This follows the BIOS menu input recovery merged in PR254. The target is the
original LEZAC.EXE observed through the installed DOSBox 0.74-3, not every PC
BIOS, keyboard layout or emulator frontend. It does not claim whole-game
fidelity, calibrated input timing or authentic manual input.

## Original Behavior

Natural-clock original captures used temporary copies, private Xvfb and dummy
audio. Successful runs restored their one clock observer and exited cleanly.
There were no gameplay writes or typing-delay gates. Read-only observations
include BIOS queue head/tail, Alt accumulator, modifier flags, the last CRT menu
character and language/player selection bytes.

- Alt plus keypad minus, plus, decimal, multiply, divide and Enter does not
  interrupt menu typing. Five entries pass through the BIOS queue but never
  reach the legacy character reader. Decimal with an initially zero Alt token
  leaves both the token and queue unchanged.
- Control plus keypad minus, plus, decimal, multiply and divide likewise
  leaves typing active while the BIOS queue advances. These are not equivalent
  to ordinary buffered-but-unsupported menu characters.
- Control plus keypad Enter is an exception: the original exposes byte 10 and
  consumes a typing skip. An unmodified keypad plus exposes byte 43 and also
  consumes a skip. A subsequent fresh physical `1` selects one player.
- Keypad decimal contributes a zero digit to an existing Alt numeric token.
  Alt `1`, the five other keypad operators, decimal and `8` leave the token at
  `1,1,1,1,1,1,10,108`. On release, byte 108 switches the menu to English.
- The same decimal-zero contribution and release were observed with Control
  held during the operator burst. The raw queue details differ for some
  Control+Alt combinations; this is not frontend-shortcut parity evidence.
- Control+Alt+top-row `1` remains a valid consumed skip, exposing extended byte
  120. Control-only digit rejection must not override Alt translation.

## C++ Changes

`InputMapper` filters the five modified keypad operator words, additionally
filters Alt+keypad Enter, and treats Alt+keypad decimal as numeric zero before
the eligibility filter. Control+keypad Enter and ordinary keypad input remain
buffered. No physical gameplay binding or other-page key dispatch was changed.

The model tests exercise left/right modifiers, modifier combinations, ordinary
keypad preservation, the Enter exception and interrupted decimal composition.
The normal-entry-point physical harness now runs four scenarios. Its new keypad
matrix checks six Alt and five Control combinations during menu typing, intro
typing and the blocking intro wait, followed by fresh character controls and
visible gameplay. The composition scenario checks decimal input without a
character before release and a complete language redraw afterward.

Xvfb exposes `KP_Decimal` at both key positions 91 and 129. The harness identifies
the legacy decimal position through its unique `KP_Delete` alias and records
the resolved keysym and physical keycode. It still rejects ambiguous mappings.

## Evidence

[`legacy_keypad_20261001/manifest.json`](evidence/legacy_keypad_20261001/manifest.json)
seals 23 raw records, four exact executed observer versions, eight images and
the packaging source. `tools/check_legacy_keypad_evidence.py` pins the archive,
validates observed byte/queue transitions and rejects ten deliberate mutations.
The prior BIOS archive remains unchanged historical evidence.

The baseline negative controls use the executable from the validated PR254
Linux package, SHA256
`7e83d43c39db5d06c9888361a7ba8d0f825e57253a87569ff5f6a0e8a7a746ac`.
It wrongly skips typing for the Alt operator burst and fails to switch language
for the decimal sequence. The corrected executable is SHA256
`f7ecfa1eefb12dba4fe11dfc480696d4cd0552fe554f0e77a09c753207f02c3f`.
Both corrected probes have fresh-selection controls and clean child exits.

The original and corrected C++ completed English menu after the same decimal
sequence have identical 320x200 RGB pixels, SHA256
`1ba172f477005a57a01132e42042e54a5d1454f5b7361ceba9cab8b36a715b58`.
This proves the paired completed-menu images, not input-trajectory, campaign or
whole-game parity. Intermediate operator screenshots were also inspected and
shown, with timing/alignment limitations kept explicit.

## Retained Failures

Seven failed records remain failed:

- An initial Alt operator run rejected queue movement, although typing stayed
  active. A fresh run explicitly allowed BIOS queue movement while retaining
  character and fresh-selection checks; the first record was not relabeled.
- Two baseline C++ mismatches described above.
- An original startup clock-boundary failure before any injected key.
- An original allocation guard failure before any capture or clock hook.
- A wrong decimal expectation included an extra zero and produced byte 240,
  not 108. The corrected fresh input sequence was captured separately.
- The first expanded C++ matrix stopped at ambiguous `KP_Decimal` lookup. Its
  exact earlier source and failed composition record are retained alongside
  the two scenarios it had completed. A fresh corrected matrix passed all four.

The operational C++ probe also respects the intro's post-skip delay during
cleanup and fails an otherwise observed record if its child needs termination.
All earlier records retain their exact executed sources.

## Validation

A fresh focused Linux CTest run passes 26/26 checks, including the four-scenario
normal-entry BIOS input matrix, physical gameplay key ownership, menu/end-flow
frame inspection, record entry/persistence and completion/fidelity guardrails.
The live BIOS matrix takes 90.55 seconds and key ownership takes 9.80 seconds;
both use private Xvfb and dummy audio with clean child exits. The sealed archive
checker also passes with native Windows Python. These focused checks do not
replace the full Linux/Windows CI and release-package validation required before
merge, and do not establish whole-game completeness.

Remaining work includes other enhanced navigation/Control combinations,
non-US physical positions, name-entry byte semantics, Ctrl+Break, emulator
shortcuts and the complete campaign. The full game goal remains incomplete.
