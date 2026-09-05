# Original Player Animation Recovery

Eight original level-1 traces provide 814 consecutive motion and animation
states: 808 samples from natural motion driven only by normalized controls,
and six from an explicitly seeded animation-cursor probe. The production C++
update matches all states continuously, including 161 displayed sprite
changes. This supersedes the port's fixed eight-tick walking animation and
hardcoded airborne sprite, not the remaining game-wide fidelity boundaries.

## Original Instructions

Ghidra anchors use segment `1000`; file offsets add `0x770`.
`LEZAC.EXE` SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

- Actor `+16..1C` is the seven-byte active cursor: current, first, last,
  counter, delay, mode and signed step. Its backup occupies `+1D..23`.
  Player actor `+2` is the idle byte. Actor `+1` selects the visual row at
  `DS:C21E + index*8`; that row stores X/Y, width/height and pixel offset.
- Initializer `06AB` sets current and first to the first-frame argument,
  counter and delay to the delay argument, and step to 1. Player setup at
  `2D91..2DCB` initializes P1 to descriptors 2..9, delay 1, mode 1;
  `2DCE..2E08` initializes P2 to 21..28. The preceding descriptor copy at
  file `34CF..34FE` initially gives both visual rows descriptor 1. These
  setup/P2 mappings are static evidence, not new P2 runtime observations.
- `6078..615A` advances animation before the player input branch. Mode 0
  does nothing. Otherwise it increments the byte counter and advances only
  when counter > delay, resetting counter to zero. Mode 2 reverses signed
  step at either endpoint. Other modes wrap current to first when above
  last. On a mode-3 wrap, `60F1` copies seven bytes from backup `+1D` into
  active `+16`, not the reverse. A successful advancement writes the
  resulting descriptor's pixel offset to the visual row.
- P1 input locals at `6193..61B4` select idle descriptor 1, right 2..9 and
  left 10..17. P2 at `6200..6221` selects idle 20, right 21..28 and left
  29..36. The frame used for directional range checks is cached after
  cursor advancement.
- Left `6A96..6AC6` and right `6AEC..6B1C` initialize the appropriate range
  with delay 0 and mode 1 if the cached frame is outside that range; they
  also clear the idle byte. They do not immediately change the displayed
  descriptor. Thus the selected cursor and displayed sprite are distinct.
- `6B55..6B6D` writes the next delay as byte `4 - abs(VX)/256`, after input
  acceleration/braking but before wall reflection and integration.
- `6B71..6BD1` increments the idle byte when normalized left+right+down is
  zero. At exactly 5 it disables the cursor, sets current to 1 even for P2,
  and writes idle descriptor 1 or 20 separately. Short pauses accumulate
  unless a directional-range change clears the byte; the byte wraps at
  255. Jump does not prevent this idle transition. These new traces have
  down=0 throughout; down normalization is not recovered by this batch.

The former diagnostic's mode-3 copy direction was backwards. The diagnostic
now uses the same `ActorAnimation` helper as production, and the controlled
original probe below establishes the corrected direction independently.

## Runtime Capture

The eight captures used a fresh temporary asset copy at
`/tmp/lezac-player-animation-20260905-6C0fGC`, private Xvfb and an owned DOSBox
child launched through the existing level-1 menu workflow. For each route:

```sh
python3 tools/capture_original_player_walk.py --animation \
  --run-dir /tmp/lezac-player-animation-20260905-6C0fGC \
  --route braking \
  --out /tmp/lezac-player-animation-20260905-6C0fGC/braking.txt \
  --approve-procmem --approve-runtime-instrumentation
```

The `cursor_restore` route additionally requires `--approve-animation-seed`.
No position, velocity, fraction, collision, gameplay timer or frame-parity
field is seeded. In seven routes only normalized input bytes are exogenous.
In the eighth, the first pre-advance stop writes exactly actor `+16..23`:
active `{6,5,6,1,1,3,1}`, backup `{8,8,9,2,2,1,1}`. The first original advance
restores all seven backup bytes to active and displays zero-based sprite 7.
The backup remains unchanged; subsequent input writes delay 4 normally.
This is a controlled cursor experiment, not a naturally reached hard landing.

The added pre-advance checkpoint is Ghidra `6064`, after `ES:DI` selects the
actor. It filters P1 behavior 0. Installation first parks the child there,
then installs the existing `6813` pre-input, `6B55` post-response and `741E`
post-integration stops. Register/FLAGS-preserving trampolines replay the
displaced instructions. Only the owned child is stopped for installation and
restoration. Thirteen original instruction windows and an empty scratch area
are guarded. Original shipped files are never rewritten in the repository.

Recorded pre-input registers are `CS=01A2`, `DS=0C44`, `ES=3EA9`, `SS=18B3`,
saved post-push `SP=3FA2`, `BP=3FEE`. Runtime checkpoint IPs are therefore
`01A2:6064`, `01A2:6813`, `01A2:6B55`, `01A2:741E`. The runtime far actor
pointer is translated using observed register segments, not Ghidra's `1000`.

The first `idle_resume` attempt failed before capture with `runtime
instruction mismatch at 60f1`: its guard included the far-call segment word,
which the DOS loader relocates. The corrected guard includes the call opcode
and offset `090E` but excludes the relocated segment. The owned child was
cleaned up, no trace/images were produced, and the rerun completed. This
instrumentation failure is not a game-behavior observation.

