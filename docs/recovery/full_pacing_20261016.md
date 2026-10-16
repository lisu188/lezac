# Full Pacing Fragment Recovery

## Scope

`FramePacingOperation` recovers original game `7903..79E8`, including the
30-frame counter gate, DOS GetTime, elapsed calculation, software Real48
display, feedback, sample carry and far CRT.Delay call. It composes the existing
instruction-level operations and preserves CPU, stack and shared BIOS/PSP state.
It stops before the following HUD refresh and keyboard handling. No production
App/rendering cadence integration or whole-function recovery is claimed.

The pinned DOSBox DIV leaves the preceding lazy arithmetic flags intact; logical
operations materialize AF as zero. Only this composed profile makes the latter
choice. The generic CRT operation's unspecified logical AF contract is unchanged.

## Controlled Original Execution

Unchanged original game/Real48/CRT instructions run under Unicorn 2.1.4. The
corpus includes all 65,536 counter inputs and 327,680 feedback inputs across five
delay/step profiles. Fifteen complete-fragment cases include counter wrap, zero
and nonzero delay, natural calibration 544, calibration-zero LOOP wrap, delay
underflow saturation, addition wrap, elapsed dead band, signed elapsed and the
Real48 division-error handoff. They provide 1,194 checkpoint comparisons across
ordinary and snapshot-restored C++ replay.

The controlled DOS provider supplies time 00:00:05.49 and control-stack/PSP ABI.
It does not execute the DOS kernel. The profile's additional 326 stub/kernel
dispatches are explicit, not counted as Unicorn-executed original instructions.
The separate natural replay below exercises actual DOSBox callback execution.

## Natural Original Capture

The silent unseeded level-one capture completed one full window with 60,408
states and an IRQ entry at state 42,291, inside the long CRT delay. The C++ replay
matches every observed state twice, for 120,816 comparisons, executing the timer
handler and its I/O rather than skipping it. It uses only initial memory and
declared ordered I/O/IRQ inputs; it does not inject later flags or memory.
Natural CPU comparisons cover the low-16 registers and observed control flags
under mask `0x700`; arithmetic flag fidelity is not claimed from this lazy-flags
observer. Controlled oracle endpoints separately compare complete flags.
The five raw RAM checkpoints independently match 43,552 relocated original code
bytes and their retained PNG hashes. Raw RAM and PNGs remain local, not fixtures.

The compressed trace SHA-256 is
`3cded9c4ec2938e954c23adb807a9c4da2ef77d65c9b34fdf7c96f29e1965934`.
CPU projection SHA-256 is
`870ab0d3f909508167730b0f03491c8ecab26a4e12e9a90ea3a29f52f74f8569`.
The frozen checker authenticates trace, recipe, producer, parser, projector,
patches, observation API and shared source identities before writing outputs.
It reports `raw_ram_files_verified=0`; historical raw verification is not
silently reclassified as verification from compact fixtures.

The immutable recipe retains an inaccurate legacy `trace_clock` string naming
atomic DOS callback boundaries. Those boundaries are disabled, as recorded by
`callback_boundary_probe=false` and the exact probe. This metadata limitation is
explicitly bound in the frozen manifest; the captured recipe was not rewritten.

## Interrupt And Acceptance Boundaries

Unit tests interrupt all 1,037 eligible boundaries in the zero-delay measurement
path, reject the single IF-masked INT21 boundary without state changes, and test
116 nonzero-delay boundaries. Snapshot restore preserves the delay operation
and SI, which is not part of the generic CRT register structure.

The natural IRQ boundary is an external observed input, not a prediction. The
long delay spans other host PIC callbacks whose queue/ticker effects have not
yet been recovered. Existing shorter coupled-clock tests remain strict and
unchanged in scope. This work does not establish IRQ eligibility prediction,
natural wall-clock fidelity, frame alignment, full App validation, visual parity
or whole-game completion. No percentage is inferred from these local checks.

Eight isolated fault injections were detected: counter period/exchange, both
feedback thresholds, delay saturation, sample carry, far return address and
delay IRQ context restore. This establishes sensitivity to those faults, not
coverage of every possible defect.

Final focused validation passed 26 CTests, the 19-case source guard self-test
with 119 mapped sources, and native MSVC replay compiled with `/W4 /WX`.
The four fixture test methods include seven frozen-file corruption controls,
44 changed/missing-source and output-preservation controls, and three terminal
or dispatch-continuity controls. The same fixture tests pass on Linux and Windows.

All validation outputs and capture runs remain RAM-only under the user's storage
exception. C: remains above the repository's 90% disk guard.
