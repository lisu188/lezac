# Natural Escape and New-Game Map Retention

## Original Observation

An unmodified original DOSBox run used ordinary keyboard input to start level 1,
acknowledge its intro, press Escape, acknowledge Game Over, and start again.
Two aborts and three starts produced eleven complete, read-only 1 MiB RAM images.
No instructions, gameplay state, RNG, clock, or heap bytes were supplied or patched.
The initial and both returned main-menu screenshots are byte-identical.
Audio was disabled. Capture sampling pauses do not establish natural timing.

The producer SHA-256 is
`0184c012ff9fa5003ee7777e3faffea7ec252e795bb24d82b757065827b4039f`.
The report SHA-256 is
`7ae99141afa9e21b4312e102cee8dc41785412b961395345f59807434b60dbd5`.
The complete report and RAM images are retained in the fixture. Raw PNGs, the
producer, and the failed first capture remain in the task's retained evidence.
The failed first capture is not used as reload proof.

The original displays Game Over after gameplay Escape. The live object and word
map pointers, logical map contents, and complete 64 KiB segment-relative views
remain unchanged through Game Over and the subsequent main menu. Map replacement
occurs at the next start, not on Escape. The second and third starts match, but
the first and second differ in fifteen object-view bytes: thirteen background
carry-in bytes at offsets 1971..1983, and allocator bytes at 1996 and 1998.
The word views are unchanged. This is one level-1, one-player, zero-score route.

## Port Repair and Tests

The pre-fix interactive package returns directly to the title menu on Escape.
Gameplay Escape now invokes the existing end-run controller, which preserves
current scores and level for its record flow. Its abort callback does not run
the unrelated level reset or free the map. Other end-run entry paths are not
changed by this repair. The next new-game selection owns map replacement.

`abort_run_unit` covers one/two players, paused/unpaused input, zero and qualifying
scores, record ordering/cancellation, Game Over acknowledgement, and restarting.
These are port contract regressions, not new original qualifying-score evidence.
Existing menu/pause/control diagnostics now acknowledge Game Over explicitly.

`abort_map_original` executes the actual App from startup, then two ordinary
controller abort/acknowledgement/new-game sequences. It compares ten complete
map-view boundaries, 1,310,720 bytes without masks, against the original RAM.
Its output-only diagnostic receives no expected original map bytes. It uses a
fixed diagnostic startup clock and settles menus explicitly; it is not a natural
keyboard, frame-aligned, or wall-clock comparison. Screenshots are also emitted.
The fixture checker independently validates original relocation, PSP/runtime
segments, fourteen pointers, persistent allocation order, and view retention.
Thirteen corruption controls include rejecting the first-start view for a reload.

Local source checks or helper tests do not establish that the new actual-App
comparison passed. Exact-head Linux/Windows execution must establish that result.
Full C++ RAM, arbitrary fragmentation/reload history, other levels, natural death,
qualifying-score original behavior, campaign, sound and pixel parity remain open.
`original_fidelity_claim`, `port_functionally_complete`, and `whole_game_complete`
remain false.
