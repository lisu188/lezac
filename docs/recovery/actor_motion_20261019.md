# Original Actor Movement and Terrain Helpers

## Recovered Scope

`ActorMotionOperation` executes game movement instructions `7018..73E5`
and the nested tile-fracture, tile-sampling and friction helpers at
`370E..3A53`, `5AFD..5B83` and `5B86..5BC9`. The two new headers contain
694 instruction cases: 335 movement and 359 terrain cases. Every new case is
executed by the frozen original corpus. Existing original steering, software
Real48, RNG, sound-latch and IRQ instructions are reused one instruction at a
time. There is no host floating-point substitute, call stub or instruction patch.

The operation stops before common integration at `73E5`, after a real standalone
helper return, at the RTL error handoff `1920:00E2`, or at an observed divide
fault before its handler. It preserves live stack/register state and resumes
from snapshots. The CPU divide fault retains the pre-handler instruction
pointer, registers and memory; interrupt-zero handler execution is not recovered.

Recovered behavior includes gravity, landing, friction, behavior-4 support and
target gates, original wrapped signed-word Manhattan distance, live-stack Real48
steering, actual wandering RNG draws, behavior-3 ledge/facing changes, kind-4
terrain damage, rectangle/tile queues, and signed half-speed side reflection.
The friction helper is compared over **all 65,536 velocity words**. In particular,
16-bit absolute value of `0x8000` remains negative and takes the zeroing branch;
it is not replaced with a host-width absolute value.

## Original Evidence

The original executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Its actual MZ image is relocated at segment `1000` and executed by Unicorn 2.1.4.
The actually mapped library is checked before and after generation against
`ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c`.
The manifest pins the executable and all ten transitive producer sources.

Two independent corrected captures have byte-identical gzip projections and
manifests:

| Evidence | Value |
| --- | --- |
| Cases | 78,927 |
| Direct movement / fracture / sampling / friction | 6,475 / 376 / 6,416 / 65,552 |
| Continuous actor / actual caller cases | 54 / 54 |
| Integration / helper return / RTL error / divide fault / actor return | 6,437 / 72,316 / 36 / 30 / 108 |
| Register states | 8,414,926 |
| Ordered writes | 669,502 |
| Executed original instruction addresses | 1,704 |
| Maximum states in one case | 5,336 |
| Decoded / gzip bytes | 98,886,957 / 14,308,854 |

Projection SHA-256:
`07f6cc24b0e2460b23908306d34445cd1b4a5e0014253dc394ca2b3b945756b8`.
Manifest SHA-256:
`5a92392c878cab569d73e108837835d429ef81062e605095892b21db2290ed6c`.

Each observed run is compared against an unobserved run over all one MiB of
memory and all endpoint registers. Ordered writes reconstruct complete final
memory, compacted initial seeds reconstruct the exact initial image, and all
43,552 code bytes preceding DGROUP remain unchanged. The lossless
`register-delta-v1` trace retains all 14 columns at every instruction boundary.
There is no hardware I/O, delivered IRQ, later-state injection or patched code
in these original baseline runs. CPU interrupt zero is observed at the actual
faulting DIV/IDIV and stopped before handler delivery.

The continuous cases start at `6053`; caller cases start at the actual `7EBB`
loop and execute its pushes, actor call and real near return to `7EE4`. The
replay asserts that **all 108** complete cases actually return, rather than
counting a premature runtime error as a complete movement continuation.
These use controlled descriptors, no boss links, and no flame/bomb/trigger group.
Fracture scans use finite fenced maps, not arbitrary invalid or zero-width maps.
Exhausting the byte at `7018` does not recover the separate behavior-0 player
branch, which is taken earlier.

An initial independent diagnostic pair accidentally enabled the boss-link pass
through an unrelated seeded `DS:79F9` byte. It reached an out-of-scope Real48
error and exposed a difference in otherwise undefined AF materialization.
That pair and its exact producer are retained in RAM, not accepted as the final
corpus. The corrected producer clears the no-link condition **before entry** and
recaptures everything; it does not overwrite intermediate state or relax endpoint
flag comparison. The shared existing Real48 implementation is unchanged.

## Validation

Strict GCC C++23, native MSVC C++ latest (`/W4 /WX /O2`), and GCC ASan/UBSan
each pass 236,781
replays over instruction grants 1, 17 and 4,096, restoring snapshots after each
grant. Each full matrix performs 9,180,512 register/control comparisons and
25,007,997 logical dispatches. All ordered writes, complete final memory and
all endpoint flag bits match. Intermediate arithmetic flags `0x8D5` are excluded
from trace comparisons, so this is not complete intermediate flag fidelity.

Sixteen separately compiled faults are detected, covering gravity, period and
signed-distance gates, RNG entry, facing lookup, side-reflection divisor and
position adjustment, both queue caps, rectangle stride, tile limits, damage
tables, above-cell marker, friction threshold/step and IRQ accounting. The
baseline and all fault variants compile successfully; baseline sources remain
unchanged. These use one-instruction grants, separately from the full matrix.

Eighteen computed IRQ-boundary checks execute 648 handler instructions. They
cover movement gates, steering, RNG, terrain loops/writes, friction and signed
reflection. They reject nested, masked and post-completion delivery, restore
CPU/clock context, and compare alternate-grant snapshot continuations after
injection. They are C++ scheduling tests, not captured original IRQ schedules.

Nine constructor/snapshot rejections, zero-budget behavior and a precise
divide-fault control pass. Both fixture Python tests pass on Linux and native
Windows, including changed, missing and directory-replaced inputs, failed-report
retention, conflicting exports and output/input aliases. Linux Git and native
Windows Git cold-check the new family (four files), with an explicit negative
control reproducing CRLF conversion when its protection rule is removed.
The full 23-family checkout remains a hosted-CI check.

The actual Linux App builds successfully. Its existing debris diagnostic emits
an unchanged snprintf truncation warning; the new core test is warning-clean
under strict GCC and MSVC builds. The prior 3,736-case steering corpus still
passes its 11,208-replay matrix. Source ownership and guardrail tests pass.
The fresh App build passes 21 focused CTests, including movement, steering,
actual-App original-backed vectors, malformed CLI inputs, two-player targeting,
player-state gates and rendered frame captures.

## Remaining Boundaries

This change adds a recovered core operation and regression evidence, not
production App movement integration. The current App still uses its existing
movement dispatcher; only the separately delivered Real48 homing vector path
is production-integrated. In particular, zero AI periods and wrapped-distance
gates are not silently changed in production by this PR.

Player behavior-0, later actor-loop/frame continuation, original IRQ/work-clock
coupling, natural routes and aligned frame/pixel timing remain incomplete.
Fresh production level-3 captures are visual regression checkpoints, not proof
that this new operation is connected. No full-frame, natural-route, visual,
whole-game or completion claim is made. Full hosted Linux/Windows suites and
a clean exact-head external review remain merge gates.
