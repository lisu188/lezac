# Original CRT Keyboard Calls

## Recovered Behavior

`CrtKeyboardOperation` implements the original CRT `084A:02FD..0330`
KeyPressed/ReadKey paths, the CheckBreak flush at `0143..015C`, and the pinned
DOSBox 0.74-3 BIOS INT16 AH=00/01 callback semantics. Each guest instruction
remains a resumable dispatch. The FE38 host service is one atomic dispatch,
matching the original normal core, while the empty ReadKey NOP/jump idle loop
remains explicit and can resume after a separately declared BIOS queue input.

The operation owns original stack/flags effects, the CRT pending scan byte at
`DS:7F6D`, the break flag at `DS:7F6E`, and the shared BIOS ring head/tail.
It preserves extended-key discard, numpad translation, ring wrap, zero-key
handling, far returns and CheckBreak's near return. KeyPressed changes the
saved IRET IF/ZF bits; ReadKey preserves the caller's saved IF. Timer delivery
uses the existing recovered IRQ0 handler and restores the interrupted context.
The caller still owns IRQ eligibility; this operation is not an IRQ scheduler.

CheckBreak flushes accepted queued keys and clears its flag, then stops at
`015C` before console output and INT23. This is an explicit handoff, not a
claim that Ctrl-Break console output or process termination is recovered.

## Three Independent Evidence Sets

The successful silent natural capture r3 entered all six complete CRT call
classes through ordinary gameplay input. It contains 75 instruction-boundary
states, giving 150 comparisons across uninterrupted and per-instruction
snapshot/restore replay. Registers, control flags under mask `0x700`, the
128-byte stack window, BIOS ring/state, CRT globals, sound globals and ordered
I/O are checked. No later CPU or memory state is injected. The six natural
calls contain no observed IRQ entry, so they establish no IRQ eligibility claim.

The observer keeps the original CPU core and BIOS handler bodies unchanged.
Five independently rehashed RAM/PNG checkpoints match all 43,552 relocated
original code bytes. The emulator exits zero with a complete trace, and
canonical original assets remain unchanged. Observer, producer, parser,
contract and getter sources are hash-bound along with the launch/input recipe.
Raw RAM and PNG files remain local; the frozen checker explicitly reports
`raw_ram_files_verified=0` rather than claiming access to unpublished evidence.

The failed r1 capture is retained: its class selector treated a BIOS low-E0
marker as ordinary ASCII and missed the extended class. The corrected r2
capture reached all classes, but retained copied DOS-time metadata; it is
preserved and superseded, not silently rewritten. Only the fresh corrected r3
producer and observations form the permanent natural fixture.

Separately, an unchanged extraction of the pinned original `IsEnhancedKey`
function executes all 65,536 possible input words. The C++ classification and
translated word match every result. This is original-source function execution,
not whole BIOS handler or original-game execution.

Finally, Unicorn 2.1.4 executes both unchanged relocated original pending-byte
paths for every nonzero byte: 510 endpoints, including the real CheckBreak near
call. No BIOS provider, interrupts, original-call stubs or instruction patches
are used. A separate unobserved emulator agrees at every endpoint. C++ matches
all endpoint registers, full flags, 128 stack bytes, CRT globals and exact work
counts (four KeyPressed dispatches and nine ReadKey dispatches).

| Projection | SHA-256 |
| --- | --- |
| Natural CPU | 93370aee4a8292d33dfb528e98c9c29b4d0aa093dd354ad998ef4902c487fa58 |
| Original-source classifier | 1f946ad4784ca712e3f20cb43ab6327c86c2d929db68139aa43a48f58c47dc37 |
| Original pending endpoints | bee3faf3b021dd807e27c49e23449a7106ba0619c8cd7b4613108308c4514195 |

## Validation

- 44 focused Linux CTests pass, including six new keyboard checks and retained
  display, elapsed-time, pacing, PIC/device and DOS/timer recovery checks.
- Native MSVC `/W4 /WX` compilation, unit tests and all three keyboard replay
  modes pass. The four fixture test methods also pass on Windows and Linux.
- Unit tests cover 91 eligible timer boundaries, five masked boundaries,
  snapshot restore, an empty BIOS read that resumes after declared queue input,
  enhanced-key discard, ring wrap, saved IF behavior and CheckBreak handoff.
- The frozen contract rejects 68 changed/missing-source controls before any
  output is created or replaced, seven corrupted files and three trace
  terminal/dispatch controls.
- Nine isolated behavioral faults are rejected: saved IF, status ZF, pending
  clear, low-E0 translation, numpad scan translation, idle-loop reentry, far
  return order, timer SI restore and break-flag clear. The original source is
  unchanged by the mutation harness, and all four baseline replay modes pass.
- Source guardrails pass 19 controls with 121 mapped sources. Diff whitespace
  checking passes.

## Acceptance Boundary

This stage does not integrate the operation into the production App, recover
the game's `7A00..7A13` keyboard drain or HUD update, model active IRQ1/repeat
production, or prove natural timer interruptions inside keyboard calls.
Other BIOS services, arbitrary ring layouts, console/INT23 termination,
complete frame scheduling, elapsed wall time and pixel/frame alignment remain
outside this evidence. No whole-game or visual fidelity claim is made.
Full local App and full-suite validation were not rerun above the Windows
90-percent disk guard. New captures, builds and validation outputs stayed in
RAM under the user's explicit exception. Current-head external review and
fresh CI remain required before merge.
