# 2026-04-22 Explosion Runtime Capture Attempt

## Goal

Capture original `LEZAC.EXE` runtime bytes for the unresolved
explosion/debris/collapse playback window around `1000:3a56..4d3b`, especially
the dispatcher/damage/collapse path reached by a level-1 player bomb at tile
`(24,22)`.

## Workstreams

- Subagent A mapped the debugger anchors and fixture requirements.
- Subagent B confirmed the shortest level-1 route: one-player game, move from
  start bomb tile `(13,22)` to `(24,22)`, press `N`, and wait for the default
  bomb fuse. This exercises the low-word collapse path, not the high-word level
  4 debris candidate.
- Subagent C confirmed that debugger memory/frame-table bytes are acceptable
  evidence only with `visual_claim=0`; screenshots are not required for this
  raw-byte fixture.
- Subagent D confirmed the strict
  `tests/fixtures/dosbox/explosion_playback_oracle_original.txt` shape expected
  by `--debug-explosion-playback-oracle`.
- Subagent E recommended documenting failed capture attempts without adding an
  original fixture.

## Temp Copy

The live attempts used a temporary run directory so original save/setup files in
the repository were not modified:

```sh
mkdir -p /tmp/lezac-dosbox-explosion-runtime
cp LEZAC.EXE BOMPAL.PAL CARO.CAR FONTS.SPR GRAN.MST LIVELS.SCH \
  PROEFS.SON PROVA.SPR RECS.DAT SFONLEF.ZBG BOMOMIMK.SPR \
  /tmp/lezac-dosbox-explosion-runtime/
```

`LEZAC.DOC` is not present in this checkout, so the explicit file list avoided
the `*.DOC` wildcard failure seen in one earlier setup attempt.

## Confirmed Runtime Entry

Launch command:

```sh
env TERM=xterm-256color xvfb-run -a dosbox-debug \
  -c "mount c /tmp/lezac-dosbox-explosion-runtime" \
  -c "c:" \
  -c "DEBUG LEZAC.EXE"
```

The debugger reached the program entry stop:

```text
CS=01ED
DS=01DD
IP=7783
01ED:7783  9A00000D0B  call 0B0D:0000
```

The xterm F5 sequence (`\x1b[15~`) continued execution from the debugger UI and
loaded the game assets, confirming the debugger was live.

## Breakpoint Plan

For this runtime segment, translate the Ghidra `1000:offset` anchors to
`01ED:offset`:

```text
BP 01ED:75F1  ; bomb_expire_dispatch_call
BP 01ED:414A  ; explosion_dispatcher
BP 01ED:370E  ; tile_damage_queue
BP 01ED:3A7E  ; damage_forward_lookup
BP 01ED:3B18  ; damage_reverse_lookup
BP 01ED:3BB2  ; collapse_forward_pass
BP 01ED:3D46  ; collapse_reverse_pass
BP 01ED:3FA6  ; extra playback-window anchor
BP 01ED:432A  ; extra playback-window anchor
```

At relevant stops, dump:

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

Minimum bytes required by the current oracle parser remain `DS:2093..209D`,
`DS:6611..661F`, `DS:C1E0`, and `DS:C21E..C225`.

## Input Attempts

Raw PTY attempt:

```sh
env TERM=xterm-256color xvfb-run -a dosbox-debug \
  -c "mount c /tmp/lezac-dosbox-explosion-runtime" \
  -c "c:" \
  -c "DEBUG LEZAC.EXE"
```

Typed `R\r`, LF, keypad Enter (`\x1bOM`), and CRLF. Printable `R` appeared at
the `->` prompt, but the command did not execute.

Piped stdin attempt:

```sh
printf 'R\r' | env TERM=xterm-256color xvfb-run -a dosbox-debug \
  -c "mount c /tmp/lezac-dosbox-explosion-runtime" \
  -c "c:" \
  -c "DEBUG LEZAC.EXE"
```

The debugger reached the same entry prompt and displayed `R`, but the command
did not execute before timeout.

Real X terminal attempt with terminal logging:

```sh
xvfb-run -a bash -lc '
rm -f /tmp/lezac-debug-zutty.log
zutty -title LEZACDBG -geometry 100x50 \
  -e script -q -f /tmp/lezac-debug-zutty.log \
  -c "env TERM=xterm-256color dosbox-debug -c \"mount c /tmp/lezac-dosbox-explosion-runtime\" -c \"c:\" -c \"DEBUG LEZAC.EXE\"" &
sleep 3
wid=$(xdotool search --name LEZACDBG | head -n 1)
xdotool windowfocus "$wid"
xdotool type --clearmodifiers R
xdotool key --clearmodifiers Return
xdotool key --clearmodifiers KP_Enter
xdotool key --clearmodifiers ctrl+j
xdotool key --clearmodifiers ctrl+m
'
```

The `script` log again showed the entry stop and `R` at the debugger prompt,
but none of the Enter variants executed the command. A control test using the
same `zutty`/`xdotool` setup with a shell `read` confirmed Return reached a
normal terminal program, so the failure is specific to this DOSBox debugger
input path.

## Result

No explosion breakpoint was reached and no original explosion/debris/collapse
runtime bytes were captured. The checked-in explosion playback oracle remains
synthetic parser coverage only, with `visual_claim=0`.

Next viable path is a manual or alternate debugger session where command Enter
works, then the level-1 `(24,22)` bomb route can be used to capture the low-word
collapse bytes. A later level-4 route is still needed for proven high-word
debris queue evidence.
