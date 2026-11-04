# Original Level 4 Cavity Bomb

The permanent regression covers ordinary gameplay from tick 13700 through
14700 inclusive: 1,001 complete 320x200 RGB frames and 2,002 present/post-update
observations. It follows startup, completion of levels 1, 2 and 3, and entry
into level 4. The native frame offset is 1623. Initial RNG control and
normalized ordinary control-bank inputs are disclosed; there are no injected
terrain, inventory, health, position or destruction values.

This is the left-cavity continuation with left+jump at route tick 13702,
right+jump at 13902, fire at 14502 and escape at 14505. It is not the distinct
route-planning candidate that fires at 13702. C++ planning supplied input
choices only; all expected state and RGB fingerprints come from the original.

## Declared Bomb Projection

In addition to the existing mapped/lifecycle/monster/marker/terrain projection,
the comparison includes original actor kind, countdown byte, pixel X/Y, signed
X/Y velocity, fractional X/Y words and behavior byte for each bomb in actor
order. It excludes owner, visual descriptor bytes, hotspot and unused/stale
actor bytes. This is not a complete actor-record model.

`bomb_state_projection.py` decodes original DS records directly. The C++ fuse
maps to the original counter as `(remaining + 1) // 2`; fuse lengths and moving
behavior are checked before comparison. Fourteen synthetic mutation controls
cover the declared values and native actor/visual bounds. Synthetic records
are test stimuli, never original expected bytes.

The original bomb first appears at tick 14503 post-update: kind 14, counter 30,
pixel `[210,360]`, velocity `[0,-500]`, zero fractional words, behavior 2.
Its final observed boundary is tick 14562 present with counter 1. There are
118 bomb-present boundaries. The medium-bomb inventory changes from four to
three at its birth. Subsequent destruction credits reach 280 at tick 14683.

At the final tick the original has 280 of the 305 required destruction credits,
22 energy, zero reserve lives, inventory `[200,3,0,0,1]`, position `[13,360]`
and RNG 1114144943. Twenty-five more credits are needed. This does not establish
level-four completion or level-five entry.

## Original Evidence

The unchanged 52,384-byte executable has SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The fixture binds the actual DOSBox host, launch arguments, working directory,
geometry, configuration, resident loader, copied/canonical assets, observer
source and silent audio environment. Owned-child termination and restored
hooks are checked. The independently audited capture is complete for the
requested interval and agrees with the preceding original session at both
tick-13700 boundaries.

All 4,016 private compressed DS/boundary members, including entry checkpoints,
were re-read in full, decoded, and checked for exact byte length and SHA-256
against their pre-compression receipts. The private compressed backups are
retained on C: under the user's explicit instruction. Raw DS snapshots, full
guest RAM and screenshots are not published. The committed bundle contains
only projected observations, RGB fingerprints, compact provenance, receipts
and frozen producer source. The packer has no C++ expectations input.

The permanent regression checks SHA-256 over each complete RGB frame, plus the
trace's own FNV checksum. It does not claim a literal RGB byte comparison
against publicly retained image files, because those files are private. The
preceding private Linux/Windows validation additionally compared all RGB bytes
directly. Both lanes cover all 1,001 frames, not just bomb-present frames.

Actual REA 6.7 with Ghidra 12.1.4 on WSL checked 34 selected instruction byte
sequences against the original MZ image. The constructor path includes the call
at `1000:6C5B` to `1000:2F9F`; expiry includes the call at `1000:75FB` to
`1000:414A`. `1000:75F1` is `SUB AX,0x0c`, not that call. Target identity,
server termination and session cleanup are retained. These bounded checks are
not whole-program equivalence evidence.

## Regression Integration

The CTests are `natural_level4_cavity_bomb_original`,
`natural_level4_cavity_bomb_guard` and `natural_level4_cavity_bomb_fixture`.
The fixture suite is also included in the Python 3.12/3.15 Windows/Linux matrix.
Twelve new test methods cover original/source/provenance mutations, missing or
changed pinned files, canonical-asset failure reports, bomb controls, strict
four-phase parsing and failed/timed-out replay output retention.

`natural_route_window.py` shares the existing strict left-return trace parser
with this regression. It validates all four phases, events, timing, sequence,
headers/footers and full-frame fingerprints. The existing left-return suite
remains a separate regression for this extraction.

No C++ source or gameplay behavior changes in this delivery. The production
source tree remains `8d059cdd61dce9a9af207cb7e07c879d6f843a84`. All launches are
silent. Automated replay is not physical-keyboard, wall-clock or owner visual
acceptance. Whole-game fidelity, full actor-record fidelity and clearance of
the held actor-pass stability findings remain explicitly unclaimed.

## Local Validation

- Fresh GCC 13.3 C++23 Release and native MSVC builds succeed. Each native App
  matches all 1,001 complete RGB fingerprints, 2,002 projected boundaries and
  4,004 trace checkpoints, with nine bomb fields compared. This is 64,064,000
  pixels per platform, with zero detected differences.
- The live Windows process loaded the SDL2.dll beside the new executable;
  its SHA-256 is `b37740a72a7a9706216df9f0134894bb7a850b356fd149398c67d874cbcfacb4`.
- Twelve new fixture/parser tests pass on Linux Python 3.12 and native Windows
  Python 3.12.14 and 3.15.2. The existing ten left-return tests also pass on
  both native Windows versions.
- The three new CTests pass, including the full-window single-launch replay.
- Twelve adjacent CTests pass, including the complete 1,761-frame left-return
  replay and its 3,522 projected boundaries, plus fuse/motion/visual/launch/order
  and capture-contract regressions. Four guard/fixture CTests are repeated
  after the final strict numeric-domain controls.

Hosted checks remain a separate lane and are not inferred from these results.
