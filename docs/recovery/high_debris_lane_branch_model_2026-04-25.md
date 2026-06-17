# High-Debris Lane Branch Model, 2026-04-25

This note records the static branch model for the high-debris lane calls in
`LEZAC.EXE`. It complements the original-runtime fixtures for `1000:4C75`,
`1000:4C96`, and `1000:4CA9`; it does not promote any new visual claim or live
C++ behavior.

Current local validation constraints:

- WSL/DOSBox process-memory access was available for the 2026-04-28
  continuation.
- `explosion_playback_oracle_original_3cd4_lane_div_scratch_runtime.txt`
  promotes one original runtime-child-memory mid-helper capture.
- `explosion_playback_oracle_original_3ce3_lane_div_scratch_runtime.txt`
  promotes one original runtime-child-memory divide call-site capture.
- `explosion_playback_oracle_original_3d1b_lane_write_scratch_runtime.txt`
  promotes one original runtime-child-memory forward collapse writeback capture.
- `explosion_playback_oracle_original_3d1b_lane_write_trampoline_runtime.txt`
  promotes the same forward collapse writeback with a safe trampoline patch.
- `explosion_playback_oracle_original_3eaf_lane_write_trampoline_runtime.txt`
  promotes the reverse collapse writeback with the same safe trampoline patch.
- `explosion_playback_oracle_original_3d2d_lane_write_trampoline_no_freeze.txt`
  and `explosion_playback_oracle_original_3ec1_lane_write_trampoline_no_freeze.txt`
  record that this route did not reach the debris-side writebacks.
- `explosion_playback_oracle_original_3d2d_lane_write_runtime_seeded.txt`
  and `explosion_playback_oracle_original_3ec1_lane_write_runtime_seeded.txt`
  prove the debris writeback arithmetic under labeled runtime seeding.
- `explosion_playback_oracle_lane_result_scratch_synthetic.txt` and
  `explosion_playback_oracle_lane_result_reverse_scratch_synthetic.txt` cover
  the final helper far-pointer result-write parser paths for `1000:3D3F` and
  `1000:3ED3`; the paired malformed fixtures reject incomplete, missing byte
  signature, mismatched kind, mismatched scratch offset, mismatched far-pointer,
  mismatched output/local, byte-width, loop-bound, and missing-present-flag
  scratch records.
- `explosion_playback_oracle_original_3ed3_lane_result_runtime.txt` promotes
  one original runtime-child-memory reverse result-write capture. It freezes
  `1000:3ED3` at runtime `01ED:3ED3`, keeps the byte guard `268805`, and
  records result byte `0x00ef`, `ES:DI=18B3:3FE6`, caller far pointer
  `18B3:3FE6`, result local `0x00ef`, active count/index `1/1`, and
  target-before byte `0xde`.
- `explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded.txt`
  promotes one labeled runtime-seeded forward result-write capture. The seed
  patch at runtime `01ED:4C96` writes `DS:655E=0xC004`, calls the original
  forward helper at `01ED:3BB2`, and freezes `1000:3D3F` at runtime
  `01ED:3D3F`. It keeps byte guard `268805` and records result byte `0x00fa`,
  `ES:DI=0C44:78D2`, caller far pointer `0C44:78D2`, result local `0x00fa`,
  active count/index `1/1`, and target-before byte `0xf3`.
- Natural-route `1000:3D3F` evidence is still pending. The 2026-05-06 default,
  timing-variant, and before-bomb attempts loaded the forward patch but did not
  hit the freeze.
- `explosion_playback_oracle_original_3d3f_lane_result_route_step_no_freeze.txt`
  promotes one natural route-step no-freeze run (`x:2.00,c:0.50`). It loaded
  the guarded `1000:3D3F` patch (`268805`) without lane-result scratch, while
  the chosen sample recorded `lane_update_flag=0x05`, `lane_word=0x0004`,
  `lane_target_offset=0x072c`, and reverse input `0xfb`.
- The evidence remains instrumentation-only (`visual_claim=0`); no live C++
  playback behavior is changed by this note alone.

## Byte Window

The local read-only PowerShell dump used file offset `0x53D4`, matching Ghidra
offset `1000:4C64` under the existing file-to-Ghidra delta of `+0x770`:

```text
0053d4: 8b 46 f6 d1 e0 c4 3e 12 66 03 f8 26 8b 05 89 46
0053e4: fc 83 7e fc 00 76 33 c7 06 78 20 01 00 8b 46 f6
0053f4: d1 e0 a3 9a 65 8b 46 fc a3 5e 65 6a 01 bf d2 78
005404: 1e 57 e8 19 ef 8b 46 fc 0d 00 80 a3 5e 65 6a 01
005414: bf d4 78 1e 57 e8 9a f0 eb 05 c6 06 d2 78 00 eb
005424: 04 c6 46 eb 01 6b 7e fe 0b 81 c7 93 20 89 7e e6
```

