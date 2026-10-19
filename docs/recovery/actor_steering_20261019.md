# Original Actor Steering and Real48 Square Root

## Recovered Scope

`ActorSteeringOperation` executes the original game helper `1000:346B..3586`,
the live behavior-4 call site `1000:710D..712B`, and the RTL square root
`1920:0FC2..101E`. Its 158 new instruction cases reuse the established Real48
multiply, add, divide, compare and integer-conversion instructions. No host
floating-point approximation, call stub or instruction patch supplies an answer.

The vector helper converts two signed words to Real48, computes their length,
divides an **unsigned** speed word by that length, multiplies each component,
truncates to a signed 32-bit integer, and stores only its low word through each
far output reference. A zero vector uses a zero factor. The recovered Newton
iteration retains the original exponent arithmetic, convergence threshold,
negative-input error, stack temporaries and real far return. The vector helper
executes its real near `RET 20`; call-site mode then executes the caller's jump
to `714F`. RTL errors stop at `1920:00E2` without pretending that the error
handler or the later actor path has executed.

The operation owns resumable CPU/IRQ context through `ActorFinishSnapshot`.
It does not own game entities, choose targets, advance a frame, or replace the
production `App::retargetMonster` caller in this change.

## Original Evidence

The producer authenticates `LEZAC.EXE` SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`,
relocates the actual MZ image at segment `1000`, and executes it with Unicorn
2.1.4. It verifies the actually mapped library, not only the Python package
version; the library SHA-256 is
`ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c`.

Two independent captures have identical compressed projections and manifests:

| Evidence | Value |
| --- | --- |
| Cases | 3,736 |
| Direct vector / live caller / square root | 2,136 / 64 / 1,536 |
| Returned / runtime error | 2,961 / 775 |
| Register states | 11,590,607 |
| Ordered writes | 493,199 |
| Executed instruction addresses, including reused RTL | 501 |
| Maximum states in one case | 4,718 |
| Decoded projection bytes | 82,011,457 |
| Gzip bytes | 15,349,744 |

Projection SHA-256:
`acc7c781d4fcf5d24e16ffdccefd13032830c1010b8453b30aefd1210f8ed334`.
Manifest SHA-256:
`06bb16586bd72e2555c8ff4daafe972afadf405528a084ddd561b5849ca5c3cf`.

Profiles include a signed-component boundary grid, unsigned speed boundaries,
all byte speeds on three vectors, real call-site pushes and return words,
six far-reference alias patterns, stack/direction controls, and all 256 Real48
exponents with three mantissas and both sign bits. Each case compares observed
and unobserved execution over **all one MiB of memory and all endpoint registers**.
Observed writes reconstruct the complete final memory. The 43,552 original code
bytes preceding DGROUP remain unchanged. There are no delivered interrupts,
hardware I/O, stubs, instruction patches or later-state injections in the
original baseline captures. The manifest pins the exact producer source.

`register-delta-v1` is a lossless encoding of all 14 register columns at every
instruction boundary. Each row begins with a 14-bit changed-column mask; the
first row must contain every column. This reduces storage, not coverage.

## Validation

The strict GCC C++23, native MSVC C++ latest (`/W4 /WX /O2`), and GCC
ASan/UBSan builds each pass 11,208 replays across instruction grants 1, 17 and
4,096, restoring snapshots after every grant. Each complete matrix performs
12,286,604 register/control comparisons and 34,760,613 logical dispatches.
All ordered writes, complete final memory and **all endpoint flag bits** match.
Intermediate arithmetic flag bits `0x8D5` remain excluded from trace comparison;
this is not a claim of complete intermediate arithmetic-flag fidelity.

Fourteen computed IRQ-boundary checks execute 504 handler instructions, reject
nesting and post-completion delivery, restore immediate CPU/clock context, and
compare alternate grant/snapshot continuations after injection. They are C++
scheduling tests, not original captured IRQ schedules or frame-timing proof.

Sixteen separately compiled faults are detected: component signs, unsigned
speed, zero-vector handling, significant square operand, square-root sign,
shift, precision, halving and loop, output reference, near-return cleanup,
call-site speed address, and IRQ flags/accounting. The initial proposed square
operand fault substituted one zero middle word for another; it was an
equivalent mutation for signed 16-bit inputs. The retained final control changes
the significant mantissa word and is detected. Baseline sources remain unchanged.

The frozen-fixture checker tests changed, missing and directory-replaced inputs,
failed-report retention, conflicting existing exports, and output/input aliases.
Both Python tests pass on Linux and native Windows. Native Windows Git's
autocrlf-enabled cold checkout preserves all 22 frozen families and 72 files;
removing the family rules reproduces 22 CRLF manifest faults. Source ownership
and guardrail checks pass. Full hosted Linux/Windows CI remains a merge gate.

## Production Counterexample and Remaining Work

Controlled original cases 583 and 584 use delta `(1,0)` and speed words `32768`
and `65535`. The original stores x-velocity words `0x8000` and `0xFFFF`.
Production currently clamps the speed to `32767`, so these states distinguish
the implementations. They establish a numerical counterexample, not that a
natural level reaches either state.

Production integration requires a typed boundary, original-backed caller checks,
the existing behavior-4 lockstep fixtures, and actual rendered App validation.
This PR does not change target selection, AI gates, random wandering, other
actor behavior paths or production code. A separately captured C++ boss-arena
ownership checkpoint uses injected damage and the existing production helpers;
it is not evidence that the new steering operation is integrated. The original
comparison frame shown to the user is historical and is not time-aligned.

No natural-route, full-frame, whole-game or visual-parity claim is made.
