# Boss Physical Ownership Counterexample

## Verified Failure

The diagnostic-only checkpoint `d5995eb` starts from integration PR #439 at
`0031cf0964d165f56d7283b5ebba6933d1a5e15a`. It adds an actual-App command,
`--debug-boss-physical-ownership`, without changing production behavior.
The command disables the legacy adapter, loads the real level-7 setup and
calls the production boss-link and monster-update helpers for eight ticks.
This is a controlled App helper test, not a natural route, whole-frame loop
test or new original-game comparison. It injects no per-tick actor state.

The isolated Linux App object was compiled with the current CMake App flags
and linked against the existing #439 objects/libraries. With original assets
and dummy SDL audio/video, the command returns 1:

```text
boss_physical_first_mismatch tick=1 order=2 typed=92,117 physical=92,118
boss_physical_ownership initial_cursor_byte_differences=35 coordinate_mismatches=46 ticks=8 legacy_adapter=0 actual_App_helpers=1 natural_route=0 original_comparison=0
fatal: boss physical visual/animation owner is stale
```

## Source Boundary

`spawnLevel7BossFromBank` allocates physical records through the generic
constructor but does not install the complete copied GRAN actor/animation
state. The original loader copies 38-byte records and rebases visual/link
indexes; generic constructor state is not an equivalent lifetime.

`updateMonsters` writes shared animation and final physical motion only for
kinds 1..8. The boss head/segments use kinds 30/31, so their typed state moves
while the physical visual rows remain stale. `WorldRaster` now reads those
rows during normal play. Existing seeded boss screenshots select the explicit
legacy visual adapter and do not test this ownership boundary.

The finding is a merge blocker on #429 and #439 even if their hosted CI and
automated reviews are green. Both PRs were returned to draft and the finding
was recorded in conversation comments. #440's unintegrated CPU prologue
recovery is separate and remains stacked on the blocked #439 dependency.

## Required Repair

Recover physical GRAN initialization, visual permutation, owner fields and
link records against original evidence. Connect shared animation, descriptor,
motion, damage and conversion writes to the live physical boss records while
preserving latched dimensions and opaque bytes. Add actual-App no-legacy
regressions and original-backed physical-state/frame checks.

Do not enable the legacy adapter in normal play or reconstruct all physical
visuals from typed vectors at render time. Keep the verified failure until a
production repair passes the same boundary and the broader boss regressions.
There is no fix, native Windows proof, natural boss victory or whole-game
parity claim in that diagnostic checkpoint. The subsequent candidate below
repairs the tested owner boundary without replacing this red evidence.

## Original Loader Exploration

A first exploratory Unicorn run executes the unchanged original `08A5..0C32`
GRAN loader and all guest callees. An explicit host DOS-file device services
the requested open/read calls from canonical `GRAN.MST` bytes; this is not a
DOSBox kernel or natural-play capture, and guest DOS services are modeled.
No guest function is stubbed or code patched. The loader consumes all 399
file bytes, returns to the seeded caller at `1000:2E9C`, leaves actor/visual/link
counts `7/9/6`, and preserves all 43,552 original code bytes.

The exact exploratory source is retained at
`evidence/boss_physical_ownership_20261018/gran_loader_probe_source.py`.
Its hard-coded RAM/dependency paths describe the actual research invocation,
not a portable supported command. The generated 1 MiB memory remains RAM-only
and is not published. This probe has not yet gained independent repeats,
observed/unobserved controls, bounded compact fixture export, complete input
binding or C++ comparison. Its output is not a frozen regression expectation
and does not clear the merge blocker.

## Guarded Original Loader Corpus

`tools/gran_loader_oracle.py` supersedes the exploratory probe for regression
expectations. It runs the unchanged original loader and all guest callees with
pinned Unicorn 2.1.4 and the verified mapped library. The host handles only
the actual INT 21h open and exact-length read requests for canonical
`GRAN.MST`: one open plus 25 reads consume all 399 bytes. Hardware I/O,
unexpected interrupts, services, filenames, read bounds and guest write
owners fail closed. No guest function is stubbed and no instruction is patched.
This is an explicit DOS file-device model, not execution of a real DOS kernel.

The 24 cases combine prior actor counts 0/1/23, prior link counts 0/1 and
four origins including signed-word wrap boundaries. Each observed run agrees
with an independent unobserved run on all 14 endpoint registers, complete
1 MiB memory and DOS request sequence. Ordered guest writes plus the explicit
DOS-device writes reconstruct all final memory. All 43,552 code bytes remain
unchanged. Independent final generations `lezac-gran-loader-t238-b` and `-c`
produce byte-identical manifests and compressed projections.

