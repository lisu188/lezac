#pragma once
#include "resources/sound.hpp"
#include <array>
#include <cstddef>
#include <cstdint>

namespace lezac::sound {
using resources::kSoundStepSize;

inline constexpr int kAudioSampleRate = 22050;
inline constexpr int kAudioToneSamples = kAudioSampleRate / 28;
inline constexpr uint16_t kSoundStopPeriod = 0x7530;
inline constexpr uint16_t kDirectSoundThreshold = 0xea60;
inline constexpr uint16_t kDirectSoundPeriodBase = 0xea42;
inline constexpr std::array<uint16_t, 4> kExplosionDirectSweepSoundOffsets{
    0xea74, 0xea7e, 0xea88, 0xeace,
};
inline constexpr std::array<uint8_t, 4> kExplosionSoundSelectors{4, 5, 6, 7};
inline constexpr uint16_t kBombPlaceSoundCursor = 0xea74;
inline constexpr uint8_t kBombPlaceSoundPriority = 3;
inline constexpr uint16_t kMonsterDeathSoundCursor = 0x003d;
inline constexpr uint8_t kMonsterDeathSoundPriority = 12;
// Level-7 boss head roar: original sets DS:0x2074=0x69, DS:0x799f=4 behind a
// ~30% RNG gate at 1000:5E59..5E8C in the 1000:5CB0 head routine.
inline constexpr uint16_t kBossHeadRoarSoundCursor = 0x0069;
inline constexpr uint8_t kBossHeadRoarSoundPriority = 4;
inline constexpr std::array<uint16_t, 6> kCompatibilitySoundCursors{
    0x0000, 0x0008, 0x0012, 0x001a, 0x0021, 0x0027,
};
inline constexpr size_t kCompatibilityObjectivePickupSound = 0;
inline constexpr size_t kCompatibilityLevelCompleteSound = 5;
inline constexpr size_t kObjectivePickupCompatibilityHookSlot = 0;
inline constexpr size_t kLevelCompleteCompatibilityHookSlot = 1;
// Diagnostic-only latch seed: a pending selector no captured hook priority can
// outrank, used to show the hooks really go through the priority latch.
inline constexpr uint8_t kCompatibilityLatchRejectionSeedPriority = 0xff;
struct RemainingSoundCompatibilityHook {
    const char* hook;
    size_t index;
    const char* captureBlocker;
    // Cursor/priority the ORIGINAL latches for this hook, captured live from
    // DOSBox by sampling the accepted sound pair (cursor DS:0x78C0, priority
    // DS:0x799E -- DS:0x2074/0x799F are the pending scratch, which many
    // routines write). objective_pickup was sampled at the exact tick the
    // objective counter DS:0x2088 went 0->1; level_complete at the tick the
    // completion flags derived, and it also matches the static banner
    // routine at file 0x250c..0x2517 (mov [2074],0x3d / mov [799f],0xa).
    uint16_t capturedCursor;
    uint8_t capturedPriority;
};
inline constexpr std::array<RemainingSoundCompatibilityHook, 2> kRemainingSoundCompatibilityHooks{{
    {"objective_pickup", kCompatibilityObjectivePickupSound,
     "rejected_static_candidates", 0x0000, 3},
    {"level_complete", kCompatibilityLevelCompleteSound,
     "no_static_candidate", 0x003d, 10},
}};
struct RejectedSoundCandidate {
    uint16_t offset;
    const char* reason;
};
inline constexpr std::array<RejectedSoundCandidate, 3> kRejectedObjectiveSoundCandidates{{
    {0x4b2c, "collapse_playback"},
    {0x6d75, "bomb_object_high_gate"},
    {0x6924, "non_objective_tile_gate"},
}};
inline constexpr uint16_t kEndFlowDispatcherStart = 0x1b14;
inline constexpr uint16_t kEndFlowDispatcherRet = 0x1d42;
struct StaticSoundContext {
    uint16_t offset;
    uint16_t cursor;
    uint8_t priority;
    const char* context;
};
inline constexpr std::array<StaticSoundContext, 5> kRecordUiSoundContexts{{
    {0x1857, 0x0078, 11, "name_entry_region"},
    {0x1a44, 0x0008, 11, "name_entry_region"},
    {0x1d9c, 0x003d, 10, "post_end_flow_record_region"},
    {0x202d, 0x0021, 0, "record_table_region"},
    {0x2083, 0x0024, 2, "record_table_region"},
}};
struct RuntimeSoundCaptureTarget {
    const char* scenario;
    uint16_t offset;
    uint16_t cursor;
    uint8_t priority;
    const char* region;
    const char* label;
    const char* status;
    const char* routeClass;
    const char* captureBlocker;
    const char* bytes;
};
inline constexpr std::array<RuntimeSoundCaptureTarget, 4> kActorContactSoundCaptureTargets{{
    {"actor_update_runtime_cursor_0024_sound", 0x6844, 0x0024, 2,
     "actor_update", "cursor_0024_priority2", "staged", "natural",
     "normalized_fixture_required",
     "c7 06 74 20 24 00 c6 06 9f 79 02 e8 08 ae"},
    {"actor_update_runtime_cursor_0035_sound", 0x6924, 0x0035, 5,
     "actor_update", "launch_pad", "staged", "natural",
     "level6_route_required",
     "c7 06 74 20 35 00 c6 06 9f 79 05 e8 28 ad"},
    {"actor_update_runtime_cursor_0021_sound", 0x7386, 0x0021, 1,
     "actor_update", "cursor_0021_priority1", "staged", "natural",
     "semantic_event_unknown",
     "c7 06 74 20 21 00 e8 cb a2"},
    {"contact_scanner_runtime_sound", 0x5e81, 0x0069, 4,
     "contact_scanner", "cursor_0069_priority4", "seeded_only",
     "runtime_seeded", "shipped_actor_modes_exclude_6",
     "c7 06 74 20 69 00 c6 06 9f 79 04 e8 cb b7"},
}};
inline constexpr std::array<uint16_t, 14> kDebugSoundCursors{
    0x0000, 0x0008, 0x0012, 0x001a, 0x0021, 0x0024, 0x0027,
    0x002d, 0x0031, 0x0035, 0x003d, 0x0056, 0x0069, 0x0078,
};
inline constexpr std::array<uint16_t, 15> kExpectedSoundStopCursors{
    0x0005, 0x0008, 0x0012, 0x001a, 0x0021, 0x0024, 0x0027, 0x002d,
    0x0031, 0x0035, 0x003d, 0x0056, 0x0069, 0x0078, 0x0082,
};
inline constexpr uint16_t kBombObjectDefaultSoundCursor = 0x0000;
inline constexpr uint16_t kBombObjectHighSoundCursor = 0x0012;
inline constexpr uint8_t kBombObjectSoundPriority = 3;
inline constexpr uint8_t kBombObjectHighSoundThreshold = 0x6c;
inline constexpr uint16_t kPortalTeleportSoundCursor = 0x001a;
inline constexpr uint8_t kPortalTeleportSoundPriority = 4;
inline constexpr uint16_t kTileTriggerSoundCursor = 0x0027;
inline constexpr uint8_t kTileTriggerSoundPriority = 6;
inline constexpr uint16_t kBonusPickupSoundCursor = 0x0008;
inline constexpr uint8_t kBonusPickupSoundPriority = 5;
inline constexpr uint16_t kRecordNamePromptSoundCursor = 0x0078;
inline constexpr uint8_t kRecordNamePromptSoundPriority = 11;
inline constexpr uint16_t kRecordNameCommitSoundCursor = 0x0008;
inline constexpr uint8_t kRecordNameCommitSoundPriority = 11;
inline constexpr uint16_t kRecordsPageSoundCursor = 0x0024;
inline constexpr uint8_t kRecordsPageSoundPriority = 2;
inline constexpr uint16_t kWeaponSwitchSoundCursor = 0x0024;
inline constexpr uint8_t kWeaponSwitchSoundPriority = 2;
inline constexpr uint16_t kLaunchPadSoundCursor = 0x0035;
inline constexpr uint8_t kLaunchPadSoundPriority = 5;

struct SoundLatch {
    bool active = false;
    uint8_t currentSelector = 0;
    uint16_t latchedOffset = 0;
    size_t recordIndex = 0;
    bool directSweep = false;
};

struct CompatibilitySoundAttempt {
    size_t index = 0;
    uint16_t cursor = 0;
};

struct SoundPlaybackSnapshot {
    int record = -1;
    uint16_t offset = 0;
    uint8_t selector = 0;
};

}  // namespace lezac::sound
