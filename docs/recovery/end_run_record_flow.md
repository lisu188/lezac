# Original End-Run Record Flow

## Original Evidence

The executable remains SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
CS addresses become file offsets by adding `0x770`.

`1CF8` waits for one ReadKey before the record loop. `1D00..1D3F` processes
score slots one and two, independently of configured player count. The earlier
nonpositive check at `1C4B` only suppresses score text on the end screen; it does
not suppress record qualification. `1D18` compares the signed high word and
unsigned low word with slot seven, accepting equality. The entry routine scans
backward over strictly smaller scores (`186F..188E`), retaining existing ties
and prefix order; it shifts the lower suffix rather than sorting the table.

A fresh silent DOSBox observation used normal level-one startup and gameplay
in one-player mode with both natural scores zero. Only the isolated record file
was seeded, with signed scores `2147483647, 65536, 0, -1, -65536, -2147483647,
-2147483648`. Pressing `1` at Game Over opened player one's prompt rather than
starting another game. Escape preserved the complete prompt frame. `q`, Return
and `r`, Return inserted at ranks four and five after the existing zero-score
record. The final menu pixels matched the initial menu.

Independent regrading verifies all ten full 1 MiB RAM samples, 43,552 unchanged
relocated code bytes per sample, all ten screenshots, and three complete
92-byte tables. No process memory writes, instruction patches, gameplay state
seeds, clock/RNG/heap seeds, or process pauses were used. RAM and image samples
were not atomic. `end_run_original.json` pins the original report, producer,
screenshots, RAM samples and committed byte fixtures. The prior all-negative
cutoff observation independently supplies the literal-space and second-slot
tables used by the same regression.

## Port Contract

The controller displays Game Over or the completed-game page before starting
the queue. A key acknowledges that page; each qualifying score then gets one
name prompt, and the final prompt returns directly to Main. Pending ownership
is explicit, so a score of zero can be committed or retained after a save
failure. Qualification is checked again for player two after player one's
insertion. Entered names, wire format and rendering remain unchanged.

The new component test replays both original record-file fixtures through the
actual controller and store, checking complete saved bytes after both commits.
Both configured-player settings and both end reasons are covered, along with
signed boundaries, inclusive cutoff equality, stable ties, unsorted-prefix
preservation, save retry and player-two cutoff rechecking. Completed-game unit
coverage exercises the shared dispatcher; it is not a new original level-seven
completion observation. Existing App diagnostics explicitly acknowledge the
end page and expect Main after committing, including sound and save-failure
checks. The static diagnostic now correctly labels inclusive signed cutoff
behavior instead of claiming a strict cutoff.

## Limits

Original equality can request rank eight and write beyond the seven-entry
table. The port qualifies and presents that rank but bounds insertion to the
table, retaining its seven entries and writing that bounded table on commit.
The original adjacent-memory corruption is not reproduced or claimed. Short
tables and JSON level metadata remain port extensions, not original contracts.

Typing, physical keyboard-buffer timing, character sound requests, naturally
aligned RNG replay, original completed-game gameplay, unsafe rank-eight memory
effects, exact-head full CI, external review and dependency delivery remain
separate open gates. No whole-game or sound/runtime fidelity claim is made.
