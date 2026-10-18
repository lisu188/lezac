# Private BIOS Menu Test Server Lifetime

The Linux CI job for waiting-map PR #434 (`117669111073`, run `39125319398`)
failed during `bios_menu_input_live_xvfb`, before the full suite. Its first
three scenarios completed; the fourth (`keypad`) exited before recording any
event or frame. The retained child log says `fatal: x11 not available`.
This is SDL video initialization, before the waiting-player code executes.

The original failed artifact remains on GitHub as `live-keyboard-linux-focused`,
artifact `12136396437`, 5,762,376 bytes, SHA-256
`289690ea432bbebe98dc49b6ef8b3d5c91266f24eff450e0dbd7191bb7034335`.
Its archive was inspected in RAM; no original failure evidence was deleted.

The four scenarios previously shared a default private Xvfb server while
disconnecting all clients between App instances. The installed Xvfb help
documents `-noreset` as disabling the last-client reset. The BIOS test now
uses `-screen 0 1280x1024x24 -noreset`, retaining the previous geometry and
`xvfb-run`'s default no-TCP-listener behavior. No game, input-harness, expected
pixel, event count, timeout or retry rule is weakened.

`bios_menu_xvfb_lifetime` independently starts two owned private servers. It
writes a root-window sentinel, closes the only X connection, waits, reconnects
and checks the sentinel. The actual BIOS server profile retains it; an explicit
`-reset` negative control loses it. Running the positive case without
`-noreset` fails deterministically. The CMake live test and lifetime check share
the same server-argument variable. Output logs and failure reports use unique
directories; owned process groups are terminated on timeout.
The BIOS test also places Xvfb authentication/temporary files in its owned
build directory, keeping RAM-backed validation off the disk-backed `/tmp`.

This proves the reset boundary and its guard, not a conclusive reproduction
of the exact CI SDL connection race. A local run with the prior default profile
also passed once, so a passing retry alone would not establish the cause.
The current-head CI must pass with the retained failed run still visible.
All game launches and child processes keep dummy audio. No desktop volume or
ambient display is changed; the lifetime probes create their own X servers.

The repaired profile passes nine selected CTests: cold checkout, source
guardrails, three waiting-map checks, natural-campaign replay/guard, the new
server-lifetime controls and the full four-scenario BIOS-menu observation.
After redirecting the BIOS authentication scratch to the RAM-backed build,
both server/menu checks pass again. The earlier default-profile passing run
and the failed CI archive remain separate from these repaired-profile runs.