## Static Interpretation

The `1000:4C64..4C72` sequence doubles the target offset local, loads the far
word-layer pointer from `DS:6612`, adds the doubled target offset, reads the
target word through `ES:DI`, and stores that word in `[BP-4]`.

The next branch is the key gate:

```text
1000:4C75  cmp word ptr [BP-4],0
1000:4C79  jbe 1000:4CAE
```

So the lane calls execute only on the positive-word side. On that side the code:

- writes `1` to `DS:2078`;
- stores the doubled target offset in `DS:659A`;
- stores the live word in `DS:655E`;
- calls the forward lane helper from `1000:4C96` with `DS:78D2`;
- ORs the live word with `0x8000` and stores it again in `DS:655E`;
- calls the reverse lane helper from `1000:4CA9` with `DS:78D4`.

The two helper call operands in the byte dump are:

```text
1000:4C96  e8 19 ef  ; near call target = 4C99 + signed 0xEF19 = 1000:3BB2
1000:4CA9  e8 9a f0  ; near call target = 4CAC + signed 0xF09A = 1000:3D46
```

That matches the existing helper mapping: `1000:3BB2` is the forward lane
blender and `1000:3D46` is the reverse lane blender.

If the gate skips to `1000:4CAE`, the code does not call the lane helpers and
instead clears `DS:78D2` in the nearby else path visible after the `4CA9` call.

## Runtime Evidence Boundaries

The promoted fixtures show that the captured original route can freeze:

- `1000:4C75` at `01ED:4C75`, proving the gate instruction is reached.
- `1000:4C96` at `01ED:4C96`, proving the forward lane-call site is reached.
- `1000:4CA9` at `01ED:4CA9`, proving the reverse lane-call site is reached.

Those fixtures also record sampled queue summaries, selected debris/collapse
bases, high-debris target bytes, and frozen frame hashes. The initial `4C75`
fixture stopped at the gate but did not capture the live `[BP-4]` local, and
the `4C96`/`4CA9` freezes patch the call instruction itself. The positive-word
claim for `4C96` and `4CA9` is therefore a static-control-flow inference from
the branch shape above, not a helper-output byte dump.

A follow-up runtime-child instrumentation mode now patches `1000:4C75` with:

```text
8B 46 FC        mov ax,[bp-4]
2E A3 7E 4C     mov cs:[4c7e],ax
EB FE           jmp $
```

The promoted `explosion_playback_oracle_original_4c75_bp4_scratch_runtime.txt`
fixture froze `01ED:4C75`, matched the final tail screenshots, and records
`instrumented_bp4_local_cs_offset=0x4c7e` plus
`instrumented_bp4_local_value=0x0003`. That directly proves one positive
word-gate local at the freeze. The same fixture's sampled selected word-layer
summary remains `0x0000`, so the queue summary should be read as surrounding
sample context, not as the exact loop-local source for the scratch value.

The next runtime-child-memory probe moved inside the forward lane blender and
froze `1000:3CD4` at runtime `01ED:3CD4`. Temp-copy patching was deliberately
blocked for this mode after attempts at `3CD4`/`3CE3` showed the DOS loader
relocating bytes inside the larger instrumentation body near the far-call
operand. Runtime patching avoids that file-image relocation hazard.

The promoted
`explosion_playback_oracle_original_3cd4_lane_div_scratch_runtime.txt` fixture
records the setup-point scratch at `CS:3D24`:

```text
AX/would-be numerator low  = 0xFFF8
DX/would-be numerator high = 0xFFFF
CX/would-be weight sum     = 0x0005
BX/would-be high divisor   = 0x0000
active staging count       = 0x0001
staging loop index         = 0x0001
[BP-8] weight local        = 0x0005
[BP-4] numerator low local = 0xFFF8
[BP-2] numerator high      = 0xFFFF
```

The same held playback sample has `DS:2078=1`, `DS:655E=0x8009`, and
`DS:659A=0x0A7A`, so this directly ties one original forward-helper iteration
to the signed lane numerator and positive weight sum that feed `0920:0945`.
The fixture still has `visual_claim=0`; it proves runtime arithmetic state, not
exact sprite timing.

A follow-up runtime-child-memory probe froze the actual forward divide call at
`1000:3CE3`, runtime `01ED:3CE3`, after the helper loaded the far routine
registers. The promoted
`explosion_playback_oracle_original_3ce3_lane_div_scratch_runtime.txt` fixture
records scratch `CS:3D33`:

```text
AX numerator low  = 0x001C
DX numerator high = 0x0000
CX weight sum     = 0x0010
BX high divisor   = 0x0000
active count      = 0x0001
loop index        = 0x0001
```

