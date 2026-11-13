# Buffered Menu Keyboard Recovery

This recovery distinguishes physical key events, BIOS queue entries and characters
read by the original legacy CRT services. It does not claim whole-game fidelity,
all keyboard layouts, DOSBox frontend shortcut parity or authentic manual input.

## Original Observations

Silent private-Xvfb captures ran the original temporary copy with its natural
startup clock. The observer restored one clock hook per successful original run;
there were no gameplay writes, seeded game state or typing-delay gates. All input
was scripted physical input. The archived records include read-only BDA flags at
`0040:0017`, decimal accumulator `0040:0019`, BIOS buffer head/tail and the menu
character at `DS:2058`.

- Fifteen Control combinations do not enqueue a character: `1,3,4,5,7,8,9,0`,
  equals, semicolon, apostrophe, grave, comma, period and slash. Typing continues
  and fresh ordinary `1` still skips typing and subsequently selects a game.
- Do not reject all modified digits. Ctrl+2 exposes the extended scan byte `03`;
  Ctrl+6 produces byte `30` and Ctrl+minus byte `31`. These are valid consumed
  typing skips, not player selections.
- F11/F12 and Shift, Control and Alt variants do not skip typing. Enhanced BIOS
  words can move through the queue without becoming legacy CRT characters. The
  Ctrl+F11/F12 capture also exercises DOSBox frontend cycle shortcuts; this is not
  a claim that the port reproduces that frontend.
- Alt+Tab does not enqueue a legacy character. The installed DOSBox keyboard
  table also gives Alt+Return no BIOS character, but its fullscreen frontend
  behavior was not runtime-validated here.
- Alt+numpad digits accumulate as a decimal byte, independent of Num Lock in
  these captures. They do not immediately enter the character queue. Alt+1
  yields byte `01` only when Alt is released and consumes a typing skip.
- At the ready menu, Alt+108 yields lowercase `l` and starts the English redraw
  only on release. Alt+364 wraps to the same byte. Alt+0 and Alt+256 wrap to zero
  and produce no character. An intervening raw physical Alt+A emits its extended
  character without clearing the pending decimal digits.
- Releasing either Alt commits the accumulator and clears the BIOS's single Alt
  flag, even with the other Alt physically held. Subsequent keypad keys are no
  longer accumulated, and releasing the remaining Alt does not emit a duplicate.

## C++ Integration

`InputMapper` keeps no character (`std::nullopt`) separate from an unsupported
but buffered character (`Key::Unknown`). Modifier-aware eligibility filters the
observed Control noncharacters and enhanced function keys. Its byte accumulator
tracks Alt make/break events, wraps decimal arithmetic to eight bits and exposes
the generated character on release.

The application's event path applies this character input to the main menu and
level intro while retaining existing physical gameplay bindings and other-page
dispatch. Typematic keypad events can accumulate without prematurely skipping
typing. Consumed skips drain queued key events while processing their modifier
state: an already-queued Alt release is consumed, whereas a still-held accumulator
survives for a future release. Those queue-boundary regressions are deterministic
SDL-event tests, not an original timing-trajectory parity claim.

The normal-entry-point physical harness checks the fifteen ignored Control
combinations, held Ctrl+1, eight enhanced-function cases, Alt+Tab, zero/wrap,
delayed language changes, overlapping Alt releases, intro typing and the blocking
intro wait. Unit tests cover 512 decimal values and modifier priority. Existing
menu, name-entry, physical control and reentry tests remain separate regressions.

## Evidence And Failures

[`bios_menu_input_20261001/manifest.json`](evidence/bios_menu_input_20261001/manifest.json)
pins 20 unmodified raw records, six exact executed observer versions, six images
and the packaging producer. `tools/check_bios_menu_input_evidence.py` verifies
the archive and rejects seven claim/status/state mutations. Original observations
are separate from the corrected C++ physical checks.

- The pre-fix C++ Ctrl+1 run is retained as failed: it skipped typing incorrectly.
- The first original Ctrl+2 expectation is retained as failed because its first
  post-input frame was transitional. A separate settled capture proves the skip.
- The first Alt+A injection used an xdotool chord, which synthesized an Alt break;
  that failed expectation is retained. The separate raw-keycode run retains Alt
  and proves the accumulator behavior. It does not rewrite the failed attempt.
- The first new C++ physical harness completed its noncharacter checks but timed
  out during intro cleanup. That run remains failed. A separately archived run
  respects the final intro wait and passes all three scenarios with child exit 0.

Corrected C++ executable SHA-256:
`7e83d43c39db5d06c9888361a7ba8d0f825e57253a87569ff5f6a0e8a7a746ac`.

The completed English screenshots after Alt+108 have equal 320x200 RGB SHA-256:
`1ba172f477005a57a01132e42042e54a5d1454f5b7361ceba9cab8b36a715b58`.
This establishes that completed menu image, not frame-aligned startup, input
timing, campaign completion or general game parity.

Other BIOS combinations, non-US layout keys, Ctrl+Break handling, frontend
shortcuts, name-entry character semantics and the broader campaign remain
separate recovery/verification work. `port_functionally_complete=0` and
`original_fidelity_claim=0` remain unchanged.

## Local Validation

- Updated menu model, event-queue repeat model and menu frame flow: 3/3 passed.
- Evidence archive, source guardrails and completion-status checks: 7/7 passed;
  the evidence checker also passed with native Windows Python 3.10.
- The broader 22-test selection passed 20. The repeat live test refused an
  existing output directory; a separate fresh-directory run passed all three
  held-choice/intro scenarios. Existing evidence was not deleted to obtain green.
- The generic `test_ui_xdotool.sh` failed `app_still_running_after_escape` on
  both this executable and the unchanged PR253 package executable with SHA-256
  `4dc99d5089fce42f3899fbbc3b97c01202776530620c2a2ea591f5075ce934f3`.
  This known baseline failure is retained, not recast as a passing UI check.
- The new normal-app BIOS matrix passed standalone and through CTest. Existing
  normal menu checks, physical player-key ownership, record entry and selected
  original-backed reentry regressions passed in the broader selection.

Full Windows/Linux CI and extracted release-package validation are delivery
gates, not implied by these focused local results. CI preserves the new physical
matrix's raw frames and records as `bios-menu-input-linux`.
