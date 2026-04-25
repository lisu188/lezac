# High-Debris Lane Branch Model, 2026-04-25

This note records the static branch model for the high-debris lane calls in
`LEZAC.EXE`. It complements the original-runtime fixtures for `1000:4C75`,
`1000:4C96`, and `1000:4CA9`; it does not promote any new visual claim or live
C++ behavior.

Current local validation constraints:

- WSL/DOSBox access is blocked in this session with `Wsl/Service/CreateInstance/E_ACCESSDENIED`.
- Native Windows CMake is blocked because `pkg-config sdl2` is not available.
- Git writes are blocked by `.git/index.lock: Permission denied`.

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
bases, high-debris target bytes, and frozen frame hashes. They do not capture
the live `[BP-4]` local at the exact frozen instruction, and the `4C96`/`4CA9`
freezes patch the call instruction itself. The positive-word claim for `4C96`
and `4CA9` is therefore a static-control-flow inference from the branch shape
above, not a direct local-variable dump or helper-output byte dump.

Follow-up temp-copy instrumentation now freezes the post-call instructions:

- `1000:4C99`, immediately after the `4C96` call returns from `1000:3BB2`.
- `1000:4CAC`, immediately after the `4CA9` call returns from `1000:3D46`.

Both stops use a patched temporary `LEZAC.EXE`, not runtime child-memory
patching, and remain `visual_claim=0`. They preserve helper side effects before
the patched return instruction executes. The paired fixtures freeze the
high-counter state with selected debris base `DS:292B`, selected collapse base
`DS:663E`, target offset `0x05B9`, target byte `0x00`, and word-layer value
`0x0000`. At the freeze, the first selected debris record is:

```text
41 05 04 c0 26 00 1c 00 00 67 80
```

and the first selected collapse record starts:

```text
06 0a 08 0a 09 80 00 04 00 00 04 00 00 01 04
```

This is post-helper lane evidence for the sampled queue state, while the exact
live `[BP-4]` local remains unresolved.

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
- `lane_target_offset_global=0x659a`
- `lane_word_global=0x655e`
- `lane_update_flag=0x2078`

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
`observed_freeze_offset`, and checks consistency with
`instrumented_freeze_observed` and `runtime_freeze_patch_applied` when those
capture-helper fields are present. Five malformed fixtures cover the
consistency failures:

- `explosion_playback_oracle_freeze_missing_break.txt`
- `explosion_playback_oracle_freeze_without_instrumented_flag.txt`
- `explosion_playback_oracle_freeze_without_runtime_patch.txt`
- `explosion_playback_oracle_multiple_freeze_breaks.txt`
- `explosion_playback_oracle_top_freeze_without_runtime_patch.txt`

The surrounding helper model from `docs/GHIDRA_NOTES.md` remains unchanged:
the forward/reverse lookup helpers at `1000:3A7E` and `1000:3B18` select
argument bytes from collapse offsets `+6/+7` and debris offsets `+4/+5`; the
lane blenders at `1000:3BB2` and `1000:3D46` write playback lanes back through
collapse offsets `+8/+9` (`DS:6617`/`DS:6618` for slot zero) and debris offsets
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

The next evidence step is to derive the exact helper inputs and compare these
post-call lane bytes to C++ frame captures before replacing the provisional
queue playback.