The frozen projection contains all 31 actor records, 33 visual rows, eight
link rows, counts and shared result, before and after each call. Inactive
tails, opaque fields, visual-index permutation and raw disabled animation
bytes are included. The row-32 descriptor alias is preserved.

| Artifact | SHA-256 |
| --- | --- |
| `manifest.json` | `39ac07d3379534a84862e340532edd30224e6f2c0dbddc5226aead1fa5ec3db6` |
| `oracle.bin.gz` (3,711 bytes) | `026d2ac051201bbb4d56ba1acad3fe9e4333ab0a11e97c8d522a309ab6419d05` |
| Expanded projection (75,900 bytes) | `2eaccaa362f7e0e99ea6abf6eeb10dcf0e5c8cfbbec6f98c10808203922b3390` |

No full memory image, raw runtime trace or screenshot is published.

## Production Candidate

`GranGroup` parses the existing binary records and appends a complete group
transactionally. It preserves raw actor fields, applies original conditional
word rebasing (including carries), initializes only nonzero animation
selectors, installs visual descriptors in file order and appends rebased
links. `ActorSlots` binds the new identities after the validated storage
transition. Capacity, duplicate/invalid identities and failing descriptor or
animation callbacks leave the previous storage and identities unchanged.

The App now loads the boss through this operation instead of generic actor
construction. Its typed mirror reads the loaded physical records. Shared
animation, motion, damage, descriptor changes and debris conversion write to
the owned physical records; normal rendering still reads those records.
Link motion writes only phase and output coordinates, preserving opaque
bytes. No render-time reconstruction or default legacy fallback is added.

The same no-legacy actual-App test now passes, extended with real rendering,
48 link checks and a direct environmental damage-to-debris test:

```text
boss_physical_ownership=ok initial_cursor_byte_differences=0 coordinate_mismatches=0 animation_byte_mismatches=0 ticks=8 physical_links=48 rendered_frames=2 frame_changed=1 death_conversions=7 damage_calls=23 damage_injected=1 legacy_adapter=0 actual_App_helpers=1 natural_route=0 original_comparison=0
```

Two fresh C++ images were visually inspected: the original boss sprites are
visible and change pose/position after eight helper ticks through the physical
renderer. The camera is explicitly controlled. These images are not an
aligned original/C++ pixel comparison or a natural boss encounter.

Validation of the candidate:

- Complete fresh Linux CMake App build, followed by 28 passing focused CTests,
  including the actual-App owner test and 15 existing boss/GRAN regressions.
- 24 original-backed complete-state cases match both the pure loader and the
  production `ActorSlots` wrapper (75,600 compared storage bytes).
- Strict GCC C++23 and native MSVC `/std:c++latest /W4 /WX /O2` original replays
  pass. AddressSanitizer and UndefinedBehaviorSanitizer pass with parser,
  capacity, callback, identity and sparse-owner-write controls.
- Eight separately compiled faults are detected: lost raw record, actor-order
  visuals, unrebased segment timer, wrong group owner, unrebased link target,
  wrong animation mode, shifted descriptor and inactive-tail corruption.
- Fixture controls reject changed/missing/unreadable assets and producer
  sources, protect authenticated inputs and retain failed reports and existing
  exports. Frozen checkout and source guard self-tests pass.

The first broader source-use check rejected the literal header name
`gameplay/gran_group.hpp` as a `gran_` member reference. The guard now excludes
actual include directives; a new same-file unauthorized data-access control
still fails. This is not a new live-consumer exemption. Native Windows frozen
checkout checks cover 13 families, 45 files and 13 CRLF rejection controls.

The existing original boss replays use their declared seeded/legacy path;
they guard typed behavior but do not establish default physical ownership.
The separate no-legacy App test establishes that bounded ownership behavior,
not a natural victory or original full-frame timing. Physical link evolution
after debris conversion remains unproved: the typed link helper ignores dead
boss targets. Complete boss actor-body instruction recovery, natural input,
continuous clock/frame integration and whole-game parity remain open.

The merge blocker on #429/#439 is not cleared by these local results alone.
The repair must be integrated, reviewed at the current head and pass the full
required hosted suites before those integration heads are merged.
