# Larax & Zaco (LEZAC) — Recovery Project

An evidence-driven recovery/reimplementation project for the 1996 DOS game **Larax & Zaco v1.0** (also known by its executable name, `LEZAC.EXE`). The current work focuses on reconstructing gameplay behavior in C++/SDL and validating it against the original program and data.

## Engineering focus

- native C++ reconstruction of original game behavior
- SDL-based runtime
- deterministic autoplayer scenarios for regression testing
- headless execution with SDL dummy drivers
- frame-sequence capture for visual evidence
- decoded/structured representations of original resource formats
- behavior-focused comparison against the DOS original

See `AGENTS.md` for the current deterministic scenarios and validation workflow.

## Original game provenance

The included original `ENGLISH.DOC` identifies the game as:

- **Larax & Zaco v1.0**
- **Zanobi Software**
- released **April 23, 1996**
- original game materials marked **all rights reserved**

That document states that the shareware game may be used, copied and distributed freely provided that no fee is charged and every original file is copied in its original form.

The original executable, data, graphics, sound and documentation in this repository are **not claimed as my work**. Their original copyright and distribution terms remain with their author/rightsholder. The recovery/reimplementation code and analysis should be evaluated separately from those original materials.

## Public-repository caution

Before redistributing or packaging the original shareware material independently, verify that the complete original file set is present and that the distribution still satisfies the conditions stated in `ENGLISH.DOC`. Do not treat the reconstructed source code and the original game assets as having one common license.

## Status

Active reverse-engineering/reimplementation research. This repository is useful as engineering evidence, but `clash-disassembly` and `clash-hd` currently provide cleaner examples of a fully documented public reverse-engineering workflow.
