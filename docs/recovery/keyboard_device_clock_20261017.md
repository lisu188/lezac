# Keyboard Controller And Clock

This stage recovers the pinned VGA/AT keyboard controller and connects its
serial transfer and repeat events to the existing PIC work clock. It does not
replace the actual App's SDL input adapter or fixed 40.8 ms scheduler.

## Behavior

`KeyboardController` owns the 32-byte circular buffer, physical-key to scan-byte
mapping, repeat owner/countdown, commands, and ports 60h/61h/64h. The numeric
physical-key tokens retain the pinned host identities. All 102 supported key
tokens have make/break coverage, including extended prefixes, Pause's three
bytes and the original ignored PrintScreen token. Pause returns before changing
repeat ownership. Full-buffer drops do not undo a changed repeat owner.

A transfer is scheduled after 0.300 ms only when no transfer is pending and
the port latch is consumed. Transfer clears its scheduled flag, latches one
buffered byte and activates IRQ1. Both the game and chained BIOS reads return
the same port byte; the first read can schedule the next byte without dequeuing
it. Controller commands retain acknowledgements, type-rate lookup, LED command
state and A20 handoff. The original F6 implementation disables scanning despite
its comment. Gate2/speaker operations are caller-owned effects, not host audio.

`PacingDeviceClock` optionally attaches the full controller snapshot. Its legacy
idle profile is unchanged. Active snapshots cross-check the compact device
fields and transfer queue against the controller. The original mixer-then-
keyboard ticker order is retained; the mixer remains silent in this profile.

`PicWorkClock` now accepts keyboard transfer callbacks and in-core scheduling.
Like original AddEntry, an earlier event ends the current CPU slice and returns
its remaining budget before queue re-entry. The IRQ1 boundary is explicitly
accepted by the caller, respecting IF, PIC masks and priority. Acceptance updates
active/pending/in-service fields and the next predecode budget; the caller still
owns the CPU interrupt frame and recovered handler operation.

## Independent Evidence

Unchanged original controller functions and the original physical-key enum are
compiled with explicit adapters for PIC effects, A20, gate2/speaker and logging.
Original keyboard source SHA is
`d3ee2544a1cef6c4006e634ceb0729d550f755a6c1fe5aff20020f6e196d5afd`;
header SHA is
`e1badf7a53fd38441077402419102e716764b9116f5f6e684f8c9d51cd8b0009`.
The extracted function fragment SHA is
`cc428a6b31c56adc651e1995e7f4e0450184b6ce2585886c1e8135d2bb983d74`.

The function oracle has 31,296 cases over 32 independent buffer, latch, command,
modifier-independent physical-key, repeat and controller profiles. Every byte
value is tested for writes to all three ports. All key makes/breaks, reads,
transfer, clear and ticker callbacks are covered. Continuous/restored C++ match
all final controller fields and 23,228 ordered effects. A second original-
function execution produces identical 8,910,328 bytes. This is controlled
function extraction, not a complete original host run; its PIC effects are
recorded adapters, not proof of full PIC execution.

Separately, two existing unseeded original host captures contain 20 port-60
reads that schedule another buffered scan byte. Fourteen end their current CPU
slice early. The new replay predicts the next observed CPU_Cycles,
CPU_CycleLeft, removed I/O delay, PIC fields and controller state, without
injecting later targets. The previous CPU budget bounds earlier existing
deadlines: in the non-resliced branch, queue dispatch is not reached; in the
resliced branch the new transfer deadline is earlier than that bound. The
test therefore does not reconstruct or claim the complete original queue.

The retained 82 natural IRQ windows also pass using the production controller
for port reads, replacing the old hand-written test adapter. Their original
register/stack/BIOS/held-state and ordered I/O comparisons remain intact.
The combined clock test predicts the observed first-repeat gap of 999 ticks
for a programmed 1000 ms pause, followed by 63-tick gaps. The first controller
ticker has already run before the first IRQ. This composed repeat test is a
model test with independently observed phase targets, not a fresh full-host
active-clock replay.

## Validation

The full Linux App builds and 38 selected CTests pass, including the retained
frame/PIC/pacing, DOS, CRT/game keyboard, actual-App control and viewport tests.
Source guardrails pass 19 controls/130 runtime files. Native MSVC 14.44 strict
`/std:c++latest /W4 /WX` builds, component units, controller/port-clock replay,
82 natural IRQ windows and 65,536 BIOS cases pass. Two initial native warnings
were repaired with explicit test literal and boolean-comparison types; failed
logs and source snapshots remain retained.

Four new Python methods pass on both platforms: 40 changed/missing-input
controls, matching-output mtime retention, failed sync/replace preservation and
three protected-source output aliases. The earlier 13 IRQ fixture methods pass
on Linux, including its paired-output transaction coverage. Eight compiling
mutations are detected: serial delay, port-ready clearing, repeat after release,
Pause tail, ring position, reset scanning, CPU reslice and keyboard ticker.
Mutant runs preserve production sources unchanged.

A fresh natural original run also completes 41 IRQ windows/3,388 states, with
four private RAM/PNG samples each verifying 43,552 original code bytes. New
continuous/restored replay passes 6,776 comparisons, 6,694 dispatches and 246
ordered I/O events on Linux and native Windows. This additional run is retained
locally rather than promoted into the already-frozen corpus.

The frozen fixture totals 195,362 bytes, not full RAM or screenshots. Its
manifest SHA is
`b41fbd123223423c7211ad6453aac635b2c6ab8f7e6566fd53b6a89635754bb5`;
decoded combined SHA is
`ef2820fea3fc8bd3cb5b8a95e1d877306a897aae256583e8b5b9fd1c07f7ba10`.
The checker binds all three oracle/projector producers and authenticates the
earlier natural capture fixture before deriving port-clock targets. Exports
stage/sync one file, atomically replace it, preserve matching mtimes and reject
overwriting authenticated source inputs. CTest shares the verified decoded file
through a hardlink locally to avoid duplicate storage.

## Remaining Work

Full active-keyboard device/PIC/foreground execution from natural whole-frame
captures remains unproved. So do live App clock/owner-bus integration, natural
Pause nesting, active audio, alternative hardware profiles, complete campaign
and frame synchronization, and owner visual acceptance. Queue overflow and
unrecovered IRQ/device profiles remain explicit unsupported boundaries.
No whole-game, full-clock or App-cadence claim is made.

Current original and C++ screenshots are presentation checkpoints, not aligned
frames. The C++ capture harness uses deterministic controls and its documented
legacy diagnostic actor adapter; it is not proof of natural original gameplay.
The inspected start captures show different HUD inventory presentation. Their
states/timing are not synchronized, so the pair does not establish whether that
is a persistent renderer defect or a state-initialization difference.
All validation and captures are silent and RAM-only. Historical large decoded
foreground replay fixtures and the full native Windows App were not rerun
under the storage guard. Current-head external review and full CI remain merge
gates, including the upstream stacked PRs.