| Route | Normalized Input Sequence | Samples |
| --- | --- | ---: |
| braking | right 20, idle 28, left 20, idle 28 | 96 |
| reversal | right 20, left 36, right 36, idle 28 | 120 |
| reaccelerate | right 20, idle 7, right 12, idle 28; mirrored left | 134 |
| air_coast | right 10, jump+right 1, idle 28 | 39 |
| switch_coast | right 20, both 8, idle 28 | 56 |
| idle_resume | idle 260, right 20, idle 28 | 308 |
| short_idle | right 20, idle 3, right 4, idle 28 | 55 |
| cursor_restore | idle 6; initial cursor-only seed described above | 6 |

All captures completed with consecutive frame counters and explicit sample
counts. The committed files are `tests/fixtures/player_animation_original`.
The `cursor_seeded=1` header identifies the controlled probe; missing or zero
means no cursor seed in the natural routes. Each file contains the 92-row
descriptor table at `DS:C322`, including its unused row 0. The replay checks
the dimensions and cumulative pixel offsets of all 91 remaining rows against
the decoded sprite bank before comparing individual displayed descriptors.

Each tick adds pre-advance actor/visual bytes (`entry`, `entry_visual`) and
post-integration actor/visual bytes (`final_actor`, `final_visual`) to the
existing three local-frame snapshots. The final checkpoint precedes motion
writeback: final actor motion and visual X/Y are still the prior committed
state, while their animation fields and descriptor are already updated.
The replay uses post-integration locals for resulting motion and only the
appropriate animation/descriptor fields from final actor/visual bytes.

## Production Replay

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-player-animation-original \
  tests/fixtures/player_animation_original \
  build-codex-tmp/player-animation-final-frames
python3 tools/capture_original_player_walk.py --self-check
```

Each route initializes from its first captured state only, then drives
production `updateWithControls` continuously with ordinary normalized
controls. No per-tick motion or animation state is injected. Assertions check
entry and final cursor, backup, idle byte, displayed descriptor, X/Y, VX/VY
and both fractional carries. An intermediate copy of the production advance
helper also matches the original pre-input animation state.

```text
player_animation_original=ok cases=8 samples=814 full_motion_states=814 input_responses=814 overspeed_states=19 air_coast_states=12 animation_states=814 sprite_descriptors=814 sprite_changes=161 coasting_idle=189 natural_samples=808 cursor_seeded_samples=6 frame_inspection=1 frame_hash=1d097f8462cac560
```

The `player_animation_original` CTest pins this bounded evidence. The existing
five-route motion replay is retained unchanged as a separate fixture bundle.
Both animation diagnostics now exercise the production cursor helper.

The renderer selects the stored displayed sprite, not a separately timed
walking loop or a fixed airborne frame. Braking sample 24 already displays
idle sprite 0 while VX=814; left-input sample 48 selects cursor 10 while the
displayed sprite remains 0 until advancement. These are intentional original
behaviors, not immediate facing changes inferred from velocity.

## Frame Inspection

The optional replay wrote 184 PPMs, each verified as nonuniform 320x200 RGB,
plus a CSV containing route/sample, input phase, original frame, motion,
sprite, cursor, idle byte and framebuffer hash. Its SHA-256 is
`2c466088420be40fb8f5ad1b745faf4ec9432b11151cd5d55b9ca225593bea6a`;
the last framebuffer hash is `1d097f8462cac560`. The viewed contact sheet at
`build-codex-tmp/player-animation-final-frames/inspection.png` shows walking,
coasting idle, delayed left selection, reversal, airborne movement, short
idle resume, long idle resume and the controlled restore pose.

Original `braking_020.png`, `air_coast_020.png`, `switch_coast_032.png` and
`reversal_020.png` were also viewed. They show level-1 gameplay, airborne
player art and the changed selected weapon, not a stuck menu. Original
screenshots are the last presented frame while the updater is paused; the
C++ harness renders the completed update. Camera and sprite phase can differ
between those images, so they are visual inspection, not pixel-parity proof.
The user-facing `original-walking.png` and `cpp-walking.png` in
`build-codex-tmp/player-animation-frames` show these nearby walking moments.

## Validation

The build and `git diff --check` pass. The full 424-case dummy-SDL run passed
423 cases and skipped only the separate Xvfb UI case, with no failures, in
427.74 seconds. That UI case then passed independently in 5.01 seconds, so
all 424 cases are covered, including original replay and existing bomb,
collapse, death/reentry and two-player autoplayers. The existing unrelated
debris-debug `snprintf` warning is unchanged. Linux and Windows CI must also
pass on the final commit before merging.

## Remaining Boundaries

This is bounded P1 level-1 motion/cursor equivalence plus one controlled
mode-3 restore probe, not whole-frame pixel parity or full-game fidelity.
P2 initialization/ranges are instruction-backed and existing two-player
autoplayers remain regression coverage, but new live P2 animation traces
have not been captured. Hard-landing cursor selection, cooldown, down-key
normalization/drop-through, launch-pad and portal presentation, death/reentry
events and unrestricted cross-gameplay ordering remain open. In particular,
the current production idle gate handles normalized left/right; the original
down contribution needs its surrounding normalization branches recovered.
The broader reverse-engineering goal remains incomplete.
