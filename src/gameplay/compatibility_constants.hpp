#pragma once
#include <array>
#include <cstdint>
#include <cstddef>
#include "resources/gran.hpp"
namespace lezac::gameplay {
constexpr uint16_t kDamagedWordBit = 0x8000;
constexpr uint16_t kDeferredThreshold = 0x4000;
constexpr uint16_t kHighHalfBase = 0x4e20;
constexpr size_t kDebrisStride = 0x0b;
constexpr size_t kCollapseStride = 0x0f;
constexpr uint16_t kDamageForwardLookupRoutine = 0x3a7e;
constexpr uint16_t kDamageReverseLookupRoutine = 0x3b18;
constexpr uint16_t kDamageForwardPassRoutine = 0x3bb2;
constexpr uint16_t kDamageReversePassRoutine = 0x3d46;
constexpr uint16_t kExplosionEffectUpdateRoutine = 0x45fa;
constexpr uint16_t kHighDebrisTargetSample = 0x4b3f;
constexpr uint16_t kHighDebrisTargetByteGate = 0x4b61;
constexpr uint16_t kHighDebrisZeroTargetBranch = 0x4b6a;
constexpr uint16_t kHighDebrisNonzeroTargetBranch = 0x4c20;
constexpr uint16_t kHighDebrisWordLoad = 0x4c64;
constexpr uint16_t kHighDebrisWordGate = 0x4c75;
constexpr uint16_t kHighDebrisWordGateSkip = 0x4cae;
constexpr uint16_t kExplosionEffectForwardCall = 0x4c96;
constexpr uint16_t kExplosionEffectForwardReturn = 0x4c99;
constexpr uint16_t kExplosionEffectReverseCall = 0x4ca9;
constexpr uint16_t kExplosionEffectReverseReturn = 0x4cac;
constexpr uint16_t kHighDebrisLaneTargetOffsetGlobal = 0x659a;
constexpr uint16_t kHighDebrisLaneWordGlobal = 0x655e;
constexpr uint16_t kHighDebrisLaneUpdateFlag = 0x2078;
constexpr uint16_t kLaneHelperStagingWordBase = 0x655c;
constexpr uint16_t kLaneHelperStagingTargetBase = 0x6598;
constexpr uint16_t kLaneHelperStagingTagBase = 0x65d4;
constexpr uint16_t kLaneHelperSelectorGlobal = 0x2074;
constexpr uint16_t kLaneHelperDebrisCountGlobal = 0x207e;
constexpr uint16_t kLaneHelperCollapseCountGlobal = 0x2080;
constexpr uint16_t kLaneHelperNeighborLaneScratch = 0x661e;
constexpr uint16_t kLaneHelperCollapseWeightBase = 0x661f;
constexpr uint16_t kExplosionEffectForwardInputGlobal = 0x78d2;
constexpr uint16_t kExplosionEffectReverseInputGlobal = 0x78d4;
constexpr uint16_t kCollapseForwardLaneBase = 0x6617;
constexpr uint16_t kCollapseReverseLaneBase = 0x6618;
constexpr uint16_t kDebrisForwardLaneBase = 0x2097;
constexpr uint16_t kDebrisReverseLaneBase = 0x2098;
constexpr uint8_t kCollapseForwardLaneRecordOffset = 0x06;
constexpr uint8_t kCollapseReverseLaneRecordOffset = 0x07;
constexpr uint8_t kCollapseWeightRecordOffset = 0x0e;
constexpr uint8_t kDebrisForwardLaneRecordOffset = 0x04;
constexpr uint8_t kDebrisReverseLaneRecordOffset = 0x05;
constexpr uint16_t kLaneHelperBlendFarSegment = 0x0920;
constexpr uint16_t kLaneHelperBlendFarOffset = 0x0945;
constexpr uint16_t kLaneHelperBlendZeroDivisorOffset = 0x09ac;
constexpr uint16_t kLaneHelperBlendZeroDivisorError = 0x00c8;
constexpr size_t kDebrisCapacity = 0x640;
constexpr size_t kCollapseCapacity = 0x00fa;
// Falling-debris mover constants (1000:45FA loop 2 / seeder 1000:370E; every
// citation re-read from LEZAC.EXE at ghidra_addr + 0x770 — see
// docs/recovery/falling_debris_update_spec.md).
constexpr size_t kDebrisRecordIndexBase = 0x00c7;  // DS:207E init (file 0x3319);
                                                   // inc-before-imul at 3783 makes
                                                   // the first record slot 200, and
                                                   // the 3753 cap check refuses when
                                                   // DS:207E >= kDebrisCapacity.
constexpr int8_t kDebrisGravityCompare = 0x7b;     // 4AA3 cmp vy,0x7b (signed jge)
constexpr int8_t kDebrisGravityStep = 4;           // 4AAA add vy,4
// 4CFF equality check after the byte increment: clear the map flag and erase
// the live record at 100. Stale tail bytes are not cleared by the original.
constexpr uint8_t kDebrisRestRetireTicks = 0x64;
constexpr uint8_t kDebrisShatterFrame = 0x76;      // 49B0/4B16 first shatter frame
constexpr uint8_t kDebrisShatterLastStep = 0x79;   // 49DC terminal-frame trigger
constexpr uint8_t kDebrisTerminalBase = 0x6b;      // 49EF add ax,0x6b (+Random(5))
constexpr uint8_t kDebrisDissolveByte = 0xff;      // 49F7 terminal / 4A23 consume
constexpr uint16_t kDebrisFragileWordFloor = 0xffbc;  // 49A4/49E2 cmp fw,0xffbc (ja)
constexpr int8_t kDebrisLandingShatterVyGate = 0x3c;  // 4AED cmp vy,0x3c (jle skips)
constexpr uint16_t kDebrisAutoShatterSoundCursor = 0x27;   // 49BD, priority 5 (49C3)
constexpr uint8_t kDebrisAutoShatterSoundPriority = 5;
constexpr uint16_t kDebrisLandingShatterSoundCursor = 0x21;  // 4B2C, priority 2 (4B27)
constexpr uint8_t kDebrisLandingShatterSoundPriority = 2;
constexpr uint16_t kDebrisBounceSoundBase = 0xea61;  // 4C51 add ax,0xea61, priority 1
constexpr uint8_t kDebrisBounceSoundPriority = 1;    // 4C57
using lezac::resources::kGranRecordSize;
constexpr int kDeathStateTicks = 0x003c;
constexpr int kReentryTicks = kDeathStateTicks;  // Raw actor countdown, not a reentry timeout.
constexpr uint8_t kSharedReentryTicks = 0xe6;  // 1000:7EFC compares DS:79B9 with 230.
// UNEVIDENCED port policy (@unevidenced:damage_cooldown_ticks): no byte citation and no
// capture fixes it. Left at its pre-governed-loop value, so its wall-clock
// duration changed from ~0.30 s to ~0.73 s when the live loop was governed.
constexpr int kDamageCooldownTicks = 18;
// The original kind-1 kill trace holds sprite 47 for DS:78C2 frames 263..311:
// 49 governed ticks. updateMonsters runs after bomb damage in the same tick,
// so the death actor is initialized one count above the first externally
// visible value.
// Impact/corpse sprite per monster kind and direction, read from the bytes.
// At 1000:745B the original does `cmp WORD [bp-0xc],0 / jle` -- [bp-0xc] is
// vx -- taking dir = 1 when vx <= 0 and dir = 2 when vx > 0, then indexes
// `al = DS:[0x77 + kind*2 + dir]` and hands the result to the sprite-assign
// helper 1000:5A75. DGROUP (image base 0xAA20, anchored on the DS:0x8B
// "larax e zaco versione 1:0 shareware" string) holds
// DS:0x0077.. = 2c 28 28 30 31 2b 2b 35 35 39 39, so entries [1..10] give
// kind 0 -> 39/39, kind 1 -> 47/48, kind 2 -> 42/42, kind 3 -> 52/52,
// kind 4 -> 56/56 after the one-based -> file-sprite -1. Only kind 1 has a
// direction pair; the others are direction-independent.
// Two level-1 kill captures agree with the kind-1 entries (47 and 48, each
// held 49 ticks) but do NOT establish the discriminator: the walk band is
// selected from the same vx sign at 1000:7286/72DA, so band and velocity
// agree whenever vx != 0. They part company at vx == 0, where the original
// takes dir = 1 unconditionally while the band keeps whatever it last had.
constexpr std::array<std::array<int, 2>, 5> kMonsterImpactSprites{{
    {{39, 39}}, {{47, 48}}, {{42, 42}}, {{52, 52}}, {{56, 56}},
}};
constexpr int kMonsterCorpseSpriteRight = 48;
// Minimum visible duration; fatal conversion on an odd frame adds one update.
constexpr int kMonsterDeathVisibleTicks = 49;
// The original's main loop is rate-governed: file offset 0x8089 holds 30
// frames in 120..125 hundredths of a second by dithering the delay word
// DS:0x78CC between 96 and 102 ms (step DS:0x78CA = 6), so the converged
// rate oscillates in a 24.2..25.2 fps band (see
// tests/fixtures/route_timing_original_level1.txt).  One update() call is
// one original game tick throughout this port, so the interactive loop must
// fire updates at that rate; kGovernedTickMs is a fixed value sitting
// mid-band rather than a reproduction of the dither.
// 40.83 ms is the midpoint of the byte-derived target itself: the governor
// at file 0x810A/0x812F holds 30 frames in 120..125 hundredths, i.e.
// 24.00..25.00 fps, whose midpoint period is (1200+1250)/2/30 = 40.83 ms.
// The 24.2..25.2 band below is what the DOSBox capture MEASURED, which sits
// slightly above the byte-derived band -- host timing overhead is the likely
// reason -- so the two are kept distinct rather than conflated.
constexpr double kGovernedTickMs = 40.8;
// Events are polled far more often than ticks so that key presses (handled
// edge-wise in processEvents/onKey) stay responsive between updates.
constexpr uint32_t kEventPollDelayMs = 4;
// Upper bound on ticks simulated in one pass after a stall, so a suspended
// window cannot fast-forward the level on resume.
constexpr int kMaxCatchUpTicks = 5;
// Acceptance band for the measured interactive tick rate: the original's
// governed 24.2..25.2 fps, widened by nothing — a loop paced any other way
// (the previous 16 ms/60 fps pacing, for instance) falls outside it.
constexpr double kGovernedRateBandMin = 24.2;
constexpr double kGovernedRateBandMax = 25.2;
// A wall-clock measurement on a loaded host can only ever lose ticks, never
// gain them: once a stall exceeds the catch-up cap the missed ticks are
// dropped for good. So the measured rate is held to the band's ceiling
// exactly — that is the bound a too-fast loop (the old 16 ms/60 fps pacing
// yields ~60) violates — while the floor carries slack for host scheduling.
constexpr double kGovernedRateMeasuredFloor = 22.0;
// Worst tolerated wall-clock gap between two gameplay ticks. One governed
// tick is 40.8 ms; this allows a little over two, so ordinary scheduling
// jitter passes while a loop that batches ticks and sleeps does not.
constexpr long kGovernedMaxTickGapMs = 90;
constexpr uint32_t kLevelIntroCharacterDelayMs = 81;
constexpr int kLevelIntroCellAdvance = 11;
constexpr int kLevelIntroTextY = 94;
constexpr uint8_t kLevelIntroPaletteFirst = 176;
constexpr size_t kLevelIntroPaletteCount = 7;
constexpr uint8_t kWeaponSwitchHoldTicks = 5;
constexpr uint8_t kLaunchPadTile = 0x27;
constexpr int16_t kOriginalNormalJumpVelocity = -848;
constexpr int16_t kOriginalLaunchPadVelocity = -2000;
// Tick-locked original measurements (frame counter DS:0x78C2, /proc/mem):
// the governed game rate is 24-25 fps (main-loop governor at file 0x8089
// holds 30 frames in 120..125 hundredths), the walk speed is a flat
// 4 px/tick and the jump is 8.8 fixed-point (v0 = -848, gravity +64/tick,
// floor-to-pixel -- every observed per-tick delta reproduces exactly).
//
// The player runs that model directly, the same way every other moving thing
// in this port does. An earlier revision approximated it with a continuous
// px/s model (98 px/s launch, 200 px/s^2 gravity); those numbers reproduced
// the 24 px PEAK but not the arc, because 98 was derived from the walk speed
// rather than from the jump: -848/256 is -3.3125 px/tick = -81 px/s, and
// 64/256 is 0.25 px/tick^2 = 150 px/s^2. The peak agreed only by coincidence
// (98^2 / (2*200) = 24.01). The per-tick deltas did not.
constexpr int16_t kPlayerWalkVelocity8 = 0x0400;   // acceleration threshold, not a hard clamp
constexpr int16_t kPlayerWalkAcceleration8 = 0x0040;
constexpr int16_t kPlayerJumpVelocity8 = kOriginalNormalJumpVelocity;  // -848
constexpr int16_t kPlayerGravity8 = 64;            // +0x40 per tick
// The player-specific branch 1000:6743..6753 also explicitly clamps at
// 0x07ff. This is now byte-cited, not borrowed from monster gravity.
constexpr int16_t kPlayerTerminalVelocity8 = 0x07ff;
// Float mirror kept for the many call sites that read player.vy as a sign or
// magnitude; it is always vy8 / 256.
constexpr float kPlayerJumpVelocity =
    static_cast<float>(kOriginalNormalJumpVelocity) / 256.0f;
constexpr float kLaunchPadVelocity =
    static_cast<float>(kOriginalLaunchPadVelocity) / 256.0f;
constexpr uint16_t kPlayerDamageSoundCursor = 0x002d;
constexpr uint8_t kPlayerDamageSoundPriority = 4;
constexpr uint16_t kPlayerDeathSoundCursor = 0x0056;
constexpr uint8_t kPlayerDeathSoundPriority = 5;

// Facing anim-set pair table recovered from the shipped data segment
// (DS:0x58/0x59, image linear 0xAA20): boss sets 0x0e -> frames 41..42,
// 0x0f -> 43..44, and 0x10 -> 40..40, drawn from the PROVA.SPR bank that the
// original loads instead of BOMOMIMK.SPR on level 7 (selector 1000:2C90).
constexpr std::array<std::array<uint8_t, 2>, 17> kBossAnimSets{{
    {0, 0}, {0, 0}, {0, 0}, {0, 0}, {0, 0}, {0, 0}, {0, 0}, {0, 0},
    {0, 0}, {0, 0}, {0, 0}, {0, 0}, {0, 0}, {0, 0},
    {41, 42}, {43, 44}, {40, 40},
}};

inline constexpr int kBossVisualBase = 2;
}