This directly validates the `DX:AX` and `BX:CX` register contract at the far
divide call itself. Immediate runtime probes at `1000:3E68` and `1000:3E77`
also loaded their reverse-helper scratch patches on the same route, but they
did not freeze and are therefore recorded only as failed reachability probes,
not promoted evidence.

A later runtime-child-memory probe first froze the forward collapse writeback at
`1000:3D1B`, runtime `01ED:3D1B`, immediately before the original
`mov [di+0x6617],al` instruction executes. The original promoted
`explosion_playback_oracle_original_3d1b_lane_write_scratch_runtime.txt`
fixture records scratch `CS:3D6B`:

```text
output/result byte = 0x0001
DI write offset    = 0x002D
selected tag       = 0x0003
active count       = 0x0001
loop index         = 0x0001
result local       = 0x0001
```

The oracle validates that the collapse tag maps to `DI` by `tag * 0x0F`;
`0x0003 * 0x0F = 0x002D`. This proves one original helper writeback where the
forward lane byte `0x01` is about to be stored at `DS:6617 + 0x002D`
(`DS:6644`). The fixture still has `visual_claim=0`; it proves the queue
writeback arithmetic and destination, not exact sprite timing.

The first writeback instrumentation body was intentionally broad and later
proved unsafe for adjacent mid-branch probes: when placed at `1000:3D2D`, it
overwrote the shared loop join at `1000:3D31`, allowing the collapse branch to
jump into the instrumentation body and produce a false debris-side scratch
record. The safe follow-up uses a three-byte near jump at the probed
instruction and parks the scratch/freezing body at runtime `CS:F000`, with
scratch data at `CS:F080`.

Using that trampoline patch, the same route produced a cleaner forward
collapse writeback fixture,
`explosion_playback_oracle_original_3d1b_lane_write_trampoline_runtime.txt`:

```text
offset             = 1000:3D1B
output/result byte = 0x0004
DI write offset    = 0x003C
selected tag       = 0x0004
active count       = 0x0001
loop index         = 0x0001
```

The tag-to-DI relation again matches collapse stride `0x0F`:
`0x0004 * 0x0F = 0x003C`.

The reverse collapse writeback fixture,
`explosion_playback_oracle_original_3eaf_lane_write_trampoline_runtime.txt`,
freezes `1000:3EAF` before `mov [di+0x6618],al`:

```text
offset             = 1000:3EAF
output/result byte = 0x0000
DI write offset    = 0x003C
selected tag       = 0x0004
active count       = 0x0001
loop index         = 0x0001
```

So the route now proves both collapse writeback bases for the same selected
tag: forward `DS:6617 + 0x003C` and reverse `DS:6618 + 0x003C`.
Safe trampoline probes at `1000:3D2D` and `1000:3EC1` loaded successfully but
did not freeze on this route, so debris writeback still needs a different route
or debugger-seeded setup before promotion as positive evidence.

The follow-up runtime-seeded fixtures patch the original helper call site only
long enough to force the staging word `DS:655E=0xC004` before calling the
original helper body. They are intentionally labeled `runtime_seeded=1`; they
prove helper mechanics, not full gameplay-route reachability.

`explosion_playback_oracle_original_3d2d_lane_write_runtime_seeded.txt` freezes
the forward debris write at `1000:3D2D`:

```text
seed word          = 0xC004
offset             = 1000:3D2D
output/result byte = 0x0035
DI write offset    = 0x0898
selected tag       = 0x4EE8
active count       = 0x0001
loop index         = 0x0001
```

`explosion_playback_oracle_original_3ec1_lane_write_runtime_seeded.txt` freezes
the reverse debris write at `1000:3EC1`:

```text
seed word          = 0xC004
offset             = 1000:3EC1
output/result byte = 0x0000
DI write offset    = 0x0898
selected tag       = 0x4EE8
active count       = 0x0001
loop index         = 0x0001
```

Both fixtures validate the debris marker/stride relation:
`(0x4EE8 - 0x4E20) * 0x0B = 0x0898`. Combined with the natural collapse
writeback fixtures, this proves the original helper's collapse and debris
writeback address arithmetic. The remaining gap is natural route reachability
for debris writeback, not the helper's branch math.

The next helper-output boundary is the final far-pointer result write at
`1000:3D3F` for the forward helper and `1000:3ED3` for the reverse helper.
The new `lane-result-cs-scratch` mode uses the same safe runtime-only shape as
the lane-write trampoline: a three-byte near jump at the probed instruction,
a scratch/freezing body at `CS:F200`, and captured fields at `CS:F280`. The
tool verifies the original/live target bytes are `26 88 05` before patching,
so the mode is tied to the intended `mov es:[di],al` instruction. The
scratch record stores:

