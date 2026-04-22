# PROEFS.SON Field Diagnostics

Date: 2026-04-21

## Subagent A - Ghidra/Disassembly Mapper

- Reconfirmed `1000:0630..06aa` loads `PROEFS.SON` as a first-word count
  `0x0082` followed by `0x82 * 6` payload bytes.
- Reconfirmed `1000:0fbe..1088` reads each non-direct step as a six-byte entry:
  bytes `+0..+1` are the speaker period word, byte `+2` is copied to
  `DS:79a1`, byte `+3` is copied to `DS:79a2`, and bytes `+4..+5` are not
  referenced in the recovered tick window.

## Subagent B - Gameplay/Audio Fidelity

- Recommended keeping this slice parse/debug only, with no live audio routing,
  latch behavior, or synthesis changes.
- Identified `--debug-son-raw-roundtrip` as the lowest-risk existing parity
  check and a structured field diagnostic as the next useful visibility layer.

## Subagent C - Rendering/Audio/Assets

- Recommended leaving `tools/export_resources_to_json.py` and
  `src/PROEFS.SON.json` as byte-preserving compatibility containers.
- Recommended a C++ debug command rather than changing the JSON schema until
  bytes `+4..+5` are understood.

## Subagent D - Verification/Test Harness

- Recommended a deterministic CTest anchored on the raw file shape:
  raw size `782`, step count `130`, payload size `780`, and six JSON chunks.
- The integrated test adds a second gate on the structured field view, including
  stop cursor boundaries and the nonzero unknown-byte count.

## Subagent E - Integration/Docs

- Recommended branch `codex/proefs-son-field-diagnostics`.
- Risk boundary: diagnostics and docs only; do not reinterpret bytes `+4..+5`
  or change live playback behavior.

## Integrated Decision

The port now has `--debug-son-step-fields`, a field-only diagnostic over the raw
`PROEFS.SON` payload. It prints sampled steps with these evidence-backed names:

```text
step_index
period_word
gate_tick
period_ticks
unknown4
unknown5
```

The diagnostic confirms:

- 130 six-byte steps.
- 15 `0x7530` stop sentinels.
- first step cursor `0x0001`, `period_word=0x00f7`, `gate_tick=1`,
  `period_ticks=1`, `unknown4=0x01`, `unknown5=0x02`.
- first stop cursor `0x0005`.
- final stop cursor `0x0082`.
- 118 steps have a nonzero `unknown4`/`unknown5` pair.

`unknown4` and `unknown5` remain raw fields only. No live audio behavior changed.
