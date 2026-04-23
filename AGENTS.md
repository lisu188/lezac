# Repository Agent Instructions

## Git workflow

- Never work directly on `main` or `master`.
- Before making code changes, create a new branch from the current default
  branch.
- Use a clear branch name that reflects the task.
- Keep all work isolated to that branch.
- Always rebase your branch onto the latest `main` before pushing or opening a
  pull request.

## Required delivery flow

- After finishing the task, review the diff.
- Run relevant tests, checks, or validation steps when available.
- Commit the changes with a clear, descriptive commit message.
- Push the branch to the remote.
- Create a pull request.

## Pull request expectations

- The pull request title should clearly describe the change.
- The pull request body should include:
  - what was changed
  - why it was changed
  - validation performed
  - any known limitations or follow-up work

## Safety rules

- Do not merge the pull request.
- Do not delete branches unless explicitly asked.
- Do not bypass failing checks unless explicitly asked.
- Do not make unrelated cleanup changes outside the task scope.

## Working style

- Prefer minimal, targeted changes over broad rewrites.
- Follow existing project patterns and conventions.
- Avoid introducing new dependencies unless necessary.
- Call out uncertainty instead of guessing.
- If the repository is missing a remote or PR creation is not possible, state
  that explicitly.
- When testing UI, rendering, DOSBox, or live gameplay behavior, use frame
  inspection whenever possible. Capture screenshots, SDL frame dumps, debugger
  memory/frame-table bytes, or other visual-frame evidence and record what was
  inspected; do not rely only on process exit status for visual behavior.

## Autoplayer and frame-harness testing

Use the deterministic C++ autoplayer before relying on ad hoc xdotool input for
the recovered port. The autoplayer drives game update helpers directly, so it is
stable under dummy SDL and suitable for CTest/headless regression work.

Run the level-1 bomb route autoplayer with frame inspection:

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer level1_bomb_route
```

Use the frame harness when a visual checkpoint or comparison artifact is needed:

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --capture-frame-sequence level1_bomb_route /tmp/lezac-cpp-frames
```

For route/gameplay regressions, prefer adding a deterministic autoplayer
scenario or extending an existing one. The harness should inspect rendered
frames and record route metadata such as player coordinates, bomb tile,
explosion/effect counts, and manifest hashes. Avoid replacing autoplayer
coverage with direct player teleports unless the test is explicitly about
rendering a state that cannot yet be reached through implemented gameplay.

## DOSBox original-game observation

Use DOSBox as an oracle for original `LEZAC.EXE` behavior when disassembly is
unclear or runtime presentation matters. Prefer observing the original in a
temporary copy so `RECS.DAT`, setup files, or other shipped assets are not
modified in-place.

Create a temporary DOSBox run directory:

```sh
mkdir -p /tmp/lezac-dosbox
cp LEZAC.EXE *.DAT *.SPR *.PAL *.SCH *.SON *.MST *.CAR *.ZBG *.DOC /tmp/lezac-dosbox/
dosbox -c "mount c /tmp/lezac-dosbox" -c "c:" -c "LEZAC.EXE"
```

Run directly from the repository only when intentional file writes are
acceptable:

```sh
dosbox -c "mount c ." -c "c:" -c "LEZAC.EXE"
```

Use DOSBox to verify focused behavior questions, then encode the recovered rule
in deterministic C++ debug commands or tests. Useful observation targets
include:

- menu, help, records, setup, pause, quit, and level-transition flows
- player death, state-2 countdown, reentry, player-out, and game-over behavior
- two-player controls and shared-objective semantics
- bomb explosions, passable objects, debris/collapse playback, and damage
  timing
- monster movement, collision, rewards, and spawner lifecycle
- record-entry cursor behavior, accepted characters, typematic repeat, and save
  behavior

If automating DOSBox, keep it best-effort and document the exact command,
environment, input sequence, and any failure reason. SDL/Xvfb/xdotool tests for
the C++ port are generally more reliable for regression coverage than DOSBox
key injection.

## DOSBox debugger workflow

