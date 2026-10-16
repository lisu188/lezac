# Original Adaptive Frame Pacing

This recovers the original counter and delay-feedback rules and validates them
against two fresh, read-only gameplay observations. It does not wire the live
C++ loop to a substitute clock, prove synchronized rendering, or establish
whole-game fidelity. The governed host loop is unchanged.

## Recovered Rules

Startup copies DS:78d0 to the mutable delay DS:78cc at CS:2951. During gameplay,
CS:7903 increments the 16-bit frame counter DS:78c2. When its new value is
divisible by 30, including zero after wraparound, the game reads DOS GetTime.
It computes a wrapping 16-bit elapsed word from minute, second and hundredth
bytes, not hours, then applies unsigned comparisons:

| Elapsed Word | Delay Update |
| --- | --- |
| Below 120 | Add DS:78ca, wrapping modulo 65536 |
| 120 through 125 | Unchanged |
| Above 125 | Subtract DS:78ca, clamping at zero |

These are centiseconds over a group of 30 frames, not milliseconds per tick.
The original then carries the newly sampled clock bytes forward and calls
CRT.Delay with DS:78cc on every frame at CS:79df. Its separate software-real
display calculation at CS:7966..799a is not translated by this extraction.

The first measurement is especially important: previous-clock bytes are stale
presentation state, not a newly sampled or normalized clock. The two runs begin
with previous byte triples 111/24/40 and 106/6/39. Their first elapsed words are
24624 and 59918. Both reduce the delay from 16 to 14, then subsequent samples
reduce it to final values 8 and 6. Initializing those bytes from a fresh host time would
silently change this observed behavior.

## Original Evidence

Runs r2 and r3 execute the unchanged shipped LEZAC.EXE, with no seeded record
file, gameplay, RNG, heap or clock state. Only ordinary `1` and Return keys are
injected. The host is explicitly instrumented DOSBox 0.74-3, normal core, fixed
6000 cycles, surface output, dummy audio and disabled sound devices. The full
clean ten-variable emulator environments, commands, configuration and timed
inputs/checkpoints are retained in their exact trace-bound recipes.

The canonical-asset-bound recaptures contain 149 and 150 complete frame-pacing
groups, nine total DOS measurements, calibrated character-delay values 81 and
81, and no incomplete final frame. The earlier producer's 144/145-frame runs
and partial shutdown call remain separately retained, not relabeled as the new
producer. Each new run checks all 43,552 relocated code
bytes at five asynchronous RAM/RGB checkpoints. Screenshots and RAM are local
only; they are not synchronized to CPU trace boundaries.

The initial r1 attempt failed terminal trace validation. Its shutdown hook read
guest memory after emulator cleanup could release it. The corrected hook writes
only a terminal marker at exit. Failed captures and diagnostics are retained;
r1 is not included as successful evidence. The producer now persists terminal
failures before raising, including emulator exit status and missing end markers.

## Independent Instruction Oracle

Optional Unicorn 2.1.4 executes two unchanged original instruction blocks:
CS:7903..7919/79df for all 65,536 prior counter values, and CS:799a..79df for all
65,536 elapsed words with delay 16 and step 2. A further 240 cases cover threshold,
zero, unsigned high-bit, subtraction clamp and addition wrap boundaries across
six delay values and five step values. The latter block includes the original
clock-byte copies, which are checked independently.

There are no original function-call stubs or instruction patches. This oracle
executes bounded blocks, not the complete game loop or its DOS/IRQ/CRT services.
The fixture contract pins the original executable, oracle producer, probe,
capture producer, exact recipes, raw CSVs, result tables and replay projections.
Native C++23 tests compare both complete input domains, all 240 cases and all
299 completed natural frame-pacing groups with these independent observations.
CI needs no Unicorn or DOSBox to replay the frozen evidence.

## Remaining Integration

This evidence rules out treating the original loop as merely a fixed 40.8-ms
host tick under the captured emulator profile. Faithful integration still needs
the CRT work-clock model, DOS quantization, IRQ ordering and all per-frame work,
then original-backed input/frame-stream comparisons. Audio behavior, corrupted
rank-eight handler execution, full campaign/boss completion and owner visual
acceptance remain separate unfinished obligations.

## Review Disposition

Review of `62052768b4` found that standalone analysis ignored four contradictory
read-only provenance fields. All four counterexamples were reproduced against
that exact source: each accepted an explicitly mutated or non-read-only recipe
and labeled 144 frames as natural input. The analyzer now requires integer-zero
host guest-register/memory write counts, an unchanged executable and read-only
process-memory access. Missing fields and wrong types are also rejected. Eighteen
focused controls cover those fields; the CLI must publish no report on failure
and preserve an existing report. The original capture fixtures are unchanged.

Follow-up review of `304aaf429a` identified contradictory instrumentation and
completion claims that were silently replaced by narrower hard-coded labels.
Those four counterexamples were reproduced too. Typed capture-mode flags now
require host instrumentation and reject natural-clock, complete-stream,
whole-game or atomic-checkpoint claims. The fixed audio/player/work-clock
profile and successful private-display autorepeat command are checked as well.
Sixty-two controls cover missing, incorrectly typed and contradictory mode or
profile fields. The CLI publication/retention regression covers both guest
mutation and instrumentation-mode contradictions. Capture fixtures remain
byte-identical; this validation repair makes no new fidelity claim.

Review of `415261e2173cc0c48fb43a61bd65e88962edee1d` found that asset hashes
were self-observed rather than pinned and geometry stdout was not validated.
Changed level-asset metadata and four malformed geometry recipes were reproduced
as accepted, each labeling 144 frames natural. The producer now verifies all
fourteen shipped size/hash pins before output creation or DOSBox launch and
copies the exact verified bytes. The analyzer checks the same canonical domain,
the shared contract hash and every geometry result's window, 320-by-200 dimensions
and private-display bounds. Eighty-four asset-recipe and forty geometry-recipe
controls reject the contradictions. Shared tests mutate every shipped asset
before the actual producer preflight. Both new CLI rejection paths publish no
report and preserve existing reports. Fresh original recaptures replace the
accepted frozen frame streams; the original executable, instruction oracle,
counter/feedback helper and live App loop are unchanged.