```text
output/result byte = AL before mov es:[di],al
ES:DI              = destination used by the write
[BP+4]/[BP+6]      = caller-provided far pointer
result local       = [BP-0D]
active count       = [BP-10]
loop index         = [BP-0A]
target before      = byte previously at ES:DI
```

Current checked-in coverage includes synthetic parser fixtures, one original
reverse result-write fixture, one labeled runtime-seeded original forward
result-write fixture, and one natural route-step forward no-freeze fixture.
Together they prove that the C++ oracle validates the expected original byte
signature `26 88 05`, the `CS:F280` scratch offset, `ES:DI == [BP+4]:[BP+6]`,
`output == [BP-0D]`, byte-width fields, and loop bounds. They anchor the
reverse `1000:3ED3` case to original runtime bytes, the forward `1000:3D3F`
case to original helper execution under a seeded debris-side writeback trigger,
and one `x:2.00,c:0.50` natural route to a documented no-freeze state. Use
`--offset forward` plus repeatable `--route-step KEY:SECONDS` for natural-route
`3D3F` retries.

Follow-up temp-copy instrumentation now freezes the post-call instructions:

- `1000:4C99`, immediately after the `4C96` call returns from `1000:3BB2`.
- `1000:4CAC`, immediately after the `4CA9` call returns from `1000:3D46`.

Both stops use a patched temporary `LEZAC.EXE`, not runtime child-memory
patching, and remain `visual_claim=0`. They preserve helper side effects before
the patched return instruction executes. The paired fixtures freeze the
high-counter state with selected debris base `DS:292B`, selected collapse base
`DS:663E`, target offset `0x05B9`, target byte `0x00`, and word-layer value
`0x0000`. The refreshed fixtures also dump the helper argument globals at
`DS:78C0`; both post-call stops show:

- `DS:78D2=0xF7`
- `DS:78D4=0xFC`
- `DS:2078=0x00`
- `DS:655E=0x0000`
- `DS:659A=0x0000`

So the captured post-call state preserves helper input bytes and queue lane
outputs, but does not prove that the staging globals still hold the static
pre-call values at the frozen sample. At the freeze, the first selected debris
record is:

```text
41 05 04 c0 26 00 1c 00 00 67 80
```

and the first selected collapse record starts:

```text
06 0a 08 0a 09 80 00 04 00 00 04 00 00 01 04
```

This is post-helper lane evidence for the sampled queue state. It complements,
but does not replace, the direct `4C75` scratch-local evidence above.

## C++ Mapping

The `damage_queues` diagnostic now names the static anchors used by this model:

- `high_target_sample=0x4b3f`
- `high_target_byte_gate=0x4b61`
- `high_zero_branch=0x4b6a`
- `high_nonzero_branch=0x4c20`
- `high_word_load=0x4c64`
- `high_word_gate=0x4c75`
- `high_word_gate_skip=0x4cae`
- `effect_forward_call=0x4c96`
- `effect_reverse_call=0x4ca9`
- `effect_forward_return=0x4c99`
- `effect_reverse_return=0x4cac`
- `effect_forward_input_global=0x78d2`
- `effect_reverse_input_global=0x78d4`
- `lane_target_offset_global=0x659a`
- `lane_word_global=0x655e`
- `lane_update_flag=0x2078`

The companion `lane_helper_model` diagnostic pins the helper bodies themselves:
`1000:3BB2` and `1000:3D46` consume a far pointer argument (`[BP+4]`) and byte
weight (`[BP+8]`), walk the one-based staging count at `DS:2078`, read staging
words from `DS:655C + 2*i` and target offsets from `DS:6598 + 2*i`, and store
selected tags in `DS:65D4 + 2*i`. Tags below `0x4E20` address collapse records;
tags at or above `0x4E20` address debris records after subtracting that marker.
The forward helper uses lookup routine `1000:3A7E`, then writes the result byte
to collapse lane base `DS:6617` or debris lane base `DS:2097`. The reverse
helper uses lookup routine `1000:3B18`, then writes the result byte to
`DS:6618` or `DS:2098`. Both helpers write the same result back through the
input far pointer. The lookup helpers store the selected neighbor lane in
`DS:661E`, which the lane blenders multiply by the unsigned selected weight
before adding it to the numerator.

The explosion playback oracle now has a parser path for that final far-pointer
write. It reports `observed_lane_forward_result`/`observed_lane_reverse_result`
and, when scratch data is present, emits `lane_result_*` fields for the result
byte, destination far pointer, caller argument pointer, result local, loop
state, and prior target byte.

