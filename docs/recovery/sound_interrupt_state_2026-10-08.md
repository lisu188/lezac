# Sound Interrupt State And Signed Priority

The signed sound-priority comparison is corrected in production. A per-IRQ
transition method is implemented and opcode-model tested. This recovery alone
did not replace the live one-shot pump. The subsequent
[clocked playback integration](clocked_sound_2026-10-08.md) does so; original
IRQ timing and natural audio parity remain unverified.

## Original Instructions

Pinned executable SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Pinned `PROEFS.SON` SHA-256:
`b5bc702a27ac85554cc76a62fced07567921b07d5c16f2027a62fbc956df701d`.

The complete 211-byte interrupt routine, including its saved-register epilogue
and `IRET`, is at `1000:0fbe..1090`, file `0x172e..0x1800`. Its SHA-256 is
`8505700f9f878bc49cb2ae0a62d2bd2c5ae9ca2849b8581bcc7cf95f6e06aecc`.
Earlier notes used `..1088` for the checked body, not the complete epilogue.
The checker also pins the 36-byte priority latch, 27-byte INT 1Ch installation
window, and ten-byte accumulator/period initialization window.

### Signed Priority

The latch executes `DEC AL`, `CMP AL,[799f]`, then **`7d 11`, signed JGE**.
The prior C++ unsigned comparison was wrong on 32,768 of 65,536 active
current/pending byte pairs. Compiled reproductions show:

| Current | Pending | Old Accepts | Original CMP/JGE Model Accepts |
| ---: | ---: | ---: | ---: |
| 0 | 1 | no | yes |
| 128 | 255 | yes | no |
| 255 | 1 | no | yes |

Priority zero is used by the original records-table sound callsite, so this is
not exclusively an artificial high-byte issue. Positive priorities 1..127
retain their ordinary ordering, but byte DEC and signed comparison govern the
boundaries. The production comparator now biases both bytes by `0x80` before
unsigned comparison, preserving that ordering without implementation-defined
signed narrowing.

The diagnostic rejection seed changes from `0xff` to `0x80`. The former becomes
signed -2 after DEC and cannot reject ordinary positive priorities. The latter
becomes signed 127 and rejects every pending byte. Accepted requests preserve
the interrupt accumulator, gate and period bytes.

### Per-Interrupt Transition

`SoundEngine::advanceSoundInterrupt()` operates on the existing sound latch
and the original's three byte counters:

- Inactive interrupts do nothing.
- Direct cursors above `0xea60` issue `Sound(cursor - 0xea42)`, subtract four,
  and, if the result is at most `0xea60`, issue NoSound and clear active in the
  same interrupt. The counters, priority and resulting cursor are retained.
- Bank playback increments the accumulator as a byte. Equality with the
  period advances the cursor before reading the corresponding six-byte entry.
  This branch takes precedence over gate equality.
- A tone entry replaces gate and period and clears the accumulator.
- A `0x7530` sentinel silences the speaker, clears active and accumulator,
  and restores period one. Gate, priority and the incremented cursor survive.
- Otherwise accumulator/gate equality issues NoSound without ending playback.
- Period zero therefore advances after a 256-interrupt byte wrap, not never.

The returned action distinguishes a tone command followed by silence within
one interrupt. It does not collapse that sequence to a tone-only or stop-only
event. Reads beyond the recovered 130-entry bank extent are explicitly rejected
instead of silently claiming the original's allocator-memory reads are known.

## Verification

The actual compiled engine passes:

- 16,777,216 accumulator/gate/period combinations at the first shipped entry.
- 8,320 boundary transitions across all 130 shipped entries.
- 149,445 transitions covering every direct cursor and 27 counter boundaries.
- 65,536 inactive cursor cases and all 65,536 active priority pairs.
- 256 inactive priority requests, all accepted without resetting IRQ state.
- Fourteen shipped-cursor trajectories through their stop sentinels.
- An eight-step sweep computed from retained native Level 4 state at tick
  9612: cursor `0xea7e`, priority 5, accumulator 0, gate 2, period 1. Lower
  priority stays rejected until completion. The seed is observed; the eight
  IRQ transitions are modeled, not an observed native interrupt count.

Independent Python models pin the original windows and verify compiled
fingerprints. The priority reference derives JGE from subtraction SF/OF flags:

| Projection | FNV-1a 64 |
| --- | --- |
| Bank transitions | `61a9aacc9ebe6019` |
| Direct transitions | `d6c18b36a3074a36` |
| Priority acceptance/writeback | `1eec5d8cb7bcd625` |

Seven separately compiled regressions are rejected: unsigned priority,
period-zero suppression, gate-before-step ordering, direct accumulator reset,
omitted final direct tone, sentinel clearing of cursor/priority, and request
resetting IRQ state. All agent runs are silent.

## Clocked Integration Follow-Up

The [follow-up integration](clocked_sound_2026-10-08.md) calls
`advanceSoundInterrupt()` from persistent clocked playback in the live and
ordinary replay paths. The old `pumpSoundLatch()` remains a bounded diagnostic
API, not a production lifetime mechanism.

Native IRQ count/phase, host cadence, waveform and device latency need separate
verification. No natural sound-timing or preemption parity is claimed.
`sound_runtime_parity_claim=false`, `original_fidelity_claim=false`,
`port_functionally_complete=false`, and `whole_game_complete=false` remain.
