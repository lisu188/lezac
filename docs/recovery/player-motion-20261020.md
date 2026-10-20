# Original Player Motion Recovery

## Scope

PlayerMotionOperation executes the original player body at 1000:6737 through
the jump to 1000:732C, stopping before common terrain response and integration.
It also recovers ammunition-cap helper 5715..573D and portal helper 5999..5A72.
The 899 original instruction sites in these intervals are present and executed
by the controlled corpus. Existing recovered contact, terrain, constructor,
animation-copy and timer operations supply nested work on the same borrowed
memory bus and live SS. No private stack reset or memory reconciliation occurs.

The body includes gravity, ground snapping and bounce, input cancellation,
weapon switching and bomb construction, portal/down/launch-pad decisions,
walking and jumping, animation state, objective/fracture scans, health and
ammunition pickups, score carry, shared RNG/scratch work, and flame impulses.
Instruction grants, partial copies and serializable continuation state retain
the existing recovered-operation contracts.

This does not integrate the new operation into the production App. Common
terrain work at 732C, the actor tail/return, whole-frame scheduling, a natural
campaign and full-frame pixels remain separate obligations.

## Original Evidence

Two independent final producer runs (F and G) produced byte-identical manifests,
compressed projections and checkpoint metadata from the unchanged executable.
All 12 declared inputs (the executable and 11 producer modules) and the actual
mapped Unicorn 2.1.4 native library are authenticated before and after capture.

| Item | Value |
| --- | --- |
| LEZAC.EXE bytes | 52,384 |
| LEZAC.EXE SHA-256 | 7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec |
| Unicorn library SHA-256 | ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c |
| Controlled cases | 7,028 |
| Actual player caller cases | 24 |
| Original player instruction sites executed | 899 |
| Register states | 3,561,155 |
| Ordered memory writes | 673,658 |
| Terrain endpoints | 7,024 |
| Original runtime-error endpoints | 4 |
| Raw projection bytes | 49,667,615 |
| Raw projection SHA-256 | 8a222f50144d047d8be896713bf68a4e854af3519d4656f79646ffdef9f70715 |
| Compressed projection bytes | 1,823,471 |
| Compressed projection SHA-256 | 127f9730f92ad487d2a7434fb07e99e94a470c577acf85c3154e815dd9794ec9 |
| Manifest SHA-256 | f1abc2dba73cb264db2d8bd0c9f1aaa5640b4f4c1939b7fd35cee67abcab1ffc |

The 24 caller cases execute 7EBB, the actual player CALL at 7F59, actor entry
6053, tile flags and player entry 6737. Both player records are seeded at their
actual caller-owned addresses, not merely labeled as player cases.

Observed and unobserved executions have identical complete 1 MiB memory,
endpoint registers and outcomes. Ordered writes reconstruct all changed memory.
All 43,552 relocated original code bytes remain unchanged. There are no patched
instructions, stubbed calls, hardware I/O, delivered interrupts or later state
injections in this original corpus. Initial data and stack state are controlled;
these are not natural gameplay captures. The published stream contains compact
initial differences, register traces and writes, not full RAM dumps.

## Validation

- All 7,028 cases pass nine grant/copy combinations: budgets 1/17/4096 and copy
  limits 1/2/all. This gives 63,252 replays, 11,362,915 register comparisons and
  31,847,211 player-operation dispatches. All ordered writes, complete final
  memory and all endpoint flags match.
- Intermediate arithmetic flag bits masked by 0x08D5 follow the existing parent
  comparator. Other intermediate flags and all endpoint flags are compared.
  This is not an exact-every-intermediate-flag claim.
- Thirteen computed C++ IRQ continuation boundaries dispatch 468 IRQ
  instructions, restore registers and advance the BIOS tick 100 to 101. One
  interrupts an actual one-byte partial copy. Snapshot forks resume identically;
  nested, masked and terminal IRQ admissions are rejected. These controls do not
  reproduce or establish an original IRQ schedule.
- Nine invalid-state controls, a wrong-entry control and zero-budget/terminal
  no-work checks pass.
- Twelve successfully compiled semantic faults are rejected: gravity, landing
  threshold, drop height, walking acceleration, super bomb, pickup energy,
  score carry, portal mask, byte-wrapping ammunition, terminal ownership, IRQ
  delivery and snapshot flags. The production and test sources stay unchanged.
- The initial score-carry mutant escaped an earlier matrix. Twelve explicit
  pickup-overflow cases (both players, pickups 1..6) were added, then both final
  original captures and all mutations were rerun. Earlier evidence is retained.
- Self-review reproduced a standalone replay accepting a changed MZ even though
  the Python gate authenticated canonical inputs. The C++ verifier now checks
  exact MZ length and FNV-1a fingerprint before relocation. Cryptographic SHA-256
  authentication remains in the fixture gate. The changed-MZ control now fails
  normally with "Player MZ fingerprint differs".
- Eight CLI negative controls reject missing/extra arguments, unavailable
  fixture/MZ, a changed MZ, and truncated/changed/extra-tail projections without
  modifying protected inputs.
- Fixture tests cover changed, missing and directory-replaced canonical inputs,
  manifest and gzip; failed reports and mismatching exports are retained.
- The final Linux batch passes all 31 focused CTests, including adjacent
  nonplayer, animation, boss, timed-writeback, reward and ledge regressions.
  Source guardrails pass 20 controls with 165 mapped sources.
- Strict GCC C++23 builds pass. ASan/UBSan unit and full-corpus runs pass.
  Native MSVC /std:c++latest /W4 /WX passes the final build, unit, full original
  replay and eight CLI controls. Native fixture rejection tests and frozen
  cold-checkout validation also pass (26 families, 85 files, 26 CRLF controls).
- A fresh silent live-App boss ownership checkpoint reports zero coordinate or
  animation-byte mismatches over 8 ticks/48 links and renders two frames. Its
  damage/camera state is controlled; it does not exercise this new player core.
  The after-frame RGB SHA-256 is
  15e9811c9084c5065530269e8b8772b4bbdd55fd7c50403972c0bf967cf53e89.

All local artifacts remain in RAM under the user's disk-pressure exception.
No system speaker output is enabled.

## Delivery And Remaining Work

Frozen player files are binary-safe in .gitattributes and included in the cold
checkout policy. CMake runs fixture authentication, original replay, CLI,
rejection and mutation checks without depending on Unicorn during normal CI.

The Linux whole-job allowance changes from 150 to 180 minutes, matching Windows.
The previous parent ran all 1,160 tests successfully but was cancelled at the
150-minute job limit. No test command, per-test threshold or comparator is
weakened. Full exact-head CI and external review remain delivery gates.

Next, compose the recovered player caller/body with common terrain and actor
finish/return on the production owners and shared bus/work clock. Then compare
natural original and C++ complete frames and their schedules. This recovery is
not whole-game equivalence, a natural boss route or owner visual acceptance.
