# Continuous Prefix To First Actor Entry

## Recovered Boundary

`FrameActorEntryOperation` carries one register set, bus and live original stack
through the post-render prefix, complete boss-link loop, caller selection and
the first selected actor's animation prologue. It stops before the instruction
at `1000:615A`, where the unrecovered actor body begins. It does not return from
that actor or complete the frame.

The controlled original corpus starts 238 cases at `1000:7A57` and 796 cases at
`1000:7EBB`. There is no later memory/register injection between stages. The
prefix's writes, including physical actor changes, remain visible to links and
actor selection. Original near-return words `7EE4` and `7F5C` remain on the live
stack. Other explicit outcomes are transient queues (`804E`), restart (`77DC`),
end-run UI (`1B14`), and runtime error (`1920:00E2`).

The full-prefix `7903` constructor delegates to the existing prefix operation;
this change tests its construction and zero-budget behavior only. The new
continuous original corpus does not start at `7903`.

## Original Evidence

The producer executes structurally relocated, unchanged `LEZAC.EXE` under pinned
Unicorn 2.1.4. It checks the actual mapped shared library, all three canonical
assets and all six producer sources before and after generation. Fresh original
startup execution creates the sine table. Its SHA-256 is
`466aea5bff071d610e66710d74d2ddecc79853ece03a4ae038113e83609e72d8`.

Two independent final captures (`t240-c` and `t240-d`) are byte-identical:

| Item | Result |
| --- | --- |
| Controlled cases | 1,034 |
| Register states, including endpoints | 9,531,751 |
| Ordered writes | 1,293,667 |
| Projection bytes | 321,930,741 |
| Compressed projection bytes | 12,127,561 |
| Original code bytes checked unchanged | 43,552 |
| Instruction patches, call stubs, interrupts, hardware I/O | 0 each |

Projection SHA-256:
`472cad28cce064a2427cfc31fa51b466e009789ea1404d6235bafa67574155f6`.
Compressed SHA-256:
`e123c5f35e3d703c673f38ef2761332af342e744c9b7e5305a5d998b7d1e1a25`.
Manifest SHA-256:
`de91ed0e80875b96e71f31ac8d3bf8dc461aa80df99dbc797b809622a24f05ab`.

Observed and unobserved executions have identical complete 1 MiB final memory
and endpoint registers. Ordered writes independently reconstruct that memory.
Outcome counts are 832 actor-body handoffs, 107 queue handoffs, 75 restarts,
two end-run UI handoffs and 18 runtime errors. Actor-kind counts include selected
calls that later fail their original stack checks, not only successful bodies.

Initial seeds include states 0/1/2/255, actor counts 0/1/30/255, link counts
0/1/6/255, inactive counter boundaries, both players, animation modes, signed
coordinates, wrapped visual rows, and original stack failures. These are
controlled raw-memory profiles, including aliases and malformed counters, not
proof that every state is naturally reachable.

### Initial Oracle Guard Failure

The first two attempts stopped at case 9 because the producer's code allowlist
omitted the existing original graphics allocator `18AC:0517..0593`. The prefix
legitimately calls it through `1000:7B28 -> 2F9F`; the existing spawner operation
already models it. The corrected allowlist admits only that bounded routine in
addition to the existing game and runtime segments. No case was removed, guest
code patched, write owner relaxed or production operation changed to evade the
failure. Failed metadata and producer snapshots remain in RAM. Removing extra
visual seeds did not avoid the call, so those aliases are not its explanation.

## C++ Validation

The replay tests all nine combinations of instruction grants 1/17/4096 and
string transfer grants 1/2/65535. Every grant reconstructs the operation from its
snapshot. The corpus passes 9,306 replays, 30,145,116 register/control comparisons
and 85,353,309 dispatched instructions. Every ordered write, complete final
memory byte and endpoint register/flag matches. Zero-budget and finished calls
are inert. Intermediate arithmetic flags are excluded from trace comparison;
control flags are compared, and the grant-1 lane visits every modeled boundary.

Strict GCC C++23 (`-Wall -Wextra -Werror -pedantic`), native MSVC C++ latest
(`/W4 /WX /O2`), and complete AddressSanitizer/UndefinedBehaviorSanitizer replays
pass. Nine separately compiled controls are rejected: skipped links, wrong
nonplayer base, wrong player base, wrong restart threshold, reset handoff AX,
early actor handoff, wrong actor return word, reversed actor gate and lost IRQ
flags. Original production/test source bytes are preserved by the controls.

Nine additional computed IRQ checks deliver the existing timer operation at
prefix, link, software-Real48, caller, actor prologue, REP and restart gates.
They require 36 timer instructions, one delivery, BDA tick 100 -> 101, preserved
endpoint registers and unchanged physical-actor/VGA results. Nested and finished
delivery is rejected. These are computed context-restoration checks, not an
original hardware IRQ schedule, work-clock calibration or real-time proof.

The fixture checker pins assets, producer sources, manifest and compressed and
expanded projections. Its negative controls change, remove and replace every
input with a directory; require failed reports; retain existing exports; and
reject input/output/report aliasing. Frozen checkout protection includes this
family so Windows autocrlf cannot rewrite authenticated bytes.

All 22 focused entry, prefix, link, animation, frozen-checkout and source-guardrail
CTests pass. The fixture rejection/retention checks also pass under native Windows
Python. Native Windows Git cold checkout preserves all 54 files in 16 families
and detects all 16 CRLF negative controls.

## Limits And Next Work

- No actor behavior instruction at or after `615A` is executed by this operation.
- No second actor, actor return, transient queue, post-actor effect or full frame
  is recovered by this change.
- The production App does not yet use this composed CPU operation.
- No new natural DOSBox, live input, visual, frame-clock, endurance, release or
  whole-game parity proof is claimed.
- Only the compressed projection and compact metadata are published, not full
  RAM dumps or screenshots. All local validation remains RAM-only while C: is
  above the repository's disk-usage limit.

The next recovery boundary is the selected actor's behavior dispatch beginning
at `1000:615A`, retaining this live caller stack and memory ownership.
