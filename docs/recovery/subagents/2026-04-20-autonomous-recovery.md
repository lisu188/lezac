# Autonomous Recovery Subagents - 2026-04-20

This pass used real read-only subagents and integrated their findings into a
single local patch.

## A - Ghidra/Disassembly Mapper

Ghidra was not available locally (`analyzeHeadless` and `ghidraRun` were not on
`PATH`). The subagent used MZ header math and `objdump -b binary -m i8086`
windows instead. Confirmed main code file offsets use:

```text
file_offset = 0x770 + address_offset
```

Key findings:

- Actor update candidate: `1000:6053..777f` (`0x67c3..0x7eef`).
- Player control branch: `1000:66f3..6b55`.
- Bomb placement: `1000:6bdf..6cb3`.
- Behavior `4` movement: `1000:7018..714f`.
- Behavior `3` ground walker: `1000:7159..732c`.
- Exact 8.8 integration anchor remains `1000:73e5..741b`.
- Sound request/priority latch: `1000:165a`, using globals `0x799e`,
  `0x799f`, `0x79c4`, and `0x78c0`.
- Record load/name-entry/end flow: `1000:16da..1d42`, with name-entry
  evidence at `1000:1845..1ad4`.

Integrated this pass:

- Record-entry keys now follow the `1000:1845..1ad4` evidence for letters,
  space, lowercase storage, Backspace, and Enter. Later tightening also pins
  the routine's eight-colon initial name template, so an untouched prompt writes
  raw `::::::::` and a typed `nessuno` remains distinct as `nessuno:`.

## B - Gameplay Fidelity

Highest-impact finding: destruction completion was using visible tile ids as
the denominator. `fieldB` in each level header exactly matches the nonzero
low-word physical-damage cell count and is the better original-progress anchor.

Integrated this pass:

- `startingDestructibleTiles` now comes from the low word-layer count and is
  checked against `fieldB`.
- Low-word collapse groups advance `destroyed_`; high-word debris, bomb object
  consumption, and tile triggers do not directly advance physical destruction.
- Smoke completion now damages low-word groups instead of arbitrary visible
  tiles.

## C - Rendering/Audio/Assets

Highest-confidence rendering finding: original transparent blit at `18ac:00f4`
treats only index `0` as transparent. The C++ sprite renderer also skipped
`0xff`, even though shipped sprite banks contain visible `0xff` pixels.

Integrated this pass:

- `drawSprite()` now draws palette index `0xff`.
- `--debug-sprite-transparency` validates that shipped sprite banks exercise
  those pixels: 104 in `BOMOMIMK.SPR`, 114 in `PROVA.SPR`, and 151 in
  `FONTS.SPR`.

Open asset/audio follow-ups:

- Generate sprite transparency/contact-sheet manifests.
- Map likely `PROVA.SPR` panel/effect art around indices `39..46`.
- Export `PROEFS.SON` five-byte groups and `GRAN.MST` word tables.

## D - Verification/Test Harness

Highest-value test gap: the runtime used converted JSON resources without a
CTest guard proving that the original binary `LIVELS.SCH` parser still matches
the JSON.

Integrated this pass:

- `--debug-level-raw-roundtrip` parses original `LIVELS.SCH` directly and
  compares all scalar fields, decoded layers, spawners, portals, and triggers
  against `src/LIVELS.SCH.json`.
- CTest now runs `level_raw_roundtrip`.

## E - Integration/Docs

Findings:

- Runtime resources are converted JSON files, but README still implied raw
  asset files were loaded at runtime.
- CTest coverage is broader than the README wording.
- `docs/recovery/` and `RECOVERY_STATUS.md` were missing.
- `src/main.cpp` remains a maintainability risk as the all-in-one translation
  unit.

Integrated this pass:

- Added `RECOVERY_STATUS.md`.
- Added this subagent notes file.
- Refreshed README and `docs/GHIDRA_NOTES.md` wording for JSON resources,
  debug coverage, sound playback status, physical destruction progress, raw
  level roundtrip, record entry, and transparency.
