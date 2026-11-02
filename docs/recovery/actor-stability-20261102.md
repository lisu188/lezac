# Actor Replay Stability Investigation

## Status

The optimized actor-pass stability hold is **not cleared**. No production
operation, comparator, ownership guard or original fixture is weakened here.
This work adds authenticated single-case replay, reproducible diagnostic
controls, actual failure evidence and focused original instruction analysis.
It does not establish whole-game fidelity, App integration or campaign coverage.

The earlier RAM-only jobs did not survive the interruptions on October 27 and
November 2. Their missing terminal reports are not counted as passes. The
October 25 ordinary failure was reported in the session, but its original
report was lost. The independent November 2 reproductions below supersede that
missing evidence. Compact typed host diagnostics are now retained privately
outside WSL RAM; no full guest-memory image or core was exported.

## Authenticated Historical Build

Use the source tree at `e5c8caf`, replacing only
`src/core/frame_actor_pass.hpp`, `src/core/player_post.hpp` and
`tests/core/frame_actor_pass_test.cpp` with their versions from
`eacb54ff8770f24e6f08ebfd7bd79ef43ee18636`. Build with GCC 13.3:

```sh
g++ -std=c++23 -O1 -Wall -Wextra -Werror -pedantic \
  -I/dev/shm/actor-historical/src \
  /dev/shm/actor-historical/tests/core/frame_actor_pass_test.cpp \
  -o /dev/shm/actor-historical-o1
```

The resulting ELF is 905,632 bytes, SHA-256
`b1c719393f987cd2a98090055c8cc06d5d71589090599a36f32c4d2fd5da47f6`.
`-O2` is not the historical profile. A separate `-g` build is used only for
external DWARF; its executable PT_LOAD bytes must exactly equal the original
ELF. The 684,625 executable bytes have SHA-256
`cba6b0faed1b643ea0ba609d9d6e74e7a6112f31240ffa251dc2bfeebb9f57cb`.
The collector verifies those bytes against the stopped process as well.

The full authenticated corpus remains 35,707,847 bytes, SHA-256
`799531ca906973fc9f0b619855e42898aa5eb876b4086641cc6b637eb63a40d3`.
The canonical MZ remains 52,384 bytes, SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

## Fresh Failures

- The uninstrumented control passed six complete runs, then failed on attempt
  6 with `Frame actor entry ID-toggle profile differs`. No debugger, preload
  hook, guest mutation or full-memory artifact was used. All protected input
  hashes were unchanged.
- The initial hardware observer passed five runs, then failed at case 813,
  row 11049, with CX `02CC` instead of `00CC` at original `1000:30D0`.
  Other register columns matched in the failure output. This observer watched
  only the ownership-exception constructor, so the trace failure was not
  captured before unwinding. Its result correctly reports failure, not bounded
  non-reproduction.
- The widened observer captured a real
  `Frame actor contact ID-toggle/callee ownership differs` exception on its
  first attempt. It stopped before unwinding, verified all owned executable
  bytes, and retained a bounded typed report. The frame-pass dispatch count and
  replay cursor were 605. This was not a synthetic calibration. The report's
  optimized DWARF values are advisory; they do not yet establish the cause.

The private 55,374-byte typed report has SHA-256
`3e9e2fb96e7d66fba1192c36312476d972c537a144ac3779055957b4e28d715f`.
It is not included in the repository. The public receipt contains only compact
outcomes, hashes and evidence identifiers.

## Diagnostics

`actor_pass_plain_parent.py` is the uninstrumented control. It authenticates the
exact historical ELF, complete corpus and MZ before execution. A replay failure
is preserved separately from an abnormal process exit. Passing bounded runs
never clear the hold.

`actor_pass_hw_parent.py` uses the compiled native layout check from
`actor_pass_ptrace_layout.cpp`. It attaches after ordinary process startup and
uses x86-64 debug registers, with no software breakpoint or guest-data write.
The pinned stops cover the invalid_argument and runtime_error constructor PLTs
and the contact-validation failure branch at ELF offset `3ABF4`. The last stop
also reads four native game/id ownership pairs and a variant tag, 33 bytes of
host metadata, before exception construction clobbers comparison registers.
These offsets apply only to the pinned ELF, not arbitrary builds.

`actor_pass_guard_gdb.py` accepts the stopped owned child, relocates the
byte-identical external DWARF with `add-symbol-file`, and retains selected
typed state. It performs no inferior function calls. Its own-launch mode uses
software breakpoints and explicitly records that distinction. Optimized values
remain advisory; lexical lookup must not borrow a caller's same-named local.

`actor_pass_throw_stop.cpp` and `actor_pass_throw_parent.py` provide an optional
host-interposition alternative. It is explicitly instrumented, not an ordinary
control. Unexpected exits, changed inputs and missing inputs fail closed.
All modes disable core dumps and use bounded, fresh RAM output directories.
Games and child processes use dummy audio; system volume is not changed.

## Original Instructions

Actual REA 6.7.0 / Ghidra 12.1.4 analysis on WSL completed 18 calls, closed the
session, returned server exit 0, and preserved the canonical MZ:

- `1000:30CC`: `MOV DS,word ptr [0xC1FE]`, bytes `8E 1E FE C1`, falls through
  to `30D0`. Evidence
  `ev_d703615e3ed3e41600e116610f88f51d147babb76fe953a5405533b5ff0ba5e9`.
- `1000:753A`: `ADD DI,0xC21E`, falls through to `753E`. Evidence
  `ev_44a7d1933d4fe71b849bfdb96a2aa41160e5f96e0aecb38af43ee9016f92a7d8`.

Neither instruction writes CX. Static instruction evidence does not diagnose
the intermittent host failure. The helper's inherited advisory decompilations
at `2F9F` and `06AB` are not used as runtime proof.

## Validation And Next Step

Strict GCC C++23 compilation and eight focused CTests pass, including the
876-case / 7,884-replay original comparison, authenticated filtered CLI,
fixture rejections and bounded failure-report contract. Twelve diagnostic
report regressions distinguish bounded non-reproduction, actual replay
failure, abnormal exit, modified input and missing input. Synthetic unit and
invalid-argv calibrations verify the hardware-stop handoff; they are not
actual bug reproductions. A wrong-ELF GDB launch returns exit 1.

The `--case N` mode still authenticates and parses all 876 cases, executes only
the selected case under nine schedules, retains full-memory and ordered-write
checks, and explicitly denies full-corpus or hold-clearing claims. Its three
positive cases and eleven negative controls pass.

Next, compare the prethrow branch's native operands with its comparison
registers and the independently owned source snapshot. Do not infer a
compiler, lifetime or hardware cause from one optimized DWARF view. A causal
regression and a validated fix remain required before promoting the held
actor-pass and dependent full-frame PRs. Global fidelity flags and completion
percentages are unchanged.