The `lane_blend_arithmetic` diagnostic now pins the delegated blend helper:
`0920:0945` divides signed 32-bit numerator `DX:AX` by signed 32-bit divisor
`BX:CX`, leaves the quotient in `DX:AX`, and uses `AL` as the lane byte. The
lane helper passes the positive weight sum as `BX:CX`, so this is the arithmetic
form of `signed_lane_weight_sum / weight_sum`. The quotient rounds toward zero,
the remainder in `BX:CX` keeps the dividend sign, and the zero-divisor path at
`0920:09AC` loads `AX=0x00C8` before entering the runtime error handler.
The original `3CD4` scratch fixture confirms this register contract in a live
forward-helper setup with `DX:AX=0xFFFF:0xFFF8` and `BX:CX=0x0000:0x0005`;
the original `3CE3` scratch fixture confirms it again at the actual far divide
call with `DX:AX=0x0000:0x001C` and `BX:CX=0x0000:0x0010`.
The original `3D1B` scratch fixture confirms the next step in the same helper
family: the quotient/result byte is copied from `[BP-0D]` to the lane table
through the selected tag's collapse record offset.
The post-call fixtures that show `DS:2078`, `DS:655E`, and `DS:659A` as zero
are therefore compatible with a transient staging lifetime: they preserve the
helper-written queue bytes after the helper has returned, not a mid-helper view
of the staging arrays.

The explosion playback oracle output now also exposes one-hot freeze flags for
the promoted high-debris fixtures:

- `observed_high_zero_branch`
- `observed_high_word_gate`
- `observed_effect_forward_call`
- `observed_effect_reverse_call`
- `observed_effect_forward_return`
- `observed_effect_reverse_return`

The original `4B6A`, `4C75`, `4C96`, `4CA9`, `4C99`, and `4CAC` CTest
expectations pin those flags so a fixture cannot silently parse while no longer
proving the intended instrumented stop. The return flags are used by the
post-call temp-copy captures because the call-site fixtures freeze before the
helper body executes. The oracle also reports `observed_freeze_count` and
`observed_freeze_offset`, reports optional `bp4_local_present`,
`bp4_local_cs_offset`, and `bp4_local_value`, and checks consistency with
`instrumented_freeze_observed` and `runtime_freeze_patch_applied` when those
capture-helper fields are present. Malformed fixtures cover the consistency
failures:

- `explosion_playback_oracle_freeze_missing_break.txt`
- `explosion_playback_oracle_freeze_without_instrumented_flag.txt`
- `explosion_playback_oracle_freeze_without_runtime_patch.txt`
- `explosion_playback_oracle_multiple_freeze_breaks.txt`
- `explosion_playback_oracle_top_freeze_without_runtime_patch.txt`
- `explosion_playback_oracle_bp4_local_without_word_gate.txt`
- `explosion_playback_oracle_lane_div_without_divide_freeze.txt`
- `explosion_playback_oracle_lane_write_bad_di.txt`
- `explosion_playback_oracle_lane_result_missing_target_before.txt`
- `explosion_playback_oracle_lane_result_bad_far_pointer.txt`
- `explosion_playback_oracle_lane_result_bad_output_local.txt`
- `explosion_playback_oracle_lane_result_bad_expected_old_bytes.txt`
- `explosion_playback_oracle_lane_result_expected_without_old_bytes.txt`
- `explosion_playback_oracle_lane_result_missing_expected_old_bytes.txt`
- `explosion_playback_oracle_lane_result_bad_scratch_offset.txt`
- `explosion_playback_oracle_lane_result_bad_kind.txt`
- `explosion_playback_oracle_lane_result_bad_loop_bounds.txt`
- `explosion_playback_oracle_lane_result_bad_target_before_width.txt`
- `explosion_playback_oracle_lane_result_field_without_present.txt`

The surrounding helper model from `docs/GHIDRA_NOTES.md` is now explicit:
the forward/reverse lookup helpers at `1000:3A7E` and `1000:3B18` select
argument bytes from collapse offsets `+6/+7` and debris offsets `+4/+5`; the
lane blenders at `1000:3BB2` and `1000:3D46` write playback lanes back through
collapse offsets `+6/+7` (`DS:6617`/`DS:6618` for slot zero) and debris offsets
`+4/+5` (`DS:2097`/`DS:2098` for slot zero), using `0x4E20` as the high-half
spill marker. The first one-based original-written slots therefore have lane
write addresses `DS:6626`/`DS:6627` for collapse and `DS:20A2`/`DS:20A3` for
debris, which the `damage_queues` diagnostic already locks.

## Current C++ Boundary

The live C++ queue model still treats `forwardPhase` and `reversePhase` as
construction-time fields and uses a provisional `drawDamageQueues` renderer.
That is intentionally weaker than the original helper pipeline described
above: the original mutates lane bytes during the `1000:45FA..4D3B` consumer
pass before the visible debris/collapse presentation. No gameplay or rendering
behavior should change from this model alone.

