# Original Keyboard IRQ1 Runtime

This stage recovers the original game interrupt at `game:1091..1155`, its
chained BIOS wrappers and the pinned BIOS keyboard translation callback. It
does not integrate the operation into the actual App's fixed-rate scheduler.
Active keyboard device scheduling and IRQ1 eligibility remain separate work.

## Behavior

The game saves its registers, loads the original data segment, and reads port
60h at 10A1. Ten make/break comparisons set the two players' held-control bytes
at DS:1B78..1B81. P1 uses M/Z/X/N/C for jump/left/right/fire/down; P2 uses
Up/Left/Right/Insert/Down. Make writes one, break writes zero, and unrelated
scan bytes leave the bank unchanged. An extended prefix is not a game-held
control; the chained BIOS callback owns its interpretation.

PUSHF and the indirect far call at 1148 chain through DS:1B60 to F000:E987.
That wrapper reads port 60h again, invokes INT15 AH=4F, calls the real keyboard
translation callback, sends master PIC EOI and returns through both interrupt
frames. The two reads return the same latched port byte; they do not dequeue
two hardware scan bytes. The port owner clears the data-ready flag and may
schedule the next transfer. This stage checks those port-owned fields, not the
future transfer deadline or hardware repeat-clock prediction.

`KeyboardIrqOperation` retains each executed guest instruction, registers,
control stack, BIOS handoff and resumable state. The existing `TimerIrqBus`
provides memory and I/O; hardware delivery and elapsed work belong to its caller.
The BIOS intercept updates carry in the saved interrupt frame. Unknown code
boundaries, callback vectors or unsupported ring geometry fail explicitly.

`handleBiosKeyboardScan` implements the pinned VGA/US, no-layout profile and
SDL >= 1.2.14 lock semantics. It preserves modifier/lock bytes, extended-key
state, Alt-numpad tokens, ring wrapping/full-buffer drops, Caps/Shift behavior
and special extended Enter/slash translation. The 89-row scan table is checked
against the independently compiled original table, not used as its own oracle.

Pause exposes the original CALLBACK_Idle boundary instead of pretending the
interrupt returned. A caller can resume after the pause flag is cleared, with
the already-issued EOI skipped. Unit coverage verifies suspension and resume;
complete natural nested idle/interrupt execution is not established here.

## Independent Evidence

Two fresh, unseeded original runs use physical X key make/break events and
the emulator's own repeat ticker. Private-display X autorepeat is disabled.
The game actually programs a 1000 ms repeat pause and 63 ms repeat rate in
this profile. An initial 750 ms hold missed repeat coverage and remains a
failed target; the final route uses a 1300 ms ordinary hold.

Each final run records 41 complete IRQ1 windows and 3,388 predecode states.
They cover all ten controls, press/release, repeated Z, E/R, an unrelated ASCII
key and extended-key prefixes. The observer does not write registers or guest
memory, seed input/clock/gameplay, pause the process or materialize lazy flags.
Original CPU and keyboard callback bodies remain unchanged; read-only getters
and the selector are source/hash bound, with prior host identities retained.

The original executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Observation host SHA-256 is
`f74c3a0c885d687cc6205dcfc004f1edc49811721eafde30e32473ea63fac108`.
Eight private RAM samples verify all 43,552 relocated code bytes. Every executed
trace opcode is also compared with the relocated MZ image or pinned BIOS stub.
RAM, CPU and RGB observations are asynchronous, not atomic frame captures.

The separate function oracle compiles unchanged DOSBox table, AddKey and IRQ1
function bodies from source SHA-256
`880ef5796c968db80b7e0d23f2d5f68e86fd3d065b40f141bd77642ad2d89416`.
It covers all 256 scan bytes across 256 modifier/ring profiles: 65,536 cases,
9,961,472 BIOS-byte comparisons and 64 explicit Pause-idle handoffs. This is
function-level extraction with declared memory/I/O/no-layout adapters, not
execution of the complete original host. A second execution produces exactly
the same 20,251,540 output bytes.

## Validation

Continuous and per-instruction restored replay match all 82 natural windows:
13,552 state comparisons, 13,388 guest dispatches and 492 ordered I/O events.
All general/segment registers, the 128-byte stack, 152 BIOS bytes including
0496/0497, ten held-control bytes, port-owned fields and PIC EOI state agree.
Natural arithmetic flags are compared under IF/TF/DF mask 0700; terminal
IRET flags and saved stack bytes have their stronger explicit comparisons.
Later observed registers, memory and hardware state are targets, not inputs.

The full Linux App builds and all 29 selected CTests pass. Retained CRT/game
keyboard, PIC/pacing, HUD, actual-App controls, ownership and viewport checks
are included. Native MSVC 14.44.35207 `/std:c++latest /W4 /WX` compilation,
unit tests, both original corpora and five Python methods pass. The fixture
tests reject 172 changed/missing-input and output-preservation controls, two
output-alias cases, and terminal canonical-asset/exit failures.

Eight compiling mutations fail: omitted held-byte write, release writing one,
wrong far-call push order, skipped BIOS callback, omitted EOI, retained extended
prefix, missing ring wrap and wrong INT15 carry. Production sources are not
changed by these isolated runs. Source guardrails pass 19 controls/129 files.

The frozen fixture totals 680,773 bytes and publishes compact traces, recipes
and the compressed function oracle, not full RAM or screenshots. Manifest SHA
is `1581397389b978a431865bc5c74aa1ffdb364d2d584fd0c4c1622d75b26ed6f6`;
the combined CPU projection SHA is
`c6e91ccbb1fef9f37c9f5271f2415b2a51fedcd03d15d4665bdfb49317b99bbe`.
Frozen CI reports `raw_ram_files_verified=0`; local raw verification is a
separate step. All 22 producer/observer inputs and 14 canonical assets are
authenticated before either decoded output can be published or replaced.

## Remaining Work

The App still uses its 40.8 ms governed loop and SDL input adapter. This module
does not yet predict active keyboard transfer/repeat callbacks, select IRQ1
through the PIC clock, or connect the foreground owner bus to live App state.
Alternative keyboard layouts, non-VGA BIOS profiles, natural Pause nesting,
active sound, complete frame/campaign synchronization and owner visual
acceptance remain incomplete. No App-cadence or whole-game claim is made.

Fresh original screenshots were inspected and shown, but are not aligned with
the C++ App. The new interrupt itself is a state/I/O proof, not a new App frame.
Full local historical foreground replays and the full native Windows App were
not rerun under the storage guard. Only reconstructed, byte-verified decoded
caches were reclaimed; all compressed traces, raw/failed captures, source,
binaries and prior reports are retained. All runs remain silent and RAM-only.
Current-head external review and fresh full GitHub CI remain merge gates.