Use `dosbox-debug` when runtime state is needed, such as confirming register
values, memory bytes, control flow, or whether a routine is reached during
actual `LEZAC.EXE` play. Prefer the same temporary copy workflow used for normal
DOSBox runs.

Check availability first:

```sh
command -v dosbox-debug
```

Launch the original game under the debugger. In this environment the reliable
shape is to set a real terminal type, run under Xvfb, and start the DOS `DEBUG`
loader inside DOSBox:

```sh
mkdir -p /tmp/lezac-dosbox
cp LEZAC.EXE *.DAT *.SPR *.PAL *.SCH *.SON *.MST *.CAR *.ZBG *.DOC /tmp/lezac-dosbox/
env TERM=xterm-256color xvfb-run -a dosbox-debug \
  -c "mount c /tmp/lezac-dosbox" \
  -c "c:" \
  -c "DEBUG LEZAC.EXE"
```

Inside the debugger, use `HELP` to confirm the exact commands supported by the
installed build. Common useful commands are:

- `C` to continue execution.
- `BP segment:offset` to set a code breakpoint.
- `BPLIST` to list breakpoints.
- `BPD` or the debugger's listed delete command to remove breakpoints.
- `R` to inspect registers.
- `D segment:offset` to dump memory.
- `MEMDUMP segment:offset length` to write `MEMDUMP.TXT` in the mounted DOS
  directory when the installed debugger supports it.
- `U segment:offset` to disassemble memory.
- `S` or `T` to single-step, depending on the debugger build.

The debugger prompt is `->` in current local runs. Commands sent through a PTY
may need carriage returns (`\r`), but this local DOSBox debugger build has also
shown an input-path failure where printable command characters reach `->` while
Return, keypad Enter, CR, LF, Ctrl-J, and Ctrl-M do not submit the command. The
xterm F5 key sequence (`\x1b[15~`) continues execution from the debugger UI in
current local runs. If command submission fails, document the exact terminal,
input sequence, and failure reason instead of treating it as game behavior.

For terminal-log evidence, a real X terminal can be run under Xvfb and captured
with `script`:

```sh
xvfb-run -a bash -lc '
zutty -title LEZACDBG -geometry 100x50 \
  -e script -q -f /tmp/lezac-debug-zutty.log \
  -c "env TERM=xterm-256color dosbox-debug -c \"mount c /tmp/lezac-dosbox\" -c \"c:\" -c \"DEBUG LEZAC.EXE\""
'
```

Do not assume Ghidra's `1000:offset` segment is the exact runtime segment in
DOSBox. First stop in the program, inspect `CS`/`DS`, and translate Ghidra
anchors by keeping the offset and using the runtime segment shown by the
debugger. For example, if the debugger shows the game code running with
`CS=1234`, investigate Ghidra routine `1000:30a3` as `1234:30a3`.

Useful runtime breakpoints for current recovery work include:

```text
BP <runtime-cs>:165A  ; sound priority latch
BP <runtime-cs>:30A3  ; player death/life-loss helper
BP <runtime-cs>:6053  ; actor update candidate
BP <runtime-cs>:7C89  ; state-2 countdown/life drain path
BP <runtime-cs>:7DDF  ; state-2 return-to-active path
```

When stopped inside the game, use the current `DS` register to inspect mapped
state bytes from the Ghidra notes:

```text
D DS:2070  ; nearby sound request globals, including DS:2074
D DS:7990  ; sound latch/request state around DS:799e/DS:799f
D DS:79E0  ; player state/life bytes around DS:79e5..79eb
D DS:C21E  ; visual/effect entries used by state-2 return
```

For each DOSBox debugger observation, record:

- exact DOSBox command and whether a temp copy was used
- breakpoint addresses using both Ghidra anchor and runtime segment
- relevant register values, especially `CS`, `DS`, `ES`, `SS`, and `IP`
- memory bytes or disassembly that support the conclusion
- resulting C++ mapping, debug command, or test to add

Keep debugger-derived claims narrow. If a breakpoint confirms that a routine is
reached or a byte changes, document that fact separately from any hypothesis
about sprite choice, timing, or gameplay meaning.