A 2026-04-25 WSL/Xvfb frame comparison bundle now pairs original and C++ frames
for the level-1 bomb route and records C++ queue metadata in the frame manifest.
The original capture visibly leaves the menu and reaches the blast/playback
frames, but the current renderer is still approximate enough that pixel diffs
are large across the whole frame. The useful frame-facing signal is the queue
metadata: C++ has one collapse record at `start=0x0A06`, `end=0x0A08`,
`flagged=0x8009`, `affected=4`, `count=2`, with `collapse0_forward=0` and
`collapse0_reverse=0` at explosion and playback checkpoints. The original
`4C99`/`4CAC` post-call fixtures preserve the same collapse span with helper
lane bytes `forward=0x00`, `reverse=0x04` after the lane helpers. That mismatch
is now explicit evidence for the next rendering/playback recovery step.

The 2026-06-15 WSL route sweeps promoted natural non-seeded evidence for the
reverse debris writeback (`1000:3EC1`) and the forward final far-pointer result
write (`1000:3D3F`). Natural forward debris writeback (`1000:3D2D`) remains
the next lane-write evidence target before replacing the provisional queue
playback, but the simple route sweeps have now been spent. The reviewed
expanded matrix completed as valid `no_freeze` evidence, and later focused
lane-global gates proved that nearby timings can arm the patch without reaching
`3D2D`. The most recent route/timing sweep wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-lane-global-route-variants-1781610807`:
routes `x:2.00,c:0.35` and `x:2.00,c:0.65` patched at `3.614s` and `2.970s`
with selected bases `209e/663e/c22e` and lane globals `0x01/0x8002/0x07be`,
but both remained `no_freeze`; the other three nearby variants stayed
`no_patch`. Do not rerun the same expanded matrix or nearby lane-global timing
variants as the next step.

Direct q78 lane-global control-flow probes on those two patching timings now
show the late predicate is too late to catch the relevant branch window. The
`1000:4C96` loop-patch run at
`C:\Users\andrz\AppData\Local\Temp\lezac-lane-global-4c96-probe-1781611559`
armed at `2.769s` for `x:2.00,c:0.35` and `3.607s` for `x:2.00,c:0.65`, with
selected bases `209e/663e/c22e`, high-debris target offset `0x05bd`, and lane
globals `0x01/0x8002/0x07be`. The native oracle reported no freeze and no
`observed_effect_forward_call`. The paired `1000:4C75` bp4-scratch run at
`C:\Users\andrz\AppData\Local\Temp\lezac-lane-global-4c75-probe-1781611676`
armed at `2.680s` and `2.708s`, recorded scratch site `01ED:4C7E` / old bytes
`2001`, and still reported no freeze, no high-word gate, and no bp4 local.
This proves only that neither `4C75` nor `4C96` is reached after the q78
lane-global patch is installed in the sampled/tail window; it does not disprove
earlier execution before the predicate matches.

The next probe moved the patch earlier and classified the route instead of the
state sample. For `x:2.00,c:0.35`, selected-base gating without lane-global
requirements armed `1000:4C75` at
`C:\Users\andrz\AppData\Local\Temp\lezac-early-4c75-selected-base-1781613438`
after `2.002s`, with selected bases `209e/663e/c22e`, high-debris target
offset `0x05bd`, and lane globals `0x00/0x0002/0x07bc`; the native oracle saw
no freeze, high-word gate, bp4 local, or lane write. The matching
selected-base `1000:4B3F` run at
`C:\Users\andrz\AppData\Local\Temp\lezac-early-4b3f-selected-base-1781613513`
armed after `2.045s` and also did not freeze. Moving `4C75` even earlier with
`after_bomb=1.0`, `after_bomb=0.0`, and `before_bomb` still loaded the patch
without a gate hit, all from the early `2093/6620/c22e` sampled state. Finally,
before-bomb `1000:4B3F` loop patches for both `x:2.00,c:0.35`
(`C:\Users\andrz\AppData\Local\Temp\lezac-early-4b3f-before-bomb-1781613826`)
and `x:2.00,c:0.65`
(`C:\Users\andrz\AppData\Local\Temp\lezac-early-4b3f-before-bomb-c0p65-1781613903`)
loaded but did not freeze. These are route-classification negatives: the two
`c` timing variants expose sampled lane-state transitions but have not shown
live `4B3F`/`4C75` branch execution after the route/bomb timing used here.

`tools/sweep_original_branch_anchor_routes.py` now captures this classification
workflow as a guarded dry-run/live runner. By default it plans before-bomb
runtime probes for `1000:4B3F`, `1000:4C75`, and `1000:4C96` across
`x:2.00`, `x:2.00,c:0.35`, `x:2.00,c:0.65`, and `x:2.00,m:0.35`; it also
supports selected-base and after-bomb timing modes when the route family needs
to be bracketed.

The first live classifier pass wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-branch-anchor-default-1781615578`.
In that default matrix, only `x:2.00,m:0.35` produced positive branch-anchor
freezes: `1000:4C75` with `bp4_local_value=0x8002` and `1000:4C96`. A focused
one-route all-anchor pass wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-branch-anchor-m-all-1781616282` and
classified the same route more sharply: `1000:492F`, `1000:4B3F`,
`1000:4B61`, `1000:4B6A`, `1000:4C75`, and `1000:4C96` froze, while
`1000:4C20` and `1000:4CA9` did not. Tail frames for the positive anchors were
visually inspected and stayed in the level-1 route/playback window, so this is
valid branch-execution evidence, not a menu/input artifact.

The corresponding natural forward-debris retry wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-lane-write-forward-m-route-1781616090`.
It targeted `1000:3D2D` on `x:2.00,m:0.35` with the classifier-derived state:
selected bases `2941/665c/c22e`, target byte `0xde`, queue score `160`,
debris/collapse counts `202/5`, and lane globals `0x00/0x0004/0x072c`. The
runtime patch applied at `2.781s` after the bomb, but the oracle and
`tools/summarize_lane_write_route_sweep.py` classify the result as
`no_freeze`: no forward-debris lane-write scratch record and
`missing_offsets=3d2d`. The sampled and tail screenshots were inspected; the
route reaches visible blast/smoke playback and then continues normally. This
brackets the remaining question between the now-proven `4C96` forward-call
anchor and the missing `3D2D` writeback, rather than between route input and
the high-debris branch path.

