# State-2 Original Runtime Fixture

Date: 2026-04-21

## Subagent A - Ghidra/Disassembly Mapper

- Recommended prioritizing original runtime bytes for the state-2 frame table
  over further static guesses in the `1000:6053` consumer.
- Reconfirmed the relevant anchors: `1000:3108`, `1000:6053`, `1000:6148`,
  `1000:7c89`, and `1000:7ddf`.

## Subagent B - Gameplay Fidelity

- Recommended keeping this PR evidence-only and avoiding live death/reentry
  rendering or accounting changes until original bytes are checked in.
- Noted that bombs/passable objects have isolated tests, but they are lower
  value than the missing state-2 runtime fixture for this loop.

## Subagent C - Rendering/Audio/Assets

- Recommended preserving `visual_claim=0` and treating captured frame-table
  bytes as raw evidence until the field layout is proven.
- Also identified future audio/export work for field-aware `PROEFS.SON` steps,
  but that was left for a separate PR.

## Subagent D - Verification/Test Harness

- Recommended adding `state2_runtime_frame_oracle_original` once real
  `dosbox-debug` bytes were available.
- The fixture should validate runtime `CS`/`DS`, translated breakpoints,
  `DS:006a`, `DS:006c`, `DS:006d`, `DS:c322 + 4 * frame`, `DS:c21e`, and
  `visual_claim=0`.

## Subagent E - Integration/Docs

- Recommended a narrow branch and PR for the original fixture:
  `codex/state2-runtime-frame-oracle-original-fixture`.
- Recommended documenting the exact command, temp-copy path, runtime registers,
  and risk boundary.

## Capture Procedure

Temporary DOSBox run directory:

```sh
/tmp/lezac-dosbox-original-fixture-2
```

Launch command:

```sh
env TERM=xterm-256color xvfb-run -a dosbox-debug \
  -c "mount c /tmp/lezac-dosbox-original-fixture-2" \
  -c "c:" \
  -c "DEBUG LEZAC.EXE"
```

Initial debugger stop:

```text
CS=01ED
DS=01DD
EIP=7783
```

Breakpoints set:

```text
BP CS:3108
BP CS:6053
BP CS:6148
BP CS:7C89
BP CS:7DDF
```

The game was continued with the xterm F5 sequence. xdotool input against the
Xvfb DOSBox window started a one-player game and pressed `N` to place a bomb.
The original stopped at runtime `01ED:7C89`.

Stop-state registers observed from the debugger UI:

```text
CS=01ED
DS=0C8F
EIP=7C89
```

Memory dumps captured with `MEMDUMP`:

```text
MEMDUMP DS:0060 80
MEMDUMP DS:C21E 80
MEMDUMP DS:C440 80
```

`MEMDUMP` wrote `MEMDUMP.TXT` in the repository working directory, so each dump
was copied to `/tmp/lezac-dosbox-original-fixture-2/` immediately and the
working-tree copy was removed.

## Integrated Evidence

- `DS:006a = 0x45`
- `DS:006c = 0x4a`
- `DS:006d = 0x4f`
- `DS:c21e` effect entry 0 words: `x = 0x0068`, `y = 0x00a8`
- Current oracle row formula: `DS:c322 + 4 * frame`
- Captured first entry address for frame `0x4a`: `0xc44a`
- First parsed row: `10,10,7d,43`
- Last parsed row for frame `0x4f`: `10,10,7d,48`

## Risk Boundary

This fixture proves one original state-2 countdown memory sample. It does not
yet prove the visual field layout or that the live renderer should draw
dead-player art from these rows. Keep `visual_claim=0` until the
`1000:6053..6156` consumer is mapped tightly enough to name the row fields.
