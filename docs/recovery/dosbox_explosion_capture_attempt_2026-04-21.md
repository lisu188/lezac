# DOSBox Explosion Capture Attempt - 2026-04-21

## Goal

Capture real `dosbox-debug` evidence for a bomb-object explosion that reaches
`1000:414a`, `1000:370e`, and the unresolved playback window
`1000:3a56..4d3b`.

## Temp Copy

The original files were copied to `/tmp/lezac-dosbox-explosion` before running
DOSBox, so repository assets and `RECS.DAT` were not modified in place.

## Commands Tried

```text
dosbox-debug -version
timeout 5s xvfb-run -a dosbox-debug -c "exit"
xvfb-run -a dosbox-debug -c "mount c /tmp/lezac-dosbox-explosion" -c "c:" -c "LEZAC.EXE"
tmux -S /tmp/lezac-dosbox-explosion/tmux.sock new-session -d -s lezacdbg -c /tmp/lezac-dosbox-explosion 'DISPLAY=:99 dosbox-debug -c "mount c /tmp/lezac-dosbox-explosion" -c "c:" -c "DEBUG LEZAC.EXE"'
```

`dosbox-debug --help` and `dosbox-debug -h` are not help modes in this build;
they open the debugger UI.

## Captured Runtime Entry State

Launching through `DEBUG LEZAC.EXE` stopped at the original entry point:

```text
runtime_cs=01ED
runtime_ds=01DD
runtime_ip=7783
temp_copy=1
command=dosbox-debug -c "mount c /tmp/lezac-dosbox-explosion" -c "c:" -c "DEBUG LEZAC.EXE"
```

The visible entry instruction matched the documented Ghidra entry offset:

```text
01ED:7783  9A00000D0B          call 0B0D:0000
```

## Automation Failure

The debugger curses UI accepted printable characters through raw PTY and tmux,
but Enter and Backspace were not delivered as command keys. As a result,
commands such as `HELP`, `R`, `BP 01ED:414A`, or `C` could be typed into the
input line but not executed. No explosion breakpoint was reached, and no
original explosion playback bytes were captured.

This is an environment/control limitation only. It is not evidence about
original explosion behavior.

## Next Manual Capture Target

Use a terminal where the debugger accepts Enter, then:

```text
BP 01ED:75F1
BP 01ED:414A
BP 01ED:370E
BP 01ED:3A7E
BP 01ED:3B18
BP 01ED:3BB2
BP 01ED:3D46
C
```

For an immediate level-1 collapse route, start a one-player game, move to bomb
tile `(24,22)`, and place a player-1 bomb with `N`. The target above the object
is `(24,21)` with word `0x0009`; expected runtime evidence should show it
flagged as `0x8009` and queued as a two-cell collapse group.

At relevant stops, record:

```text
R
U CS:IP
D SS:SP
D DS:2070
D DS:7990
D DS:2090
D DS:6610
D DS:C1E0
D DS:C21E
D DS:C320
```

Normalize only real captured bytes into
`tests/fixtures/dosbox/explosion_playback_oracle_original.txt`.