The next helper-path probes closed that bracket for this route. A runtime
`1000:4C99` return probe wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-helper-path-4c99-m-route-1781617322`
and froze after the `4C96 -> 3BB2` forward helper returned with the same
selected bases `2941/665c/c22e`, target byte `0xde`, and lane globals
`0x00/0x0004/0x072c`. A `1000:3CE3` lane-divide scratch probe wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-helper-path-3ce3-m-route-1781617440`
and froze inside the forward helper with active count/index `1/1`,
`DX:AX=0xffff:0xfff3`, `BX:CX=0x0000:0x0021`, and weight local `0x0021`.
Finally, a `1000:3D1B` lane-write scratch probe wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-helper-path-3d1b-m-route-1781617379`
and froze the natural forward collapse write: output `0x0000`, `DI=0x001e`,
tag `0x0002`, active count/index `1/1`, result local `0x0000`. The tail
freeze frames for all three captures were inspected and remained in the
visible level-1 playback window. This explains why the same route misses
`3D2D`: the helper is executing, but the active writeback tag is a collapse
tag below the debris marker base `0x4e20`, so the natural store is `3D1B`.

A follow-up helper-tag route search wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-forward-helper-tag-search-1781617957`
and tested `1000:3D1B`/`1000:3D2D` across `x:1.50,m:0.35`,
`x:2.50,m:0.35`, `x:2.00,m:0.15`, and `x:2.00,m:0.65`. The summary reports
eight candidates, two observed freezes, two ready candidates, six valid
no-freeze candidates, and `missing_offsets=3d2d`. Both freezes were again
forward collapse writes at `3D1B`: the `x:2.00,m:0.15` and `x:2.00,m:0.65`
routes wrote output `0x0000`, `DI=0x004b`, tag `0x0005`, active count/index
`1/1`, and no debris write. Their paired `3D2D` candidates patched cleanly but
did not freeze. Tail frames for the positive `3D1B` route, its paired `3D2D`
miss, and the `x:2.50,m:0.35` `3D2D` miss were inspected in the level-1
explosion/playback window. The search extends the negative evidence: nearby
`m` timings still produce collapse tags below `0x4e20`, not the debris-marker
helper state needed for natural `3D2D`.

A broader expanded-route subset wrote
`C:\Users\andrz\AppData\Local\Temp\lezac-forward-helper-expanded-tag-subset-1781622932`
and tested `x:1.75`, `x:2.25`, `x:2.00,c:0.25`, `x:2.00,c:0.75`, and
`x:5.00,m:0.50,x:2.00` against both `1000:3D1B` and `1000:3D2D`. All ten
candidates patched and parsed, but the summary reports `observed_freezes=0`,
`ready_candidates=0`, `no_freeze_candidates=10`, and
`missing_offsets=3d1b,3d2d`. Representative tail frames for `x1p75`,
`x2p00_c0p25`, and `x5p00_m0p50_x2p00` stayed in live level-1 playback. These
routes are route-pruning evidence: they neither show a collapse-tag helper
write nor the desired debris-marker helper write under before-bomb patching.

