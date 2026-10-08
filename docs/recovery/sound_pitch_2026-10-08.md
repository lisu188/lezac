# PC Speaker Frequency Conversion

The original-backed pitch conversion is recovered. Sound playback timing and
whole-game audio fidelity remain unverified.

## Original Evidence

`LEZAC.EXE` SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

The sound IRQ passes a bank entry's first word, or the direct-sweep cursor minus
`0xea42`, to the far Sound helper at `084a:02c9`. Its complete 45-byte body is
at executable file offsets `0x8ed9..0x8f05`. It reads the argument into BX,
loads `DX:AX = 0x0012:34dd`, compares DX with BX, and returns without speaker
I/O when BX is at most 18. Otherwise unsigned `DIV BX` computes the PIT reload
as `floor(1193181 / frequency)`. It enables port `0x61` when needed and sends
the reload's low and high bytes to PIT channel 2 at port `0x42`.

These are frequency commands, not PIT reloads. The shipped bank has 115
non-stop entries, all above the ignored-command threshold. The legacy
`soundStepPeriodWord` API name is retained to avoid unrelated caller churn.

## Production Correction

Previously, synthesis interpreted each frequency as a reload, computed
`1193182 / argument`, and clamped the result to 80..4200 Hz. It also silenced
arguments below 32. A compiled reproduction against the unchanged pre-fix
sound engine produced the following for 22,036 samples per requested tone:

| Frequency Command | Old Nonzero Samples | Old Sign Changes | Fixed Nonzero Samples | Fixed Sign Changes |
| --- | ---: | ---: | ---: | ---: |
| 20 | 0 | 0 | 22036 | 39 |
| 40 | 22036 | 8394 | 22036 | 79 |
| 247 | 22036 | 8394 | 22036 | 493 |
| 311 | 22036 | 7668 | 22036 | 621 |

Both bank and direct-sweep synthesis now use the original integer reload
conversion, then the existing 1,193,182 Hz PIT clock model to generate PCM.
The pitch clamp is removed. An ignored command preserves the previous reload
and enabled state; it neither starts an idle speaker nor restarts a gated one.

## Validation

- `sound_pitch`: actual production sound-engine tests, including all 65,536
  frequency words; 128,000 PCM samples checked against integer phase positions
  for ten frequencies; three ignored-command states; bank and direct-sweep
  callers; and gate-off followed by an ignored command.
- `sound_pitch_original`: pins the whole original executable and complete
  Sound helper, derives the numerator and threshold from its immediate words,
  and compares all 65,536 compiled conversion results. Packed little-endian
  reload SHA-256:
  `0222adf3d177b4cdc022d6188e0b3d89a91c35c845faea0c652c6d5c58d09854`.
- The opcode-model comparison is not native execution of the original helper.
  All agent-launched checks use dummy audio and do not play through speakers.

## Still Open

The one-shot pump still clears the active sound latch after queuing a complete
effect. The original clears it only when the IRQ reaches the end of playback;
accepted replacements also preserve the interrupt accumulator, gate and period
bytes. Recovering that lifetime, interrupt cadence and phase, preemption,
speaker waveform/gating, device latency and natural end-to-end audio comparison
remains necessary. This pitch correction does not establish those properties.

The legacy 28-tick PCM segment lengths and half-length direct-sweep segments
are unchanged; their passing tests are compatibility checks, not original
interrupt-timing evidence. `sound_runtime_parity_claim=false`,
`original_fidelity_claim=false`, `port_functionally_complete=false`, and
`whole_game_complete=false` remain unchanged.
