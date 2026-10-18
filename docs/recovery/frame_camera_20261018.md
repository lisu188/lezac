# Resumable Original Camera

`FrameCameraOperation` recovers the original near Pascal routine
`1000:3587..370E` (exclusive end), its CRT stack check at `0920:04DF..04F7`,
and its 32-bit multiply at `0920:092A..0945`. All 195 instruction addresses
are exercised by the frozen controlled corpus. This is the camera called
before each active player's world rasterization and final VGA copy.

The operation retains original 16-bit wrapping, signed `IDIV` quotient and
remainder, coarse rounding, map-index multiplication, signed edge comparisons,
fine offsets and shake addition. It runs the actual stack-check instructions
and exposes the original runtime-error handoff rather than silently accepting
an invalid stack. Near `RET 4`, far returns and intermediate stack writes are
part of the model. Snapshots resume between individual instructions.

## Independent Original Execution

`tools/frame_camera_oracle.py` runs unchanged shipped instructions in Unicorn
2.1.4. MZ relocation records are applied exactly as loader relocation, not as
instruction substitution. No callee is stubbed; no interrupts, port responses
or gameplay observations are fed back into the execution.

All inputs are controlled, not a natural capture. Four full/split/tall/narrowed
geometries cross signed-coordinate extremes, tile and map-edge boundaries,
three shake values and both DF states. Four explicit stack profiles include
three errors and the exact successful stack-limit boundary. Both view callers'
return addresses are covered.

Observed and unobserved runs agree on all endpoint registers/flags and complete
1 MiB memory. The producer verifies unchanged loaded code. Only register traces,
declared context words, 72 stack bytes per case and original word-write sequences
are retained in the public projection; there are no full RAM images or PNGs.

- Original EXE SHA256: `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
- Actual mapped Unicorn library SHA256: `ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c`.
- Cases: 1,876; original register states: 276,203; instruction addresses: 195.
- Projection: 8,918,494 bytes; compressed: 620,394 bytes.
- Projection SHA256: `e00ccd69321a30e94157e6dc8a80746245308d9d3b442007eb6c9631c6d2b777`.
- Manifest SHA256: `24271bd77c822a8615699b7e5c6179a78c80349b4a4fbf1ec619b9e72e755688`.

The checker authenticates the complete manifest, producer, EXE and compressed/
decoded data before export. It requires no Unicorn or raw RAM in CI. Matching
outputs are reused without rewriting; conflicting outputs are preserved. The
fixture test makes 26 rejection calls, retaining failed reports where a separate
writable report is supplied, and rejects overlapping report/export paths.

## Validation

Instruction budgets 1, 2, 17 and 4,096 produce 7,504 replays and 438,001
register-state comparisons. Each advance is followed by snapshot reconstruction.
Original word writes must match in address, value and order. Every final context,
stack, outcome, register and complete flags value is compared. Zero-budget and
finished calls are nonmutating.

Intermediate trace comparisons exclude arithmetic EFLAGS bits: `MUL` and
`IDIV` leave some undefined, and pinned DOSBox normal-core materialization is
not the same claim as Unicorn's. Other flag bits and every register/PC are
compared at checked boundaries; complete endpoint flags are compared without
that exclusion. No general claim about intermediate undefined flags is made.

Strict GCC C++23 and native MSVC C++latest `/W4 /WX` builds pass the unit and
all original-backed replays. The fixture rejection test passes on Linux and
native Windows. AddressSanitizer and UndefinedBehaviorSanitizer pass. Five new
CTests and 19 existing source-guardrail controls pass. Four isolated faults are
detected: unsigned negative remainder, zero right-edge fine offset, omitted
shake and skipped stack-limit failure. Their diagnostics are retained; the
actual source stays unchanged. A full Linux App build also succeeds, with the
existing unrelated diagnostic `snprintf` warning unchanged.

## Remaining Integration

The actual renderer still uses its existing geometric camera calculation.
This operation is not yet connected to it or to the work-clock scheduler.
`FrameForegroundOperation` still ends at `7A13`; world-raster instruction
recovery, live owner-bus wiring, natural IRQ delivery during rendering and
narrowed-viewport/full-frame equivalence remain open. Controlled camera traces
are not natural gameplay, verified wall-clock cadence or whole-game fidelity.

All local builds, fixtures, diagnostics and silent App captures are RAM-only
while C: remains above the repository's disk guard.
