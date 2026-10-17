# Pacing Device Clock Observation

This observer extends the retained full-pacing observer in a separate namespace;
the earlier observer, captures and fixtures are unchanged. It observes the
original `game:7903..79E8` fragment and records timing-relevant device inputs.

Queue kind IDs come from direct equality with the original callback function
pointers, not from event values or timing guesses: 1 PIT0, 2 unknown, 3 VGA draw
part, 4 VGA vertical timer, 5 display-start latch, 6 panning latch, 7 VGA vertical
interrupt. Ticker IDs likewise identify 10 keyboard, 11 silent mixer, 12 mixer;
unknown callbacks remain explicit and the recovered profile rejects them.

`build.py` pins the configured DOSBox source, copies the existing build products,
and adds read-only getters through a generated patch. It records fragment,
source, patch and host hashes. The original callback bodies and CPU core source
remain unchanged. Reused build products are not a clean-build reproducibility
claim. `capture.py` checks getter identities before launching silent, unseeded
gameplay under the fixed-6000 normal core.

The `devices` field contains 25 unsigned values followed by six IEEE-754 double
bit patterns. The getter fragments define each slot explicitly: VGA machine,
mode, PART counters, retrace controls, renderer state, keyboard repeat/buffer
state, silent mixer/channel state, capture state and channel count; then PART,
vertical-total, retrace-start, retrace-end, display-end and horizontal-total
delays. Tickers are recorded in actual list order. The capture preserves both
compressed and expanded trace identities with strict terminal validation.

Run the projector as a module from `tools/`:

```sh
python3 -B -m pacing_clock_probe.project --capture /dev/shm/capture \
  --out /dev/shm/projection --exe /path/to/LEZAC.EXE
```

It verifies local raw RAM/PNG identities and relocated original code, then emits
CPU and device-clock projections. Projection is not execution proof. The C++
`--device-clock-projection` mode constructs its clock from the first state only;
later observations are comparison targets. IRQ positions in the CPU projection
are not used to drive coupled replay. The separate observed-IRQ mode remains
explicit and does not acquire an eligibility claim.

The current C++ device-clock profile is VGA mode 13h, PART drawing, zero frame
skip, idle keyboard, no mixer channels and no host capture. Its callback model
covers scheduling effects, not rendered pixels. Active input, other IRQs,
enabled audio channels, other graphics modes and actual App integration remain
outside this proved profile and are not silently approximated.