Use `tools/sweep_original_lane_write_routes.py` only when a new route or
control-flow hypothesis has been identified. The default matrix targets
`3D2D`/`3EC1` with the `late-collapse` runtime-freeze gate and writes stable
route/offset labels, commands, logs, and manifest entries. The last focused
lane-global command shape was:

```sh
python3 tools/sweep_original_lane_write_routes.py \
  /mnt/c/Users/andrz/AppData/Local/Temp/lezac-lane-write-forward-lane-global-route-variants . \
  --route x:2.00,c:0.35 --route x:2.00,c:0.65 --offset forward-debris \
  --runtime-freeze-preset none \
  --runtime-freeze-min-queue-score 0x78 \
  --runtime-freeze-min-debris-nonzero 0x20 \
  --runtime-freeze-min-collapse-nonzero 0x01 \
  --runtime-freeze-min-effect-nonzero 0x10 \
  --runtime-freeze-require-collapse-base 0x663e \
  --runtime-freeze-require-effect-base 0xc22e \
  --runtime-freeze-require-lane-update-flag 0x01 \
  --runtime-freeze-require-lane-word-global-value 0x8002 \
  --runtime-freeze-require-lane-target-offset-global-value 0x07be \
  --approve-procmem --approve-runtime-instrumentation \
  --cpp-exe ./build-win-codex-vs3/Debug/lezac_cpp.exe --continue-on-oracle-error
```

The next useful evidence step should search for a natural forward-helper
iteration whose scratch tag is a debris marker (`>= 0x4e20`). Use helper-path
scratch probes such as `3CE3`/`3D1B` first to classify candidate routes, then
target natural `1000:3D2D` only after a route has shown a forward helper
debris tag. Do not rerun the same `m:0.35` branch-anchor matrix or the same
classifier-derived `3D2D` gate unchanged.
The final unpruned level-1 route pair is encoded as
`--route-preset forward-helper-tag-open`; the completed no-sample run at
`C:\Users\andrz\AppData\Local\Temp\lezac-forward-helper-tag-open-nosamples-1781623828`
tested those routes with the `forward-collapse` and `forward-debris` offsets,
`--runtime-freeze-preset none`, and `--runtime-freeze-before-bomb`. It produced
four valid no-freeze fixtures and `missing_offsets=3d1b,3d2d`; route/tail
frames stayed in live level-1 playback. A sampled predecessor at
`...\lezac-forward-helper-tag-open-1781623743` failed during route-state
sampling with a `/proc/<pid>/mem` permission error, so use
`--route-state-interval 0` for reproducing this classification.

Summarize its output with
`tools/summarize_lane_write_route_sweep.py <manifest-or-dir>`. The summarizer
prints each ready lane-write candidate's scratch tag and derived
`lane_write_tag_class`; add `--require-debris-tag` when the search should fail
unless a ready candidate has a tag at or above the `0x4e20` debris-marker base.
For the remaining natural forward writeback, prefer
`--require-forward-debris-tag`; broad debris evidence can be satisfied by the
already-observed reverse debris write at `3EC1`, while the unresolved target is
the forward debris write at `3D2D`. Once that stricter gate passes,
`--write-forward-debris-route-manifest` records the exact matching route steps
as `lane_write_forward_debris_route_candidates` for a focused
`tools/sweep_original_lane_write_routes.py --route-manifest` retry.
The prior helper-tag search now reports `debris_tag_candidates=0`,
`collapse_tag_candidates=2`, and `max_lane_write_tag=0x0005`, so it remains
negative evidence for natural forward-debris writeback. Add
`--write-ready-manifest <path>` when a follow-up oracle run should use only
ready natural debris-write candidates. Recheck that ready manifest with
`tools/run_lane_write_ready_manifest.py <manifest> --dry-run` first, then run it
live with `--log-dir <tmp-dir>` and `--write-result-manifest <tmp-file>`.
Summarize the executed or planned result manifest with
`tools/summarize_lane_write_ready_results.py <result-manifest>`, adding
`--require-success --require-executed --require-source-environment-preflight`
when promoting a completed original run.
Use
`tools/sweep_original_lane_result_routes.py --offset forward` for the final
`3D3F` result-write retries or regression reruns; pass `--cpp-exe <lezac_cpp>` when the default
`build/lezac_cpp` path is not the active build, and inspect the dry-run
`oracle_commands` count before running the capture. The lane-result sweep
accepts only `forward`/`3D3F` and `reverse`/`3ED3` offsets, so bad capture
plans fail during dry-run review. The sweep wrappers take repeatable
`--route KEY:SECONDS,...` entries and pass those through to the lower-level
capture helpers as `--route-step KEY:SECONDS`.
