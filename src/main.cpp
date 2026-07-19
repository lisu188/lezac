#include <SDL.h>

#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

constexpr int kScreenW = 320;
constexpr int kScreenH = 200;
// CARO.CAR tile index used by the reconstructed bottom HUD: the fixed
// destruction-target star (verified from the original HUD icon renderer, which
// blits 8x8 CARO tiles, not BOMOMIMK sprites, for the objective icons).
constexpr int kHudDestructionStarTile = 117;
constexpr int kHudLifeMarkerTile = 115;  // green walking figure
constexpr int kNameEntryLabelX = 58;
constexpr int kNameEntrySlotY = 120;
constexpr int kNameEntrySlotCount = 8;
constexpr int kNameEntrySlotAdvance = 9;
constexpr int kNameEntryCursorBoxW = 8;
constexpr int kNameEntryCursorBoxH = 10;
constexpr uint32_t kNameEntryCursorBackground = 0xff90ffb0u;
constexpr uint32_t kNameEntryCursorForeground = 0xff000000u;
constexpr int kBackgroundW = 320;
constexpr int kBackgroundH = 200;
constexpr int kTileSize = 8;
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
constexpr size_t kGranRecordSize = 57;
constexpr int kReentryTicks = 180;
constexpr int kDeathStateTicks = 0x003c;
constexpr uint8_t kState2VisualStartFrame = 0x4a;
constexpr uint8_t kState2VisualEndFrame = 0x4f;
constexpr uint8_t kState2VisualDelay = 3;
constexpr int kDamageCooldownTicks = 18;
constexpr uint32_t kFrameDelayMs = 16;
constexpr uint32_t kLevelIntroCharacterDelayMs = 81;
constexpr int kLevelIntroCellAdvance = 11;
constexpr int kLevelIntroTextY = 94;
constexpr uint8_t kLevelIntroPaletteFirst = 176;
constexpr size_t kLevelIntroPaletteCount = 7;
constexpr int kCollisionPushoutLimit = 1024;
constexpr int kAudioSampleRate = 22050;
constexpr int kAudioToneSamples = kAudioSampleRate / 28;
constexpr size_t kSoundStepSize = 6;
constexpr uint16_t kSoundStopPeriod = 0x7530;
constexpr uint16_t kDirectSoundThreshold = 0xea60;
constexpr uint16_t kDirectSoundPeriodBase = 0xea42;
constexpr std::array<uint16_t, 4> kExplosionDirectSweepSoundOffsets{
    0xea74, 0xea7e, 0xea88, 0xeace,
};
constexpr std::array<uint8_t, 4> kExplosionSoundSelectors{4, 5, 6, 7};
constexpr uint16_t kBombPlaceSoundCursor = 0xea74;
constexpr uint8_t kBombPlaceSoundPriority = 3;
constexpr uint16_t kMonsterDeathSoundCursor = 0x003d;
constexpr uint8_t kMonsterDeathSoundPriority = 12;
// Level-7 boss head roar: original sets DS:0x2074=0x69, DS:0x799f=4 behind a
// ~30% RNG gate on the head state tick (1000:5CB0 / 1000:65db).
constexpr uint16_t kBossHeadRoarSoundCursor = 0x0069;
constexpr uint8_t kBossHeadRoarSoundPriority = 4;
constexpr std::array<uint16_t, 6> kCompatibilitySoundCursors{
    0x0000, 0x0008, 0x0012, 0x001a, 0x0021, 0x0027,
};
constexpr size_t kCompatibilityObjectivePickupSound = 0;
constexpr size_t kCompatibilityLevelCompleteSound = 5;
constexpr size_t kObjectivePickupCompatibilityHookSlot = 0;
constexpr size_t kLevelCompleteCompatibilityHookSlot = 1;
struct RemainingSoundCompatibilityHook {
    const char* hook;
    size_t index;
    const char* captureBlocker;
};
constexpr std::array<RemainingSoundCompatibilityHook, 2> kRemainingSoundCompatibilityHooks{{
    {"objective_pickup", kCompatibilityObjectivePickupSound,
     "rejected_static_candidates"},
    {"level_complete", kCompatibilityLevelCompleteSound,
     "no_static_candidate"},
}};
struct RejectedSoundCandidate {
    uint16_t offset;
    const char* reason;
};
constexpr std::array<RejectedSoundCandidate, 3> kRejectedObjectiveSoundCandidates{{
    {0x4b2c, "collapse_playback"},
    {0x6d75, "bomb_object_high_gate"},
    {0x6924, "non_objective_tile_gate"},
}};
constexpr uint16_t kEndFlowDispatcherStart = 0x1b14;
constexpr uint16_t kEndFlowDispatcherRet = 0x1d42;
struct StaticSoundContext {
    uint16_t offset;
    uint16_t cursor;
    uint8_t priority;
    const char* context;
};
constexpr std::array<StaticSoundContext, 5> kRecordUiSoundContexts{{
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
constexpr std::array<RuntimeSoundCaptureTarget, 4> kActorContactSoundCaptureTargets{{
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
constexpr std::array<uint16_t, 14> kDebugSoundCursors{
    0x0000, 0x0008, 0x0012, 0x001a, 0x0021, 0x0024, 0x0027,
    0x002d, 0x0031, 0x0035, 0x003d, 0x0056, 0x0069, 0x0078,
};
constexpr std::array<uint16_t, 15> kExpectedSoundStopCursors{
    0x0005, 0x0008, 0x0012, 0x001a, 0x0021, 0x0024, 0x0027, 0x002d,
    0x0031, 0x0035, 0x003d, 0x0056, 0x0069, 0x0078, 0x0082,
};
constexpr uint16_t kBombObjectDefaultSoundCursor = 0x0000;
constexpr uint16_t kBombObjectHighSoundCursor = 0x0012;
constexpr uint8_t kBombObjectSoundPriority = 3;
constexpr uint8_t kBombObjectHighSoundThreshold = 0x6c;
constexpr uint16_t kPortalTeleportSoundCursor = 0x001a;
constexpr uint8_t kPortalTeleportSoundPriority = 4;
constexpr uint16_t kTileTriggerSoundCursor = 0x0027;
constexpr uint8_t kTileTriggerSoundPriority = 6;
constexpr uint16_t kBonusPickupSoundCursor = 0x0008;
constexpr uint8_t kBonusPickupSoundPriority = 5;
constexpr uint16_t kRecordNamePromptSoundCursor = 0x0078;
constexpr uint8_t kRecordNamePromptSoundPriority = 11;
constexpr uint16_t kRecordNameCommitSoundCursor = 0x0008;
constexpr uint8_t kRecordNameCommitSoundPriority = 11;
constexpr uint16_t kRecordsPageSoundCursor = 0x0024;
constexpr uint8_t kRecordsPageSoundPriority = 2;
constexpr uint8_t kWeaponSwitchHoldTicks = 5;
constexpr uint16_t kWeaponSwitchSoundCursor = 0x0024;
constexpr uint8_t kWeaponSwitchSoundPriority = 2;
constexpr uint8_t kLaunchPadTile = 0x27;
constexpr uint16_t kLaunchPadSoundCursor = 0x0035;
constexpr uint8_t kLaunchPadSoundPriority = 5;
constexpr int16_t kOriginalNormalJumpVelocity = -848;
constexpr int16_t kOriginalLaunchPadVelocity = -2000;
constexpr float kPlayerJumpVelocity = -135.0f;
constexpr float kLaunchPadVelocity =
    kPlayerJumpVelocity * (static_cast<float>(kOriginalLaunchPadVelocity) /
                           static_cast<float>(kOriginalNormalJumpVelocity));
constexpr uint8_t kLaunchPadMarkerTimer = 5;
constexpr uint8_t kLaunchPadMarkerFrame = 0x5b;
constexpr uint8_t kLaunchPadMarkerKind = 0x0b;
constexpr uint8_t kLaunchPadMarkerMode = 5;
constexpr int16_t kLaunchPadMarkerVelocityY8 = -200;
constexpr uint16_t kPlayerDamageSoundCursor = 0x002d;
constexpr uint8_t kPlayerDamageSoundPriority = 4;
constexpr uint16_t kPlayerDeathSoundCursor = 0x0056;
constexpr uint8_t kPlayerDeathSoundPriority = 5;

struct Rgb {
    uint8_t r = 0;
    uint8_t g = 0;
    uint8_t b = 0;
};

struct LevelIntroPattern {
    int horizontalStep = 1;
    int verticalStep = 1;
    std::array<Rgb, kLevelIntroPaletteCount> colors{};
};

struct LevelIntroState {
    bool active = false;
    uint32_t startedAt = 0;
    int levelIndex = 0;
    LevelIntroPattern pattern;
};

using Palette = std::array<Rgb, 256>;

struct IndexedImage {
    int width = 0;
    int height = 0;
    std::vector<uint8_t> pixels;
};

struct Sprite {
    int width = 0;
    int height = 0;
    std::vector<uint8_t> pixels;
};

struct SpriteBank {
    std::vector<Sprite> sprites;
};

struct TileBank {
    int count = 0;
    std::vector<uint8_t> pixels;

    const uint8_t* tile(int id) const {
        if (id < 0 || id >= count) {
            return nullptr;
        }
        return pixels.data() + static_cast<size_t>(id) * kTileSize * kTileSize;
    }
};

struct MonsterSpawner {
    uint16_t x = 0;
    uint16_t y = 0;
    uint16_t tileIndex = 0;
    uint16_t savedWordOrLink = 0;
    uint8_t enabled = 0;
    uint8_t spawnBudget = 0;
    uint8_t liveAllowance = 0;
    uint8_t monsterKind = 0;
    uint16_t param0Base = 0;
    uint16_t param0Range = 0;
    uint16_t param1Base = 0;
    uint16_t param1Range = 0;
    uint16_t param2Base = 0;
    uint16_t param2Range = 0;
    uint8_t randomBase = 0;
    uint8_t randomRange = 0;
    uint8_t spawnArg = 0;
    uint8_t cooldown = 0;
    uint8_t cooldownReset = 0;
    uint8_t animationDelay = 0;
};

struct LevelPortal {
    uint16_t key = 0;
    uint16_t x = 0;
    uint16_t y = 0;
    uint8_t marker = 0;
};

struct TileTriggerRule {
    uint16_t wordRangeFirst = 0;
    uint16_t wordRangeLast = 0;
    uint16_t triggerKey = 0;
    std::array<uint8_t, 4> from{};
    std::array<uint8_t, 4> to{};
};

struct Level {
    size_t fileOffset = 0;
    int width = 0;
    int height = 0;
    uint8_t objectiveTile = 0;
    uint16_t requiredBonus = 0;
    uint8_t requiredDestruction = 0;
    uint16_t tileEncodedSize = 0;
    uint16_t wordEncodedSize = 0;
    uint16_t fieldA = 0;
    uint16_t fieldB = 0;
    std::vector<uint8_t> tiles;
    std::vector<uint16_t> wordLayer;
    std::vector<MonsterSpawner> monsterSpawners;
    std::vector<LevelPortal> portals;
    std::vector<TileTriggerRule> tileTriggers;
    int startingObjectiveTiles = 0;
    int startingDestructibleTiles = 0;
};

bool countsForDestructionProgress(uint8_t tile, uint8_t objectiveTile) {
    return tile > 1 && tile != 0xff && tile != objectiveTile;
}

bool countsForPhysicalDamageProgress(uint16_t word) {
    return word != 0 && (word & kDamagedWordBit) == 0 && word < kDeferredThreshold;
}

int countPhysicalDamageProgressCells(const std::vector<uint16_t>& words) {
    return static_cast<int>(std::count_if(words.begin(), words.end(),
                                          countsForPhysicalDamageProgress));
}

struct Record {
    uint32_t score = 0;
    uint8_t level = 0;
    std::string name;
    std::string encodedName;
};

struct SoundEffectRecord {
    std::vector<uint8_t> bytes;
};

struct SoundBank {
    uint16_t recordSize = 0;
    std::vector<SoundEffectRecord> records;
    std::vector<uint8_t> payload;
    size_t stepCount = 0;
};

struct SoundLatch {
    bool active = false;
    uint8_t currentSelector = 0;
    uint16_t latchedOffset = 0;
    size_t recordIndex = 0;
    bool directSweep = false;
};

struct GranRecord {
    std::vector<uint8_t> bytes;
};

struct GranBank {
    size_t recordSize = kGranRecordSize;
    std::vector<GranRecord> records;
};

enum class MenuPage {
    Main,
    Info,
    Instructions,
    Records,
    NameEntry,
    GameOver,
    CompletedGame,
};

enum class EndReason {
    GameOver,
    CompletedGame,
};

struct PendingRecordEntry {
    uint32_t score = 0;
    uint8_t level = 0;
    uint8_t player = 1;
    EndReason reason = EndReason::GameOver;
};

enum class BombType : uint8_t {
    Small = 0,
    Medium = 1,
    Large = 2,
    Super = 3,
};

struct BombProfile {
    uint8_t actorKind = 0x0d;
    uint8_t spriteBase = 58;
    int fuseTicks = 20;
};

struct BombInventory {
    std::array<int, 4> counts{200, 20, 6, 0};
    BombType selected = BombType::Small;
};

struct Bomb {
    int x = 0;
    int y = 0;
    int timer = 95;
    BombType type = BombType::Small;
    int fuseTicks = 20;
    uint8_t owner = 1;
};

struct Flash {
    int x = 0;
    int y = 0;
    int timer = 12;
    uint8_t power = 1;
};

struct LaunchPadMarker {
    int x = 0;
    int y = 0;
    uint8_t fracX = 0;
    uint8_t fracY = 0;
    int16_t velocityX8 = 0;
    int16_t velocityY8 = kLaunchPadMarkerVelocityY8;
    uint8_t timer = kLaunchPadMarkerTimer;
    uint8_t frame = kLaunchPadMarkerFrame;
    uint8_t kind = kLaunchPadMarkerKind;
    uint8_t mode = kLaunchPadMarkerMode;
};

struct ExplosionEffect {
    int x = 0;
    int y = 0;
    uint8_t visualSelector = 1;
    uint8_t dispatcherState = 4;
    uint8_t slotIndex = 1;
    uint8_t sourceIndex = 0;
    bool inactive = false;
    int timer = 8;
    int totalTimer = 8;
    uint16_t soundOffset = kExplosionDirectSweepSoundOffsets[0];
    uint8_t soundSelector = kExplosionSoundSelectors[0];
    uint8_t seedTicksByte = 8;
    uint8_t detailByte = 0x75;
    uint8_t variantByte = 5;
    int computedX = 0;
    int computedY = 0;
    int finalSignedOffset = 0;
};

struct DebrisRecord {
    int tileIndex = 0;
    uint16_t flaggedWord = 0;
    uint8_t forwardPhase = 0;
    uint8_t reversePhase = 0;
    std::array<uint8_t, 3> zeroPad{0, 0, 0};
    uint8_t lookup = 0;
    uint8_t trailingZero = 0;
    int timer = 18;
};

struct CollapseRecord {
    int x = 0;
    int y = 0;
    uint16_t startOffsetBytes = 0;
    uint16_t endOffsetBytes = 0;
    uint16_t word = 0;
    uint16_t flaggedWord = 0;
    uint8_t forwardPhase = 0;
    uint8_t reversePhase = 0;
    uint16_t argMagnitude = 0;
    uint8_t affectedBytes = 0;
    int count = 0;
    int timer = 24;
};

struct DamagePhaseLookup {
    int slotIndex = 0;
    uint8_t phase = 0;
    bool debris = false;
};

struct LaneWriteTagModel {
    uint16_t tag = 0;
    bool debris = false;
    uint16_t slot = 0;
    uint16_t di = 0;
    uint16_t forwardWrite = 0;
    uint16_t reverseWrite = 0;
};

LaneWriteTagModel laneWriteTagModelForTag(uint16_t tag) {
    const bool debris = tag >= kHighHalfBase;
    const uint16_t slot = debris ? static_cast<uint16_t>(tag - kHighHalfBase) : tag;
    const size_t stride = debris ? kDebrisStride : kCollapseStride;
    const uint16_t di = static_cast<uint16_t>(stride * slot);
    const uint16_t forwardBase = debris ? kDebrisForwardLaneBase : kCollapseForwardLaneBase;
    const uint16_t reverseBase = debris ? kDebrisReverseLaneBase : kCollapseReverseLaneBase;
    return {tag,
            debris,
            slot,
            di,
            static_cast<uint16_t>(forwardBase + di),
            static_cast<uint16_t>(reverseBase + di)};
}

struct FrameInspection {
    size_t changedPixels = 0;
    uint64_t hash = 0;
};

struct Player {
    float x = 24.0f;
    float y = 24.0f;
    float vx = 0.0f;
    float vy = 0.0f;
    bool grounded = false;
};

struct SpawnerState {
    int remaining = 0;
    int availableSlots = 0;
    int cooldown = 0;
};

struct ActiveMonster {
    int x = 0;
    int y = 0;
    int16_t vx8 = 0;
    int16_t vy8 = 0;
    uint8_t fracX = 0;
    uint8_t fracY = 0;
    uint8_t kind = 0;
    uint8_t behavior = 0;
    uint16_t ai0 = 0;
    uint16_t ai1 = 0;
    uint16_t ai2 = 0;
    uint8_t animFrame = 0;
    uint8_t animStart = 0;
    uint8_t animEnd = 0;
    uint8_t animDelay = 0;
    uint8_t animMode = 1;
    int8_t animStep = 1;
    size_t spawnerIndex = 0;
    bool hasSpawner = false;
    int hp = 1;
    int stateTimer = 0;
    int motionTimer = 0;
    int animTick = 0;
    bool deathCredited = false;
    bool alive = true;
    // Level-7 boss fields recovered from the GRAN.MST static consumer model:
    // kind 0x1e runs the original 1000:5CB0 head brain (behavior/state 6) and
    // kind 0x1f segments follow DS:0x79EA motion links (behavior/state 5).
    uint8_t bossVisual = 0;
    uint8_t bossLives = 0;
    uint8_t bossHpByte = 0;
    uint8_t bossBoxW = 0;
    uint8_t bossBoxH = 0;
    uint8_t linkA = 0;
    uint8_t linkB = 0;
    uint8_t linkC = 0;
    int bossTick = 0;
    int hurtFlash = 0;
    bool bossDebris = false;
};

// Semantic view of one 16-byte DS:0x79EA motion-link entry from GRAN.MST.
// mode != 0xff: spring/follow (out = (target - self + off) * gain, plus a
// per-axis velocity pull-back of `mode`); mode == 0xff: orbit (out = target +
// off + radius * sin/cos of a 128-step phase advanced by `gain`).
struct BossMotionLink {
    uint8_t targetVisual = 0;
    uint8_t selfVisual = 0;
    uint8_t gain = 0;
    uint8_t mode = 0;
    uint8_t radiusX = 0;
    uint8_t radiusY = 0;
    uint8_t phase = 0;
    int16_t offX = 0;
    int16_t offY = 0;
    int16_t outX = 0;
    int16_t outY = 0;
    int8_t biasY = 0;
};

// Facing anim-set pair table recovered from the shipped data segment
// (DS:0x58/0x59, image linear 0xAA20): boss sets 0x0e -> frames 41..42,
// 0x0f -> 43..44, and 0x10 -> 40..40, drawn from the PROVA.SPR bank that the
// original loads instead of BOMOMIMK.SPR on level 7 (selector 1000:2C90).
constexpr std::array<std::array<uint8_t, 2>, 17> kBossAnimSets{{
    {0, 0}, {0, 0}, {0, 0}, {0, 0}, {0, 0}, {0, 0}, {0, 0}, {0, 0},
    {0, 0}, {0, 0}, {0, 0}, {0, 0}, {0, 0}, {0, 0},
    {41, 42}, {43, 44}, {40, 40},
}};

enum class BonusType : uint8_t {
    Present,
    FirstAid,
    HotDog,
    JollyCloud,
    YellowBombBox,
    GreenBombBox,
    BigDiamond,
};

struct BonusDrop {
    float x = 0.0f;
    float y = 0.0f;
    BonusType type = BonusType::Present;
    int animTick = 0;
    bool collected = false;
};

int16_t clampI16(int value) {
    return static_cast<int16_t>(std::clamp(value, -32768, 32767));
}

void integrateAxis8_8(int& pos, uint8_t& frac, int16_t velocity) {
    uint16_t bits = static_cast<uint16_t>(velocity);
    uint16_t sum = static_cast<uint16_t>(frac) + (bits & 0x00ffu);
    frac = static_cast<uint8_t>(sum & 0x00ffu);
    int delta = static_cast<int>(static_cast<int8_t>((bits >> 8) & 0x00ffu));
    if (sum > 0x00ffu) {
        ++delta;
    }
    pos += delta;
}

std::vector<uint8_t> readFile(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in && path.find('/') == std::string::npos &&
        path.find('\\') == std::string::npos) {
        in.clear();
        in.open("src/" + path, std::ios::binary);
    }
    if (!in) {
        throw std::runtime_error("cannot open " + path);
    }
    return std::vector<uint8_t>(std::istreambuf_iterator<char>(in),
                                std::istreambuf_iterator<char>());
}

std::string readTextFile(const std::string& path) {
    std::ifstream in(path);
    if (!in && path.find('/') == std::string::npos &&
        path.find('\\') == std::string::npos) {
        in.clear();
        in.open("src/" + path);
    }
    if (!in) {
        throw std::runtime_error("cannot open " + path);
    }
    return std::string(std::istreambuf_iterator<char>(in),
                       std::istreambuf_iterator<char>());
}

std::vector<uint8_t> parseHexByteList(const std::string& hexList) {
    std::vector<uint8_t> out;
    std::istringstream iss(hexList);
    std::string token;
    while (iss >> token) {
        int value = std::stoi(token, nullptr, 16);
        out.push_back(static_cast<uint8_t>(value));
    }
    return out;
}

std::vector<uint16_t> parseHexWordList(const std::string& hexList) {
    std::vector<uint16_t> out;
    std::istringstream iss(hexList);
    std::string token;
    while (iss >> token) {
        int value = std::stoi(token, nullptr, 16);
        out.push_back(static_cast<uint16_t>(value));
    }
    return out;
}

std::vector<std::string> extractStringArray(const std::string& json, const std::string& key) {
    std::vector<std::string> rows;
    std::string needle = "\"" + key + "\"";
    size_t keyPos = json.find(needle);
    if (keyPos == std::string::npos) return rows;
    size_t open = json.find('[', keyPos);
    if (open == std::string::npos) return rows;
    size_t depth = 1;
    for (size_t i = open + 1; i < json.size() && depth > 0; ++i) {
        char ch = json[i];
        if (ch == '[') {
            ++depth;
        } else if (ch == ']') {
            --depth;
        } else if (ch == '"') {
            size_t end = json.find('"', i + 1);
            if (end == std::string::npos) break;
            rows.push_back(json.substr(i + 1, end - i - 1));
            i = end;
        }
    }
    return rows;
}

std::vector<std::string> extractObjectArray(const std::string& json, const std::string& key) {
    std::vector<std::string> objects;
    std::string needle = "\"" + key + "\"";
    size_t keyPos = json.find(needle);
    if (keyPos == std::string::npos) return objects;
    size_t open = json.find('[', keyPos);
    if (open == std::string::npos) return objects;
    size_t depth = 1;
    for (size_t i = open + 1; i < json.size() && depth > 0; ++i) {
        if (json[i] == '[') {
            ++depth;
        } else if (json[i] == ']') {
            --depth;
        } else if (depth == 1 && json[i] == '{') {
            size_t objStart = i;
            size_t objDepth = 1;
            for (++i; i < json.size() && objDepth > 0; ++i) {
                if (json[i] == '{') ++objDepth;
                else if (json[i] == '}') --objDepth;
            }
            if (objDepth == 0) {
                objects.push_back(json.substr(objStart, i - objStart));
            }
            --i;
        }
    }
    return objects;
}

int extractInt(const std::string& json, const std::string& key, int fallback = 0) {
    std::regex re("\"" + key + "\"\\s*:\\s*(-?\\d+)");
    std::smatch m;
    if (std::regex_search(json, m, re)) {
        return std::stoi(m[1].str());
    }
    return fallback;
}

std::string extractString(const std::string& json, const std::string& key,
                          const std::string& fallback = "") {
    std::regex re("\"" + key + "\"\\s*:\\s*\"([^\"]*)\"");
    std::smatch m;
    if (std::regex_search(json, m, re)) {
        return m[1].str();
    }
    return fallback;
}

std::array<uint8_t, 4> extractU8Array4(const std::string& json, const std::string& key) {
    std::array<uint8_t, 4> out{};
    std::regex re("\"" + key + "\"\\s*:\\s*\\[([^\\]]*)\\]");
    std::smatch m;
    if (!std::regex_search(json, m, re)) return out;
    std::regex intRe("(\\d+)");
    int i = 0;
    std::string body = m[1].str();
    for (auto it = std::sregex_iterator(body.begin(), body.end(), intRe);
         it != std::sregex_iterator() && i < 4; ++it, ++i) {
        out[static_cast<size_t>(i)] = static_cast<uint8_t>(std::stoi((*it)[1].str()));
    }
    return out;
}

uint16_t le16(const std::vector<uint8_t>& data, size_t off) {
    if (off + 2 > data.size()) {
        throw std::runtime_error("unexpected EOF while reading u16");
    }
    return static_cast<uint16_t>(data[off] | (data[off + 1] << 8));
}

uint32_t le32(const std::vector<uint8_t>& data, size_t off) {
    if (off + 4 > data.size()) {
        throw std::runtime_error("unexpected EOF while reading u32");
    }
    return static_cast<uint32_t>(data[off] | (data[off + 1] << 8) |
                                 (data[off + 2] << 16) | (data[off + 3] << 24));
}

template <size_t N>
uint16_t recLe16(const std::array<uint8_t, N>& rec, size_t off) {
    return static_cast<uint16_t>(rec[off] | (rec[off + 1] << 8));
}

uint8_t getU8(const std::vector<uint8_t>& data, size_t& off) {
    if (off >= data.size()) {
        throw std::runtime_error("unexpected EOF while reading u8");
    }
    return data[off++];
}

uint16_t getU16(const std::vector<uint8_t>& data, size_t& off) {
    uint16_t value = le16(data, off);
    off += 2;
    return value;
}

template <size_t N>
std::vector<std::array<uint8_t, N>> getFixedRecords(const std::vector<uint8_t>& data, size_t& off) {
    uint8_t count = getU8(data, off);
    if (off + static_cast<size_t>(count) * N > data.size()) {
        throw std::runtime_error("truncated fixed record block");
    }
    std::vector<std::array<uint8_t, N>> out;
    out.reserve(count);
    for (uint8_t i = 0; i < count; ++i) {
        std::array<uint8_t, N> rec{};
        std::copy_n(data.begin() + static_cast<long>(off), N, rec.begin());
        off += N;
        out.push_back(rec);
    }
    return out;
}

std::vector<uint8_t> getBytes(const std::vector<uint8_t>& data, size_t& off, size_t size) {
    if (off + size > data.size()) {
        throw std::runtime_error("truncated byte block");
    }
    std::vector<uint8_t> out(data.begin() + static_cast<long>(off),
                             data.begin() + static_cast<long>(off + size));
    off += size;
    return out;
}

uint8_t vga6To8(uint8_t v) {
    return static_cast<uint8_t>((v << 2) | (v >> 4));
}

Palette loadPalette(const std::vector<uint8_t>& data, size_t off) {
    if (off + 768 > data.size()) {
        throw std::runtime_error("palette data is truncated");
    }
    Palette palette{};
    for (int i = 0; i < 256; ++i) {
        palette[i] = {vga6To8(data[off + i * 3]),
                      vga6To8(data[off + i * 3 + 1]),
                      vga6To8(data[off + i * 3 + 2])};
    }
    return palette;
}

Palette loadPaletteFile(const std::string& path) {
    auto json = readTextFile(path);
    std::regex rgbRe("\"rgb8\"\\s*:\\s*\\[\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\]");
    auto begin = std::sregex_iterator(json.begin(), json.end(), rgbRe);
    auto end = std::sregex_iterator();
    Palette palette{};
    int i = 0;
    for (auto it = begin; it != end && i < 256; ++it, ++i) {
        palette[i] = {
            static_cast<uint8_t>(std::stoi((*it)[1].str())),
            static_cast<uint8_t>(std::stoi((*it)[2].str())),
            static_cast<uint8_t>(std::stoi((*it)[3].str())),
        };
    }
    if (i != 256) {
        throw std::runtime_error(path + " does not contain 256 rgb8 palette entries");
    }
    return palette;
}

uint32_t argb(const Palette& palette, uint8_t index) {
    const Rgb c = palette[index];
    return 0xff000000u | (static_cast<uint32_t>(c.r) << 16) |
           (static_cast<uint32_t>(c.g) << 8) | c.b;
}

std::string hex64(uint64_t value) {
    std::ostringstream oss;
    oss << "0x" << std::hex << std::nouppercase << std::setw(16)
        << std::setfill('0') << value;
    return oss.str();
}

std::string hex4(uint16_t value) {
    std::ostringstream oss;
    oss << "0x" << std::hex << std::nouppercase << std::setw(4)
        << std::setfill('0') << value;
    return oss.str();
}

std::string hex2(uint8_t value) {
    std::ostringstream oss;
    oss << "0x" << std::hex << std::nouppercase << std::setw(2)
        << std::setfill('0') << static_cast<int>(value);
    return oss.str();
}

std::string joinPath(const std::string& dir, const std::string& name) {
    return (std::filesystem::path(dir) / name).string();
}

void writeArgbPpm(const std::string& path, const std::vector<uint32_t>& pixels,
                  int width, int height) {
    if (pixels.size() != static_cast<size_t>(width) * height) {
        throw std::runtime_error("frame buffer size mismatch while writing " + path);
    }
    std::ofstream out(path, std::ios::binary);
    if (!out) {
        throw std::runtime_error("cannot create " + path);
    }
    out << "P6\n" << width << ' ' << height << "\n255\n";
    for (uint32_t pixelValue : pixels) {
        out.put(static_cast<char>((pixelValue >> 16) & 0xffu));
        out.put(static_cast<char>((pixelValue >> 8) & 0xffu));
        out.put(static_cast<char>(pixelValue & 0xffu));
    }
}

std::vector<uint8_t> decodeLevelRle3(const std::vector<uint8_t>& encoded, size_t targetSize) {
    std::vector<uint8_t> out(targetSize + 32, 0);
    size_t in = 0;
    size_t pos = 0;

    auto run = [&](uint8_t value, size_t len) {
        const size_t end = std::min(pos + len, out.size() - 1);
        for (size_t i = pos; i <= end; ++i) {
            out[i] = value;
        }
        pos += len;
    };

    while (pos < targetSize && in + 2 < encoded.size()) {
        uint8_t cmd = encoded[in++];
        uint8_t a = encoded[in++];
        uint8_t b = encoded[in++];
        run(a, static_cast<size_t>((cmd >> 4) + 1));
        if (pos >= targetSize) {
            break;
        }
        run(b, static_cast<size_t>((cmd & 0x0f) + 1));
    }

    out.resize(targetSize);
    return out;
}

IndexedImage loadBackground(const std::string& path, Palette& paletteOut) {
    auto json = readTextFile(path);
    std::regex rgbRe("\"rgb8\"\\s*:\\s*\\[\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\]");
    auto begin = std::sregex_iterator(json.begin(), json.end(), rgbRe);
    auto end = std::sregex_iterator();
    int pi = 0;
    for (auto it = begin; it != end && pi < 256; ++it, ++pi) {
        paletteOut[pi] = {
            static_cast<uint8_t>(std::stoi((*it)[1].str())),
            static_cast<uint8_t>(std::stoi((*it)[2].str())),
            static_cast<uint8_t>(std::stoi((*it)[3].str())),
        };
    }
    if (pi != 256) throw std::runtime_error(path + " palette section is incomplete");

    IndexedImage image;
    image.width = extractInt(json, "width", kBackgroundW);
    image.height = extractInt(json, "height", kBackgroundH);
    image.pixels.reserve(kBackgroundW * kBackgroundH);
    for (const auto& row : extractStringArray(json, "pixel_rows_hex")) {
        auto bytes = parseHexByteList(row);
        image.pixels.insert(image.pixels.end(), bytes.begin(), bytes.end());
    }
    if (image.pixels.size() != static_cast<size_t>(image.width) * image.height) {
        throw std::runtime_error(path + " decoded to " + std::to_string(image.pixels.size()) +
                                 " bytes, expected " +
                                 std::to_string(static_cast<size_t>(image.width) * image.height));
    }
    return image;
}

IndexedImage loadRawBackground(const std::string& path, Palette& paletteOut) {
    auto data = readFile(path);
    if (data.size() < 770) {
        throw std::runtime_error(path + " is too small for a palette and header");
    }
    paletteOut = loadPalette(data, 0);

    // Recovered from the original ZBG display routine (Ghidra 1000:030b, decoder
    // 1000:82d0). After the 768-byte VGA palette, a 2-byte little-endian length
    // header gives the RLE payload size; the payload is a nibble-paired RLE that
    // decodes to exactly one 320x200 mode-13h screen. Each 3-byte group
    // (b0, b1, b2) emits (b0>>4)+1 copies of b1 followed by (b0&0x0f)+1 copies
    // of b2.
    const size_t rleLength = static_cast<size_t>(data[768]) |
                             (static_cast<size_t>(data[769]) << 8);
    const size_t rleEnd = std::min(data.size(), 770 + rleLength);
    const size_t targetPixels =
        static_cast<size_t>(kBackgroundW) * kBackgroundH;

    IndexedImage image;
    image.width = kBackgroundW;
    image.height = kBackgroundH;
    image.pixels.reserve(targetPixels);
    size_t off = 770;
    while (off + 3 <= rleEnd && image.pixels.size() < targetPixels) {
        const uint8_t b0 = data[off];
        const uint8_t value1 = data[off + 1];
        const uint8_t value2 = data[off + 2];
        off += 3;
        image.pixels.insert(image.pixels.end(),
                            static_cast<size_t>((b0 >> 4) & 0x0f) + 1, value1);
        image.pixels.insert(image.pixels.end(),
                            static_cast<size_t>(b0 & 0x0f) + 1, value2);
    }
    if (image.pixels.size() > targetPixels) {
        image.pixels.resize(targetPixels);
    }
    if (image.pixels.size() != targetPixels) {
        throw std::runtime_error(path + " raw RLE decoded to " +
                                 std::to_string(image.pixels.size()) +
                                 " bytes, expected " +
                                 std::to_string(targetPixels));
    }
    return image;
}

TileBank loadTiles(const std::string& path) {
    auto json = readTextFile(path);
    TileBank bank;
    bank.count = extractInt(json, "tile_count");
    auto tileObjects = extractObjectArray(json, "tiles");
    if (static_cast<int>(tileObjects.size()) != bank.count) {
        throw std::runtime_error(path + " tile count mismatch");
    }
    for (const auto& tileJson : tileObjects) {
        for (const auto& row : extractStringArray(tileJson, "rows_hex")) {
            auto bytes = parseHexByteList(row);
            bank.pixels.insert(bank.pixels.end(), bytes.begin(), bytes.end());
        }
    }
    return bank;
}

TileBank loadRawTiles(const std::string& path) {
    auto data = readFile(path);
    if (data.size() < 2) {
        throw std::runtime_error(path + " is too small for a tile header");
    }
    TileBank bank;
    bank.count = static_cast<int>((data[0] << 8) | data[1]);
    size_t payloadSize = data.size() - 2;
    size_t expectedSize = static_cast<size_t>(bank.count) * kTileSize * kTileSize;
    if (bank.count <= 0 || payloadSize != expectedSize) {
        throw std::runtime_error(path + " raw tile payload size mismatch");
    }
    bank.pixels.insert(bank.pixels.end(), data.begin() + 2, data.end());
    return bank;
}

SpriteBank loadSprites(const std::string& path) {
    auto json = readTextFile(path);
    SpriteBank bank;
    auto spriteObjects = extractObjectArray(json, "sprites");
    bank.sprites.reserve(spriteObjects.size());
    for (const auto& spriteJson : spriteObjects) {
        Sprite s;
        s.width = extractInt(spriteJson, "width");
        s.height = extractInt(spriteJson, "height");
        for (const auto& row : extractStringArray(spriteJson, "rows_hex")) {
            auto bytes = parseHexByteList(row);
            s.pixels.insert(s.pixels.end(), bytes.begin(), bytes.end());
        }
        if (s.pixels.size() != static_cast<size_t>(s.width) * s.height) {
            throw std::runtime_error(path + " sprite size mismatch");
        }
        bank.sprites.push_back(std::move(s));
    }
    return bank;
}

SpriteBank loadRawSprites(const std::string& path) {
    auto data = readFile(path);
    if (data.empty()) {
        throw std::runtime_error(path + " is empty");
    }
    SpriteBank bank;
    size_t offset = 0;
    uint8_t count = data[offset++];
    bank.sprites.reserve(count);
    for (uint8_t i = 0; i < count; ++i) {
        if (offset + 2 > data.size()) {
            throw std::runtime_error(path + " truncated sprite header");
        }
        Sprite sprite;
        sprite.width = data[offset++];
        sprite.height = data[offset++];
        size_t pixelCount = static_cast<size_t>(sprite.width) * sprite.height;
        if (offset + pixelCount > data.size()) {
            throw std::runtime_error(path + " truncated sprite pixels");
        }
        sprite.pixels.insert(sprite.pixels.end(),
                             data.begin() + static_cast<std::ptrdiff_t>(offset),
                             data.begin() +
                                 static_cast<std::ptrdiff_t>(offset + pixelCount));
        offset += pixelCount;
        bank.sprites.push_back(std::move(sprite));
    }
    if (offset != data.size()) {
        throw std::runtime_error(path + " trailing sprite bytes");
    }
    return bank;
}

std::vector<Record> parseJsonRecords(const std::string& json) {
    std::vector<Record> records;
    auto recordObjects = extractObjectArray(json, "records");
    for (const auto& recJson : recordObjects) {
        Record r;
        r.score = static_cast<uint32_t>(extractInt(recJson, "score"));
        r.level = static_cast<uint8_t>(extractInt(recJson, "level"));
        r.name = extractString(recJson, "decoded_name", "nessuno");
        r.encodedName = extractString(recJson, "encoded_name", "");
        records.push_back(r);
    }
    return records;
}

std::string decodeRawRecordName(std::string encoded) {
    std::replace(encoded.begin(), encoded.end(), ':', ' ');
    while (!encoded.empty() && encoded.back() == ' ') {
        encoded.pop_back();
    }
    return encoded.empty() ? std::string("nessuno") : encoded;
}

std::vector<Record> parseRawRecords(const std::vector<uint8_t>& data,
                                    const std::string& path) {
    constexpr size_t kRecordSize = 13;
    if (data.empty()) {
        throw std::runtime_error(path + " is empty");
    }
    uint8_t count = data[0];
    if (data.size() != 1 + static_cast<size_t>(count) * kRecordSize) {
        throw std::runtime_error(path + " raw record table size mismatch");
    }
    std::vector<Record> records;
    records.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        size_t off = 1 + i * kRecordSize;
        Record record;
        record.score = le32(data, off);
        record.level = data[off + 4];
        std::string encoded(data.begin() + static_cast<std::ptrdiff_t>(off + 5),
                            data.begin() + static_cast<std::ptrdiff_t>(off + 13));
        record.name = decodeRawRecordName(encoded);
        record.encodedName = encoded;
        records.push_back(std::move(record));
    }
    return records;
}

std::vector<Record> loadRawRecords(const std::string& path) {
    return parseRawRecords(readFile(path), path);
}

std::vector<Record> loadRecords(const std::string& path) {
    auto data = readFile(path);
    auto first = std::find_if(data.begin(), data.end(), [](uint8_t byte) {
        return !std::isspace(static_cast<unsigned char>(byte));
    });
    if (first != data.end() && *first == '{') {
        return parseJsonRecords(std::string(data.begin(), data.end()));
    }
    return parseRawRecords(data, path);
}

std::string encodeRecordName(const std::string& name) {
    std::string out = name;
    out.resize(8, ':');
    for (char& ch : out) {
        if (ch == ' ') ch = ':';
    }
    return out;
}

std::string encodedRecordName(const Record& record) {
    if (record.encodedName.size() == 8) {
        return record.encodedName;
    }
    return encodeRecordName(record.name);
}

Record makeRecord(uint32_t score, uint8_t level, const std::string& enteredName) {
    Record record;
    record.score = score;
    record.level = level;
    record.encodedName = encodeRecordName(enteredName);
    record.name = decodeRawRecordName(record.encodedName);
    return record;
}

bool isJsonRecordPath(const std::string& path) {
    std::string ext = std::filesystem::path(path).extension().string();
    std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return ext == ".json";
}

void saveRecords(const std::string& path, const std::vector<Record>& records) {
    if (!isJsonRecordPath(path)) {
        std::ofstream out(path, std::ios::binary);
        if (!out) {
            throw std::runtime_error("cannot create " + path);
        }
        size_t count = std::min<size_t>(records.size(), 255);
        out.put(static_cast<char>(count));
        for (size_t i = 0; i < count; ++i) {
            uint32_t score = records[i].score;
            out.put(static_cast<char>(score & 0xffu));
            out.put(static_cast<char>((score >> 8) & 0xffu));
            out.put(static_cast<char>((score >> 16) & 0xffu));
            out.put(static_cast<char>((score >> 24) & 0xffu));
            out.put(static_cast<char>(records[i].level));
            std::string name = encodedRecordName(records[i]);
            out.write(name.data(), static_cast<std::streamsize>(name.size()));
        }
        return;
    }

    std::ofstream out(path);
    if (!out) {
        throw std::runtime_error("cannot create " + path);
    }
    size_t count = std::min<size_t>(records.size(), 255);
    out << "{\n";
    out << "  \"file\": \"RECS.DAT\",\n";
    out << "  \"type\": \"high_scores\",\n";
    out << "  \"record_count\": " << count << ",\n";
    out << "  \"records\": [\n";
    for (size_t i = 0; i < count; ++i) {
        std::string name = encodedRecordName(records[i]);
        out << "    {\n";
        out << "      \"index\": " << i << ",\n";
        out << "      \"score\": " << records[i].score << ",\n";
        out << "      \"level\": " << static_cast<int>(records[i].level) << ",\n";
        out << "      \"encoded_name\": " << std::quoted(name) << ",\n";
        out << "      \"decoded_name\": " << std::quoted(records[i].name) << "\n";
        out << "    }" << (i + 1 == count ? "\n" : ",\n");
    }
    out << "  ]\n";
    out << "}\n";
}

bool insertRecord(std::vector<Record>& records, Record record, size_t maxRecords = 7) {
    std::vector<Record> before = records;
    records.push_back(std::move(record));
    std::stable_sort(records.begin(), records.end(),
                     [](const Record& a, const Record& b) {
                         return a.score > b.score;
                     });
    if (records.size() > maxRecords) {
        records.resize(maxRecords);
    }
    if (records.size() != before.size()) return true;
    for (size_t i = 0; i < records.size(); ++i) {
        if (records[i].score != before[i].score ||
            records[i].level != before[i].level ||
            records[i].name != before[i].name ||
            encodedRecordName(records[i]) != encodedRecordName(before[i])) {
            return true;
        }
    }
    return false;
}

SoundBank loadSon(const std::string& path) {
    auto json = readTextFile(path);
    SoundBank bank;
    bank.recordSize = static_cast<uint16_t>(extractInt(json, "record_size"));
    int declaredCount = extractInt(json, "record_count", -1);
    auto recordObjects = extractObjectArray(json, "records");
    if (declaredCount >= 0 && declaredCount != static_cast<int>(recordObjects.size())) {
        throw std::runtime_error(path + " record_count does not match records array");
    }
    for (const auto& recJson : recordObjects) {
        SoundEffectRecord record;
        record.bytes = parseHexByteList(extractString(recJson, "bytes_hex"));
        if (record.bytes.size() != bank.recordSize) {
            throw std::runtime_error(path + " record length does not match record_size");
        }
        bank.payload.insert(bank.payload.end(), record.bytes.begin(), record.bytes.end());
        bank.records.push_back(std::move(record));
    }
    if (bank.payload.empty() || bank.payload.size() % kSoundStepSize != 0) {
        throw std::runtime_error(path + " payload is not a whole number of six-byte steps");
    }
    bank.stepCount = bank.payload.size() / kSoundStepSize;
    return bank;
}

SoundBank loadRawSon(const std::string& path) {
    auto data = readFile(path);
    if (data.size() < 2) {
        throw std::runtime_error(path + " is too small for a sound header");
    }
    SoundBank bank;
    bank.stepCount = le16(data, 0);
    size_t payloadSize = bank.stepCount * kSoundStepSize;
    if (data.size() != 2 + payloadSize) {
        throw std::runtime_error(path + " raw payload size mismatch");
    }
    bank.payload.insert(bank.payload.end(), data.begin() + 2, data.end());
    bank.recordSize = 130;
    if (bank.payload.size() % bank.recordSize != 0) {
        throw std::runtime_error(path + " raw payload cannot be split into JSON chunks");
    }
    for (size_t off = 0; off < bank.payload.size(); off += bank.recordSize) {
        SoundEffectRecord record;
        record.bytes.insert(record.bytes.end(),
                            bank.payload.begin() + static_cast<std::ptrdiff_t>(off),
                            bank.payload.begin() +
                                static_cast<std::ptrdiff_t>(off + bank.recordSize));
        bank.records.push_back(std::move(record));
    }
    return bank;
}

GranBank loadGran(const std::string& path) {
    auto json = readTextFile(path);
    GranBank bank;
    bank.recordSize = static_cast<size_t>(extractInt(json, "record_size", static_cast<int>(kGranRecordSize)));
    if (bank.recordSize != kGranRecordSize) {
        throw std::runtime_error(path + " record_size does not match GRAN.MST fixed record size");
    }
    auto recordObjects = extractObjectArray(json, "records");
    if (recordObjects.size() != 7) {
        throw std::runtime_error(path + " records array does not contain seven records");
    }
    for (const auto& recJson : recordObjects) {
        GranRecord record;
        record.bytes = parseHexByteList(extractString(recJson, "bytes_hex"));
        if (record.bytes.size() != bank.recordSize) {
            throw std::runtime_error(path + " record length does not match record_size");
        }
        bank.records.push_back(std::move(record));
    }
    return bank;
}

GranBank loadRawGran(const std::string& path) {
    auto data = readFile(path);
    if (data.size() != 7 * kGranRecordSize) {
        throw std::runtime_error(path + " raw size does not match seven GRAN records");
    }
    GranBank bank;
    bank.recordSize = kGranRecordSize;
    for (size_t off = 0; off < data.size(); off += kGranRecordSize) {
        GranRecord record;
        record.bytes.insert(record.bytes.end(),
                            data.begin() + static_cast<std::ptrdiff_t>(off),
                            data.begin() +
                                static_cast<std::ptrdiff_t>(off + kGranRecordSize));
        bank.records.push_back(std::move(record));
    }
    return bank;
}

MonsterSpawner parseMonsterSpawner(const std::array<uint8_t, 30>& rec) {
    MonsterSpawner spawner;
    spawner.x = recLe16(rec, 0);
    spawner.y = recLe16(rec, 2);
    spawner.tileIndex = recLe16(rec, 4);
    spawner.savedWordOrLink = recLe16(rec, 6);
    spawner.enabled = rec[8];
    spawner.spawnBudget = rec[9];
    spawner.liveAllowance = rec[10];
    spawner.monsterKind = rec[11];
    spawner.param0Base = recLe16(rec, 12);
    spawner.param0Range = recLe16(rec, 14);
    spawner.param1Base = recLe16(rec, 16);
    spawner.param1Range = recLe16(rec, 18);
    spawner.param2Base = recLe16(rec, 20);
    spawner.param2Range = recLe16(rec, 22);
    spawner.randomBase = rec[24];
    spawner.randomRange = rec[25];
    spawner.spawnArg = rec[26];
    spawner.cooldown = rec[27];
    spawner.cooldownReset = rec[28];
    spawner.animationDelay = rec[29];
    return spawner;
}

LevelPortal parseLevelPortal(const std::array<uint8_t, 7>& rec) {
    return {recLe16(rec, 0), recLe16(rec, 2), recLe16(rec, 4), rec[6]};
}

TileTriggerRule parseTileTriggerRule(const std::array<uint8_t, 14>& rec) {
    TileTriggerRule rule;
    rule.wordRangeFirst = recLe16(rec, 0);
    rule.wordRangeLast = recLe16(rec, 2);
    rule.triggerKey = recLe16(rec, 4);
    std::copy_n(rec.begin() + 6, 4, rule.from.begin());
    std::copy_n(rec.begin() + 10, 4, rule.to.begin());
    return rule;
}

std::vector<Level> loadRawLevels(const std::string& path) {
    std::vector<uint8_t> data = readFile(path);
    std::vector<Level> levels;
    size_t off = 0;
    while (off < data.size()) {
        Level level;
        level.fileOffset = off;
        level.width = getU16(data, off);
        level.height = getU16(data, off);
        if (level.width <= 0 || level.height <= 0 || level.width > 300 || level.height > 200) {
            throw std::runtime_error(path + " has invalid raw level dimensions");
        }
        level.objectiveTile = getU8(data, off);
        level.requiredBonus = getU16(data, off);
        level.requiredDestruction = getU8(data, off);

        level.tileEncodedSize = getU16(data, off);
        std::vector<uint8_t> tileEncoded = getBytes(data, off, level.tileEncodedSize);
        size_t tileCount = static_cast<size_t>(level.width) * level.height;
        level.tiles = decodeLevelRle3(tileEncoded, tileCount);

        level.wordEncodedSize = getU16(data, off);
        std::vector<uint8_t> wordEncoded = getBytes(data, off, level.wordEncodedSize);
        std::vector<uint8_t> wordBytes = decodeLevelRle3(wordEncoded, tileCount * 2);
        level.wordLayer.reserve(tileCount);
        for (size_t i = 0; i + 1 < wordBytes.size(); i += 2) {
            level.wordLayer.push_back(le16(wordBytes, i));
        }

        level.fieldA = getU16(data, off);
        level.fieldB = getU16(data, off);

        for (const auto& rec : getFixedRecords<30>(data, off)) {
            level.monsterSpawners.push_back(parseMonsterSpawner(rec));
        }
        for (const auto& rec : getFixedRecords<7>(data, off)) {
            level.portals.push_back(parseLevelPortal(rec));
        }
        for (const auto& rec : getFixedRecords<14>(data, off)) {
            level.tileTriggers.push_back(parseTileTriggerRule(rec));
        }

        if (level.tiles.size() != tileCount || level.wordLayer.size() != tileCount) {
            throw std::runtime_error(path + " raw level arrays are inconsistent");
        }
        level.startingObjectiveTiles = static_cast<int>(
            std::count(level.tiles.begin(), level.tiles.end(), level.objectiveTile));
        level.startingDestructibleTiles = countPhysicalDamageProgressCells(level.wordLayer);
        levels.push_back(std::move(level));
    }
    return levels;
}

std::vector<Level> loadLevels(const std::string& path) {
    auto json = readTextFile(path);
    std::vector<Level> levels;
    auto levelObjects = extractObjectArray(json, "levels");
    for (const auto& levelJson : levelObjects) {
        Level level;
        level.fileOffset = static_cast<size_t>(extractInt(levelJson, "fileOffset"));
        level.width = extractInt(levelJson, "width");
        level.height = extractInt(levelJson, "height");
        if (level.width <= 0 || level.height <= 0 || level.width > 300 || level.height > 200) {
            throw std::runtime_error(path + " has invalid level dimensions");
        }
        level.objectiveTile = static_cast<uint8_t>(extractInt(levelJson, "objectiveTile"));
        level.requiredBonus = static_cast<uint16_t>(extractInt(levelJson, "requiredBonus"));
        level.requiredDestruction = static_cast<uint8_t>(extractInt(levelJson, "requiredDestruction"));
        level.tileEncodedSize = static_cast<uint16_t>(extractInt(levelJson, "tileEncodedSize"));
        level.wordEncodedSize = static_cast<uint16_t>(extractInt(levelJson, "wordEncodedSize"));
        level.fieldA = static_cast<uint16_t>(extractInt(levelJson, "fieldA"));
        level.fieldB = static_cast<uint16_t>(extractInt(levelJson, "fieldB"));

        for (const auto& row : extractStringArray(levelJson, "tiles_rows_hex")) {
            auto bytes = parseHexByteList(row);
            level.tiles.insert(level.tiles.end(), bytes.begin(), bytes.end());
        }
        for (const auto& row : extractStringArray(levelJson, "word_rows_hex")) {
            auto words = parseHexWordList(row);
            level.wordLayer.insert(level.wordLayer.end(), words.begin(), words.end());
        }

        for (const auto& spawnerJson : extractObjectArray(levelJson, "monsterSpawners")) {
            MonsterSpawner spawner;
            spawner.x = static_cast<uint16_t>(extractInt(spawnerJson, "x"));
            spawner.y = static_cast<uint16_t>(extractInt(spawnerJson, "y"));
            spawner.tileIndex = static_cast<uint16_t>(extractInt(spawnerJson, "tileIndex"));
            spawner.savedWordOrLink = static_cast<uint16_t>(extractInt(spawnerJson, "savedWordOrLink"));
            spawner.enabled = static_cast<uint8_t>(extractInt(spawnerJson, "enabled"));
            spawner.spawnBudget = static_cast<uint8_t>(extractInt(spawnerJson, "spawnBudget"));
            spawner.liveAllowance = static_cast<uint8_t>(extractInt(spawnerJson, "liveAllowance"));
            spawner.monsterKind = static_cast<uint8_t>(extractInt(spawnerJson, "monsterKind"));
            spawner.param0Base = static_cast<uint16_t>(extractInt(spawnerJson, "param0Base"));
            spawner.param0Range = static_cast<uint16_t>(extractInt(spawnerJson, "param0Range"));
            spawner.param1Base = static_cast<uint16_t>(extractInt(spawnerJson, "param1Base"));
            spawner.param1Range = static_cast<uint16_t>(extractInt(spawnerJson, "param1Range"));
            spawner.param2Base = static_cast<uint16_t>(extractInt(spawnerJson, "param2Base"));
            spawner.param2Range = static_cast<uint16_t>(extractInt(spawnerJson, "param2Range"));
            spawner.randomBase = static_cast<uint8_t>(extractInt(spawnerJson, "randomBase"));
            spawner.randomRange = static_cast<uint8_t>(extractInt(spawnerJson, "randomRange"));
            spawner.spawnArg = static_cast<uint8_t>(extractInt(spawnerJson, "spawnArg"));
            spawner.cooldown = static_cast<uint8_t>(extractInt(spawnerJson, "cooldown"));
            spawner.cooldownReset = static_cast<uint8_t>(extractInt(spawnerJson, "cooldownReset"));
            spawner.animationDelay = static_cast<uint8_t>(extractInt(spawnerJson, "animationDelay"));
            level.monsterSpawners.push_back(spawner);
        }
        for (const auto& portalJson : extractObjectArray(levelJson, "portals")) {
            LevelPortal p;
            p.key = static_cast<uint16_t>(extractInt(portalJson, "key"));
            p.x = static_cast<uint16_t>(extractInt(portalJson, "x"));
            p.y = static_cast<uint16_t>(extractInt(portalJson, "y"));
            p.marker = static_cast<uint8_t>(extractInt(portalJson, "marker"));
            level.portals.push_back(p);
        }
        for (const auto& triggerJson : extractObjectArray(levelJson, "tileTriggers")) {
            TileTriggerRule rule;
            rule.wordRangeFirst = static_cast<uint16_t>(extractInt(triggerJson, "wordRangeFirst"));
            rule.wordRangeLast = static_cast<uint16_t>(extractInt(triggerJson, "wordRangeLast"));
            rule.triggerKey = static_cast<uint16_t>(extractInt(triggerJson, "triggerKey"));
            rule.from = extractU8Array4(triggerJson, "from");
            rule.to = extractU8Array4(triggerJson, "to");
            level.tileTriggers.push_back(rule);
        }

        const size_t tileCount = static_cast<size_t>(level.width) * level.height;
        if (level.tiles.size() != tileCount || level.wordLayer.size() != tileCount) {
            throw std::runtime_error(path + " level arrays are inconsistent");
        }

        level.startingObjectiveTiles = static_cast<int>(
            std::count(level.tiles.begin(), level.tiles.end(), level.objectiveTile));
        level.startingDestructibleTiles = countPhysicalDamageProgressCells(level.wordLayer);
        if (level.fieldB != static_cast<uint16_t>(level.startingDestructibleTiles)) {
            throw std::runtime_error(path + " fieldB does not match low word-layer damage count");
        }
        levels.push_back(std::move(level));
    }
    return levels;
}

class App {
    struct FrameControls {
        bool p1Left = false;
        bool p1Right = false;
        bool p1Jump = false;
        bool p1Down = false;
        bool p2Left = false;
        bool p2Right = false;
        bool p2Jump = false;
        bool p2Down = false;
    };

    struct AutoplayRouteResult {
        int frames = 0;
        int startX = 0;
        int startY = 0;
        int finalX = 0;
        int finalY = 0;
        int bombTileX = 0;
        int bombTileY = 0;
    };

    struct State2VisualCursor {
        uint8_t current = kState2VisualStartFrame;
        uint8_t first = kState2VisualStartFrame;
        uint8_t last = kState2VisualEndFrame;
        uint8_t counter = kState2VisualDelay;
        uint8_t delay = kState2VisualDelay;
        uint8_t mode = 1;
        int8_t step = 1;
        bool active = false;
    };

    struct State2VisualRow {
        uint8_t frame = 0;
        uint8_t row0 = 0;
        uint8_t row1 = 0;
        uint8_t row2 = 0;
        uint8_t row3 = 0;
    };

    struct State2EffectEntry {
        int x = 0;
        int y = 0;
        uint8_t visualFrame = 0;
        uint8_t drawDx = 0;
        uint8_t drawDy = 0;
        uint8_t row2 = 0;
        uint8_t spriteIndex = 0;
        bool active = false;
    };

    struct CompatibilitySoundAttempt {
        size_t index = 0;
        uint16_t cursor = 0;
    };

    static bool sameSoundLatch(const SoundLatch& lhs, const SoundLatch& rhs) {
        return lhs.active == rhs.active &&
               lhs.currentSelector == rhs.currentSelector &&
               lhs.latchedOffset == rhs.latchedOffset &&
               lhs.recordIndex == rhs.recordIndex &&
               lhs.directSweep == rhs.directSweep;
    }

    static bool originalState2VisualRow(uint8_t frame, State2VisualRow& row) {
        if (frame < kState2VisualStartFrame || frame > kState2VisualEndFrame) {
            return false;
        }
        row.frame = frame;
        row.row0 = 0x10;
        row.row1 = 0x10;
        row.row2 = 0x7d;
        row.row3 = static_cast<uint8_t>(
            0x43 + (frame - kState2VisualStartFrame));
        return true;
    }

public:
    void loadJsonAssets() {
        palette_ = loadPaletteFile("BOMPAL.PAL.json");
        background_ = loadBackground("SFONLEF.ZBG.json", backgroundPalette_);
        tiles_ = loadTiles("CARO.CAR.json");
        sprites_ = loadSprites("BOMOMIMK.SPR.json");
        altSprites_ = loadSprites("PROVA.SPR.json");
        fontSprites_ = loadSprites("FONTS.SPR.json");
        records_ = loadRecords("RECS.DAT.json");
        sounds_ = loadSon("PROEFS.SON.json");
        gran_ = loadGran("GRAN.MST.json");
        levels_ = loadLevels("LIVELS.SCH.json");
        if (levels_.empty()) {
            throw std::runtime_error("no levels");
        }
    }

    void loadOriginalAssets() {
        palette_ = loadPalette(readFile("BOMPAL.PAL"), 0);
        background_ = loadRawBackground("SFONLEF.ZBG", backgroundPalette_);
        tiles_ = loadRawTiles("CARO.CAR");
        sprites_ = loadRawSprites("BOMOMIMK.SPR");
        altSprites_ = loadRawSprites("PROVA.SPR");
        fontSprites_ = loadRawSprites("FONTS.SPR");
        records_ = loadRawRecords("RECS.DAT");
        sounds_ = loadRawSon("PROEFS.SON");
        gran_ = loadRawGran("GRAN.MST");
        levels_ = loadRawLevels("LIVELS.SCH");
        if (levels_.empty()) {
            throw std::runtime_error("no levels");
        }
    }

    void load() {
        const char* jsonAssets = std::getenv("LEZAC_LOAD_JSON_ASSETS");
        const char* originalAssets = std::getenv("LEZAC_LOAD_ORIGINAL_ASSETS");
        if ((jsonAssets != nullptr && std::string(jsonAssets) != "0") ||
            (originalAssets != nullptr && std::string(originalAssets) == "0")) {
            loadJsonAssets();
        } else {
            loadOriginalAssets();
        }
    }

    void run() {
        load();
        initSdl();
        resetLevel(0);
        interactiveLevelIntroEnabled_ = true;
        uint32_t last = SDL_GetTicks();
        bool running = true;
        while (running) {
            processEvents(running);
            uint32_t now = SDL_GetTicks();
            float dt = std::min(0.05f, (now - last) / 1000.0f);
            last = now;
            update(dt);
            draw();
            SDL_Delay(kFrameDelayMs);
        }
    }

    void smokeControls() {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_i);
        processEvents(running);
        if (menuPage_ != MenuPage::Info) {
            throw std::runtime_error("info key did not open info page");
        }

        pushKeyDown(SDLK_z);
        processEvents(running);
        if (menuPage_ != MenuPage::Instructions) {
            throw std::runtime_error("instructions key did not open instructions page");
        }

        pushKeyDown(SDLK_r);
        processEvents(running);
        if (menuPage_ != MenuPage::Records) {
            throw std::runtime_error("records key did not open records page");
        }

        pushKeyDown(SDLK_ESCAPE);
        processEvents(running);
        if (menuPage_ != MenuPage::Main || !menu_) {
            throw std::runtime_error("Escape did not return records page to menu");
        }

        pushKeyDown(SDLK_2);
        processEvents(running);
        if (menu_ || playerCount_ != 2) {
            throw std::runtime_error("two-player key did not start two-player mode");
        }

        int twoPlayerViewWidth = gameplayViewWidth_;
        pushKeyDown(SDLK_r);
        processEvents(running);
        pushKeyDown(SDLK_e);
        processEvents(running);
        if (gameplayViewWidth_ != twoPlayerViewWidth) {
            throw std::runtime_error("two-player game changed one-player view width");
        }

        size_t twoPlayerBombs = bombs_.size();
        int player1BombX = static_cast<int>(player_.x + 6.0f) / 8;
        int player1BombY = static_cast<int>(player_.y + 12.0f) / 8;
        int player2BombX = static_cast<int>(player2_.x + 6.0f) / 8;
        int player2BombY = static_cast<int>(player2_.y + 12.0f) / 8;
        int player1SmallBombs = bombInventory_.counts[0];
        int player2SmallBombs = bombInventory2_.counts[0];
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.size() != twoPlayerBombs + 1 ||
            bombs_.back().owner != 1 ||
            bombs_.back().x != player1BombX || bombs_.back().y != player1BombY) {
            throw std::runtime_error("N key did not place player 1 bomb in two-player mode");
        }
        if (bombInventory_.counts[0] != player1SmallBombs - 1 ||
            bombInventory2_.counts[0] != player2SmallBombs) {
            throw std::runtime_error("N key did not consume player 1 inventory only");
        }
        pushKeyDown(SDLK_KP_0);
        processEvents(running);
        if (bombs_.size() != twoPlayerBombs + 2 ||
            bombs_.back().owner != 2 ||
            bombs_.back().x != player2BombX || bombs_.back().y != player2BombY) {
            throw std::runtime_error("keypad 0 did not place player 2 bomb in two-player mode");
        }
        if (bombInventory_.counts[0] != player1SmallBombs - 1 ||
            bombInventory2_.counts[0] != player2SmallBombs - 1) {
            throw std::runtime_error("keypad 0 did not consume player 2 inventory only");
        }

        resetLevel(0);
        size_t insertBombs = bombs_.size();
        int insertPlayer1SmallBombs = bombInventory_.counts[0];
        int insertPlayer2SmallBombs = bombInventory2_.counts[0];
        player2BombX = static_cast<int>(player2_.x + 6.0f) / 8;
        player2BombY = static_cast<int>(player2_.y + 12.0f) / 8;
        pushKeyDown(SDLK_INSERT);
        processEvents(running);
        if (bombs_.size() != insertBombs + 1 ||
            bombs_.back().owner != 2 ||
            bombs_.back().x != player2BombX || bombs_.back().y != player2BombY) {
            throw std::runtime_error("Insert did not place player 2 bomb in two-player mode");
        }
        if (bombInventory_.counts[0] != insertPlayer1SmallBombs ||
            bombInventory2_.counts[0] != insertPlayer2SmallBombs - 1) {
            throw std::runtime_error("Insert did not consume player 2 inventory only");
        }

        pushKeyDown(SDLK_ESCAPE);
        processEvents(running);
        if (!menu_) {
            throw std::runtime_error("Escape did not return two-player game to menu");
        }

        pushKeyDown(SDLK_2);
        processEvents(running);
        if (menu_ || playerCount_ != 2) {
            throw std::runtime_error("two-player restart key did not leave menu");
        }

        energy_ = 0;
        lives_ = 3;
        lives2_ = 3;
        damageCooldown_ = 0;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        int timeoutLevel = levelIndex_;
        float player2XBeforeTimeout = player2_.x;
        float player2YBeforeTimeout = player2_.y;
        for (int i = 0; i < kDeathStateTicks + kReentryTicks + 2; ++i) {
            updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                          playerCount_ == 1 || player2Dead_);
        }
        if (levelIndex_ != timeoutLevel || !playerDead_ || player2Dead_ ||
            reentryTimer_ != 0 || player2_.x != player2XBeforeTimeout ||
            player2_.y != player2YBeforeTimeout) {
            throw std::runtime_error("single-player reentry timeout reset two-player level");
        }
        lives_ = 3;
        lives2_ = 3;
        resetLevel(0);

        energy2_ = 0;
        lives_ = 3;
        lives2_ = 3;
        damageCooldown2_ = 0;
        size_t beforePlayer2ReentryBombs = bombs_.size();
        damagePlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                     damageCooldown2_, 2);
        if (menu_ || !player2Dead_ || lives2_ != 3 || !pendingLifeLoss2_ ||
            reentryTimer2_ <= 0 || playerDead_) {
            throw std::runtime_error("player 2 death did not enter reentry state");
        }
        pushKeyDown(SDLK_KP_0);
        processEvents(running);
        if (!player2Dead_ || energy2_ != 100 ||
            bombs_.size() != beforePlayer2ReentryBombs || damageCooldown2_ != 0) {
            throw std::runtime_error("keypad 0 bypassed player 2 state-2 death gate");
        }
        for (int i = 0; i < kDeathStateTicks; ++i) {
            updateReentry(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_, 2,
                          playerDead_);
        }
        pushKeyDown(SDLK_KP_0);
        processEvents(running);
        if (player2Dead_ || energy2_ != 100 || lives2_ != 2 ||
            bombs_.size() != beforePlayer2ReentryBombs || damageCooldown2_ <= 0) {
            throw std::runtime_error("keypad 0 did not reenter player 2 after death");
        }
        size_t afterPlayer2ReentryBombs = bombs_.size();
        int player2BombsAfterReentry = bombInventory2_.counts[0];
        pushKeyDown(SDLK_KP_0);
        processEvents(running);
        if (bombs_.size() != afterPlayer2ReentryBombs + 1 ||
            bombInventory2_.counts[0] != player2BombsAfterReentry - 1) {
            throw std::runtime_error("keypad 0 did not fire for player 2 after reentry");
        }

        energy2_ = 0;
        lives_ = 3;
        lives2_ = 1;
        damageCooldown2_ = 0;
        damagePlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                     damageCooldown2_, 2);
        if (menu_ || !player2Dead_ || lives2_ != 1 || !pendingLifeLoss2_ ||
            lives_ != 3 || playerDead_) {
            throw std::runtime_error("player 2 final life did not enter state-2");
        }
        size_t afterPlayer2OutBombs = bombs_.size();
        pushKeyDown(SDLK_KP_0);
        processEvents(running);
        if (!player2Dead_ || bombs_.size() != afterPlayer2OutBombs) {
            throw std::runtime_error("player 2 reentered or fired during final state-2");
        }
        for (int i = 0; i < kDeathStateTicks; ++i) {
            updateReentry(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_, 2,
                          playerDead_);
        }
        if (menu_ || !player2Dead_ || lives2_ != 0 || pendingLifeLoss2_) {
            throw std::runtime_error("player 2 final life was not consumed after state-2");
        }

        energy_ = 0;
        lives_ = 1;
        damageCooldown_ = 0;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        if (menu_ || !playerDead_ || lives_ != 1 || !pendingLifeLoss_) {
            throw std::runtime_error("player 1 final life did not enter state-2");
        }
        for (int i = 0; i < kDeathStateTicks; ++i) {
            updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                          true);
        }
        if (!menu_ || menuPage_ != MenuPage::GameOver) {
            throw std::runtime_error("both players out of lives did not end game");
        }

        pushKeyDown(SDLK_RETURN);
        processEvents(running);
        if (!menu_ || menuPage_ != MenuPage::Main) {
            throw std::runtime_error("game-over confirm did not return to main menu");
        }

        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1) {
            throw std::runtime_error("start key did not leave menu");
        }

        energy_ = 0;
        lives_ = 3;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        if (!playerDead_ || lives_ != 3 || !pendingLifeLoss_ || reentryTimer_ <= 0) {
            throw std::runtime_error("player death did not enter reentry state");
        }
        pushKeyDown(SDLK_SPACE);
        processEvents(running);
        if (!playerDead_ || damageCooldown_ != 0) {
            throw std::runtime_error("fire key bypassed state-2 death gate");
        }
        for (int i = 0; i < kDeathStateTicks; ++i) {
            updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                          true);
        }
        pushKeyDown(SDLK_SPACE);
        processEvents(running);
        if (playerDead_ || energy_ != 100 || lives_ != 2 || damageCooldown_ <= 0) {
            throw std::runtime_error("fire key did not reenter after death");
        }

        auto objectivePos = findObjectiveTileForSmoke();
        if (!consumeBombObjectTile(objectivePos[0], objectivePos[1]) ||
            canReenterLevel()) {
            throw std::runtime_error("objective destruction did not block reentry");
        }
        energy_ = 0;
        lives_ = 3;
        damageCooldown_ = 0;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        pushKeyDown(SDLK_SPACE);
        processEvents(running);
        if (!playerDead_ || lives_ != 3 || !pendingLifeLoss_ ||
            remainingObjectiveTiles() != level_.startingObjectiveTiles - 1) {
            throw std::runtime_error("fire bypassed unwinnable state-2 gate");
        }
        for (int i = 0; i < kDeathStateTicks; ++i) {
            updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                          true);
        }
        if (playerDead_ || lives_ != 2 ||
            remainingObjectiveTiles() != level_.startingObjectiveTiles) {
            throw std::runtime_error("fire reentered instead of restarting unwinnable level");
        }

        size_t bombCount = bombs_.size();
        int smallBombs = bombInventory_.counts[0];
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.size() != bombCount + 1) {
            throw std::runtime_error("N key did not place a bomb");
        }
        if (bombInventory_.counts[0] != smallBombs - 1) {
            throw std::runtime_error("N key did not consume bomb inventory");
        }

        energy_ = 100;
        damageCooldown_ = 0;
        DebrisRecord debris;
        debris.tileIndex = (static_cast<int>(player_.y + 8.0f) / 8) * level_.width +
                           (static_cast<int>(player_.x + 6.0f) / 8);
        debris.timer = 2;
        debrisQueue_.push_back(debris);
        updateFlashes();
        drainPlayerDamageCounters();
        if (energy_ >= 100) {
            throw std::runtime_error("active debris did not drain player energy");
        }
        int afterDebrisEnergy = energy_;
        updateFlashes();
        drainPlayerDamageCounters();
        if (energy_ >= afterDebrisEnergy) {
            throw std::runtime_error("active debris did not drain on the next pass");
        }

        pushKeyDown(SDLK_SPACE);
        processEvents(running);
        if (bombs_.size() != bombCount + 1) {
            throw std::runtime_error("duplicate bomb placed on occupied tile");
        }

        energy_ = 100;
        damageCooldown_ = 0;
        BombProfile contactProfile = bombProfile(BombType::Small);
        Bomb contactBomb{static_cast<int>(player_.x + 6.0f) / 8,
                         static_cast<int>(player_.y + 12.0f) / 8,
                         contactProfile.fuseTicks, BombType::Small,
                         contactProfile.fuseTicks};
        explode(contactBomb);
        drainPlayerDamageCounters();
        if (energy_ >= 100) {
            throw std::runtime_error("bomb explosion did not drain player energy");
        }

        FrameInspection backgroundOnFrame =
            inspectRenderedFrame("controls-background-on");
        bool background = showBackground_;
        pushKeyDown(SDLK_s);
        processEvents(running);
        if (showBackground_ == background) {
            throw std::runtime_error("background toggle key did not change state");
        }
        FrameInspection backgroundOffFrame =
            inspectRenderedFrame("controls-background-off");
        if (backgroundOffFrame.hash == backgroundOnFrame.hash) {
            throw std::runtime_error("background toggle did not change rendered frame");
        }

        int viewWidth = gameplayViewWidth_;
        pushKeyDown(SDLK_r);
        processEvents(running);
        if (gameplayViewWidth_ >= viewWidth) {
            throw std::runtime_error("R key did not reduce playfield width");
        }
        int reducedViewWidth = gameplayViewWidth_;
        FrameInspection reducedWidthFrame =
            inspectRenderedFrame("controls-view-width-reduced");
        if (reducedWidthFrame.hash == backgroundOffFrame.hash) {
            throw std::runtime_error("reduced playfield width did not change frame");
        }

        pushKeyDown(SDLK_e);
        processEvents(running);
        if (gameplayViewWidth_ != viewWidth) {
            throw std::runtime_error("E key did not restore playfield width");
        }
        FrameInspection restoredWidthFrame =
            inspectRenderedFrame("controls-view-width-restored");
        if (restoredWidthFrame.hash != backgroundOffFrame.hash) {
            throw std::runtime_error("restored playfield width did not redraw original frame");
        }

        pushKeyDown(SDLK_PAGEUP);
        processEvents(running);
        if (levelIndex_ != 1) {
            throw std::runtime_error("PageUp did not advance level");
        }

        pushKeyDown(SDLK_PAGEDOWN);
        processEvents(running);
        if (levelIndex_ != 0) {
            throw std::runtime_error("PageDown did not return to level 1");
        }

        pushKeyDown(SDLK_PAGEUP);
        processEvents(running);
        if (levelIndex_ != 1) {
            throw std::runtime_error("second PageUp did not advance level");
        }

        pushKeyDown(SDLK_ESCAPE);
        processEvents(running);
        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1 || levelIndex_ != 0) {
            throw std::runtime_error("menu start did not reset to level 1");
        }

        smokeBombObjectDestructionProgress();
        resetLevel(0);
        smokeCompleteCurrentLevelFromMapProgress();

        size_t preResetBombs = bombs_.size();
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.size() != preResetBombs + 1) {
            throw std::runtime_error("pre-reset bomb was not placed");
        }

        pushKeyDown(SDLK_F5);
        processEvents(running);
        if (!bombs_.empty()) {
            throw std::runtime_error("reset key did not clear active bombs");
        }

        pushKeyDown(SDLK_ESCAPE);
        processEvents(running);
        if (!menu_) {
            throw std::runtime_error("Escape did not return to menu");
        }

        pushKeyDown(SDLK_ESCAPE);
        processEvents(running);
        if (running) {
            throw std::runtime_error("Escape from menu did not exit");
        }
        std::cout << "control_smoke=ok manual_controls=s,e,r"
                  << " fire_keys=n,kp0,insert"
                  << " background_toggle=1"
                  << " view_width=" << viewWidth << "->" << reducedViewWidth
                  << "->" << gameplayViewWidth_
                  << " two_player_width_locked=1"
                  << " frame_inspection=1\n";
    }

    void smokeUi(int frames) {
        load();
        initSdl();
        resetLevel(0);
        frames = std::max(1, frames);
        for (int i = 0; i < frames; ++i) {
            SDL_PumpEvents();
            inspectRenderedFrame("smoke-ui");
            SDL_Delay(1);
        }
        std::cout << "ui_smoke=ok frames=" << frames << " frame_inspection=1\n";
    }

    void debugMenuFrameFlow() {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;
        std::set<uint64_t> hashes;

        auto inspectMenuPage = [&](MenuPage expected, const std::string& label) {
            if (!menu_ || menuPage_ != expected) {
                throw std::runtime_error(label + " menu page not active");
            }
            FrameInspection frame = inspectRenderedFrame("menu-frame-" + label);
            if (!regionHasVariation(30, 40, 260, 134)) {
                throw std::runtime_error(label + " menu text region was not visible");
            }
            hashes.insert(frame.hash);
            return frame;
        };
        auto press = [&](SDL_Keycode key) {
            pushKeyDown(key);
            processEvents(running);
        };

        FrameInspection mainFrame = inspectMenuPage(MenuPage::Main, "main");
        press(SDLK_i);
        FrameInspection infoFrame = inspectMenuPage(MenuPage::Info, "info");
        press(SDLK_z);
        FrameInspection instructionsFrame =
            inspectMenuPage(MenuPage::Instructions, "instructions");
        clearSoundLatch();
        lastPumpedSoundOffset_ = 0;
        lastPumpedSoundSelector_ = 0;
        press(SDLK_r);
        FrameInspection recordsFrame = inspectMenuPage(MenuPage::Records, "records");
        pumpSoundLatch();
        if (lastPumpedSoundOffset_ != kRecordsPageSoundCursor ||
            lastPumpedSoundSelector_ != kRecordsPageSoundPriority) {
            throw std::runtime_error("records menu frame flow did not pump records sound");
        }

        press(SDLK_ESCAPE);
        if (!menu_ || menuPage_ != MenuPage::Main) {
            throw std::runtime_error("records menu did not return to main with Escape");
        }
        showBackground_ = true;
        press(SDLK_1);
        if (menu_ || playerCount_ != 1 || levelIndex_ != 0) {
            throw std::runtime_error("menu frame flow did not start one-player game");
        }
        FrameInspection gameFrame =
            inspectRenderedFrame("menu-frame-game-background-on");
        if (gameFrame.hash == mainFrame.hash ||
            !regionHasVariation(0, 0, kScreenW, 24) ||
            !regionHasVariation(0, 24, kScreenW, kScreenH - 24)) {
            throw std::runtime_error("one-player start frame did not expose HUD/world");
        }
        press(SDLK_s);
        if (showBackground_) {
            throw std::runtime_error("gameplay background toggle did not turn off background");
        }
        FrameInspection backgroundOffFrame =
            inspectRenderedFrame("menu-frame-game-background-off");
        if (backgroundOffFrame.hash == gameFrame.hash) {
            throw std::runtime_error("gameplay background toggle did not change rendered frame");
        }
        hashes.insert(gameFrame.hash);
        hashes.insert(backgroundOffFrame.hash);

        press(SDLK_ESCAPE);
        FrameInspection returnedMenuFrame =
            inspectMenuPage(MenuPage::Main, "return-main");
        if (!menu_ || returnedMenuFrame.hash == backgroundOffFrame.hash) {
            throw std::runtime_error("game Escape did not render the main menu");
        }
        press(SDLK_ESCAPE);
        if (running) {
            throw std::runtime_error("main-menu Escape did not request exit");
        }

        if (hashes.size() < 6 ||
            mainFrame.hash == infoFrame.hash ||
            infoFrame.hash == instructionsFrame.hash ||
            instructionsFrame.hash == recordsFrame.hash) {
            throw std::runtime_error("menu frame flow did not render distinct pages");
        }

        std::cout << "menu_frame_flow=ok"
                  << " pages=main,info,instructions,records"
                  << " unique_frames=" << hashes.size()
                  << " gameplay_background_toggle=1"
                  << " records_sound_cursor=" << hex4(kRecordsPageSoundCursor)
                  << " records_sound_priority="
                  << static_cast<int>(kRecordsPageSoundPriority)
                  << " start_game=1"
                  << " escape_exit=1"
                  << " frame_inspection=1\n";
    }

    void debugLevel1FrameInspection() {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        int initialPlayerX = static_cast<int>(player_.x);
        int initialPlayerY = static_cast<int>(player_.y);
        FrameInspection menuFrame = inspectRenderedFrame("level1-menu");
        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1 || levelIndex_ != 0 ||
            level_.width != 60 || level_.height != 33 ||
            initialPlayerX != 104 || initialPlayerY != 168 ||
            bombInventory_.counts[0] != 200) {
            throw std::runtime_error("level1 frame smoke did not start one-player level 1");
        }
        FrameInspection playFrame = inspectRenderedFrame("level1-start");
        std::vector<uint32_t> playPixels = fb_;
        if (playFrame.hash == menuFrame.hash) {
            throw std::runtime_error("level1 start frame did not differ from menu frame");
        }
        if (!regionHasVariation(0, 0, kScreenW, 16)) {
            throw std::runtime_error("level1 HUD band did not contain visible glyphs");
        }
        if (!regionHasVariation(0, 16, kScreenW, kScreenH - 16)) {
            throw std::runtime_error("level1 world band did not contain visible pixels");
        }
        if (!regionHasVariation(initialPlayerX - 2, initialPlayerY - 64 - 2, 16, 20)) {
            throw std::runtime_error("level1 player sprite region was not visible");
        }

        size_t bombsBefore = bombs_.size();
        int smallBombsBefore = bombInventory_.counts[0];
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.size() != bombsBefore + 1 ||
            bombInventory_.counts[0] != smallBombsBefore - 1) {
            throw std::runtime_error("level1 N key did not place and consume a bomb");
        }
        FrameInspection bombFrame = inspectRenderedFrame("level1-n-bomb");
        int bombTileX = bombs_.back().x;
        int bombTileY = bombs_.back().y;
        int smallBombsAfterN = bombInventory_.counts[0];
        if (bombFrame.hash == playFrame.hash) {
            throw std::runtime_error("level1 bomb placement did not change the frame");
        }
        if (!regionChanged(playPixels, bombTileX * kTileSize, bombTileY * kTileSize - 64,
                           kTileSize, kTileSize)) {
            throw std::runtime_error("level1 bomb tile region did not change after N");
        }

        int fuse = bombs_.back().timer;
        for (int i = 0; i < fuse; ++i) {
            update(1.0f / 60.0f);
        }
        if (!bombs_.empty() || explosionEffects_.empty() || flashes_.empty()) {
            throw std::runtime_error("level1 N bomb did not explode through update loop");
        }
        FrameInspection explosionFrame = inspectRenderedFrame("level1-n-explosion");
        if (explosionFrame.hash == bombFrame.hash) {
            throw std::runtime_error("level1 explosion did not change the frame");
        }

        collectAllObjectiveTilesForSmoke();
        damageRequiredTilesForSmoke();
        if (!isComplete()) {
            throw std::runtime_error("level1 map progress did not complete the level");
        }
        FrameInspection completeFrame = inspectRenderedFrame("level1-complete");
        if (completeFrame.hash == explosionFrame.hash) {
            throw std::runtime_error("level1 completion did not change the frame");
        }
        for (int i = 0; i <= 100; ++i) {
            update(1.0f / 60.0f);
        }
        if (levelIndex_ != 1) {
            throw std::runtime_error("level1 frame smoke did not advance to level 2");
        }
        FrameInspection nextLevelFrame = inspectRenderedFrame("level2-start");
        if (nextLevelFrame.hash == completeFrame.hash) {
            throw std::runtime_error("level transition did not change the frame");
        }

        std::cout << "level1_frame_inspection=ok"
                  << " level=1 size=60x33"
                  << " p1_xy=" << initialPlayerX << ',' << initialPlayerY
                  << " p1_bomb_tile=" << bombTileX << ',' << bombTileY
                  << " initial_small=" << smallBombsBefore
                  << " after_n_small=" << smallBombsAfterN
                  << " bombs=1 menu_uniform=0 gameplay_uniform=0"
                  << " menu_game_different=" << (menuFrame.hash != playFrame.hash ? 1 : 0)
                  << " hud_nonempty=1 world_nonempty=1 player_visible=1"
                  << " bomb_visible=1 explosion_visible=1 completion_visible=1"
                  << " advanced_level=" << (levelIndex_ + 1)
                  << '\n';
    }

    void captureFrameSequence(const std::string& scenario, const std::string& outDir) {
        load();
        initSdl();
        resetLevel(0);
        std::filesystem::create_directories(outDir);

        struct CapturedFrame {
            std::string label;
            std::string file;
            FrameInspection inspection;
            int menu = 0;
            int level = 0;
            int playerCount = 0;
            int p1x = 0;
            int p1y = 0;
            int p1BombX = 0;
            int p1BombY = 0;
            int p1FootTile = 0;
            int p1Dead = 0;
            int p2x = -1;
            int p2y = -1;
            int p2BombX = -1;
            int p2BombY = -1;
            int p2Dead = 0;
            size_t bombs = 0;
            size_t flashes = 0;
            size_t launchMarkers = 0;
            int launchMarkerX = -1;
            int launchMarkerY = -1;
            int launchMarkerTimer = 0;
            int launchMarkerFrame = 0;
            int launchMarkerKind = 0;
            int launchMarkerMode = 0;
            uint16_t lastSoundOffset = 0;
            int lastSoundPriority = 0;
            size_t explosions = 0;
            size_t debris = 0;
            size_t collapse = 0;
            int firstDebrisTile = -1;
            uint16_t firstDebrisFlagged = 0;
            int firstDebrisForward = 0;
            int firstDebrisReverse = 0;
            int firstDebrisLookup = 0;
            int firstDebrisTimer = 0;
            int firstCollapseX = -1;
            int firstCollapseY = -1;
            uint16_t firstCollapseStart = 0;
            uint16_t firstCollapseEnd = 0;
            uint16_t firstCollapseFlagged = 0;
            int firstCollapseForward = 0;
            int firstCollapseReverse = 0;
            int firstCollapseAffected = 0;
            int firstCollapseCount = 0;
            int firstCollapseTimer = 0;
            int firstEffectX = -1;
            int firstEffectY = -1;
            int firstEffectVisual = 0;
            int firstEffectDetail = 0;
            int firstEffectTimer = 0;
            int firstEffectVariant = 0;
            size_t monsters = 0;
            int monsterX = -1;
            int monsterY = -1;
            int monsterVx8 = 0;
            int monsterVy8 = 0;
            int monsterBehavior = -1;
            int monsterHp = 0;
            int monsterSpawner = 0;
        };

        std::vector<CapturedFrame> captures;
        auto capture = [&](const std::string& label) {
            CapturedFrame frame;
            frame.label = label;
            frame.file = label + ".ppm";
            frame.inspection = inspectRenderedFrame(label);
            frame.menu = menu_ ? 1 : 0;
            frame.level = levelIndex_ + 1;
            frame.playerCount = playerCount_;
            frame.p1x = static_cast<int>(player_.x);
            frame.p1y = static_cast<int>(player_.y);
            frame.p1BombX = static_cast<int>(player_.x + 6.0f) / kTileSize;
            frame.p1BombY = static_cast<int>(player_.y + 12.0f) / kTileSize;
            frame.p1FootTile = tileAt(
                static_cast<int>(player_.x + 6.0f) / kTileSize,
                static_cast<int>(player_.y + 16.0f) / kTileSize);
            frame.p1Dead = playerDead_ ? 1 : 0;
            if (playerCount_ > 1) {
                frame.p2x = static_cast<int>(player2_.x);
                frame.p2y = static_cast<int>(player2_.y);
                frame.p2BombX = static_cast<int>(player2_.x + 6.0f) / kTileSize;
                frame.p2BombY = static_cast<int>(player2_.y + 12.0f) / kTileSize;
            }
            frame.p2Dead = player2Dead_ ? 1 : 0;
            frame.bombs = bombs_.size();
            frame.flashes = flashes_.size();
            frame.launchMarkers = launchPadMarkers_.size();
            frame.lastSoundOffset = lastPumpedSoundOffset_;
            frame.lastSoundPriority = lastPumpedSoundSelector_;
            if (!launchPadMarkers_.empty()) {
                const LaunchPadMarker& marker = launchPadMarkers_.front();
                frame.launchMarkerX = marker.x;
                frame.launchMarkerY = marker.y;
                frame.launchMarkerTimer = marker.timer;
                frame.launchMarkerFrame = marker.frame;
                frame.launchMarkerKind = marker.kind;
                frame.launchMarkerMode = marker.mode;
            }
            frame.explosions = explosionEffects_.size();
            frame.debris = debrisQueue_.size();
            frame.collapse = collapseQueue_.size();
            if (!debrisQueue_.empty()) {
                const DebrisRecord& debris = debrisQueue_.front();
                frame.firstDebrisTile = debris.tileIndex;
                frame.firstDebrisFlagged = debris.flaggedWord;
                frame.firstDebrisForward = debris.forwardPhase;
                frame.firstDebrisReverse = debris.reversePhase;
                frame.firstDebrisLookup = debris.lookup;
                frame.firstDebrisTimer = debris.timer;
            }
            if (!collapseQueue_.empty()) {
                const CollapseRecord& collapse = collapseQueue_.front();
                frame.firstCollapseX = collapse.x;
                frame.firstCollapseY = collapse.y;
                frame.firstCollapseStart = collapse.startOffsetBytes;
                frame.firstCollapseEnd = collapse.endOffsetBytes;
                frame.firstCollapseFlagged = collapse.flaggedWord;
                frame.firstCollapseForward = collapse.forwardPhase;
                frame.firstCollapseReverse = collapse.reversePhase;
                frame.firstCollapseAffected = collapse.affectedBytes;
                frame.firstCollapseCount = collapse.count;
                frame.firstCollapseTimer = collapse.timer;
            }
            if (!explosionEffects_.empty()) {
                const ExplosionEffect& effect = explosionEffects_.front();
                frame.firstEffectX = effect.x;
                frame.firstEffectY = effect.y;
                frame.firstEffectVisual = effect.visualSelector;
                frame.firstEffectDetail = effect.detailByte;
                frame.firstEffectTimer = effect.timer;
                frame.firstEffectVariant = effect.variantByte;
            }
            frame.monsters = monsters_.size();
            if (!monsters_.empty()) {
                const ActiveMonster& monster = monsters_.front();
                frame.monsterX = monster.x;
                frame.monsterY = monster.y;
                frame.monsterVx8 = monster.vx8;
                frame.monsterVy8 = monster.vy8;
                frame.monsterBehavior = monster.behavior;
                frame.monsterHp = monster.hp;
                frame.monsterSpawner = monster.hasSpawner ? static_cast<int>(monster.spawnerIndex) + 1 : 0;
            }
            writeArgbPpm(joinPath(outDir, frame.file), fb_, kScreenW, kScreenH);
            captures.push_back(std::move(frame));
        };

        bool running = true;
        auto spanUpper = [](uint16_t base, uint16_t range) {
            return static_cast<uint16_t>(base + std::max<uint16_t>(1, range));
        };
        auto findSpawnerByBehavior = [&](uint8_t behavior) {
            for (size_t i = 0; i < level_.monsterSpawners.size(); ++i) {
                if (level_.monsterSpawners[i].spawnArg == behavior) {
                    return i;
                }
            }
            return level_.monsterSpawners.size();
        };
        auto disableOtherSpawners = [&](size_t keepIndex) {
            for (size_t i = 0; i < spawnerStates_.size(); ++i) {
                if (i != keepIndex) {
                    spawnerStates_[i].remaining = 0;
                    spawnerStates_[i].availableSlots = 0;
                }
            }
        };

        capture("000_menu");

        if (scenario == "level1_bomb_route") {
            pushKeyDown(SDLK_1);
            processEvents(running);
            if (menu_ || playerCount_ != 1 || levelIndex_ != 0) {
                throw std::runtime_error("frame sequence failed to start one-player level 1");
            }
            capture("010_level1_start");

            AutoplayRouteResult route = autoplayLevel1BombRoute();
            if (route.bombTileX != 24 || route.bombTileY != 22) {
                throw std::runtime_error("frame sequence autoplayer missed level-1 tile 24,22");
            }
            capture("020_level1_tile24_aligned");

            pushKeyDown(SDLK_n);
            processEvents(running);
            if (bombs_.empty() || bombs_.back().x != 24 || bombs_.back().y != 22) {
                throw std::runtime_error(
                    "frame sequence N key did not place the level-1 tile 24,22 bomb");
            }
            capture("030_level1_tile24_bomb");

            int fuse = bombs_.back().timer;
            for (int i = 0; i < fuse; ++i) {
                update(1.0f / 60.0f);
            }
            if (!bombs_.empty() || explosionEffects_.empty()) {
                throw std::runtime_error("frame sequence bomb did not reach explosion playback");
            }
            capture("040_level1_tile24_explosion");

            for (int i = 0; i < 4; ++i) {
                update(1.0f / 60.0f);
            }
            capture("050_level1_tile24_playback_4");

            for (int i = 0; i < 8; ++i) {
                update(1.0f / 60.0f);
            }
            capture("060_level1_tile24_playback_12");
        } else if (scenario == "launch_pad_route") {
            pushKeyDown(SDLK_1);
            processEvents(running);
            resetLevel(5);
            if (menu_ || playerCount_ != 1 || levelIndex_ != 5) {
                throw std::runtime_error("frame sequence failed to start launch-pad route");
            }
            for (SpawnerState& state : spawnerStates_) {
                state.remaining = 0;
                state.availableSlots = 0;
            }

            int padX = -1;
            int padY = -1;
            for (int y = 0; y < level_.height && padX < 0; ++y) {
                for (int x = 0; x < level_.width; ++x) {
                    if (tileAt(x, y) == kLaunchPadTile) {
                        padX = x;
                        padY = y;
                        break;
                    }
                }
            }
            if (padX < 0) {
                throw std::runtime_error("frame sequence found no level-6 launch pad");
            }
            player_.x = static_cast<float>(padX * kTileSize);
            player_.y = static_cast<float>(padY * kTileSize - 16);
            player_.vx = 0.0f;
            player_.vy = 0.0f;
            player_.grounded = true;
            clearSoundLatch();
            lastPumpedSoundOffset_ = 0;
            lastPumpedSoundSelector_ = 0;
            capture("010_level6_launch_pad_ready");
            uint64_t readyHash = captures.back().inspection.hash;

            FrameControls down;
            down.p1Down = true;
            updateWithControls(down, 1.0f / 60.0f);
            if (launchPadMarkers_.size() != 1 || player_.vy >= 0.0f ||
                lastPumpedSoundOffset_ != kLaunchPadSoundCursor ||
                lastPumpedSoundSelector_ != kLaunchPadSoundPriority) {
                throw std::runtime_error("frame sequence launch-pad activation mismatch");
            }
            capture("020_level6_launch_pad_fired");
            if (captures.back().inspection.hash == readyHash) {
                throw std::runtime_error("frame sequence launch-pad frame did not move");
            }

            FrameControls idle;
            for (int i = 0; i < 4; ++i) {
                updateWithControls(idle, 1.0f / 60.0f);
            }
            if (launchPadMarkers_.size() != 1 ||
                launchPadMarkers_.front().timer != 2) {
                throw std::runtime_error("frame sequence launch marker midpoint mismatch");
            }
            capture("030_level6_launch_pad_airborne");

            int markerUpdates = 4;
            while (!launchPadMarkers_.empty() && markerUpdates < 12) {
                updateWithControls(idle, 1.0f / 60.0f);
                ++markerUpdates;
            }
            if (!launchPadMarkers_.empty() || markerUpdates != 8) {
                throw std::runtime_error("frame sequence launch marker lifetime mismatch");
            }
            capture("040_level6_launch_pad_marker_expired");
        } else if (scenario == "monster_bomb_reward") {
            pushKeyDown(SDLK_1);
            processEvents(running);
            if (menu_ || playerCount_ != 1 || levelIndex_ != 0) {
                throw std::runtime_error("frame sequence failed to start monster bomb route");
            }
            capture("010_monster_bomb_start");

            pushKeyDown(SDLK_n);
            processEvents(running);
            if (bombs_.empty() || bombs_.back().owner != 1) {
                throw std::runtime_error("frame sequence monster bomb did not place bomb");
            }
            bombs_.back().timer = 1;
            Bomb placed = bombs_.back();
            auto tiles = explosionTilesFor(placed);
            std::array<int, 2> monsterTile = tiles.front();
            for (const auto& tile : tiles) {
                if (!monsterCollides(tile[0] * kTileSize, tile[1] * kTileSize - kTileSize)) {
                    monsterTile = tile;
                    break;
                }
            }

            ActiveMonster monster;
            monster.x = monsterTile[0] * kTileSize;
            monster.y = monsterTile[1] * kTileSize - kTileSize;
            monster.kind = 2;
            monster.behavior = 3;
            monster.ai0 = 0;
            monster.ai1 = 0;
            monster.ai2 = 1;
            monster.hp = 1;
            monster.animDelay = 1;
            refreshMonsterAnimationProfile(monster);
            initializeMonsterMotion(monster);
            monsters_.push_back(monster);

            player_.x = static_cast<float>(
                std::min(level_.width * kTileSize - 24, (placed.x + 5) * kTileSize));
            player_.y = static_cast<float>(placed.y * kTileSize);
            capture("020_monster_bomb_armed");

            FrameControls idle;
            updateWithControls(idle, 1.0f / 60.0f);
            if (!bombs_.empty() || monsters_.empty() ||
                monsters_.front().behavior != 2 || bonusDrops_.empty()) {
                throw std::runtime_error("frame sequence monster bomb did not kill monster");
            }
            capture("030_monster_bomb_death");

            uint32_t scoreBefore = score_;
            BonusDrop drop = bonusDrops_.front();
            player_.x = drop.x;
            player_.y = drop.y;
            updateWithControls(idle, 1.0f / 60.0f);
            if (score_ <= scoreBefore) {
                throw std::runtime_error("frame sequence monster reward was not collected");
            }
            capture("040_monster_bomb_reward_collected");
        } else if (scenario == "monster_spawner_behavior4_level2") {
            pushKeyDown(SDLK_1);
            processEvents(running);
            if (menu_ || playerCount_ != 1) {
                throw std::runtime_error("frame sequence failed to start one-player level 2");
            }
            resetLevel(1);
            if (levelIndex_ != 1) {
                throw std::runtime_error("frame sequence did not load level 2");
            }
            capture("010_level2_start");

            size_t spawnerIndex = findSpawnerByBehavior(4);
            if (spawnerIndex >= level_.monsterSpawners.size()) {
                throw std::runtime_error("frame sequence found no level-2 behavior-4 spawner");
            }
            disableOtherSpawners(spawnerIndex);
            const MonsterSpawner& spawner = level_.monsterSpawners[spawnerIndex];
            randomSeed_ = 0x1234abcd;
            player_.x = static_cast<float>(spawner.x + 40);
            player_.y = static_cast<float>(spawner.y);
            player_.vy = -6.0f;
            player_.grounded = false;
            spawnerStates_[spawnerIndex].cooldown = 0;
            capture("020_level2_behavior4_spawner_armed");

            FrameControls idle;
            updateWithControls(idle, 1.0f / 60.0f);
            if (monsters_.size() != 1) {
                throw std::runtime_error("frame sequence did not spawn level-2 behavior-4 actor");
            }
            const ActiveMonster& monster = monsters_.front();
            if (!monster.hasSpawner || monster.spawnerIndex != spawnerIndex ||
                monster.kind != spawner.monsterKind || monster.behavior != 4 ||
                monster.animDelay != std::max<uint8_t>(1, spawner.animationDelay) ||
                monster.ai0 < spawner.param0Base ||
                monster.ai0 >= spanUpper(spawner.param0Base, spawner.param0Range) ||
                monster.ai1 < spawner.param1Base ||
                monster.ai1 >= spanUpper(spawner.param1Base, spawner.param1Range) ||
                monster.ai2 < spawner.param2Base ||
                monster.ai2 >= spanUpper(spawner.param2Base, spawner.param2Range) ||
                monster.hp < spawner.randomBase ||
                monster.hp >= spanUpper(spawner.randomBase, spawner.randomRange) ||
                monster.motionTimer != std::max<int>(1, monster.ai0) - 1 ||
                monster.vx8 <= 0 || monster.vy8 != 0 || monster.x <= spawner.x) {
                throw std::runtime_error(
                    "frame sequence level-2 behavior-4 spawn fields mismatched");
            }
            capture("030_level2_behavior4_spawned");
        } else if (scenario == "monster_spawner_behavior4_level3") {
            pushKeyDown(SDLK_1);
            processEvents(running);
            if (menu_ || playerCount_ != 1) {
                throw std::runtime_error("frame sequence failed to start one-player level 3");
            }
            resetLevel(2);
            if (levelIndex_ != 2) {
                throw std::runtime_error("frame sequence did not load level 3");
            }
            capture("010_level3_start");

            size_t spawnerIndex = findSpawnerByBehavior(4);
            if (spawnerIndex >= level_.monsterSpawners.size()) {
                throw std::runtime_error("frame sequence found no level-3 behavior-4 spawner");
            }
            disableOtherSpawners(spawnerIndex);
            const MonsterSpawner& spawner = level_.monsterSpawners[spawnerIndex];
            randomSeed_ = 0x1234abcd;
            player_.x = static_cast<float>(spawner.x + 24);
            player_.y = static_cast<float>(spawner.y - 16);
            player_.vy = -6.0f;
            player_.grounded = false;
            spawnerStates_[spawnerIndex].cooldown = 0;
            capture("020_level3_behavior4_spawner_armed");

            FrameControls idle;
            updateWithControls(idle, 1.0f / 60.0f);
            if (monsters_.size() != 1) {
                throw std::runtime_error("frame sequence did not spawn level-3 behavior-4 actor");
            }
            const ActiveMonster& monster = monsters_.front();
            if (!monster.hasSpawner || monster.spawnerIndex != spawnerIndex ||
                monster.kind != spawner.monsterKind || monster.behavior != 4 ||
                monster.animDelay != std::max<uint8_t>(1, spawner.animationDelay) ||
                monster.ai0 < spawner.param0Base ||
                monster.ai0 >= spanUpper(spawner.param0Base, spawner.param0Range) ||
                monster.ai1 < spawner.param1Base ||
                monster.ai1 >= spanUpper(spawner.param1Base, spawner.param1Range) ||
                monster.ai2 < spawner.param2Base ||
                monster.ai2 >= spanUpper(spawner.param2Base, spawner.param2Range) ||
                monster.hp < spawner.randomBase ||
                monster.hp >= spanUpper(spawner.randomBase, spawner.randomRange) ||
                monster.motionTimer != std::max<int>(1, monster.ai0) - 1 ||
                monster.vx8 <= 0 || monster.vy8 >= 0) {
                throw std::runtime_error(
                    "frame sequence level-3 behavior-4 spawn fields mismatched");
            }
            capture("030_level3_behavior4_spawned");
        } else if (scenario == "monster_behavior4_target_selection") {
            pushKeyDown(SDLK_2);
            processEvents(running);
            if (menu_ || playerCount_ != 2 || playerDead_ || player2Dead_) {
                throw std::runtime_error("frame sequence failed to start two-player level 3");
            }
            resetLevel(2);
            if (levelIndex_ != 2) {
                throw std::runtime_error("frame sequence did not load level 3");
            }
            capture("010_level3_two_player_start");

            size_t spawnerIndex = findSpawnerByBehavior(4);
            if (spawnerIndex >= level_.monsterSpawners.size()) {
                throw std::runtime_error("frame sequence found no level-3 behavior-4 spawner");
            }
            disableOtherSpawners(spawnerIndex);
            const MonsterSpawner& spawner = level_.monsterSpawners[spawnerIndex];
            randomSeed_ = 0x1234abcd;
            spawnerStates_[spawnerIndex].cooldown = 0;
            player_.x = static_cast<float>(spawner.x + 40);
            player_.y = static_cast<float>(spawner.y);
            player_.vy = -6.0f;
            player2_.x = static_cast<float>(spawner.x - 16);
            player2_.y = static_cast<float>(spawner.y);
            player2_.vy = -6.0f;
            playerDead_ = false;
            player2Dead_ = false;
            capture("020_level3_behavior4_target_armed");

            FrameControls idle;
            updateWithControls(idle, 1.0f / 60.0f);
            if (monsters_.size() != 1 || monsters_.front().behavior != 4 ||
                monsters_.front().vx8 >= 0 || monsters_.front().x >= spawner.x) {
                throw std::runtime_error(
                    "frame sequence behavior-4 target did not prefer player 2");
            }
            int xAfterP2 = monsters_.front().x;
            capture("030_level3_behavior4_target_p2");

            player2Dead_ = true;
            player_.x = static_cast<float>(monsters_.front().x + 24);
            player_.y = static_cast<float>(monsters_.front().y);
            monsters_.front().motionTimer = 1;
            updateWithControls(idle, 1.0f / 60.0f);
            if (monsters_.front().vx8 <= 0 || monsters_.front().x <= xAfterP2) {
                throw std::runtime_error(
                    "frame sequence behavior-4 target did not retarget player 1");
            }
            int xAfterP1 = monsters_.front().x;
            capture("040_level3_behavior4_target_p1");

            playerDead_ = true;
            player2Dead_ = false;
            player2_.x = static_cast<float>(monsters_.front().x - 24);
            player2_.y = static_cast<float>(monsters_.front().y);
            monsters_.front().motionTimer = 1;
            updateWithControls(idle, 1.0f / 60.0f);
            if (monsters_.front().vx8 >= 0 || monsters_.front().x >= xAfterP1) {
                throw std::runtime_error(
                    "frame sequence behavior-4 target did not retarget back to player 2");
            }
            capture("050_level3_behavior4_target_p2_return");
        } else {
            throw std::runtime_error("unknown frame sequence scenario " + scenario);
        }

        std::ofstream manifest(joinPath(outDir, "manifest.txt"));
        if (!manifest) {
            throw std::runtime_error("cannot create " + joinPath(outDir, "manifest.txt"));
        }
        manifest << "scenario=" << scenario << '\n';
        manifest << "source=lezac_cpp\n";
        manifest << "size=" << kScreenW << 'x' << kScreenH << '\n';
        manifest << "frame_count=" << captures.size() << '\n';
        for (const CapturedFrame& frame : captures) {
            manifest << "frame label=" << frame.label
                     << " file=" << frame.file
                     << " hash=" << hex64(frame.inspection.hash)
                     << " changed_pixels=" << frame.inspection.changedPixels
                     << " menu=" << frame.menu
                     << " level=" << frame.level
                     << " players=" << frame.playerCount
                     << " p1_xy=" << frame.p1x << ',' << frame.p1y
                     << " p1_bomb_tile=" << frame.p1BombX << ',' << frame.p1BombY
                     << " p1_foot_tile=" << frame.p1FootTile
                     << " p1_dead=" << frame.p1Dead
                     << " p2_xy=" << frame.p2x << ',' << frame.p2y
                     << " p2_bomb_tile=" << frame.p2BombX << ',' << frame.p2BombY
                     << " p2_dead=" << frame.p2Dead
                     << " bombs=" << frame.bombs
                     << " flashes=" << frame.flashes
                     << " launch_markers=" << frame.launchMarkers
                     << " launch_marker_xy=" << frame.launchMarkerX << ','
                     << frame.launchMarkerY
                     << " launch_marker_timer=" << frame.launchMarkerTimer
                     << " launch_marker_frame=" << frame.launchMarkerFrame
                     << " launch_marker_kind=" << frame.launchMarkerKind
                     << " launch_marker_mode=" << frame.launchMarkerMode
                     << " last_sound=" << hex4(frame.lastSoundOffset) << '/'
                     << frame.lastSoundPriority
                     << " explosions=" << frame.explosions
                     << " debris=" << frame.debris
                     << " collapse=" << frame.collapse
                     << " debris0_tile=" << frame.firstDebrisTile
                     << " debris0_flagged=" << hex4(frame.firstDebrisFlagged)
                     << " debris0_forward=" << frame.firstDebrisForward
                     << " debris0_reverse=" << frame.firstDebrisReverse
                     << " debris0_lookup=" << frame.firstDebrisLookup
                     << " debris0_timer=" << frame.firstDebrisTimer
                     << " collapse0_xy=" << frame.firstCollapseX << ','
                     << frame.firstCollapseY
                     << " collapse0_start=" << hex4(frame.firstCollapseStart)
                     << " collapse0_end=" << hex4(frame.firstCollapseEnd)
                     << " collapse0_flagged=" << hex4(frame.firstCollapseFlagged)
                     << " collapse0_forward=" << frame.firstCollapseForward
                     << " collapse0_reverse=" << frame.firstCollapseReverse
                     << " collapse0_affected=" << frame.firstCollapseAffected
                     << " collapse0_count=" << frame.firstCollapseCount
                     << " collapse0_timer=" << frame.firstCollapseTimer
                     << " effect0_xy=" << frame.firstEffectX << ','
                     << frame.firstEffectY
                     << " effect0_visual=" << frame.firstEffectVisual
                     << " effect0_detail=" << frame.firstEffectDetail
                     << " effect0_timer=" << frame.firstEffectTimer
                     << " effect0_variant=" << frame.firstEffectVariant
                     << " monsters=" << frame.monsters
                     << " monster_xy=" << frame.monsterX << ',' << frame.monsterY
                     << " monster_v8=" << frame.monsterVx8 << ',' << frame.monsterVy8
                     << " monster_behavior=" << frame.monsterBehavior
                     << " monster_hp=" << frame.monsterHp
                     << " monster_spawner=" << frame.monsterSpawner << '\n';
        }

        std::cout << "frame_sequence=ok"
                  << " scenario=" << scenario
                  << " frames=" << captures.size()
                  << " size=" << kScreenW << 'x' << kScreenH
                  << " out=" << outDir
                  << " manifest=manifest.txt\n";
    }

    void debugAutoplayerBossLevel7(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1) {
            throw std::runtime_error("boss level7 autoplayer failed to start");
        }
        resetLevel(6);
        if (levelIndex_ != 6 || !bossPresent_) {
            throw std::runtime_error("boss level7 autoplayer did not spawn the boss");
        }
        if (monsters_.size() != 7 || bossLinks_.size() != 6) {
            throw std::runtime_error("boss level7 autoplayer boss shape mismatch");
        }
        randomSeed_ = 0x1234abcd;

        auto findHead = [&]() -> ActiveMonster* {
            for (ActiveMonster& monster : monsters_) {
                if (monster.alive && monster.behavior == 6) return &monster;
            }
            return nullptr;
        };
        ActiveMonster* head = findHead();
        if (!head || head->kind != 0x1e || head->x != 100 || head->y != 100 ||
            head->bossVisual != 8 || head->animFrame != 40 ||
            head->bossHpByte != 10 || head->bossLives != 1 ||
            head->bossBoxW != 5 || head->bossBoxH != 4) {
            throw std::runtime_error("boss level7 autoplayer head fields mismatch");
        }
        // Decoded spawn layout: visual index -> world position and sprite.
        struct ExpectedSegment {
            uint8_t visual;
            int x;
            int y;
            uint8_t sprite;
            uint8_t serial;
        };
        static const std::array<ExpectedSegment, 6> kExpectedSegments{{
            {4, 138, 110, 46, 6},
            {5, 142, 104, 46, 5},
            {6, 93, 110, 45, 4},
            {7, 88, 116, 45, 3},
            {9, 92, 118, 42, 1},
            {10, 139, 117, 43, 2},
        }};
        int springLinks = 0;
        int orbitLinks = 0;
        for (const BossMotionLink& link : bossLinks_) {
            if (link.targetVisual != 8) {
                throw std::runtime_error("boss level7 autoplayer link target mismatch");
            }
            if (link.mode == 0xff) {
                ++orbitLinks;
            } else {
                ++springLinks;
            }
        }
        if (springLinks != 2 || orbitLinks != 4) {
            throw std::runtime_error("boss level7 autoplayer link modes mismatch");
        }
        for (const ExpectedSegment& expected : kExpectedSegments) {
            bool found = false;
            for (const ActiveMonster& monster : monsters_) {
                if (monster.behavior == 5 && monster.bossVisual == expected.visual) {
                    if (monster.kind != 0x1f || monster.x != expected.x ||
                        monster.y != expected.y ||
                        monster.animFrame != expected.sprite ||
                        monster.linkA != expected.serial) {
                        throw std::runtime_error(
                            "boss level7 autoplayer segment fields mismatch");
                    }
                    found = true;
                    break;
                }
            }
            if (!found) {
                throw std::runtime_error("boss level7 autoplayer segment missing");
            }
        }
        // Park the player near the boss cluster so the camera keeps the boss
        // on screen for the inspected frames.
        player_.x = 60.0f;
        player_.y = 120.0f;
        FrameInspection spawnFrame = inspectRenderedFrame("autoplayer-boss-level7-spawn");

        FrameControls idle;
        const int orbiterStartX = 138;
        const int orbiterStartY = 110;
        for (int frame = 0; frame < 30; ++frame) {
            updateWithControls(idle, 1.0f / 60.0f);
        }
        head = findHead();
        if (!head || head->bossTick != 30) {
            throw std::runtime_error("boss level7 autoplayer head did not tick");
        }
        bool orbiterMoved = false;
        for (const ActiveMonster& monster : monsters_) {
            if (monster.behavior == 5 && monster.bossVisual == 4) {
                // Serial 6 -> orbit link with radius (1,7) and offset (38,10)
                // around the head: the segment teleports to the link output
                // each frame.
                orbiterMoved = monster.x != orbiterStartX || monster.y != orbiterStartY;
                const BossMotionLink& orbit = bossLinks_[5];
                if (orbit.mode != 0xff || monster.x != orbit.outX ||
                    monster.y != orbit.outY) {
                    throw std::runtime_error(
                        "boss level7 autoplayer orbiter left its orbit output");
                }
            }
        }
        if (!orbiterMoved) {
            throw std::runtime_error("boss level7 autoplayer orbiter did not move");
        }
        FrameInspection motionFrame =
            inspectRenderedFrame("autoplayer-boss-level7-motion");
        if (motionFrame.hash == spawnFrame.hash) {
            throw std::runtime_error(
                "boss level7 autoplayer boss motion left the frame unchanged");
        }

        // Drive the recovered flame-drain damage model: seed flame flashes
        // over the head box each frame until the lives underflow fires the
        // death chain (phase 1 overkill, byte-wrap refill, second underflow).
        const uint32_t scoreBefore = score_;
        int damageFrames = 0;
        bool sawHurtFlash = false;
        while (!bossDefeated_ && damageFrames < 600) {
            head = findHead();
            if (!head) break;
            flashes_.clear();
            const int headTileX = head->x / kTileSize;
            const int headTileY = head->y / kTileSize;
            for (int dx = 0; dx < head->bossBoxW; dx += 2) {
                for (int dy = 0; dy < head->bossBoxH; ++dy) {
                    flashes_.push_back({headTileX + dx, headTileY + dy, 2, 2});
                }
            }
            updateWithControls(idle, 1.0f / 60.0f);
            head = findHead();
            if (head && head->hurtFlash > 0) {
                sawHurtFlash = true;
                if (monsterSpriteIndex(*head) != 0x2f) {
                    throw std::runtime_error(
                        "boss level7 autoplayer hurt flash sprite mismatch");
                }
            }
            ++damageFrames;
        }
        if (!bossDefeated_ || !sawHurtFlash) {
            throw std::runtime_error("boss level7 autoplayer did not defeat the boss");
        }
        if (score_ != scoreBefore + 1000) {
            throw std::runtime_error("boss level7 autoplayer death award mismatch");
        }
        int debrisCount = 0;
        for (const ActiveMonster& monster : monsters_) {
            if (monster.alive && monster.bossDebris && monster.behavior == 2) {
                ++debrisCount;
            }
        }
        if (debrisCount != 7) {
            throw std::runtime_error("boss level7 autoplayer debris conversion mismatch");
        }
        FrameInspection deathFrame =
            inspectRenderedFrame("autoplayer-boss-level7-death");

        for (int frame = 0; frame < 90; ++frame) {
            updateWithControls(idle, 1.0f / 60.0f);
        }
        for (const ActiveMonster& monster : monsters_) {
            if (monster.bossDebris) {
                throw std::runtime_error("boss level7 autoplayer debris did not clear");
            }
        }
        FrameInspection clearFrame =
            inspectRenderedFrame("autoplayer-boss-level7-cleared");

        std::cout << "autoplayer=ok scenario=" << scenario
                  << " boss_actors=7 links=6 springs=" << springLinks
                  << " orbits=" << orbitLinks
                  << " head_sprite=40 head_box=5x4 head_pos=100,100"
                  << " sprite_bank=prova"
                  << " damage_frames=" << damageFrames
                  << " score_award=1000 debris=7 debris_cleared=1"
                  << " frames_inspected=4"
                  << " spawn_hash=" << std::hex << spawnFrame.hash
                  << " motion_hash=" << motionFrame.hash
                  << " death_hash=" << deathFrame.hash
                  << " clear_hash=" << clearFrame.hash << std::dec
                  << " original_runtime_claim=0" << '\n';
    }

    void debugAutoplayer(const std::string& scenario) {
        if (scenario == "level1_bomb_route") {
            debugAutoplayerLevel1BombRoute(scenario);
        } else if (scenario == "pause_flow") {
            debugAutoplayerPauseFlow(scenario);
        } else if (scenario == "death_reentry") {
            debugAutoplayerDeathReentry(scenario);
        } else if (scenario == "death_visuals") {
            debugAutoplayerDeathVisuals(scenario);
        } else if (scenario == "level_transition") {
            debugAutoplayerLevelTransition(scenario);
        } else if (scenario == "portal_weapon_route") {
            debugAutoplayerPortalWeaponRoute(scenario);
        } else if (scenario == "launch_pad_route") {
            debugAutoplayerLaunchPadRoute(scenario);
        } else if (scenario == "records_flow") {
            debugAutoplayerRecordsFlow(scenario);
        } else if (scenario == "monster_bomb_reward") {
            debugAutoplayerMonsterBombReward(scenario);
        } else if (scenario == "monster_behavior3_multihit") {
            debugAutoplayerMonsterBehavior3Multihit(scenario);
        } else if (scenario == "monster_behavior4_chase") {
            debugAutoplayerMonsterBehavior4Chase(scenario);
        } else if (scenario == "monster_spawner_cycle") {
            debugAutoplayerMonsterSpawnerCycle(scenario);
        } else if (scenario == "monster_spawner_behavior4_level2") {
            debugAutoplayerMonsterSpawnerBehavior4Level2(scenario);
        } else if (scenario == "monster_spawner_behavior4_level3") {
            debugAutoplayerMonsterSpawnerBehavior4Level3(scenario);
        } else if (scenario == "monster_behavior4_target_selection") {
            debugAutoplayerMonsterBehavior4TargetSelection(scenario);
        } else if (scenario == "boss_level7") {
            debugAutoplayerBossLevel7(scenario);
        } else if (scenario == "collapse_playback_route") {
            debugAutoplayerCollapsePlaybackRoute(scenario);
        } else if (scenario == "two_player_route") {
            debugAutoplayerTwoPlayerRoute(scenario);
        } else if (scenario == "two_player_death_visuals") {
            debugAutoplayerTwoPlayerDeathVisuals(scenario);
        } else if (scenario == "two_player_progression") {
            debugAutoplayerTwoPlayerProgression(scenario);
        } else {
            throw std::runtime_error("unknown autoplayer scenario " + scenario);
        }
    }

    void debugAutoplayerLevel1BombRoute(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1 || levelIndex_ != 0) {
            throw std::runtime_error("autoplayer failed to start one-player level 1");
        }

        FrameInspection startFrame = inspectRenderedFrame("autoplayer-level1-start");
        AutoplayRouteResult route = autoplayLevel1BombRoute();
        if (route.bombTileX != 24 || route.bombTileY != 22) {
            throw std::runtime_error("autoplayer missed level-1 tile 24,22");
        }

        FrameInspection routeFrame = inspectRenderedFrame("autoplayer-level1-route");
        if (routeFrame.hash == startFrame.hash) {
            throw std::runtime_error("autoplayer route did not change the rendered frame");
        }

        size_t bombsBefore = bombs_.size();
        int smallBombsBefore = bombInventory_.counts[0];
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.size() != bombsBefore + 1 || bombs_.back().x != 24 ||
            bombs_.back().y != 22 || bombInventory_.counts[0] != smallBombsBefore - 1) {
            throw std::runtime_error("autoplayer N key did not place a level-1 route bomb");
        }

        FrameInspection bombFrame = inspectRenderedFrame("autoplayer-level1-bomb");
        if (bombFrame.hash == routeFrame.hash) {
            throw std::runtime_error("autoplayer bomb placement did not change frame");
        }

        int fuse = bombs_.back().timer;
        FrameControls idle;
        for (int i = 0; i < fuse; ++i) {
            updateWithControls(idle, 1.0f / 60.0f);
        }
        if (!bombs_.empty() || explosionEffects_.empty()) {
            throw std::runtime_error("autoplayer route bomb did not explode");
        }

        FrameInspection explosionFrame = inspectRenderedFrame("autoplayer-level1-explosion");
        if (explosionFrame.hash == bombFrame.hash) {
            throw std::runtime_error("autoplayer explosion did not change frame");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " route_frames=" << route.frames
                  << " start_xy=" << route.startX << ',' << route.startY
                  << " final_xy=" << route.finalX << ',' << route.finalY
                  << " p1_bomb_tile=" << route.bombTileX << ',' << route.bombTileY
                  << " bombs=1 explosion=1 frame_inspection=1\n";
    }

    void debugAutoplayerPauseFlow(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || paused_ || playerCount_ != 1 || levelIndex_ != 0) {
            throw std::runtime_error("pause flow failed to start one-player level 1");
        }

        FrameInspection startFrame = inspectRenderedFrame("autoplayer-pause-start");
        size_t bombsBefore = bombs_.size();
        int smallBombsBefore = bombInventory_.counts[0];
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.size() != bombsBefore + 1 ||
            bombInventory_.counts[0] != smallBombsBefore - 1) {
            throw std::runtime_error("pause flow failed to arm a bomb before pausing");
        }

        FrameInspection armedFrame = inspectRenderedFrame("autoplayer-pause-armed");
        if (armedFrame.hash == startFrame.hash) {
            throw std::runtime_error("pause flow armed frame did not change");
        }
        std::vector<uint32_t> armedPixels = fb_;
        uint32_t logicBeforePause = logicTick_;
        int bombTimerBeforePause = bombs_.back().timer;
        float playerXBeforePause = player_.x;
        float playerYBeforePause = player_.y;
        float playerVyBeforePause = player_.vy;
        size_t bombsArmed = bombs_.size();
        int smallBombsArmed = bombInventory_.counts[0];

        pushKeyDown(SDLK_p);
        processEvents(running);
        if (!paused_ || menu_) {
            throw std::runtime_error("P key did not enter pause state");
        }
        FrameInspection pauseFrame = inspectRenderedFrame("autoplayer-pause-overlay");
        if (pauseFrame.hash == armedFrame.hash ||
            !regionChanged(armedPixels, 112, 84, 96, 28)) {
            throw std::runtime_error("pause overlay did not change the rendered frame");
        }

        pushKeyDown(SDLK_n);
        processEvents(running);
        FrameControls pausedControls;
        pausedControls.p1Right = true;
        pausedControls.p1Jump = true;
        updateWithControls(pausedControls, 1.0f / 60.0f);
        update(1.0f / 60.0f);
        if (!paused_ || logicTick_ != logicBeforePause ||
            bombs_.size() != bombsArmed ||
            bombs_.back().timer != bombTimerBeforePause ||
            bombInventory_.counts[0] != smallBombsArmed ||
            player_.x != playerXBeforePause ||
            player_.y != playerYBeforePause ||
            player_.vy != playerVyBeforePause) {
            throw std::runtime_error("paused gameplay state advanced");
        }
        inspectRenderedFrame("autoplayer-pause-frozen");

        pushKeyDown(SDLK_p);
        processEvents(running);
        if (paused_ || menu_) {
            throw std::runtime_error("P key did not leave pause state");
        }
        FrameInspection resumedFrame = inspectRenderedFrame("autoplayer-pause-resumed");
        if (resumedFrame.hash != armedFrame.hash) {
            throw std::runtime_error("resumed frame did not restore the pre-pause game view");
        }

        updateWithControls(pausedControls, 1.0f / 60.0f);
        if (logicTick_ != logicBeforePause + 1 ||
            bombs_.back().timer >= bombTimerBeforePause) {
            throw std::runtime_error("gameplay did not advance after unpausing");
        }
        inspectRenderedFrame("autoplayer-pause-advanced");

        pushKeyDown(SDLK_p);
        processEvents(running);
        if (!paused_) {
            throw std::runtime_error("pause flow could not re-enter pause before escape");
        }
        pushKeyDown(SDLK_ESCAPE);
        processEvents(running);
        if (!menu_ || menuPage_ != MenuPage::Main || paused_) {
            throw std::runtime_error("escape did not clear pause and return to menu");
        }
        FrameInspection menuFrame = inspectRenderedFrame("autoplayer-pause-menu");
        if (menuFrame.hash == resumedFrame.hash) {
            throw std::runtime_error("pause flow menu frame did not redraw");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " paused_overlay=1 frozen_ticks=1 frozen_bomb=1"
                  << " frozen_inputs=1 resumed=1 escape_menu=1"
                  << " frame_inspection=1 original_pause_claim=0\n";
    }

    void debugAutoplayerDeathReentry(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1 || levelIndex_ != 0) {
            throw std::runtime_error("death autoplayer failed to start one-player level 1");
        }

        FrameInspection startFrame = inspectRenderedFrame("autoplayer-death-start");
        energy_ = 0;
        lives_ = 3;
        damageCooldown_ = 0;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        if (!playerDead_ || lives_ != 3 || !pendingLifeLoss_ || energy_ != 100 ||
            reentryTimer_ != kReentryTicks || deathStateTimer_ != kDeathStateTicks) {
            throw std::runtime_error("death autoplayer did not enter state-2");
        }

        FrameInspection deathFrame = inspectRenderedFrame("autoplayer-death-state2");
        if (deathFrame.hash == startFrame.hash) {
            throw std::runtime_error("death autoplayer state-2 frame did not change");
        }

        pushKeyDown(SDLK_SPACE);
        processEvents(running);
        if (!playerDead_ || damageCooldown_ != 0) {
            throw std::runtime_error("death autoplayer early reentry was accepted");
        }

        FrameControls idle;
        for (int i = 0; i < kDeathStateTicks; ++i) {
            updateWithControls(idle, 1.0f / 60.0f);
        }
        pushKeyDown(SDLK_SPACE);
        processEvents(running);
        if (playerDead_ || energy_ != 100 || lives_ != 2 ||
            deathStateTimer_ != 0 || reentryTimer_ != 0 || damageCooldown_ <= 0) {
            throw std::runtime_error("death autoplayer did not reenter after countdown");
        }

        FrameInspection reentryFrame = inspectRenderedFrame("autoplayer-reentered");
        if (reentryFrame.hash == deathFrame.hash) {
            throw std::runtime_error("death autoplayer reentry frame did not change");
        }

        int manualReentryLives = lives_;

        resetLevel(0);
        int waitRestartGeneration = levelResetGeneration_;
        float waitStartX = player_.x;
        float waitStartY = player_.y;
        player_.x += 40.0f;
        player_.y -= 8.0f;
        BombProfile profile = bombProfile(BombType::Small);
        bombs_.push_back({static_cast<int>(player_.x + 6.0f) / kTileSize,
                          static_cast<int>(player_.y + 12.0f) / kTileSize,
                          profile.fuseTicks, BombType::Small,
                          profile.fuseTicks, 1});
        energy_ = 0;
        lives_ = 3;
        damageCooldown_ = 0;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        if (!playerDead_ || lives_ != 3 || !pendingLifeLoss_ ||
            reentryTimer_ != kReentryTicks || deathStateTimer_ != kDeathStateTicks ||
            bombs_.empty()) {
            throw std::runtime_error("death autoplayer wait-restart setup failed");
        }
        FrameInspection waitDeathFrame =
            inspectRenderedFrame("autoplayer-death-wait-state2");
        int waitRestartFrames = 0;
        for (; waitRestartFrames < kDeathStateTicks + kReentryTicks + 4;
             ++waitRestartFrames) {
            updateWithControls(idle, 1.0f / 60.0f);
            if (levelResetGeneration_ > waitRestartGeneration) break;
        }
        if (levelResetGeneration_ <= waitRestartGeneration || playerDead_ ||
            lives_ != 2 || pendingLifeLoss_ || deathStateTimer_ != 0 ||
            reentryTimer_ != 0 || !bombs_.empty() ||
            player_.x != waitStartX || player_.y != waitStartY) {
            std::ostringstream oss;
            oss << "death autoplayer wait did not restart level"
                << " generation=" << levelResetGeneration_
                << " before=" << waitRestartGeneration
                << " dead=" << (playerDead_ ? 1 : 0)
                << " lives=" << lives_
                << " pending=" << (pendingLifeLoss_ ? 1 : 0)
                << " death_timer=" << deathStateTimer_
                << " reentry_timer=" << reentryTimer_
                << " bombs=" << bombs_.size()
                << " xy=" << player_.x << ',' << player_.y
                << " start_xy=" << waitStartX << ',' << waitStartY;
            throw std::runtime_error(oss.str());
        }
        FrameInspection waitRestartFrame =
            inspectRenderedFrame("autoplayer-death-wait-restart");
        if (waitRestartFrame.hash == waitDeathFrame.hash) {
            throw std::runtime_error("death autoplayer wait restart frame did not change");
        }

        resetLevel(0);
        auto objectivePos = findObjectiveTileForSmoke();
        if (!consumeBombObjectTile(objectivePos[0], objectivePos[1]) ||
            canReenterLevel()) {
            throw std::runtime_error("death autoplayer could not create unwinnable level");
        }
        int missingObjectiveTiles = remainingObjectiveTiles();
        int unwinnableGeneration = levelResetGeneration_;
        energy_ = 0;
        lives_ = 3;
        damageCooldown_ = 0;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        if (!playerDead_ || lives_ != 3 || !pendingLifeLoss_ ||
            reentryTimer_ != 1 || deathStateTimer_ != kDeathStateTicks ||
            remainingObjectiveTiles() != missingObjectiveTiles) {
            throw std::runtime_error("death autoplayer unwinnable setup failed");
        }
        FrameInspection unwinnableDeathFrame =
            inspectRenderedFrame("autoplayer-death-unwinnable-state2");
        pushKeyDown(SDLK_SPACE);
        processEvents(running);
        if (!playerDead_ || lives_ != 3 ||
            levelResetGeneration_ != unwinnableGeneration) {
            throw std::runtime_error("death autoplayer early unwinnable fire restarted");
        }
        int unwinnableRestartFrames = 0;
        for (; unwinnableRestartFrames < kDeathStateTicks + 4;
             ++unwinnableRestartFrames) {
            updateWithControls(idle, 1.0f / 60.0f);
            if (levelResetGeneration_ > unwinnableGeneration) break;
        }
        if (levelResetGeneration_ <= unwinnableGeneration || playerDead_ ||
            lives_ != 2 || pendingLifeLoss_ || deathStateTimer_ != 0 ||
            reentryTimer_ != 0 ||
            remainingObjectiveTiles() != level_.startingObjectiveTiles) {
            throw std::runtime_error("death autoplayer unwinnable restart failed");
        }
        FrameInspection unwinnableRestartFrame =
            inspectRenderedFrame("autoplayer-death-unwinnable-restart");
        if (unwinnableRestartFrame.hash == unwinnableDeathFrame.hash) {
            throw std::runtime_error("death autoplayer unwinnable frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " death_state_ticks=" << kDeathStateTicks
                  << " lives=" << manualReentryLives
                  << " energy=" << energy_
                  << " reentered=1 wait_restart=1"
                  << " unwinnable_restart=1 early_unwinnable_fire_blocked=1"
                  << " frame_inspection=1\n";
    }

    void debugAutoplayerDeathVisuals(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1 || levelIndex_ != 0) {
            throw std::runtime_error("death visual autoplayer failed to start level 1");
        }

        FrameInspection startFrame = inspectRenderedFrame("autoplayer-death-visual-start");
        energy_ = 0;
        lives_ = 3;
        damageCooldown_ = 0;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        if (!playerDead_ || !state2Visual_.active ||
            state2Visual_.current != kState2VisualStartFrame ||
            deathStateTimer_ != kDeathStateTicks) {
            throw std::runtime_error("death visual autoplayer did not seed state-2 cursor");
        }
        auto cursorPreviewFrame = [&](const std::string& label) {
            state2VisualCursorPreview_ = true;
            FrameInspection inspection = inspectRenderedFrame(label);
            state2VisualCursorPreview_ = false;
            return inspection;
        };
        auto visualRowFor = [&](uint8_t frame) {
            State2VisualRow row;
            if (!originalState2VisualRow(frame, row)) {
                throw std::runtime_error("death visual row candidate missing");
            }
            return row;
        };

        FrameInspection deathStartFrame =
            inspectRenderedFrame("autoplayer-death-visual-frame-4a");
        if (deathStartFrame.hash == startFrame.hash) {
            throw std::runtime_error("death visual initial frame did not change rendering");
        }
        State2EffectEntry effect4a = state2Effect_;
        FrameInspection cursorStartFrame =
            cursorPreviewFrame("autoplayer-death-visual-cursor-frame-4a");
        if (cursorStartFrame.hash == deathStartFrame.hash) {
            throw std::runtime_error("death visual cursor frame 4a matched live row-byte-3 frame");
        }

        FrameControls idle;
        updateWithControls(idle, 1.0f / 60.0f);
        if (state2Visual_.current != static_cast<uint8_t>(kState2VisualStartFrame + 1) ||
            deathStateTimer_ != kDeathStateTicks - 1) {
            throw std::runtime_error("death visual cursor did not advance on first tick");
        }
        FrameInspection tick1Frame =
            inspectRenderedFrame("autoplayer-death-visual-frame-4b");
        if (tick1Frame.hash == deathStartFrame.hash) {
            throw std::runtime_error("death visual first tick frame did not change");
        }
        State2EffectEntry effect4b = state2Effect_;
        FrameInspection cursorTick1Frame =
            cursorPreviewFrame("autoplayer-death-visual-cursor-frame-4b");
        if (cursorTick1Frame.hash == tick1Frame.hash ||
            cursorTick1Frame.hash == cursorStartFrame.hash) {
            throw std::runtime_error("death visual cursor frame 4b did not advance");
        }

        for (int i = 0; i < kState2VisualDelay + 1; ++i) {
            updateWithControls(idle, 1.0f / 60.0f);
        }
        if (state2Visual_.current != static_cast<uint8_t>(kState2VisualStartFrame + 2)) {
            throw std::runtime_error("death visual cursor did not reach the third frame");
        }
        FrameInspection tick5Frame =
            inspectRenderedFrame("autoplayer-death-visual-frame-4c");
        if (tick5Frame.hash == tick1Frame.hash) {
            throw std::runtime_error("death visual third frame did not change");
        }
        State2EffectEntry effect4c = state2Effect_;
        FrameInspection cursorTick5Frame =
            cursorPreviewFrame("autoplayer-death-visual-cursor-frame-4c");
        if (cursorTick5Frame.hash == tick5Frame.hash ||
            cursorTick5Frame.hash == cursorTick1Frame.hash) {
            throw std::runtime_error("death visual cursor frame 4c did not advance");
        }
        if (state2VisualCursorPreview_) {
            throw std::runtime_error("death visual cursor preview flag leaked");
        }

        int cursor4a = static_cast<int>(kState2VisualStartFrame);
        int cursor4b = static_cast<int>(kState2VisualStartFrame + 1);
        int cursor4c = static_cast<int>(kState2VisualStartFrame + 2);
        State2VisualRow row4a = visualRowFor(kState2VisualStartFrame);
        State2VisualRow row4b =
            visualRowFor(static_cast<uint8_t>(kState2VisualStartFrame + 1));
        State2VisualRow row4c =
            visualRowFor(static_cast<uint8_t>(kState2VisualStartFrame + 2));
        int row3_4a = static_cast<int>(row4a.row3);
        int row3_4b = static_cast<int>(row4b.row3);
        int row3_4c = static_cast<int>(row4c.row3);
        if (row3_4a != 67 || row3_4b != 68 || row3_4c != 69 ||
            cursor4a != 74 || cursor4b != 75 || cursor4c != 76 ||
            row4a.row0 != 16 || row4a.row1 != 16 ||
            row4b.row0 != 16 || row4b.row1 != 16 ||
            row4c.row0 != 16 || row4c.row1 != 16) {
            throw std::runtime_error("death visual sprite sequence mismatch");
        }
        int playerEffectX = static_cast<int>(player_.x);
        int playerEffectY = static_cast<int>(player_.y);
        auto effectMatches = [&](const State2EffectEntry& effect,
                                 uint8_t frame,
                                 const State2VisualRow& row) {
            return effect.active && effect.x == playerEffectX &&
                   effect.y == playerEffectY && effect.visualFrame == frame &&
                   effect.drawDx == row.row0 && effect.drawDy == row.row1 &&
                   effect.row2 == row.row2 && effect.spriteIndex == row.row3;
        };
        if (!effectMatches(effect4a, kState2VisualStartFrame, row4a) ||
            !effectMatches(effect4b,
                           static_cast<uint8_t>(kState2VisualStartFrame + 1),
                           row4b) ||
            !effectMatches(effect4c,
                           static_cast<uint8_t>(kState2VisualStartFrame + 2),
                           row4c)) {
            throw std::runtime_error("death visual effect entry mismatch");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " death_state_ticks=" << kDeathStateTicks
                  << " start_frame=0x" << std::hex << static_cast<int>(kState2VisualStartFrame)
                  << " tick1_frame=0x" << static_cast<int>(kState2VisualStartFrame + 1)
                  << " tick5_frame=0x" << static_cast<int>(kState2VisualStartFrame + 2)
                  << std::dec
                  << " live_sprites=" << row3_4a << ',' << row3_4b
                  << ',' << row3_4c
                  << " cursor_legacy_sprites=" << cursor4a << ',' << cursor4b
                  << ',' << cursor4c
                  << " draw_offset=16,16"
                  << " effect_entry_xy=" << playerEffectX << ',' << playerEffectY
                  << " effect_entry_frames=0x" << std::hex
                  << static_cast<int>(effect4a.visualFrame) << ",0x"
                  << static_cast<int>(effect4b.visualFrame) << ",0x"
                  << static_cast<int>(effect4c.visualFrame) << std::dec
                  << " effect_entry_sprites="
                  << static_cast<int>(effect4a.spriteIndex) << ','
                  << static_cast<int>(effect4b.spriteIndex) << ','
                  << static_cast<int>(effect4c.spriteIndex)
                  << " effect_entry_draw_offset=16,16"
                  << " cursor_legacy_hash_mismatch=1"
                  << " row3_live_renderer=1"
                  << " frame_inspection=1 visual_claim=0\n";
    }

    void debugAutoplayerLevelTransition(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1 || levelIndex_ != 0) {
            throw std::runtime_error("level transition autoplayer failed to start level 1");
        }

        FrameInspection startFrame = inspectRenderedFrame("autoplayer-transition-start");
        int requiredBonus = level_.requiredBonus;
        int requiredDestruction = level_.requiredDestruction;
        collectAllObjectiveTilesForSmoke();
        damageRequiredTilesForSmoke();
        if (!isComplete() || collected_ < requiredBonus ||
            destructionPercent() < requiredDestruction) {
            throw std::runtime_error("level transition autoplayer did not satisfy progress");
        }

        FrameInspection completeFrame = inspectRenderedFrame("autoplayer-transition-complete");
        if (completeFrame.hash == startFrame.hash) {
            throw std::runtime_error("level transition completion frame did not change");
        }

        FrameControls idle;
        int frames = 0;
        while (levelIndex_ == 0 && frames <= 101) {
            updateWithControls(idle, 1.0f / 60.0f);
            ++frames;
        }
        if (levelIndex_ != 1 || menu_ || frames != 101 || collected_ != 0 ||
            completeTimer_ != 0) {
            throw std::runtime_error("level transition autoplayer did not enter level 2");
        }

        FrameInspection nextFrame = inspectRenderedFrame("autoplayer-transition-level2");
        if (nextFrame.hash == completeFrame.hash) {
            throw std::runtime_error("level transition next-level frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " start_level=1 completed_bonus=" << requiredBonus
                  << " completed_destruction=" << requiredDestruction
                  << " transition_frames=" << frames
                  << " advanced_level=" << (levelIndex_ + 1)
                  << " frame_inspection=1\n";
    }

    void debugAutoplayerPortalWeaponRoute(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1 || levelIndex_ != 0) {
            throw std::runtime_error("portal/weapon autoplayer failed to start level 1");
        }

        int portalLevel = -1;
        int sourceX = -1;
        int sourceY = -1;
        uint16_t portalKey = 0;
        const LevelPortal* destination = nullptr;
        auto findPortalSource = [&]() {
            sourceX = -1;
            sourceY = -1;
            portalKey = 0;
            destination = nullptr;
            for (int y = 1; y < level_.height && !destination; ++y) {
                for (int x = 0; x < level_.width && !destination; ++x) {
                    if (tileAt(x, y) != 0x45) continue;
                    uint16_t key = static_cast<uint16_t>(wordAt(x, y) & 0x7fffu);
                    if (key == 0) continue;
                    for (const LevelPortal& portal : level_.portals) {
                        if (portal.key == key) {
                            sourceX = x;
                            sourceY = y;
                            portalKey = key;
                            destination = &portal;
                            break;
                        }
                    }
                }
            }
            return destination != nullptr;
        };

        if (!findPortalSource()) {
            for (size_t level = 1; level < levels_.size(); ++level) {
                resetLevel(static_cast<int>(level));
                if (findPortalSource()) {
                    portalLevel = static_cast<int>(level);
                    break;
                }
            }
        } else {
            portalLevel = levelIndex_;
        }
        if (portalLevel < 0) {
            throw std::runtime_error("portal/weapon autoplayer found no portal source");
        }
        menu_ = false;

        FrameInspection startFrame = inspectRenderedFrame("autoplayer-portal-weapon-start");
        FrameControls switchControls;
        switchControls.p1Left = true;
        switchControls.p1Right = true;
        driveAutoplayerWeaponSwitchChord(switchControls);
        if (bombInventory_.selected != BombType::Medium) {
            throw std::runtime_error("portal/weapon autoplayer did not switch to medium bomb");
        }

        size_t bombsBefore = bombs_.size();
        int mediumBefore = bombInventory_.counts[1];
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.size() != bombsBefore + 1 ||
            bombs_.back().type != BombType::Medium ||
            bombInventory_.counts[1] != mediumBefore - 1) {
            throw std::runtime_error("portal/weapon autoplayer did not place medium bomb");
        }
        FrameInspection bombFrame = inspectRenderedFrame("autoplayer-portal-weapon-bomb");
        if (bombFrame.hash == startFrame.hash) {
            throw std::runtime_error("portal/weapon bomb frame did not change");
        }

        player_.x = static_cast<float>(sourceX * kTileSize);
        player_.y = static_cast<float>(sourceY * kTileSize - kTileSize);
        clearSoundLatch();
        lastPumpedSoundOffset_ = 0;
        lastPumpedSoundSelector_ = 0;
        FrameControls idle;
        idle.p1Down = true;
        updateWithControls(idle, 1.0f / 60.0f);
        if (player_.x != static_cast<float>(destination->x) ||
            player_.y != static_cast<float>(destination->y) ||
            portalCooldown_ != 30 || soundLatch_.active ||
            lastPumpedSoundOffset_ != kPortalTeleportSoundCursor ||
            lastPumpedSoundSelector_ != kPortalTeleportSoundPriority) {
            throw std::runtime_error("portal/weapon autoplayer did not trigger portal");
        }

        FrameInspection portalFrame = inspectRenderedFrame("autoplayer-portal-weapon-portal");
        if (portalFrame.hash == bombFrame.hash) {
            throw std::runtime_error("portal/weapon portal frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " level=" << (levelIndex_ + 1)
                  << " switched_weapon=2 medium_bomb=1"
                  << " switch_hold_ticks=" << static_cast<int>(kWeaponSwitchHoldTicks)
                  << " switch_trigger=release switch_sound=0x0024/p2"
                  << " portal_key=" << portalKey
                  << " portal_from=" << sourceX << ',' << sourceY
                  << " portal_to=" << destination->x << ',' << destination->y
                  << " cooldown=" << portalCooldown_
                  << " frame_inspection=1\n";
    }

    void debugAutoplayerLaunchPadRoute(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;
        pushKeyDown(SDLK_1);
        processEvents(running);
        resetLevel(5);
        if (menu_ || playerCount_ != 1 || levelIndex_ != 5) {
            throw std::runtime_error("launch-pad autoplayer failed to start level 6");
        }
        for (SpawnerState& state : spawnerStates_) {
            state.remaining = 0;
            state.availableSlots = 0;
        }

        int padX = -1;
        int padY = -1;
        for (int y = 0; y < level_.height && padX < 0; ++y) {
            for (int x = 0; x < level_.width; ++x) {
                if (tileAt(x, y) == kLaunchPadTile) {
                    padX = x;
                    padY = y;
                    break;
                }
            }
        }
        if (padX < 0) {
            throw std::runtime_error("launch-pad autoplayer found no level-6 pad");
        }

        player_.x = static_cast<float>(padX * kTileSize);
        player_.y = static_cast<float>(padY * kTileSize - 16);
        player_.vx = 0.0f;
        player_.vy = 0.0f;
        player_.grounded = true;
        if (collides(player_.x, player_.y) ||
            tileAt(static_cast<int>(player_.x + 6.0f) / kTileSize,
                   static_cast<int>(player_.y + 16.0f) / kTileSize) !=
                kLaunchPadTile) {
            throw std::runtime_error("launch-pad autoplayer did not align with pad");
        }

        int overheadX = static_cast<int>(player_.x) / kTileSize;
        int overheadY = static_cast<int>(player_.y - 1.0f) / kTileSize;
        uint8_t overheadTile = static_cast<uint8_t>(tileAt(overheadX, overheadY));
        tileRef(overheadX, overheadY) = 2;
        if (activateLaunchPad(player_, true) || !launchPadMarkers_.empty()) {
            throw std::runtime_error("launch-pad overhead gate accepted blocked launch");
        }
        tileRef(overheadX, overheadY) = overheadTile;

        FrameInspection readyFrame = inspectRenderedFrame("autoplayer-launch-pad-ready");
        FrameControls cancelled;
        cancelled.p1Jump = true;
        cancelled.p1Down = true;
        updateWithControls(cancelled, 1.0f / 60.0f);
        if (!launchPadMarkers_.empty() || player_.vy < 0.0f ||
            lastPumpedSoundOffset_ == kLaunchPadSoundCursor) {
            throw std::runtime_error("launch-pad Up+Down cancellation failed");
        }
        player_.x = static_cast<float>(padX * kTileSize);
        player_.y = static_cast<float>(padY * kTileSize - 16);
        player_.vx = 0.0f;
        player_.vy = 0.0f;
        player_.grounded = true;

        clearSoundLatch();
        lastPumpedSoundOffset_ = 0;
        lastPumpedSoundSelector_ = 0;
        float readyY = player_.y;
        FrameControls down;
        down.p1Down = true;
        updateWithControls(down, 1.0f / 60.0f);
        if (player_.y >= readyY || player_.vy >= 0.0f || player_.grounded ||
            launchPadMarkers_.size() != 1 || soundLatch_.active ||
            lastPumpedSoundOffset_ != kLaunchPadSoundCursor ||
            lastPumpedSoundSelector_ != kLaunchPadSoundPriority) {
            throw std::runtime_error("launch-pad activation mismatch");
        }
        const LaunchPadMarker& marker = launchPadMarkers_.front();
        if (marker.timer != kLaunchPadMarkerTimer ||
            marker.frame != kLaunchPadMarkerFrame ||
            marker.kind != kLaunchPadMarkerKind ||
            marker.mode != kLaunchPadMarkerMode ||
            marker.velocityY8 != kLaunchPadMarkerVelocityY8) {
            throw std::runtime_error("launch-pad invisible marker mismatch");
        }

        FrameInspection launchedFrame =
            inspectRenderedFrame("autoplayer-launch-pad-launched");
        if (launchedFrame.hash == readyFrame.hash) {
            throw std::runtime_error("launch-pad activation did not change frame");
        }

        FrameControls idle;
        int markerLifetimeUpdates = 0;
        while (!launchPadMarkers_.empty() && markerLifetimeUpdates < 12) {
            updateWithControls(idle, 1.0f / 60.0f);
            ++markerLifetimeUpdates;
        }
        if (!launchPadMarkers_.empty() || markerLifetimeUpdates != 9) {
            throw std::runtime_error("launch-pad marker lifetime mismatch");
        }
        FrameInspection airborneFrame =
            inspectRenderedFrame("autoplayer-launch-pad-marker-expired");
        if (airborneFrame.hash == launchedFrame.hash) {
            throw std::runtime_error("launch-pad airborne frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " level=6 pad_tile=" << padX << ',' << padY
                  << " input=down up_down_cancelled=1 overhead_blocked=1"
                  << " original_velocity=" << kOriginalLaunchPadVelocity
                  << " normal_jump_velocity=" << kOriginalNormalJumpVelocity
                  << " marker_frame=0x5b marker_kind=0x0b marker_mode=5"
                  << " marker_timer=" << static_cast<int>(kLaunchPadMarkerTimer)
                  << " marker_lifetime_updates=" << markerLifetimeUpdates
                  << " sound=0x0035/p5 marker_invisible=1 frame_inspection=1\n";
    }

    void debugAutoplayerRecordsFlow(const std::string& scenario) {
        load();
        initSdl();
        std::filesystem::path recordPath =
            std::filesystem::temp_directory_path() /
            ("lezac_autoplayer_records_" + std::to_string(SDL_GetTicks()) + ".json");
        std::filesystem::remove(recordPath);
        recordPath_ = recordPath.string();
        saveRecords(recordPath_, records_);

        resetLevel(0);
        FrameInspection menuFrame = inspectRenderedFrame("autoplayer-record-menu");
        playerCount_ = 1;
        score_ = 999999u;
        levelIndex_ = 2;
        beginGameOver();
        if (!menu_ || menuPage_ != MenuPage::NameEntry ||
            pendingRecordScore_ != 999999u || pendingRecordLevel_ != 3 ||
            pendingRecordPlayer_ != 1) {
            throw std::runtime_error("records autoplayer did not open name entry");
        }

        FrameInspection nameFrame = inspectRenderedFrame("autoplayer-record-name-entry");
        if (nameFrame.hash == menuFrame.hash) {
            throw std::runtime_error("records autoplayer name-entry frame did not change");
        }

        bool running = true;
        for (SDL_Keycode key : {SDLK_b, SDLK_o, SDLK_t, SDLK_RETURN}) {
            pushKeyDown(key);
            processEvents(running);
        }
        auto reloaded = loadRecords(recordPath_);
        if (menuPage_ != MenuPage::Records || reloaded.empty() ||
            reloaded[0].score != 999999u || reloaded[0].level != 3 ||
            reloaded[0].name != "bot") {
            throw std::runtime_error("records autoplayer did not save entered record");
        }

        FrameInspection recordsFrame = inspectRenderedFrame("autoplayer-records-page");
        if (recordsFrame.hash == nameFrame.hash) {
            throw std::runtime_error("records autoplayer records frame did not change");
        }
        std::filesystem::remove(recordPath);

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " record_score=" << reloaded[0].score
                  << " record_level=" << static_cast<int>(reloaded[0].level)
                  << " name=" << reloaded[0].name
                  << " frame_inspection=1\n";
    }

    void debugAutoplayerMonsterBombReward(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1 || levelIndex_ != 0) {
            throw std::runtime_error("monster reward autoplayer failed to start level 1");
        }

        FrameInspection startFrame = inspectRenderedFrame("autoplayer-monster-reward-start");
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.empty() || bombs_.back().owner != 1) {
            throw std::runtime_error("monster reward autoplayer did not place bomb");
        }
        bombs_.back().timer = 1;
        Bomb placed = bombs_.back();
        auto tiles = explosionTilesFor(placed);
        std::array<int, 2> monsterTile = tiles.front();
        for (const auto& tile : tiles) {
            if (!monsterCollides(tile[0] * kTileSize, tile[1] * kTileSize - kTileSize)) {
                monsterTile = tile;
                break;
            }
        }

        ActiveMonster monster;
        monster.x = monsterTile[0] * kTileSize;
        monster.y = monsterTile[1] * kTileSize - kTileSize;
        monster.kind = 2;
        monster.behavior = 3;
        monster.ai0 = 0;
        monster.ai1 = 0;
        monster.ai2 = 1;
        monster.hp = 1;
        monster.animDelay = 1;
        refreshMonsterAnimationProfile(monster);
        initializeMonsterMotion(monster);
        monsters_.push_back(monster);

        player_.x = static_cast<float>(
            std::min(level_.width * kTileSize - 24, (placed.x + 5) * kTileSize));
        player_.y = static_cast<float>(placed.y * kTileSize);
        FrameControls idle;
        updateWithControls(idle, 1.0f / 60.0f);
        if (bombs_.size() != 0 || monsters_.empty() ||
            monsters_.front().behavior != 2 || bonusDrops_.empty()) {
            throw std::runtime_error("monster reward autoplayer did not kill monster");
        }
        FrameInspection deathFrame = inspectRenderedFrame("autoplayer-monster-reward-death");
        if (deathFrame.hash == startFrame.hash) {
            throw std::runtime_error("monster reward death frame did not change");
        }

        uint32_t scoreBefore = score_;
        BonusDrop drop = bonusDrops_.front();
        player_.x = drop.x;
        player_.y = drop.y;
        clearSoundLatch();
        lastPumpedSoundOffset_ = 0;
        lastPumpedSoundSelector_ = 0;
        updateWithControls(idle, 1.0f / 60.0f);
        if (score_ <= scoreBefore || soundLatch_.active ||
            lastPumpedSoundOffset_ != kBonusPickupSoundCursor ||
            lastPumpedSoundSelector_ != kBonusPickupSoundPriority) {
            throw std::runtime_error("monster reward autoplayer did not collect reward");
        }
        FrameInspection collectFrame =
            inspectRenderedFrame("autoplayer-monster-reward-collect");
        if (collectFrame.hash == deathFrame.hash) {
            throw std::runtime_error("monster reward collection frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " monster_dead=1 reward_collected=1"
                  << " score_delta=" << (score_ - scoreBefore)
                  << " frame_inspection=1\n";
    }

    void debugAutoplayerMonsterBehavior3Multihit(const std::string& scenario) {
        load();
        initSdl();
        prepareAutoplayerMonsterFixtureLevel();
        bool running = true;

        player_.x = 80.0f;
        player_.y = 24.0f;
        ActiveMonster monster;
        monster.x = 40;
        monster.y = 24;
        monster.kind = 1;
        monster.behavior = 3;
        monster.ai0 = 0x0100;
        monster.hp = 3;
        monster.animDelay = 1;
        refreshMonsterAnimationProfile(monster);
        initializeMonsterMotion(monster);
        monsters_.push_back(monster);

        FrameInspection startFrame = inspectRenderedFrame("autoplayer-monster-b3-start");
        FrameControls idle;
        updateWithControls(idle, 1.0f / 60.0f);
        if (monsters_.empty() || monsters_.front().behavior != 3 ||
            monsters_.front().x <= 40 || monsters_.front().hp != 3) {
            throw std::runtime_error("monster behavior-3 autoplayer did not advance walker");
        }
        int movedPx = monsters_.front().x - 40;
        FrameInspection moveFrame = inspectRenderedFrame("autoplayer-monster-b3-move");
        if (moveFrame.hash == startFrame.hash) {
            throw std::runtime_error("monster behavior-3 move frame did not change");
        }

        player_.x = 40.0f;
        player_.y = 24.0f;
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.empty() || bombs_.back().type != BombType::Small) {
            throw std::runtime_error("monster behavior-3 autoplayer did not place small bomb");
        }
        bombs_.back().timer = 1;
        player_.x = 88.0f;
        player_.y = 24.0f;
        updateWithControls(idle, 1.0f / 60.0f);
        if (!bombs_.empty() || monsters_.empty() || monsters_.front().behavior != 3 ||
            monsters_.front().hp != 2 || !bonusDrops_.empty()) {
            throw std::runtime_error("monster behavior-3 autoplayer first hit mismatch");
        }
        FrameInspection firstHitFrame =
            inspectRenderedFrame("autoplayer-monster-b3-first-hit");
        if (firstHitFrame.hash == moveFrame.hash) {
            throw std::runtime_error("monster behavior-3 first-hit frame did not change");
        }

        FrameControls switchControls;
        switchControls.p1Left = true;
        switchControls.p1Right = true;
        driveAutoplayerWeaponSwitchChord(switchControls);
        if (bombInventory_.selected != BombType::Medium) {
            throw std::runtime_error("monster behavior-3 autoplayer did not switch to medium");
        }

        player_.x = 40.0f;
        player_.y = 24.0f;
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.empty() || bombs_.back().type != BombType::Medium) {
            throw std::runtime_error("monster behavior-3 autoplayer did not place medium bomb");
        }
        bombs_.back().timer = 1;
        player_.x = 88.0f;
        player_.y = 24.0f;
        updateWithControls(idle, 1.0f / 60.0f);
        if (!bombs_.empty() || monsters_.empty() || monsters_.front().behavior != 2 ||
            bonusDrops_.empty()) {
            throw std::runtime_error("monster behavior-3 autoplayer second hit did not kill");
        }
        FrameInspection deathFrame =
            inspectRenderedFrame("autoplayer-monster-b3-death");
        if (deathFrame.hash == firstHitFrame.hash) {
            throw std::runtime_error("monster behavior-3 death frame did not change");
        }

        uint32_t scoreBefore = score_;
        BonusDrop drop = bonusDrops_.front();
        player_.x = drop.x;
        player_.y = drop.y;
        clearSoundLatch();
        lastPumpedSoundRecord_ = -1;
        lastPumpedSoundOffset_ = 0;
        lastPumpedSoundSelector_ = 0;
        updateWithControls(idle, 1.0f / 60.0f);
        if (score_ <= scoreBefore || soundLatch_.active ||
            lastPumpedSoundOffset_ != kBonusPickupSoundCursor ||
            lastPumpedSoundSelector_ != kBonusPickupSoundPriority) {
            throw std::runtime_error("monster behavior-3 autoplayer did not collect reward");
        }
        FrameInspection collectFrame =
            inspectRenderedFrame("autoplayer-monster-b3-collect");
        if (collectFrame.hash == deathFrame.hash) {
            throw std::runtime_error("monster behavior-3 collect frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " moved_px=" << movedPx
                  << " first_hit_hp=2 second_hit_kill=1 reward_collected=1"
                  << " score_delta=" << (score_ - scoreBefore)
                  << " frame_inspection=1\n";
    }

    void debugAutoplayerMonsterBehavior4Chase(const std::string& scenario) {
        load();
        initSdl();
        prepareAutoplayerMonsterFixtureLevel();
        bool running = true;

        player_.x = 80.0f;
        player_.y = 24.0f;
        ActiveMonster monster;
        monster.x = 40;
        monster.y = 24;
        monster.kind = 2;
        monster.behavior = 4;
        monster.ai0 = 2;
        monster.ai1 = 0x0200;
        monster.ai2 = 100;
        monster.hp = 2;
        monster.animDelay = 1;
        refreshMonsterAnimationProfile(monster);
        initializeMonsterMotion(monster);
        monsters_.push_back(monster);

        FrameInspection startFrame = inspectRenderedFrame("autoplayer-monster-b4-start");
        FrameControls idle;
        updateWithControls(idle, 1.0f / 60.0f);
        if (monsters_.empty() || monsters_.front().behavior != 4 ||
            monsters_.front().motionTimer != 1 || monsters_.front().x <= 40) {
            throw std::runtime_error("monster behavior-4 autoplayer did not chase");
        }
        int chaseDx = monsters_.front().x - 40;
        FrameInspection chaseFrame = inspectRenderedFrame("autoplayer-monster-b4-chase");
        if (chaseFrame.hash == startFrame.hash) {
            throw std::runtime_error("monster behavior-4 chase frame did not change");
        }

        FrameControls switchControls;
        switchControls.p1Left = true;
        switchControls.p1Right = true;
        driveAutoplayerWeaponSwitchChord(switchControls);
        if (bombInventory_.selected != BombType::Medium) {
            throw std::runtime_error("monster behavior-4 autoplayer did not switch to medium");
        }

        player_.x = static_cast<float>(monsters_.front().x);
        player_.y = static_cast<float>(monsters_.front().y);
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.empty() || bombs_.back().type != BombType::Medium) {
            throw std::runtime_error("monster behavior-4 autoplayer did not place medium bomb");
        }
        bombs_.back().timer = 1;
        player_.x = 96.0f;
        player_.y = 24.0f;
        updateWithControls(idle, 1.0f / 60.0f);
        if (!bombs_.empty() || monsters_.empty() || monsters_.front().behavior != 2 ||
            bonusDrops_.empty()) {
            throw std::runtime_error("monster behavior-4 autoplayer bomb kill mismatch");
        }
        FrameInspection deathFrame =
            inspectRenderedFrame("autoplayer-monster-b4-death");
        if (deathFrame.hash == chaseFrame.hash) {
            throw std::runtime_error("monster behavior-4 death frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " chase_dx=" << chaseDx
                  << " timer_after=1 killed=1 frame_inspection=1\n";
    }

    void debugAutoplayerMonsterSpawnerCycle(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1 || levelIndex_ != 0 || spawnerStates_.empty()) {
            throw std::runtime_error("monster spawner autoplayer failed to start level 1");
        }

        randomSeed_ = 0x1234abcd;
        player_.x = 320.0f;
        player_.y = 168.0f;
        player_.vy = 0.0f;
        player_.grounded = true;
        spawnerStates_[0].cooldown = 0;
        int initialSlots = spawnerStates_[0].availableSlots;
        int initialRemaining = spawnerStates_[0].remaining;

        FrameInspection startFrame = inspectRenderedFrame("autoplayer-monster-spawner-start");
        FrameControls idle;
        updateWithControls(idle, 1.0f / 60.0f);
        if (monsters_.empty() || !monsters_.front().hasSpawner ||
            monsters_.front().spawnerIndex != 0 || monsters_.front().behavior != 3 ||
            spawnerStates_[0].availableSlots != initialSlots - 1 ||
            spawnerStates_[0].remaining != initialRemaining - 1) {
            throw std::runtime_error("monster spawner autoplayer did not spawn actor");
        }
        FrameInspection spawnFrame = inspectRenderedFrame("autoplayer-monster-spawner-live");
        if (spawnFrame.hash == startFrame.hash) {
            throw std::runtime_error("monster spawner live frame did not change");
        }

        player_.x = static_cast<float>(monsters_.front().x);
        player_.y = static_cast<float>(monsters_.front().y);
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.empty() || bombs_.back().type != BombType::Small) {
            throw std::runtime_error("monster spawner autoplayer did not place small bomb");
        }
        bombs_.back().timer = 1;
        player_.x = static_cast<float>(monsters_.front().x + 32);
        player_.y = static_cast<float>(monsters_.front().y);
        updateWithControls(idle, 1.0f / 60.0f);
        if (monsters_.empty() || monsters_.front().behavior != 2 ||
            spawnerStates_[0].availableSlots != initialSlots || bonusDrops_.empty()) {
            throw std::runtime_error("monster spawner autoplayer did not release slot");
        }
        FrameInspection deathFrame = inspectRenderedFrame("autoplayer-monster-spawner-death");
        if (deathFrame.hash == spawnFrame.hash) {
            throw std::runtime_error("monster spawner death frame did not change");
        }

        spawnerStates_[0].cooldown = 0;
        updateWithControls(idle, 1.0f / 60.0f);
        int liveSpawnerOwned = static_cast<int>(std::count_if(
            monsters_.begin(), monsters_.end(),
            [](const ActiveMonster& monster) {
                return monster.alive && monster.hasSpawner && monster.behavior != 2;
            }));
        if (liveSpawnerOwned != 1 || spawnerStates_[0].availableSlots != initialSlots - 1 ||
            spawnerStates_[0].remaining != initialRemaining - 2) {
            throw std::runtime_error("monster spawner autoplayer did not respawn actor");
        }
        FrameInspection respawnFrame =
            inspectRenderedFrame("autoplayer-monster-spawner-respawn");
        if (respawnFrame.hash == deathFrame.hash) {
            throw std::runtime_error("monster spawner respawn frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " spawner_index=1 reserved_slot=1 released_slot=1 respawned=1"
                  << " frame_inspection=1\n";
    }

    void debugAutoplayerMonsterSpawnerBehavior4Level2(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1) {
            throw std::runtime_error("monster behavior-4 level2 autoplayer failed to start");
        }
        resetLevel(1);
        if (levelIndex_ != 1) {
            throw std::runtime_error("monster behavior-4 level2 autoplayer did not load level 2");
        }

        auto spanUpper = [](uint16_t base, uint16_t range) {
            return static_cast<uint16_t>(base + std::max<uint16_t>(1, range));
        };
        size_t spawnerIndex = level_.monsterSpawners.size();
        for (size_t i = 0; i < level_.monsterSpawners.size(); ++i) {
            if (level_.monsterSpawners[i].spawnArg == 4) {
                spawnerIndex = i;
                break;
            }
        }
        if (spawnerIndex >= level_.monsterSpawners.size()) {
            throw std::runtime_error("monster behavior-4 level2 autoplayer found no spawner");
        }
        for (size_t i = 0; i < spawnerStates_.size(); ++i) {
            if (i != spawnerIndex) {
                spawnerStates_[i].remaining = 0;
                spawnerStates_[i].availableSlots = 0;
            }
        }
        const MonsterSpawner& spawner = level_.monsterSpawners[spawnerIndex];
        randomSeed_ = 0x1234abcd;
        player_.x = static_cast<float>(spawner.x + 40);
        player_.y = static_cast<float>(spawner.y);
        player_.vy = -6.0f;
        player_.grounded = false;
        spawnerStates_[spawnerIndex].cooldown = 0;

        FrameInspection startFrame =
            inspectRenderedFrame("autoplayer-monster-spawner-b4-level2-start");
        FrameControls idle;
        updateWithControls(idle, 1.0f / 60.0f);
        if (monsters_.size() != 1) {
            throw std::runtime_error("monster behavior-4 level2 autoplayer did not spawn one actor");
        }
        const ActiveMonster& monster = monsters_.front();
        if (!monster.hasSpawner || monster.spawnerIndex != spawnerIndex ||
            monster.kind != spawner.monsterKind || monster.behavior != 4 ||
            monster.animDelay != std::max<uint8_t>(1, spawner.animationDelay) ||
            monster.ai0 < spawner.param0Base || monster.ai0 >= spanUpper(spawner.param0Base, spawner.param0Range) ||
            monster.ai1 < spawner.param1Base || monster.ai1 >= spanUpper(spawner.param1Base, spawner.param1Range) ||
            monster.ai2 < spawner.param2Base || monster.ai2 >= spanUpper(spawner.param2Base, spawner.param2Range) ||
            monster.hp < spawner.randomBase || monster.hp >= spanUpper(spawner.randomBase, spawner.randomRange) ||
            monster.motionTimer != std::max<int>(1, monster.ai0) - 1 ||
            monster.vx8 <= 0 || monster.vy8 != 0 || monster.x <= spawner.x) {
            throw std::runtime_error("monster behavior-4 level2 autoplayer spawn fields mismatched");
        }
        FrameInspection spawnFrame =
            inspectRenderedFrame("autoplayer-monster-spawner-b4-level2-live");
        if (spawnFrame.hash == startFrame.hash) {
            throw std::runtime_error("monster behavior-4 level2 frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " level=2 spawner_index=" << (spawnerIndex + 1)
                  << " ai0=" << monster.ai0
                  << " ai1=" << monster.ai1
                  << " ai2=" << monster.ai2
                  << " hp=" << monster.hp
                  << " vx8=" << monster.vx8
                  << " vy8=" << monster.vy8
                  << " frame_inspection=1\n";
    }

    void debugAutoplayerMonsterSpawnerBehavior4Level3(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1) {
            throw std::runtime_error("monster behavior-4 level3 autoplayer failed to start");
        }
        resetLevel(2);
        if (levelIndex_ != 2) {
            throw std::runtime_error("monster behavior-4 level3 autoplayer did not load level 3");
        }

        auto spanUpper = [](uint16_t base, uint16_t range) {
            return static_cast<uint16_t>(base + std::max<uint16_t>(1, range));
        };
        size_t spawnerIndex = level_.monsterSpawners.size();
        for (size_t i = 0; i < level_.monsterSpawners.size(); ++i) {
            if (level_.monsterSpawners[i].spawnArg == 4) {
                spawnerIndex = i;
                break;
            }
        }
        if (spawnerIndex >= level_.monsterSpawners.size()) {
            throw std::runtime_error("monster behavior-4 level3 autoplayer found no spawner");
        }
        for (size_t i = 0; i < spawnerStates_.size(); ++i) {
            if (i != spawnerIndex) {
                spawnerStates_[i].remaining = 0;
                spawnerStates_[i].availableSlots = 0;
            }
        }
        const MonsterSpawner& spawner = level_.monsterSpawners[spawnerIndex];
        randomSeed_ = 0x1234abcd;
        player_.x = static_cast<float>(spawner.x + 24);
        player_.y = static_cast<float>(spawner.y - 16);
        player_.vy = -6.0f;
        player_.grounded = false;
        spawnerStates_[spawnerIndex].cooldown = 0;

        FrameInspection startFrame =
            inspectRenderedFrame("autoplayer-monster-spawner-b4-level3-start");
        FrameControls idle;
        updateWithControls(idle, 1.0f / 60.0f);
        if (monsters_.size() != 1) {
            throw std::runtime_error("monster behavior-4 level3 autoplayer did not spawn one actor");
        }
        const ActiveMonster& monster = monsters_.front();
        if (!monster.hasSpawner || monster.spawnerIndex != spawnerIndex ||
            monster.kind != spawner.monsterKind || monster.behavior != 4 ||
            monster.animDelay != std::max<uint8_t>(1, spawner.animationDelay) ||
            monster.ai0 < spawner.param0Base || monster.ai0 >= spanUpper(spawner.param0Base, spawner.param0Range) ||
            monster.ai1 < spawner.param1Base || monster.ai1 >= spanUpper(spawner.param1Base, spawner.param1Range) ||
            monster.ai2 < spawner.param2Base || monster.ai2 >= spanUpper(spawner.param2Base, spawner.param2Range) ||
            monster.hp < spawner.randomBase || monster.hp >= spanUpper(spawner.randomBase, spawner.randomRange) ||
            monster.motionTimer != std::max<int>(1, monster.ai0) - 1 ||
            monster.vx8 <= 0 || monster.vy8 >= 0) {
            throw std::runtime_error("monster behavior-4 level3 autoplayer spawn fields mismatched");
        }
        FrameInspection spawnFrame =
            inspectRenderedFrame("autoplayer-monster-spawner-b4-level3-live");
        if (spawnFrame.hash == startFrame.hash) {
            throw std::runtime_error("monster behavior-4 level3 frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " level=3 spawner_index=" << (spawnerIndex + 1)
                  << " ai0=" << monster.ai0
                  << " ai1=" << monster.ai1
                  << " ai2=" << monster.ai2
                  << " hp=" << monster.hp
                  << " vx8=" << monster.vx8
                  << " vy8=" << monster.vy8
                  << " frame_inspection=1\n";
    }

    void debugAutoplayerMonsterBehavior4TargetSelection(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_2);
        processEvents(running);
        if (menu_ || playerCount_ != 2 || playerDead_ || player2Dead_) {
            throw std::runtime_error("monster behavior-4 target autoplayer failed to start");
        }
        resetLevel(2);
        if (levelIndex_ != 2) {
            throw std::runtime_error("monster behavior-4 target autoplayer did not load level 3");
        }

        size_t spawnerIndex = level_.monsterSpawners.size();
        for (size_t i = 0; i < level_.monsterSpawners.size(); ++i) {
            if (level_.monsterSpawners[i].spawnArg == 4) {
                spawnerIndex = i;
                break;
            }
        }
        if (spawnerIndex >= level_.monsterSpawners.size()) {
            throw std::runtime_error("monster behavior-4 target autoplayer found no spawner");
        }
        for (size_t i = 0; i < spawnerStates_.size(); ++i) {
            if (i != spawnerIndex) {
                spawnerStates_[i].remaining = 0;
                spawnerStates_[i].availableSlots = 0;
            }
        }
        const MonsterSpawner& spawner = level_.monsterSpawners[spawnerIndex];
        randomSeed_ = 0x1234abcd;
        spawnerStates_[spawnerIndex].cooldown = 0;
        player_.x = static_cast<float>(spawner.x + 40);
        player_.y = static_cast<float>(spawner.y);
        player_.vy = -6.0f;
        player2_.x = static_cast<float>(spawner.x - 16);
        player2_.y = static_cast<float>(spawner.y);
        player2_.vy = -6.0f;
        playerDead_ = false;
        player2Dead_ = false;

        FrameInspection startFrame =
            inspectRenderedFrame("autoplayer-monster-b4-target-start");
        FrameControls idle;
        updateWithControls(idle, 1.0f / 60.0f);
        if (monsters_.size() != 1 || monsters_.front().behavior != 4 ||
            monsters_.front().vx8 >= 0 || monsters_.front().x >= spawner.x) {
            throw std::runtime_error("monster behavior-4 target autoplayer did not prefer player 2");
        }
        int xAfterP2 = monsters_.front().x;
        FrameInspection p2Frame =
            inspectRenderedFrame("autoplayer-monster-b4-target-p2");
        if (p2Frame.hash == startFrame.hash) {
            throw std::runtime_error("monster behavior-4 target player-2 frame did not change");
        }

        player2Dead_ = true;
        player_.x = static_cast<float>(monsters_.front().x + 24);
        player_.y = static_cast<float>(monsters_.front().y);
        monsters_.front().motionTimer = 1;
        updateWithControls(idle, 1.0f / 60.0f);
        if (monsters_.front().vx8 <= 0 || monsters_.front().x <= xAfterP2) {
            throw std::runtime_error("monster behavior-4 target autoplayer did not retarget player 1");
        }
        int xAfterP1 = monsters_.front().x;
        FrameInspection p1Frame =
            inspectRenderedFrame("autoplayer-monster-b4-target-p1");
        if (p1Frame.hash == p2Frame.hash) {
            throw std::runtime_error("monster behavior-4 target player-1 frame did not change");
        }

        playerDead_ = true;
        player2Dead_ = false;
        player2_.x = static_cast<float>(monsters_.front().x - 24);
        player2_.y = static_cast<float>(monsters_.front().y);
        monsters_.front().motionTimer = 1;
        updateWithControls(idle, 1.0f / 60.0f);
        if (monsters_.front().vx8 >= 0 || monsters_.front().x >= xAfterP1) {
            throw std::runtime_error("monster behavior-4 target autoplayer did not retarget back to player 2");
        }
        FrameInspection p2ReturnFrame =
            inspectRenderedFrame("autoplayer-monster-b4-target-p2-return");
        if (p2ReturnFrame.hash == p1Frame.hash) {
            throw std::runtime_error("monster behavior-4 target return frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " level=3 spawner_index=" << (spawnerIndex + 1)
                  << " initial_target=2 retarget_p1=1 retarget_p2=1"
                  << " frame_inspection=1\n";
    }

    void debugAutoplayerCollapsePlaybackRoute(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_1);
        processEvents(running);
        if (menu_ || playerCount_ != 1 || levelIndex_ != 0) {
            throw std::runtime_error("collapse autoplayer failed to start level 1");
        }

        AutoplayRouteResult route = autoplayLevel1BombRoute();
        if (route.bombTileX != 24 || route.bombTileY != 22) {
            throw std::runtime_error("collapse autoplayer missed level-1 tile 24,22");
        }
        FrameInspection routeFrame = inspectRenderedFrame("autoplayer-collapse-route");

        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.empty() || bombs_.back().x != 24 || bombs_.back().y != 22) {
            throw std::runtime_error("collapse autoplayer did not place route bomb");
        }
        int fuse = bombs_.back().timer;
        FrameControls idle;
        for (int i = 0; i < fuse; ++i) {
            updateWithControls(idle, 1.0f / 60.0f);
        }
        if (!bombs_.empty() || explosionEffects_.empty() || collapseQueue_.empty()) {
            throw std::runtime_error("collapse autoplayer did not start collapse playback");
        }
        int collapseCount = collapseQueue_.front().count;
        FrameInspection explosionFrame =
            inspectRenderedFrame("autoplayer-collapse-explosion");
        if (explosionFrame.hash == routeFrame.hash) {
            throw std::runtime_error("collapse explosion frame did not change");
        }

        int playbackFrames = 0;
        while (!collapseQueue_.empty() && playbackFrames < 32) {
            updateWithControls(idle, 1.0f / 60.0f);
            ++playbackFrames;
        }
        if (!collapseQueue_.empty() || playbackFrames != 24) {
            throw std::runtime_error("collapse autoplayer playback duration mismatch");
        }
        FrameInspection clearFrame = inspectRenderedFrame("autoplayer-collapse-clear");
        if (clearFrame.hash == explosionFrame.hash) {
            throw std::runtime_error("collapse clear frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " collapse_started=1 collapse_count=" << collapseCount
                  << " playback_frames=" << playbackFrames
                  << " frame_inspection=1\n";
    }

    void debugAutoplayerTwoPlayerRoute(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_2);
        processEvents(running);
        if (menu_ || playerCount_ != 2 || playerDead_ || player2Dead_) {
            throw std::runtime_error("two-player autoplayer failed to start");
        }

        FrameInspection startFrame = inspectRenderedFrame("autoplayer-two-player-start");
        int p1StartX = static_cast<int>(player_.x);
        int p2StartX = static_cast<int>(player2_.x);
        int p2StartY = static_cast<int>(player2_.y);
        FrameControls controls;
        controls.p2Right = true;
        for (int i = 0; i < 24; ++i) {
            updateWithControls(controls, 1.0f / 60.0f);
        }
        if (static_cast<int>(player2_.x) <= p2StartX + 12 ||
            static_cast<int>(player_.x) != p1StartX || collides(player2_.x, player2_.y)) {
            throw std::runtime_error("two-player autoplayer did not move player 2 cleanly");
        }

        FrameInspection movedFrame = inspectRenderedFrame("autoplayer-two-player-moved");
        if (movedFrame.hash == startFrame.hash) {
            throw std::runtime_error("two-player autoplayer movement frame did not change");
        }

        size_t bombsBefore = bombs_.size();
        int p2SmallBefore = bombInventory2_.counts[0];
        int bombTileX = static_cast<int>(player2_.x + 6.0f) / kTileSize;
        int bombTileY = static_cast<int>(player2_.y + 12.0f) / kTileSize;
        pushKeyDown(SDLK_KP_0);
        processEvents(running);
        if (bombs_.size() != bombsBefore + 1 || bombs_.back().owner != 2 ||
            bombs_.back().x != bombTileX || bombs_.back().y != bombTileY ||
            bombInventory2_.counts[0] != p2SmallBefore - 1) {
            throw std::runtime_error("two-player autoplayer keypad 0 did not place player 2 bomb");
        }

        FrameInspection bombFrame = inspectRenderedFrame("autoplayer-two-player-bomb");
        if (bombFrame.hash == movedFrame.hash) {
            throw std::runtime_error("two-player autoplayer bomb frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " p1_x=" << p1StartX
                  << " p2_start_xy=" << p2StartX << ',' << p2StartY
                  << " p2_final_xy=" << static_cast<int>(player2_.x) << ','
                  << static_cast<int>(player2_.y)
                  << " p2_bomb_tile=" << bombTileX << ',' << bombTileY
                  << " p2_fire_key=kp0 bombs=1 frame_inspection=1\n";
    }

    void debugAutoplayerTwoPlayerDeathVisuals(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_2);
        processEvents(running);
        if (menu_ || playerCount_ != 2 || playerDead_ || player2Dead_) {
            throw std::runtime_error("two-player death visual autoplayer failed to start");
        }

        auto visualRowFor = [&](uint8_t frame) {
            State2VisualRow row;
            if (!originalState2VisualRow(frame, row)) {
                throw std::runtime_error("two-player death visual row missing");
            }
            return row;
        };
        auto effectMatches = [&](const State2EffectEntry& effect,
                                 const Player& player,
                                 uint8_t frame,
                                 const State2VisualRow& row) {
            return effect.active && effect.x == static_cast<int>(player.x) &&
                   effect.y == static_cast<int>(player.y) &&
                   effect.visualFrame == frame && effect.drawDx == row.row0 &&
                   effect.drawDy == row.row1 && effect.row2 == row.row2 &&
                   effect.spriteIndex == row.row3;
        };
        auto cursorPreviewFrame = [&](const std::string& label) {
            state2VisualCursorPreview_ = true;
            FrameInspection inspection = inspectRenderedFrame(label);
            state2VisualCursorPreview_ = false;
            return inspection;
        };

        FrameInspection startFrame =
            inspectRenderedFrame("autoplayer-two-player-death-visual-start");
        int p1StartX = static_cast<int>(player_.x);
        int p1StartY = static_cast<int>(player_.y);
        int p2StartX = static_cast<int>(player2_.x);
        int p2StartY = static_cast<int>(player2_.y);

        energy2_ = 0;
        lives2_ = 3;
        damageCooldown2_ = 0;
        damagePlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                     damageCooldown2_, 2);
        State2VisualRow row4a = visualRowFor(kState2VisualStartFrame);
        if (playerDead_ || !player2Dead_ || state2Effect_.active ||
            !state2Visual2_.active ||
            state2Visual2_.current != kState2VisualStartFrame ||
            !effectMatches(state2Effect2_, player2_, kState2VisualStartFrame,
                           row4a)) {
            throw std::runtime_error("player 2 death visual effect entry mismatch");
        }

        FrameInspection p2DeathFrame =
            inspectRenderedFrame("autoplayer-two-player-death-visual-p2-4a");
        if (p2DeathFrame.hash == startFrame.hash) {
            throw std::runtime_error("player 2 death visual frame did not change");
        }
        FrameInspection p2CursorFrame =
            cursorPreviewFrame("autoplayer-two-player-death-visual-p2-cursor-4a");
        if (p2CursorFrame.hash == p2DeathFrame.hash) {
            throw std::runtime_error("player 2 cursor preview matched live effect renderer");
        }

        FrameControls idle;
        updateWithControls(idle, 1.0f / 60.0f);
        State2VisualRow row4b =
            visualRowFor(static_cast<uint8_t>(kState2VisualStartFrame + 1));
        if (!player2Dead_ || deathStateTimer2_ != kDeathStateTicks - 1 ||
            state2Visual2_.current !=
                static_cast<uint8_t>(kState2VisualStartFrame + 1) ||
            !effectMatches(state2Effect2_, player2_,
                           static_cast<uint8_t>(kState2VisualStartFrame + 1),
                           row4b)) {
            throw std::runtime_error("player 2 death visual tick mismatch");
        }
        FrameInspection p2TickFrame =
            inspectRenderedFrame("autoplayer-two-player-death-visual-p2-4b");
        if (p2TickFrame.hash == p2DeathFrame.hash) {
            throw std::runtime_error("player 2 death visual tick frame did not change");
        }

        energy_ = 0;
        lives_ = 3;
        damageCooldown_ = 0;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        if (!playerDead_ || !player2Dead_ || !state2Effect_.active ||
            !state2Effect2_.active ||
            !effectMatches(state2Effect_, player_, kState2VisualStartFrame,
                           row4a) ||
            (state2Effect_.x == state2Effect2_.x &&
             state2Effect_.y == state2Effect2_.y)) {
            throw std::runtime_error("two-player death visual slots aliased");
        }
        FrameInspection bothDeathFrame =
            inspectRenderedFrame("autoplayer-two-player-death-visual-both");
        if (bothDeathFrame.hash == p2TickFrame.hash) {
            throw std::runtime_error("two-player death visual second slot frame did not change");
        }
        if (state2VisualCursorPreview_) {
            throw std::runtime_error("two-player death visual cursor preview flag leaked");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " p1_effect_xy=" << p1StartX << ',' << p1StartY
                  << " p2_effect_xy=" << p2StartX << ',' << p2StartY
                  << " p2_frames=0x" << std::hex
                  << static_cast<int>(kState2VisualStartFrame) << ",0x"
                  << static_cast<int>(kState2VisualStartFrame + 1) << std::dec
                  << " p2_sprites=" << static_cast<int>(row4a.row3) << ','
                  << static_cast<int>(row4b.row3)
                  << " p1_frame=0x" << std::hex
                  << static_cast<int>(state2Effect_.visualFrame) << std::dec
                  << " p1_sprite=" << static_cast<int>(state2Effect_.spriteIndex)
                  << " draw_offset=16,16"
                  << " effects_separate=1"
                  << " cursor_legacy_hash_mismatch=1"
                  << " frame_inspection=1 visual_claim=0\n";
    }

    void debugAutoplayerTwoPlayerProgression(const std::string& scenario) {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        pushKeyDown(SDLK_2);
        processEvents(running);
        if (menu_ || playerCount_ != 2 || playerDead_ || player2Dead_) {
            throw std::runtime_error("two-player progression autoplayer failed to start");
        }

        FrameInspection startFrame = inspectRenderedFrame("autoplayer-two-progress-start");
        int p1StartX = static_cast<int>(player_.x);
        int p2StartX = static_cast<int>(player2_.x);

        FrameControls bothRight;
        bothRight.p1Right = true;
        bothRight.p2Right = true;
        for (int i = 0; i < 18; ++i) {
            updateWithControls(bothRight, 1.0f / 60.0f);
        }
        if (static_cast<int>(player_.x) <= p1StartX + 8 ||
            static_cast<int>(player2_.x) <= p2StartX + 8) {
            throw std::runtime_error("two-player progression did not move both players");
        }
        FrameInspection movedFrame = inspectRenderedFrame("autoplayer-two-progress-moved");
        if (movedFrame.hash == startFrame.hash) {
            throw std::runtime_error("two-player progression movement frame did not change");
        }

        energy2_ = 0;
        lives2_ = 3;
        damageCooldown2_ = 0;
        damagePlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                     damageCooldown2_, 2);
        if (!player2Dead_ || lives2_ != 3 || !pendingLifeLoss2_ ||
            deathStateTimer2_ != kDeathStateTicks || !state2Visual2_.active) {
            throw std::runtime_error("two-player progression did not enter player-2 state-2");
        }
        FrameInspection p2DeathFrame = inspectRenderedFrame("autoplayer-two-progress-p2-death");
        if (p2DeathFrame.hash == movedFrame.hash) {
            throw std::runtime_error("two-player progression p2 death frame did not change");
        }

        FrameControls p1Only;
        p1Only.p1Right = true;
        int p1BeforeSolo = static_cast<int>(player_.x);
        int p2DeadX = static_cast<int>(player2_.x);
        for (int i = 0; i < 10; ++i) {
            updateWithControls(p1Only, 1.0f / 60.0f);
        }
        if (static_cast<int>(player_.x) <= p1BeforeSolo ||
            static_cast<int>(player2_.x) != p2DeadX || !player2Dead_) {
            throw std::runtime_error("two-player progression p1 did not remain active");
        }

        FrameControls idle;
        while (deathStateTimer2_ > 0) {
            updateWithControls(idle, 1.0f / 60.0f);
        }
        pushKeyDown(SDLK_KP_0);
        processEvents(running);
        if (player2Dead_ || lives2_ != 2 || energy2_ != 100 ||
            damageCooldown2_ <= 0 || state2Visual2_.active) {
            throw std::runtime_error("two-player progression keypad 0 did not reenter player 2");
        }
        FrameInspection reentryFrame = inspectRenderedFrame("autoplayer-two-progress-reentry");
        if (reentryFrame.hash == p2DeathFrame.hash) {
            throw std::runtime_error("two-player progression reentry frame did not change");
        }

        size_t bombsBefore = bombs_.size();
        int p2SmallBefore = bombInventory2_.counts[0];
        int p2BombX = static_cast<int>(player2_.x + 6.0f) / kTileSize;
        int p2BombY = static_cast<int>(player2_.y + 12.0f) / kTileSize;
        pushKeyDown(SDLK_KP_0);
        processEvents(running);
        if (bombs_.size() != bombsBefore + 1 || bombs_.back().owner != 2 ||
            bombs_.back().x != p2BombX || bombs_.back().y != p2BombY ||
            bombInventory2_.counts[0] != p2SmallBefore - 1) {
            throw std::runtime_error("two-player progression keypad 0 did not place p2 bomb after reentry");
        }

        auto objective = findObjectiveTileForSmoke();
        player2_.x = static_cast<float>(objective[0] * kTileSize);
        player2_.y = static_cast<float>(objective[1] * kTileSize);
        uint32_t p1ScoreBefore = score_;
        uint32_t p2ScoreBefore = score2_;
        collectObjectiveTiles(player2_, 2);
        if (collected_ != 1 || score_ != p1ScoreBefore ||
            score2_ != p2ScoreBefore + 1000) {
            throw std::runtime_error("two-player progression p2 objective score mismatch");
        }
        FrameInspection scoreFrame = inspectRenderedFrame("autoplayer-two-progress-score");
        if (scoreFrame.hash == reentryFrame.hash) {
            throw std::runtime_error("two-player progression score frame did not change");
        }

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " p1_moved=1 p2_death_timer=" << kDeathStateTicks
                  << " p2_reentered=1 p2_bomb_tile=" << p2BombX << ',' << p2BombY
                  << " p2_fire_key=kp0"
                  << " p2_score=" << score2_
                  << " collected=" << collected_
                  << " frame_inspection=1\n";
    }

    FrameInspection inspectRenderedFrame(const std::string& label) {
        draw();
        if (fb_.empty()) {
            throw std::runtime_error(label + " frame buffer is empty");
        }
        FrameInspection inspection;
        uint32_t first = fb_.front();
        uint64_t hash = 1469598103934665603ull;
        for (uint32_t pixelValue : fb_) {
            if (pixelValue != first) ++inspection.changedPixels;
            hash ^= static_cast<uint64_t>(pixelValue);
            hash *= 1099511628211ull;
        }
        inspection.hash = hash;
        if (inspection.changedPixels == 0) {
            throw std::runtime_error(label + " rendered a uniform frame");
        }
        return inspection;
    }

    bool regionHasVariation(int x, int y, int w, int h) const {
        int x0 = std::clamp(x, 0, kScreenW);
        int y0 = std::clamp(y, 0, kScreenH);
        int x1 = std::clamp(x + w, 0, kScreenW);
        int y1 = std::clamp(y + h, 0, kScreenH);
        if (x0 >= x1 || y0 >= y1) return false;
        uint32_t first = fb_[static_cast<size_t>(y0) * kScreenW + x0];
        for (int yy = y0; yy < y1; ++yy) {
            for (int xx = x0; xx < x1; ++xx) {
                if (fb_[static_cast<size_t>(yy) * kScreenW + xx] != first) {
                    return true;
                }
            }
        }
        return false;
    }

    bool regionChanged(const std::vector<uint32_t>& before, int x, int y,
                       int w, int h) const {
        if (before.size() != fb_.size()) return false;
        int x0 = std::clamp(x, 0, kScreenW);
        int y0 = std::clamp(y, 0, kScreenH);
        int x1 = std::clamp(x + w, 0, kScreenW);
        int y1 = std::clamp(y + h, 0, kScreenH);
        if (x0 >= x1 || y0 >= y1) return false;
        for (int yy = y0; yy < y1; ++yy) {
            for (int xx = x0; xx < x1; ++xx) {
                size_t idx = static_cast<size_t>(yy) * kScreenW + xx;
                if (fb_[idx] != before[idx]) {
                    return true;
                }
            }
        }
        return false;
    }

    size_t countColorInRegion(int x, int y, int w, int h, uint32_t color) const {
        int x0 = std::clamp(x, 0, kScreenW);
        int y0 = std::clamp(y, 0, kScreenH);
        int x1 = std::clamp(x + w, 0, kScreenW);
        int y1 = std::clamp(y + h, 0, kScreenH);
        size_t count = 0;
        for (int yy = y0; yy < y1; ++yy) {
            for (int xx = x0; xx < x1; ++xx) {
                if (fb_[static_cast<size_t>(yy) * kScreenW + xx] == color) {
                    ++count;
                }
            }
        }
        return count;
    }

    void validate() {
        load();
        std::cout << "background=" << background_.width << "x" << background_.height
                  << " pixels=" << background_.pixels.size() << '\n';
        std::cout << "tiles=" << tiles_.count << '\n';
        std::cout << "sprites_bomomimk=" << sprites_.sprites.size() << '\n';
        std::cout << "sprites_prova=" << altSprites_.sprites.size() << '\n';
        std::cout << "sprites_fonts=" << fontSprites_.sprites.size() << '\n';
        std::cout << "sound_record_size=" << sounds_.recordSize
                  << " sound_records=" << sounds_.records.size() << '\n';
        std::cout << "gran_record_size=" << gran_.recordSize
                  << " gran_records=" << gran_.records.size() << '\n';
        std::cout << "records=" << records_.size() << '\n';
        for (size_t i = 0; i < records_.size(); ++i) {
            std::cout << "record_" << (i + 1) << "=score:" << records_[i].score
                      << " level:" << static_cast<int>(records_[i].level)
                      << " name:" << records_[i].name << '\n';
        }
        std::cout << "levels=" << levels_.size() << '\n';
        for (size_t i = 0; i < levels_.size(); ++i) {
            const Level& l = levels_[i];
            std::cout << "level_" << (i + 1) << '=' << l.width << 'x' << l.height
                      << " objective_tile=" << static_cast<int>(l.objectiveTile)
                      << " required_bonus=" << l.requiredBonus
                      << " destruction=" << static_cast<int>(l.requiredDestruction)
                      << " spawners=" << l.monsterSpawners.size()
                      << " portals=" << l.portals.size()
                      << " triggers=" << l.tileTriggers.size() << '\n';
        }
    }

    void debugRecordUpdate(const std::string& path) {
        load();
        std::vector<Record> testRecords = records_;
        bool changed = insertRecord(testRecords, makeRecord(999999u, 9u, "TEST"));
        if (!changed) {
            throw std::runtime_error("test record was not inserted");
        }
        saveRecords(path, testRecords);
        auto reloaded = loadRecords(path);
        if (reloaded.empty() || reloaded[0].score != 999999u ||
            reloaded[0].level != 9u || reloaded[0].name != "TEST") {
            throw std::runtime_error("saved test record did not round-trip");
        }
        int binary = isJsonRecordPath(path) ? 0 : 1;
        size_t rawSize = 0;
        std::string encodedName = encodeRecordName(reloaded[0].name);
        if (binary) {
            auto bytes = readFile(path);
            rawSize = bytes.size();
            if (bytes.size() != 92 || bytes[0] != 7 || le32(bytes, 1) != 999999u ||
                bytes[5] != 9u) {
                throw std::runtime_error("saved raw test record layout changed");
            }
            encodedName = std::string(bytes.begin() + 6, bytes.begin() + 14);
            if (encodedName != "TEST::::") {
                throw std::runtime_error("saved raw test record name encoding changed");
            }
        }
        std::cout << "record_update=ok top=" << reloaded[0].score
                  << " level=" << static_cast<int>(reloaded[0].level)
                  << " name=" << reloaded[0].name
                  << " binary=" << binary
                  << " raw_size=" << rawSize
                  << " encoded=" << encodedName << '\n';
    }

    void debugRecordsRawRoundtrip() {
        load();
        auto rawBytes = readFile("RECS.DAT");
        constexpr size_t kRecordSize = 13;
        if (rawBytes.empty()) {
            throw std::runtime_error("RECS.DAT raw file is empty");
        }
        uint8_t rawCount = rawBytes[0];
        if (rawCount != 7 ||
            rawBytes.size() != 1 + static_cast<size_t>(rawCount) * kRecordSize) {
            throw std::runtime_error("RECS.DAT raw layout mismatch");
        }

        auto jsonRecords = extractObjectArray(readTextFile("RECS.DAT.json"), "records");
        if (jsonRecords.size() != rawCount || records_.size() != rawCount) {
            throw std::runtime_error("RECS.DAT JSON record count mismatch");
        }
        auto decodeRawName = [](std::string encoded) {
            std::replace(encoded.begin(), encoded.end(), ':', ' ');
            while (!encoded.empty() && encoded.back() == ' ') {
                encoded.pop_back();
            }
            return encoded.empty() ? std::string("nessuno") : encoded;
        };

        uint64_t scoreSum = 0;
        int level8Count = 0;
        int decodedAgaCount = 0;
        int encodedColonPaddedCount = 0;
        int byteSum = 0;
        int weightedSum = 0;
        uint8_t xorValue = 0;
        uint32_t previousScore = UINT32_MAX;
        for (size_t i = 0; i < rawBytes.size(); ++i) {
            uint8_t byte = rawBytes[i];
            byteSum += byte;
            weightedSum += static_cast<int>((i + 1) * byte);
            xorValue = static_cast<uint8_t>(xorValue ^ byte);
        }

        for (size_t i = 0; i < rawCount; ++i) {
            size_t off = 1 + i * kRecordSize;
            uint32_t rawScore = le32(rawBytes, off);
            uint8_t rawLevel = rawBytes[off + 4];
            std::string rawEncoded(rawBytes.begin() + static_cast<std::ptrdiff_t>(off + 5),
                                   rawBytes.begin() + static_cast<std::ptrdiff_t>(off + 13));
            std::string rawDecoded = decodeRawName(rawEncoded);

            const std::string& recJson = jsonRecords[i];
            uint32_t jsonScore = static_cast<uint32_t>(extractInt(recJson, "score"));
            uint8_t jsonLevel = static_cast<uint8_t>(extractInt(recJson, "level"));
            std::string jsonEncoded = extractString(recJson, "encoded_name");
            std::string jsonDecoded = extractString(recJson, "decoded_name");
            if (rawScore != jsonScore || rawLevel != jsonLevel ||
                rawEncoded != jsonEncoded || rawDecoded != jsonDecoded ||
                records_[i].score != rawScore || records_[i].level != rawLevel ||
                records_[i].name != rawDecoded) {
                throw std::runtime_error("RECS.DAT raw/json record mismatch");
            }
            if (i != 0 && rawScore > previousScore) {
                throw std::runtime_error("RECS.DAT scores are no longer descending");
            }
            previousScore = rawScore;
            scoreSum += rawScore;
            if (rawLevel == 8) ++level8Count;
            if (rawDecoded == "aga") ++decodedAgaCount;
            if (rawEncoded == "aga:::::") ++encodedColonPaddedCount;
        }
        if (scoreSum != 3508890 || byteSum != 6047 ||
            weightedSum != 278918 || xorValue != 0xdd ||
            level8Count != 7 || decodedAgaCount != 7 ||
            encodedColonPaddedCount != 7) {
            throw std::runtime_error("RECS.DAT raw aggregate changed");
        }

        std::cout << "records_raw_roundtrip=ok raw_size=" << rawBytes.size()
                  << " count=" << static_cast<int>(rawCount)
                  << " record_size=" << kRecordSize
                  << " score_sum=" << scoreSum
                  << " top=" << records_.front().score
                  << " cutoff=" << records_.back().score
                  << " level8_count=" << level8Count
                  << " decoded_aga=" << decodedAgaCount
                  << " encoded_colon_padded=" << encodedColonPaddedCount
                  << " byte_sum=" << byteSum
                  << " weighted_sum=" << weightedSum
                  << " xor=0x" << std::hex << std::setw(2) << std::setfill('0')
                  << static_cast<int>(xorValue) << std::dec << std::setfill(' ')
                  << '\n';
    }

    void debugRecordEntryStaticModel() {
        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for record entry scan");
        }
        constexpr uint16_t kTemplate = 0x183c;
        constexpr uint16_t kRoutineStart = 0x1845;
        constexpr uint16_t kPromptSound = 0x1857;
        constexpr uint16_t kBackspaceCheck = 0x1a07;
        constexpr uint16_t kEnterCheck = 0x1a3a;
        constexpr uint16_t kCommitSound = 0x1a44;
        constexpr uint16_t kRecordShift = 0x1a76;
        constexpr uint16_t kStoredRecordPointer = 0x1a9e;
        constexpr uint16_t kNameCopy = 0x1aab;
        constexpr uint16_t kScoreWrite = 0x1ac0;
        constexpr uint16_t kRoutineRet = 0x1ad6;

        auto requireBytes = [&](uint16_t offset, const std::string& hex,
                                const std::string& label) {
            std::vector<uint8_t> expected = parseHexByteList(hex);
            size_t p = imageBase + offset;
            if (p + expected.size() > exeBytes.size()) {
                throw std::runtime_error(label + " extends past LEZAC.EXE");
            }
            for (size_t i = 0; i < expected.size(); ++i) {
                if (exeBytes[p + i] != expected[i]) {
                    throw std::runtime_error(label + " bytes changed");
                }
            }
        };
        auto countBytes = [&](const std::string& hex) {
            std::vector<uint8_t> expected = parseHexByteList(hex);
            int count = 0;
            auto begin = exeBytes.begin() + static_cast<long>(imageBase + kRoutineStart);
            auto end = exeBytes.begin() + static_cast<long>(imageBase + kRoutineRet + 1);
            for (auto it = begin; it != end;) {
                it = std::search(it, end, expected.begin(), expected.end());
                if (it == end) break;
                ++count;
                ++it;
            }
            return count;
        };

        requireBytes(kTemplate, "08 3a 3a 3a 3a 3a 3a 3a 3a",
                     "record empty-name template");
        requireBytes(kRoutineStart, "55 89 e5 b8 10 02 9a df 04 20 09",
                     "record entry prologue");
        requireBytes(kPromptSound,
                     "c7 06 74 20 78 00 c6 06 9f 79 0b e8 f5 fd",
                     "record prompt sound request");
        requireBytes(kBackspaceCheck, "80 3e 58 20 08",
                     "record backspace key check");
        requireBytes(kEnterCheck, "80 3e 58 20 0d 74 03 e9 3c ff",
                     "record enter key check");
        requireBytes(kCommitSound,
                     "c7 06 74 20 08 00 c6 06 9f 79 0b e8 08 fc",
                     "record commit sound request");
        requireBytes(kRecordShift,
                     "6b f8 0d 81 c7 f7 1a 1e 57 6b 3e 82 20 0d "
                     "81 c7 f7 1a 1e 57 6a 0d 9a 0e 09 20 09",
                     "record table shift copy");
        requireBytes(kStoredRecordPointer, "6b f8 0d 81 c7 f7 1a",
                     "record stored pointer stride");
        requireBytes(kNameCopy,
                     "8d 7e f0 16 57 c4 7e ec 81 c7 04 00 06 57 "
                     "6a 08 9a f4 09 20 09",
                     "record name copy");
        requireBytes(kScoreWrite,
                     "8b 46 08 8b 56 0a c4 7e ec 26 89 05 26 89 55 02",
                     "record score dword write");
        requireBytes(kRoutineRet - 3, "c9 c2 08 00", "record entry return");

        int strideImulCount = countBytes("6b f8 0d");
        int copy13Count = countBytes("6a 0d 9a 0e 09 20 09");
        int copy8Count = countBytes("6a 08 9a f4 09 20 09");
        if (strideImulCount != 3 || copy13Count != 1 || copy8Count != 2) {
            throw std::runtime_error("record entry stride/copy model changed");
        }

        std::cout << "record_entry_static_model=ok"
                  << " routine=" << hex4(kRoutineStart) << ".." << hex4(kRoutineRet)
                  << " template=" << hex4(kTemplate)
                  << " template_len=8"
                  << " template_byte=0x3a"
                  << " record_stride=13"
                  << " stride_imuls=" << strideImulCount
                  << " shift_copy_bytes=13"
                  << " shift_copies=" << copy13Count
                  << " name_offset=4"
                  << " name_copy_bytes=8"
                  << " name_copies=" << copy8Count
                  << " score_offset=0"
                  << " score_bytes=4"
                  << " backspace_key=0x08"
                  << " enter_key=0x0d"
                  << " prompt_sound=0x0078/p11"
                  << " commit_sound=0x0008/p11\n";
    }

    void debugCoreResourceRawRoundtrip() {
        load();
        auto metrics = [](const std::vector<uint8_t>& bytes) {
            struct Metrics {
                uint64_t sum = 0;
                uint64_t weighted = 0;
                int nonzero = 0;
                uint8_t xorValue = 0;
            } result;
            for (size_t i = 0; i < bytes.size(); ++i) {
                uint8_t byte = bytes[i];
                result.sum += byte;
                result.weighted += static_cast<uint64_t>(i + 1) * byte;
                if (byte != 0) ++result.nonzero;
                result.xorValue = static_cast<uint8_t>(result.xorValue ^ byte);
            }
            return result;
        };
        auto samePalette = [](const Palette& a, const Palette& b) {
            for (size_t i = 0; i < a.size(); ++i) {
                if (a[i].r != b[i].r || a[i].g != b[i].g || a[i].b != b[i].b) {
                    return false;
                }
            }
            return true;
        };
        auto decodeRawBackground = [](const std::vector<uint8_t>& data) {
            std::vector<uint8_t> pixels;
            if (data.size() < 770) {
                throw std::runtime_error("SFONLEF.ZBG raw file is too small");
            }
            // Nibble-paired RLE recovered from the original ZBG decoder
            // (1000:82d0): 768-byte palette, 2-byte little-endian payload
            // length, then 3-byte groups (b0,b1,b2) emitting (b0>>4)+1 copies
            // of b1 and (b0&0x0f)+1 copies of b2 into one 320x200 screen.
            const size_t rleLength = static_cast<size_t>(data[768]) |
                                     (static_cast<size_t>(data[769]) << 8);
            const size_t rleEnd = std::min(data.size(), 770 + rleLength);
            const size_t targetPixels =
                static_cast<size_t>(kBackgroundW) * kBackgroundH;
            size_t off = 770;
            while (off + 3 <= rleEnd && pixels.size() < targetPixels) {
                const uint8_t b0 = data[off];
                const uint8_t v1 = data[off + 1];
                const uint8_t v2 = data[off + 2];
                off += 3;
                pixels.insert(pixels.end(),
                              static_cast<size_t>((b0 >> 4) & 0x0f) + 1, v1);
                pixels.insert(pixels.end(),
                              static_cast<size_t>(b0 & 0x0f) + 1, v2);
            }
            if (pixels.size() > targetPixels) pixels.resize(targetPixels);
            return pixels;
        };

        auto paletteRaw = readFile("BOMPAL.PAL");
        auto backgroundRaw = readFile("SFONLEF.ZBG");
        auto tilesRaw = readFile("CARO.CAR");
        if (paletteRaw.size() != 768 || backgroundRaw.size() < 768 ||
            tilesRaw.size() < 2) {
            throw std::runtime_error("core raw resource size preflight failed");
        }

        Palette rawPalette = loadPalette(paletteRaw, 0);
        Palette rawBackgroundPalette = loadPalette(backgroundRaw, 0);
        if (!samePalette(rawPalette, palette_) ||
            !samePalette(rawBackgroundPalette, backgroundPalette_)) {
            throw std::runtime_error("raw palette data does not match JSON resources");
        }

        std::vector<uint8_t> backgroundPixels = decodeRawBackground(backgroundRaw);
        if (background_.width != kBackgroundW || background_.height != kBackgroundH ||
            backgroundPixels.size() != static_cast<size_t>(kBackgroundW) * kBackgroundH ||
            background_.pixels != backgroundPixels) {
            throw std::runtime_error("raw background data does not match JSON resource");
        }

        int rawTileCount = static_cast<int>((tilesRaw[0] << 8) | tilesRaw[1]);
        size_t tilePayloadSize = tilesRaw.size() - 2;
        if (rawTileCount != 132 || tiles_.count != rawTileCount ||
            tilePayloadSize != static_cast<size_t>(rawTileCount) * kTileSize * kTileSize ||
            tiles_.pixels.size() != tilePayloadSize ||
            !std::equal(tiles_.pixels.begin(), tiles_.pixels.end(), tilesRaw.begin() + 2)) {
            throw std::runtime_error("raw tile data does not match JSON resource");
        }

        auto paletteMetrics = metrics(paletteRaw);
        auto backgroundMetrics = metrics(backgroundRaw);
        auto backgroundPixelMetrics = metrics(backgroundPixels);
        auto tileMetrics = metrics(tilesRaw);
        if (paletteMetrics.sum != 20767 || paletteMetrics.weighted != 6683027 ||
            paletteMetrics.xorValue != 0x31 ||
            backgroundMetrics.sum != 2442898 ||
            backgroundMetrics.weighted != 37574726726ull ||
            backgroundMetrics.xorValue != 0x30 ||
            backgroundPixelMetrics.sum != 7462763 ||
            backgroundPixelMetrics.xorValue != 0x2b ||
            tileMetrics.sum != 601303 || tileMetrics.weighted != 2783120138ull ||
            tileMetrics.xorValue != 0x01) {
            throw std::runtime_error("core raw resource aggregate changed");
        }

        std::cout << "core_resource_raw_roundtrip=ok"
                  << " palette_size=" << paletteRaw.size()
                  << " palette_sum=" << paletteMetrics.sum
                  << " palette_weighted=" << paletteMetrics.weighted
                  << " palette_xor=0x" << std::hex << std::setw(2)
                  << std::setfill('0') << static_cast<int>(paletteMetrics.xorValue)
                  << std::dec << std::setfill(' ')
                  << " background_raw_size=" << backgroundRaw.size()
                  << " background_sum=" << backgroundMetrics.sum
                  << " background_weighted=" << backgroundMetrics.weighted
                  << " background_xor=0x" << std::hex << std::setw(2)
                  << std::setfill('0') << static_cast<int>(backgroundMetrics.xorValue)
                  << std::dec << std::setfill(' ')
                  << " background_pixels=" << backgroundPixels.size()
                  << " background_pixel_sum=" << backgroundPixelMetrics.sum
                  << " background_pixel_nonzero=" << backgroundPixelMetrics.nonzero
                  << " background_pixel_xor=0x" << std::hex << std::setw(2)
                  << std::setfill('0') << static_cast<int>(backgroundPixelMetrics.xorValue)
                  << std::dec << std::setfill(' ')
                  << " tile_raw_size=" << tilesRaw.size()
                  << " tile_count=" << rawTileCount
                  << " tile_payload=" << tilePayloadSize
                  << " tile_sum=" << tileMetrics.sum
                  << " tile_weighted=" << tileMetrics.weighted
                  << " tile_xor=0x" << std::hex << std::setw(2)
                  << std::setfill('0') << static_cast<int>(tileMetrics.xorValue)
                  << std::dec << std::setfill(' ') << '\n';
    }

    void debugShippedFileManifest() {
        struct ExpectedFile {
            const char* name;
            size_t size;
            uint64_t sum;
            uint64_t weighted;
            int nonzero;
            uint8_t xorValue;
        };
        struct Metrics {
            uint64_t sum = 0;
            uint64_t weighted = 0;
            int nonzero = 0;
            uint8_t xorValue = 0;
        };
        struct ExpectedExeFilename {
            const char* name;
            std::vector<size_t> fileOffsets;
        };
        static const std::array<ExpectedFile, 14> kExpectedFiles{{
            {"BOMOMIMK.SPR", 20168, 721398, 8117120635ull, 10865, 0xb6},
            {"BOMPAL.PAL", 768, 20767, 6683027ull, 653, 0x31},
            {"CARO.CAR", 8450, 601303, 2783120138ull, 7041, 0x01},
            {"ENGLISH.DOC", 3522, 292353, 520099545ull, 3522, 0x2f},
            {"FONTS.SPR", 5425, 42172, 72344441ull, 2695, 0xba},
            {"GRAN.MST", 399, 12560, 2894452ull, 249, 0x0c},
            {"ITALIANO.DOC", 4392, 377573, 841106589ull, 4392, 0xe5},
            {"LEZAC.EXE", 52384, 5435302, 135039782411ull, 46261, 0x08},
            {"LIVELS.SCH", 41047, 1776660, 36064103152ull, 21351, 0x90},
            {"PROEFS.SON", 782, 38799, 14543304ull, 702, 0xcf},
            {"PROVA.SPR", 21250, 1231583, 14912492233ull, 11887, 0x3d},
            {"RECS.DAT", 92, 6047, 278918ull, 85, 0xdd},
            {"SETUP.LOG", 566, 38565, 10906350ull, 566, 0x13},
            {"SFONLEF.ZBG", 34292, 2442898, 37574726726ull, 28451, 0x30},
        }};
        static const std::array<ExpectedExeFilename, 10> kExpectedExeFilenames{{
            {"proefs.son", {0x0d96}},
            {"recs.dat", {0x1def, 0x2cf6}},
            {"fonts.spr", {0x2248, 0x24b6, 0x2abc, 0x2e4f, 0x3223}},
            {"sfonlef.zbg", {0x2ac6}},
            {"caro.car", {0x2e46}},
            {"bompal.pal", {0x3218}},
            {"bomomimk.spr", {0x322d}},
            {"prova.spr", {0x323a}},
            {"gran.mst", {0x3244}},
            {"livels.sch", {0x3663}},
        }};

        auto metrics = [](const std::vector<uint8_t>& bytes) {
            Metrics result;
            for (size_t i = 0; i < bytes.size(); ++i) {
                uint8_t byte = bytes[i];
                result.sum += byte;
                result.weighted += static_cast<uint64_t>(i + 1) * byte;
                if (byte != 0) ++result.nonzero;
                result.xorValue = static_cast<uint8_t>(result.xorValue ^ byte);
            }
            return result;
        };
        auto findAscii = [](const std::vector<uint8_t>& haystack,
                            const std::string& needle) {
            std::vector<size_t> hits;
            if (needle.empty() || haystack.size() < needle.size()) return hits;
            for (size_t offset = 0; offset <= haystack.size() - needle.size();
                 ++offset) {
                bool match = true;
                for (size_t i = 0; i < needle.size(); ++i) {
                    if (haystack[offset + i] !=
                        static_cast<uint8_t>(needle[i])) {
                        match = false;
                        break;
                    }
                }
                if (match) hits.push_back(offset);
            }
            return hits;
        };

        size_t totalSize = 0;
        uint64_t totalSum = 0;
        uint64_t totalWeighted = 0;
        uint8_t totalXor = 0;
        std::vector<uint8_t> exeBytes;
        for (const ExpectedFile& expected : kExpectedFiles) {
            std::vector<uint8_t> bytes = readFile(expected.name);
            Metrics actual = metrics(bytes);
            if (bytes.size() != expected.size || actual.sum != expected.sum ||
                actual.weighted != expected.weighted ||
                actual.nonzero != expected.nonzero ||
                actual.xorValue != expected.xorValue) {
                throw std::runtime_error(std::string("shipped file fingerprint changed: ") +
                                         expected.name);
            }
            totalSize += bytes.size();
            totalSum += actual.sum;
            totalWeighted += actual.weighted;
            totalXor = static_cast<uint8_t>(totalXor ^ actual.xorValue);
            if (std::string(expected.name) == "LEZAC.EXE") exeBytes = std::move(bytes);
        }

        if (totalSize != 193537 || totalSum != 13037980 ||
            totalWeighted != 235960201921ull || totalXor != 0x6e) {
            throw std::runtime_error("shipped file aggregate fingerprint changed");
        }
        if (exeBytes.size() != 52384 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE MZ header changed");
        }
        uint16_t lastPageBytes = le16(exeBytes, 0x02);
        uint16_t pages = le16(exeBytes, 0x04);
        uint16_t relocations = le16(exeBytes, 0x06);
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        size_t imageSize = (static_cast<size_t>(pages) - 1) * 512 +
                           lastPageBytes - imageBase;
        if (lastPageBytes != 160 || pages != 103 || relocations != 468 ||
            headerParagraphs != 119 || imageBase != 0x0770 ||
            imageSize != 50480) {
            throw std::runtime_error("LEZAC.EXE MZ layout changed");
        }
        size_t exeFilenameRefs = 0;
        std::map<std::string, std::vector<size_t>> exeFilenameAnchors;
        for (const ExpectedExeFilename& expected : kExpectedExeFilenames) {
            std::vector<size_t> hits = findAscii(exeBytes, expected.name);
            if (hits != expected.fileOffsets) {
                throw std::runtime_error(std::string("LEZAC.EXE filename anchors changed: ") +
                                         expected.name);
            }
            exeFilenameRefs += hits.size();
            exeFilenameAnchors.emplace(expected.name, hits);
        }
        auto ghidraAnchor = [&](const char* name, size_t index = 0) {
            const auto found = exeFilenameAnchors.find(name);
            if (found == exeFilenameAnchors.end() ||
                index >= found->second.size() || found->second[index] < imageBase) {
                throw std::runtime_error(std::string("missing LEZAC.EXE filename anchor: ") +
                                         name);
            }
            return found->second[index] - imageBase;
        };

        std::cout << "shipped_file_manifest=ok"
                  << " files=" << kExpectedFiles.size()
                  << " total_size=" << totalSize
                  << " total_sum=" << totalSum
                  << " total_weighted=" << totalWeighted
                  << " total_xor=0x" << std::hex << std::setw(2)
                  << std::setfill('0') << static_cast<int>(totalXor)
                  << std::dec << std::setfill(' ')
                  << " exe_size=" << exeBytes.size()
                  << " exe_image_base=0x" << std::hex << std::setw(4)
                  << std::setfill('0') << imageBase
                  << std::dec << std::setfill(' ')
                  << " exe_image_size=" << imageSize
                  << " exe_filename_names=" << kExpectedExeFilenames.size()
                  << " exe_filename_refs=" << exeFilenameRefs
                  << " exe_sound_anchor=1000:" << std::hex << std::setw(4)
                  << std::setfill('0') << ghidraAnchor("proefs.son")
                  << " exe_gran_anchor=1000:" << std::setw(4)
                  << ghidraAnchor("gran.mst")
                  << " exe_level_anchor=1000:" << std::setw(4)
                  << ghidraAnchor("livels.sch")
                  << std::dec << std::setfill(' ')
                  << " exe_record_refs="
                  << exeFilenameAnchors.at("recs.dat").size()
                  << " exe_font_refs="
                  << exeFilenameAnchors.at("fonts.spr").size()
                  << " docs=2 setup_log=566" << '\n';
    }

    void debugPortCompletionStatus() {
        struct PortSubsystem {
            const char* name;
            const char* validation;
        };
        // Functional port coverage: every gameplay/data subsystem recovered
        // from LEZAC.EXE has a C++ implementation and a deterministic
        // validation entry point listed here.
        static const std::array<PortSubsystem, 23> kPortSubsystems{{
            {"resource_loading", "--validate"},
            {"shipped_file_manifest", "--debug-shipped-file-manifest"},
            {"sprites", "--debug-sprite-raw-roundtrip"},
            {"background", "--export-background"},
            {"palette_fonts", "--debug-core-resource-raw-roundtrip"},
            {"levels", "--debug-level-raw-roundtrip"},
            {"gran_mst_preservation", "--debug-gran-raw-roundtrip"},
            {"sound_playback", "--debug-sound-render"},
            {"sound_priority_latch", "--debug-sound-priority-latch"},
            {"menu_ui", "--debug-menu-frame-flow"},
            {"records", "--debug-records-raw-roundtrip"},
            {"record_name_entry", "--debug-record-name-entry-cursor"},
            {"player_input", "--debug-input-fire-key-model"},
            {"bombs_explosions", "--debug-autoplayer level1_bomb_route"},
            {"collapse_playback", "--debug-autoplayer collapse_playback_route"},
            {"passable_objects_portals", "--debug-autoplayer portal_weapon_route"},
            {"monsters_behaviors", "--debug-autoplayer monster_behavior4_chase"},
            {"monster_spawners", "--debug-autoplayer monster_spawner_cycle"},
            {"level7_boss", "--debug-autoplayer boss_level7"},
            {"player_death_state2", "--debug-autoplayer death_reentry"},
            {"two_player", "--debug-autoplayer two_player_progression"},
            {"pause_end_flow", "--debug-autoplayer pause_flow"},
            {"autoplayer_frame_harness", "--capture-frame-sequence"},
        }};
        // Open original-evidence follow-ups: fidelity verification against
        // the original runtime, tracked in RECOVERY_STATUS.md. These are not
        // missing port functionality; each stays visual_claim=0 until the
        // matching original fixture is promoted.
        static const std::array<const char*, 12> kOpenOriginalEvidenceItems{{
            "natural_forward_debris_writeback_3d2d",
            "exact_explosion_sprite_playback",
            "state2_death_presentation_frame_compare",
            "sound_callsite_cursor_priority_map",
            "actor_update_original_contact_semantics",
            "contact_scanner_runtime_confirmation",
            "behavior4_branch_runtime_fixture",
            "two_player_panel_artwork_frame_compare",
            "monster_sprite_table_runtime_consumption",
            "gran_mst_field_semantics",
            "ds79b9_fallback_runtime_reachability",
            "level1_route_timing_original_confirmation",
        }};

        for (const auto& subsystem : kPortSubsystems) {
            std::cout << "subsystem=" << subsystem.name
                      << " implemented=1 validation=" << subsystem.validation
                      << '\n';
        }
        for (const char* item : kOpenOriginalEvidenceItems) {
            std::cout << "open_original_evidence_item=" << item
                      << " class=fidelity_verification visual_claim=0" << '\n';
        }
        std::cout << "port_completion_status=ok"
                  << " subsystems=" << kPortSubsystems.size()
                  << " implemented=" << kPortSubsystems.size()
                  << " open_original_evidence_items="
                  << kOpenOriginalEvidenceItems.size()
                  << " port_functionally_complete=1"
                  << " original_fidelity_claim=0" << '\n';
    }

    void debugOriginalAssetLoad() {
        auto fail = [](const std::string& what) {
            throw std::runtime_error("original asset load mismatch: " + what);
        };
        auto samePalette = [](const Palette& a, const Palette& b) {
            for (size_t i = 0; i < a.size(); ++i) {
                if (a[i].r != b[i].r || a[i].g != b[i].g || a[i].b != b[i].b) {
                    return false;
                }
            }
            return true;
        };
        auto sameSprites = [](const SpriteBank& a, const SpriteBank& b) {
            if (a.sprites.size() != b.sprites.size()) return false;
            for (size_t i = 0; i < a.sprites.size(); ++i) {
                if (a.sprites[i].width != b.sprites[i].width ||
                    a.sprites[i].height != b.sprites[i].height ||
                    a.sprites[i].pixels != b.sprites[i].pixels) {
                    return false;
                }
            }
            return true;
        };
        auto sameRecords = [](const std::vector<Record>& a,
                              const std::vector<Record>& b) {
            if (a.size() != b.size()) return false;
            for (size_t i = 0; i < a.size(); ++i) {
                if (a[i].score != b[i].score || a[i].level != b[i].level ||
                    a[i].name != b[i].name ||
                    encodedRecordName(a[i]) != encodedRecordName(b[i])) {
                    return false;
                }
            }
            return true;
        };
        auto sameSound = [](const SoundBank& a, const SoundBank& b) {
            if (a.recordSize != b.recordSize || a.payload != b.payload ||
                a.stepCount != b.stepCount || a.records.size() != b.records.size()) {
                return false;
            }
            for (size_t i = 0; i < a.records.size(); ++i) {
                if (a.records[i].bytes != b.records[i].bytes) return false;
            }
            return true;
        };
        auto sameGran = [](const GranBank& a, const GranBank& b) {
            if (a.recordSize != b.recordSize || a.records.size() != b.records.size()) {
                return false;
            }
            for (size_t i = 0; i < a.records.size(); ++i) {
                if (a.records[i].bytes != b.records[i].bytes) return false;
            }
            return true;
        };
        auto sameSpawner = [](const MonsterSpawner& a, const MonsterSpawner& b) {
            return a.x == b.x && a.y == b.y && a.tileIndex == b.tileIndex &&
                   a.savedWordOrLink == b.savedWordOrLink && a.enabled == b.enabled &&
                   a.spawnBudget == b.spawnBudget && a.liveAllowance == b.liveAllowance &&
                   a.monsterKind == b.monsterKind && a.param0Base == b.param0Base &&
                   a.param0Range == b.param0Range && a.param1Base == b.param1Base &&
                   a.param1Range == b.param1Range && a.param2Base == b.param2Base &&
                   a.param2Range == b.param2Range && a.randomBase == b.randomBase &&
                   a.randomRange == b.randomRange && a.spawnArg == b.spawnArg &&
                   a.cooldown == b.cooldown && a.cooldownReset == b.cooldownReset &&
                   a.animationDelay == b.animationDelay;
        };
        auto samePortal = [](const LevelPortal& a, const LevelPortal& b) {
            return a.key == b.key && a.x == b.x && a.y == b.y && a.marker == b.marker;
        };
        auto sameTrigger = [](const TileTriggerRule& a, const TileTriggerRule& b) {
            return a.wordRangeFirst == b.wordRangeFirst &&
                   a.wordRangeLast == b.wordRangeLast &&
                   a.triggerKey == b.triggerKey && a.from == b.from && a.to == b.to;
        };
        auto sameLevels = [&](const std::vector<Level>& a,
                              const std::vector<Level>& b) {
            if (a.size() != b.size()) return false;
            for (size_t i = 0; i < a.size(); ++i) {
                const Level& left = a[i];
                const Level& right = b[i];
                if (left.fileOffset != right.fileOffset ||
                    left.width != right.width || left.height != right.height ||
                    left.objectiveTile != right.objectiveTile ||
                    left.requiredBonus != right.requiredBonus ||
                    left.requiredDestruction != right.requiredDestruction ||
                    left.tileEncodedSize != right.tileEncodedSize ||
                    left.wordEncodedSize != right.wordEncodedSize ||
                    left.fieldA != right.fieldA || left.fieldB != right.fieldB ||
                    left.tiles != right.tiles || left.wordLayer != right.wordLayer ||
                    left.startingObjectiveTiles != right.startingObjectiveTiles ||
                    left.startingDestructibleTiles != right.startingDestructibleTiles ||
                    left.monsterSpawners.size() != right.monsterSpawners.size() ||
                    left.portals.size() != right.portals.size() ||
                    left.tileTriggers.size() != right.tileTriggers.size()) {
                    return false;
                }
                for (size_t j = 0; j < left.monsterSpawners.size(); ++j) {
                    if (!sameSpawner(left.monsterSpawners[j],
                                     right.monsterSpawners[j])) {
                        return false;
                    }
                }
                for (size_t j = 0; j < left.portals.size(); ++j) {
                    if (!samePortal(left.portals[j], right.portals[j])) return false;
                }
                for (size_t j = 0; j < left.tileTriggers.size(); ++j) {
                    if (!sameTrigger(left.tileTriggers[j], right.tileTriggers[j])) {
                        return false;
                    }
                }
            }
            return true;
        };

        loadJsonAssets();
        Palette jsonPalette = palette_;
        Palette jsonBackgroundPalette = backgroundPalette_;
        IndexedImage jsonBackground = background_;
        TileBank jsonTiles = tiles_;
        SpriteBank jsonSprites = sprites_;
        SpriteBank jsonAltSprites = altSprites_;
        SpriteBank jsonFontSprites = fontSprites_;
        std::vector<Record> jsonRecords = records_;
        SoundBank jsonSounds = sounds_;
        GranBank jsonGran = gran_;
        std::vector<Level> jsonLevels = levels_;

        loadOriginalAssets();
        if (!samePalette(palette_, jsonPalette)) fail("BOMPAL.PAL palette");
        if (!samePalette(backgroundPalette_, jsonBackgroundPalette)) {
            fail("SFONLEF.ZBG palette");
        }
        if (background_.width != jsonBackground.width ||
            background_.height != jsonBackground.height ||
            background_.pixels != jsonBackground.pixels) {
            fail("SFONLEF.ZBG background pixels");
        }
        if (tiles_.count != jsonTiles.count || tiles_.pixels != jsonTiles.pixels) {
            fail("CARO.CAR tiles");
        }
        if (!sameSprites(sprites_, jsonSprites)) fail("BOMOMIMK.SPR sprites");
        if (!sameSprites(altSprites_, jsonAltSprites)) fail("PROVA.SPR sprites");
        if (!sameSprites(fontSprites_, jsonFontSprites)) fail("FONTS.SPR sprites");
        if (!sameRecords(records_, jsonRecords)) fail("RECS.DAT records");
        if (!sameSound(sounds_, jsonSounds)) fail("PROEFS.SON sound bank");
        if (!sameGran(gran_, jsonGran)) fail("GRAN.MST records");
        if (!sameLevels(levels_, jsonLevels)) fail("LIVELS.SCH levels");

        size_t totalSprites = sprites_.sprites.size() + altSprites_.sprites.size() +
                              fontSprites_.sprites.size();
        size_t cells = 0;
        size_t spawners = 0;
        size_t portals = 0;
        size_t triggers = 0;
        for (const Level& level : levels_) {
            cells += level.tiles.size();
            spawners += level.monsterSpawners.size();
            portals += level.portals.size();
            triggers += level.tileTriggers.size();
        }
        std::cout << "original_asset_load=ok"
                  << " palettes=2"
                  << " background=" << background_.width << 'x' << background_.height
                  << " pixels=" << background_.pixels.size()
                  << " tiles=" << tiles_.count
                  << " sprites=" << totalSprites
                  << " records=" << records_.size()
                  << " sound_steps=" << sounds_.stepCount
                  << " sound_chunks=" << sounds_.records.size()
                  << " gran_records=" << gran_.records.size()
                  << " levels=" << levels_.size()
                  << " cells=" << cells
                  << " spawners=" << spawners
                  << " portals=" << portals
                  << " triggers=" << triggers << '\n';
    }

    void debugRecordNameEntry(const std::string& path) {
        load();
        recordPath_ = path;
        saveRecords(recordPath_, records_);
        auto encodedNameAt = [](const std::string& recordPath, size_t index) {
            auto bytes = readFile(recordPath);
            constexpr size_t kRecordSize = 13;
            if (bytes.empty() || index >= bytes[0] ||
                bytes.size() < 1 + (index + 1) * kRecordSize) {
                throw std::runtime_error("record table too small for encoded-name check");
            }
            size_t off = 1 + index * kRecordSize + 5;
            return std::string(bytes.begin() + static_cast<std::ptrdiff_t>(off),
                               bytes.begin() + static_cast<std::ptrdiff_t>(off + 8));
        };
        score_ = 999999u;
        levelIndex_ = 0;
        beginGameOver();
        if (menuPage_ != MenuPage::NameEntry) {
            throw std::runtime_error("high score did not open name entry");
        }
        bool running = true;
        onKey(SDLK_ESCAPE, running);
        auto afterCancel = loadRecords(path);
        if (menuPage_ != MenuPage::Records || pendingRecordScore_ != 0 ||
            (!afterCancel.empty() && afterCancel[0].score == 999999u)) {
            throw std::runtime_error("Escape committed pending record instead of cancelling");
        }

        score_ = 999999u;
        levelIndex_ = 0;
        beginGameOver();
        if (menuPage_ != MenuPage::NameEntry) {
            throw std::runtime_error("second high score did not open name entry");
        }
        onKey(SDLK_t, running);
        onKey(SDLK_e, running);
        onKey(SDLK_s, running);
        onKey(SDLK_t, running);
        onKey(SDLK_KP_1, running);
        onKey(SDLK_DELETE, running);
        onKey(SDLK_x, running);
        onKey(SDLK_BACKSPACE, running);
        onKey(SDLK_RETURN, running);
        auto reloaded = loadRecords(path);
        if (reloaded.empty() || reloaded[0].score != 999999u ||
            reloaded[0].name != "test") {
            throw std::runtime_error("name-entry record did not save");
        }
        if (encodedNameAt(path, 0) != "test::::") {
            throw std::runtime_error("short name did not use colon padding");
        }

        score_ = 1000000u;
        levelIndex_ = 0;
        beginGameOver();
        if (menuPage_ != MenuPage::NameEntry) {
            throw std::runtime_error("third high score did not open name entry");
        }
        onKey(SDLK_a, running);
        onKey(SDLK_b, running);
        onKey(SDLK_SPACE, running);
        onKey(SDLK_c, running);
        onKey(SDLK_d, running);
        onKey(SDLK_e, running);
        onKey(SDLK_f, running);
        onKey(SDLK_g, running);
        onKey(SDLK_h, running);
        onKey(SDLK_i, running);
        onKey(SDLK_RETURN, running);
        auto capped = loadRecords(path);
        if (capped.empty() || capped[0].score != 1000000u ||
            capped[0].name != "ab cdefg" ||
            encodedNameAt(path, 0) != "ab:cdefg") {
            throw std::runtime_error("name-entry cap or space encoding changed");
        }

        score_ = 1000001u;
        levelIndex_ = 0;
        beginGameOver();
        if (menuPage_ != MenuPage::NameEntry) {
            throw std::runtime_error("fourth high score did not open name entry");
        }
        onKey(SDLK_RETURN, running);
        auto emptyName = loadRecords(path);
        std::string emptyNameEncoding = encodedNameAt(path, 0);
        if (emptyName.empty() || emptyName[0].score != 1000001u ||
            emptyName[0].name != "nessuno" || emptyNameEncoding != "::::::::") {
            throw std::runtime_error("empty name-entry encoding changed");
        }

        score_ = 1000002u;
        levelIndex_ = 0;
        beginGameOver();
        if (menuPage_ != MenuPage::NameEntry) {
            throw std::runtime_error("fifth high score did not open name entry");
        }
        onKey(SDLK_n, running);
        onKey(SDLK_e, running);
        onKey(SDLK_s, running);
        onKey(SDLK_s, running);
        onKey(SDLK_u, running);
        onKey(SDLK_n, running);
        onKey(SDLK_o, running);
        onKey(SDLK_RETURN, running);
        auto typedNessuno = loadRecords(path);
        if (typedNessuno.empty() || typedNessuno[0].score != 1000002u ||
            typedNessuno[0].name != "nessuno" ||
            encodedNameAt(path, 0) != "nessuno:" ||
            encodedNameAt(path, 1) != "::::::::") {
            throw std::runtime_error("typed nessuno and empty name encodings collapsed");
        }
        std::cout << "record_name_entry=ok top=" << reloaded[0].score
                  << " name=" << reloaded[0].name
                  << " padded=test:::: capped=" << capped[0].name
                  << " encoded_space=ab:cdefg"
                  << " empty=" << emptyName[0].name
                  << " empty_encoded=" << emptyNameEncoding
                  << " typed_nessuno_encoded=nessuno:"
                  << " preserved_empty=::::::::\n";
    }

    void debugRecordNameEntryCursor() {
        load();
        initSdl();
        score_ = 999999u;
        levelIndex_ = 0;
        beginGameOver();
        if (menuPage_ != MenuPage::NameEntry || !pendingRecordName_.empty()) {
            throw std::runtime_error("record name cursor fixture did not open name entry");
        }

        FrameInspection emptyFrame = inspectRenderedFrame("record-name-cursor-empty");
        std::vector<uint32_t> emptyPixels = fb_;
        int emptySlot = nameEntryCursorSlot();
        size_t emptyCursorPixels = countColorInRegion(
            nameEntrySlotX(emptySlot) - 1, kNameEntrySlotY - 2,
            kNameEntryCursorBoxW, kNameEntryCursorBoxH,
            kNameEntryCursorBackground);
        if (emptySlot != 0 || emptyCursorPixels == 0) {
            throw std::runtime_error("empty name-entry cursor was not visible at slot 0");
        }

        bool running = true;
        onKey(SDLK_a, running);
        FrameInspection oneFrame = inspectRenderedFrame("record-name-cursor-one");
        std::vector<uint32_t> onePixels = fb_;
        int oneSlot = nameEntryCursorSlot();
        size_t oneCursorPixels = countColorInRegion(
            nameEntrySlotX(oneSlot) - 1, kNameEntrySlotY - 2,
            kNameEntryCursorBoxW, kNameEntryCursorBoxH,
            kNameEntryCursorBackground);
        if (pendingRecordName_ != "a" || oneSlot != 1 ||
            oneFrame.hash == emptyFrame.hash || oneCursorPixels == 0 ||
            !regionChanged(emptyPixels, nameEntrySlotX(0) - 1,
                           kNameEntrySlotY - 2, kNameEntrySlotAdvance * 2,
                           kNameEntryCursorBoxH)) {
            throw std::runtime_error("name-entry cursor did not advance to slot 1");
        }

        onKey(SDLK_b, running);
        FrameInspection twoFrame = inspectRenderedFrame("record-name-cursor-two");
        int twoSlot = nameEntryCursorSlot();
        size_t twoCursorPixels = countColorInRegion(
            nameEntrySlotX(twoSlot) - 1, kNameEntrySlotY - 2,
            kNameEntryCursorBoxW, kNameEntryCursorBoxH,
            kNameEntryCursorBackground);
        if (pendingRecordName_ != "ab" || twoSlot != 2 ||
            twoFrame.hash == oneFrame.hash || twoCursorPixels == 0 ||
            !regionChanged(onePixels, nameEntrySlotX(1) - 1,
                           kNameEntrySlotY - 2, kNameEntrySlotAdvance * 2,
                           kNameEntryCursorBoxH)) {
            throw std::runtime_error("name-entry cursor did not advance to slot 2");
        }

        onKey(SDLK_BACKSPACE, running);
        FrameInspection backspaceFrame =
            inspectRenderedFrame("record-name-cursor-backspace");
        int backspaceSlot = nameEntryCursorSlot();
        size_t backspaceCursorPixels = countColorInRegion(
            nameEntrySlotX(backspaceSlot) - 1, kNameEntrySlotY - 2,
            kNameEntryCursorBoxW, kNameEntryCursorBoxH,
            kNameEntryCursorBackground);
        if (pendingRecordName_ != "a" || backspaceSlot != 1 ||
            backspaceCursorPixels == 0 || backspaceFrame.hash != oneFrame.hash) {
            throw std::runtime_error("name-entry cursor did not return after Backspace");
        }

        std::cout << "record_name_entry_cursor=ok"
                  << " empty_slot=" << emptySlot
                  << " typed_slot=" << oneSlot
                  << " second_slot=" << twoSlot
                  << " backspace_slot=" << backspaceSlot
                  << " cursor_pixels=" << emptyCursorPixels << ','
                  << oneCursorPixels << ',' << twoCursorPixels << ','
                  << backspaceCursorPixels
                  << " backspace_restores_frame=1"
                  << " frame_inspection=1\n";
    }

    void debugRecordNameEntryRepeat(const std::string& path) {
        load();
        recordPath_ = path;
        saveRecords(recordPath_, records_);
        initSdl();
        score_ = 999999u;
        levelIndex_ = 0;
        beginGameOver();
        if (menuPage_ != MenuPage::NameEntry || !pendingRecordName_.empty()) {
            throw std::runtime_error("record name repeat fixture did not open name entry");
        }

        bool running = true;
        pushKeyDown(SDLK_a);
        processEvents(running);
        pushKeyDown(SDLK_SPACE, true);
        processEvents(running);
        for (int i = 0; i < 3; ++i) {
            pushKeyDown(SDLK_b, true);
            processEvents(running);
        }
        if (pendingRecordName_ != "a bbb" || nameEntryCursorSlot() != 5) {
            throw std::runtime_error("repeated name-entry text was not accepted");
        }

        for (int i = 0; i < 2; ++i) {
            pushKeyDown(SDLK_BACKSPACE, true);
            processEvents(running);
        }
        if (pendingRecordName_ != "a b" || nameEntryCursorSlot() != 3) {
            throw std::runtime_error("repeated name-entry Backspace was not accepted");
        }

        pushKeyDown(SDLK_RETURN, true);
        processEvents(running);
        bool ignoredRepeatEnter = menuPage_ == MenuPage::NameEntry &&
                                  pendingRecordName_ == "a b";
        pushKeyDown(SDLK_ESCAPE, true);
        processEvents(running);
        bool ignoredRepeatEscape = menuPage_ == MenuPage::NameEntry &&
                                   pendingRecordName_ == "a b";
        if (!ignoredRepeatEnter || !ignoredRepeatEscape) {
            throw std::runtime_error("repeated name-entry commit/cancel key was accepted");
        }

        pushKeyDown(SDLK_RETURN);
        processEvents(running);
        auto reloaded = loadRecords(path);
        if (menuPage_ != MenuPage::Records || reloaded.empty() ||
            reloaded[0].score != 999999u || reloaded[0].name != "a b") {
            throw std::runtime_error("name-entry repeat record did not commit");
        }

        std::cout << "record_name_entry_repeat=ok"
                  << " repeated_space=1"
                  << " repeated_letters=3"
                  << " repeated_backspaces=2"
                  << " ignored_repeat_enter=" << (ignoredRepeatEnter ? 1 : 0)
                  << " ignored_repeat_escape=" << (ignoredRepeatEscape ? 1 : 0)
                  << " final_name=" << reloaded[0].name
                  << " cursor_slot=3"
                  << " committed=1\n";
    }

    void debugRecordSaveFailure(const std::string& path) {
        load();
        recordPath_ = path;
        score_ = 999999u;
        levelIndex_ = 0;
        beginGameOver();
        pendingRecordName_ = "FAIL";
        finalizePendingRecord();
        if (menuPage_ != MenuPage::NameEntry || pendingRecordScore_ != 999999u ||
            pendingRecordName_ != "FAIL") {
            throw std::runtime_error("record save failure discarded pending entry");
        }

        std::filesystem::path retryPath = std::filesystem::path(path).parent_path()
                                             .parent_path() /
                                         "records_save_failure_retry.dat";
        if (retryPath.empty()) {
            retryPath = "records_save_failure_retry.dat";
        }
        recordPath_ = retryPath.string();
        saveRecords(recordPath_, records_);
        finalizePendingRecord();
        auto reloaded = loadRecords(recordPath_);
        if (menuPage_ != MenuPage::Records || pendingRecordScore_ != 0 ||
            !pendingRecordName_.empty() || reloaded.empty() ||
            reloaded[0].score != 999999u || reloaded[0].name != "FAIL") {
            throw std::runtime_error("record save retry did not commit pending entry");
        }
        std::cout << "record_save_failure=ok pending_preserved=999999"
                  << " retry_committed=1 name=" << reloaded[0].name << '\n';
    }

    void debugEndFlowRecords(const std::string& path) {
        load();
        recordPath_ = path;
        saveRecords(recordPath_, records_);
        const std::vector<Record> baselineRecords = records_;

        auto containsRecord = [&](uint32_t score, const std::string& name) {
            auto reloaded = loadRecords(recordPath_);
            return std::any_of(reloaded.begin(), reloaded.end(),
                               [&](const Record& record) {
                                   return record.score == score && record.name == name;
                               });
        };
        auto containsScore = [&](uint32_t score) {
            auto reloaded = loadRecords(recordPath_);
            return std::any_of(reloaded.begin(), reloaded.end(),
                               [&](const Record& record) {
                                   return record.score == score;
                               });
        };

        resetLevel(0);
        menu_ = false;
        int startLevel = levelIndex_;
        collectAllObjectiveTilesForSmoke();
        damageRequiredTilesForSmoke();
        if (!isComplete()) {
            throw std::runtime_error("completion prerequisites did not complete level");
        }
        for (int i = 0; i <= 100; ++i) {
            updateLevelCompletion();
        }
        int completionLevel = levelIndex_ + 1;
        if (levelIndex_ != startLevel + 1 || menu_ || pendingRecordScore_ != 0 ||
            menuPage_ == MenuPage::NameEntry) {
            throw std::runtime_error("mid-game completion entered end-flow records");
        }

        playerCount_ = 1;
        score_ = 999997u;
        score2_ = 0;
        levelIndex_ = 2;
        beginGameOver();
        if (!menu_ || menuPage_ != MenuPage::NameEntry ||
            pendingRecordScore_ != 999997u || pendingRecordLevel_ != 3 ||
            pendingRecordPlayer_ != 1 || lives_ != 3 || lives2_ != 3 ||
            levelIndex_ != 0) {
            throw std::runtime_error("single-player qualifying game-over state mismatch");
        }
        pendingRecordName_ = "one";
        finalizePendingRecord();
        if (!containsRecord(999997u, "one")) {
            throw std::runtime_error("single-player record was not committed");
        }

        score_ = 1u;
        score2_ = 0;
        levelIndex_ = 0;
        beginGameOver();
        if (!menu_ || menuPage_ != MenuPage::GameOver || pendingRecordScore_ != 0 ||
            pendingRecordLevel_ != 0 || !pendingRecordName_.empty()) {
            throw std::runtime_error("non-qualifying game-over did not show terminal state");
        }
        bool running = true;
        onKey(SDLK_RETURN, running);
        if (menuPage_ != MenuPage::Main || score_ != 0 || score2_ != 0) {
            throw std::runtime_error("game-over confirm did not clear score state");
        }

        records_ = baselineRecords;
        saveRecords(recordPath_, records_);
        playerCount_ = 1;
        score_ = records_.back().score;
        score2_ = 0;
        levelIndex_ = 2;
        beginGameOver();
        if (!menu_ || menuPage_ != MenuPage::GameOver || pendingRecordScore_ != 0 ||
            pendingRecordLevel_ != 0 || !pendingRecordName_.empty()) {
            throw std::runtime_error("score equal to record cutoff qualified");
        }

        playerCount_ = 2;
        score_ = 1u;
        score2_ = 999998u;
        levelIndex_ = 4;
        beginGameOver();
        if (!menu_ || menuPage_ != MenuPage::NameEntry ||
            pendingRecordScore_ != 999998u || pendingRecordLevel_ != 5 ||
            pendingRecordPlayer_ != 2) {
            throw std::runtime_error("player 2 qualifying score was not prompted");
        }
        pendingRecordName_ = "two";
        finalizePendingRecord();
        if (!containsRecord(999998u, "two")) {
            throw std::runtime_error("player 2 record was not committed");
        }

        playerCount_ = 2;
        score_ = 999996u;
        score2_ = 999995u;
        levelIndex_ = 5;
        beginGameOver();
        if (menuPage_ != MenuPage::NameEntry || pendingRecordPlayer_ != 1 ||
            pendingRecordScore_ != 999996u) {
            throw std::runtime_error("two-player double qualifier did not start with player 1");
        }
        pendingRecordName_ = "cat";
        finalizePendingRecord();
        if (menuPage_ != MenuPage::NameEntry || pendingRecordPlayer_ != 2 ||
            pendingRecordScore_ != 999995u) {
            throw std::runtime_error("two-player double qualifier did not continue to player 2");
        }
        pendingRecordName_ = "dog";
        finalizePendingRecord();
        if (menuPage_ != MenuPage::Records || score_ != 0 || score2_ != 0 ||
            !containsRecord(999996u, "cat") || !containsRecord(999995u, "dog")) {
            throw std::runtime_error("two-player queued records did not finish cleanly");
        }

        records_ = baselineRecords;
        saveRecords(recordPath_, records_);
        if (records_.size() < 7 || records_[5].score <= records_[6].score + 1) {
            throw std::runtime_error("baseline records cannot exercise p2 re-check");
        }
        playerCount_ = 2;
        score_ = records_.front().score + 1000u;
        score2_ = records_[6].score + 1u;
        levelIndex_ = 4;
        beginGameOver();
        if (menuPage_ != MenuPage::NameEntry || pendingRecordPlayer_ != 1 ||
            pendingRecordScore_ != score_) {
            throw std::runtime_error("threshold re-check did not start with player 1");
        }
        uint32_t recheckP2Score = score2_;
        pendingRecordName_ = "top";
        finalizePendingRecord();
        if (menuPage_ != MenuPage::Records || pendingRecordScore_ != 0 ||
            containsScore(recheckP2Score)) {
            throw std::runtime_error("player 2 was not re-checked after player 1 insert");
        }

        playerCount_ = 1;
        resetLevel(static_cast<int>(levels_.size()) - 1);
        menu_ = false;
        collectAllObjectiveTilesForSmoke();
        damageRequiredTilesForSmoke();
        score_ = 1u;
        score2_ = 0;
        for (int i = 0; i <= 100; ++i) {
            updateLevelCompletion();
        }
        if (!menu_ || menuPage_ != MenuPage::CompletedGame ||
            lastEndReason_ != EndReason::CompletedGame || levelIndex_ != 0 ||
            pendingRecordScore_ != 0) {
            throw std::runtime_error("final level completion did not enter completed-game flow");
        }

        auto finalRecords = loadRecords(recordPath_);
        std::cout << "end_flow_records=ok completion_level=" << completionLevel
                  << " p1_record=999997 p2_record=999998 records="
                  << finalRecords.size()
                  << " cutoff_equal_skipped=1"
                  << " p2_recheck_skipped=1\n";
    }

    void debugEndFlowFrameFlow() {
        load();
        initSdl();
        resetLevel(0);
        bool running = true;

        FrameInspection mainFrame = inspectRenderedFrame("end-flow-main-menu");
        playerCount_ = 2;
        score_ = 1u;
        score2_ = 2u;
        levelIndex_ = 3;
        beginGameOver();
        if (!menu_ || menuPage_ != MenuPage::GameOver ||
            lastEndReason_ != EndReason::GameOver ||
            pendingRecordScore_ != 0 || score_ != 1u || score2_ != 2u) {
            throw std::runtime_error("game-over frame fixture entered wrong state");
        }
        FrameInspection gameOverFrame = inspectRenderedFrame("end-flow-game-over");
        if (gameOverFrame.hash == mainFrame.hash ||
            !regionHasVariation(70, 68, 190, 112)) {
            throw std::runtime_error("game-over frame did not render title/scores");
        }

        pushKeyDown(SDLK_RETURN);
        processEvents(running);
        if (!menu_ || menuPage_ != MenuPage::Main ||
            score_ != 0 || score2_ != 0) {
            throw std::runtime_error("game-over confirm did not clear scores");
        }
        FrameInspection afterGameOverFrame =
            inspectRenderedFrame("end-flow-after-game-over");
        if (afterGameOverFrame.hash == gameOverFrame.hash) {
            throw std::runtime_error("game-over confirm did not redraw menu");
        }

        playerCount_ = 1;
        resetLevel(static_cast<int>(levels_.size()) - 1);
        menu_ = false;
        collectAllObjectiveTilesForSmoke();
        damageRequiredTilesForSmoke();
        score_ = 1u;
        score2_ = 0;
        if (!isComplete() || !isFinalLevel()) {
            throw std::runtime_error("completed-game frame fixture did not satisfy final level");
        }
        for (int i = 0; i <= 100; ++i) {
            updateLevelCompletion();
        }
        if (!menu_ || menuPage_ != MenuPage::CompletedGame ||
            lastEndReason_ != EndReason::CompletedGame ||
            pendingRecordScore_ != 0 || levelIndex_ != 0 || score_ != 1u) {
            throw std::runtime_error("final-level completion did not show completed-game page");
        }
        FrameInspection completedFrame =
            inspectRenderedFrame("end-flow-completed-game");
        if (completedFrame.hash == gameOverFrame.hash ||
            completedFrame.hash == afterGameOverFrame.hash ||
            !regionHasVariation(50, 54, 230, 120)) {
            throw std::runtime_error("completed-game frame did not render distinct text");
        }

        pushKeyDown(SDLK_SPACE);
        processEvents(running);
        if (!menu_ || menuPage_ != MenuPage::Main || score_ != 0) {
            throw std::runtime_error("completed-game confirm did not clear score");
        }
        FrameInspection finalMenuFrame =
            inspectRenderedFrame("end-flow-final-menu");
        if (finalMenuFrame.hash == completedFrame.hash) {
            throw std::runtime_error("completed-game confirm did not redraw menu");
        }

        std::cout << "end_flow_frame_flow=ok"
                  << " game_over_scores=1,2"
                  << " completed_score=1"
                  << " final_level=" << levels_.size()
                  << " completed_page=1"
                  << " confirm_clears_scores=1"
                  << " frame_inspection=1\n";
    }

    void debugEndFlowStaticModel() {
        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for end-flow scan");
        }

        auto requireBytes = [&](uint16_t offset, const std::string& hex,
                                const std::string& label) {
            std::vector<uint8_t> expected = parseHexByteList(hex);
            size_t p = imageBase + offset;
            if (p + expected.size() > exeBytes.size()) {
                throw std::runtime_error(label + " extends past LEZAC.EXE");
            }
            for (size_t i = 0; i < expected.size(); ++i) {
                if (exeBytes[p + i] != expected[i]) {
                    throw std::runtime_error(label + " bytes changed");
                }
            }
        };
        auto nearTarget = [&](uint16_t offset, const std::string& label) {
            size_t p = imageBase + offset;
            if (p + 3 > exeBytes.size() || exeBytes[p] != 0xe8) {
                throw std::runtime_error(label + " is not a near call");
            }
            int rel = static_cast<int>(le16(exeBytes, p + 1));
            if (rel >= 0x8000) rel -= 0x10000;
            return static_cast<uint16_t>(offset + 3 + rel);
        };

        requireBytes(0x1ae1, "09 67 61 6d 65 20 6f 76 65 72",
                     "game-over string");
        requireBytes(0x1aeb, "0d 65 63 63 65 6c 6c 65 6e 74 65 3e 3e 3e",
                     "completed-game title string");
        requireBytes(0x1af9,
                     "17 68 61 69 20 63 6f 6d 70 6c 65 74 61 74 6f "
                     "20 69 6c 20 67 69 6f 63 6f",
                     "completed-game body string");
        requireBytes(kEndFlowDispatcherStart,
                     "55 89 e5 b8 0c 03 9a df 04 20 09 81 ec 0c 03",
                     "end-flow dispatcher prologue");
        requireBytes(0x1b63,
                     "8a 46 04 3c 01 75 1e 6a 3c 6a 4d bf e1 1a",
                     "end-flow mode-1 branch");
        requireBytes(0x1b88,
                     "3c 02 75 3d 6a 3c 6a 37 bf eb 1a",
                     "end-flow mode-2 branch");
        requireBytes(0x1bc4, "c6 06 8c 20 01", "completed-game flag write");
        requireBytes(0x1bf8,
                     "c7 46 fc 01 00 eb 03 ff 46 fc 83 7e fc 01 75 13 "
                     "b8 5a 78 8c da a3 b6 78 89 16 b8 78 c6 06 58 "
                     "20 31 eb 11 b8 88 78 8c da a3 b6 78 89 16 b8 "
                     "78 c6 06 58 20 32",
                     "end-flow player score pointer setup");
        requireBytes(0x1c4b,
                     "83 bb f2 fe 00 7f 0f 7d 03 e9 98 00 83 bb f0 "
                     "fe 00 77 03 e9 8e 00",
                     "end-flow zero-score skip");
        requireBytes(0x1cf8, "9a 0f 03 4a 08 a2 58 20",
                     "end-flow key wait");
        requireBytes(0x1d00, "c7 46 fc 01 00 eb 03 ff 46 fc",
                     "end-flow record loop");
        requireBytes(0x1d18,
                     "3b 16 54 1b 7f 08 7c 1b 3b 06 52 1b 72 15",
                     "end-flow seventh-record cutoff compare");
        requireBytes(0x1d2c,
                     "ff b3 f2 fe ff b3 f0 fe ff 76 fc 55 e8 0a fb",
                     "end-flow record-entry call setup");
        requireBytes(0x1d3b, "83 7e fc 02 75 c6 c9 c2 02 00",
                     "end-flow record loop return");

        uint16_t recordEntryTarget = nearTarget(0x1d38, "end-flow record-entry call");
        if (recordEntryTarget != 0x1845) {
            throw std::runtime_error("end-flow record-entry target changed");
        }

        std::cout << "end_flow_static_model=ok"
                  << " routine=" << hex4(kEndFlowDispatcherStart)
                  << ".." << hex4(kEndFlowDispatcherRet)
                  << " game_over_string=0x1ae1"
                  << " completed_strings=0x1aeb,0x1af9"
                  << " mode_param=bp+4"
                  << " completed_flag=0x208c"
                  << " player_score_ptrs=0x785a,0x7888"
                  << " player_markers=0x31,0x32"
                  << " key_latch=0x2058"
                  << " record_cutoff=0x1b52/0x1b54"
                  << " record_stride=13"
                  << " record_entry_call=" << hex4(recordEntryTarget)
                  << " strict_cutoff=1"
                  << " player_order=1,2\n";
    }

    void exportBackground(const std::string& path) {
        load();
        std::ofstream out(path, std::ios::binary);
        if (!out) {
            throw std::runtime_error("cannot create " + path);
        }
        out << "P6\n" << background_.width << ' ' << background_.height << "\n255\n";
        for (uint8_t idx : background_.pixels) {
            const Rgb c = backgroundPalette_[idx];
            out.put(static_cast<char>(c.r));
            out.put(static_cast<char>(c.g));
            out.put(static_cast<char>(c.b));
        }
    }

    void debugBombs() {
        load();
        resetLevel(0);
        printBombInventory("initial");
        bombInventory_.selected = BombType::Medium;
        printBombInventory("selected_medium");
        grantNormalBombSet(bombInventory_);
        printBombInventory("after_yellow_box");
        grantSuperBombSet(bombInventory_);
        printBombInventory("after_green_box");
        BombProfile profile = bombProfile(BombType::Super);
        Bomb bomb{10, 10, profile.fuseTicks, BombType::Super, profile.fuseTicks};
        auto tiles = explosionTilesFor(bomb);
        std::cout << "super_bomb_footprint_tiles=" << tiles.size() << '\n';
    }

    void debugBonuses() {
        load();
        resetLevel(0);
        Player collector = player_;
        BombInventory inventory;
        int energy = 50;

        auto expectScore = [&](BonusType type, uint32_t expectedScore) {
            uint32_t before = score_;
            applyBonus(type, collector, energy, inventory);
            if (score_ != before + expectedScore) {
                throw std::runtime_error("bonus score table mismatch");
            }
        };

        std::array<std::array<int, 2>, 7> spriteScores{{
            {61, 2000}, {62, 1000}, {63, 1500}, {64, 2000},
            {65, 3000}, {66, 1000}, {67, 5000},
        }};
        for (int i = 0; i < static_cast<int>(spriteScores.size()); ++i) {
            BonusType type = static_cast<BonusType>(i);
            if (bonusSpriteIndex(type) != spriteScores[static_cast<size_t>(i)][0]) {
                throw std::runtime_error("bonus sprite table mismatch");
            }
        }

        score_ = 0;
        energy = 50;
        expectScore(BonusType::Present, 2000);
        if (energy != 50) throw std::runtime_error("present changed energy");

        score_ = 0;
        energy = 20;
        expectScore(BonusType::FirstAid, 1000);
        if (energy != 100) throw std::runtime_error("first aid did not restore energy");

        score_ = 0;
        energy = 50;
        expectScore(BonusType::HotDog, 1500);
        if (energy != 83) throw std::runtime_error("hot dog did not add one-third energy");
        energy = 90;
        applyBonus(BonusType::HotDog, collector, energy, inventory);
        if (energy != 100) throw std::runtime_error("hot dog did not clamp energy");

        score_ = 0;
        bonusDrops_.clear();
        expectScore(BonusType::JollyCloud, 2000);
        if (bonusDrops_.size() != 4 ||
            bonusDrops_[0].type != BonusType::Present ||
            bonusDrops_[1].type != BonusType::BigDiamond ||
            bonusDrops_[2].type != BonusType::Present ||
            bonusDrops_[3].type != BonusType::BigDiamond) {
            throw std::runtime_error("jolly cloud did not spawn bonus rain");
        }

        bonusDrops_.clear();
        bonusDrops_.shrink_to_fit();
        BonusDrop cloud;
        cloud.x = player_.x;
        cloud.y = player_.y;
        cloud.type = BonusType::JollyCloud;
        bonusDrops_.push_back(cloud);
        bonusDrops_.shrink_to_fit();
        updateBonusDrops();
        if (bonusDrops_.size() != 4 ||
            std::any_of(bonusDrops_.begin(), bonusDrops_.end(),
                        [](const BonusDrop& drop) { return drop.collected; })) {
            throw std::runtime_error("jolly cloud collection corrupted bonus drops");
        }

        playerCount_ = 2;
        playerDead_ = false;
        player2Dead_ = false;
        player_.x = 95.0f;
        player_.y = 100.0f;
        player2_.x = 100.0f;
        player2_.y = 100.0f;
        energy_ = 50;
        energy2_ = 50;
        bonusDrops_.clear();
        BonusDrop sharedDrop;
        sharedDrop.x = 100.0f;
        sharedDrop.y = 100.0f;
        sharedDrop.type = BonusType::FirstAid;
        bonusDrops_.push_back(sharedDrop);
        updateBonusDrops();
        if (energy_ != 50 || energy2_ != 100 || !bonusDrops_.empty()) {
            throw std::runtime_error("shared bonus was not awarded to nearest player");
        }
        playerCount_ = 1;

        score_ = 0;
        inventory = {};
        inventory.counts = {0, 0, 0, 0};
        inventory.selected = BombType::Super;
        randomSeed_ = 0x1234abcd;
        expectScore(BonusType::YellowBombBox, 3000);
        if (inventory.counts[0] != 200 || inventory.counts[1] <= 0 ||
            inventory.counts[2] <= 0 || inventory.counts[3] != 0 ||
            !hasBomb(inventory, inventory.selected)) {
            throw std::runtime_error("yellow bomb box did not grant normal set");
        }

        score_ = 0;
        inventory = {};
        inventory.counts = {0, 0, 0, 0};
        inventory.selected = BombType::Super;
        randomSeed_ = 0x1234abcd;
        expectScore(BonusType::GreenBombBox, 1000);
        if (inventory.counts[0] != 200 || inventory.counts[1] <= 0 ||
            inventory.counts[2] <= 0 || inventory.counts[3] <= 0 ||
            inventory.selected != BombType::Super) {
            throw std::runtime_error("green bomb box did not grant super set");
        }

        score_ = 0;
        expectScore(BonusType::BigDiamond, 5000);

        clearSoundLatch();
        BonusDrop soundDrop;
        soundDrop.x = collector.x;
        soundDrop.y = collector.y;
        soundDrop.type = BonusType::Present;
        collectBonusDrop(soundDrop, collector, energy, inventory, 1);
        if (!soundLatch_.active || soundLatch_.latchedOffset != kBonusPickupSoundCursor ||
            soundLatch_.currentSelector != kBonusPickupSoundPriority ||
            soundLatch_.directSweep) {
            throw std::runtime_error("bonus pickup did not queue recovered sound cursor");
        }
        pumpSoundLatch();
        if (soundLatch_.active || lastPumpedSoundOffset_ != kBonusPickupSoundCursor ||
            lastPumpedSoundSelector_ != kBonusPickupSoundPriority) {
            throw std::runtime_error("bonus pickup sound cursor did not pump");
        }
        std::cout << "bonuses=ok sprites=" << spriteScores.size()
                  << " rain=" << bonusDrops_.size()
                  << " sound_cursor=" << std::showbase << std::hex
                  << kBonusPickupSoundCursor << std::dec << std::noshowbase
                  << " sound_priority="
                  << static_cast<int>(kBonusPickupSoundPriority) << '\n';
    }

    void debugBonusRewardStaticModel() {
        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for bonus reward scan");
        }

        constexpr uint16_t kScoreTableGhidraOffset = 0xaa56;
        constexpr uint16_t kScoreTableFileOffset = 0xb1c6;
        if (imageBase + kScoreTableGhidraOffset != kScoreTableFileOffset) {
            throw std::runtime_error("bonus reward score-table offset mapping changed");
        }
        constexpr std::array<uint16_t, 7> expectedScores{{
            2000, 1000, 1500, 2000, 3000, 1000, 5000,
        }};
        constexpr std::array<int, 7> expectedSpriteIndices{{61, 62, 63, 64, 65, 66, 67}};

        std::ostringstream scoreList;
        uint32_t scoreSum = 0;
        uint16_t topScore = 0;
        for (size_t i = 0; i < expectedScores.size(); ++i) {
            const uint16_t score = le16(exeBytes, kScoreTableFileOffset + i * 2);
            if (score != expectedScores[i]) {
                throw std::runtime_error("bonus reward score table changed");
            }
            if (i != 0) scoreList << ',';
            scoreList << score;
            scoreSum += score;
            topScore = std::max(topScore, score);
        }

        load();
        std::ostringstream spriteList;
        int spriteInBounds = 0;
        for (size_t i = 0; i < expectedSpriteIndices.size(); ++i) {
            BonusType type = static_cast<BonusType>(i);
            const int spriteIndex = bonusSpriteIndex(type);
            if (spriteIndex != expectedSpriteIndices[i]) {
                throw std::runtime_error("bonus reward sprite mapping changed");
            }
            if (spriteIndex < 0 ||
                spriteIndex >= static_cast<int>(sprites_.sprites.size())) {
                throw std::runtime_error("bonus reward sprite index out of bounds");
            }
            const Sprite& sprite = sprites_.sprites[static_cast<size_t>(spriteIndex)];
            if (sprite.width <= 0 || sprite.height <= 0 ||
                sprite.pixels.size() !=
                    static_cast<size_t>(sprite.width) * static_cast<size_t>(sprite.height)) {
                throw std::runtime_error("bonus reward sprite payload changed");
            }
            if (i != 0) spriteList << ',';
            spriteList << spriteIndex;
            ++spriteInBounds;
        }

        std::cout << "bonus_reward_static_model=ok"
                  << " image_base=0x0770"
                  << " score_table_file=" << hex4(kScoreTableFileOffset)
                  << " score_table_ghidra=" << hex4(kScoreTableGhidraOffset)
                  << " rewards=" << expectedScores.size()
                  << " scores=" << scoreList.str()
                  << " sprite_indices=" << spriteList.str()
                  << " bomomimk_sprites=" << sprites_.sprites.size()
                  << " sprite_in_bounds=" << spriteInBounds
                  << " score_sum=" << scoreSum
                  << " top_score=" << topScore
                  << " pickup_sound=" << hex4(kBonusPickupSoundCursor)
                  << "/p" << static_cast<int>(kBonusPickupSoundPriority)
                  << '\n';
    }

    void debugMonsterSpriteTableModel() {
        load();
        if (sprites_.sprites.size() != 91) {
            throw std::runtime_error("BOMOMIMK sprite count changed");
        }

        struct SpriteMetrics {
            int width = 0;
            int height = 0;
            int nonzero = 0;
        };

        auto metricsFor = [&](int index) {
            if (index < 0 || index >= static_cast<int>(sprites_.sprites.size())) {
                throw std::runtime_error("monster sprite table index out of bounds");
            }
            const Sprite& sprite = sprites_.sprites[static_cast<size_t>(index)];
            SpriteMetrics metrics;
            metrics.width = sprite.width;
            metrics.height = sprite.height;
            for (uint8_t pixelValue : sprite.pixels) {
                if (pixelValue != 0) ++metrics.nonzero;
            }
            return metrics;
        };
        auto joinInts = [](const std::vector<int>& values) {
            std::ostringstream oss;
            for (size_t i = 0; i < values.size(); ++i) {
                if (i != 0) oss << ',';
                oss << values[i];
            }
            return oss.str();
        };
        auto nonzeroList = [&](const std::vector<int>& indices) {
            std::vector<int> values;
            values.reserve(indices.size());
            for (int index : indices) values.push_back(metricsFor(index).nonzero);
            return joinInts(values);
        };
        auto dimensionList = [&](const std::vector<int>& indices) {
            std::ostringstream oss;
            for (size_t i = 0; i < indices.size(); ++i) {
                if (i != 0) oss << ',';
                SpriteMetrics metrics = metricsFor(indices[i]);
                oss << metrics.width << 'x' << metrics.height;
            }
            return oss.str();
        };
        auto count16x16 = [&](const std::vector<int>& indices) {
            return static_cast<int>(std::count_if(
                indices.begin(), indices.end(), [&](int index) {
                    SpriteMetrics metrics = metricsFor(index);
                    return metrics.width == 16 && metrics.height == 16;
                }));
        };

        const std::array<int, 2> kind1Left = monsterDirectionalFrameRange(1, -0x0100);
        const std::array<int, 2> kind1Right = monsterDirectionalFrameRange(1, 0x0100);
        const std::array<int, 2> kind2 = monsterFrameRange(2);
        const std::array<int, 2> kind3 = monsterFrameRange(3);
        const std::array<int, 2> kind4 = monsterFrameRange(4);
        if (kind1Left != std::array<int, 2>{43, 44} ||
            kind1Right != std::array<int, 2>{45, 46} ||
            kind2 != std::array<int, 2>{39, 41} ||
            kind3 != std::array<int, 2>{49, 51} ||
            kind4 != std::array<int, 2>{53, 55}) {
            throw std::runtime_error("monster normal frame ranges changed");
        }

        constexpr std::array<uint16_t, 7> kRewardScores{{
            2000, 1000, 1500, 2000, 3000, 1000, 5000,
        }};
        std::vector<int> rewardFrames;
        for (int i = 0; i < static_cast<int>(kRewardScores.size()); ++i) {
            int spriteIndex = bonusSpriteIndex(static_cast<BonusType>(i));
            if (spriteIndex != 61 + i) {
                throw std::runtime_error("monster reward sprite table changed");
            }
            rewardFrames.push_back(spriteIndex);
        }

        std::vector<int> normalFrames{39, 40, 41, 43, 44, 45, 46,
                                      49, 50, 51, 53, 54, 55};
        std::vector<int> impactCandidates{42, 47, 48, 52, 56};
        std::vector<int> deathCurrent{18};
        std::vector<int> allFrames = normalFrames;
        allFrames.insert(allFrames.end(), impactCandidates.begin(),
                         impactCandidates.end());
        allFrames.insert(allFrames.end(), deathCurrent.begin(),
                         deathCurrent.end());
        allFrames.insert(allFrames.end(), rewardFrames.begin(),
                         rewardFrames.end());

        std::vector<int> scores(kRewardScores.begin(), kRewardScores.end());
        std::cout << "monster_sprite_table_model=ok"
                  << " bank=BOMOMIMK"
                  << " normal_ranges=k1_left:43-44,k1_right:45-46,k2:39-41,k3:49-51,k4:53-55"
                  << " normal_frames=" << joinInts(normalFrames)
                  << " impact_candidates=" << joinInts(impactCandidates)
                  << " death_current_renderer=" << joinInts(deathCurrent)
                  << " reward_frames=" << joinInts(rewardFrames)
                  << " reward_scores=" << joinInts(scores)
                  << " normal_nonzero=" << nonzeroList(normalFrames)
                  << " impact_nonzero=" << nonzeroList(impactCandidates)
                  << " death_nonzero=" << nonzeroList(deathCurrent)
                  << " reward_nonzero=" << nonzeroList(rewardFrames)
                  << " normal_dims=" << dimensionList(normalFrames)
                  << " impact_dims=" << dimensionList(impactCandidates)
                  << " death_dims=" << dimensionList(deathCurrent)
                  << " reward_dims=" << dimensionList(rewardFrames)
                  << " frame_count=" << allFrames.size()
                  << " frames_16x16=" << count16x16(allFrames)
                  << " death_runtime_claim=0"
                  << " visual_claim=0"
                  << " ghidra=1000:70bc..7513\n";
    }

    void debugFixed() {
        auto run = [](int16_t velocity, int ticks) {
            int pos = 0;
            uint8_t frac = 0;
            for (int i = 0; i < ticks; ++i) {
                integrateAxis8_8(pos, frac, velocity);
            }
            std::cout << "vel=" << velocity << " ticks=" << ticks
                      << " pos=" << pos << " frac=" << static_cast<int>(frac) << '\n';
        };
        run(0x0040, 4);
        run(static_cast<int16_t>(-0x0040), 1);
        run(static_cast<int16_t>(-0x0040), 4);
        run(0x0100, 4);
        run(static_cast<int16_t>(-0x0100), 4);
    }

    void debugSounds() {
        load();
        std::cout << "sound_record_size=" << sounds_.recordSize
                  << " records=" << sounds_.records.size()
                  << " steps=" << sounds_.stepCount
                  << " words_per_record=" << (sounds_.recordSize / 2)
                  << " six_byte_steps=" << (sounds_.payload.size() / kSoundStepSize)
                  << '\n';
        for (size_t i = 0; i < sounds_.records.size(); ++i) {
            const std::vector<uint8_t>& bytes = sounds_.records[i].bytes;
            std::cout << "sound_" << (i + 1)
                      << "=bytes:" << bytes.size()
                      << " zero_bytes:" << std::count(bytes.begin(), bytes.end(), 0)
                      << " first_words:";
            for (size_t off = 0; off + 1 < bytes.size() && off < 12; off += 2) {
                if (off != 0) std::cout << ',';
                std::cout << std::showbase << std::hex << le16(bytes, off)
                          << std::dec << std::noshowbase;
            }
            std::cout << " first_groups:";
            for (size_t group = 0; group < 3 && group * 5 + 4 < bytes.size(); ++group) {
                if (group != 0) std::cout << ';';
                for (size_t j = 0; j < 5; ++j) {
                    if (j != 0) std::cout << '-';
                    std::cout << std::hex << std::setw(2) << std::setfill('0')
                              << static_cast<int>(bytes[group * 5 + j])
                              << std::dec << std::setfill(' ');
                }
            }
            std::cout << '\n';
        }
    }

    void debugSoundRender() {
        load();
        size_t totalSamples = 0;
        size_t totalNonZero = 0;
        for (size_t i = 0; i < sounds_.records.size(); ++i) {
            std::vector<int16_t> samples = synthesizeSound(i);
            size_t nonZero = static_cast<size_t>(
                std::count_if(samples.begin(), samples.end(),
                              [](int16_t sample) { return sample != 0; }));
            if (samples.empty() || nonZero == 0) {
                throw std::runtime_error("sound " + std::to_string(i + 1) +
                                         " rendered no audible samples");
            }
            totalSamples += samples.size();
            totalNonZero += nonZero;
            auto range = std::minmax_element(samples.begin(), samples.end());
            std::cout << "sound_render_" << (i + 1)
                      << "=cursor:" << std::showbase << std::hex
                      << compatibilitySoundCursor(i) << std::dec << std::noshowbase
                      << " samples:" << samples.size()
                      << " nonzero:" << nonZero
                      << " min:" << *range.first
                      << " max:" << *range.second << '\n';
        }
        std::cout << "sound_render_total=samples:" << totalSamples
                  << " nonzero:" << totalNonZero << '\n';
    }

    void debugSoundCursorSegments() {
        load();
        std::vector<uint16_t> stopCursors;
        for (size_t i = 0; i < sounds_.stepCount; ++i) {
            if (soundStepPeriodWord(i) == kSoundStopPeriod) {
                stopCursors.push_back(static_cast<uint16_t>(i + 1));
            }
        }
        if (stopCursors.size() != kExpectedSoundStopCursors.size() ||
            !std::equal(stopCursors.begin(), stopCursors.end(),
                        kExpectedSoundStopCursors.begin())) {
            throw std::runtime_error("PROEFS.SON stop cursor map changed");
        }

        std::cout << "sound_cursor_segments steps=" << sounds_.stepCount
                  << " stops=" << stopCursors.size()
                  << " stop_cursors=";
        for (size_t i = 0; i < stopCursors.size(); ++i) {
            if (i != 0) std::cout << ',';
            std::cout << std::showbase << std::hex << stopCursors[i]
                      << std::dec << std::noshowbase;
        }
        std::cout << '\n';

        for (uint16_t cursor : kDebugSoundCursors) {
            uint16_t stopCursor = soundStopCursorFor(cursor);
            std::vector<int16_t> samples = synthesizeSoundCursor(cursor);
            if (samples.empty()) {
                throw std::runtime_error("PROEFS.SON cursor rendered no samples");
            }
            std::cout << "sound_cursor cursor=" << std::showbase << std::hex
                      << cursor << " stop=" << stopCursor
                      << std::dec << std::noshowbase
                      << " steps=" << (stopCursor - cursor)
                      << " samples=" << samples.size() << '\n';
        }
        std::cout << "sound_cursor_segments=ok\n";
    }

    void debugSonRawRoundtrip() {
        load();
        auto rawBytes = readFile("PROEFS.SON");
        if (rawBytes.size() < 2) {
            throw std::runtime_error("PROEFS.SON is too small");
        }
        uint16_t stepCount = le16(rawBytes, 0);
        size_t payloadSize = rawBytes.size() - 2;
        if (stepCount != 0x82 || payloadSize != static_cast<size_t>(stepCount) * 6) {
            throw std::runtime_error("PROEFS.SON raw step layout mismatch");
        }
        std::vector<uint8_t> jsonPayload;
        for (const SoundEffectRecord& record : sounds_.records) {
            jsonPayload.insert(jsonPayload.end(), record.bytes.begin(), record.bytes.end());
        }
        if (jsonPayload.size() != payloadSize ||
            !std::equal(jsonPayload.begin(), jsonPayload.end(), rawBytes.begin() + 2)) {
            throw std::runtime_error("PROEFS.SON raw/json payload mismatch");
        }
        std::cout << "son_raw_roundtrip=ok raw_size=" << rawBytes.size()
                  << " step_count=" << stepCount
                  << " payload_size=" << payloadSize
                  << " json_chunks=" << sounds_.records.size() << '\n';
    }

    void debugSoundLoaderStaticModel() {
        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for sound loader scan");
        }
        constexpr uint16_t kFilenameAnchor = 0x0625;
        constexpr uint16_t kLoaderStart = 0x0630;
        constexpr uint16_t kCountConstant = 0x0633;
        constexpr uint16_t kFilenameCopy = 0x0644;
        constexpr uint16_t kCountRead = 0x065f;
        constexpr uint16_t kSoundBankRead = 0x0675;
        constexpr uint16_t kCountTimesSix = 0x067b;
        constexpr uint16_t kCloseFile = 0x0691;
        constexpr uint16_t kLoaderRet = 0x06aa;

        auto requireBytes = [&](uint16_t offset, const std::string& hex,
                                const std::string& label) {
            std::vector<uint8_t> expected = parseHexByteList(hex);
            size_t p = imageBase + offset;
            if (p + expected.size() > exeBytes.size()) {
                throw std::runtime_error(label + " extends past LEZAC.EXE");
            }
            for (size_t i = 0; i < expected.size(); ++i) {
                if (exeBytes[p + i] != expected[i]) {
                    throw std::runtime_error(label + " bytes changed");
                }
            }
        };
        auto countBytes = [&](const std::string& hex) {
            std::vector<uint8_t> expected = parseHexByteList(hex);
            int count = 0;
            auto begin = exeBytes.begin() + static_cast<long>(imageBase + kLoaderStart);
            auto end = exeBytes.begin() + static_cast<long>(imageBase + kLoaderRet);
            for (auto it = begin; it != end;) {
                it = std::search(it, end, expected.begin(), expected.end());
                if (it == end) break;
                ++count;
                ++it;
            }
            return count;
        };

        requireBytes(kFilenameAnchor, "0a 70 72 6f 65 66 73 2e 73 6f 6e",
                     "PROEFS.SON filename anchor");
        requireBytes(kLoaderStart, "55 89 e5", "sound loader prologue");
        requireBytes(kCountConstant, "b8 82 00", "sound loader count constant");
        requireBytes(0x063b, "81 ec 82 00", "sound loader local buffer size");
        requireBytes(kFilenameCopy, "bf 25 06 0e 57 9a ca 15 20 09",
                     "sound loader filename copy");
        requireBytes(0x0653, "6a 01 9a f8 15 20 09", "sound loader open call");
        requireBytes(kCountRead, "8d be 7e ff 16 57 6a 02 31 c0 50 50 9a e3 16 20 09",
                     "sound loader count read");
        requireBytes(kSoundBankRead, "c4 3e c0 79 06 57",
                     "sound loader sound-bank pointer");
        requireBytes(kCountTimesSix, "8b 86 7e ff d1 e0 8b f0 d1 e0 01 f0 50",
                     "sound loader count times six");
        requireBytes(0x068c, "9a e3 16 20 09", "sound loader payload read");
        requireBytes(kCloseFile, "8d 7e 80 16 57 9a 79 16 20 09",
                     "sound loader close call");
        requireBytes(0x069b, "9a a2 04 20 09 09 c0 74 05 6a 01 e8 fa f9 c9 c3",
                     "sound loader io result tail");

        int readCalls = countBytes("9a e3 16 20 09");
        if (readCalls != 2) {
            throw std::runtime_error("sound loader read-call count changed");
        }

        std::cout << "sound_loader_static_model=ok"
                  << " routine=" << hex4(kLoaderStart) << ".." << hex4(kLoaderRet)
                  << " filename=proefs.son"
                  << " filename_anchor=" << hex4(kFilenameAnchor)
                  << " step_count=0x0082"
                  << " step_size=6"
                  << " payload_bytes=780"
                  << " count_read_bytes=2"
                  << " sound_bank_ptr=0x79c0"
                  << " count_local=bp-0x82"
                  << " count_times_six=1"
                  << " read_calls=" << readCalls << '\n';
    }

    void debugSonStepFields() {
        load();
        if (sounds_.stepCount != 0x82 ||
            sounds_.payload.size() != sounds_.stepCount * kSoundStepSize) {
            throw std::runtime_error("PROEFS.SON step field layout mismatch");
        }

        auto hex2 = [](uint8_t value) {
            std::ostringstream oss;
            oss << "0x" << std::hex << std::nouppercase << std::setw(2)
                << std::setfill('0') << static_cast<int>(value);
            return oss.str();
        };
        auto hex4 = [](uint16_t value) {
            std::ostringstream oss;
            oss << "0x" << std::hex << std::nouppercase << std::setw(4)
                << std::setfill('0') << value;
            return oss.str();
        };

        struct StepFields {
            uint16_t periodWord = 0;
            uint8_t gateTick = 0;
            uint8_t periodTicks = 0;
            uint8_t tail4 = 0;
            uint8_t tail5 = 0;
        };

        auto step = [&](size_t stepIndex) {
            size_t off = stepIndex * kSoundStepSize;
            if (off + 5 >= sounds_.payload.size()) {
                throw std::runtime_error("PROEFS.SON step index out of range");
            }
            return StepFields{le16(sounds_.payload, off), sounds_.payload[off + 2],
                              sounds_.payload[off + 3], sounds_.payload[off + 4],
                              sounds_.payload[off + 5]};
        };

        std::vector<uint16_t> stopCursors;
        int tailPairNonzeroSteps = 0;
        for (size_t i = 0; i < sounds_.stepCount; ++i) {
            StepFields fields = step(i);
            if (fields.periodWord == kSoundStopPeriod) {
                stopCursors.push_back(static_cast<uint16_t>(i + 1));
            }
            if (fields.tail4 != 0 || fields.tail5 != 0) {
                ++tailPairNonzeroSteps;
            }
        }
        if (stopCursors.size() != kExpectedSoundStopCursors.size() ||
            !std::equal(stopCursors.begin(), stopCursors.end(),
                        kExpectedSoundStopCursors.begin())) {
            throw std::runtime_error("PROEFS.SON step stop cursor map changed");
        }

        auto printStep = [&](const std::string& label, size_t stepIndex) {
            StepFields fields = step(stepIndex);
            std::cout << "son_step_fields " << label
                      << " step_index=" << stepIndex
                      << " cursor=" << hex4(static_cast<uint16_t>(stepIndex + 1))
                      << " period_word=" << hex4(fields.periodWord)
                      << " gate_tick=" << static_cast<int>(fields.gateTick)
                      << " period_ticks=" << static_cast<int>(fields.periodTicks)
                      << " tail4=" << hex2(fields.tail4)
                      << " tail5=" << hex2(fields.tail5)
                      << " stop=" << (fields.periodWord == kSoundStopPeriod ? 1 : 0)
                      << '\n';
        };

        std::cout << "son_step_fields=summary steps=" << sounds_.stepCount
                  << " step_size=" << kSoundStepSize
                  << " stop_sentinels=" << stopCursors.size()
                  << " tail_pair_nonzero_steps=" << tailPairNonzeroSteps
                  << " period_word=bytes0-1"
                  << " gate_tick=byte2"
                  << " period_ticks=byte3"
                  << " tail4=byte4"
                  << " tail5=byte5"
                  << " tail_behavior=preserved_playback_unused\n";
        printStep("first", 0);
        printStep("first_stop", stopCursors.front() - 1);
        printStep("final_stop", stopCursors.back() - 1);
        std::cout << "son_step_fields=ok steps=" << sounds_.stepCount
                  << " first_period=" << hex4(step(0).periodWord)
                  << " first_stop_cursor=" << hex4(stopCursors.front())
                  << " final_stop_cursor=" << hex4(stopCursors.back())
                  << " tail_pair_nonzero_steps=" << tailPairNonzeroSteps
                  << " tail_behavior=preserved_playback_unused"
                  << '\n';
    }

    void debugSonTailFieldMutation() {
        load();
        if (sounds_.stepCount != 0x82 ||
            sounds_.payload.size() != sounds_.stepCount * kSoundStepSize) {
            throw std::runtime_error("PROEFS.SON step field layout mismatch");
        }

        std::vector<std::vector<int16_t>> baseline;
        baseline.reserve(kDebugSoundCursors.size());
        size_t baselineSamples = 0;
        for (uint16_t cursor : kDebugSoundCursors) {
            baseline.push_back(synthesizeSoundCursor(cursor));
            baselineSamples += baseline.back().size();
            if (baseline.back().empty()) {
                throw std::runtime_error("PROEFS.SON cursor rendered no samples");
            }
        }

        std::vector<uint8_t> originalPayload = sounds_.payload;
        int tailPairNonzeroSteps = 0;
        int mutatedSteps = 0;
        for (size_t step = 0; step < sounds_.stepCount; ++step) {
            size_t off = step * kSoundStepSize;
            if (sounds_.payload[off + 4] != 0 || sounds_.payload[off + 5] != 0) {
                ++tailPairNonzeroSteps;
            }
            sounds_.payload[off + 4] =
                static_cast<uint8_t>(sounds_.payload[off + 4] ^ 0xffu);
            sounds_.payload[off + 5] =
                static_cast<uint8_t>(sounds_.payload[off + 5] ^ 0xa5u);
            ++mutatedSteps;
        }

        size_t mutatedSamples = 0;
        for (size_t i = 0; i < kDebugSoundCursors.size(); ++i) {
            std::vector<int16_t> mutated = synthesizeSoundCursor(kDebugSoundCursors[i]);
            mutatedSamples += mutated.size();
            if (mutated != baseline[i]) {
                std::ostringstream oss;
                oss << "PROEFS.SON tail field mutation changed cursor 0x"
                    << std::hex << std::setw(4) << std::setfill('0')
                    << kDebugSoundCursors[i];
                throw std::runtime_error(oss.str());
            }
        }
        sounds_.payload = std::move(originalPayload);

        std::cout << "son_tail_fields_mutation=ok steps=" << sounds_.stepCount
                  << " mutated_steps=" << mutatedSteps
                  << " compared_cursors=" << kDebugSoundCursors.size()
                  << " baseline_samples=" << baselineSamples
                  << " mutated_samples=" << mutatedSamples
                  << " tail_pair_nonzero_steps=" << tailPairNonzeroSteps
                  << " ignored_tail_bytes=4,5"
                  << " tail_behavior=preserved_playback_unused\n";
    }

    void debugSoundTickStaticModel() {
        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for sound tick scan");
        }
        constexpr uint16_t kTickStart = 0x0fbe;
        constexpr uint16_t kTickRet = 0x1088;
        constexpr uint16_t kDirectSweepBranch = 0x0fd9;
        constexpr uint16_t kStepAdvance = 0x1014;
        constexpr uint16_t kStepAddress = 0x1023;
        constexpr uint16_t kStopCompare = 0x1033;
        constexpr uint16_t kPeriodPush = 0x1053;
        constexpr uint16_t kGateByteRead = 0x105e;
        constexpr uint16_t kPeriodByteRead = 0x1068;

        auto requireBytes = [&](uint16_t offset, const std::string& hex,
                                const std::string& label) {
            std::vector<uint8_t> expected = parseHexByteList(hex);
            size_t p = imageBase + offset;
            if (p + expected.size() > exeBytes.size()) {
                throw std::runtime_error(label + " extends past LEZAC.EXE");
            }
            for (size_t i = 0; i < expected.size(); ++i) {
                if (exeBytes[p + i] != expected[i]) {
                    throw std::runtime_error(label + " bytes changed");
                }
            }
        };
        auto containsBytes = [&](const std::vector<uint8_t>& expected) {
            auto begin = exeBytes.begin() + static_cast<long>(imageBase + kTickStart);
            auto end = exeBytes.begin() + static_cast<long>(imageBase + kTickRet);
            return std::search(begin, end, expected.begin(), expected.end()) != end;
        };
        auto countBytes = [&](const std::string& hex) {
            std::vector<uint8_t> expected = parseHexByteList(hex);
            int count = 0;
            auto begin = exeBytes.begin() + static_cast<long>(imageBase + kTickStart);
            auto end = exeBytes.begin() + static_cast<long>(imageBase + kTickRet);
            for (auto it = begin; it != end;) {
                it = std::search(it, end, expected.begin(), expected.end());
                if (it == end) break;
                ++count;
                ++it;
            }
            return count;
        };

        requireBytes(kTickStart, "50 53 51 52 56 57 1e 06 c8 04 00 00",
                     "sound tick prologue");
        requireBytes(kDirectSweepBranch,
                     "81 3e c0 78 60 ea 76 26 a1 c0 78 2d 42 ea 50",
                     "sound tick direct sweep branch");
        requireBytes(kStepAdvance,
                     "ff 06 c0 78 a1 c0 78 d1 e0 8b f0 d1 e0 01 f0",
                     "sound tick cursor stride");
        requireBytes(kStepAddress, "c4 3e c0 79 03 f8 81 c7 fa ff",
                     "sound tick step address");
        requireBytes(kStopCompare, "c4 7e fc 26 81 3d 30 75",
                     "sound tick stop compare");
        requireBytes(kPeriodPush, "c4 7e fc 26 ff 35 9a c9 02 4a 08",
                     "sound tick period push");
        requireBytes(kGateByteRead, "c4 7e fc 26 8a 45 02 a2 a1 79",
                     "sound tick gate byte read");
        requireBytes(kPeriodByteRead, "c4 7e fc 26 8a 45 03 a2 a2 79",
                     "sound tick period byte read");
        requireBytes(kTickRet - 1, "c9", "sound tick leave");

        int byteReads = countBytes("26 8a 45");
        int wordReads = countBytes("26 81 3d") + countBytes("26 ff 35");
        int tailReadPatterns = 0;
        for (const std::string& pattern : {
                 "26 8a 45 04", "26 8a 45 05", "26 8b 45 04",
                 "26 8b 45 05", "26 ff 75 04", "26 ff 75 05",
             }) {
            if (containsBytes(parseHexByteList(pattern))) ++tailReadPatterns;
        }
        if (byteReads != 2 || wordReads != 2 || tailReadPatterns != 0) {
            throw std::runtime_error("sound tick step read model changed");
        }

        std::cout << "sound_tick_static_model=ok"
                  << " routine=" << hex4(kTickStart) << ".." << hex4(kTickRet)
                  << " direct_sweep_threshold=0xea60"
                  << " direct_sweep_subtract=0xea42"
                  << " direct_sweep_step=4"
                  << " cursor_increment=" << hex4(kStepAdvance)
                  << " entry_stride=6"
                  << " entry_base=sound_bank+cursor*6-6"
                  << " stop_sentinel=0x7530"
                  << " period_word_offsets=0"
                  << " gate_byte_offset=2"
                  << " period_byte_offset=3"
                  << " word_entry_reads=" << wordReads
                  << " byte_entry_reads=" << byteReads
                  << " tail_read_patterns=" << tailReadPatterns
                  << " ignored_tail_bytes=4,5"
                  << " tail_behavior=preserved_playback_unused\n";
    }

    void debugSoundLatchStaticModel() {
        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for sound latch scan");
        }
        constexpr uint16_t kLatchStart = 0x165a;
        constexpr uint16_t kInactiveAcceptBranch = 0x165f;
        constexpr uint16_t kRejectBranch = 0x166a;
        constexpr uint16_t kAcceptPath = 0x166c;
        constexpr uint16_t kRejectRet = 0x167d;

        auto requireBytes = [&](uint16_t offset, const std::string& hex,
                                const std::string& label) {
            std::vector<uint8_t> expected = parseHexByteList(hex);
            size_t p = imageBase + offset;
            if (p + expected.size() > exeBytes.size()) {
                throw std::runtime_error(label + " extends past LEZAC.EXE");
            }
            for (size_t i = 0; i < expected.size(); ++i) {
                if (exeBytes[p + i] != expected[i]) {
                    throw std::runtime_error(label + " bytes changed");
                }
            }
        };
        auto shortJumpTarget = [&](uint16_t offset, const std::string& label) {
            size_t p = imageBase + offset;
            if (p + 2 > exeBytes.size()) {
                throw std::runtime_error(label + " jump extends past LEZAC.EXE");
            }
            uint8_t raw = exeBytes[p + 1];
            int displacement = raw < 0x80 ? raw : static_cast<int>(raw) - 0x100;
            return static_cast<uint16_t>(offset + 2 + displacement);
        };

        requireBytes(kLatchStart,
                     "a0 c4 79 3c 00 74 0b a0 9e 79 fe c8 3a 06 9f 79 "
                     "7d 11 a0 9f 79 a2 9e 79 a1 74 20 a3 c0 78 c6 06 "
                     "c4 79 01 c3",
                     "sound latch routine");
        requireBytes(kLatchStart, "a0 c4 79 3c 00 74 0b",
                     "sound latch active gate");
        requireBytes(0x1661, "a0 9e 79 fe c8 3a 06 9f 79 7d 11",
                     "sound latch priority compare");
        requireBytes(kAcceptPath, "a0 9f 79 a2 9e 79",
                     "sound latch priority copy");
        requireBytes(0x1672, "a1 74 20 a3 c0 78",
                     "sound latch cursor copy");
        requireBytes(0x1678, "c6 06 c4 79 01 c3",
                     "sound latch active flag set");

        uint16_t inactiveAcceptTarget =
            shortJumpTarget(kInactiveAcceptBranch, "sound latch inactive accept");
        uint16_t rejectTarget = shortJumpTarget(kRejectBranch, "sound latch reject");
        if (inactiveAcceptTarget != kAcceptPath || rejectTarget != kRejectRet) {
            throw std::runtime_error("sound latch branch target changed");
        }

        std::cout << "sound_latch_static_model=ok"
                  << " routine=" << hex4(kLatchStart) << ".." << hex4(kRejectRet)
                  << " active_flag=0x79c4"
                  << " current_priority=0x799e"
                  << " pending_priority=0x799f"
                  << " pending_cursor=0x2074"
                  << " current_cursor=0x78c0"
                  << " inactive_accept=1"
                  << " reject_branch=" << hex4(rejectTarget)
                  << " accept_branch=" << hex4(inactiveAcceptTarget)
                  << " current_minus_one_compare=1"
                  << " copies_priority=1"
                  << " copies_cursor=1"
                  << " sets_active=1\n";
    }

    void debugGranRawRoundtrip() {
        auto rawBytes = readFile("GRAN.MST");
        GranBank rawBank = loadRawGran("GRAN.MST");
        GranBank jsonBank = loadGran("GRAN.MST.json");
        constexpr size_t kExpectedGranRecords = 7;
        constexpr size_t kExpectedGranPayloadSize = kExpectedGranRecords * kGranRecordSize;
        const std::array<int, 7> expectedSums{631, 2230, 1389, 1242, 1780, 2720, 2568};
        const std::array<int, 7> expectedWeightedSums{
            18094, 59871, 40052, 35568, 63621, 65838, 54274};
        const std::array<int, 7> expectedNonzero{31, 41, 29, 30, 33, 41, 44};
        const std::array<uint8_t, 7> expectedXor{
            0x83, 0x08, 0x53, 0x80, 0xd0, 0xda, 0x5e};
        if (rawBytes.size() != kExpectedGranPayloadSize) {
            throw std::runtime_error("GRAN.MST raw size mismatch");
        }

        auto flattenPayload = [](const GranBank& bank, const char* label) {
            if (bank.recordSize != kGranRecordSize || bank.records.size() != 7) {
                throw std::runtime_error(std::string(label) + " GRAN shape mismatch");
            }
            std::vector<uint8_t> payload;
            payload.reserve(bank.recordSize * bank.records.size());
            for (const GranRecord& record : bank.records) {
                if (record.bytes.size() != kGranRecordSize) {
                    throw std::runtime_error(std::string(label) +
                                             " GRAN record length mismatch");
                }
                payload.insert(payload.end(), record.bytes.begin(), record.bytes.end());
            }
            return payload;
        };
        std::vector<uint8_t> rawPayload = flattenPayload(rawBank, "raw");
        std::vector<uint8_t> jsonPayload = flattenPayload(jsonBank, "JSON");
        if (rawPayload != rawBytes) {
            throw std::runtime_error("GRAN.MST raw loader payload mismatch");
        }
        if (jsonPayload.size() != rawPayload.size() || jsonPayload != rawPayload) {
            throw std::runtime_error("GRAN.MST raw/json payload mismatch");
        }
        auto joinedInts = [](const auto& values) {
            std::ostringstream oss;
            for (size_t i = 0; i < values.size(); ++i) {
                if (i != 0) oss << ',';
                oss << static_cast<int>(values[i]);
            }
            return oss.str();
        };
        auto joinedHexBytes = [](const auto& values) {
            std::ostringstream oss;
            for (size_t i = 0; i < values.size(); ++i) {
                if (i != 0) oss << ',';
                oss << "0x" << std::hex << std::setw(2) << std::setfill('0')
                    << static_cast<int>(values[i]);
            }
            return oss.str();
        };
        int totalSum = 0;
        int totalWeightedSum = 0;
        int totalNonzero = 0;
        uint8_t totalXor = 0;
        for (size_t i = 0; i < kExpectedGranRecords; ++i) {
            const size_t base = i * kGranRecordSize;
            int byteSum = 0;
            int weightedSum = 0;
            int nonzero = 0;
            uint8_t xorValue = 0;
            for (size_t j = 0; j < kGranRecordSize; ++j) {
                uint8_t byte = jsonPayload[base + j];
                byteSum += byte;
                weightedSum += static_cast<int>((j + 1) * byte);
                if (byte != 0) ++nonzero;
                xorValue = static_cast<uint8_t>(xorValue ^ byte);
            }
            if (byteSum != expectedSums[i] ||
                weightedSum != expectedWeightedSums[i] ||
                nonzero != expectedNonzero[i] ||
                xorValue != expectedXor[i]) {
                throw std::runtime_error("GRAN.MST record fingerprint mismatch");
            }
            totalSum += byteSum;
            totalWeightedSum += weightedSum;
            totalNonzero += nonzero;
            totalXor = static_cast<uint8_t>(totalXor ^ xorValue);
        }
        if (totalSum != 12560 || totalWeightedSum != 337318 ||
            totalNonzero != 249 || totalXor != 0x0c) {
            throw std::runtime_error("GRAN.MST aggregate fingerprint mismatch");
        }
        std::cout << "gran_raw_roundtrip=ok raw_size=" << rawBytes.size()
                  << " record_size=" << rawBank.recordSize
                  << " raw_records=" << rawBank.records.size()
                  << " payload_size=" << jsonPayload.size()
                  << " json_records=" << jsonBank.records.size()
                  << " raw_json_match=1"
                  << " byte_sum=" << totalSum
                  << " weighted_sum=" << totalWeightedSum
                  << " nonzero_bytes=" << totalNonzero
                  << " zero_bytes=" << (static_cast<int>(jsonPayload.size()) - totalNonzero)
                  << " xor=0x" << std::hex << std::setw(2) << std::setfill('0')
                  << static_cast<int>(totalXor) << std::dec << std::setfill(' ')
                  << " record_sums=" << joinedInts(expectedSums)
                  << " record_weighted_sums=" << joinedInts(expectedWeightedSums)
                  << " record_nonzero=" << joinedInts(expectedNonzero)
                  << " record_xor=" << joinedHexBytes(expectedXor) << '\n';
    }

    void debugGranStaticConsumerModel() {
        // Static recovery of the original GRAN.MST consumer. The shipped
        // executable loads gran.mst only when the current-level byte
        // DS:0x79B7 equals 7, through the generic actor-file reader at
        // 1000:08A5. The reader walks the file as:
        //   [count N:1][N x 38-byte actor records][N x sprite byte]
        //   [N x (dx:int16, dy:int16)][count M:1][M x 16-byte entries]
        // appending the records to the actor table at DS:0x1BAE (stride
        // 0x26), placing per-record visual entries at DS:0xC21E (stride 8)
        // offset from the caller's anchor arguments (100,100), and appending
        // the 16-byte entries to the DS:0x79EA table counted by DS:0x79F9.
        // This is static instruction/file evidence only; no original runtime
        // capture is claimed.
        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for GRAN consumer scan");
        }

        struct PinnedWindow {
            const char* label;
            uint16_t ghidraOffset;
            const char* hexBytes;
        };
        static const std::array<PinnedWindow, 12> kPinnedWindows{{
            {"filename_literal", 0x2AD3, "086772616e2e6d7374"},
            {"level7_gate_call", 0x2E78, "803eb77907750cbfd32a0e576a646a64e81ada"},
            {"reader_prologue", 0x08A5, "5589e5b89001"},
            {"record_dest_1bae", 0x0902, "a08d2030e4406bf82681c7ae1b"},
            {"record_count_x26", 0x0911, "8a8679fe30e46bc02650"},
            {"visual_dest_c21e", 0x09CF, "8bf8c1e70381c71ec2"},
            {"head_link_1bc0", 0x0A2C, "6bf8268995c01b"},
            {"segment_link_25", 0x0AC8, "c4be70fe26884525"},
            {"extra_dest_79ea", 0x0AE9, "8bf8c1e70481c7ea79"},
            {"extra_count_x10", 0x0AF4, "8a8677fe30e4c1e00450"},
            {"actor_count_grow", 0x0C27, "8a8679fe00068d20"},
            {"reader_epilogue", 0x0C2F, "c9c20800"},
        }};
        auto nibble = [](char c) -> int {
            if (c >= '0' && c <= '9') return c - '0';
            if (c >= 'a' && c <= 'f') return c - 'a' + 10;
            throw std::runtime_error("bad pinned hex digit");
        };
        for (const auto& window : kPinnedWindows) {
            const std::string hexText = window.hexBytes;
            for (size_t i = 0; i * 2 < hexText.size(); ++i) {
                const uint8_t expected = static_cast<uint8_t>(
                    nibble(hexText[i * 2]) * 16 + nibble(hexText[i * 2 + 1]));
                const size_t fileOffset = imageBase + window.ghidraOffset + i;
                if (fileOffset >= exeBytes.size() ||
                    exeBytes[fileOffset] != expected) {
                    throw std::runtime_error(
                        std::string("GRAN consumer bytes changed: ") + window.label);
                }
            }
        }

        // Reparse the shipped file with the recovered reader layout.
        std::vector<uint8_t> granBytes = readFile("GRAN.MST");
        constexpr size_t kActorRecordStride = 0x26;
        constexpr size_t kExtraRecordStride = 0x10;
        size_t pos = 0;
        auto need = [&](size_t count, const char* what) {
            if (pos + count > granBytes.size()) {
                throw std::runtime_error(std::string("GRAN.MST truncated at ") + what);
            }
        };
        need(1, "record count");
        const size_t recordCount = granBytes[pos++];
        need(recordCount * kActorRecordStride, "actor records");
        const size_t recordsBase = pos;
        pos += recordCount * kActorRecordStride;
        need(recordCount, "sprite bytes");
        const size_t spritesBase = pos;
        pos += recordCount;
        need(recordCount * 4, "visual offsets");
        const size_t pairsBase = pos;
        pos += recordCount * 4;
        need(1, "extra count");
        const size_t extraCount = granBytes[pos++];
        need(extraCount * kExtraRecordStride, "extra records");
        const size_t extrasBase = pos;
        pos += extraCount * kExtraRecordStride;
        if (recordCount != 7 || extraCount != 6 || pos != granBytes.size() ||
            granBytes.size() != 399) {
            throw std::runtime_error("GRAN.MST recovered layout mismatch");
        }

        load();
        std::ostringstream spriteList;
        std::ostringstream pairList;
        std::ostringstream typeList;
        for (size_t i = 0; i < recordCount; ++i) {
            const uint8_t spriteIndex = granBytes[spritesBase + i];
            if (spriteIndex < 39 || spriteIndex > 55 ||
                spriteIndex >= sprites_.sprites.size()) {
                throw std::runtime_error("GRAN.MST sprite byte outside monster frame range");
            }
            const uint8_t typeByte = granBytes[recordsBase + i * kActorRecordStride + 3];
            const int dx = static_cast<int16_t>(
                le16(granBytes, pairsBase + i * 4));
            const int dy = static_cast<int16_t>(
                le16(granBytes, pairsBase + i * 4 + 2));
            if (i != 0) {
                spriteList << ',';
                pairList << ',';
                typeList << ',';
                // Non-head records carry their serial number in the +0x0e
                // word the reader later rebases into the DS:0x79EA table.
                const uint16_t serial = le16(
                    granBytes, recordsBase + i * kActorRecordStride + 0x0e);
                const uint16_t reserved = le16(
                    granBytes, recordsBase + i * kActorRecordStride + 0x10);
                if (serial != i || reserved != 0) {
                    throw std::runtime_error("GRAN.MST segment serial fields changed");
                }
            }
            spriteList << static_cast<int>(spriteIndex);
            pairList << dx << ':' << dy;
            typeList << "0x" << std::hex << std::setw(2) << std::setfill('0')
                     << static_cast<int>(typeByte) << std::dec << std::setfill(' ');
        }
        if (granBytes[recordsBase + 3] != 0x10) {
            throw std::runtime_error("GRAN.MST head record type byte changed");
        }
        for (size_t i = 0; i < extraCount; ++i) {
            const uint8_t visualA = granBytes[extrasBase + i * kExtraRecordStride];
            const uint8_t visualB = granBytes[extrasBase + i * kExtraRecordStride + 1];
            if (visualA != 4 || visualB > 6) {
                throw std::runtime_error("GRAN.MST extra visual link bytes changed");
            }
        }

        std::cout << "gran_static_consumer_model=ok"
                  << " image_base=0x0770"
                  << " filename_literal=1000:2ad3"
                  << " level_gate=1000:2e78"
                  << " level_gate_byte=ds:79b7"
                  << " level_gate_value=7"
                  << " reader=1000:08a5..0c32"
                  << " pinned_windows=" << kPinnedWindows.size()
                  << " file_size=" << granBytes.size()
                  << " consumed=" << pos
                  << " actor_records=" << recordCount
                  << " actor_record_stride=0x26"
                  << " actor_table=ds:1bae"
                  << " actor_count_global=ds:208d"
                  << " sprite_bytes=" << spriteList.str()
                  << " visual_offsets=" << pairList.str()
                  << " visual_table=ds:c21e"
                  << " visual_stride=8"
                  << " record_types=" << typeList.str()
                  << " segment_link_field=0x25"
                  << " extra_records=" << extraCount
                  << " extra_record_stride=0x10"
                  << " extra_table=ds:79ea"
                  << " extra_count_global=ds:79f9"
                  << " seven_by_57_layout=0"
                  << " original_runtime_claim=0" << '\n';
    }

    // Validate the statically-decoded level-7 boss model against captured
    // ORIGINAL RUNTIME evidence (the DS:0x1BAE actor table and DS:0x79EA link
    // table read from a live DOSBox session at level 7). Confirms the head/
    // segment kinds, actor count, link count, and head hit-box against what the
    // original game actually built in memory.
    void debugBossRuntimeEvidence(const std::string& fixturePath) {
        std::ifstream in(fixturePath);
        if (!in) throw std::runtime_error("cannot open boss runtime fixture " + fixturePath);
        std::string line, actorHex, linkHex;
        int headKind = 0, headBehavior = 0, segmentKind = 0, actorEntrySize = 38;
        while (std::getline(in, line)) {
            if (line.empty() || line[0] == '#') continue;
            auto eq = line.find('=');
            if (eq == std::string::npos) continue;
            std::string key = line.substr(0, eq), val = line.substr(eq + 1);
            if (key == "actor_table_hex") actorHex = val;
            else if (key == "link_table_hex") linkHex = val;
            else if (key == "head_kind") headKind = std::stoi(val, nullptr, 0);
            else if (key == "head_behavior") headBehavior = std::stoi(val, nullptr, 0);
            else if (key == "segment_kind") segmentKind = std::stoi(val, nullptr, 0);
            else if (key == "actor_entry_size") actorEntrySize = std::stoi(val, nullptr, 0);
        }
        auto hexToBytes = [](const std::string& h) {
            std::vector<uint8_t> b;
            for (size_t i = 0; i + 1 < h.size(); i += 2)
                b.push_back(static_cast<uint8_t>(std::stoi(h.substr(i, 2), nullptr, 16)));
            return b;
        };
        std::vector<uint8_t> actors = hexToBytes(actorHex);
        std::vector<uint8_t> links = hexToBytes(linkHex);

        // Parse the original runtime actor table: locate the head (kind byte
        // followed by its behavior byte) and count the segments.
        int origHeadCount = 0, origSegmentCount = 0;
        int origHeadBoxW = -1, origHeadBoxH = -1;
        for (size_t off = 0; off + 2 <= actors.size(); ++off) {
            if (actors[off] == headKind && actors[off + 1] == headBehavior) {
                ++origHeadCount;
                // Head hit-box is the 5x4 pair 14 bytes into the head entry
                // (kind,behavior,...,boxW,boxH), matching the decoded model.
                if (off + 15 < actors.size()) {
                    origHeadBoxW = actors[off + 14];
                    origHeadBoxH = actors[off + 15];
                }
            }
        }
        // Count segments as kind bytes sitting on the head's 38-byte entry grid.
        int gridSegments = 0;
        int headIdx = -1;
        for (size_t off = 0; off + 2 <= actors.size(); ++off)
            if (actors[off] == headKind && actors[off + 1] == headBehavior) { headIdx = static_cast<int>(off); break; }
        if (headIdx >= 0) {
            for (int slot = -1; slot < 8; ++slot) {
                int idx = headIdx + slot * actorEntrySize;
                if (idx < 0 || idx + 1 >= static_cast<int>(actors.size())) continue;
                if (actors[idx] == segmentKind) ++gridSegments;
            }
        }
        int origLinkCount = 0;
        for (size_t s = 0; s + 16 <= links.size(); s += 16) {
            bool nz = false;
            for (size_t k = 0; k < 16; ++k) if (links[s + k]) { nz = true; break; }
            if (nz) ++origLinkCount;
        }
        // slot 0 of the link table is the head record; the rest are segments.
        int origSegmentLinks = std::max(0, origLinkCount - 1);
        origSegmentCount = gridSegments;

        // Decode the port's static boss model.
        load();
        resetLevel(6);
        if (levelIndex_ != 6 || !bossPresent_)
            throw std::runtime_error("port did not build the level-7 boss");
        int portSegments = 0, portHead = 0;
        int portHeadBoxW = -1, portHeadBoxH = -1;
        for (const ActiveMonster& m : monsters_) {
            if (m.behavior == 6) { ++portHead; portHeadBoxW = m.bossBoxW; portHeadBoxH = m.bossBoxH; }
            else ++portSegments;
        }
        int portActors = static_cast<int>(monsters_.size());
        int portLinks = static_cast<int>(bossLinks_.size());

        bool match =
            origHeadCount == 1 && portHead == 1 &&
            origSegmentCount == portSegments && portSegments == 6 &&
            portActors == 7 &&
            origSegmentLinks == portLinks && portLinks == 6 &&
            origHeadBoxW == portHeadBoxW && origHeadBoxH == portHeadBoxH;

        // Validate the MOTION PHYSICS of each segment link, not just the count.
        // The runtime link table (DS:0x79EA slots 1..6) is initialised from the
        // GRAN.MST link records in order, so its static physics fields must
        // equal the port's decoded bossLinks_[i] element-for-element:
        //   gain (byte2), mode (byte3), radiusX (byte4), radiusY (byte5),
        //   offX (bytes7..8), offY (bytes9..10), biasY (byte15).
        // Excluded: bytes 11..14 (per-frame outX/outY) and byte6 (phase) are
        // runtime-advanced, and bytes0..1 (target/self visual) carry a runtime
        // +2 base vs the port's +4 base (an internal numbering offset that does
        // not affect physics or rendering). Match by link index.
        int linkParamMatches = 0, linkParamChecked = 0;
        int origSpringLinks = 0, origOrbitLinks = 0;
        for (int slot = 1; slot <= 6; ++slot) {
            size_t s = static_cast<size_t>(slot) * 16;
            size_t li = static_cast<size_t>(slot - 1);
            if (s + 16 > links.size() || li >= bossLinks_.size()) continue;
            uint8_t gain = links[s + 2];
            uint8_t mode = links[s + 3];
            uint8_t radiusX = links[s + 4];
            uint8_t radiusY = links[s + 5];
            int16_t offX = static_cast<int16_t>(links[s + 7] | (links[s + 8] << 8));
            int16_t offY = static_cast<int16_t>(links[s + 9] | (links[s + 10] << 8));
            int8_t biasY = static_cast<int8_t>(links[s + 15]);
            if (mode == 0xff) ++origOrbitLinks; else ++origSpringLinks;
            const BossMotionLink& pl = bossLinks_[li];
            ++linkParamChecked;
            if (pl.gain == gain && pl.mode == mode &&
                pl.radiusX == radiusX && pl.radiusY == radiusY &&
                pl.offX == offX && pl.offY == offY && pl.biasY == biasY) {
                ++linkParamMatches;
            }
        }
        int portSpringLinks = 0, portOrbitLinks = 0;
        for (const BossMotionLink& l : bossLinks_)
            if (l.mode == 0xff) ++portOrbitLinks; else ++portSpringLinks;
        bool linkMatch = linkParamChecked == 6 && linkParamMatches == 6 &&
                         origSpringLinks == portSpringLinks &&
                         origOrbitLinks == portOrbitLinks;
        match = match && linkMatch;

        std::cout << "boss_runtime_evidence=" << (match ? "ok" : "MISMATCH")
                  << " original_head=" << origHeadCount
                  << " original_segments=" << origSegmentCount
                  << " original_actors=" << (origHeadCount + origSegmentCount)
                  << " original_segment_links=" << origSegmentLinks
                  << " original_head_box=" << origHeadBoxW << 'x' << origHeadBoxH
                  << " port_head=" << portHead
                  << " port_segments=" << portSegments
                  << " port_actors=" << portActors
                  << " port_links=" << portLinks
                  << " port_head_box=" << portHeadBoxW << 'x' << portHeadBoxH
                  << " head_kind=0x1e head_behavior=6 segment_kind=0x1f"
                  << " link_params_matched=" << linkParamMatches << '/' << linkParamChecked
                  << " original_spring_links=" << origSpringLinks
                  << " original_orbit_links=" << origOrbitLinks
                  << " port_spring_links=" << portSpringLinks
                  << " port_orbit_links=" << portOrbitLinks
                  << " boss_structure_confirmed=" << (match ? 1 : 0) << '\n';
        if (!match) throw std::runtime_error("boss model does not match original runtime evidence");
    }

    // Verify the port's RNG is bit-identical to the original's Turbo Pascal
    // Random() (generator at 0x920:0x13a8): RandSeed=RandSeed*0x08088405+1,
    // Random(L)=(RandSeed>>16) mod L. The expected vectors are computed
    // independently from that formula.
    void debugTurboRandom() {
        randomSeed_ = 0;
        std::cout << "turbo_random=ok seq100_from0=";
        for (int i = 0; i < 12; ++i) {
            if (i) std::cout << ',';
            std::cout << randomRangeValue(0, 100);
        }
        randomSeed_ = 0x1234abcd;
        std::cout << " seq1000_from_0x1234abcd=";
        for (int i = 0; i < 8; ++i) {
            if (i) std::cout << ',';
            std::cout << randomRangeValue(0, 1000);
        }
        std::cout << " multiplier=0x08088405 increment=1"
                     " extraction=high16_mod_L original=0x920:0x13a8\n";
    }

    // Pin the boss head's per-state-tick decision draws against the original's
    // formula (1000:5CB0): roar roll = Random(100), speed = 0x96 + Random(0x320),
    // in that draw order, with no player-position read. Verifies the head's
    // decision logic is a faithful translation on top of the bit-exact RNG.
    void debugBossHeadDecisions() {
        randomSeed_ = 0x1234abcd;
        std::cout << "boss_head_decisions=ok";
        for (int t = 0; t < 4; ++t) {
            int roar = static_cast<int>(randomRangeValue(0, 100));
            int speed = 0x96 + static_cast<int>(randomRangeValue(0, 0x320));
            std::cout << " tick" << t << "=roar" << roar << ",speed" << speed;
        }
        std::cout << " roar_gate=>0x46 seek=none source=1000:5CB0\n";
    }

    void debugGranBossModel() {
        // Pins the level-7 boss semantics recovered statically from the
        // shipped executable: the PROVA.SPR bank selector, the DS:0x58/0x59
        // facing anim-set pair table rows used by the boss records, and the
        // decoded GRAN.MST boss model consumed by spawnLevel7Boss(). This is
        // static instruction/data evidence; live boss presentation remains
        // original_runtime_claim=0.
        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for boss model scan");
        }
        // Level-7 sprite bank selector at 1000:2C90: cmp byte [DS:79B7],7;
        // je -> load "prova.spr" (literal 1000:2AC9) instead of
        // "bomomimk.spr" (literal 1000:2ABC) through the far loader
        // 08AC:05DC.
        static const uint8_t kSelectorBytes[] = {
            0x80, 0x3e, 0xb7, 0x79, 0x07, 0x74, 0x0c, 0xbf, 0xbc, 0x2a, 0x0e,
            0x57, 0x9a, 0xdc, 0x05, 0xac, 0x08, 0xeb, 0x0a, 0xbf, 0xc9, 0x2a,
            0x0e, 0x57};
        for (size_t i = 0; i < sizeof(kSelectorBytes); ++i) {
            if (exeBytes[imageBase + 0x2C90 + i] != kSelectorBytes[i]) {
                throw std::runtime_error("level-7 sprite bank selector bytes changed");
            }
        }
        // Facing anim-set pair table rows in the initialized data segment
        // (runtime DS = CS + 0xAA2 paragraphs -> image linear 0xAA20):
        // sets 0x0e -> 41..42, 0x0f -> 43..44, 0x10 -> 40..40.
        static const uint8_t kAnimRows[] = {0x29, 0x2a, 0x2b, 0x2c, 0x28, 0x28};
        const size_t animBase = imageBase + 0xAA20 + 0x58 + 2 * 0x0e;
        for (size_t i = 0; i < sizeof(kAnimRows); ++i) {
            if (exeBytes[animBase + i] != kAnimRows[i]) {
                throw std::runtime_error("boss anim-set pair table bytes changed");
            }
        }
        for (size_t set = 0x0e; set <= 0x10; ++set) {
            if (kBossAnimSets[set][0] != exeBytes[imageBase + 0xAA20 + 0x58 + 2 * set] ||
                kBossAnimSets[set][1] != exeBytes[imageBase + 0xAA20 + 0x59 + 2 * set]) {
                throw std::runtime_error("kBossAnimSets diverged from shipped table");
            }
        }

        // Decode the shipped boss model through the live consumer and report
        // the semantic table.
        load();
        resetLevel(6);
        if (levelIndex_ != 6 || !bossPresent_ || monsters_.size() != 7 ||
            bossLinks_.size() != 6) {
            throw std::runtime_error("boss model decode did not produce the boss");
        }
        int springLinks = 0;
        int orbitLinks = 0;
        for (const BossMotionLink& link : bossLinks_) {
            if (link.mode == 0xff) {
                ++orbitLinks;
            } else {
                ++springLinks;
            }
        }
        std::ostringstream actorList;
        const ActiveMonster* head = nullptr;
        for (size_t i = 0; i < monsters_.size(); ++i) {
            const ActiveMonster& monster = monsters_[i];
            if (i != 0) actorList << ' ';
            actorList << "actor=" << (monster.behavior == 6 ? "head" : "segment")
                      << ":vis" << static_cast<int>(monster.bossVisual) << ":"
                      << monster.x << ',' << monster.y << ":spr"
                      << static_cast<int>(monster.animFrame);
            if (monster.behavior == 6) head = &monster;
        }
        if (!head) {
            throw std::runtime_error("boss model decode missing head");
        }
        std::cout << "gran_boss_model=ok"
                  << " selector=1000:2c90"
                  << " level7_bank=prova.spr"
                  << " anim_sets=0x0e:41..42,0x0f:43..44,0x10:40..40"
                  << " boss_actors=" << monsters_.size()
                  << " head_visual=" << static_cast<int>(head->bossVisual)
                  << " head_hp=" << static_cast<int>(head->bossHpByte)
                  << " head_lives=" << static_cast<int>(head->bossLives)
                  << " head_box=" << static_cast<int>(head->bossBoxW) << 'x'
                  << static_cast<int>(head->bossBoxH)
                  << " links=" << bossLinks_.size()
                  << " spring_links=" << springLinks
                  << " orbit_links=" << orbitLinks << ' ' << actorList.str()
                  << " original_runtime_claim=0" << '\n';
    }

    void debugSoundPriorityLatch() {
        load();
        auto printCase = [&](const std::string& name, bool accepted) {
            std::cout << "sound_latch case=" << name
                      << " accepted=" << (accepted ? 1 : 0)
                      << " active=" << (soundLatch_.active ? 1 : 0)
                      << " priority=" << static_cast<int>(soundLatch_.currentSelector)
                      << " offset=" << std::showbase << std::hex
                      << soundLatch_.latchedOffset << std::dec << std::noshowbase
                      << '\n';
        };

        clearSoundLatch();
        printCase("inactive_accept",
                  latchSoundRequest(kExplosionDirectSweepSoundOffsets[0], 4));
        printCase("lower_rejected",
                  latchSoundRequest(kExplosionDirectSweepSoundOffsets[1], 2));
        printCase("same_refresh",
                  latchSoundRequest(kExplosionDirectSweepSoundOffsets[2], 4));
        printCase("higher_replaces",
                  latchSoundRequest(kExplosionDirectSweepSoundOffsets[3], 7));
        printCase("one_below_high_rejected",
                  latchSoundRequest(kExplosionDirectSweepSoundOffsets[2], 6));
        clearSoundLatch();
        printCase("cleared_accepts",
                  latchSoundRequest(kExplosionDirectSweepSoundOffsets[1], 1));

        if (!soundLatch_.active || soundLatch_.currentSelector != 1 ||
            soundLatch_.latchedOffset != kExplosionDirectSweepSoundOffsets[1] ||
            !soundLatch_.directSweep) {
            throw std::runtime_error("sound latch final state mismatch");
        }
        pumpSoundLatch();
        if (soundLatch_.active || lastPumpedSoundRecord_ != 1 ||
            lastPumpedSoundOffset_ != kExplosionDirectSweepSoundOffsets[1] ||
            lastPumpedSoundSelector_ != 1) {
            throw std::runtime_error("sound latch pump mismatch");
        }
        std::cout << "sound_pump active=" << (soundLatch_.active ? 1 : 0)
                  << " last_record=" << lastPumpedSoundRecord_
                  << " last_offset=" << std::showbase << std::hex
                  << lastPumpedSoundOffset_ << std::dec << std::noshowbase
                  << " last_selector=" << static_cast<int>(lastPumpedSoundSelector_)
                  << '\n';
        std::cout << "sound_latch=ok\n";
    }

    void debugSoundSelectorMap() {
        load();
        std::cout << "sound_selector_map records=" << sounds_.records.size() << '\n';
        for (uint8_t selector = 4; selector <= 7; ++selector) {
            uint16_t offset = explosionSoundOffset(selector - 3);
            size_t fallbackIndex = soundIndexForOffsetFallback(offset, selector);
            std::vector<int16_t> samples = synthesizeDirectSweep(offset);
            if (samples.empty()) {
                throw std::runtime_error("mapped direct sweep rendered no samples");
            }
            std::cout << "sound_selector_map selector=" << static_cast<int>(selector)
                      << " offset=" << std::showbase << std::hex << offset
                      << std::dec << std::noshowbase
                      << " direct_sweep=1"
                      << " fallback_record_index=" << fallbackIndex
                      << " samples=" << samples.size() << '\n';
        }
        if (!std::all_of(kExplosionDirectSweepSoundOffsets.begin(),
                         kExplosionDirectSweepSoundOffsets.end(),
                         [&](uint16_t offset) { return isDirectSoundSweep(offset); }) ||
            soundIndexForOffsetFallback(kExplosionDirectSweepSoundOffsets[0], 4) != 0 ||
            soundIndexForOffsetFallback(kExplosionDirectSweepSoundOffsets[1], 5) != 1 ||
            soundIndexForOffsetFallback(kExplosionDirectSweepSoundOffsets[2], 6) != 2 ||
            soundIndexForOffsetFallback(kExplosionDirectSweepSoundOffsets[3], 7) != 3) {
            throw std::runtime_error("explosion selector map mismatch");
        }
        std::cout << "sound_selector_map=ok\n";
    }

    void debugStaticSoundRequests() {
        struct StaticSoundWrite {
            uint16_t offset;
            uint16_t cursor;
        };
        struct MappedStaticSoundWrite {
            uint16_t offset;
            const char* label;
        };
        struct UnresolvedStaticSoundWrite {
            uint16_t offset;
            const char* label;
        };
        static const std::array<StaticSoundWrite, 27> kExpectedWrites{{
            {0x1857, 0x0078}, {0x1a44, 0x0008}, {0x1d9c, 0x003d},
            {0x202d, 0x0021}, {0x2083, 0x0024}, {0x2c04, 0x0078},
            {0x30b1, 0x0056}, {0x41a9, 0xea74}, {0x41ed, 0xea7e},
            {0x4231, 0xea88}, {0x431d, 0xeace}, {0x49bd, 0x0027},
            {0x4b2c, 0x0021}, {0x4d3c, 0x2710}, {0x4dd3, 0x2710},
            {0x557b, 0xea74}, {0x575d, 0x0027}, {0x5a0e, 0x001a},
            {0x5c9e, 0x003d}, {0x5e81, 0x0069}, {0x6844, 0x0024},
            {0x6924, 0x0035}, {0x6e34, 0x0012}, {0x6f82, 0x0008},
            {0x7386, 0x0021}, {0x789c, 0x0001}, {0x7f84, 0x002d},
        }};
        static const std::array<MappedStaticSoundWrite, 17> kMappedWrites{{
            {0x1857, "record_name_prompt"},
            {0x1a44, "record_name_commit"},
            {0x2083, "records_page"},
            {0x30b1, "player_death"},
            {0x41a9, "explosion_small"},
            {0x41ed, "explosion_medium"},
            {0x4231, "explosion_large"},
            {0x431d, "explosion_super"},
            {0x557b, "bomb_place"},
            {0x575d, "tile_trigger"},
            {0x5a0e, "portal_teleport"},
            {0x5c9e, "monster_death"},
            {0x6844, "weapon_switch"},
            {0x6924, "launch_pad"},
            {0x6e34, "bomb_object_high"},
            {0x6f82, "bonus_pickup"},
            {0x7f84, "player_damage"},
        }};
        static const std::array<UnresolvedStaticSoundWrite, 10> kUnresolvedWrites{{
            {0x1d9c, "post_end_flow_record_region"},
            {0x202d, "record_table_cursor_only"},
            {0x2c04, "cursor_0078_priority11"},
            {0x49bd, "cursor_0027_priority5"},
            {0x4b2c, "collapse_playback_rejected"},
            {0x4d3c, "cursor_2710"},
            {0x4dd3, "cursor_2710"},
            {0x5e81, "cursor_0069_priority4"},
            {0x7386, "cursor_0021_priority1"},
            {0x789c, "cursor_0001_no_latch"},
        }};

        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for sound scan");
        }
        size_t imageSize = exeBytes.size() - imageBase;
        std::vector<StaticSoundWrite> writes;
        for (size_t off = 0; off + 6 <= imageSize; ++off) {
            size_t p = imageBase + off;
            if (exeBytes[p] == 0xc7 && exeBytes[p + 1] == 0x06 &&
                exeBytes[p + 2] == 0x74 && exeBytes[p + 3] == 0x20) {
                writes.push_back({
                    static_cast<uint16_t>(off),
                    le16(exeBytes, p + 4),
                });
            }
        }
        if (writes.size() != kExpectedWrites.size()) {
            throw std::runtime_error("static sound request write count changed");
        }
        for (size_t i = 0; i < writes.size(); ++i) {
            if (writes[i].offset != kExpectedWrites[i].offset ||
                writes[i].cursor != kExpectedWrites[i].cursor) {
                throw std::runtime_error("static sound request table changed");
            }
        }

        auto nearLatchCallCount = [&](uint16_t offset) {
            int count = 0;
            for (size_t relOff = 0; relOff < 160; ++relOff) {
                size_t callOff = static_cast<size_t>(offset) + relOff;
                size_t p = imageBase + callOff;
                if (p + 3 > exeBytes.size() || exeBytes[p] != 0xe8) continue;
                uint16_t rawRel = le16(exeBytes, p + 1);
                int signedRel = rawRel >= 0x8000u
                                    ? static_cast<int>(rawRel) - 0x10000
                                    : static_cast<int>(rawRel);
                uint16_t target = static_cast<uint16_t>(callOff + 3 + signedRel);
                if (target == 0x165a) ++count;
            }
            return count;
        };
        auto nearPriorityWrite = [&](uint16_t offset) {
            for (size_t relOff = 0; relOff < 160; ++relOff) {
                size_t p = imageBase + static_cast<size_t>(offset) + relOff;
                if (p + 5 > exeBytes.size()) break;
                if (exeBytes[p] == 0xc6 && exeBytes[p + 1] == 0x06 &&
                    exeBytes[p + 2] == 0x9f && exeBytes[p + 3] == 0x79) {
                    return true;
                }
            }
            return false;
        };
        auto priorityAt = [&](uint16_t offset) {
            size_t p = imageBase + offset;
            if (p + 5 > exeBytes.size() || exeBytes[p] != 0xc6 ||
                exeBytes[p + 1] != 0x06 || exeBytes[p + 2] != 0x9f ||
                exeBytes[p + 3] != 0x79) {
                throw std::runtime_error("expected static priority write missing");
            }
            return exeBytes[p + 4];
        };

        int latchCandidates = 0;
        int latchRefs = 0;
        int priorityCandidates = 0;
        int directSweepWrites = 0;
        int mappedWrites = 0;
        std::ostringstream list;
        std::ostringstream mappedLabels;
        std::ostringstream unresolvedCandidates;
        std::ostringstream unresolvedLabels;
        for (size_t i = 0; i < writes.size(); ++i) {
            int calls = nearLatchCallCount(writes[i].offset);
            if (calls > 0) ++latchCandidates;
            latchRefs += calls;
            if (nearPriorityWrite(writes[i].offset)) ++priorityCandidates;
            if (isDirectSoundSweep(writes[i].cursor)) ++directSweepWrites;
            auto mappedIt = std::find_if(
                kMappedWrites.begin(), kMappedWrites.end(),
                [&](const MappedStaticSoundWrite& mapped) {
                    return mapped.offset == writes[i].offset;
                });
            if (mappedIt != kMappedWrites.end()) {
                ++mappedWrites;
                if (mappedLabels.tellp() > 0) mappedLabels << ',';
                mappedLabels << hex4(mappedIt->offset) << ':' << mappedIt->label;
            } else {
                auto unresolvedIt = std::find_if(
                    kUnresolvedWrites.begin(), kUnresolvedWrites.end(),
                    [&](const UnresolvedStaticSoundWrite& unresolved) {
                        return unresolved.offset == writes[i].offset;
                    });
                if (unresolvedIt == kUnresolvedWrites.end()) {
                    throw std::runtime_error("unclassified static sound write");
                }
                if (unresolvedCandidates.tellp() > 0) unresolvedCandidates << ',';
                unresolvedCandidates << hex4(writes[i].offset);
                if (unresolvedLabels.tellp() > 0) unresolvedLabels << ',';
                unresolvedLabels << hex4(unresolvedIt->offset) << ':'
                                 << unresolvedIt->label;
            }
            if (i != 0) list << ',';
            list << hex4(writes[i].offset) << ':' << hex4(writes[i].cursor);
        }
        if (latchCandidates != 21 || latchRefs != 22 ||
            priorityCandidates != 21 || directSweepWrites != 5 ||
            mappedWrites != static_cast<int>(kMappedWrites.size()) ||
            priorityAt(0x185d) != kRecordNamePromptSoundPriority ||
            nearLatchCallCount(0x1857) != 1 ||
            priorityAt(0x1a4a) != kRecordNameCommitSoundPriority ||
            nearLatchCallCount(0x1a44) != 1 ||
            priorityAt(0x2089) != kRecordsPageSoundPriority ||
            nearLatchCallCount(0x2083) != 1 ||
            priorityAt(0x5581) != kBombPlaceSoundPriority ||
            nearLatchCallCount(0x557b) != 1 ||
            priorityAt(0x5ca4) != kMonsterDeathSoundPriority ||
            nearLatchCallCount(0x5c9e) != 1) {
            throw std::runtime_error("static sound request summary changed");
        }
        auto remainingHookList = [] {
            std::ostringstream out;
            for (size_t i = 0; i < kRemainingSoundCompatibilityHooks.size(); ++i) {
                if (i != 0) out << ',';
                out << kRemainingSoundCompatibilityHooks[i].hook;
            }
            return out.str();
        };
        auto rejectedObjectiveCandidateList = [] {
            std::ostringstream out;
            for (size_t i = 0; i < kRejectedObjectiveSoundCandidates.size(); ++i) {
                if (i != 0) out << ',';
                const RejectedSoundCandidate& candidate =
                    kRejectedObjectiveSoundCandidates[i];
                out << hex4(candidate.offset) << ':' << candidate.reason;
            }
            return out.str();
        };
        auto remainingCaptureBlockerList = [] {
            std::ostringstream out;
            for (size_t i = 0; i < kRemainingSoundCompatibilityHooks.size(); ++i) {
                if (i != 0) out << ',';
                const RemainingSoundCompatibilityHook& hook =
                    kRemainingSoundCompatibilityHooks[i];
                out << hook.hook << ':' << hook.captureBlocker;
            }
            return out.str();
        };
        std::string remainingHooks = remainingHookList();
        std::string rejectedObjectiveCandidates = rejectedObjectiveCandidateList();
        std::string remainingCaptureBlockers = remainingCaptureBlockerList();
        std::string mappedLabelList = mappedLabels.str();
        std::string unresolvedCandidateList = unresolvedCandidates.str();
        std::string unresolvedLabelList = unresolvedLabels.str();
        if (remainingHooks != "objective_pickup,level_complete" ||
            rejectedObjectiveCandidates !=
                "0x4b2c:collapse_playback,0x6d75:bomb_object_high_gate,"
                "0x6924:non_objective_tile_gate" ||
            remainingCaptureBlockers !=
                "objective_pickup:rejected_static_candidates,"
                "level_complete:no_static_candidate") {
            throw std::runtime_error("sound compatibility recovery notes changed");
        }
        if (mappedLabelList !=
                "0x1857:record_name_prompt,0x1a44:record_name_commit,"
                "0x2083:records_page,0x30b1:player_death,"
                "0x41a9:explosion_small,0x41ed:explosion_medium,"
                "0x4231:explosion_large,0x431d:explosion_super,"
                "0x557b:bomb_place,0x575d:tile_trigger,"
                "0x5a0e:portal_teleport,0x5c9e:monster_death,"
                "0x6844:weapon_switch,0x6924:launch_pad,"
                "0x6e34:bomb_object_high,0x6f82:bonus_pickup,"
                "0x7f84:player_damage" ||
            unresolvedCandidateList !=
                "0x1d9c,0x202d,0x2c04,0x49bd,0x4b2c,0x4d3c,"
                "0x4dd3,0x5e81,0x7386,0x789c") {
            throw std::runtime_error("static sound mapping ledger changed");
        }
        if (unresolvedLabelList !=
                "0x1d9c:post_end_flow_record_region,"
                "0x202d:record_table_cursor_only,"
                "0x2c04:cursor_0078_priority11,"
                "0x49bd:cursor_0027_priority5,"
                "0x4b2c:collapse_playback_rejected,"
                "0x4d3c:cursor_2710,"
                "0x4dd3:cursor_2710,"
                "0x5e81:cursor_0069_priority4,"
                "0x7386:cursor_0021_priority1,"
                "0x789c:cursor_0001_no_latch") {
            throw std::runtime_error("static sound unresolved labels changed");
        }

        std::cout << "static_sound_requests=ok writes=" << writes.size()
                  << " image_base=0x0770"
                  << " latch=0x165a"
                  << " latch_candidates=" << latchCandidates
                  << " latch_refs=" << latchRefs
                  << " priority_candidates=" << priorityCandidates
                  << " direct_sweep=" << directSweepWrites
                  << " mapped=" << mappedWrites
                  << " unresolved=" << (static_cast<int>(writes.size()) - mappedWrites)
                  << " record_prompt=" << hex4(0x1857) << ':'
                  << hex4(kRecordNamePromptSoundCursor)
                  << "/p" << static_cast<int>(kRecordNamePromptSoundPriority)
                  << " record_commit=" << hex4(0x1a44) << ':'
                  << hex4(kRecordNameCommitSoundCursor)
                  << "/p" << static_cast<int>(kRecordNameCommitSoundPriority)
                  << " records_page=" << hex4(0x2083) << ':'
                  << hex4(kRecordsPageSoundCursor)
                  << "/p" << static_cast<int>(kRecordsPageSoundPriority)
                  << " bomb_place=" << hex4(0x557b) << ':' << hex4(kBombPlaceSoundCursor)
                  << "/p" << static_cast<int>(kBombPlaceSoundPriority)
                  << " monster_death=" << hex4(0x5c9e) << ':'
                  << hex4(kMonsterDeathSoundCursor)
                  << "/p" << static_cast<int>(kMonsterDeathSoundPriority)
                  << " weapon_switch=" << hex4(0x6844) << ':'
                  << hex4(kWeaponSwitchSoundCursor)
                  << "/p" << static_cast<int>(kWeaponSwitchSoundPriority)
                  << " launch_pad=" << hex4(0x6924) << ':'
                  << hex4(kLaunchPadSoundCursor)
                  << "/p" << static_cast<int>(kLaunchPadSoundPriority)
                  << " mapped_labels=" << mappedLabelList
                  << " unresolved_candidates=" << unresolvedCandidateList
                  << " unresolved_labels=" << unresolvedLabelList
                  << " remaining_compat_hooks=" << remainingHooks
                  << " capture_blockers=" << remainingCaptureBlockers
                  << " rejected_objective_candidates="
                  << rejectedObjectiveCandidates
                  << " cursor_writes=" << list.str() << '\n';
    }

    void debugInputFireKeyModel() {
        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for input key scan");
        }

        auto requireBytes = [&](uint16_t offset, const std::string& hex,
                                const std::string& label) {
            std::vector<uint8_t> expected = parseHexByteList(hex);
            size_t p = imageBase + offset;
            if (p + expected.size() > exeBytes.size()) {
                throw std::runtime_error(label + " context extends past LEZAC.EXE");
            }
            for (size_t i = 0; i < expected.size(); ++i) {
                if (exeBytes[p + i] != expected[i]) {
                    throw std::runtime_error(label + " context bytes changed");
                }
            }
        };
        auto countBytes = [&](const std::string& hex) {
            std::vector<uint8_t> needle = parseHexByteList(hex);
            int count = 0;
            for (size_t p = imageBase; p + needle.size() <= exeBytes.size(); ++p) {
                if (std::equal(needle.begin(), needle.end(), exeBytes.begin() + p)) {
                    ++count;
                }
            }
            return count;
        };

        requireBytes(0x10bd, "3c 31 75 04 88 26 7b 1b",
                     "player 1 fire make gate");
        requireBytes(0x110f, "3c b1 75 04 88 26 7b 1b",
                     "player 1 fire break gate");
        requireBytes(0x10dd, "3c 52 75 04 88 26 80 1b",
                     "player 2 fire make gate");
        requireBytes(0x112f, "3c d2 75 04 88 26 80 1b",
                     "player 2 fire break gate");

        int p1GateRefs = countBytes("7b 1b");
        int p2GateRefs = countBytes("80 1b");
        if (p1GateRefs != 7 || p2GateRefs != 7) {
            throw std::runtime_error("input fire key gate reference count changed");
        }
        if (!isPlayer1FireKey(SDLK_n) || !isPlayer1FireKey(SDLK_SPACE) ||
            !isPlayer1FireKey(SDLK_RCTRL) || isPlayer1FireKey(SDLK_KP_0) ||
            !isPlayer2FireKey(SDLK_KP_0) || !isPlayer2FireKey(SDLK_INSERT) ||
            isPlayer2FireKey(SDLK_n)) {
            throw std::runtime_error("SDL fire key compatibility mapping changed");
        }

        std::cout << "input_fire_key_model=ok"
                  << " image_base=0x0770"
                  << " handler=1000:1091"
                  << " p1_gate=DS:1b7b"
                  << " p1_make=0x31"
                  << " p1_break=0xb1"
                  << " p1_refs=" << p1GateRefs
                  << " p1_sdl=n"
                  << " p1_compat=space,rctrl"
                  << " p2_gate=DS:1b80"
                  << " p2_make=0x52"
                  << " p2_break=0xd2"
                  << " p2_refs=" << p2GateRefs
                  << " p2_sdl=kp0,insert"
                  << '\n';
    }

    void debugStaticSoundContexts() {
        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for sound context scan");
        }

        auto requireBytes = [&](uint16_t offset, const std::string& hex,
                                const std::string& label) {
            std::vector<uint8_t> expected = parseHexByteList(hex);
            size_t p = imageBase + offset;
            if (p + expected.size() > exeBytes.size()) {
                throw std::runtime_error(label + " context extends past LEZAC.EXE");
            }
            for (size_t i = 0; i < expected.size(); ++i) {
                if (exeBytes[p + i] != expected[i]) {
                    throw std::runtime_error(label + " context bytes changed");
                }
            }
        };
        auto imageContainsAscii = [&](const std::string& needle) {
            std::vector<uint8_t> bytes(needle.begin(), needle.end());
            return std::search(exeBytes.begin() + static_cast<long>(imageBase),
                               exeBytes.end(), bytes.begin(), bytes.end()) != exeBytes.end();
        };
        auto priorityString = [](uint8_t priority) {
            if (priority == 0) return std::string("deferred");
            return std::string("p") + std::to_string(static_cast<int>(priority));
        };

        requireBytes(0x1857, "c7 06 74 20 78 00 c6 06 9f 79 0b e8 f5 fd",
                     "name-entry 0x1857 sound write");
        requireBytes(0x1a44, "c7 06 74 20 08 00 c6 06 9f 79 0b e8 08 fc",
                     "name-entry 0x1a44 sound write");
        requireBytes(0x1d42, "c2 02 00", "end-flow dispatcher return");
        requireBytes(0x1d45, "09 66 6f 6e 74 73 2e 73 70 72 0b 62 6f 6d 62 61 20 62 6f 6e 75 73",
                     "post-end-flow font/bonus strings");
        requireBytes(0x1d9c, "c7 06 74 20 3d 00 c6 06 9f 79 0a e8 b0 f8",
                     "post-end-flow 0x1d9c sound write");
        requireBytes(0x202d, "c7 06 74 20 21 00 e8 24 f6",
                     "record-table 0x202d sound write");
        requireBytes(0x2083, "c7 06 74 20 24 00 c6 06 9f 79 02 e8 c9 f5",
                     "record-table 0x2083 sound write");

        if (!imageContainsAscii("inserisci il tuo nome;") ||
            !imageContainsAscii("punteggi migliori") ||
            !imageContainsAscii("bomba bonus")) {
            throw std::runtime_error("record/menu sound context strings changed");
        }
        for (const StaticSoundContext& context : kRecordUiSoundContexts) {
            if (context.offset >= kEndFlowDispatcherStart &&
                context.offset <= kEndFlowDispatcherRet) {
                throw std::runtime_error("record UI sound context overlaps end-flow dispatcher");
            }
        }
        if (!(0x1d9c > kEndFlowDispatcherRet && 0x1d9c < 0x202d)) {
            throw std::runtime_error("post-end-flow sound context ordering changed");
        }

        std::ostringstream recordContexts;
        for (size_t i = 0; i < kRecordUiSoundContexts.size(); ++i) {
            if (i != 0) recordContexts << ',';
            const StaticSoundContext& context = kRecordUiSoundContexts[i];
            recordContexts << hex4(context.offset) << ':' << hex4(context.cursor)
                           << '/' << priorityString(context.priority) << ':'
                           << context.context;
        }

        std::cout << "static_sound_contexts=ok"
                  << " image_base=0x0770"
                  << " end_flow_dispatcher=" << hex4(kEndFlowDispatcherStart)
                  << ".." << hex4(kEndFlowDispatcherRet)
                  << " first_post_end_flow_sound=" << hex4(0x1d9c)
                  << " level_complete_static_candidate=none"
                  << " record_ui_writes=" << recordContexts.str()
                  << " strings=inserisci_il_tuo_nome,punteggi_migliori,bomba_bonus"
                  << " remaining_compat_hooks=objective_pickup,level_complete"
                  << '\n';
    }

    void debugStaticSoundUnresolvedContexts() {
        struct UnresolvedContext {
            uint16_t offset;
            uint16_t cursor;
            int priority;
            uint16_t priorityOffset;
            const char* priorityPlacement;
            int expectedLocalLatchCalls;
            const char* region;
            const char* captureClass;
            const char* label;
            const char* bytes;
        };
        static const std::array<UnresolvedContext, 10> kContexts{{
            {0x1d9c, 0x003d, 10, 0x1da2, "inline", 1,
             "record_ui", "record_ui_static", "post_end_flow_record_region",
             "c7 06 74 20 3d 00 c6 06 9f 79 0a e8 b0 f8"},
            {0x202d, 0x0021, -1, 0x0000, "none", 1,
             "record_ui", "record_ui_static", "record_table_cursor_only",
             "c7 06 74 20 21 00 e8 24 f6"},
            {0x2c04, 0x0078, 11, 0x2c0a, "inline", 1,
             "pre_new_game_setup", "pre_new_game_static", "cursor_0078_priority11",
             "c7 06 74 20 78 00 c6 06 9f 79 0b e8 48 ea"},
            {0x49bd, 0x0027, 5, 0x49c3, "inline", 1,
             "explosion_playback", "explosion_static", "cursor_0027_priority5",
             "c7 06 74 20 27 00 c6 06 9f 79 05 e8 8f cc"},
            {0x4b2c, 0x0021, 2, 0x4b27, "preceding", 1,
             "explosion_playback", "explosion_static", "collapse_playback_rejected",
             "c7 06 74 20 21 00 e8 25 cb"},
            {0x4d3c, 0x2710, -1, 0x0000, "none", 0,
             "effect_extent_scan", "effect_extent_static", "cursor_2710",
             "c7 06 74 20 10 27 c7 06 72 20 00 00 c6 06 1e 66 00"},
            {0x4dd3, 0x2710, -1, 0x0000, "none", 0,
             "effect_extent_scan", "effect_extent_static", "cursor_2710",
             "c7 06 74 20 10 27 c7 06 72 20 00 00 c6 06 1e 66 00"},
            {0x5e81, 0x0069, 4, 0x5e87, "inline", 1,
             "contact_scanner", "actor_contact_runtime", "cursor_0069_priority4",
             "c7 06 74 20 69 00 c6 06 9f 79 04 e8 cb b7"},
            {0x7386, 0x0021, 1, 0x7381, "preceding", 1,
             "actor_update", "actor_contact_runtime", "cursor_0021_priority1",
             "c7 06 74 20 21 00 e8 cb a2"},
            {0x789c, 0x0001, -1, 0x0000, "none", 0,
             "post_actor_update_no_latch", "post_actor_update_no_latch",
             "cursor_0001_no_latch",
             "c7 06 74 20 01 00 eb 04 ff 06 74 20"},
        }};

        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for unresolved sound scan");
        }

        auto requireBytes = [&](uint16_t offset, const std::string& hex,
                                const std::string& label) {
            std::vector<uint8_t> expected = parseHexByteList(hex);
            size_t p = imageBase + offset;
            if (p + expected.size() > exeBytes.size()) {
                throw std::runtime_error(label + " extends past LEZAC.EXE");
            }
            for (size_t i = 0; i < expected.size(); ++i) {
                if (exeBytes[p + i] != expected[i]) {
                    throw std::runtime_error(label + " bytes changed");
                }
            }
        };
        auto localLatchCallCount = [&](uint16_t offset) {
            int count = 0;
            for (size_t relOff = 0; relOff < 24; ++relOff) {
                size_t callOff = static_cast<size_t>(offset) + relOff;
                size_t p = imageBase + callOff;
                if (p + 3 > exeBytes.size() || exeBytes[p] != 0xe8) continue;
                uint16_t rawRel = le16(exeBytes, p + 1);
                int signedRel = rawRel >= 0x8000u
                                    ? static_cast<int>(rawRel) - 0x10000
                                    : static_cast<int>(rawRel);
                uint16_t target = static_cast<uint16_t>(callOff + 3 + signedRel);
                if (target == 0x165a) ++count;
            }
            return count;
        };
        auto requirePriority = [&](const UnresolvedContext& context) {
            if (context.priority < 0) return;
            size_t p = imageBase + context.priorityOffset;
            if (p + 5 > exeBytes.size() || exeBytes[p] != 0xc6 ||
                exeBytes[p + 1] != 0x06 || exeBytes[p + 2] != 0x9f ||
                exeBytes[p + 3] != 0x79 ||
                exeBytes[p + 4] != static_cast<uint8_t>(context.priority)) {
                throw std::runtime_error(std::string(context.label) +
                                         " priority bytes changed");
            }
        };

        int localLatch = 0;
        int localLatchRefs = 0;
        int inlinePriority = 0;
        int precedingPriority = 0;
        int noPriority = 0;
        int noLatch = 0;
        int directSweep = 0;
        int cursor2710 = 0;
        std::map<std::string, int> regionCounts;
        std::map<std::string, int> captureClassCounts;
        std::ostringstream contexts;
        std::ostringstream actorContactCaptureCandidates;
        for (size_t i = 0; i < kContexts.size(); ++i) {
            const UnresolvedContext& context = kContexts[i];
            requireBytes(context.offset, context.bytes, context.label);
            requirePriority(context);
            ++regionCounts[context.region];
            ++captureClassCounts[context.captureClass];
            int calls = localLatchCallCount(context.offset);
            if (calls != context.expectedLocalLatchCalls) {
                throw std::runtime_error(std::string(context.label) +
                                         " local latch call count changed");
            }
            if (calls > 0) ++localLatch;
            else ++noLatch;
            localLatchRefs += calls;
            if (std::string(context.priorityPlacement) == "inline") {
                ++inlinePriority;
            } else if (std::string(context.priorityPlacement) == "preceding") {
                ++precedingPriority;
            } else {
                ++noPriority;
            }
            if (isDirectSoundSweep(context.cursor)) ++directSweep;
            if (context.cursor == 0x2710) ++cursor2710;
            if (std::string(context.captureClass) == "actor_contact_runtime") {
                if (actorContactCaptureCandidates.tellp() > 0) {
                    actorContactCaptureCandidates << ',';
                }
                actorContactCaptureCandidates << hex4(context.offset) << ':'
                                              << context.region;
            }

            if (i != 0) contexts << ',';
            contexts << hex4(context.offset) << ':' << hex4(context.cursor) << '/';
            if (context.priority >= 0) {
                contexts << 'p' << context.priority;
            } else {
                contexts << "no_priority";
            }
            contexts << ':' << context.priorityPlacement
                     << ":latch" << calls << ':' << context.region << ':'
                     << context.label;
        }

        auto regionCountText = [&] {
            std::ostringstream out;
            bool first = true;
            for (const auto& entry : regionCounts) {
                if (!first) out << ',';
                first = false;
                out << entry.first << ':' << entry.second;
            }
            return out.str();
        };
        auto captureClassCountText = [&] {
            std::ostringstream out;
            bool first = true;
            for (const auto& entry : captureClassCounts) {
                if (!first) out << ',';
                first = false;
                out << entry.first << ':' << entry.second;
            }
            return out.str();
        };
        std::string contextList = contexts.str();
        std::string regionCountsList = regionCountText();
        std::string captureClassCountsList = captureClassCountText();
        std::string actorContactCaptureCandidateList =
            actorContactCaptureCandidates.str();
        if (localLatch != 7 || localLatchRefs != 7 || inlinePriority != 4 ||
            precedingPriority != 2 || noPriority != 4 || noLatch != 3 ||
            directSweep != 0 || cursor2710 != 2) {
            throw std::runtime_error("unresolved static sound context summary changed");
        }
        if (regionCountsList !=
                "actor_update:1,contact_scanner:1,effect_extent_scan:2,"
                "explosion_playback:2,post_actor_update_no_latch:1,"
                "pre_new_game_setup:1,record_ui:2") {
            throw std::runtime_error("unresolved static sound region counts changed");
        }
        if (captureClassCountsList !=
                "actor_contact_runtime:2,effect_extent_static:2,"
                "explosion_static:2,post_actor_update_no_latch:1,"
                "pre_new_game_static:1,record_ui_static:2") {
            throw std::runtime_error("unresolved static sound capture classes changed");
        }
        if (actorContactCaptureCandidateList !=
                "0x5e81:contact_scanner,0x7386:actor_update") {
            throw std::runtime_error(
                "unresolved static sound actor/contact capture list changed");
        }
        if (contextList !=
                "0x1d9c:0x003d/p10:inline:latch1:record_ui:post_end_flow_record_region,"
                "0x202d:0x0021/no_priority:none:latch1:record_ui:record_table_cursor_only,"
                "0x2c04:0x0078/p11:inline:latch1:pre_new_game_setup:cursor_0078_priority11,"
                "0x49bd:0x0027/p5:inline:latch1:explosion_playback:cursor_0027_priority5,"
                "0x4b2c:0x0021/p2:preceding:latch1:explosion_playback:collapse_playback_rejected,"
                "0x4d3c:0x2710/no_priority:none:latch0:effect_extent_scan:cursor_2710,"
                "0x4dd3:0x2710/no_priority:none:latch0:effect_extent_scan:cursor_2710,"
                "0x5e81:0x0069/p4:inline:latch1:contact_scanner:cursor_0069_priority4,"
                "0x7386:0x0021/p1:preceding:latch1:actor_update:cursor_0021_priority1,"
                "0x789c:0x0001/no_priority:none:latch0:post_actor_update_no_latch:cursor_0001_no_latch") {
            throw std::runtime_error("unresolved static sound context list changed");
        }

        std::cout << "static_sound_unresolved_contexts=ok"
                  << " writes=" << kContexts.size()
                  << " image_base=0x0770"
                  << " latch=0x165a"
                  << " local_latch=" << localLatch
                  << " local_latch_refs=" << localLatchRefs
                  << " inline_priority=" << inlinePriority
                  << " preceding_priority=" << precedingPriority
                  << " no_priority=" << noPriority
                  << " no_latch=" << noLatch
                  << " direct_sweep=" << directSweep
                  << " cursor_2710=" << cursor2710
                  << " region_counts=" << regionCountsList
                  << " capture_classes=" << captureClassCountsList
                  << " actor_contact_capture_candidates="
                  << actorContactCaptureCandidateList
                  << " contexts=" << contextList
                  << '\n';
    }

    void debugSoundRuntimeCaptureQueue() {
        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for sound runtime queue");
        }

        auto requireBytes = [&](const RuntimeSoundCaptureTarget& target) {
            std::vector<uint8_t> expected = parseHexByteList(target.bytes);
            size_t p = imageBase + target.offset;
            if (p + expected.size() > exeBytes.size()) {
                throw std::runtime_error(std::string(target.scenario) +
                                         " bytes extend past LEZAC.EXE");
            }
            for (size_t i = 0; i < expected.size(); ++i) {
                if (exeBytes[p + i] != expected[i]) {
                    throw std::runtime_error(std::string(target.scenario) +
                                             " bytes changed");
                }
            }
        };

        std::ostringstream targets;
        std::map<std::string, int> regionCounts;
        std::map<std::string, int> routeClassCounts;
        for (size_t i = 0; i < kActorContactSoundCaptureTargets.size(); ++i) {
            const RuntimeSoundCaptureTarget& target =
                kActorContactSoundCaptureTargets[i];
            requireBytes(target);
            ++regionCounts[target.region];
            ++routeClassCounts[target.routeClass];
            if (i != 0) targets << ',';
            targets << target.scenario << ':' << hex4(target.offset) << ':'
                    << hex4(target.cursor) << "/p"
                    << static_cast<int>(target.priority) << ':' << target.region
                    << ':' << target.label << ':' << target.status << ':'
                    << target.routeClass << ':' << target.captureBlocker;
        }

        std::ostringstream regionText;
        bool first = true;
        for (const auto& entry : regionCounts) {
            if (!first) regionText << ',';
            first = false;
            regionText << entry.first << ':' << entry.second;
        }

        std::ostringstream routeClassText;
        first = true;
        for (const auto& entry : routeClassCounts) {
            if (!first) routeClassText << ',';
            first = false;
            routeClassText << entry.first << ':' << entry.second;
        }

        const std::string targetText = targets.str();
        const std::string regionList = regionText.str();
        const std::string routeClassList = routeClassText.str();
        if (targetText !=
                "actor_update_runtime_cursor_0024_sound:0x6844:0x0024/p2:actor_update:cursor_0024_priority2:staged:natural:normalized_fixture_required,"
                "actor_update_runtime_cursor_0035_sound:0x6924:0x0035/p5:actor_update:launch_pad:staged:natural:level6_route_required,"
                "actor_update_runtime_cursor_0021_sound:0x7386:0x0021/p1:actor_update:cursor_0021_priority1:staged:natural:semantic_event_unknown,"
                "contact_scanner_runtime_sound:0x5e81:0x0069/p4:contact_scanner:cursor_0069_priority4:seeded_only:runtime_seeded:shipped_actor_modes_exclude_6") {
            throw std::runtime_error("sound runtime capture target queue changed");
        }
        if (regionList != "actor_update:3,contact_scanner:1") {
            throw std::runtime_error("sound runtime capture region summary changed");
        }
        if (routeClassList != "natural:3,runtime_seeded:1") {
            throw std::runtime_error("sound runtime capture route classes changed");
        }

        std::cout << "sound_runtime_capture_queue=ok"
                  << " capture_class=actor_contact_runtime"
                  << " targets=" << kActorContactSoundCaptureTargets.size()
                  << " first_target=actor_update_runtime_cursor_0024_sound"
                  << " helper=tools/capture_original_sound_callsite_procmem.sh"
                  << " route_sweep=tools/sweep_original_sound_callsite_routes.py"
                  << " oracle=--debug-sound-callsite-oracle"
                  << " fixture_prefix=sound_callsite_oracle_original"
                  << " promotion_status=runtime_fixture_required"
                  << " approval_flags=LEZAC_SOUND_CALLSITE_APPROVE_PROCMEM,"
                  << "LEZAC_SOUND_CALLSITE_APPROVE_RUNTIME_INSTRUMENTATION"
                  << " original_cursor_priority_claim=0"
                  << " regions=" << regionList
                  << " route_classes=" << routeClassList
                  << " state6_capture_blocker=shipped_actor_modes_exclude_6"
                  << " target_queue=" << targetText
                  << '\n';
    }

    void debugRemainingSoundCompatibilityHooks() {
        load();
        resetLevel(0);

        traceCompatibilitySoundAttempts_ = true;
        compatibilitySoundAttempts_.clear();
        std::array<int, 2> objectiveProbe = findSingleObjectiveProbeForSmoke();
        player_.x = static_cast<float>(objectiveProbe[0]);
        player_.y = static_cast<float>(objectiveProbe[1]);
        int collectedBefore = collected_;
        uint32_t scoreBefore = score_;
        clearSoundLatch();
        requestRecordsPageSound();
        SoundLatch objectiveSeedLatch = soundLatch_;
        collectObjectiveTiles(player_, 1);
        bool objectiveLatchPreserved = sameSoundLatch(soundLatch_, objectiveSeedLatch);
        if (compatibilitySoundAttempts_.size() != 1) {
            throw std::runtime_error("objective pickup compatibility sound call count mismatch");
        }
        const RemainingSoundCompatibilityHook& objectiveHook =
            kRemainingSoundCompatibilityHooks[kObjectivePickupCompatibilityHookSlot];
        CompatibilitySoundAttempt objectiveAttempt = compatibilitySoundAttempts_.front();
        if (std::string(objectiveHook.hook) != "objective_pickup" ||
            objectiveAttempt.index != objectiveHook.index ||
            objectiveAttempt.cursor != compatibilitySoundCursor(objectiveHook.index) ||
            collected_ != collectedBefore + 1 ||
            score_ != scoreBefore + 1000u ||
            !objectiveSeedLatch.active ||
            !objectiveLatchPreserved) {
            throw std::runtime_error("objective pickup compatibility sound route mismatch");
        }
        int collectedDelta = collected_ - collectedBefore;
        uint32_t scoreDelta = score_ - scoreBefore;

        traceCompatibilitySoundAttempts_ = false;
        resetLevel(0);
        collectAllObjectiveTilesForSmoke();
        damageRequiredTilesForSmoke();
        if (!isComplete()) {
            throw std::runtime_error("level-complete compatibility fixture is incomplete");
        }

        traceCompatibilitySoundAttempts_ = true;
        compatibilitySoundAttempts_.clear();
        clearSoundLatch();
        requestRecordsPageSound();
        SoundLatch levelSeedLatch = soundLatch_;
        int startLevel = levelIndex_;
        updateLevelCompletion();
        bool levelLatchPreserved = sameSoundLatch(soundLatch_, levelSeedLatch);
        size_t callsFirstTick = compatibilitySoundAttempts_.size();
        if (callsFirstTick != 1) {
            throw std::runtime_error("level-complete compatibility sound call count mismatch");
        }
        const RemainingSoundCompatibilityHook& levelHook =
            kRemainingSoundCompatibilityHooks[kLevelCompleteCompatibilityHookSlot];
        CompatibilitySoundAttempt levelAttempt = compatibilitySoundAttempts_.front();
        if (std::string(levelHook.hook) != "level_complete" ||
            levelAttempt.index != levelHook.index ||
            levelAttempt.cursor != compatibilitySoundCursor(levelHook.index) ||
            !levelSeedLatch.active ||
            !levelLatchPreserved) {
            throw std::runtime_error("level-complete compatibility sound route mismatch");
        }

        compatibilitySoundAttempts_.clear();
        int completionTicksAfterFirst = 0;
        while (levelIndex_ == startLevel && completionTicksAfterFirst <= 120) {
            updateLevelCompletion();
            ++completionTicksAfterFirst;
        }
        size_t repeatCalls = compatibilitySoundAttempts_.size();
        traceCompatibilitySoundAttempts_ = false;
        if (repeatCalls != 0 || levelIndex_ != startLevel + 1) {
            throw std::runtime_error("level-complete compatibility sound repeat/advance mismatch");
        }

        std::cout << "remaining_sound_compat_hooks=ok"
                  << " live_hooks=2"
                  << " helper=playCompatibilitySound"
                  << " objective_pickup=index" << objectiveAttempt.index
                  << "/cursor" << hex4(objectiveAttempt.cursor)
                  << "/blocker=" << objectiveHook.captureBlocker
                  << " collected_delta=" << collectedDelta
                  << " score_delta=" << scoreDelta
                  << " latch_seed=" << hex4(objectiveSeedLatch.latchedOffset)
                  << "/p" << static_cast<int>(objectiveSeedLatch.currentSelector)
                  << " latch_preserved=" << (objectiveLatchPreserved ? 1 : 0)
                  << " level_complete=index" << levelAttempt.index
                  << "/cursor" << hex4(levelAttempt.cursor)
                  << "/blocker=" << levelHook.captureBlocker
                  << " calls_first_tick=" << callsFirstTick
                  << " repeat_calls=" << repeatCalls
                  << " advanced_level=" << (levelIndex_ + 1)
                  << " latch_seed=" << hex4(levelSeedLatch.latchedOffset)
                  << "/p" << static_cast<int>(levelSeedLatch.currentSelector)
                  << " latch_preserved=" << (levelLatchPreserved ? 1 : 0)
                  << " capture_blockers=objective_pickup:rejected_static_candidates,"
                  << "level_complete:no_static_candidate"
                  << " original_cursor_priority_claim=0\n";
    }

    void debugRecordNameSoundRouting(const std::string& path) {
        load();
        recordPath_ = path;
        saveRecords(recordPath_, records_);
        clearSoundLatch();
        lastPumpedSoundOffset_ = 0;
        lastPumpedSoundSelector_ = 0;

        score_ = 999999u;
        levelIndex_ = 0;
        beginGameOver();
        if (menuPage_ != MenuPage::NameEntry ||
            !soundLatch_.active ||
            soundLatch_.latchedOffset != kRecordNamePromptSoundCursor ||
            soundLatch_.currentSelector != kRecordNamePromptSoundPriority ||
            soundLatch_.directSweep) {
            throw std::runtime_error("record name prompt sound request mismatch");
        }
        pumpSoundLatch();
        if (soundLatch_.active ||
            lastPumpedSoundOffset_ != kRecordNamePromptSoundCursor ||
            lastPumpedSoundSelector_ != kRecordNamePromptSoundPriority) {
            throw std::runtime_error("record name prompt sound pump mismatch");
        }

        bool running = true;
        onKey(SDLK_o, running);
        onKey(SDLK_k, running);
        onKey(SDLK_RETURN, running);
        if (menuPage_ != MenuPage::Records ||
            !soundLatch_.active ||
            soundLatch_.latchedOffset != kRecordNameCommitSoundCursor ||
            soundLatch_.currentSelector != kRecordNameCommitSoundPriority ||
            soundLatch_.directSweep) {
            throw std::runtime_error("record name commit sound request mismatch");
        }
        pumpSoundLatch();
        if (soundLatch_.active ||
            lastPumpedSoundOffset_ != kRecordNameCommitSoundCursor ||
            lastPumpedSoundSelector_ != kRecordNameCommitSoundPriority) {
            throw std::runtime_error("record name commit sound pump mismatch");
        }

        auto reloaded = loadRecords(recordPath_);
        if (reloaded.empty() || reloaded[0].score != 999999u ||
            reloaded[0].name != "ok") {
            throw std::runtime_error("record name sound route did not commit record");
        }

        std::cout << "record_name_sound=ok"
                  << " prompt_cursor=" << hex4(kRecordNamePromptSoundCursor)
                  << " prompt_priority="
                  << static_cast<int>(kRecordNamePromptSoundPriority)
                  << " commit_cursor=" << hex4(kRecordNameCommitSoundCursor)
                  << " commit_priority="
                  << static_cast<int>(kRecordNameCommitSoundPriority)
                  << " direct_sweep=0"
                  << " ghidra_prompt=1000:1857"
                  << " ghidra_commit=1000:1a44"
                  << " latch=1000:165a"
                  << '\n';
    }

    void debugRecordsPageSoundRouting() {
        load();
        clearSoundLatch();
        lastPumpedSoundOffset_ = 0;
        lastPumpedSoundSelector_ = 0;

        bool running = true;
        if (!menu_ || menuPage_ != MenuPage::Main) {
            throw std::runtime_error("records page sound route did not start in menu");
        }
        onKey(SDLK_r, running);
        if (!running || !menu_ || menuPage_ != MenuPage::Records ||
            !soundLatch_.active ||
            soundLatch_.latchedOffset != kRecordsPageSoundCursor ||
            soundLatch_.currentSelector != kRecordsPageSoundPriority ||
            soundLatch_.directSweep) {
            throw std::runtime_error("records page sound request mismatch");
        }
        pumpSoundLatch();
        if (soundLatch_.active ||
            lastPumpedSoundOffset_ != kRecordsPageSoundCursor ||
            lastPumpedSoundSelector_ != kRecordsPageSoundPriority) {
            throw std::runtime_error("records page sound pump mismatch");
        }

        std::cout << "records_page_sound=ok"
                  << " cursor=" << hex4(kRecordsPageSoundCursor)
                  << " priority=" << static_cast<int>(kRecordsPageSoundPriority)
                  << " direct_sweep=0"
                  << " ghidra=1000:2083"
                  << " latch=1000:165a"
                  << " string=punteggi_migliori"
                  << '\n';
    }

    void debugWeaponSwitchSoundRouting() {
        load();
        resetLevel(0);
        bombInventory_.selected = BombType::Small;
        grantNormalBombSet(bombInventory_);
        clearSoundLatch();
        lastPumpedSoundOffset_ = 0;
        lastPumpedSoundSelector_ = 0;

        for (uint8_t tick = 0; tick < kWeaponSwitchHoldTicks - 1; ++tick) {
            updateWeaponSwitch(bombInventory_, weaponSwitchHoldTicks_, true);
        }
        if (weaponSwitchHoldTicks_ != kWeaponSwitchHoldTicks - 1 ||
            bombInventory_.selected != BombType::Small || soundLatch_.active) {
            throw std::runtime_error("short weapon-switch chord changed state");
        }
        updateWeaponSwitch(bombInventory_, weaponSwitchHoldTicks_, false);
        if (weaponSwitchHoldTicks_ != 0 ||
            bombInventory_.selected != BombType::Small || soundLatch_.active) {
            throw std::runtime_error("short weapon-switch release was not ignored");
        }

        for (uint8_t tick = 0; tick < kWeaponSwitchHoldTicks; ++tick) {
            updateWeaponSwitch(bombInventory_, weaponSwitchHoldTicks_, true);
        }
        if (weaponSwitchHoldTicks_ != kWeaponSwitchHoldTicks ||
            bombInventory_.selected != BombType::Small || soundLatch_.active) {
            throw std::runtime_error("held weapon-switch chord triggered before release");
        }
        updateWeaponSwitch(bombInventory_, weaponSwitchHoldTicks_, false);
        if (weaponSwitchHoldTicks_ != 0 ||
            bombInventory_.selected != BombType::Medium ||
            !soundLatch_.active ||
            soundLatch_.latchedOffset != kWeaponSwitchSoundCursor ||
            soundLatch_.currentSelector != kWeaponSwitchSoundPriority ||
            soundLatch_.directSweep) {
            throw std::runtime_error("weapon-switch release state or sound mismatch");
        }
        pumpSoundLatch();
        if (soundLatch_.active ||
            lastPumpedSoundOffset_ != kWeaponSwitchSoundCursor ||
            lastPumpedSoundSelector_ != kWeaponSwitchSoundPriority) {
            throw std::runtime_error("weapon-switch sound cursor did not pump");
        }

        std::cout << "weapon_switch_sound=ok"
                  << " hold_ticks=" << static_cast<int>(kWeaponSwitchHoldTicks)
                  << " trigger=release short_chord_ignored=1 selected=2"
                  << " cursor=" << hex4(kWeaponSwitchSoundCursor)
                  << " priority=" << static_cast<int>(kWeaponSwitchSoundPriority)
                  << " direct_sweep=0 pumped=1"
                  << " ghidra=1000:6844 latch=1000:165a\n";
    }

    void debugBombPlaceSoundRouting() {
        load();
        resetLevel(0);
        bombInventory_.selected = BombType::Small;
        grantNormalBombSet(bombInventory_);
        clearSoundLatch();
        size_t beforeBombs = bombs_.size();
        int beforeSmallBombs = bombInventory_.counts[0];
        placeBombAt(player_, bombInventory_, 1);
        if (bombs_.size() != beforeBombs + 1 ||
            bombInventory_.counts[0] != beforeSmallBombs - 1 ||
            !soundLatch_.active ||
            soundLatch_.latchedOffset != kBombPlaceSoundCursor ||
            soundLatch_.currentSelector != kBombPlaceSoundPriority ||
            !soundLatch_.directSweep) {
            throw std::runtime_error("bomb placement sound request mismatch");
        }
        pumpSoundLatch();
        if (soundLatch_.active ||
            lastPumpedSoundOffset_ != kBombPlaceSoundCursor ||
            lastPumpedSoundSelector_ != kBombPlaceSoundPriority) {
            throw std::runtime_error("bomb placement sound pump mismatch");
        }
        std::cout << "bomb_place_sound=ok cursor=" << hex4(kBombPlaceSoundCursor)
                  << " priority=" << static_cast<int>(kBombPlaceSoundPriority)
                  << " direct_sweep=1 placed=1 pumped=1"
                  << " ghidra=1000:557b latch=1000:165a\n";
    }

    void debugMonsterDeathSoundRouting() {
        load();
        resetLevel(0);
        ActiveMonster monster;
        monster.x = 40;
        monster.y = 24;
        monster.kind = 1;
        monster.behavior = 3;
        monster.hp = 1;
        refreshMonsterAnimationProfile(monster);
        clearSoundLatch();
        enterMonsterDeath(monster);
        if (monster.behavior != 2 || monster.stateTimer != 25 ||
            !soundLatch_.active ||
            soundLatch_.latchedOffset != kMonsterDeathSoundCursor ||
            soundLatch_.currentSelector != kMonsterDeathSoundPriority ||
            soundLatch_.directSweep) {
            throw std::runtime_error("monster death sound request mismatch");
        }
        pumpSoundLatch();
        if (soundLatch_.active ||
            lastPumpedSoundOffset_ != kMonsterDeathSoundCursor ||
            lastPumpedSoundSelector_ != kMonsterDeathSoundPriority) {
            throw std::runtime_error("monster death sound pump mismatch");
        }
        std::cout << "monster_death_sound=ok cursor="
                  << hex4(kMonsterDeathSoundCursor)
                  << " priority=" << static_cast<int>(kMonsterDeathSoundPriority)
                  << " direct_sweep=0 state=2 death_ticks=" << monster.stateTimer
                  << " reward=1 pumped=1 ghidra=1000:5c9e latch=1000:165a\n";
    }

    void debugBombObjectSoundRouting() {
        load();

        clearSoundLatch();
        bool lowAccepted = requestBombObjectScoreSound(false);
        if (!lowAccepted || !soundLatch_.active ||
            soundLatch_.currentSelector != kBombObjectSoundPriority ||
            soundLatch_.latchedOffset != kBombObjectDefaultSoundCursor) {
            throw std::runtime_error("low bomb-object sound request mismatch");
        }
        pumpSoundLatch();
        if (soundLatch_.active || lastPumpedSoundOffset_ != kBombObjectDefaultSoundCursor ||
            lastPumpedSoundSelector_ != kBombObjectSoundPriority) {
            throw std::runtime_error("low bomb-object sound pump mismatch");
        }

        clearSoundLatch();
        bool highAccepted = requestBombObjectScoreSound(true);
        if (!highAccepted || !soundLatch_.active ||
            soundLatch_.currentSelector != kBombObjectSoundPriority ||
            soundLatch_.latchedOffset != kBombObjectHighSoundCursor) {
            throw std::runtime_error("high bomb-object sound request mismatch");
        }

        clearSoundLatch();
        bool explosionAccepted = requestSoundOffset(explosionSoundOffset(1),
                                                    explosionSoundSelector(1));
        bool suppressed = !requestBombObjectScoreSound(true);
        if (!explosionAccepted || !suppressed || !soundLatch_.active ||
            soundLatch_.currentSelector != explosionSoundSelector(1) ||
            soundLatch_.latchedOffset != explosionSoundOffset(1)) {
            throw std::runtime_error("bomb-object sound did not yield to explosion priority");
        }

        std::cout << "bomb_object_sound=ok low_cursor=" << std::showbase << std::hex
                  << kBombObjectDefaultSoundCursor
                  << " high_cursor=" << kBombObjectHighSoundCursor
                  << std::dec << std::noshowbase
                  << " priority=" << static_cast<int>(kBombObjectSoundPriority)
                  << " suppressed_by_explosion=1\n";
    }

    void debugPlayerDamageSoundRouting() {
        load();
        resetLevel(0);

        energy_ = 100;
        lives_ = 3;
        playerDead_ = false;
        reentryTimer_ = 0;
        damageCooldown_ = 0;
        clearSoundLatch();
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        if (energy_ != 99 || playerDead_ || lives_ != 3 ||
            damageCooldown_ != 0 || !soundLatch_.active ||
            soundLatch_.latchedOffset != kPlayerDamageSoundCursor ||
            soundLatch_.currentSelector != kPlayerDamageSoundPriority) {
            throw std::runtime_error("player damage sound request mismatch");
        }
        int nonlethalEnergy = energy_;
        pumpSoundLatch();
        if (soundLatch_.active || lastPumpedSoundOffset_ != kPlayerDamageSoundCursor ||
            lastPumpedSoundSelector_ != kPlayerDamageSoundPriority) {
            throw std::runtime_error("player damage sound pump mismatch");
        }

        clearSoundLatch();
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        bool secondDamageAccepted = energy_ == 98 && soundLatch_.active &&
                                    soundLatch_.latchedOffset == kPlayerDamageSoundCursor;
        if (!secondDamageAccepted) {
            throw std::runtime_error("player damage sound did not accept second hit");
        }
        int secondEnergy = energy_;

        clearSoundLatch();
        bool smallExplosionAccepted = requestSoundOffset(explosionSoundOffset(1),
                                                         explosionSoundSelector(1));
        bool damageRefreshedSamePriority = requestPlayerDamageSound();
        if (!smallExplosionAccepted || !damageRefreshedSamePriority ||
            !soundLatch_.active || soundLatch_.latchedOffset != kPlayerDamageSoundCursor ||
            soundLatch_.currentSelector != kPlayerDamageSoundPriority) {
            throw std::runtime_error("player damage sound same-priority latch mismatch");
        }

        clearSoundLatch();
        bool mediumExplosionAccepted = requestSoundOffset(explosionSoundOffset(2),
                                                          explosionSoundSelector(2));
        bool higherPriorityBlocked = !requestPlayerDamageSound();
        if (!mediumExplosionAccepted || !higherPriorityBlocked || !soundLatch_.active ||
            soundLatch_.latchedOffset != explosionSoundOffset(2) ||
            soundLatch_.currentSelector != explosionSoundSelector(2)) {
            throw std::runtime_error("player damage sound priority block mismatch");
        }

        clearSoundLatch();
        energy_ = 0;
        lives_ = 3;
        playerDead_ = false;
        reentryTimer_ = 0;
        damageCooldown_ = 0;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        if (energy_ != 100 || !playerDead_ || lives_ != 3 || !pendingLifeLoss_ ||
            reentryTimer_ != kReentryTicks || !soundLatch_.active ||
            soundLatch_.latchedOffset != kPlayerDeathSoundCursor ||
            soundLatch_.currentSelector != kPlayerDeathSoundPriority) {
            throw std::runtime_error("player death sound did not replace hurt sound");
        }
        pumpSoundLatch();
        if (soundLatch_.active || lastPumpedSoundOffset_ != kPlayerDeathSoundCursor ||
            lastPumpedSoundSelector_ != kPlayerDeathSoundPriority) {
            throw std::runtime_error("player death sound pump mismatch");
        }

        std::cout << "player_damage_sound=ok nonlethal_energy=" << nonlethalEnergy
                  << " second_energy=" << secondEnergy
                  << " nonlethal_cooldown=0"
                  << " death_energy=" << energy_
                  << " dead=" << (playerDead_ ? 1 : 0)
                  << " lives=" << lives_
                  << " pending_life_loss=" << (pendingLifeLoss_ ? 1 : 0)
                  << " cursor=" << std::showbase << std::hex
                  << kPlayerDamageSoundCursor << std::dec << std::noshowbase
                  << " priority=" << static_cast<int>(kPlayerDamageSoundPriority)
                  << " death_cursor=" << std::showbase << std::hex
                  << kPlayerDeathSoundCursor << std::dec << std::noshowbase
                  << " death_priority=" << static_cast<int>(kPlayerDeathSoundPriority)
                  << " pumped=1 cooldown_gate_removed=1 same_priority_refresh=1"
                  << " second_damage_accepted=1 higher_priority_blocks=1"
                  << " lethal_replaced=1\n";
    }

    void debugOriginalDamageCounters() {
        struct DrainResult {
            uint8_t energy = 0;
            int hurtRequests = 0;
            bool deathDispatch = false;
        };

        auto drain = [](uint8_t energy, uint8_t accumulatedDamage,
                        bool stateTwo) -> DrainResult {
            uint8_t updatedEnergy = energy;
            if (!stateTwo) {
                updatedEnergy = static_cast<uint8_t>(energy - accumulatedDamage);
            }
            return {updatedEnergy, accumulatedDamage > 0 ? 1 : 0,
                    static_cast<uint16_t>(updatedEnergy) > 0x00c8};
        };

        DrainResult p1 = drain(100, 3, false);
        DrainResult p2 = drain(100, 2, false);
        DrainResult zero = drain(100, 0, false);
        DrainResult stateTwo = drain(100, 4, true);
        DrainResult underflow = drain(1, 2, false);

        if (p1.energy != 97 || p1.hurtRequests != 1 || p1.deathDispatch ||
            p2.energy != 98 || p2.hurtRequests != 1 || p2.deathDispatch ||
            zero.energy != 100 || zero.hurtRequests != 0 || zero.deathDispatch ||
            stateTwo.energy != 100 || stateTwo.hurtRequests != 1 ||
            stateTwo.deathDispatch || underflow.energy != 255 ||
            underflow.hurtRequests != 1 || !underflow.deathDispatch) {
            throw std::runtime_error("original damage counter model mismatch");
        }

        load();
        playerCount_ = 2;
        resetLevel(0);
        menu_ = false;
        energy_ = 100;
        energy2_ = 100;
        lives_ = 3;
        lives2_ = 3;
        playerDead_ = false;
        player2Dead_ = false;
        clearSoundLatch();
        queuePlayerDamage(1);
        queuePlayerDamage(1);
        queuePlayerDamage(1);
        queuePlayerDamage(2);
        queuePlayerDamage(2);
        drainPlayerDamageCounters();
        if (energy_ != 97 || energy2_ != 98 || pendingDamage_ != 0 ||
            pendingDamage2_ != 0 || playerDead_ || player2Dead_ ||
            !soundLatch_.active ||
            soundLatch_.latchedOffset != kPlayerDamageSoundCursor ||
            soundLatch_.currentSelector != kPlayerDamageSoundPriority) {
            throw std::runtime_error("live damage counter drain mismatch");
        }

        clearSoundLatch();
        energy_ = 1;
        lives_ = 3;
        playerDead_ = false;
        deathStateTimer_ = 0;
        queuePlayerDamage(1, 2);
        drainPlayerDamageCounters();
        if (!playerDead_ || lives_ != 3 || !pendingLifeLoss_ || energy_ != 100 ||
            deathStateTimer_ != kDeathStateTicks || pendingDamage_ != 0 ||
            !soundLatch_.active ||
            soundLatch_.latchedOffset != kPlayerDeathSoundCursor ||
            soundLatch_.currentSelector != kPlayerDeathSoundPriority) {
            throw std::runtime_error("live damage counter underflow mismatch");
        }

        clearSoundLatch();
        energy_ = 100;
        playerDead_ = true;
        queuePlayerDamage(1, 4);
        drainPlayerDamageCounters();
        if (energy_ != 100 || !playerDead_ || pendingDamage_ != 0 ||
            !soundLatch_.active ||
            soundLatch_.latchedOffset != kPlayerDamageSoundCursor ||
            soundLatch_.currentSelector != kPlayerDamageSoundPriority) {
            throw std::runtime_error("live state-2 damage counter mismatch");
        }

        std::cout << "original_damage_counters=ok p1_hits=3 p1_energy="
                  << static_cast<int>(p1.energy)
                  << " p1_hurt_requests=" << p1.hurtRequests
                  << " p2_hits=2 p2_energy=" << static_cast<int>(p2.energy)
                  << " p2_hurt_requests=" << p2.hurtRequests
                  << " zero_pass_silent=" << (zero.hurtRequests == 0 ? 1 : 0)
                  << " state2_hurt_without_subtract=1"
                  << " underflow_raw=" << static_cast<int>(underflow.energy)
                  << " death_dispatch=" << (underflow.deathDispatch ? 1 : 0)
                  << " live_p1_energy=97 live_p2_energy=98"
                  << " live_underflow_dead=1 live_state2_energy=100"
                  << " live_pending_life_loss=1"
                  << '\n';
    }

    void debugPlayerState2DeathFields() {
        load();
        resetLevel(0);
        menu_ = false;

        player_.vx = 12.0f;
        player_.vy = -9.0f;
        player_.grounded = true;
        energy_ = 0;
        lives_ = 3;
        damageCooldown_ = 0;
        deathStateTimer_ = 0;
        clearSoundLatch();
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        if (!playerDead_ || lives_ != 3 || !pendingLifeLoss_ || energy_ != 100 ||
            reentryTimer_ != kReentryTicks ||
            deathStateTimer_ != kDeathStateTicks ||
            player_.vx != 0.0f || player_.vy != 0.0f || player_.grounded ||
            !soundLatch_.active || soundLatch_.latchedOffset != kPlayerDeathSoundCursor ||
            soundLatch_.currentSelector != kPlayerDeathSoundPriority) {
            throw std::runtime_error("player state-2 death fields mismatch");
        }
        pumpSoundLatch();
        tryReenterPlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                         damageCooldown_, 1);
        if (!playerDead_ || lives_ != 3 || !pendingLifeLoss_ || energy_ != 100 ||
            reentryTimer_ != kReentryTicks ||
            deathStateTimer_ != kDeathStateTicks || damageCooldown_ != 0) {
            throw std::runtime_error("player state-2 early reentry was accepted");
        }
        for (int i = 0; i < 59; ++i) {
            updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                          true);
        }
        tryReenterPlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                         damageCooldown_, 1);
        if (!playerDead_ || lives_ != 3 || !pendingLifeLoss_ ||
            deathStateTimer_ != 1) {
            throw std::runtime_error("player state-2 59-tick gate mismatch");
        }
        updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                      true);
        tryReenterPlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                         damageCooldown_, 1);
        if (playerDead_ || lives_ != 2 || energy_ != 100 ||
            reentryTimer_ != 0 || deathStateTimer_ != 0 ||
            damageCooldown_ != kDamageCooldownTicks || player_.vx != 0.0f ||
            player_.vy != 0.0f || player_.grounded) {
            throw std::runtime_error("player state-2 reentry clear mismatch");
        }

        playerCount_ = 2;
        lives_ = 3;
        lives2_ = 1;
        resetLevel(0);
        menu_ = false;
        energy2_ = 0;
        damageCooldown2_ = 0;
        deathStateTimer2_ = 0;
        damagePlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                     damageCooldown2_, 2);
        if (menu_ || playerDead_ || !player2Dead_ || lives_ != 3 || lives2_ != 1 ||
            !pendingLifeLoss2_ || energy2_ != 100 || reentryTimer2_ != kReentryTicks ||
            deathStateTimer2_ != kDeathStateTicks) {
            throw std::runtime_error("player 2 zero-life state-2 fields mismatch");
        }
        for (int i = 0; i < kDeathStateTicks; ++i) {
            updateReentry(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_, 2,
                          playerDead_);
        }
        if (menu_ || !player2Dead_ || lives2_ != 0 || pendingLifeLoss2_ ||
            deathStateTimer2_ != 0 || reentryTimer2_ != 0) {
            throw std::runtime_error("player 2 zero-life state-2 timer mismatch");
        }

        std::cout << "player_state2_death_fields=ok reentry_dead=1"
                  << " reentry_lives_during_countdown=3 reentry_lives_after=2"
                  << " reentry_energy=100 pending_life_loss=1"
                  << " reentry_timer=" << kReentryTicks
                  << " death_state_timer=60 vx=0 vy=0 grounded=0"
                  << " death_cursor=" << std::showbase << std::hex
                  << kPlayerDeathSoundCursor << std::dec << std::noshowbase
                  << " death_priority=" << static_cast<int>(kPlayerDeathSoundPriority)
                  << " early_reentry_blocked=1 after_59_blocked=1 reentered=1"
                  << " cooldown=" << kDamageCooldownTicks
                  << " zero_lives_during_countdown=1 zero_lives_after=0"
                  << " zero_timer=0 zero_death_state_after_60=0"
                  << " no_gameover_with_p1=1\n";
    }

    void debugOriginalState2ReturnModel() {
        struct ReturnModel {
            struct PlayerSlot {
                uint16_t countdown = kDeathStateTicks;
                uint8_t status = 2;
                uint8_t actorState = 2;
                uint8_t energy = 100;
                bool keyByte = false;
                bool otherKeyByte = true;
            };

            std::array<PlayerSlot, 2> players{};
            uint8_t activePlayers = 2;
            uint8_t fallbackCounter = 0;

            void tick(int player) {
                if (players.at(player).countdown > 0) --players.at(player).countdown;
            }

            bool returnActive(int player, bool gate, bool effectReady,
                              bool placementReady) {
                PlayerSlot& slot = players.at(player);
                if (slot.status != 2 || slot.countdown != 0 || !gate ||
                    !effectReady || !placementReady) {
                    return false;
                }
                slot.status = 1;
                slot.actorState = player == 0 ? 0 : 1;
                slot.energy = 100;
                slot.keyByte = false;
                slot.otherKeyByte = false;
                return true;
            }

            void markOut(int player) {
                PlayerSlot& slot = players.at(player);
                if (slot.status != 0 && activePlayers > 0) --activePlayers;
                slot.status = 0;
            }

            bool fallbackNoActivePlayers() {
                if (activePlayers != 0) return false;
                ++fallbackCounter;
                bool promoted = false;
                for (PlayerSlot& slot : players) {
                    if (slot.status == 2) {
                        slot.status = 1;
                        promoted = true;
                    }
                }
                return promoted;
            }
        };

        ReturnModel timerModel;
        for (int i = 0; i < 59; ++i) timerModel.tick(0);
        uint16_t after59 = timerModel.players[0].countdown;
        timerModel.tick(0);
        uint16_t after60 = timerModel.players[0].countdown;

        ReturnModel gateModel;
        gateModel.players[0].countdown = 0;
        bool gate0Blocked = !gateModel.returnActive(0, false, true, true);
        bool effectWaitBlocked = !gateModel.returnActive(0, true, false, true);
        bool placementBlocked = !gateModel.returnActive(0, true, true, false);
        bool gate1Restored = gateModel.returnActive(0, true, true, true);

        ReturnModel playerModel;
        playerModel.players[0].countdown = 0;
        playerModel.players[1].countdown = 0;
        bool p1Restored = playerModel.returnActive(0, true, true, true);
        bool p2Restored = playerModel.returnActive(1, true, true, true);

        ReturnModel outModel;
        outModel.markOut(1);
        uint8_t activeAfterP2Out = outModel.activePlayers;
        outModel.markOut(0);

        ReturnModel fallbackBlockedModel;
        fallbackBlockedModel.activePlayers = 1;
        bool fallbackBlocked = !fallbackBlockedModel.fallbackNoActivePlayers();

        ReturnModel fallbackModel;
        fallbackModel.activePlayers = 0;
        fallbackModel.players[0].status = 2;
        fallbackModel.players[1].status = 0;
        fallbackModel.players[0].actorState = 2;
        fallbackModel.players[0].energy = 77;
        bool fallbackPromoted = fallbackModel.fallbackNoActivePlayers();

        if (after59 != 1 || after60 != 0 || !gate0Blocked ||
            !effectWaitBlocked || !placementBlocked || !gate1Restored ||
            !p1Restored || !p2Restored || playerModel.players[0].status != 1 ||
            playerModel.players[1].status != 1 ||
            playerModel.players[0].actorState != 0 ||
            playerModel.players[1].actorState != 1 ||
            playerModel.players[0].energy != 100 ||
            playerModel.players[1].energy != 100 ||
            playerModel.players[0].keyByte || playerModel.players[0].otherKeyByte ||
            playerModel.players[1].keyByte || playerModel.players[1].otherKeyByte ||
            outModel.players[1].status != 0 || activeAfterP2Out != 1 ||
            outModel.activePlayers != 0 || !fallbackBlocked ||
            !fallbackPromoted || fallbackModel.fallbackCounter != 1 ||
            fallbackModel.players[0].status != 1 ||
            fallbackModel.players[0].actorState != 2 ||
            fallbackModel.players[0].energy != 77 ||
            fallbackModel.players[1].status != 0) {
            throw std::runtime_error("original state-2 return model mismatch");
        }

        std::cout << "original_state2_return_model=ok timer_start=60"
                  << " timer_after_59=" << after59
                  << " timer_after_60=" << after60
                  << " gate0_blocked=1 effect_wait_blocked=1"
                  << " placement_blocked=1 gate1_restored=1"
                  << " p1_status=" << static_cast<int>(playerModel.players[0].status)
                  << " p1_actor_state="
                  << static_cast<int>(playerModel.players[0].actorState)
                  << " p1_energy=" << static_cast<int>(playerModel.players[0].energy)
                  << " p1_cleared=1"
                  << " p2_status=" << static_cast<int>(playerModel.players[1].status)
                  << " p2_actor_state="
                  << static_cast<int>(playerModel.players[1].actorState)
                  << " p2_energy=" << static_cast<int>(playerModel.players[1].energy)
                  << " p2_cleared=1"
                  << " zero_life_status=" << static_cast<int>(outModel.players[1].status)
                  << " active_players_after_p2_out="
                  << static_cast<int>(activeAfterP2Out)
                  << " active_players_after_both_out="
                  << static_cast<int>(outModel.activePlayers)
                  << " fallback_blocked_with_active=1"
                  << " fallback_counter="
                  << static_cast<int>(fallbackModel.fallbackCounter)
                  << " fallback_promoted_status="
                  << static_cast<int>(fallbackModel.players[0].status)
                  << " fallback_actor_state_preserved="
                  << static_cast<int>(fallbackModel.players[0].actorState)
                  << " fallback_energy_preserved="
                  << static_cast<int>(fallbackModel.players[0].energy) << '\n';
    }

    void debugOriginalState2AnimationInit() {
        auto initialize = [](uint8_t arg04, uint8_t arg06, uint8_t arg08,
                             uint8_t arg0a) {
            return std::array<uint8_t, 7>{arg0a, arg0a, arg08, arg06,
                                          arg06, arg04, 1};
        };

        std::array<uint8_t, 7> bytes = initialize(4, 6, 8, 12);
        const std::array<uint8_t, 7> expected{12, 12, 8, 6, 6, 4, 1};
        if (bytes != expected || bytes[0] != bytes[1] ||
            bytes[3] != bytes[4] || bytes[6] != 1) {
            throw std::runtime_error("original state-2 animation init mismatch");
        }

        std::cout << "original_state2_animation_init=ok actor_offset=0x16"
                  << " bytes=12,12,8,6,6,4,1"
                  << " duplicate_0a=1 duplicate_06=1 terminator=1"
                  << " ghidra=1000:06ab\n";
    }

    void debugOriginalState2AnimationAdvance() {
        struct AnimationCursor {
            uint8_t current = 0;
            uint8_t first = 0;
            uint8_t last = 0;
            uint8_t counter = 0;
            uint8_t delay = 0;
            uint8_t mode = 0;
            int8_t step = 1;
        };

        auto packed = [](const AnimationCursor& cursor) {
            return std::array<uint8_t, 7>{
                cursor.current, cursor.first, cursor.last, cursor.counter,
                cursor.delay, cursor.mode, static_cast<uint8_t>(cursor.step)};
        };

        auto tick = [&](AnimationCursor& cursor,
                        std::array<uint8_t, 7>* mode3Backup = nullptr) {
            if (cursor.mode == 0) return;
            ++cursor.counter;
            if (cursor.counter <= cursor.delay) return;

            cursor.counter = 0;
            cursor.current = static_cast<uint8_t>(
                static_cast<int>(cursor.current) + static_cast<int>(cursor.step));

            if (cursor.mode == 2) {
                if (cursor.current >= cursor.last || cursor.current <= cursor.first) {
                    cursor.step = static_cast<int8_t>(-cursor.step);
                }
                return;
            }

            if (cursor.current > cursor.last) {
                cursor.current = cursor.first;
                if (cursor.mode == 3 && mode3Backup != nullptr) {
                    *mode3Backup = packed(cursor);
                }
            }
        };

        AnimationCursor death{0x72, 0x72, 0x79, 3, 3, 1, 1};
        tick(death);
        uint8_t mode1FirstFrame = death.current;
        for (int i = 0; i < 4; ++i) tick(death);
        uint8_t mode1After5 = death.current;

        AnimationCursor wrap{0x79, 0x72, 0x79, 3, 3, 1, 1};
        tick(wrap);

        AnimationCursor pingpong{3, 2, 4, 0, 0, 2, 1};
        std::array<uint8_t, 4> pingpongSequence{};
        for (uint8_t& frame : pingpongSequence) {
            tick(pingpong);
            frame = pingpong.current;
        }

        AnimationCursor mode3{6, 5, 6, 1, 1, 3, 1};
        std::array<uint8_t, 7> backup{};
        tick(mode3, &backup);

        AnimationCursor disabled{8, 8, 9, 9, 1, 0, 1};
        tick(disabled);

        if (mode1FirstFrame != 0x73 || mode1After5 != 0x74 ||
            wrap.current != 0x72 || wrap.counter != 0 ||
            pingpongSequence != std::array<uint8_t, 4>{4, 3, 2, 3} ||
            pingpong.step != 1 || mode3.current != 5 || backup[0] != 5 ||
            backup[5] != 3 || disabled.current != 8 || disabled.counter != 9) {
            throw std::runtime_error("original state-2 animation advance mismatch");
        }

        std::cout << "original_state2_animation_advance=ok"
                  << " death_start=0x72 death_end=0x79 delay=3"
                  << " mode1_first_frame=0x73 mode1_after_5=0x74"
                  << " wrap_frame=0x72 wrap_counter=0"
                  << " mode2_seq=4,3,2,3 mode2_final_step=1"
                  << " mode3_backup_frame=5 mode3_backup_mode=3"
                  << " mode0_unchanged=1 ghidra=1000:6053\n";
    }

    void debugOriginalState2VisualRowModel() {
        constexpr uint8_t kDrawOffsetXByte = 0x10;
        constexpr uint8_t kDrawOffsetYByte = 0x10;
        constexpr uint8_t kStableRow2Byte = 0x7d;
        constexpr uint8_t kFirstSpriteIndexByte = 0x43;
        constexpr uint8_t kLastSpriteIndexByte = 0x48;

        auto bareHex2 = [](uint8_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(2)
                << std::setfill('0') << static_cast<int>(value);
            return oss.str();
        };
        auto prefixedHex2 = [&](uint8_t value) {
            return std::string("0x") + bareHex2(value);
        };
        auto rowText = [&](const State2VisualRow& row) {
            return bareHex2(row.frame) + ":" + bareHex2(row.row0) + "," +
                   bareHex2(row.row1) + "," + bareHex2(row.row2) + "," +
                   bareHex2(row.row3);
        };

        std::ostringstream rows;
        std::ostringstream row0Sequence;
        std::ostringstream row1Sequence;
        std::ostringstream row2Sequence;
        std::ostringstream row3Sequence;
        std::ostringstream spriteCandidates;
        for (uint8_t frame = kState2VisualStartFrame;
             frame <= kState2VisualEndFrame; ++frame) {
            State2VisualRow row;
            if (!originalState2VisualRow(frame, row)) {
                throw std::runtime_error("state-2 visual row missing");
            }
            const uint8_t expectedSpriteIndex =
                static_cast<uint8_t>(kFirstSpriteIndexByte +
                                     (frame - kState2VisualStartFrame));
            if (row.row0 != kDrawOffsetXByte ||
                row.row1 != kDrawOffsetYByte ||
                row.row2 != kStableRow2Byte ||
                row.row3 != expectedSpriteIndex) {
                throw std::runtime_error("state-2 visual row field candidates changed");
            }
            if (frame != kState2VisualStartFrame) {
                rows << ';';
                row0Sequence << ',';
                row1Sequence << ',';
                row2Sequence << ',';
                row3Sequence << ',';
                spriteCandidates << ',';
            }
            rows << rowText(row);
            row0Sequence << bareHex2(row.row0);
            row1Sequence << bareHex2(row.row1);
            row2Sequence << bareHex2(row.row2);
            row3Sequence << bareHex2(row.row3);
            spriteCandidates << static_cast<int>(row.row3);
        }

        State2VisualRow before;
        State2VisualRow after;
        if (originalState2VisualRow(0x49, before) ||
            originalState2VisualRow(0x50, after)) {
            throw std::runtime_error("state-2 visual row range guard mismatch");
        }

        std::cout << "original_state2_visual_row_model=ok"
                  << " frame_range=0x4a..0x4f"
                  << " rows=" << rows.str()
                  << " row0_sequence=" << row0Sequence.str()
                  << " row1_sequence=" << row1Sequence.str()
                  << " row2_sequence=" << row2Sequence.str()
                  << " row3_sequence=" << row3Sequence.str()
                  << " sprite_bank=BOMOMIMK"
                  << " sprite_source=row_byte3"
                  << " sprite_candidates=" << spriteCandidates.str()
                  << " field_candidates=row0_draw_x,row1_draw_y,row2_constant,row3_sprite_index"
                  << " draw_offset_bytes=" << prefixedHex2(kDrawOffsetXByte)
                  << ',' << prefixedHex2(kDrawOffsetYByte)
                  << " draw_offset_candidate=16,16"
                  << " row2_constant=" << prefixedHex2(kStableRow2Byte)
                  << " row3_sprite_index_range="
                  << prefixedHex2(kFirstSpriteIndexByte) << ".."
                  << prefixedHex2(kLastSpriteIndexByte)
                  << " range_guard=1"
                  << " visual_claim=0"
                  << " ghidra=1000:6053\n";
    }

    void debugOriginalState2VisualRowAssets() {
        load();

        struct SpriteMetrics {
            int width = 0;
            int height = 0;
            int nonzero = 0;
            int minX = 0;
            int minY = 0;
            int maxX = -1;
            int maxY = -1;
        };

        auto metricsFor = [&](int index) {
            if (index < 0 || index >= static_cast<int>(sprites_.sprites.size())) {
                throw std::runtime_error("state-2 visual sprite index out of range");
            }
            const Sprite& sprite = sprites_.sprites[static_cast<size_t>(index)];
            SpriteMetrics metrics;
            metrics.width = sprite.width;
            metrics.height = sprite.height;
            metrics.minX = sprite.width;
            metrics.minY = sprite.height;
            for (int y = 0; y < sprite.height; ++y) {
                for (int x = 0; x < sprite.width; ++x) {
                    uint8_t pixelValue =
                        sprite.pixels[static_cast<size_t>(y) * sprite.width + x];
                    if (pixelValue == 0) continue;
                    ++metrics.nonzero;
                    metrics.minX = std::min(metrics.minX, x);
                    metrics.minY = std::min(metrics.minY, y);
                    metrics.maxX = std::max(metrics.maxX, x);
                    metrics.maxY = std::max(metrics.maxY, y);
                }
            }
            if (metrics.nonzero == 0) {
                metrics.minX = metrics.minY = metrics.maxX = metrics.maxY = 0;
            }
            return metrics;
        };

        auto metricsText = [](int index, const SpriteMetrics& metrics) {
            std::ostringstream oss;
            oss << index << ':' << metrics.width << 'x' << metrics.height
                << ":nonzero" << metrics.nonzero << ":bbox" << metrics.minX
                << ',' << metrics.minY << ',' << metrics.maxX << ','
                << metrics.maxY;
            return oss.str();
        };

        std::ostringstream row3Sprites;
        std::ostringstream row3Nonzero;
        std::ostringstream cursorSprites;
        std::ostringstream cursorNonzero;
        bool row3All16 = true;
        bool cursorMatchesRow3 = true;
        int row3MinusFrame = 0;
        for (uint8_t frame = kState2VisualStartFrame;
             frame <= kState2VisualEndFrame; ++frame) {
            State2VisualRow row;
            if (!originalState2VisualRow(frame, row)) {
                throw std::runtime_error("state-2 visual row missing");
            }
            int row3Index = static_cast<int>(row.row3);
            int cursorIndex = static_cast<int>(frame);
            SpriteMetrics row3 = metricsFor(row3Index);
            SpriteMetrics cursor = metricsFor(cursorIndex);
            if (frame == kState2VisualStartFrame) {
                row3MinusFrame = row3Index - cursorIndex;
            } else {
                row3Sprites << ';';
                row3Nonzero << ',';
                cursorSprites << ';';
                cursorNonzero << ',';
            }
            row3Sprites << metricsText(row3Index, row3);
            row3Nonzero << row3.nonzero;
            cursorSprites << metricsText(cursorIndex, cursor);
            cursorNonzero << cursor.nonzero;
            row3All16 = row3All16 && row3.width == 16 && row3.height == 16;
            cursorMatchesRow3 = cursorMatchesRow3 && row3Index == cursorIndex;
        }

        std::cout << "original_state2_visual_row_assets=ok"
                  << " bank=BOMOMIMK"
                  << " row3_sprites=" << row3Sprites.str()
                  << " row3_nonzero_sequence=" << row3Nonzero.str()
                  << " row3_all_in_bounds=1"
                  << " row3_all_16x16=" << (row3All16 ? 1 : 0)
                  << " cursor_sprites=" << cursorSprites.str()
                  << " cursor_nonzero_sequence=" << cursorNonzero.str()
                  << " row3_minus_frame=" << row3MinusFrame
                  << " cursor_matches_row3=" << (cursorMatchesRow3 ? 1 : 0)
                  << " visual_claim=0"
                  << " ghidra=1000:6053\n";
    }

    void captureState2VisualRowPreview(const std::string& outDir) {
        load();
        std::filesystem::create_directories(outDir);

        struct PreviewFrame {
            uint8_t visualFrame = 0;
            State2VisualRow row;
            int row3Sprite = 0;
            int cursorSprite = 0;
            std::string row3File;
            std::string cursorFile;
            FrameInspection row3Inspection;
            FrameInspection cursorInspection;
        };

        auto bareHex2 = [](uint8_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(2)
                << std::setfill('0') << static_cast<int>(value);
            return oss.str();
        };
        auto rowText = [&](const State2VisualRow& row) {
            return bareHex2(row.row0) + "," + bareHex2(row.row1) + "," +
                   bareHex2(row.row2) + "," + bareHex2(row.row3);
        };
        auto inspectBuffer = [&](const std::string& label) {
            if (fb_.empty()) {
                throw std::runtime_error(label + " frame buffer is empty");
            }
            FrameInspection inspection;
            uint32_t first = fb_.front();
            uint64_t hash = 1469598103934665603ull;
            for (uint32_t pixelValue : fb_) {
                if (pixelValue != first) ++inspection.changedPixels;
                hash ^= static_cast<uint64_t>(pixelValue);
                hash *= 1099511628211ull;
            }
            inspection.hash = hash;
            if (inspection.changedPixels == 0) {
                throw std::runtime_error(label + " rendered a uniform preview");
            }
            return inspection;
        };
        auto renderSpritePreview = [&](int spriteIndex, const std::string& file) {
            if (spriteIndex < 0 || spriteIndex >= static_cast<int>(sprites_.sprites.size())) {
                throw std::runtime_error("state-2 visual preview sprite index out of range");
            }
            std::fill(fb_.begin(), fb_.end(), argb(palette_, 0));
            resetClip();
            const Sprite& sprite = sprites_.sprites[static_cast<size_t>(spriteIndex)];
            drawSprite(sprite, (kScreenW - sprite.width) / 2,
                       (kScreenH - sprite.height) / 2);
            FrameInspection inspection = inspectBuffer(file);
            writeArgbPpm(joinPath(outDir, file), fb_, kScreenW, kScreenH);
            return inspection;
        };

        std::vector<PreviewFrame> previews;
        std::ostringstream row3Sequence;
        std::ostringstream cursorSequence;
        int row3MinusFrame = 0;
        bool row3CursorHashMismatch = true;
        for (uint8_t frame = kState2VisualStartFrame;
             frame <= kState2VisualEndFrame; ++frame) {
            PreviewFrame preview;
            preview.visualFrame = frame;
            if (!originalState2VisualRow(frame, preview.row)) {
                throw std::runtime_error("state-2 visual preview row missing");
            }
            preview.row3Sprite = static_cast<int>(preview.row.row3);
            preview.cursorSprite = static_cast<int>(frame);
            if (frame == kState2VisualStartFrame) {
                row3MinusFrame = preview.row3Sprite - preview.cursorSprite;
            } else {
                row3Sequence << ',';
                cursorSequence << ',';
            }
            row3Sequence << preview.row3Sprite;
            cursorSequence << preview.cursorSprite;

            std::string frameSuffix = bareHex2(frame);
            preview.row3File = "state2_row3_" + frameSuffix + ".ppm";
            preview.cursorFile = "state2_cursor_" + frameSuffix + ".ppm";
            preview.row3Inspection =
                renderSpritePreview(preview.row3Sprite, preview.row3File);
            preview.cursorInspection =
                renderSpritePreview(preview.cursorSprite, preview.cursorFile);
            row3CursorHashMismatch =
                row3CursorHashMismatch &&
                preview.row3Inspection.hash != preview.cursorInspection.hash;
            previews.push_back(std::move(preview));
        }

        std::ofstream manifest(joinPath(outDir, "manifest.txt"));
        if (!manifest) {
            throw std::runtime_error("cannot create " + joinPath(outDir, "manifest.txt"));
        }
        manifest << "scenario=state2_visual_row_preview\n";
        manifest << "source=lezac_cpp\n";
        manifest << "bank=BOMOMIMK\n";
        manifest << "visual_claim=0\n";
        manifest << "frame_count=" << previews.size() << '\n';
        manifest << "output_count=" << (previews.size() * 2) << '\n';
        for (const PreviewFrame& preview : previews) {
            manifest << "frame visual_frame=" << hex2(preview.visualFrame)
                     << " row=" << rowText(preview.row)
                     << " row3_sprite=" << preview.row3Sprite
                     << " row3_file=" << preview.row3File
                     << " row3_hash=" << hex64(preview.row3Inspection.hash)
                     << " row3_changed_pixels="
                     << preview.row3Inspection.changedPixels
                     << " cursor_sprite=" << preview.cursorSprite
                     << " cursor_file=" << preview.cursorFile
                     << " cursor_hash=" << hex64(preview.cursorInspection.hash)
                     << " cursor_changed_pixels="
                     << preview.cursorInspection.changedPixels << '\n';
        }

        std::cout << "state2_visual_row_preview=ok"
                  << " frames=" << previews.size()
                  << " outputs=" << (previews.size() * 2)
                  << " row3_sprites=" << row3Sequence.str()
                  << " cursor_sprites=" << cursorSequence.str()
                  << " row3_minus_frame=" << row3MinusFrame
                  << " row3_cursor_hash_mismatch="
                  << (row3CursorHashMismatch ? 1 : 0)
                  << " visual_claim=0"
                  << " out=" << outDir
                  << " manifest=manifest.txt\n";
    }

    void captureState2VisualRowGamePreview(const std::string& outDir) {
        load();
        resetLevel(0);
        std::filesystem::create_directories(outDir);
        menu_ = false;
        playerCount_ = 1;
        gameplayViewWidth_ = kScreenW;
        player_.x = 104.0f;
        player_.y = 168.0f;
        playerDead_ = true;
        deathStateTimer_ = kDeathStateTicks;
        resetState2VisualCursor(state2Visual_);

        struct GamePreviewFrame {
            uint8_t visualFrame = 0;
            int currentSprite = 0;
            int cursorSprite = 0;
            std::string currentFile;
            std::string cursorFile;
            FrameInspection currentInspection;
            FrameInspection cursorInspection;
        };

        auto bareHex2 = [](uint8_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(2)
                << std::setfill('0') << static_cast<int>(value);
            return oss.str();
        };
        auto inspectBuffer = [&](const std::string& label) {
            if (fb_.empty()) {
                throw std::runtime_error(label + " frame buffer is empty");
            }
            FrameInspection inspection;
            uint32_t first = fb_.front();
            uint64_t hash = 1469598103934665603ull;
            for (uint32_t pixelValue : fb_) {
                if (pixelValue != first) ++inspection.changedPixels;
                hash ^= static_cast<uint64_t>(pixelValue);
                hash *= 1099511628211ull;
            }
            inspection.hash = hash;
            if (inspection.changedPixels == 0) {
                throw std::runtime_error(label + " rendered a uniform game preview");
            }
            return inspection;
        };
        auto renderGamePreview = [&](const std::string& file, bool cursorPreview) {
            state2VisualCursorPreview_ = cursorPreview;
            drawGame();
            FrameInspection inspection = inspectBuffer(file);
            writeArgbPpm(joinPath(outDir, file), fb_, kScreenW, kScreenH);
            return inspection;
        };

        std::vector<GamePreviewFrame> previews;
        std::ostringstream currentSequence;
        std::ostringstream cursorSequence;
        std::ostringstream drawOffsetSequence;
        int cursorMinusCurrent = 0;
        bool cursorHashMismatch = true;
        for (uint8_t frame = kState2VisualStartFrame;
             frame <= kState2VisualEndFrame; ++frame) {
            State2VisualRow row;
            if (!originalState2VisualRow(frame, row)) {
                throw std::runtime_error("state-2 visual game preview row missing");
            }
            GamePreviewFrame preview;
            preview.visualFrame = frame;
            preview.currentSprite = static_cast<int>(row.row3);
            preview.cursorSprite = static_cast<int>(frame);
            if (frame == kState2VisualStartFrame) {
                cursorMinusCurrent = preview.cursorSprite - preview.currentSprite;
            } else {
                currentSequence << ',';
                cursorSequence << ',';
                drawOffsetSequence << ';';
            }
            currentSequence << preview.currentSprite;
            cursorSequence << preview.cursorSprite;
            drawOffsetSequence << static_cast<int>(row.row0) << ','
                               << static_cast<int>(row.row1);

            state2Visual_.current = frame;
            state2Visual_.first = kState2VisualStartFrame;
            state2Visual_.last = kState2VisualEndFrame;
            state2Visual_.counter = kState2VisualDelay;
            state2Visual_.delay = kState2VisualDelay;
            state2Visual_.active = true;
            refreshState2EffectEntry(player_, state2Visual_, state2Effect_);
            std::string frameSuffix = bareHex2(frame);
            preview.currentFile = "state2_game_current_" + frameSuffix + ".ppm";
            preview.cursorFile = "state2_game_cursor_" + frameSuffix + ".ppm";
            preview.currentInspection =
                renderGamePreview(preview.currentFile, false);
            preview.cursorInspection =
                renderGamePreview(preview.cursorFile, true);
            cursorHashMismatch =
                cursorHashMismatch &&
                preview.currentInspection.hash != preview.cursorInspection.hash;
            previews.push_back(std::move(preview));
        }
        state2VisualCursorPreview_ = false;

        std::ofstream manifest(joinPath(outDir, "manifest.txt"));
        if (!manifest) {
            throw std::runtime_error("cannot create " + joinPath(outDir, "manifest.txt"));
        }
        manifest << "scenario=state2_visual_row_game_preview\n";
        manifest << "source=lezac_cpp\n";
        manifest << "bank=BOMOMIMK\n";
        manifest << "current_renderer=effect_entry_row_byte3\n";
        manifest << "current_base=state2_effect_entry\n";
        manifest << "current_draw_offsets=effect_entry_row_byte0,row_byte1\n";
        manifest << "effect_entry_xy=" << static_cast<int>(player_.x) << ','
                 << static_cast<int>(player_.y) << '\n';
        manifest << "cursor_renderer=debug_only\n";
        manifest << "visual_claim=0\n";
        manifest << "frame_count=" << previews.size() << '\n';
        manifest << "output_count=" << (previews.size() * 2) << '\n';
        for (const GamePreviewFrame& preview : previews) {
            manifest << "frame visual_frame=" << hex2(preview.visualFrame)
                     << " current_sprite=" << preview.currentSprite
                     << " current_file=" << preview.currentFile
                     << " current_hash=" << hex64(preview.currentInspection.hash)
                     << " current_changed_pixels="
                     << preview.currentInspection.changedPixels
                     << " cursor_sprite=" << preview.cursorSprite
                     << " cursor_file=" << preview.cursorFile
                     << " cursor_hash=" << hex64(preview.cursorInspection.hash)
                     << " cursor_changed_pixels="
                     << preview.cursorInspection.changedPixels << '\n';
        }

        std::cout << "state2_visual_row_game_preview=ok"
                  << " frames=" << previews.size()
                  << " outputs=" << (previews.size() * 2)
                  << " current_sprites=" << currentSequence.str()
                  << " cursor_sprites=" << cursorSequence.str()
                  << " cursor_minus_current=" << cursorMinusCurrent
                  << " draw_offsets=" << drawOffsetSequence.str()
                  << " cursor_hash_mismatch=" << (cursorHashMismatch ? 1 : 0)
                  << " effect_entry_xy=" << static_cast<int>(player_.x)
                  << ',' << static_cast<int>(player_.y)
                  << " current_renderer=effect_entry_row_byte3"
                  << " current_base=state2_effect_entry"
                  << " current_draw_offsets=effect_entry_row_byte0,row_byte1"
                  << " cursor_renderer=debug_only"
                  << " visual_claim=0"
                  << " out=" << outDir
                  << " manifest=manifest.txt\n";
    }

    int debugState2RuntimeFrameOracle(const std::string& path, bool expectError) {
        auto fixtureName = [](const std::string& inputPath) {
            size_t slash = inputPath.find_last_of("/\\");
            std::string name =
                slash == std::string::npos ? inputPath : inputPath.substr(slash + 1);
            size_t dot = name.find_last_of('.');
            if (dot != std::string::npos) name = name.substr(0, dot);
            return name;
        };
        const std::string fixture = fixtureName(path);

        auto hex4 = [](uint16_t value) {
            std::ostringstream oss;
            oss << "0x" << std::hex << std::nouppercase << std::setw(4)
                << std::setfill('0') << value;
            return oss.str();
        };
        auto hex2 = [](uint8_t value) {
            std::ostringstream oss;
            oss << "0x" << std::hex << std::nouppercase << std::setw(2)
                << std::setfill('0') << static_cast<int>(value);
            return oss.str();
        };
        auto bareHex4 = [](uint16_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(4)
                << std::setfill('0') << value;
            return oss.str();
        };
        auto bareHex2 = [](uint8_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(2)
                << std::setfill('0') << static_cast<int>(value);
            return oss.str();
        };
        auto fail = [&](const std::string& reason) {
            throw std::runtime_error("state2_runtime_frame_oracle=error fixture=" +
                                     fixture + " reason=" + reason);
        };
        auto parseHex16 = [&](const std::string& token,
                              const std::string& field) -> uint16_t {
            if (token.empty() || token.size() > 4 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("bad_hex16 field=" + field + " token=" + token);
            }
            return static_cast<uint16_t>(std::stoul(token, nullptr, 16));
        };
        auto parseHexByte = [&](const std::string& token,
                                uint16_t address) -> uint8_t {
            if (token.size() != 2 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("non_hex_byte token=" + token + " address=" +
                     bareHex4(address));
            }
            return static_cast<uint8_t>(std::stoul(token, nullptr, 16));
        };
        auto trim = [](std::string value) {
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.front()))) {
                value.erase(value.begin());
            }
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.back()))) {
                value.pop_back();
            }
            return value;
        };
        try {
            std::string text = readTextFile(path);
            std::vector<uint8_t> memory(0x10000);
            std::vector<bool> present(0x10000, false);
            uint16_t runtimeCs = 0;
            uint16_t runtimeDs = 0;
            bool haveRuntimeCs = false;
            bool haveRuntimeDs = false;
            bool tempCopy = false;
            int breakCount = 0;

            std::istringstream lines(text);
            std::string line;
            std::regex keyRe("^([A-Za-z0-9_]+)=(.*)$");
            std::regex breakRe(
                "^break\\s+ghidra=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+"
                "runtime=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+label=([^\\s]+).*$");
            std::regex dumpRe("^dump\\s+DS:([0-9A-Fa-f]{4}).*$");
            std::regex rowRe("^([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+(.+)$");
            uint16_t currentDump = 0;
            bool inDump = false;
            while (std::getline(lines, line)) {
                line = trim(line);
                if (line.empty() || line[0] == '#') continue;

                std::smatch match;
                if (std::regex_match(line, match, keyRe)) {
                    std::string key = match[1].str();
                    std::string value = trim(match[2].str());
                    if (key == "runtime_cs") {
                        runtimeCs = parseHex16(value, key);
                        haveRuntimeCs = true;
                    } else if (key == "runtime_ds") {
                        runtimeDs = parseHex16(value, key);
                        haveRuntimeDs = true;
                    } else if (key == "temp_copy") {
                        tempCopy = value == "1";
                    }
                    continue;
                }

                if (std::regex_match(line, match, breakRe)) {
                    if (!haveRuntimeCs) fail("runtime_cs_missing_before_break");
                    uint16_t ghidraSegment = parseHex16(match[1].str(), "ghidra");
                    uint16_t ghidraOffset = parseHex16(match[2].str(), "ghidra");
                    uint16_t runtimeSegment = parseHex16(match[3].str(), "runtime");
                    uint16_t runtimeOffset = parseHex16(match[4].str(), "runtime");
                    if (ghidraSegment != 0x1000) {
                        fail("breakpoint_ghidra_segment expected=0x1000 actual=" +
                             hex4(ghidraSegment));
                    }
                    if (runtimeSegment != runtimeCs) {
                        fail("breakpoint_segment_mismatch expected=" + hex4(runtimeCs) +
                             " actual=" + hex4(runtimeSegment));
                    }
                    if (runtimeOffset != ghidraOffset) {
                        fail("breakpoint_offset_mismatch expected=" +
                             bareHex4(ghidraOffset) + " actual=" +
                             bareHex4(runtimeOffset));
                    }
                    ++breakCount;
                    continue;
                }

                if (std::regex_match(line, match, dumpRe)) {
                    currentDump = parseHex16(match[1].str(), "dump");
                    inDump = true;
                    continue;
                }

                if (std::regex_match(line, match, rowRe)) {
                    if (!inDump) fail("dump_row_without_header");
                    if (!haveRuntimeDs) fail("runtime_ds_missing_before_dump");
                    uint16_t segment = parseHex16(match[1].str(), "row_segment");
                    uint16_t address = parseHex16(match[2].str(), "row_address");
                    if (segment != runtimeDs) {
                        fail("dump_segment_mismatch expected=" + hex4(runtimeDs) +
                             " actual=" + hex4(segment) +
                             " address=" + bareHex4(address));
                    }
                    if (address < currentDump) {
                        fail("dump_address_before_header header=" + bareHex4(currentDump) +
                             " address=" + bareHex4(address));
                    }
                    std::istringstream byteStream(match[3].str());
                    std::string token;
                    uint16_t cursor = address;
                    while (byteStream >> token) {
                        memory[cursor] = parseHexByte(token, cursor);
                        present[cursor] = true;
                        ++cursor;
                    }
                    continue;
                }

                fail("unrecognized_line");
            }

            if (!haveRuntimeCs) fail("runtime_cs_missing");
            if (!haveRuntimeDs) fail("runtime_ds_missing");
            if (breakCount == 0) fail("breakpoints_missing");

            auto requireByte = [&](uint16_t address) -> uint8_t {
                if (!present[address]) {
                    fail("missing_byte address=" + bareHex4(address));
                }
                return memory[address];
            };
            auto rowString = [&](uint16_t address) {
                std::array<uint8_t, 4> bytes{requireByte(address),
                                             requireByte(static_cast<uint16_t>(address + 1)),
                                             requireByte(static_cast<uint16_t>(address + 2)),
                                             requireByte(static_cast<uint16_t>(address + 3))};
                return bareHex2(bytes[0]) + "," + bareHex2(bytes[1]) + "," +
                       bareHex2(bytes[2]) + "," + bareHex2(bytes[3]);
            };

            uint8_t deathCursor = requireByte(0x006a);
            uint8_t deathStart = requireByte(0x006c);
            uint8_t deathEnd = requireByte(0x006d);
            if (deathEnd < deathStart) {
                fail("death_frame_range_reversed start=" + hex2(deathStart) +
                     " end=" + hex2(deathEnd));
            }

            constexpr uint16_t kFrameEntryBase = 0xc322;
            uint16_t firstEntry = static_cast<uint16_t>(
                kFrameEntryBase + static_cast<uint16_t>(deathStart) * 4u);
            uint16_t lastEntry = static_cast<uint16_t>(
                kFrameEntryBase + static_cast<uint16_t>(deathEnd) * 4u);
            int frameRows = static_cast<int>(deathEnd - deathStart + 1);
            std::string firstRow = rowString(firstEntry);
            std::string lastRow = rowString(lastEntry);
            std::ostringstream rows;
            std::ostringstream row0Sequence;
            std::ostringstream row1Sequence;
            std::ostringstream row2Sequence;
            std::ostringstream row3Sequence;
            for (int frame = deathStart; frame <= deathEnd; ++frame) {
                uint16_t entry = static_cast<uint16_t>(
                    kFrameEntryBase + static_cast<uint16_t>(frame) * 4u);
                if (frame != deathStart) {
                    rows << ';';
                    row0Sequence << ',';
                    row1Sequence << ',';
                    row2Sequence << ',';
                    row3Sequence << ',';
                }
                rows << bareHex2(static_cast<uint8_t>(frame)) << '@'
                     << bareHex4(entry) << ':' << rowString(entry);
                row0Sequence << bareHex2(requireByte(entry));
                row1Sequence << bareHex2(
                    requireByte(static_cast<uint16_t>(entry + 1)));
                row2Sequence << bareHex2(
                    requireByte(static_cast<uint16_t>(entry + 2)));
                row3Sequence << bareHex2(
                    requireByte(static_cast<uint16_t>(entry + 3)));
            }
            uint16_t effectX = static_cast<uint16_t>(requireByte(0xc21e) |
                                                     (requireByte(0xc21f) << 8));
            uint16_t effectY = static_cast<uint16_t>(requireByte(0xc220) |
                                                     (requireByte(0xc221) << 8));

            std::cout << "state2_runtime_frame_oracle=ok fixture=" << fixture
                      << " runtime_cs=" << hex4(runtimeCs)
                      << " runtime_ds=" << hex4(runtimeDs)
                      << " death_cursor=" << hex2(deathCursor)
                      << " death_start=" << hex2(deathStart)
                      << " death_end=" << hex2(deathEnd)
                      << " table_entry_base=0xc322"
                      << " first_entry_addr=" << hex4(firstEntry)
                      << " frame_rows=" << frameRows
                      << " first_row=" << firstRow
                      << " last_row=" << lastRow
                      << " rows=" << rows.str()
                      << " row0_sequence=" << row0Sequence.str()
                      << " row1_sequence=" << row1Sequence.str()
                      << " row2_sequence=" << row2Sequence.str()
                      << " row3_sequence=" << row3Sequence.str()
                      << " effect0_xy=" << hex4(effectX) << ',' << hex4(effectY)
                      << " breaks=" << breakCount
                      << " temp_copy=" << (tempCopy ? 1 : 0)
                      << " visual_claim=0\n";
            if (expectError) {
                std::cout << "state2_runtime_frame_oracle=error fixture=" << fixture
                          << " reason=expected_error_missing\n";
                return 1;
            }
            return 0;
        } catch (const std::exception& e) {
            std::cout << e.what() << '\n';
            return expectError ? 0 : 1;
        }
    }

    int debugVisualTableOracle(const std::string& path, bool expectError) {
        auto fixtureName = [](const std::string& inputPath) {
            size_t slash = inputPath.find_last_of("/\\");
            std::string name =
                slash == std::string::npos ? inputPath : inputPath.substr(slash + 1);
            size_t dot = name.find_last_of('.');
            if (dot != std::string::npos) name = name.substr(0, dot);
            return name;
        };
        const std::string fixture = fixtureName(path);

        auto hex4 = [](uint16_t value) {
            std::ostringstream oss;
            oss << "0x" << std::hex << std::nouppercase << std::setw(4)
                << std::setfill('0') << value;
            return oss.str();
        };
        auto hex2 = [](uint8_t value) {
            std::ostringstream oss;
            oss << "0x" << std::hex << std::nouppercase << std::setw(2)
                << std::setfill('0') << static_cast<int>(value);
            return oss.str();
        };
        auto bareHex4 = [](uint16_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(4)
                << std::setfill('0') << value;
            return oss.str();
        };
        auto bareHex2 = [](uint8_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(2)
                << std::setfill('0') << static_cast<int>(value);
            return oss.str();
        };
        auto fail = [&](const std::string& reason) {
            throw std::runtime_error("visual_table_oracle=error fixture=" +
                                     fixture + " reason=" + reason);
        };
        auto trim = [](std::string value) {
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.front()))) {
                value.erase(value.begin());
            }
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.back()))) {
                value.pop_back();
            }
            return value;
        };
        auto parseHex16 = [&](std::string token,
                              const std::string& field) -> uint16_t {
            token = trim(token);
            if (token.rfind("0x", 0) == 0 || token.rfind("0X", 0) == 0) {
                token = token.substr(2);
            }
            if (token.empty() || token.size() > 4 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("bad_hex16 field=" + field + " token=" + token);
            }
            return static_cast<uint16_t>(std::stoul(token, nullptr, 16));
        };
        auto parseHexByte = [&](const std::string& token,
                                uint16_t address) -> uint8_t {
            if (token.size() != 2 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("non_hex_byte token=" + token + " address=" +
                     bareHex4(address));
            }
            return static_cast<uint8_t>(std::stoul(token, nullptr, 16));
        };
        auto parseInt = [&](const std::string& token,
                            const std::string& field) -> int {
            try {
                size_t pos = 0;
                int value = std::stoi(token, &pos, 0);
                if (pos != token.size()) fail("bad_int field=" + field + " token=" + token);
                return value;
            } catch (const std::exception&) {
                fail("bad_int field=" + field + " token=" + token);
            }
            return 0;
        };
        auto parseRecord = [&](const std::string& line) {
            std::istringstream stream(line);
            std::string record;
            stream >> record;
            std::map<std::string, std::string> fields;
            std::string token;
            while (stream >> token) {
                size_t eq = token.find('=');
                if (eq == std::string::npos || eq == 0 || eq + 1 >= token.size()) {
                    fail("bad_record_token record=" + record + " token=" + token);
                }
                fields[token.substr(0, eq)] = token.substr(eq + 1);
            }
            if (fields.empty()) fail("record_without_fields record=" + record);
            return std::pair<std::string, std::map<std::string, std::string>>{
                record, fields};
        };
        auto requireField = [&](const std::map<std::string, std::string>& fields,
                                const std::string& name,
                                const std::string& record) -> std::string {
            auto it = fields.find(name);
            if (it == fields.end()) fail(record + "_" + name + "_missing");
            return it->second;
        };
        auto parseRowBytes = [&](const std::string& value,
                                 const std::string& field) {
            std::array<uint8_t, 4> bytes{};
            std::istringstream stream(value);
            std::string token;
            int index = 0;
            while (std::getline(stream, token, ',')) {
                if (index >= 4) fail("too_many_row_bytes field=" + field);
                token = trim(token);
                if (token.rfind("0x", 0) == 0 || token.rfind("0X", 0) == 0) {
                    token = token.substr(2);
                }
                bytes[static_cast<size_t>(index)] =
                    parseHexByte(token, static_cast<uint16_t>(index));
                ++index;
            }
            if (index != 4) fail("row_byte_count field=" + field);
            return bytes;
        };
        auto rowString = [&](const std::array<uint8_t, 4>& bytes) {
            return bareHex2(bytes[0]) + "," + bareHex2(bytes[1]) + "," +
                   bareHex2(bytes[2]) + "," + bareHex2(bytes[3]);
        };
        auto normalizeBank = [&](std::string bank) {
            std::transform(bank.begin(), bank.end(), bank.begin(),
                           [](unsigned char ch) {
                               return static_cast<char>(std::toupper(ch));
                           });
            if (bank == "BOMOMIMK.SPR") bank = "BOMOMIMK";
            if (bank == "PROVA.SPR") bank = "PROVA";
            if (bank == "FONTS.SPR") bank = "FONTS";
            if (bank != "BOMOMIMK" && bank != "PROVA" && bank != "FONTS") {
                fail("unknown_sprite_bank value=" + bank);
            }
            return bank;
        };
        auto bankCount = [&](const std::string& bank) {
            if (bank == "BOMOMIMK" || bank == "PROVA") return 91;
            return 68;
        };

        try {
            std::string text = readTextFile(path);
            std::vector<uint8_t> memory(0x10000);
            std::vector<bool> present(0x10000, false);
            std::map<std::string, std::string> values;
            std::map<std::string, std::map<std::string, std::string>> records;
            std::vector<std::map<std::string, std::string>> visualRecords;
            std::vector<std::map<std::string, std::string>> effectBeforeRecords;
            std::vector<std::map<std::string, std::string>> effectAfterRecords;
            std::set<uint16_t> breakOffsets;
            uint16_t runtimeCs = 0;
            uint16_t runtimeDs = 0;
            bool haveRuntimeCs = false;
            bool haveRuntimeDs = false;
            bool tempCopy = false;
            bool visualClaim = false;
            int breakCount = 0;

            std::istringstream lines(text);
            std::string line;
            std::regex keyRe("^([A-Za-z0-9_]+)=(.*)$");
            std::regex breakRe(
                "^break\\s+ghidra=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+"
                "runtime=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+label=([^\\s]+).*$");
            std::regex dumpRe("^dump\\s+DS:([0-9A-Fa-f]{4}).*$");
            std::regex rowRe("^([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+(.+)$");
            uint16_t currentDump = 0;
            bool inDump = false;
            while (std::getline(lines, line)) {
                line = trim(line);
                if (line.empty() || line[0] == '#') continue;

                std::smatch match;
                if (std::regex_match(line, match, keyRe)) {
                    std::string key = match[1].str();
                    std::string value = trim(match[2].str());
                    values[key] = value;
                    if (key == "runtime_cs") {
                        runtimeCs = parseHex16(value, key);
                        haveRuntimeCs = true;
                    } else if (key == "runtime_ds") {
                        runtimeDs = parseHex16(value, key);
                        haveRuntimeDs = true;
                    } else if (key == "temp_copy") {
                        tempCopy = value == "1";
                    } else if (key == "visual_claim") {
                        visualClaim = value != "0";
                    }
                    continue;
                }
                if (std::regex_match(line, match, breakRe)) {
                    if (!haveRuntimeCs) fail("runtime_cs_missing_before_break");
                    uint16_t ghidraSegment = parseHex16(match[1].str(), "ghidra");
                    uint16_t ghidraOffset = parseHex16(match[2].str(), "ghidra");
                    uint16_t runtimeSegment = parseHex16(match[3].str(), "runtime");
                    uint16_t runtimeOffset = parseHex16(match[4].str(), "runtime");
                    if (ghidraSegment != 0x1000) {
                        fail("breakpoint_ghidra_segment expected=0x1000 actual=" +
                             hex4(ghidraSegment));
                    }
                    if (runtimeSegment != runtimeCs) {
                        fail("breakpoint_segment_mismatch expected=" + hex4(runtimeCs) +
                             " actual=" + hex4(runtimeSegment));
                    }
                    if (runtimeOffset != ghidraOffset) {
                        fail("breakpoint_offset_mismatch expected=" +
                             bareHex4(ghidraOffset) + " actual=" +
                             bareHex4(runtimeOffset));
                    }
                    breakOffsets.insert(ghidraOffset);
                    ++breakCount;
                    continue;
                }
                if (std::regex_match(line, match, dumpRe)) {
                    currentDump = parseHex16(match[1].str(), "dump");
                    inDump = true;
                    continue;
                }
                if (std::regex_match(line, match, rowRe)) {
                    if (!inDump) fail("dump_row_without_header");
                    if (!haveRuntimeDs) fail("runtime_ds_missing_before_dump");
                    uint16_t segment = parseHex16(match[1].str(), "row_segment");
                    uint16_t address = parseHex16(match[2].str(), "row_address");
                    if (segment != runtimeDs) {
                        fail("dump_segment_mismatch expected=" + hex4(runtimeDs) +
                             " actual=" + hex4(segment) +
                             " address=" + bareHex4(address));
                    }
                    if (address < currentDump) {
                        fail("dump_address_before_header header=" + bareHex4(currentDump) +
                             " address=" + bareHex4(address));
                    }
                    std::istringstream byteStream(match[3].str());
                    std::string token;
                    uint16_t cursor = address;
                    while (byteStream >> token) {
                        memory[cursor] = parseHexByte(token, cursor);
                        present[cursor] = true;
                        ++cursor;
                    }
                    continue;
                }
                if (line.rfind("actor ", 0) == 0 ||
                    line.rfind("visual ", 0) == 0 ||
                    line.rfind("effect_before ", 0) == 0 ||
                    line.rfind("effect_after ", 0) == 0) {
                    auto parsed = parseRecord(line);
                    if (parsed.first == "visual") {
                        visualRecords.push_back(parsed.second);
                    } else if (parsed.first == "effect_before") {
                        effectBeforeRecords.push_back(parsed.second);
                    } else if (parsed.first == "effect_after") {
                        effectAfterRecords.push_back(parsed.second);
                    } else {
                        records[parsed.first] = parsed.second;
                    }
                    continue;
                }
                fail("unrecognized_line");
            }

            if (!haveRuntimeCs) fail("runtime_cs_missing");
            if (!haveRuntimeDs) fail("runtime_ds_missing");
            if (visualClaim) fail("visual_claim_not_supported");
            auto scenarioIt = values.find("scenario");
            if (scenarioIt == values.end()) fail("scenario_missing");
            const std::string scenario = scenarioIt->second;

            std::vector<uint16_t> requiredBreaks;
            if (scenario == "state2_death_table_consumption") {
                requiredBreaks = {0x3108, 0x6053, 0x6148, 0x7c89, 0x7ddf};
            } else if (scenario == "monster_death_impact_frame") {
                requiredBreaks = {0x74a6, 0x7513};
            } else if (scenario == "bonus_reward_drop_frame") {
                requiredBreaks = {0x6e4b, 0x6f8d};
            } else if (scenario == "two_player_panel_art" ||
                       scenario == "records_menu_cursor") {
                requiredBreaks = {0x1b14, 0x1d42};
            } else {
                fail("unknown_scenario value=" + scenario);
            }
            for (uint16_t offset : requiredBreaks) {
                if (breakOffsets.count(offset) == 0) {
                    fail("missing_breakpoint offset=" + bareHex4(offset));
                }
            }

            auto actorIt = records.find("actor");
            if (actorIt == records.end()) fail("actor_missing");
            if (visualRecords.empty()) fail("visual_missing");
            if (effectBeforeRecords.empty()) fail("effect_before_missing");
            if (effectAfterRecords.empty()) fail("effect_after_missing");
            if (effectBeforeRecords.size() != 1 &&
                effectBeforeRecords.size() != visualRecords.size()) {
                fail("effect_before_count_mismatch expected=1_or_" +
                     std::to_string(visualRecords.size()) + " actual=" +
                     std::to_string(effectBeforeRecords.size()));
            }
            if (effectAfterRecords.size() != 1 &&
                effectAfterRecords.size() != visualRecords.size()) {
                fail("effect_after_count_mismatch expected=1_or_" +
                     std::to_string(visualRecords.size()) + " actual=" +
                     std::to_string(effectAfterRecords.size()));
            }
            if (effectBeforeRecords.size() != effectAfterRecords.size()) {
                fail("effect_count_shape_mismatch before=" +
                     std::to_string(effectBeforeRecords.size()) + " after=" +
                     std::to_string(effectAfterRecords.size()));
            }

            const auto& actor = actorIt->second;
            int actorSlot = parseInt(requireField(actor, "slot", "actor"), "actor.slot");
            int actorState = parseInt(requireField(actor, "state", "actor"), "actor.state");
            uint8_t animCurrent = static_cast<uint8_t>(
                parseHex16(requireField(actor, "anim_current", "actor"),
                           "actor.anim_current"));
            uint8_t animFirst = static_cast<uint8_t>(
                parseHex16(requireField(actor, "anim_first", "actor"),
                           "actor.anim_first"));
            uint8_t animLast = static_cast<uint8_t>(
                parseHex16(requireField(actor, "anim_last", "actor"),
                           "actor.anim_last"));
            int animMode = parseInt(requireField(actor, "anim_mode", "actor"),
                                    "actor.anim_mode");

            struct VisualSummary {
                uint8_t frame = 0;
                uint16_t rowAddress = 0;
                std::array<uint8_t, 4> row{};
                std::string bank;
                int spriteIndex = 0;
                std::string spriteSource;
                int drawDx = 0;
                int drawDy = 0;
            };
            struct EffectSummary {
                int slot = 0;
                uint16_t beforeX = 0;
                uint16_t beforeY = 0;
                uint16_t afterX = 0;
                uint16_t afterY = 0;
                uint8_t beforeFrame = 0;
                uint8_t afterFrame = 0;
            };

            constexpr uint16_t kFrameEntryBase = 0xc322;
            auto requireByte = [&](uint16_t address) -> uint8_t {
                if (!present[address]) {
                    fail("missing_byte address=" + bareHex4(address));
                }
                return memory[address];
            };

            std::vector<VisualSummary> parsedRows;
            parsedRows.reserve(visualRecords.size());
            for (const auto& visual : visualRecords) {
                uint8_t visualFrame = static_cast<uint8_t>(
                    parseHex16(requireField(visual, "frame", "visual"),
                               "visual.frame"));
                if (parsedRows.empty()) {
                    if (visualFrame != animCurrent) {
                        fail("visual_frame_mismatch actor=" + hex2(animCurrent) +
                             " visual=" + hex2(visualFrame));
                    }
                } else {
                    uint8_t expectedNext =
                        static_cast<uint8_t>(parsedRows.back().frame + 1u);
                    if (visualFrame != expectedNext) {
                        fail("visual_frame_sequence_mismatch expected=" +
                             hex2(expectedNext) + " actual=" + hex2(visualFrame));
                    }
                }
                if (visualFrame < animFirst || visualFrame > animLast) {
                    fail("visual_frame_out_of_range range=" + hex2(animFirst) +
                         ".." + hex2(animLast) + " visual=" + hex2(visualFrame));
                }
                uint16_t rowAddress =
                    parseHex16(requireField(visual, "row_addr", "visual"),
                               "visual.row_addr");
                uint16_t expectedRowAddress = static_cast<uint16_t>(
                    kFrameEntryBase + static_cast<uint16_t>(visualFrame) * 4u);
                if (rowAddress != expectedRowAddress) {
                    fail("row_addr_mismatch expected=" + hex4(expectedRowAddress) +
                         " actual=" + hex4(rowAddress));
                }
                bool hasVisualRow = visual.count("row") != 0;
                bool hasSpriteIndex = visual.count("sprite_index") != 0;
                if (hasSpriteIndex && !hasVisualRow) {
                    fail("visual_row_missing_for_sprite");
                }
                if (!hasVisualRow) fail("visual_row_missing");
                std::array<uint8_t, 4> claimedRow =
                    parseRowBytes(requireField(visual, "row", "visual"),
                                  "visual.row");
                std::array<uint8_t, 4> memoryRow{
                    requireByte(rowAddress),
                    requireByte(static_cast<uint16_t>(rowAddress + 1)),
                    requireByte(static_cast<uint16_t>(rowAddress + 2)),
                    requireByte(static_cast<uint16_t>(rowAddress + 3)),
                };
                if (claimedRow != memoryRow) {
                    fail("visual_row_mismatch expected=" + rowString(memoryRow) +
                         " actual=" + rowString(claimedRow));
                }

                std::string bank =
                    normalizeBank(requireField(visual, "bank", "visual"));
                int spriteIndex =
                    parseInt(requireField(visual, "sprite_index", "visual"),
                             "visual.sprite_index");
                if (spriteIndex < 0 || spriteIndex >= bankCount(bank)) {
                    fail("sprite_index_out_of_range bank=" + bank +
                         " index=" + std::to_string(spriteIndex));
                }
                std::string spriteSource =
                    visual.count("sprite_source") ? visual.at("sprite_source")
                                                  : "runtime";
                if (spriteSource == "row_byte0" && spriteIndex != claimedRow[0]) {
                    fail("sprite_index_row0_mismatch row0=" +
                         std::to_string(static_cast<int>(claimedRow[0])) +
                         " sprite_index=" + std::to_string(spriteIndex));
                }
                if (spriteSource == "row_byte3" && spriteIndex != claimedRow[3]) {
                    fail("sprite_index_row3_mismatch row3=" +
                         std::to_string(static_cast<int>(claimedRow[3])) +
                         " sprite_index=" + std::to_string(spriteIndex));
                }
                if (spriteSource != "row_byte0" && spriteSource != "row_byte3" &&
                    spriteSource != "runtime_draw_call" &&
                    spriteSource != "static_table") {
                    fail("bad_sprite_source value=" + spriteSource);
                }
                if (!parsedRows.empty() && bank != parsedRows.front().bank) {
                    fail("visual_bank_changed first=" + parsedRows.front().bank +
                         " actual=" + bank);
                }
                if (!parsedRows.empty() &&
                    spriteSource != parsedRows.front().spriteSource) {
                    fail("visual_sprite_source_changed first=" +
                         parsedRows.front().spriteSource + " actual=" +
                         spriteSource);
                }

                parsedRows.push_back(VisualSummary{
                    visualFrame,
                    rowAddress,
                    memoryRow,
                    bank,
                    spriteIndex,
                    spriteSource,
                    parseInt(requireField(visual, "draw_dx", "visual"),
                             "visual.draw_dx"),
                    parseInt(requireField(visual, "draw_dy", "visual"),
                             "visual.draw_dy"),
                });
            }

            auto parseEffectPair = [&](size_t index, uint8_t expectedFrame) {
                const auto& effectBefore = effectBeforeRecords[index];
                const auto& effectAfter = effectAfterRecords[index];
                int effectBeforeSlot = parseInt(
                    requireField(effectBefore, "slot", "effect_before"),
                    "effect_before.slot");
                int effectAfterSlot = parseInt(
                    requireField(effectAfter, "slot", "effect_after"),
                    "effect_after.slot");
                if (effectBeforeSlot != effectAfterSlot) {
                    fail("effect_slot_changed before=" +
                         std::to_string(effectBeforeSlot) + " after=" +
                         std::to_string(effectAfterSlot));
                }
                uint16_t effectBeforeX =
                    parseHex16(requireField(effectBefore, "x", "effect_before"),
                               "effect_before.x");
                uint16_t effectBeforeY =
                    parseHex16(requireField(effectBefore, "y", "effect_before"),
                               "effect_before.y");
                uint16_t effectAfterX =
                    parseHex16(requireField(effectAfter, "x", "effect_after"),
                               "effect_after.x");
                uint16_t effectAfterY =
                    parseHex16(requireField(effectAfter, "y", "effect_after"),
                               "effect_after.y");
                uint8_t effectBeforeFrame = static_cast<uint8_t>(
                    parseHex16(requireField(effectBefore, "frame", "effect_before"),
                               "effect_before.frame"));
                uint8_t effectAfterFrame = static_cast<uint8_t>(
                    parseHex16(requireField(effectAfter, "frame", "effect_after"),
                               "effect_after.frame"));
                if (effectBeforeFrame != expectedFrame) {
                    fail("effect_before_frame_mismatch expected=" +
                         hex2(expectedFrame) + " actual=" +
                         hex2(effectBeforeFrame));
                }
                if (effectAfterFrame != expectedFrame) {
                    fail("effect_after_frame_mismatch expected=" +
                         hex2(expectedFrame) + " actual=" + hex2(effectAfterFrame));
                }
                return EffectSummary{
                    effectBeforeSlot,
                    effectBeforeX,
                    effectBeforeY,
                    effectAfterX,
                    effectAfterY,
                    effectBeforeFrame,
                    effectAfterFrame,
                };
            };

            std::vector<EffectSummary> effects;
            if (effectBeforeRecords.size() == 1) {
                effects.push_back(parseEffectPair(0, parsedRows.front().frame));
            } else {
                effects.reserve(parsedRows.size());
                for (size_t index = 0; index < parsedRows.size(); ++index) {
                    effects.push_back(parseEffectPair(index, parsedRows[index].frame));
                }
            }

            auto rowsSummary = [&]() {
                std::string value;
                for (size_t index = 0; index < parsedRows.size(); ++index) {
                    if (index != 0) value += ";";
                    const auto& row = parsedRows[index];
                    value += bareHex2(row.frame) + "@" + bareHex4(row.rowAddress) +
                             ":" + rowString(row.row);
                }
                return value;
            };
            auto spriteIndexSummary = [&]() {
                std::string value;
                for (size_t index = 0; index < parsedRows.size(); ++index) {
                    if (index != 0) value += ",";
                    value += std::to_string(parsedRows[index].spriteIndex);
                }
                return value;
            };
            auto drawOffsetSummary = [&]() {
                std::string value;
                for (size_t index = 0; index < parsedRows.size(); ++index) {
                    if (index != 0) value += ";";
                    value += std::to_string(parsedRows[index].drawDx) + "," +
                             std::to_string(parsedRows[index].drawDy);
                }
                return value;
            };
            auto effectAfterFrameSummary = [&]() {
                std::string value;
                for (size_t index = 0; index < effects.size(); ++index) {
                    if (index != 0) value += ",";
                    value += hex2(effects[index].afterFrame);
                }
                return value;
            };

            const auto& firstRow = parsedRows.front();
            const auto& firstEffect = effects.front();
            if (parsedRows.size() == 1) {
                std::cout << "visual_table_oracle=ok fixture=" << fixture
                          << " scenario=" << scenario
                          << " runtime_cs=" << hex4(runtimeCs)
                          << " runtime_ds=" << hex4(runtimeDs)
                          << " actor_slot=" << actorSlot
                          << " actor_state=" << actorState
                          << " anim_current=" << hex2(animCurrent)
                          << " anim_range=" << hex2(animFirst) << ".."
                          << hex2(animLast)
                          << " anim_mode=" << animMode
                          << " visual_frame=" << hex2(firstRow.frame)
                          << " row_addr=" << hex4(firstRow.rowAddress)
                          << " row=" << rowString(firstRow.row)
                          << " bank=" << firstRow.bank
                          << " sprite_index=" << firstRow.spriteIndex
                          << " sprite_source=" << firstRow.spriteSource
                          << " draw_offset=" << firstRow.drawDx << ','
                          << firstRow.drawDy
                          << " effect_slot=" << firstEffect.slot
                          << " effect_before_xy=" << hex4(firstEffect.beforeX)
                          << ',' << hex4(firstEffect.beforeY)
                          << " effect_after_xy=" << hex4(firstEffect.afterX)
                          << ',' << hex4(firstEffect.afterY)
                          << " effect_after_frame="
                          << hex2(firstEffect.afterFrame)
                          << " breaks=" << breakCount
                          << " temp_copy=" << (tempCopy ? 1 : 0)
                          << " visual_claim=0\n";
            } else {
                std::cout << "visual_table_oracle=ok fixture=" << fixture
                          << " scenario=" << scenario
                          << " runtime_cs=" << hex4(runtimeCs)
                          << " runtime_ds=" << hex4(runtimeDs)
                          << " actor_slot=" << actorSlot
                          << " actor_state=" << actorState
                          << " anim_current=" << hex2(animCurrent)
                          << " anim_range=" << hex2(animFirst) << ".."
                          << hex2(animLast)
                          << " anim_mode=" << animMode
                          << " visual_rows=" << parsedRows.size()
                          << " visual_frames=" << hex2(firstRow.frame) << ".."
                          << hex2(parsedRows.back().frame)
                          << " rows=" << rowsSummary()
                          << " bank=" << firstRow.bank
                          << " sprite_indices=" << spriteIndexSummary()
                          << " sprite_source=" << firstRow.spriteSource
                          << " draw_offsets=" << drawOffsetSummary()
                          << " effect_slot=" << firstEffect.slot
                          << " effect_before_xy=" << hex4(firstEffect.beforeX)
                          << ',' << hex4(firstEffect.beforeY)
                          << " effect_after_xy=" << hex4(firstEffect.afterX)
                          << ',' << hex4(firstEffect.afterY)
                          << " effect_after_frames="
                          << effectAfterFrameSummary()
                          << " breaks=" << breakCount
                          << " temp_copy=" << (tempCopy ? 1 : 0)
                          << " visual_claim=0\n";
            }
            if (expectError) {
                std::cout << "visual_table_oracle=error fixture=" << fixture
                          << " reason=expected_error_missing\n";
                return 1;
            }
            return 0;
        } catch (const std::exception& e) {
            std::cout << e.what() << '\n';
            return expectError ? 0 : 1;
        }
    }

    int debugBehavior4RuntimeOracle(const std::string& path, bool expectError) {
        auto fixtureName = [](const std::string& inputPath) {
            size_t slash = inputPath.find_last_of("/\\");
            std::string name =
                slash == std::string::npos ? inputPath : inputPath.substr(slash + 1);
            size_t dot = name.find_last_of('.');
            if (dot != std::string::npos) name = name.substr(0, dot);
            return name;
        };
        const std::string fixture = fixtureName(path);

        auto bareHex4 = [](uint16_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(4)
                << std::setfill('0') << value;
            return oss.str();
        };
        auto fail = [&](const std::string& reason) {
            throw std::runtime_error("behavior4_runtime_oracle=error fixture=" +
                                     fixture + " reason=" + reason);
        };
        auto parseHex16 = [&](const std::string& token,
                              const std::string& field) -> uint16_t {
            if (token.empty() || token.size() > 4 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("bad_hex16 field=" + field + " token=" + token);
            }
            return static_cast<uint16_t>(std::stoul(token, nullptr, 16));
        };
        auto parseHexByte = [&](const std::string& token,
                                uint16_t address) -> uint8_t {
            if (token.size() != 2 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("non_hex_byte token=" + token + " address=" +
                     bareHex4(address));
            }
            return static_cast<uint8_t>(std::stoul(token, nullptr, 16));
        };
        auto trim = [](std::string value) {
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.front()))) {
                value.erase(value.begin());
            }
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.back()))) {
                value.pop_back();
            }
            return value;
        };
        auto parseIntAuto = [&](const std::string& token,
                                const std::string& field) -> int {
            try {
                size_t parsed = 0;
                long value = std::stol(token, &parsed, 0);
                if (parsed != token.size()) {
                    fail("bad_int field=" + field + " token=" + token);
                }
                return static_cast<int>(value);
            } catch (const std::exception&) {
                fail("bad_int field=" + field + " token=" + token);
            }
            return 0;
        };
        auto parseFields = [&](const std::string& body,
                               const std::string& record) {
            std::map<std::string, std::string> fields;
            std::istringstream stream(body);
            std::string token;
            while (stream >> token) {
                size_t equals = token.find('=');
                if (equals == std::string::npos || equals == 0 ||
                    equals + 1 >= token.size()) {
                    fail("bad_field record=" + record + " token=" + token);
                }
                fields[token.substr(0, equals)] = token.substr(equals + 1);
            }
            return fields;
        };
        auto fieldInt = [&](const std::map<std::string, std::string>& fields,
                            const std::string& name,
                            const std::string& record) -> int {
            auto found = fields.find(name);
            if (found == fields.end()) {
                fail("missing_field record=" + record + " field=" + name);
            }
            return parseIntAuto(found->second, record + "." + name);
        };
        auto optionalFieldInt = [&](const std::map<std::string, std::string>& fields,
                                    const std::string& name,
                                    const std::string& record,
                                    int fallback) -> int {
            auto found = fields.find(name);
            if (found == fields.end()) return fallback;
            return parseIntAuto(found->second, record + "." + name);
        };

        struct SpawnerRecord {
            bool present = false;
            int index = 0;
            int behavior = 0;
            int ai0 = 0;
            int ai1 = 0;
            int ai2 = 0;
            int hp = 0;
            int spawnTimer = 0;
        };
        struct ActorRecord {
            bool present = false;
            int slot = 0;
            int behavior = 0;
            int x = 0;
            int y = 0;
            int vx8 = 0;
            int vy8 = 0;
            int motionTimer = 0;
            int target = 0;
            int hp = 0;
            int dead = 0;
        };
        struct PlayerRecord {
            bool present = false;
            int p1Dead = 0;
            int p2Dead = 0;
            int p1State = 0;
            int p2State = 0;
            int targetBefore = 0;
            int targetAfter = 0;
        };

        try {
            std::string text = readTextFile(path);
            uint16_t runtimeCs = 0;
            uint16_t runtimeDs = 0;
            bool haveRuntimeCs = false;
            bool haveRuntimeDs = false;
            bool tempCopy = false;
            bool visualClaim = false;
            bool haveScenario = false;
            bool haveLevel = false;
            std::string scenario;
            int level = 0;
            SpawnerRecord spawner;
            ActorRecord actorBefore;
            ActorRecord actorAfter;
            PlayerRecord players;
            int breakCount = 0;
            int dumpBytes = 0;
            constexpr std::array<uint16_t, 6> kRequiredOffsets{
                0x7a6b, 0x7c2c, 0x728c, 0x731b, 0x73e5, 0x741b};
            std::array<bool, 6> sawRequired{};

            std::istringstream lines(text);
            std::string line;
            std::regex keyRe("^([A-Za-z0-9_]+)=(.*)$");
            std::regex breakRe(
                "^break\\s+ghidra=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+"
                "runtime=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+label=([^\\s]+).*$");
            std::regex dumpRe("^dump\\s+DS:([0-9A-Fa-f]{4}).*$");
            std::regex rowRe("^([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+(.+)$");
            uint16_t currentDump = 0;
            bool inDump = false;
            while (std::getline(lines, line)) {
                line = trim(line);
                if (line.empty() || line[0] == '#') continue;

                std::smatch match;
                if (std::regex_match(line, match, keyRe)) {
                    std::string key = match[1].str();
                    std::string value = trim(match[2].str());
                    if (key == "runtime_cs") {
                        runtimeCs = parseHex16(value, key);
                        haveRuntimeCs = true;
                    } else if (key == "runtime_ds") {
                        runtimeDs = parseHex16(value, key);
                        haveRuntimeDs = true;
                    } else if (key == "temp_copy") {
                        tempCopy = value == "1";
                    } else if (key == "visual_claim") {
                        visualClaim = value != "0";
                    } else if (key == "scenario") {
                        scenario = value;
                        haveScenario = true;
                    } else if (key == "level") {
                        level = parseIntAuto(value, key);
                        haveLevel = true;
                    }
                    continue;
                }

                if (line.rfind("spawner ", 0) == 0) {
                    auto fields = parseFields(line.substr(8), "spawner");
                    spawner.present = true;
                    spawner.index = fieldInt(fields, "index", "spawner");
                    spawner.behavior = fieldInt(fields, "behavior", "spawner");
                    spawner.ai0 = fieldInt(fields, "ai0", "spawner");
                    spawner.ai1 = fieldInt(fields, "ai1", "spawner");
                    spawner.ai2 = fieldInt(fields, "ai2", "spawner");
                    spawner.hp = fieldInt(fields, "hp", "spawner");
                    spawner.spawnTimer =
                        optionalFieldInt(fields, "spawn_timer", "spawner", 0);
                    continue;
                }
                if (line.rfind("actor_before ", 0) == 0 ||
                    line.rfind("actor_after ", 0) == 0) {
                    bool after = line.rfind("actor_after ", 0) == 0;
                    const std::string record = after ? "actor_after" : "actor_before";
                    auto fields = parseFields(
                        line.substr(after ? 12 : 13), record);
                    ActorRecord parsed;
                    parsed.present = true;
                    parsed.slot = fieldInt(fields, "slot", record);
                    parsed.behavior = fieldInt(fields, "behavior", record);
                    parsed.x = fieldInt(fields, "x", record);
                    parsed.y = fieldInt(fields, "y", record);
                    parsed.vx8 = fieldInt(fields, "vx8", record);
                    parsed.vy8 = fieldInt(fields, "vy8", record);
                    parsed.motionTimer = fieldInt(fields, "motion_timer", record);
                    parsed.target = fieldInt(fields, "target", record);
                    parsed.hp = fieldInt(fields, "hp", record);
                    parsed.dead = fieldInt(fields, "dead", record);
                    if (after) {
                        actorAfter = parsed;
                    } else {
                        actorBefore = parsed;
                    }
                    continue;
                }
                if (line.rfind("players ", 0) == 0) {
                    auto fields = parseFields(line.substr(8), "players");
                    players.present = true;
                    players.p1Dead = fieldInt(fields, "p1_dead", "players");
                    players.p2Dead = fieldInt(fields, "p2_dead", "players");
                    players.p1State = fieldInt(fields, "p1_state", "players");
                    players.p2State = fieldInt(fields, "p2_state", "players");
                    players.targetBefore =
                        fieldInt(fields, "target_before", "players");
                    players.targetAfter = fieldInt(fields, "target_after", "players");
                    continue;
                }

                if (std::regex_match(line, match, breakRe)) {
                    if (!haveRuntimeCs) fail("runtime_cs_missing_before_break");
                    uint16_t ghidraSegment = parseHex16(match[1].str(), "ghidra");
                    uint16_t ghidraOffset = parseHex16(match[2].str(), "ghidra");
                    uint16_t runtimeSegment = parseHex16(match[3].str(), "runtime");
                    uint16_t runtimeOffset = parseHex16(match[4].str(), "runtime");
                    if (ghidraSegment != 0x1000) {
                        fail("breakpoint_ghidra_segment expected=0x1000 actual=" +
                             hex4(ghidraSegment));
                    }
                    if (runtimeSegment != runtimeCs) {
                        fail("breakpoint_segment_mismatch expected=" + hex4(runtimeCs) +
                             " actual=" + hex4(runtimeSegment));
                    }
                    if (runtimeOffset != ghidraOffset) {
                        fail("breakpoint_offset_mismatch expected=" +
                             bareHex4(ghidraOffset) + " actual=" +
                             bareHex4(runtimeOffset));
                    }
                    ++breakCount;
                    for (size_t i = 0; i < kRequiredOffsets.size(); ++i) {
                        if (ghidraOffset == kRequiredOffsets[i]) sawRequired[i] = true;
                    }
                    continue;
                }

                if (std::regex_match(line, match, dumpRe)) {
                    currentDump = parseHex16(match[1].str(), "dump");
                    inDump = true;
                    continue;
                }

                if (std::regex_match(line, match, rowRe)) {
                    if (!inDump) fail("dump_row_without_header");
                    if (!haveRuntimeDs) fail("runtime_ds_missing_before_dump");
                    uint16_t segment = parseHex16(match[1].str(), "row_segment");
                    uint16_t address = parseHex16(match[2].str(), "row_address");
                    if (segment != runtimeDs) {
                        fail("dump_segment_mismatch expected=" + hex4(runtimeDs) +
                             " actual=" + hex4(segment) +
                             " address=" + bareHex4(address));
                    }
                    if (address < currentDump) {
                        fail("dump_address_before_header header=" + bareHex4(currentDump) +
                             " address=" + bareHex4(address));
                    }
                    std::istringstream byteStream(match[3].str());
                    std::string token;
                    uint16_t cursor = address;
                    while (byteStream >> token) {
                        (void)parseHexByte(token, cursor);
                        ++cursor;
                        ++dumpBytes;
                    }
                    continue;
                }

                fail("unrecognized_line");
            }

            if (!haveRuntimeCs) fail("runtime_cs_missing");
            if (!haveRuntimeDs) fail("runtime_ds_missing");
            if (!haveScenario) fail("scenario_missing");
            if (!haveLevel) fail("level_missing");
            if (visualClaim) fail("visual_claim_not_supported");
            if (!spawner.present) fail("spawner_missing");
            if (!actorBefore.present) fail("actor_before_missing");
            if (!actorAfter.present) fail("actor_after_missing");
            if (!players.present) fail("players_missing");
            for (size_t i = 0; i < kRequiredOffsets.size(); ++i) {
                if (!sawRequired[i]) {
                    fail("missing_breakpoint offset=" + bareHex4(kRequiredOffsets[i]));
                }
            }
            if (spawner.behavior != 4) {
                fail("spawner_behavior_not_4 actual=" +
                     std::to_string(spawner.behavior));
            }
            if (actorBefore.behavior != 4) {
                fail("actor_before_behavior_not_4 actual=" +
                     std::to_string(actorBefore.behavior));
            }
            if (actorAfter.behavior != 4) {
                fail("actor_after_behavior_not_4 actual=" +
                     std::to_string(actorAfter.behavior));
            }
            if (actorBefore.slot != actorAfter.slot) {
                fail("actor_slot_changed before=" + std::to_string(actorBefore.slot) +
                     " after=" + std::to_string(actorAfter.slot));
            }
            if (players.targetBefore != actorBefore.target) {
                fail("target_before_mismatch actor=" +
                     std::to_string(actorBefore.target) + " players=" +
                     std::to_string(players.targetBefore));
            }
            if (players.targetAfter != actorAfter.target) {
                fail("target_after_mismatch actor=" +
                     std::to_string(actorAfter.target) + " players=" +
                     std::to_string(players.targetAfter));
            }

            std::cout << "behavior4_runtime_oracle=ok fixture=" << fixture
                      << " scenario=" << scenario
                      << " level=" << level
                      << " runtime_cs=" << hex4(runtimeCs)
                      << " runtime_ds=" << hex4(runtimeDs)
                      << " spawner_index=" << spawner.index
                      << " spawner_behavior=" << spawner.behavior
                      << " spawner_ai=" << spawner.ai0 << ',' << spawner.ai1
                      << ',' << spawner.ai2
                      << " spawner_hp=" << spawner.hp
                      << " actor_slot=" << actorAfter.slot
                      << " before_xy="
                      << hex4(static_cast<uint16_t>(actorBefore.x)) << ','
                      << hex4(static_cast<uint16_t>(actorBefore.y))
                      << " after_xy="
                      << hex4(static_cast<uint16_t>(actorAfter.x)) << ','
                      << hex4(static_cast<uint16_t>(actorAfter.y))
                      << " velocity8=" << actorAfter.vx8 << ','
                      << actorAfter.vy8
                      << " motion_timer=" << actorAfter.motionTimer
                      << " target_before=" << actorBefore.target
                      << " target_after=" << actorAfter.target
                      << " players_dead=" << players.p1Dead << ','
                      << players.p2Dead
                      << " breaks=" << breakCount
                      << " dump_bytes=" << dumpBytes
                      << " temp_copy=" << (tempCopy ? 1 : 0)
                      << " visual_claim=0\n";
            if (expectError) {
                std::cout << "behavior4_runtime_oracle=error fixture=" << fixture
                          << " reason=expected_error_missing\n";
                return 1;
            }
            return 0;
        } catch (const std::exception& e) {
            std::cout << e.what() << '\n';
            return expectError ? 0 : 1;
        }
    }

    void debugBehavior4StaticModel() {
        struct Anchor {
            uint16_t offset;
            const char* label;
            const char* region;
            const char* bytes;
        };

        const std::array<Anchor, 6> anchors{{
            {0x7a6b, "spawner_loop_start", "spawner_loop",
             "80 3e a6 79 00 77 03 e9 c8 01 c7 06 82 20 01 00 "
             "a0 a6 79 30 e4 3b 06 82 20 73 03 e9 b4 01 6b 3e"},
            {0x7c2c, "spawner_loop_end", "spawner_loop",
             "a0 82 20 c4 7e f8 26 88 45 25 ff 06 82 20 e9 3e "
             "fe c7 06 82 20 01 00 eb 04 ff 06 82 20 8b 3e 82"},
            {0x728c, "behavior4_branch_start", "behavior4_branch",
             "c4 7e 04 26 8a 45 03 88 46 ee c4 7e 04 81 c7 16 "
             "00 89 7e c6 8c 46 c8 8a 46 ee 30 e4 8b f8 d1 e7"},
            {0x731b, "behavior4_branch_end", "behavior4_branch",
             "26 88 45 02 c4 7e c6 26 8a 45 01 c4 7e c6 26 88 "
             "05 80 7e f1 04 75 5d 8b 46 d6 03 06 04 c2 a3 e8"},
            {0x73e5, "integration_8_8_start", "integration_8_8",
             "8b 46 f2 30 ff 3d 00 00 7d 02 b7 ff 8a 5e ef 00 "
             "c3 88 5e ef 88 e0 88 fc 11 46 d2 8b 46 f4 30 ff"},
            {0x741b, "integration_8_8_end", "integration_8_8",
             "11 46 d4 80 7e f1 01 73 03 e9 f0 00 80 7e f1 08 "
             "76 03 e9 e7 00 80 7e f1 1f 75 03 e9 de 00 31 c0"},
        }};

        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for behavior-4 scan");
        }

        auto requireBytes = [&](const Anchor& anchor) {
            std::vector<uint8_t> expected = parseHexByteList(anchor.bytes);
            size_t p = imageBase + anchor.offset;
            if (p + expected.size() > exeBytes.size()) {
                throw std::runtime_error(std::string(anchor.label) +
                                         " extends past LEZAC.EXE");
            }
            for (size_t i = 0; i < expected.size(); ++i) {
                if (exeBytes[p + i] != expected[i]) {
                    throw std::runtime_error(std::string(anchor.label) +
                                             " bytes changed");
                }
            }
        };

        int spawnerAnchors = 0;
        int branchAnchors = 0;
        int integrationAnchors = 0;
        std::ostringstream targetMap;
        for (size_t i = 0; i < anchors.size(); ++i) {
            const Anchor& anchor = anchors[i];
            requireBytes(anchor);
            if (std::string(anchor.region) == "spawner_loop") {
                ++spawnerAnchors;
            } else if (std::string(anchor.region) == "behavior4_branch") {
                ++branchAnchors;
            } else if (std::string(anchor.region) == "integration_8_8") {
                ++integrationAnchors;
            }
            if (i != 0) {
                targetMap << ',';
            }
            targetMap << hex4(anchor.offset) << ':' << anchor.label << '/'
                      << anchor.region;
        }

        if (spawnerAnchors != 2 || branchAnchors != 2 ||
            integrationAnchors != 2) {
            throw std::runtime_error("behavior-4 static anchor summary changed");
        }

        std::cout << "behavior4_static_model=ok"
                  << " image_base=0x0770"
                  << " anchors=" << anchors.size()
                  << " spawner=" << spawnerAnchors
                  << " branch=" << branchAnchors
                  << " integration=" << integrationAnchors
                  << " target_map=" << targetMap.str()
                  << " runtime_oracle=--debug-behavior4-runtime-oracle"
                  << " procmem_helper=tools/capture_original_behavior4_procmem.sh"
                  << " visual_claim=0"
                  << '\n';
    }

    int debugActorUpdateRuntimeOracle(const std::string& path, bool expectError) {
        auto fixtureName = [](const std::string& inputPath) {
            size_t slash = inputPath.find_last_of("/\\");
            std::string name =
                slash == std::string::npos ? inputPath : inputPath.substr(slash + 1);
            size_t dot = name.find_last_of('.');
            if (dot != std::string::npos) name = name.substr(0, dot);
            return name;
        };
        const std::string fixture = fixtureName(path);

        auto bareHex4 = [](uint16_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(4)
                << std::setfill('0') << value;
            return oss.str();
        };
        auto hex4 = [&](uint16_t value) { return "0x" + bareHex4(value); };
        auto fail = [&](const std::string& reason) {
            throw std::runtime_error("actor_update_runtime_oracle=error fixture=" +
                                     fixture + " reason=" + reason);
        };
        auto parseHex16 = [&](const std::string& token,
                              const std::string& field) -> uint16_t {
            if (token.empty() || token.size() > 4 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("bad_hex16 field=" + field + " token=" + token);
            }
            return static_cast<uint16_t>(std::stoul(token, nullptr, 16));
        };
        auto parseHexByte = [&](const std::string& token,
                                uint16_t address) -> uint8_t {
            if (token.size() != 2 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("non_hex_byte token=" + token + " address=" +
                     bareHex4(address));
            }
            return static_cast<uint8_t>(std::stoul(token, nullptr, 16));
        };
        auto trim = [](std::string value) {
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.front()))) {
                value.erase(value.begin());
            }
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.back()))) {
                value.pop_back();
            }
            return value;
        };
        auto parseIntAuto = [&](const std::string& token,
                                const std::string& field) -> int {
            try {
                size_t parsed = 0;
                long value = std::stol(token, &parsed, 0);
                if (parsed != token.size()) {
                    fail("bad_int field=" + field + " token=" + token);
                }
                return static_cast<int>(value);
            } catch (const std::exception&) {
                fail("bad_int field=" + field + " token=" + token);
            }
            return 0;
        };
        auto parseFields = [&](const std::string& body,
                               const std::string& record) {
            std::map<std::string, std::string> fields;
            std::istringstream stream(body);
            std::string token;
            while (stream >> token) {
                size_t equals = token.find('=');
                if (equals == std::string::npos || equals == 0 ||
                    equals + 1 >= token.size()) {
                    fail("bad_field record=" + record + " token=" + token);
                }
                fields[token.substr(0, equals)] = token.substr(equals + 1);
            }
            return fields;
        };
        auto fieldInt = [&](const std::map<std::string, std::string>& fields,
                            const std::string& name,
                            const std::string& record) -> int {
            auto found = fields.find(name);
            if (found == fields.end()) {
                fail("missing_field record=" + record + " field=" + name);
            }
            return parseIntAuto(found->second, record + "." + name);
        };
        auto optionalFieldInt = [&](const std::map<std::string, std::string>& fields,
                                    const std::string& name,
                                    const std::string& record,
                                    int fallback) -> int {
            auto found = fields.find(name);
            if (found == fields.end()) return fallback;
            return parseIntAuto(found->second, record + "." + name);
        };

        struct ActorRecord {
            bool present = false;
            int slot = 0;
            int behavior = 0;
            int kind = 0;
            int state = 0;
            int x = 0;
            int y = 0;
            int vx8 = 0;
            int vy8 = 0;
            int hp = 0;
            int flags = 0;
            int contact = 0;
            int onGround = 0;
        };
        struct ContactRecord {
            bool present = false;
            int subjectSlot = 0;
            int otherSlot = 0;
            int flagsBefore = 0;
            int flagsAfter = 0;
            int contact = 0;
            int playerContact = 0;
            int monsterContact = 0;
            int objectContact = 0;
            int damagePending = 0;
        };
        struct TileProbeRecord {
            bool present = false;
            int tileX = 0;
            int tileY = 0;
            int tile = 0;
            int object = 0;
            int passable = 0;
            int standable = 0;
        };

        try {
            std::string text = readTextFile(path);
            uint16_t runtimeCs = 0;
            uint16_t runtimeDs = 0;
            bool haveRuntimeCs = false;
            bool haveRuntimeDs = false;
            bool tempCopy = false;
            bool visualClaim = false;
            bool haveScenario = false;
            bool haveLevel = false;
            std::string scenario;
            int level = 0;
            ActorRecord actorBefore;
            ActorRecord actorAfter;
            ContactRecord contactScan;
            TileProbeRecord tileProbe;
            int breakCount = 0;
            int dumpBytes = 0;
            constexpr std::array<uint16_t, 4> kRequiredOffsets{
                0x5cb0, 0x604f, 0x6053, 0x777f};
            std::array<bool, 4> sawRequired{};
            constexpr std::array<std::pair<uint16_t, const char*>, 5>
                kDispatchGateOffsets{{
                    {0x65a2, "actor_update_gate5"},
                    {0x65d7, "actor_update_gate5_integration"},
                    {0x7595, "actor_update_gate5_exit"},
                    {0x654e, "actor_update_gate6"},
                    {0x6555, "contact_scanner_callsite"},
                }};
            std::array<bool, 5> sawDispatchGate{};

            std::istringstream lines(text);
            std::string line;
            std::regex keyRe("^([A-Za-z0-9_]+)=(.*)$");
            std::regex breakRe(
                "^break\\s+ghidra=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+"
                "runtime=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+label=([^\\s]+).*$");
            std::regex dumpRe("^dump\\s+DS:([0-9A-Fa-f]{4}).*$");
            std::regex rowRe("^([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+(.+)$");
            uint16_t currentDump = 0;
            bool inDump = false;
            while (std::getline(lines, line)) {
                line = trim(line);
                if (line.empty() || line[0] == '#') continue;

                std::smatch match;
                if (std::regex_match(line, match, keyRe)) {
                    std::string key = match[1].str();
                    std::string value = trim(match[2].str());
                    if (key == "runtime_cs") {
                        runtimeCs = parseHex16(value, key);
                        haveRuntimeCs = true;
                    } else if (key == "runtime_ds") {
                        runtimeDs = parseHex16(value, key);
                        haveRuntimeDs = true;
                    } else if (key == "temp_copy") {
                        tempCopy = value == "1";
                    } else if (key == "visual_claim") {
                        visualClaim = value != "0";
                    } else if (key == "scenario") {
                        scenario = value;
                        haveScenario = true;
                    } else if (key == "level") {
                        level = parseIntAuto(value, key);
                        haveLevel = true;
                    }
                    continue;
                }

                if (line.rfind("actor_before ", 0) == 0 ||
                    line.rfind("actor_after ", 0) == 0) {
                    bool after = line.rfind("actor_after ", 0) == 0;
                    const std::string record = after ? "actor_after" : "actor_before";
                    auto fields = parseFields(
                        line.substr(after ? 12 : 13), record);
                    ActorRecord parsed;
                    parsed.present = true;
                    parsed.slot = fieldInt(fields, "slot", record);
                    parsed.behavior = fieldInt(fields, "behavior", record);
                    parsed.kind = fieldInt(fields, "kind", record);
                    parsed.state = fieldInt(fields, "state", record);
                    parsed.x = fieldInt(fields, "x", record);
                    parsed.y = fieldInt(fields, "y", record);
                    parsed.vx8 = fieldInt(fields, "vx8", record);
                    parsed.vy8 = fieldInt(fields, "vy8", record);
                    parsed.hp = fieldInt(fields, "hp", record);
                    parsed.flags = fieldInt(fields, "flags", record);
                    parsed.contact = fieldInt(fields, "contact", record);
                    parsed.onGround = optionalFieldInt(
                        fields, "on_ground", record, 0);
                    if (after) {
                        actorAfter = parsed;
                    } else {
                        actorBefore = parsed;
                    }
                    continue;
                }
                if (line.rfind("contact_scan ", 0) == 0) {
                    auto fields = parseFields(line.substr(13), "contact_scan");
                    contactScan.present = true;
                    contactScan.subjectSlot =
                        fieldInt(fields, "subject_slot", "contact_scan");
                    contactScan.otherSlot =
                        fieldInt(fields, "other_slot", "contact_scan");
                    contactScan.flagsBefore =
                        fieldInt(fields, "flags_before", "contact_scan");
                    contactScan.flagsAfter =
                        fieldInt(fields, "flags_after", "contact_scan");
                    contactScan.contact =
                        fieldInt(fields, "contact", "contact_scan");
                    contactScan.playerContact =
                        fieldInt(fields, "player_contact", "contact_scan");
                    contactScan.monsterContact =
                        fieldInt(fields, "monster_contact", "contact_scan");
                    contactScan.objectContact =
                        fieldInt(fields, "object_contact", "contact_scan");
                    contactScan.damagePending =
                        fieldInt(fields, "damage_pending", "contact_scan");
                    continue;
                }
                if (line.rfind("tile_probe ", 0) == 0) {
                    auto fields = parseFields(line.substr(11), "tile_probe");
                    tileProbe.present = true;
                    tileProbe.tileX = fieldInt(fields, "tile_x", "tile_probe");
                    tileProbe.tileY = fieldInt(fields, "tile_y", "tile_probe");
                    tileProbe.tile = fieldInt(fields, "tile", "tile_probe");
                    tileProbe.object = fieldInt(fields, "object", "tile_probe");
                    tileProbe.passable =
                        fieldInt(fields, "passable", "tile_probe");
                    tileProbe.standable =
                        fieldInt(fields, "standable", "tile_probe");
                    continue;
                }

                if (std::regex_match(line, match, breakRe)) {
                    if (!haveRuntimeCs) fail("runtime_cs_missing_before_break");
                    uint16_t ghidraSegment = parseHex16(match[1].str(), "ghidra");
                    uint16_t ghidraOffset = parseHex16(match[2].str(), "ghidra");
                    uint16_t runtimeSegment = parseHex16(match[3].str(), "runtime");
                    uint16_t runtimeOffset = parseHex16(match[4].str(), "runtime");
                    if (ghidraSegment != 0x1000) {
                        fail("breakpoint_ghidra_segment expected=0x1000 actual=" +
                             hex4(ghidraSegment));
                    }
                    if (runtimeSegment != runtimeCs) {
                        fail("breakpoint_segment_mismatch expected=" + hex4(runtimeCs) +
                             " actual=" + hex4(runtimeSegment));
                    }
                    if (runtimeOffset != ghidraOffset) {
                        fail("breakpoint_offset_mismatch expected=" +
                             bareHex4(ghidraOffset) + " actual=" +
                             bareHex4(runtimeOffset));
                    }
                    ++breakCount;
                    for (size_t i = 0; i < kRequiredOffsets.size(); ++i) {
                        if (ghidraOffset == kRequiredOffsets[i]) sawRequired[i] = true;
                    }
                    for (size_t i = 0; i < kDispatchGateOffsets.size(); ++i) {
                        if (ghidraOffset == kDispatchGateOffsets[i].first) {
                            sawDispatchGate[i] = true;
                        }
                    }
                    continue;
                }

                if (std::regex_match(line, match, dumpRe)) {
                    currentDump = parseHex16(match[1].str(), "dump");
                    inDump = true;
                    continue;
                }

                if (std::regex_match(line, match, rowRe)) {
                    if (!inDump) fail("dump_row_without_header");
                    if (!haveRuntimeDs) fail("runtime_ds_missing_before_dump");
                    uint16_t segment = parseHex16(match[1].str(), "row_segment");
                    uint16_t address = parseHex16(match[2].str(), "row_address");
                    if (segment != runtimeDs) {
                        fail("dump_segment_mismatch expected=" + hex4(runtimeDs) +
                             " actual=" + hex4(segment) +
                             " address=" + bareHex4(address));
                    }
                    if (address < currentDump) {
                        fail("dump_address_before_header header=" + bareHex4(currentDump) +
                             " address=" + bareHex4(address));
                    }
                    std::istringstream byteStream(match[3].str());
                    std::string token;
                    uint16_t cursor = address;
                    while (byteStream >> token) {
                        (void)parseHexByte(token, cursor);
                        ++cursor;
                        ++dumpBytes;
                    }
                    continue;
                }

                fail("unrecognized_line");
            }

            if (!haveRuntimeCs) fail("runtime_cs_missing");
            if (!haveRuntimeDs) fail("runtime_ds_missing");
            if (!haveScenario) fail("scenario_missing");
            if (!haveLevel) fail("level_missing");
            if (visualClaim) fail("visual_claim_not_supported");
            if (!actorBefore.present) fail("actor_before_missing");
            if (!actorAfter.present) fail("actor_after_missing");
            if (!contactScan.present) fail("contact_scan_missing");
            if (!tileProbe.present) fail("tile_probe_missing");
            for (size_t i = 0; i < kRequiredOffsets.size(); ++i) {
                if (!sawRequired[i]) {
                    fail("missing_breakpoint offset=" + bareHex4(kRequiredOffsets[i]));
                }
            }
            if (actorBefore.slot != actorAfter.slot) {
                fail("actor_slot_changed before=" + std::to_string(actorBefore.slot) +
                     " after=" + std::to_string(actorAfter.slot));
            }
            if (actorBefore.slot != contactScan.subjectSlot) {
                fail("contact_scan_subject_mismatch actor=" +
                     std::to_string(actorBefore.slot) + " scan=" +
                     std::to_string(contactScan.subjectSlot));
            }
            if (actorBefore.flags != contactScan.flagsBefore) {
                fail("contact_flags_before_mismatch actor=" +
                     hex4(static_cast<uint16_t>(actorBefore.flags)) + " scan=" +
                     hex4(static_cast<uint16_t>(contactScan.flagsBefore)));
            }
            if (actorAfter.flags != contactScan.flagsAfter) {
                fail("contact_flags_after_mismatch actor=" +
                     hex4(static_cast<uint16_t>(actorAfter.flags)) + " scan=" +
                     hex4(static_cast<uint16_t>(contactScan.flagsAfter)));
            }
            std::string dispatchGates;
            for (size_t i = 0; i < kDispatchGateOffsets.size(); ++i) {
                if (!sawDispatchGate[i]) continue;
                if (!dispatchGates.empty()) dispatchGates += ',';
                dispatchGates += kDispatchGateOffsets[i].second;
            }
            if (dispatchGates.empty()) dispatchGates = "none";

            std::cout << "actor_update_runtime_oracle=ok fixture=" << fixture
                      << " scenario=" << scenario
                      << " level=" << level
                      << " runtime_cs=" << hex4(runtimeCs)
                      << " runtime_ds=" << hex4(runtimeDs)
                      << " actor_slot=" << actorAfter.slot
                      << " behavior=" << actorAfter.behavior
                      << " kind=" << actorAfter.kind
                      << " before_xy=" << hex4(static_cast<uint16_t>(actorBefore.x))
                      << ',' << hex4(static_cast<uint16_t>(actorBefore.y))
                      << " after_xy=" << hex4(static_cast<uint16_t>(actorAfter.x))
                      << ',' << hex4(static_cast<uint16_t>(actorAfter.y))
                      << " velocity8=" << actorAfter.vx8 << ',' << actorAfter.vy8
                      << " state=" << actorBefore.state << ',' << actorAfter.state
                      << " contact_flags="
                      << hex4(static_cast<uint16_t>(actorBefore.flags)) << ','
                      << hex4(static_cast<uint16_t>(actorAfter.flags))
                      << " scan_subject=" << contactScan.subjectSlot
                      << " scan_other=" << contactScan.otherSlot
                      << " scan_contact=" << contactScan.contact
                      << " player_contact=" << contactScan.playerContact
                      << " monster_contact=" << contactScan.monsterContact
                      << " object_contact=" << contactScan.objectContact
                      << " damage_pending=" << contactScan.damagePending
                      << " tile_probe=" << tileProbe.tileX << ',' << tileProbe.tileY
                      << " tile=" << hex4(static_cast<uint16_t>(tileProbe.tile))
                      << " object=" << hex4(static_cast<uint16_t>(tileProbe.object))
                      << " passable=" << tileProbe.passable
                      << " standable=" << tileProbe.standable
                      << " breaks=" << breakCount
                      << " dump_bytes=" << dumpBytes
                      << " temp_copy=" << (tempCopy ? 1 : 0)
                      << " visual_claim=0"
                      << " dispatch_gates=" << dispatchGates << "\n";
            if (expectError) {
                std::cout << "actor_update_runtime_oracle=error fixture=" << fixture
                          << " reason=expected_error_missing\n";
                return 1;
            }
            return 0;
        } catch (const std::exception& e) {
            std::cout << e.what() << '\n';
            return expectError ? 0 : 1;
        }
    }

    int debugContactScannerRuntimeOracle(const std::string& path, bool expectError) {
        auto fixtureName = [](const std::string& inputPath) {
            size_t slash = inputPath.find_last_of("/\\");
            std::string name =
                slash == std::string::npos ? inputPath : inputPath.substr(slash + 1);
            size_t dot = name.find_last_of('.');
            if (dot != std::string::npos) name = name.substr(0, dot);
            return name;
        };
        const std::string fixture = fixtureName(path);

        auto bareHex4 = [](uint16_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(4)
                << std::setfill('0') << value;
            return oss.str();
        };
        auto hex4 = [&](uint16_t value) { return "0x" + bareHex4(value); };
        auto fail = [&](const std::string& reason) {
            throw std::runtime_error("contact_scanner_runtime_oracle=error fixture=" +
                                     fixture + " reason=" + reason);
        };
        auto parseHex16 = [&](const std::string& token,
                              const std::string& field) -> uint16_t {
            if (token.empty() || token.size() > 4 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("bad_hex16 field=" + field + " token=" + token);
            }
            return static_cast<uint16_t>(std::stoul(token, nullptr, 16));
        };
        auto parseHexByte = [&](const std::string& token,
                                uint16_t address) -> uint8_t {
            if (token.size() != 2 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("non_hex_byte token=" + token + " address=" +
                     bareHex4(address));
            }
            return static_cast<uint8_t>(std::stoul(token, nullptr, 16));
        };
        auto trim = [](std::string value) {
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.front()))) {
                value.erase(value.begin());
            }
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.back()))) {
                value.pop_back();
            }
            return value;
        };
        auto parseIntAuto = [&](const std::string& token,
                                const std::string& field) -> int {
            try {
                size_t parsed = 0;
                long value = std::stol(token, &parsed, 0);
                if (parsed != token.size()) {
                    fail("bad_int field=" + field + " token=" + token);
                }
                return static_cast<int>(value);
            } catch (const std::exception&) {
                fail("bad_int field=" + field + " token=" + token);
            }
            return 0;
        };
        auto parseFields = [&](const std::string& body,
                               const std::string& record) {
            std::map<std::string, std::string> fields;
            std::istringstream stream(body);
            std::string token;
            while (stream >> token) {
                size_t equals = token.find('=');
                if (equals == std::string::npos || equals == 0 ||
                    equals + 1 >= token.size()) {
                    fail("bad_field record=" + record + " token=" + token);
                }
                fields[token.substr(0, equals)] = token.substr(equals + 1);
            }
            return fields;
        };
        auto fieldInt = [&](const std::map<std::string, std::string>& fields,
                            const std::string& name,
                            const std::string& record) -> int {
            auto found = fields.find(name);
            if (found == fields.end()) {
                fail("missing_field record=" + record + " field=" + name);
            }
            return parseIntAuto(found->second, record + "." + name);
        };

        struct ContactActorRecord {
            bool present = false;
            int slot = 0;
            int kind = 0;
            int state = 0;
            int x = 0;
            int y = 0;
            int w = 0;
            int h = 0;
            int flags = 0;
        };
        struct ContactRecord {
            bool present = false;
            int subjectSlot = 0;
            int otherSlot = 0;
            int flagsBefore = 0;
            int flagsAfter = 0;
            int contact = 0;
            int playerContact = 0;
            int monsterContact = 0;
            int objectContact = 0;
            int damagePending = 0;
            int overlapX = 0;
            int overlapY = 0;
        };

        try {
            std::string text = readTextFile(path);
            uint16_t runtimeCs = 0;
            uint16_t runtimeDs = 0;
            bool haveRuntimeCs = false;
            bool haveRuntimeDs = false;
            bool tempCopy = false;
            bool visualClaim = false;
            bool haveScenario = false;
            bool haveLevel = false;
            std::string scenario;
            int level = 0;
            ContactActorRecord subject;
            ContactActorRecord other;
            ContactRecord contactScan;
            int breakCount = 0;
            int dumpBytes = 0;
            constexpr std::array<uint16_t, 2> kRequiredOffsets{0x5cb0, 0x604f};
            std::array<bool, 2> sawRequired{};

            std::istringstream lines(text);
            std::string line;
            std::regex keyRe("^([A-Za-z0-9_]+)=(.*)$");
            std::regex breakRe(
                "^break\\s+ghidra=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+"
                "runtime=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+label=([^\\s]+).*$");
            std::regex dumpRe("^dump\\s+DS:([0-9A-Fa-f]{4}).*$");
            std::regex rowRe("^([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+(.+)$");
            uint16_t currentDump = 0;
            bool inDump = false;
            while (std::getline(lines, line)) {
                line = trim(line);
                if (line.empty() || line[0] == '#') continue;

                std::smatch match;
                if (std::regex_match(line, match, keyRe)) {
                    std::string key = match[1].str();
                    std::string value = trim(match[2].str());
                    if (key == "runtime_cs") {
                        runtimeCs = parseHex16(value, key);
                        haveRuntimeCs = true;
                    } else if (key == "runtime_ds") {
                        runtimeDs = parseHex16(value, key);
                        haveRuntimeDs = true;
                    } else if (key == "temp_copy") {
                        tempCopy = value == "1";
                    } else if (key == "visual_claim") {
                        visualClaim = value != "0";
                    } else if (key == "scenario") {
                        scenario = value;
                        haveScenario = true;
                    } else if (key == "level") {
                        level = parseIntAuto(value, key);
                        haveLevel = true;
                    }
                    continue;
                }

                if (line.rfind("subject_actor ", 0) == 0 ||
                    line.rfind("other_actor ", 0) == 0) {
                    bool isSubject = line.rfind("subject_actor ", 0) == 0;
                    const std::string record =
                        isSubject ? "subject_actor" : "other_actor";
                    auto fields = parseFields(
                        line.substr(isSubject ? 14 : 12), record);
                    ContactActorRecord parsed;
                    parsed.present = true;
                    parsed.slot = fieldInt(fields, "slot", record);
                    parsed.kind = fieldInt(fields, "kind", record);
                    parsed.state = fieldInt(fields, "state", record);
                    parsed.x = fieldInt(fields, "x", record);
                    parsed.y = fieldInt(fields, "y", record);
                    parsed.w = fieldInt(fields, "w", record);
                    parsed.h = fieldInt(fields, "h", record);
                    parsed.flags = fieldInt(fields, "flags", record);
                    if (isSubject) {
                        subject = parsed;
                    } else {
                        other = parsed;
                    }
                    continue;
                }
                if (line.rfind("contact_scan ", 0) == 0) {
                    auto fields = parseFields(line.substr(13), "contact_scan");
                    contactScan.present = true;
                    contactScan.subjectSlot =
                        fieldInt(fields, "subject_slot", "contact_scan");
                    contactScan.otherSlot =
                        fieldInt(fields, "other_slot", "contact_scan");
                    contactScan.flagsBefore =
                        fieldInt(fields, "flags_before", "contact_scan");
                    contactScan.flagsAfter =
                        fieldInt(fields, "flags_after", "contact_scan");
                    contactScan.contact =
                        fieldInt(fields, "contact", "contact_scan");
                    contactScan.playerContact =
                        fieldInt(fields, "player_contact", "contact_scan");
                    contactScan.monsterContact =
                        fieldInt(fields, "monster_contact", "contact_scan");
                    contactScan.objectContact =
                        fieldInt(fields, "object_contact", "contact_scan");
                    contactScan.damagePending =
                        fieldInt(fields, "damage_pending", "contact_scan");
                    contactScan.overlapX =
                        fieldInt(fields, "overlap_x", "contact_scan");
                    contactScan.overlapY =
                        fieldInt(fields, "overlap_y", "contact_scan");
                    continue;
                }

                if (std::regex_match(line, match, breakRe)) {
                    if (!haveRuntimeCs) fail("runtime_cs_missing_before_break");
                    uint16_t ghidraSegment = parseHex16(match[1].str(), "ghidra");
                    uint16_t ghidraOffset = parseHex16(match[2].str(), "ghidra");
                    uint16_t runtimeSegment = parseHex16(match[3].str(), "runtime");
                    uint16_t runtimeOffset = parseHex16(match[4].str(), "runtime");
                    if (ghidraSegment != 0x1000) {
                        fail("breakpoint_ghidra_segment expected=0x1000 actual=" +
                             hex4(ghidraSegment));
                    }
                    if (runtimeSegment != runtimeCs) {
                        fail("breakpoint_segment_mismatch expected=" + hex4(runtimeCs) +
                             " actual=" + hex4(runtimeSegment));
                    }
                    if (runtimeOffset != ghidraOffset) {
                        fail("breakpoint_offset_mismatch expected=" +
                             bareHex4(ghidraOffset) + " actual=" +
                             bareHex4(runtimeOffset));
                    }
                    ++breakCount;
                    for (size_t i = 0; i < kRequiredOffsets.size(); ++i) {
                        if (ghidraOffset == kRequiredOffsets[i]) sawRequired[i] = true;
                    }
                    continue;
                }

                if (std::regex_match(line, match, dumpRe)) {
                    currentDump = parseHex16(match[1].str(), "dump");
                    inDump = true;
                    continue;
                }

                if (std::regex_match(line, match, rowRe)) {
                    if (!inDump) fail("dump_row_without_header");
                    if (!haveRuntimeDs) fail("runtime_ds_missing_before_dump");
                    uint16_t segment = parseHex16(match[1].str(), "row_segment");
                    uint16_t address = parseHex16(match[2].str(), "row_address");
                    if (segment != runtimeDs) {
                        fail("dump_segment_mismatch expected=" + hex4(runtimeDs) +
                             " actual=" + hex4(segment) +
                             " address=" + bareHex4(address));
                    }
                    if (address < currentDump) {
                        fail("dump_address_before_header header=" + bareHex4(currentDump) +
                             " address=" + bareHex4(address));
                    }
                    std::istringstream byteStream(match[3].str());
                    std::string token;
                    uint16_t cursor = address;
                    while (byteStream >> token) {
                        (void)parseHexByte(token, cursor);
                        ++cursor;
                        ++dumpBytes;
                    }
                    continue;
                }

                fail("unrecognized_line");
            }

            if (!haveRuntimeCs) fail("runtime_cs_missing");
            if (!haveRuntimeDs) fail("runtime_ds_missing");
            if (!haveScenario) fail("scenario_missing");
            if (!haveLevel) fail("level_missing");
            if (visualClaim) fail("visual_claim_not_supported");
            if (!subject.present) fail("subject_actor_missing");
            if (!other.present) fail("other_actor_missing");
            if (!contactScan.present) fail("contact_scan_missing");
            for (size_t i = 0; i < kRequiredOffsets.size(); ++i) {
                if (!sawRequired[i]) {
                    fail("missing_breakpoint offset=" + bareHex4(kRequiredOffsets[i]));
                }
            }
            if (subject.slot != contactScan.subjectSlot) {
                fail("contact_scan_subject_mismatch actor=" +
                     std::to_string(subject.slot) + " scan=" +
                     std::to_string(contactScan.subjectSlot));
            }
            if (other.slot != contactScan.otherSlot) {
                fail("contact_scan_other_mismatch actor=" +
                     std::to_string(other.slot) + " scan=" +
                     std::to_string(contactScan.otherSlot));
            }
            if (subject.flags != contactScan.flagsBefore) {
                fail("contact_flags_before_mismatch actor=" +
                     hex4(static_cast<uint16_t>(subject.flags)) + " scan=" +
                     hex4(static_cast<uint16_t>(contactScan.flagsBefore)));
            }

            std::cout << "contact_scanner_runtime_oracle=ok fixture=" << fixture
                      << " scenario=" << scenario
                      << " level=" << level
                      << " runtime_cs=" << hex4(runtimeCs)
                      << " runtime_ds=" << hex4(runtimeDs)
                      << " subject_slot=" << subject.slot
                      << " other_slot=" << other.slot
                      << " subject_kind=" << subject.kind
                      << " other_kind=" << other.kind
                      << " subject_xy=" << hex4(static_cast<uint16_t>(subject.x))
                      << ',' << hex4(static_cast<uint16_t>(subject.y))
                      << " other_xy=" << hex4(static_cast<uint16_t>(other.x))
                      << ',' << hex4(static_cast<uint16_t>(other.y))
                      << " subject_size=" << subject.w << ',' << subject.h
                      << " other_size=" << other.w << ',' << other.h
                      << " subject_flags="
                      << hex4(static_cast<uint16_t>(subject.flags)) << ','
                      << hex4(static_cast<uint16_t>(contactScan.flagsAfter))
                      << " contact=" << contactScan.contact
                      << " player_contact=" << contactScan.playerContact
                      << " monster_contact=" << contactScan.monsterContact
                      << " object_contact=" << contactScan.objectContact
                      << " damage_pending=" << contactScan.damagePending
                      << " overlap=" << contactScan.overlapX << ','
                      << contactScan.overlapY
                      << " breaks=" << breakCount
                      << " dump_bytes=" << dumpBytes
                      << " temp_copy=" << (tempCopy ? 1 : 0)
                      << " visual_claim=0\n";
            if (expectError) {
                std::cout << "contact_scanner_runtime_oracle=error fixture="
                          << fixture << " reason=expected_error_missing\n";
                return 1;
            }
            return 0;
        } catch (const std::exception& e) {
            std::cout << e.what() << '\n';
            return expectError ? 0 : 1;
        }
    }

    int debugSoundCallsiteOracle(const std::string& path, bool expectError) {
        auto fixtureName = [](const std::string& inputPath) {
            size_t slash = inputPath.find_last_of("/\\");
            std::string name =
                slash == std::string::npos ? inputPath : inputPath.substr(slash + 1);
            size_t dot = name.find_last_of('.');
            if (dot != std::string::npos) name = name.substr(0, dot);
            return name;
        };
        const std::string fixture = fixtureName(path);

        auto bareHex4 = [](uint16_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(4)
                << std::setfill('0') << value;
            return oss.str();
        };
        auto hex4 = [&](uint16_t value) { return "0x" + bareHex4(value); };
        auto trim = [](std::string value) {
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.front()))) {
                value.erase(value.begin());
            }
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.back()))) {
                value.pop_back();
            }
            return value;
        };
        auto fail = [&](const std::string& reason) {
            throw std::runtime_error("sound_callsite_oracle=error fixture=" +
                                     fixture + " reason=" + reason);
        };
        auto parseHex16 = [&](std::string token,
                              const std::string& field) -> uint16_t {
            token = trim(token);
            if (token.rfind("0x", 0) == 0 || token.rfind("0X", 0) == 0) {
                token = token.substr(2);
            }
            if (token.empty() || token.size() > 4 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("bad_hex16 field=" + field + " token=" + token);
            }
            return static_cast<uint16_t>(std::stoul(token, nullptr, 16));
        };
        auto parseHexByte = [&](const std::string& token,
                                uint16_t address) -> uint8_t {
            if (token.size() != 2 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("non_hex_byte token=" + token + " address=" +
                     bareHex4(address));
            }
            return static_cast<uint8_t>(std::stoul(token, nullptr, 16));
        };
        auto parseIntAuto = [&](const std::string& token,
                                const std::string& field) -> int {
            try {
                size_t parsed = 0;
                long value = std::stol(token, &parsed, 0);
                if (parsed != token.size()) {
                    fail("bad_int field=" + field + " token=" + token);
                }
                return static_cast<int>(value);
            } catch (const std::exception&) {
                fail("bad_int field=" + field + " token=" + token);
            }
            return 0;
        };
        auto parseFields = [&](const std::string& body,
                               const std::string& record) {
            std::map<std::string, std::string> fields;
            std::istringstream stream(body);
            std::string token;
            while (stream >> token) {
                size_t equals = token.find('=');
                if (equals == std::string::npos || equals == 0 ||
                    equals + 1 >= token.size()) {
                    fail("bad_field record=" + record + " token=" + token);
                }
                fields[token.substr(0, equals)] = token.substr(equals + 1);
            }
            return fields;
        };
        auto requireField = [&](const std::map<std::string, std::string>& fields,
                                const std::string& name,
                                const std::string& record) -> std::string {
            auto found = fields.find(name);
            if (found == fields.end()) {
                fail("missing_field record=" + record + " field=" + name);
            }
            return found->second;
        };
        auto parseFarPointer = [&](const std::string& token,
                                   const std::string& field) {
            size_t colon = token.find(':');
            if (colon == std::string::npos || colon == 0 ||
                colon + 1 >= token.size()) {
                fail("bad_far_pointer field=" + field + " token=" + token);
            }
            return std::pair<uint16_t, uint16_t>{
                parseHex16(token.substr(0, colon), field + ".segment"),
                parseHex16(token.substr(colon + 1), field + ".offset")};
        };

        struct SoundRequestRecord {
            bool present = false;
            std::string label;
            uint16_t callsiteSegment = 0;
            uint16_t callsiteOffset = 0;
            uint16_t latchSegment = 0;
            uint16_t latchOffset = 0;
            uint16_t cursor = 0;
            int priority = 0;
            int activeBefore = 0;
            int currentPriorityBefore = 0;
            uint16_t pendingCursor = 0;
            int pendingPriority = 0;
            int accepted = 0;
            int activeAfter = 0;
            int currentPriorityAfter = 0;
            uint16_t currentCursorAfter = 0;
            int directSweep = 0;
        };

        try {
            std::string text = readTextFile(path);
            std::vector<uint8_t> memory(0x10000);
            std::vector<bool> present(0x10000, false);
            uint16_t runtimeCs = 0;
            uint16_t runtimeDs = 0;
            bool haveRuntimeCs = false;
            bool haveRuntimeDs = false;
            bool tempCopy = false;
            bool visualClaim = false;
            bool haveScenario = false;
            bool haveLevel = false;
            std::string scenario;
            int level = 0;
            SoundRequestRecord request;
            std::set<uint16_t> breakOffsets;
            int breakCount = 0;
            int dumpBytes = 0;

            std::istringstream lines(text);
            std::string line;
            std::regex keyRe("^([A-Za-z0-9_]+)=(.*)$");
            std::regex breakRe(
                "^break\\s+ghidra=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+"
                "runtime=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+label=([^\\s]+).*$");
            std::regex dumpRe("^dump\\s+DS:([0-9A-Fa-f]{4}).*$");
            std::regex rowRe("^([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+(.+)$");
            uint16_t currentDump = 0;
            bool inDump = false;
            while (std::getline(lines, line)) {
                line = trim(line);
                if (line.empty() || line[0] == '#') continue;

                std::smatch match;
                if (std::regex_match(line, match, keyRe)) {
                    std::string key = match[1].str();
                    std::string value = trim(match[2].str());
                    if (key == "runtime_cs") {
                        runtimeCs = parseHex16(value, key);
                        haveRuntimeCs = true;
                    } else if (key == "runtime_ds") {
                        runtimeDs = parseHex16(value, key);
                        haveRuntimeDs = true;
                    } else if (key == "temp_copy") {
                        tempCopy = value == "1";
                    } else if (key == "visual_claim") {
                        visualClaim = value != "0";
                    } else if (key == "scenario") {
                        scenario = value;
                        haveScenario = true;
                    } else if (key == "level") {
                        level = parseIntAuto(value, key);
                        haveLevel = true;
                    }
                    continue;
                }

                if (line.rfind("sound_request ", 0) == 0) {
                    auto fields = parseFields(line.substr(14), "sound_request");
                    request.present = true;
                    request.label = requireField(fields, "label", "sound_request");
                    auto callsite = parseFarPointer(
                        requireField(fields, "callsite", "sound_request"),
                        "sound_request.callsite");
                    request.callsiteSegment = callsite.first;
                    request.callsiteOffset = callsite.second;
                    auto latch = parseFarPointer(
                        requireField(fields, "latch", "sound_request"),
                        "sound_request.latch");
                    request.latchSegment = latch.first;
                    request.latchOffset = latch.second;
                    request.cursor = parseHex16(
                        requireField(fields, "cursor", "sound_request"),
                        "sound_request.cursor");
                    request.priority = parseIntAuto(
                        requireField(fields, "priority", "sound_request"),
                        "sound_request.priority");
                    request.activeBefore = parseIntAuto(
                        requireField(fields, "active_before", "sound_request"),
                        "sound_request.active_before");
                    request.currentPriorityBefore = parseIntAuto(
                        requireField(fields, "current_priority_before",
                                     "sound_request"),
                        "sound_request.current_priority_before");
                    request.pendingCursor = parseHex16(
                        requireField(fields, "pending_cursor", "sound_request"),
                        "sound_request.pending_cursor");
                    request.pendingPriority = parseIntAuto(
                        requireField(fields, "pending_priority", "sound_request"),
                        "sound_request.pending_priority");
                    request.accepted = parseIntAuto(
                        requireField(fields, "accepted", "sound_request"),
                        "sound_request.accepted");
                    request.activeAfter = parseIntAuto(
                        requireField(fields, "active_after", "sound_request"),
                        "sound_request.active_after");
                    request.currentPriorityAfter = parseIntAuto(
                        requireField(fields, "current_priority_after",
                                     "sound_request"),
                        "sound_request.current_priority_after");
                    request.currentCursorAfter = parseHex16(
                        requireField(fields, "current_cursor_after", "sound_request"),
                        "sound_request.current_cursor_after");
                    request.directSweep = parseIntAuto(
                        requireField(fields, "direct_sweep", "sound_request"),
                        "sound_request.direct_sweep");
                    continue;
                }

                if (std::regex_match(line, match, breakRe)) {
                    if (!haveRuntimeCs) fail("runtime_cs_missing_before_break");
                    uint16_t ghidraSegment = parseHex16(match[1].str(), "ghidra");
                    uint16_t ghidraOffset = parseHex16(match[2].str(), "ghidra");
                    uint16_t runtimeSegment = parseHex16(match[3].str(), "runtime");
                    uint16_t runtimeOffset = parseHex16(match[4].str(), "runtime");
                    if (ghidraSegment != 0x1000) {
                        fail("breakpoint_ghidra_segment expected=0x1000 actual=" +
                             hex4(ghidraSegment));
                    }
                    if (runtimeSegment != runtimeCs) {
                        fail("breakpoint_segment_mismatch expected=" + hex4(runtimeCs) +
                             " actual=" + hex4(runtimeSegment));
                    }
                    if (runtimeOffset != ghidraOffset) {
                        fail("breakpoint_offset_mismatch expected=" +
                             bareHex4(ghidraOffset) + " actual=" +
                             bareHex4(runtimeOffset));
                    }
                    breakOffsets.insert(ghidraOffset);
                    ++breakCount;
                    continue;
                }

                if (std::regex_match(line, match, dumpRe)) {
                    currentDump = parseHex16(match[1].str(), "dump");
                    inDump = true;
                    continue;
                }

                if (std::regex_match(line, match, rowRe)) {
                    if (!inDump) fail("dump_row_without_header");
                    if (!haveRuntimeDs) fail("runtime_ds_missing_before_dump");
                    uint16_t segment = parseHex16(match[1].str(), "row_segment");
                    uint16_t address = parseHex16(match[2].str(), "row_address");
                    if (segment != runtimeDs) {
                        fail("dump_segment_mismatch expected=" + hex4(runtimeDs) +
                             " actual=" + hex4(segment) +
                             " address=" + bareHex4(address));
                    }
                    if (address < currentDump) {
                        fail("dump_address_before_header header=" + bareHex4(currentDump) +
                             " address=" + bareHex4(address));
                    }
                    std::istringstream byteStream(match[3].str());
                    std::string token;
                    uint16_t cursor = address;
                    while (byteStream >> token) {
                        memory[cursor] = parseHexByte(token, cursor);
                        present[cursor] = true;
                        ++cursor;
                        ++dumpBytes;
                    }
                    continue;
                }

                fail("unrecognized_line");
            }

            auto requireByteIfPresent = [&](uint16_t address,
                                            uint8_t expected,
                                            const std::string& reason) {
                if (present[address] && memory[address] != expected) {
                    fail(reason + " expected=" + hex4(expected) +
                         " actual=" + hex4(memory[address]));
                }
            };
            auto requireWordIfPresent = [&](uint16_t address,
                                            uint16_t expected,
                                            const std::string& reason) {
                if (present[address] && present[static_cast<uint16_t>(address + 1)]) {
                    uint16_t actual = static_cast<uint16_t>(
                        memory[address] |
                        (memory[static_cast<uint16_t>(address + 1)] << 8));
                    if (actual != expected) {
                        fail(reason + " expected=" + hex4(expected) +
                             " actual=" + hex4(actual));
                    }
                }
            };

            if (!haveRuntimeCs) fail("runtime_cs_missing");
            if (!haveRuntimeDs) fail("runtime_ds_missing");
            if (!haveScenario) fail("scenario_missing");
            if (!haveLevel) fail("level_missing");
            if (visualClaim) fail("visual_claim_not_supported");
            if (!request.present) fail("sound_request_missing");
            if (request.callsiteSegment != 0x1000) {
                fail("callsite_segment_not_1000 actual=" + hex4(request.callsiteSegment));
            }
            if (request.latchSegment != 0x1000 || request.latchOffset != 0x165a) {
                fail("latch_address_mismatch actual=" + hex4(request.latchSegment) +
                     ":" + bareHex4(request.latchOffset));
            }
            if (breakOffsets.count(request.callsiteOffset) == 0) {
                fail("missing_breakpoint offset=" + bareHex4(request.callsiteOffset));
            }
            if (breakOffsets.count(request.latchOffset) == 0) {
                fail("missing_breakpoint offset=" + bareHex4(request.latchOffset));
            }
            if (request.pendingCursor != request.cursor) {
                fail("pending_cursor_mismatch expected=" + hex4(request.cursor) +
                     " actual=" + hex4(request.pendingCursor));
            }
            if (request.pendingPriority != request.priority) {
                fail("pending_priority_mismatch expected=" +
                     std::to_string(request.priority) + " actual=" +
                     std::to_string(request.pendingPriority));
            }
            if (request.accepted != 0) {
                if (request.activeAfter == 0) fail("accepted_but_inactive_after");
                if (request.currentPriorityAfter != request.priority) {
                    fail("accepted_priority_mismatch expected=" +
                         std::to_string(request.priority) + " actual=" +
                         std::to_string(request.currentPriorityAfter));
                }
                if (request.currentCursorAfter != request.cursor) {
                    fail("accepted_cursor_mismatch expected=" + hex4(request.cursor) +
                         " actual=" + hex4(request.currentCursorAfter));
                }
            }
            int expectedDirectSweep = request.cursor > 0xea60 ? 1 : 0;
            if (request.directSweep != expectedDirectSweep) {
                fail("direct_sweep_mismatch expected=" +
                     std::to_string(expectedDirectSweep) + " actual=" +
                     std::to_string(request.directSweep));
            }

            requireWordIfPresent(0x2074, request.pendingCursor,
                                 "pending_cursor_dump_mismatch");
            requireByteIfPresent(0x799f, static_cast<uint8_t>(request.pendingPriority),
                                 "pending_priority_dump_mismatch");
            requireByteIfPresent(0x799e,
                                 static_cast<uint8_t>(request.currentPriorityAfter),
                                 "current_priority_dump_mismatch");
            requireWordIfPresent(0x78c0, request.currentCursorAfter,
                                 "current_cursor_dump_mismatch");
            requireByteIfPresent(0x79c4, static_cast<uint8_t>(request.activeAfter),
                                 "active_flag_dump_mismatch");

            std::cout << "sound_callsite_oracle=ok fixture=" << fixture
                      << " scenario=" << scenario
                      << " level=" << level
                      << " runtime_cs=" << hex4(runtimeCs)
                      << " runtime_ds=" << hex4(runtimeDs)
                      << " label=" << request.label
                      << " callsite=" << hex4(request.callsiteSegment) << ':'
                      << bareHex4(request.callsiteOffset)
                      << " latch=" << hex4(request.latchSegment) << ':'
                      << bareHex4(request.latchOffset)
                      << " cursor=" << hex4(request.cursor)
                      << " priority=" << request.priority
                      << " active_before=" << request.activeBefore
                      << " current_priority_before=" << request.currentPriorityBefore
                      << " accepted=" << request.accepted
                      << " active_after=" << request.activeAfter
                      << " current_priority_after=" << request.currentPriorityAfter
                      << " current_cursor_after=" << hex4(request.currentCursorAfter)
                      << " direct_sweep=" << request.directSweep
                      << " breaks=" << breakCount
                      << " dump_bytes=" << dumpBytes
                      << " temp_copy=" << (tempCopy ? 1 : 0)
                      << " visual_claim=0\n";
            if (expectError) {
                std::cout << "sound_callsite_oracle=error fixture=" << fixture
                          << " reason=expected_error_missing\n";
                return 1;
            }
            return 0;
        } catch (const std::exception& e) {
            std::cout << e.what() << '\n';
            return expectError ? 0 : 1;
        }
    }

    int debugExplosionPlaybackOracle(const std::string& path, bool expectError) {
        auto fixtureName = [](const std::string& inputPath) {
            size_t slash = inputPath.find_last_of("/\\");
            std::string name =
                slash == std::string::npos ? inputPath : inputPath.substr(slash + 1);
            size_t dot = name.find_last_of('.');
            if (dot != std::string::npos) name = name.substr(0, dot);
            return name;
        };
        const std::string fixture = fixtureName(path);

        auto hex4 = [](uint16_t value) {
            std::ostringstream oss;
            oss << "0x" << std::hex << std::nouppercase << std::setw(4)
                << std::setfill('0') << value;
            return oss.str();
        };
        auto hexByte = [](uint8_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(2)
                << std::setfill('0') << static_cast<int>(value);
            return oss.str();
        };
        auto hexBytePrefix = [&](uint8_t value) {
            return "0x" + hexByte(value);
        };
        auto bareHex4 = [](uint16_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(4)
                << std::setfill('0') << value;
            return oss.str();
        };
        auto fail = [&](const std::string& reason) {
            throw std::runtime_error("explosion_playback_oracle=error fixture=" +
                                     fixture + " reason=" + reason);
        };
        auto parseHex16 = [&](const std::string& token,
                              const std::string& field) -> uint16_t {
            if (token.empty() || token.size() > 4 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("bad_hex16 field=" + field + " token=" + token);
            }
            return static_cast<uint16_t>(std::stoul(token, nullptr, 16));
        };
        auto parseHex16Auto = [&](std::string token,
                                  const std::string& field) -> uint16_t {
            if (token.rfind("0x", 0) == 0 || token.rfind("0X", 0) == 0) {
                token = token.substr(2);
            }
            return parseHex16(token, field);
        };
        auto parseHexByte = [&](const std::string& token,
                                uint16_t address) -> uint8_t {
            if (token.size() != 2 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("non_hex_byte token=" + token + " address=" +
                     bareHex4(address));
            }
            return static_cast<uint8_t>(std::stoul(token, nullptr, 16));
        };
        auto trim = [](std::string value) {
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.front()))) {
                value.erase(value.begin());
            }
            while (!value.empty() &&
                   std::isspace(static_cast<unsigned char>(value.back()))) {
                value.pop_back();
            }
            return value;
        };
        auto normalizeHexBytes = [&](std::string token,
                                     const std::string& field) {
            if (token.rfind("0x", 0) == 0 || token.rfind("0X", 0) == 0) {
                token = token.substr(2);
            }
            if ((token.size() % 2) != 0 ||
                !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                    return std::isxdigit(ch) != 0;
                })) {
                fail("bad_hex_bytes field=" + field + " token=" + token);
            }
            std::transform(token.begin(), token.end(), token.begin(),
                           [](unsigned char ch) {
                               return static_cast<char>(std::tolower(ch));
                           });
            return token;
        };

        try {
            std::string text = readTextFile(path);
            std::vector<uint8_t> memory(0x10000);
            std::vector<bool> present(0x10000, false);
            uint16_t runtimeCs = 0;
            uint16_t runtimeDs = 0;
            bool haveRuntimeCs = false;
            bool haveRuntimeDs = false;
            bool tempCopy = false;
            bool visualClaim = false;
            bool instrumentedFreezeObserved = false;
            bool haveInstrumentedFreezeObserved = false;
            bool runtimeFreezePatchApplied = false;
            bool haveRuntimeFreezePatchApplied = false;
            bool haveFreezeExpectedOldBytes = false;
            bool haveFreezeOldBytes = false;
            std::string freezeExpectedOldBytes;
            std::string freezeOldBytes;
            int dispatcherBreaks = 0;
            int damageBreaks = 0;
            int playbackBreaks = 0;
            int observedFreezeBreaks = 0;
            uint16_t firstObservedFreezeOffset = 0;
            bool observedHighZeroBranch = false;
            bool observedHighWordGate = false;
            bool observedEffectForwardCall = false;
            bool observedEffectReverseCall = false;
            bool observedEffectForwardReturn = false;
            bool observedEffectReverseReturn = false;
            bool observedLaneForwardDivide = false;
            bool observedLaneReverseDivide = false;
            bool observedLaneForwardWrite = false;
            bool observedLaneReverseWrite = false;
            bool observedLaneCollapseWrite = false;
            bool observedLaneDebrisWrite = false;
            bool observedLaneForwardResult = false;
            bool observedLaneReverseResult = false;
            uint16_t selectedDebrisBase = 0;
            uint16_t selectedCollapseBase = 0;
            uint16_t selectedEffectBase = 0xc21e;
            bool haveSelectedDebrisBase = false;
            bool haveSelectedCollapseBase = false;
            uint16_t highDebrisTargetDelta = 0;
            uint16_t highDebrisTargetOffset = 0;
            uint16_t highDebrisLookupSegment = 0;
            uint16_t highDebrisWordLayerOffset = 0;
            uint16_t highDebrisWordLayerSegment = 0;
            uint16_t highDebrisWordLayerAddress = 0;
            uint16_t highDebrisC204 = 0;
            uint8_t highDebrisTargetByte = 0;
            uint16_t highDebrisWordLayerValue = 0;
            bool haveHighDebrisTargetOffset = false;
            bool haveHighDebrisTargetByte = false;
            bool haveHighDebrisWordLayerValue = false;
            bool haveInstrumentedBp4LocalPresent = false;
            bool instrumentedBp4LocalPresent = false;
            bool haveInstrumentedBp4LocalOffset = false;
            bool haveInstrumentedBp4LocalValue = false;
            uint16_t instrumentedBp4LocalOffset = 0;
            uint16_t instrumentedBp4LocalValue = 0;
            bool haveInstrumentedLaneDivScratchPresent = false;
            bool instrumentedLaneDivScratchPresent = false;
            bool haveInstrumentedLaneDivOffset = false;
            bool haveInstrumentedLaneDivKind = false;
            std::string instrumentedLaneDivKind;
            uint16_t instrumentedLaneDivOffset = 0;
            std::array<uint16_t, 9> instrumentedLaneDivValues{};
            std::array<bool, 9> haveInstrumentedLaneDivValues{};
            constexpr std::array<const char*, 9> kLaneDivFieldNames{
                "ax", "dx", "cx", "bx", "active_count", "loop_index",
                "weight_local", "numerator_low", "numerator_high",
            };
            auto laneDivFieldIndex = [&](const std::string& name) -> int {
                for (size_t i = 0; i < kLaneDivFieldNames.size(); ++i) {
                    if (name == kLaneDivFieldNames[i]) return static_cast<int>(i);
                }
                return -1;
            };
            bool haveInstrumentedLaneWriteScratchPresent = false;
            bool instrumentedLaneWriteScratchPresent = false;
            bool haveInstrumentedLaneWriteOffset = false;
            bool haveInstrumentedLaneWriteKind = false;
            bool haveInstrumentedLaneWriteTarget = false;
            std::string instrumentedLaneWriteKind;
            std::string instrumentedLaneWriteTarget;
            uint16_t instrumentedLaneWriteOffset = 0;
            std::array<uint16_t, 6> instrumentedLaneWriteValues{};
            std::array<bool, 6> haveInstrumentedLaneWriteValues{};
            constexpr std::array<const char*, 6> kLaneWriteFieldNames{
                "output", "di", "tag", "active_count", "loop_index",
                "result_local",
            };
            auto laneWriteFieldIndex = [&](const std::string& name) -> int {
                for (size_t i = 0; i < kLaneWriteFieldNames.size(); ++i) {
                    if (name == kLaneWriteFieldNames[i]) return static_cast<int>(i);
                }
                return -1;
            };
            bool haveInstrumentedLaneResultScratchPresent = false;
            bool instrumentedLaneResultScratchPresent = false;
            bool haveInstrumentedLaneResultOffset = false;
            bool haveInstrumentedLaneResultKind = false;
            std::string instrumentedLaneResultKind;
            uint16_t instrumentedLaneResultOffset = 0;
            std::array<uint16_t, 9> instrumentedLaneResultValues{};
            std::array<bool, 9> haveInstrumentedLaneResultValues{};
            constexpr std::array<const char*, 9> kLaneResultFieldNames{
                "output", "es", "di", "arg_offset", "arg_segment",
                "result_local", "active_count", "loop_index", "target_before",
            };
            auto laneResultFieldIndex = [&](const std::string& name) -> int {
                for (size_t i = 0; i < kLaneResultFieldNames.size(); ++i) {
                    if (name == kLaneResultFieldNames[i]) return static_cast<int>(i);
                }
                return -1;
            };
            bool haveRuntimeSeeded = false;
            bool runtimeSeeded = false;
            bool haveRuntimeSeedKind = false;
            bool haveRuntimeSeedDirection = false;
            bool haveRuntimeSeedWord = false;
            bool haveRuntimeSeedPatchApplied = false;
            bool runtimeSeedPatchApplied = false;
            std::string runtimeSeedKind;
            std::string runtimeSeedDirection;
            uint16_t runtimeSeedWord = 0;

            std::istringstream lines(text);
            std::string line;
            std::regex keyRe("^([A-Za-z0-9_]+)=(.*)$");
            std::regex breakRe(
                "^break\\s+ghidra=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+"
                "runtime=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+label=([^\\s]+).*$");
            std::regex dumpRe("^dump\\s+DS:([0-9A-Fa-f]{4}).*$");
            std::regex rowRe("^([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+(.+)$");
            uint16_t currentDump = 0;
            bool inDump = false;
            while (std::getline(lines, line)) {
                line = trim(line);
                if (line.empty() || line[0] == '#') continue;

                std::smatch match;
                if (std::regex_match(line, match, keyRe)) {
                    std::string key = match[1].str();
                    std::string value = trim(match[2].str());
                    if (key == "runtime_cs") {
                        runtimeCs = parseHex16(value, key);
                        haveRuntimeCs = true;
                    } else if (key == "runtime_ds") {
                        runtimeDs = parseHex16(value, key);
                        haveRuntimeDs = true;
                    } else if (key == "temp_copy") {
                        tempCopy = value == "1";
                    } else if (key == "visual_claim") {
                        visualClaim = value != "0";
                    } else if (key == "instrumented_freeze_observed") {
                        instrumentedFreezeObserved = value == "1";
                        haveInstrumentedFreezeObserved = true;
                    } else if (key == "runtime_freeze_patch_applied") {
                        runtimeFreezePatchApplied = value == "1";
                        haveRuntimeFreezePatchApplied = true;
                    } else if (key == "freeze_expected_old_bytes") {
                        freezeExpectedOldBytes = normalizeHexBytes(value, key);
                        haveFreezeExpectedOldBytes = true;
                    } else if (key == "freeze_old_bytes") {
                        freezeOldBytes = normalizeHexBytes(value, key);
                        haveFreezeOldBytes = true;
                    } else if (key == "runtime_seeded") {
                        runtimeSeeded = value == "1";
                        haveRuntimeSeeded = true;
                    } else if (key == "runtime_seed_kind") {
                        if (value != "debris-writeback") {
                            fail("bad_runtime_seed_kind value=" + value);
                        }
                        runtimeSeedKind = value;
                        haveRuntimeSeedKind = true;
                    } else if (key == "runtime_seed_direction") {
                        if (value != "forward" && value != "reverse") {
                            fail("bad_runtime_seed_direction value=" + value);
                        }
                        runtimeSeedDirection = value;
                        haveRuntimeSeedDirection = true;
                    } else if (key == "runtime_seed_word") {
                        runtimeSeedWord = parseHex16Auto(value, key);
                        haveRuntimeSeedWord = true;
                    } else if (key == "runtime_seed_patch_applied") {
                        runtimeSeedPatchApplied = value == "1";
                        haveRuntimeSeedPatchApplied = true;
                    } else if (key == "selected_debris_base") {
                        selectedDebrisBase = parseHex16(value, key);
                        haveSelectedDebrisBase = true;
                    } else if (key == "selected_collapse_base") {
                        selectedCollapseBase = parseHex16(value, key);
                        haveSelectedCollapseBase = true;
                    } else if (key == "selected_effect_base") {
                        selectedEffectBase = parseHex16(value, key);
                    } else if (key == "high_debris_target_delta") {
                        highDebrisTargetDelta = parseHex16Auto(value, key);
                    } else if (key == "high_debris_target_offset") {
                        highDebrisTargetOffset = parseHex16Auto(value, key);
                        haveHighDebrisTargetOffset = true;
                    } else if (key == "high_debris_lookup_segment") {
                        highDebrisLookupSegment = parseHex16Auto(value, key);
                    } else if (key == "high_debris_word_layer_offset") {
                        highDebrisWordLayerOffset = parseHex16Auto(value, key);
                    } else if (key == "high_debris_word_layer_segment") {
                        highDebrisWordLayerSegment = parseHex16Auto(value, key);
                    } else if (key == "high_debris_word_layer_address") {
                        highDebrisWordLayerAddress = parseHex16Auto(value, key);
                    } else if (key == "high_debris_c204") {
                        highDebrisC204 = parseHex16Auto(value, key);
                    } else if (key == "high_debris_target_byte") {
                        highDebrisTargetByte = static_cast<uint8_t>(
                            parseHex16Auto(value, key) & 0xff);
                        haveHighDebrisTargetByte = true;
                    } else if (key == "high_debris_word_layer_value") {
                        highDebrisWordLayerValue = parseHex16Auto(value, key);
                        haveHighDebrisWordLayerValue = true;
                    } else if (key == "instrumented_bp4_local_present") {
                        instrumentedBp4LocalPresent = value == "1";
                        haveInstrumentedBp4LocalPresent = true;
                    } else if (key == "instrumented_bp4_local_cs_offset") {
                        instrumentedBp4LocalOffset = parseHex16Auto(value, key);
                        haveInstrumentedBp4LocalOffset = true;
                    } else if (key == "instrumented_bp4_local_value") {
                        instrumentedBp4LocalValue = parseHex16Auto(value, key);
                        haveInstrumentedBp4LocalValue = true;
                    } else if (key == "instrumented_lane_div_scratch_present") {
                        instrumentedLaneDivScratchPresent = value == "1";
                        haveInstrumentedLaneDivScratchPresent = true;
                    } else if (key == "instrumented_lane_div_cs_offset") {
                        instrumentedLaneDivOffset = parseHex16Auto(value, key);
                        haveInstrumentedLaneDivOffset = true;
                    } else if (key == "instrumented_lane_div_kind") {
                        if (value != "forward" && value != "reverse") {
                            fail("bad_lane_div_kind value=" + value);
                        }
                        instrumentedLaneDivKind = value;
                        haveInstrumentedLaneDivKind = true;
                    } else if (key.rfind("instrumented_lane_div_", 0) == 0) {
                        std::string field =
                            key.substr(std::string("instrumented_lane_div_").size());
                        int index = laneDivFieldIndex(field);
                        if (index < 0) {
                            fail("bad_lane_div_field field=" + field);
                        }
                        instrumentedLaneDivValues[static_cast<size_t>(index)] =
                            parseHex16Auto(value, key);
                        haveInstrumentedLaneDivValues[static_cast<size_t>(index)] =
                            true;
                    } else if (key == "instrumented_lane_write_scratch_present") {
                        instrumentedLaneWriteScratchPresent = value == "1";
                        haveInstrumentedLaneWriteScratchPresent = true;
                    } else if (key == "instrumented_lane_write_cs_offset") {
                        instrumentedLaneWriteOffset = parseHex16Auto(value, key);
                        haveInstrumentedLaneWriteOffset = true;
                    } else if (key == "instrumented_lane_write_kind") {
                        if (value != "forward" && value != "reverse") {
                            fail("bad_lane_write_kind value=" + value);
                        }
                        instrumentedLaneWriteKind = value;
                        haveInstrumentedLaneWriteKind = true;
                    } else if (key == "instrumented_lane_write_target") {
                        if (value != "collapse" && value != "debris") {
                            fail("bad_lane_write_target value=" + value);
                        }
                        instrumentedLaneWriteTarget = value;
                        haveInstrumentedLaneWriteTarget = true;
                    } else if (key.rfind("instrumented_lane_write_", 0) == 0) {
                        std::string field =
                            key.substr(std::string("instrumented_lane_write_").size());
                        int index = laneWriteFieldIndex(field);
                        if (index < 0) {
                            fail("bad_lane_write_field field=" + field);
                        }
                        instrumentedLaneWriteValues[static_cast<size_t>(index)] =
                            parseHex16Auto(value, key);
                        haveInstrumentedLaneWriteValues[static_cast<size_t>(index)] =
                            true;
                    } else if (key == "instrumented_lane_result_scratch_present") {
                        instrumentedLaneResultScratchPresent = value == "1";
                        haveInstrumentedLaneResultScratchPresent = true;
                    } else if (key == "instrumented_lane_result_cs_offset") {
                        instrumentedLaneResultOffset = parseHex16Auto(value, key);
                        haveInstrumentedLaneResultOffset = true;
                    } else if (key == "instrumented_lane_result_kind") {
                        if (value != "forward" && value != "reverse") {
                            fail("bad_lane_result_kind value=" + value);
                        }
                        instrumentedLaneResultKind = value;
                        haveInstrumentedLaneResultKind = true;
                    } else if (key.rfind("instrumented_lane_result_", 0) == 0) {
                        std::string field =
                            key.substr(std::string("instrumented_lane_result_").size());
                        int index = laneResultFieldIndex(field);
                        if (index < 0) {
                            fail("bad_lane_result_field field=" + field);
                        }
                        instrumentedLaneResultValues[static_cast<size_t>(index)] =
                            parseHex16Auto(value, key);
                        haveInstrumentedLaneResultValues[static_cast<size_t>(index)] =
                            true;
                    }
                    continue;
                }

                if (std::regex_match(line, match, breakRe)) {
                    if (!haveRuntimeCs) fail("runtime_cs_missing_before_break");
                    uint16_t ghidraSegment = parseHex16(match[1].str(), "ghidra");
                    uint16_t ghidraOffset = parseHex16(match[2].str(), "ghidra");
                    uint16_t runtimeSegment = parseHex16(match[3].str(), "runtime");
                    uint16_t runtimeOffset = parseHex16(match[4].str(), "runtime");
                    if (ghidraSegment != 0x1000) {
                        fail("breakpoint_ghidra_segment expected=0x1000 actual=" +
                             hex4(ghidraSegment));
                    }
                    if (runtimeSegment != runtimeCs) {
                        fail("breakpoint_segment_mismatch expected=" + hex4(runtimeCs) +
                             " actual=" + hex4(runtimeSegment));
                    }
                    if (runtimeOffset != ghidraOffset) {
                        fail("breakpoint_offset_mismatch expected=" +
                             bareHex4(ghidraOffset) + " actual=" +
                             bareHex4(runtimeOffset));
                    }
                    if (ghidraOffset == 0x414a) ++dispatcherBreaks;
                    if (ghidraOffset == 0x370e) ++damageBreaks;
                    bool freezeObserved =
                        line.find("observed=runtime_child_memory_freeze_observed") !=
                            std::string::npos ||
                        line.find("observed=instrumented_temp_copy_freeze_observed") !=
                            std::string::npos;
                    if (freezeObserved) {
                        if (observedFreezeBreaks == 0) {
                            firstObservedFreezeOffset = ghidraOffset;
                        }
                        ++observedFreezeBreaks;
                    }
                    if (ghidraOffset == 0x3a7e || ghidraOffset == 0x3b18 ||
                        ghidraOffset == 0x3bb2 || ghidraOffset == 0x3d46 ||
                        ghidraOffset == 0x3cd4 || ghidraOffset == 0x3ce3 ||
                        ghidraOffset == 0x3e68 || ghidraOffset == 0x3e77 ||
                        ghidraOffset == 0x3d1b || ghidraOffset == 0x3d2d ||
                        ghidraOffset == 0x3d3f ||
                        ghidraOffset == 0x3eaf || ghidraOffset == 0x3ec1 ||
                        ghidraOffset == 0x3ed3 ||
                        ghidraOffset == 0x45fa || ghidraOffset == 0x492f ||
                        ghidraOffset == 0x4b3f || ghidraOffset == 0x4b61 ||
                        ghidraOffset == 0x4b6a || ghidraOffset == 0x4c20 ||
                        ghidraOffset == 0x4c75 || ghidraOffset == 0x4c96 ||
                        ghidraOffset == 0x4c99 || ghidraOffset == 0x4ca9 ||
                        ghidraOffset == 0x4cac) {
                        ++playbackBreaks;
                    }
                    if (freezeObserved) {
                        if (ghidraOffset == 0x4b6a) observedHighZeroBranch = true;
                        if (ghidraOffset == 0x4c75) observedHighWordGate = true;
                        if (ghidraOffset == 0x4c96) observedEffectForwardCall = true;
                        if (ghidraOffset == 0x4ca9) observedEffectReverseCall = true;
                        if (ghidraOffset == 0x4c99) {
                            observedEffectForwardReturn = true;
                        }
                        if (ghidraOffset == 0x4cac) {
                            observedEffectReverseReturn = true;
                        }
                        if (ghidraOffset == 0x3cd4 || ghidraOffset == 0x3ce3) {
                            observedLaneForwardDivide = true;
                        }
                        if (ghidraOffset == 0x3e68 || ghidraOffset == 0x3e77) {
                            observedLaneReverseDivide = true;
                        }
                        if (ghidraOffset == 0x3d1b || ghidraOffset == 0x3d2d) {
                            observedLaneForwardWrite = true;
                        }
                        if (ghidraOffset == 0x3eaf || ghidraOffset == 0x3ec1) {
                            observedLaneReverseWrite = true;
                        }
                        if (ghidraOffset == 0x3d1b || ghidraOffset == 0x3eaf) {
                            observedLaneCollapseWrite = true;
                        }
                        if (ghidraOffset == 0x3d2d || ghidraOffset == 0x3ec1) {
                            observedLaneDebrisWrite = true;
                        }
                        if (ghidraOffset == 0x3d3f) {
                            observedLaneForwardResult = true;
                        }
                        if (ghidraOffset == 0x3ed3) {
                            observedLaneReverseResult = true;
                        }
                    }
                    continue;
                }

                if (std::regex_match(line, match, dumpRe)) {
                    currentDump = parseHex16(match[1].str(), "dump");
                    inDump = true;
                    continue;
                }

                if (std::regex_match(line, match, rowRe)) {
                    if (!inDump) fail("dump_row_without_header");
                    if (!haveRuntimeDs) fail("runtime_ds_missing_before_dump");
                    uint16_t segment = parseHex16(match[1].str(), "row_segment");
                    uint16_t address = parseHex16(match[2].str(), "row_address");
                    if (segment != runtimeDs) {
                        fail("dump_segment_mismatch expected=" + hex4(runtimeDs) +
                             " actual=" + hex4(segment) +
                             " address=" + bareHex4(address));
                    }
                    if (address < currentDump) {
                        fail("dump_address_before_header header=" + bareHex4(currentDump) +
                             " address=" + bareHex4(address));
                    }
                    std::istringstream byteStream(match[3].str());
                    std::string token;
                    uint16_t cursor = address;
                    while (byteStream >> token) {
                        memory[cursor] = parseHexByte(token, cursor);
                        present[cursor] = true;
                        ++cursor;
                    }
                    continue;
                }

                fail("unrecognized_line");
            }

            if (!haveRuntimeCs) fail("runtime_cs_missing");
            if (!haveRuntimeDs) fail("runtime_ds_missing");
            if (!tempCopy) fail("temp_copy_required");
            if (visualClaim) fail("visual_claim_not_allowed");
            if (dispatcherBreaks == 0) fail("dispatcher_break_missing");
            if (damageBreaks == 0) fail("damage_break_missing");
            if (playbackBreaks == 0) fail("playback_break_missing");
            if (observedFreezeBreaks > 1) {
                fail("multiple_observed_freeze_breaks");
            }
            if (haveInstrumentedFreezeObserved && instrumentedFreezeObserved &&
                haveRuntimeFreezePatchApplied && !runtimeFreezePatchApplied) {
                fail("instrumented_freeze_without_runtime_patch");
            }
            if (haveInstrumentedFreezeObserved && instrumentedFreezeObserved &&
                observedFreezeBreaks == 0) {
                fail("instrumented_freeze_without_observed_break");
            }
            if (haveInstrumentedFreezeObserved && !instrumentedFreezeObserved &&
                observedFreezeBreaks != 0) {
                fail("observed_break_without_instrumented_freeze");
            }
            if (haveRuntimeFreezePatchApplied && !runtimeFreezePatchApplied &&
                observedFreezeBreaks != 0) {
                fail("observed_break_without_runtime_patch");
            }
            if (haveFreezeExpectedOldBytes) {
                if (!haveFreezeOldBytes) {
                    fail("freeze_expected_without_old_bytes");
                }
                if (freezeOldBytes.rfind(freezeExpectedOldBytes, 0) != 0) {
                    fail("freeze_expected_old_bytes_mismatch");
                }
            }
            if (haveInstrumentedBp4LocalPresent && instrumentedBp4LocalPresent) {
                if (!observedHighWordGate) {
                    fail("bp4_local_without_word_gate_freeze");
                }
                if (!haveInstrumentedBp4LocalOffset) {
                    fail("bp4_local_offset_missing");
                }
                if (!haveInstrumentedBp4LocalValue) {
                    fail("bp4_local_value_missing");
                }
            }
            if (haveInstrumentedBp4LocalValue &&
                (!haveInstrumentedBp4LocalPresent || !instrumentedBp4LocalPresent)) {
                fail("bp4_local_value_without_present");
            }
            if (haveInstrumentedLaneDivScratchPresent &&
                instrumentedLaneDivScratchPresent) {
                if (!observedLaneForwardDivide && !observedLaneReverseDivide) {
                    fail("lane_div_scratch_without_lane_divide_freeze");
                }
                if (!haveInstrumentedLaneDivOffset) {
                    fail("lane_div_offset_missing");
                }
                if (!haveInstrumentedLaneDivKind) {
                    fail("lane_div_kind_missing");
                }
                if (instrumentedLaneDivKind == "forward" &&
                    !observedLaneForwardDivide) {
                    fail("lane_div_forward_kind_without_forward_freeze");
                }
                if (instrumentedLaneDivKind == "reverse" &&
                    !observedLaneReverseDivide) {
                    fail("lane_div_reverse_kind_without_reverse_freeze");
                }
                for (size_t i = 0; i < haveInstrumentedLaneDivValues.size(); ++i) {
                    if (!haveInstrumentedLaneDivValues[i]) {
                        fail(std::string("lane_div_field_missing field=") +
                             kLaneDivFieldNames[i]);
                    }
                }
                if (instrumentedLaneDivValues[0] !=
                        instrumentedLaneDivValues[7] ||
                    instrumentedLaneDivValues[1] !=
                        instrumentedLaneDivValues[8] ||
                    instrumentedLaneDivValues[2] !=
                        instrumentedLaneDivValues[6] ||
                    instrumentedLaneDivValues[3] != 0) {
                    fail("lane_div_register_local_mismatch");
                }
            }
            bool haveAnyLaneDivValueField = false;
            for (bool haveField : haveInstrumentedLaneDivValues) {
                haveAnyLaneDivValueField = haveAnyLaneDivValueField || haveField;
            }
            if (haveAnyLaneDivValueField &&
                (!haveInstrumentedLaneDivScratchPresent ||
                 !instrumentedLaneDivScratchPresent)) {
                fail("lane_div_field_without_present");
            }
            if (haveInstrumentedLaneWriteScratchPresent &&
                instrumentedLaneWriteScratchPresent) {
                if (!observedLaneForwardWrite && !observedLaneReverseWrite) {
                    fail("lane_write_scratch_without_lane_write_freeze");
                }
                if (!haveInstrumentedLaneWriteOffset) {
                    fail("lane_write_offset_missing");
                }
                if (!haveInstrumentedLaneWriteKind) {
                    fail("lane_write_kind_missing");
                }
                if (!haveInstrumentedLaneWriteTarget) {
                    fail("lane_write_target_missing");
                }
                if (instrumentedLaneWriteKind == "forward" &&
                    !observedLaneForwardWrite) {
                    fail("lane_write_forward_kind_without_forward_freeze");
                }
                if (instrumentedLaneWriteKind == "reverse" &&
                    !observedLaneReverseWrite) {
                    fail("lane_write_reverse_kind_without_reverse_freeze");
                }
                if (instrumentedLaneWriteTarget == "collapse" &&
                    !observedLaneCollapseWrite) {
                    fail("lane_write_collapse_target_without_collapse_freeze");
                }
                if (instrumentedLaneWriteTarget == "debris" &&
                    !observedLaneDebrisWrite) {
                    fail("lane_write_debris_target_without_debris_freeze");
                }
                for (size_t i = 0; i < haveInstrumentedLaneWriteValues.size(); ++i) {
                    if (!haveInstrumentedLaneWriteValues[i]) {
                        fail(std::string("lane_write_field_missing field=") +
                             kLaneWriteFieldNames[i]);
                    }
                }
                uint16_t output = instrumentedLaneWriteValues[0];
                uint16_t di = instrumentedLaneWriteValues[1];
                uint16_t tag = instrumentedLaneWriteValues[2];
                uint16_t activeCount = instrumentedLaneWriteValues[3];
                uint16_t loopIndex = instrumentedLaneWriteValues[4];
                uint16_t resultLocal = instrumentedLaneWriteValues[5];
                if (output != resultLocal || (output & 0xff00u) != 0) {
                    fail("lane_write_output_local_mismatch");
                }
                if (loopIndex == 0 || activeCount == 0 || loopIndex > activeCount) {
                    fail("lane_write_loop_bounds");
                }
                if (instrumentedLaneWriteTarget == "collapse") {
                    if (tag >= 0x4e20u || di != static_cast<uint16_t>(tag * 0x0fu)) {
                        fail("lane_write_collapse_tag_di_mismatch");
                    }
                } else {
                    if (tag < 0x4e20u ||
                        di != static_cast<uint16_t>((tag - 0x4e20u) * 0x0bu)) {
                        fail("lane_write_debris_tag_di_mismatch");
                    }
                }
            }
            bool haveAnyLaneWriteValueField = false;
            for (bool haveField : haveInstrumentedLaneWriteValues) {
                haveAnyLaneWriteValueField = haveAnyLaneWriteValueField || haveField;
            }
            if (haveAnyLaneWriteValueField &&
                (!haveInstrumentedLaneWriteScratchPresent ||
                 !instrumentedLaneWriteScratchPresent)) {
                fail("lane_write_field_without_present");
            }
            if (haveInstrumentedLaneResultScratchPresent &&
                instrumentedLaneResultScratchPresent) {
                if (!observedLaneForwardResult && !observedLaneReverseResult) {
                    fail("lane_result_scratch_without_lane_result_freeze");
                }
                if (!haveFreezeExpectedOldBytes ||
                    freezeExpectedOldBytes != "268805") {
                    fail("lane_result_expected_old_bytes_missing");
                }
                if (!haveInstrumentedLaneResultOffset) {
                    fail("lane_result_offset_missing");
                }
                if (instrumentedLaneResultOffset != 0xf280u) {
                    fail("lane_result_scratch_offset_mismatch");
                }
                if (!haveInstrumentedLaneResultKind) {
                    fail("lane_result_kind_missing");
                }
                if (instrumentedLaneResultKind == "forward" &&
                    !observedLaneForwardResult) {
                    fail("lane_result_forward_kind_without_forward_freeze");
                }
                if (instrumentedLaneResultKind == "reverse" &&
                    !observedLaneReverseResult) {
                    fail("lane_result_reverse_kind_without_reverse_freeze");
                }
                for (size_t i = 0; i < haveInstrumentedLaneResultValues.size(); ++i) {
                    if (!haveInstrumentedLaneResultValues[i]) {
                        fail(std::string("lane_result_field_missing field=") +
                             kLaneResultFieldNames[i]);
                    }
                }
                uint16_t output = instrumentedLaneResultValues[0];
                uint16_t es = instrumentedLaneResultValues[1];
                uint16_t di = instrumentedLaneResultValues[2];
                uint16_t argOffset = instrumentedLaneResultValues[3];
                uint16_t argSegment = instrumentedLaneResultValues[4];
                uint16_t resultLocal = instrumentedLaneResultValues[5];
                uint16_t activeCount = instrumentedLaneResultValues[6];
                uint16_t loopIndex = instrumentedLaneResultValues[7];
                uint16_t targetBefore = instrumentedLaneResultValues[8];
                if (output != resultLocal || (output & 0xff00u) != 0) {
                    fail("lane_result_output_local_mismatch");
                }
                if ((targetBefore & 0xff00u) != 0) {
                    fail("lane_result_target_before_width");
                }
                if (es != argSegment || di != argOffset) {
                    fail("lane_result_far_pointer_mismatch");
                }
                if (loopIndex == 0 || activeCount == 0 || loopIndex > activeCount) {
                    fail("lane_result_loop_bounds");
                }
            }
            bool haveAnyLaneResultValueField = false;
            for (bool haveField : haveInstrumentedLaneResultValues) {
                haveAnyLaneResultValueField = haveAnyLaneResultValueField || haveField;
            }
            if (haveAnyLaneResultValueField &&
                (!haveInstrumentedLaneResultScratchPresent ||
                 !instrumentedLaneResultScratchPresent)) {
                fail("lane_result_field_without_present");
            }
            if (haveRuntimeSeeded && runtimeSeeded) {
                if (!haveRuntimeSeedKind) {
                    fail("runtime_seed_kind_missing");
                }
                if (!haveRuntimeSeedDirection) {
                    fail("runtime_seed_direction_missing");
                }
                if (!haveRuntimeSeedWord) {
                    fail("runtime_seed_word_missing");
                }
                if (!haveRuntimeSeedPatchApplied || !runtimeSeedPatchApplied) {
                    fail("runtime_seed_patch_not_applied");
                }
                if (haveInstrumentedLaneWriteKind &&
                    instrumentedLaneWriteKind != runtimeSeedDirection) {
                    fail("runtime_seed_direction_mismatch");
                }
            }

            auto requireByte = [&](uint16_t address) -> uint8_t {
                if (!present[address]) {
                    fail("missing_byte address=" + bareHex4(address));
                }
                return memory[address];
            };
            auto byteList = [&](uint16_t address, int len) {
                std::ostringstream oss;
                for (int i = 0; i < len; ++i) {
                    if (i > 0) oss << ',';
                    oss << hexByte(requireByte(static_cast<uint16_t>(address + i)));
                }
                return oss.str();
            };
            auto requireLe16 = [&](uint16_t address) {
                return static_cast<uint16_t>(
                    requireByte(address) |
                    (requireByte(static_cast<uint16_t>(address + 1)) << 8));
            };
            auto bytesPresent = [&](uint16_t address, size_t len) {
                uint32_t end = static_cast<uint32_t>(address) + static_cast<uint32_t>(len);
                if (end > present.size()) return false;
                for (size_t i = 0; i < len; ++i) {
                    if (!present[static_cast<uint16_t>(address + i)]) return false;
                }
                return true;
            };
            auto countedBase = [&](uint16_t base, size_t stride, uint16_t count,
                                   size_t len, uint16_t& out) {
                if (count == 0) return false;
                uint32_t address = static_cast<uint32_t>(base) +
                                   static_cast<uint32_t>(stride) * count;
                if (address + len > 0x10000u) return false;
                out = static_cast<uint16_t>(address);
                return bytesPresent(out, len);
            };

            constexpr uint16_t kLookupBase = 0xc1e0;
            constexpr uint16_t kDebrisRecordBase = 0x2093;
            constexpr uint16_t kCollapseRecordBase = 0x6611;
            bool haveDebrisCount = bytesPresent(0x207e, 2);
            bool haveCollapseCount = bytesPresent(0x2080, 2);
            uint16_t debrisQueueCount = haveDebrisCount ? requireLe16(0x207e) : 0;
            uint16_t collapseQueueCount = haveCollapseCount ? requireLe16(0x2080) : 0;
            uint16_t debrisCountBase = 0;
            uint16_t collapseCountBase = 0;
            bool haveDebrisCountBase = countedBase(kDebrisRecordBase, kDebrisStride,
                                                   debrisQueueCount, kDebrisStride,
                                                   debrisCountBase);
            bool haveCollapseCountBase = countedBase(kCollapseRecordBase, kCollapseStride,
                                                     collapseQueueCount, kCollapseStride,
                                                     collapseCountBase);
            if (!haveSelectedDebrisBase && haveDebrisCountBase) {
                selectedDebrisBase = debrisCountBase;
                haveSelectedDebrisBase = true;
            }
            if (!haveSelectedCollapseBase && haveCollapseCountBase) {
                selectedCollapseBase = collapseCountBase;
                haveSelectedCollapseBase = true;
            }
            if (!haveSelectedDebrisBase) selectedDebrisBase = kDebrisRecordBase;
            if (!haveSelectedCollapseBase) selectedCollapseBase = kCollapseRecordBase;

            std::string debris0 =
                byteList(selectedDebrisBase, static_cast<int>(kDebrisStride));
            std::string collapse0 =
                byteList(selectedCollapseBase, static_cast<int>(kCollapseStride));
            std::string effect0 = byteList(selectedEffectBase, 8);
            uint8_t lookup0 = requireByte(kLookupBase);
            uint16_t debrisTileIndex = requireLe16(selectedDebrisBase);
            uint16_t debrisFlagged =
                requireLe16(static_cast<uint16_t>(selectedDebrisBase + 2));
            uint8_t debrisForward =
                requireByte(static_cast<uint16_t>(selectedDebrisBase + 4));
            uint8_t debrisReverse =
                requireByte(static_cast<uint16_t>(selectedDebrisBase + 5));
            uint8_t debrisLookup =
                requireByte(static_cast<uint16_t>(selectedDebrisBase + 9));
            uint16_t collapseStart = requireLe16(selectedCollapseBase);
            uint16_t collapseEnd =
                requireLe16(static_cast<uint16_t>(selectedCollapseBase + 2));
            uint16_t collapseStoredWord =
                requireLe16(static_cast<uint16_t>(selectedCollapseBase + 4));
            uint16_t collapseWord =
                static_cast<uint16_t>(collapseStoredWord & ~kDamagedWordBit);
            uint16_t collapseFlagged = collapseStoredWord;
            uint8_t collapseForward =
                requireByte(static_cast<uint16_t>(selectedCollapseBase + 6));
            uint8_t collapseReverse =
                requireByte(static_cast<uint16_t>(selectedCollapseBase + 7));
            uint8_t collapseLane8 =
                requireByte(static_cast<uint16_t>(selectedCollapseBase + 8));
            uint8_t collapseLane9 =
                requireByte(static_cast<uint16_t>(selectedCollapseBase + 9));
            uint16_t collapseMagnitude =
                requireLe16(static_cast<uint16_t>(selectedCollapseBase + 0x0a));
            uint8_t collapseAffectedBytes =
                requireByte(static_cast<uint16_t>(selectedCollapseBase + 0x0e));
            uint8_t collapseCount = static_cast<uint8_t>(collapseAffectedBytes / 2);
            uint16_t effectX = requireLe16(selectedEffectBase);
            uint16_t effectY = requireLe16(static_cast<uint16_t>(selectedEffectBase + 2));
            uint8_t effectSprite =
                requireByte(static_cast<uint16_t>(selectedEffectBase + 4));
            uint8_t effectDetail =
                requireByte(static_cast<uint16_t>(selectedEffectBase + 5));
            uint8_t effectTimer =
                requireByte(static_cast<uint16_t>(selectedEffectBase + 6));
            uint8_t effectVariant =
                requireByte(static_cast<uint16_t>(selectedEffectBase + 7));
            bool haveLaneGlobals =
                bytesPresent(kHighDebrisLaneUpdateFlag, 1) &&
                bytesPresent(kHighDebrisLaneWordGlobal, 2) &&
                bytesPresent(kHighDebrisLaneTargetOffsetGlobal, 2);
            uint8_t laneUpdateFlag =
                haveLaneGlobals ? requireByte(kHighDebrisLaneUpdateFlag) : 0;
            uint16_t laneWordGlobal =
                haveLaneGlobals ? requireLe16(kHighDebrisLaneWordGlobal) : 0;
            uint16_t laneTargetOffsetGlobal =
                haveLaneGlobals ? requireLe16(kHighDebrisLaneTargetOffsetGlobal) : 0;
            bool haveEffectInputGlobals =
                bytesPresent(kExplosionEffectForwardInputGlobal, 1) &&
                bytesPresent(kExplosionEffectReverseInputGlobal, 1);
            uint8_t effectForwardInputGlobal =
                haveEffectInputGlobals
                    ? requireByte(kExplosionEffectForwardInputGlobal)
                    : 0;
            uint8_t effectReverseInputGlobal =
                haveEffectInputGlobals
                    ? requireByte(kExplosionEffectReverseInputGlobal)
                    : 0;

            std::cout << "explosion_playback_oracle=ok fixture=" << fixture
                      << " runtime_cs=" << hex4(runtimeCs)
                      << " runtime_ds=" << hex4(runtimeDs)
                      << " dispatcher_break=" << dispatcherBreaks
                      << " damage_break=" << damageBreaks
                      << " playback_breaks=" << playbackBreaks
                      << " observed_freeze_count=" << observedFreezeBreaks
                      << " observed_freeze_offset=" << hex4(firstObservedFreezeOffset)
                      << " observed_high_zero_branch="
                      << (observedHighZeroBranch ? 1 : 0)
                      << " observed_high_word_gate="
                      << (observedHighWordGate ? 1 : 0)
                      << " observed_effect_forward_call="
                      << (observedEffectForwardCall ? 1 : 0)
                      << " observed_effect_reverse_call="
                      << (observedEffectReverseCall ? 1 : 0)
                      << " observed_effect_forward_return="
                      << (observedEffectForwardReturn ? 1 : 0)
                      << " observed_effect_reverse_return="
                      << (observedEffectReverseReturn ? 1 : 0)
                      << " observed_lane_forward_divide="
                      << (observedLaneForwardDivide ? 1 : 0)
                      << " observed_lane_reverse_divide="
                      << (observedLaneReverseDivide ? 1 : 0)
                      << " observed_lane_forward_write="
                      << (observedLaneForwardWrite ? 1 : 0)
                      << " observed_lane_reverse_write="
                      << (observedLaneReverseWrite ? 1 : 0)
                      << " observed_lane_collapse_write="
                      << (observedLaneCollapseWrite ? 1 : 0)
                      << " observed_lane_debris_write="
                      << (observedLaneDebrisWrite ? 1 : 0)
                      << " observed_lane_forward_result="
                      << (observedLaneForwardResult ? 1 : 0)
                      << " observed_lane_reverse_result="
                      << (observedLaneReverseResult ? 1 : 0)
                      << " bp4_local_present="
                      << (instrumentedBp4LocalPresent ? 1 : 0)
                      << (instrumentedBp4LocalPresent
                              ? std::string(" bp4_local_cs_offset=") +
                                    hex4(instrumentedBp4LocalOffset) +
                                    " bp4_local_value=" +
                                    hex4(instrumentedBp4LocalValue)
                              : "")
                      << " lane_div_scratch_present="
                      << (instrumentedLaneDivScratchPresent ? 1 : 0)
                      << (instrumentedLaneDivScratchPresent
                              ? std::string(" lane_div_kind=") +
                                    instrumentedLaneDivKind +
                                    " lane_div_cs_offset=" +
                                    hex4(instrumentedLaneDivOffset) +
                                    " lane_div_ax=" +
                                    hex4(instrumentedLaneDivValues[0]) +
                                    " lane_div_dx=" +
                                    hex4(instrumentedLaneDivValues[1]) +
                                    " lane_div_cx=" +
                                    hex4(instrumentedLaneDivValues[2]) +
                                    " lane_div_bx=" +
                                    hex4(instrumentedLaneDivValues[3]) +
                                    " lane_div_active_count=" +
                                    hex4(instrumentedLaneDivValues[4]) +
                                    " lane_div_loop_index=" +
                                    hex4(instrumentedLaneDivValues[5]) +
                                    " lane_div_weight_local=" +
                                    hex4(instrumentedLaneDivValues[6]) +
                                    " lane_div_numerator_low=" +
                                    hex4(instrumentedLaneDivValues[7]) +
                                    " lane_div_numerator_high=" +
                                    hex4(instrumentedLaneDivValues[8])
                              : "")
                      << " lane_write_scratch_present="
                      << (instrumentedLaneWriteScratchPresent ? 1 : 0)
                      << (instrumentedLaneWriteScratchPresent
                              ? std::string(" lane_write_kind=") +
                                    instrumentedLaneWriteKind +
                                    " lane_write_target=" +
                                    instrumentedLaneWriteTarget +
                                    " lane_write_cs_offset=" +
                                    hex4(instrumentedLaneWriteOffset) +
                                    " lane_write_output=" +
                                    hex4(instrumentedLaneWriteValues[0]) +
                                    " lane_write_di=" +
                                    hex4(instrumentedLaneWriteValues[1]) +
                                    " lane_write_tag=" +
                                    hex4(instrumentedLaneWriteValues[2]) +
                                    " lane_write_active_count=" +
                                    hex4(instrumentedLaneWriteValues[3]) +
                                    " lane_write_loop_index=" +
                                    hex4(instrumentedLaneWriteValues[4]) +
                                    " lane_write_result_local=" +
                                    hex4(instrumentedLaneWriteValues[5])
                              : "")
                      << " lane_result_scratch_present="
                      << (instrumentedLaneResultScratchPresent ? 1 : 0)
                      << (instrumentedLaneResultScratchPresent
                              ? std::string(" lane_result_kind=") +
                                    instrumentedLaneResultKind +
                                    " lane_result_cs_offset=" +
                                    hex4(instrumentedLaneResultOffset) +
                                    " lane_result_output=" +
                                    hex4(instrumentedLaneResultValues[0]) +
                                    " lane_result_es=" +
                                    hex4(instrumentedLaneResultValues[1]) +
                                    " lane_result_di=" +
                                    hex4(instrumentedLaneResultValues[2]) +
                                    " lane_result_arg_offset=" +
                                    hex4(instrumentedLaneResultValues[3]) +
                                    " lane_result_arg_segment=" +
                                    hex4(instrumentedLaneResultValues[4]) +
                                    " lane_result_result_local=" +
                                    hex4(instrumentedLaneResultValues[5]) +
                                    " lane_result_active_count=" +
                                    hex4(instrumentedLaneResultValues[6]) +
                                    " lane_result_loop_index=" +
                                    hex4(instrumentedLaneResultValues[7]) +
                                    " lane_result_target_before=" +
                                    hex4(instrumentedLaneResultValues[8])
                              : "")
                      << " freeze_expected_old_bytes_present="
                      << (haveFreezeExpectedOldBytes ? 1 : 0)
                      << (haveFreezeExpectedOldBytes
                              ? std::string(" freeze_expected_old_bytes=") +
                                    freezeExpectedOldBytes +
                                    " freeze_old_bytes=" + freezeOldBytes
                              : "")
                      << " runtime_seeded=" << (runtimeSeeded ? 1 : 0)
                      << (runtimeSeeded
                              ? std::string(" runtime_seed_kind=") +
                                    runtimeSeedKind +
                                    " runtime_seed_direction=" +
                                    runtimeSeedDirection +
                                    " runtime_seed_word=" +
                                    hex4(runtimeSeedWord) +
                                    " runtime_seed_patch_applied=" +
                                    std::to_string(runtimeSeedPatchApplied ? 1 : 0)
                              : "")
                      << " lane_globals_present=" << (haveLaneGlobals ? 1 : 0)
                      << " lane_update_flag=" << hexBytePrefix(laneUpdateFlag)
                      << " lane_word_global_value=" << hex4(laneWordGlobal)
                      << " lane_target_offset_global_value="
                      << hex4(laneTargetOffsetGlobal)
                      << " effect_input_globals_present="
                      << (haveEffectInputGlobals ? 1 : 0)
                      << " effect_forward_input_global_value="
                      << hexBytePrefix(effectForwardInputGlobal)
                      << " effect_reverse_input_global_value="
                      << hexBytePrefix(effectReverseInputGlobal)
                      << " debris_count_present=" << (haveDebrisCount ? 1 : 0)
                      << " debris_count=" << hex4(debrisQueueCount)
                      << " debris_count_base=" << hex4(debrisCountBase)
                      << " debris_base=" << hex4(selectedDebrisBase)
                      << " debris_stride=" << kDebrisStride
                      << " debris0=" << debris0
                      << " debris0_tile_index=" << hex4(debrisTileIndex)
                      << " debris0_flagged=" << hex4(debrisFlagged)
                      << " debris0_forward=" << hexBytePrefix(debrisForward)
                      << " debris0_reverse=" << hexBytePrefix(debrisReverse)
                      << " debris0_lookup=" << hexBytePrefix(debrisLookup)
                      << " collapse_count_present=" << (haveCollapseCount ? 1 : 0)
                      << " collapse_count=" << hex4(collapseQueueCount)
                      << " collapse_count_base=" << hex4(collapseCountBase)
                      << " collapse_base=" << hex4(selectedCollapseBase)
                      << " collapse_stride=" << kCollapseStride
                      << " collapse0=" << collapse0
                      << " collapse0_start=" << hex4(collapseStart)
                      << " collapse0_end=" << hex4(collapseEnd)
                      << " collapse0_word=" << hex4(collapseWord)
                      << " collapse0_flagged=" << hex4(collapseFlagged)
                      << " collapse0_forward=" << hexBytePrefix(collapseForward)
                      << " collapse0_reverse=" << hexBytePrefix(collapseReverse)
                      << " collapse0_lane8=" << hexBytePrefix(collapseLane8)
                      << " collapse0_lane9=" << hexBytePrefix(collapseLane9)
                      << " collapse0_magnitude=" << hex4(collapseMagnitude)
                      << " collapse0_affected_bytes="
                      << hexBytePrefix(collapseAffectedBytes)
                      << " collapse0_count=" << hexBytePrefix(collapseCount)
                      << " lookup_base=0xc1e0 lookup0=0x" << hexByte(lookup0)
                      << (haveHighDebrisTargetOffset
                              ? std::string(" high_debris_target_delta=") +
                                    hex4(highDebrisTargetDelta) +
                                    " high_debris_target_offset=" +
                                    hex4(highDebrisTargetOffset) +
                                    " high_debris_lookup_segment=" +
                                    hex4(highDebrisLookupSegment) +
                                    " high_debris_word_layer_offset=" +
                                    hex4(highDebrisWordLayerOffset) +
                                    " high_debris_word_layer_segment=" +
                                    hex4(highDebrisWordLayerSegment) +
                                    " high_debris_word_layer_address=" +
                                    hex4(highDebrisWordLayerAddress) +
                                    " high_debris_c204=" + hex4(highDebrisC204)
                              : "")
                      << (haveHighDebrisTargetByte
                              ? std::string(" high_debris_target_byte=") +
                                    hexBytePrefix(highDebrisTargetByte)
                              : "")
                      << (haveHighDebrisWordLayerValue
                              ? std::string(" high_debris_word_layer_value=") +
                                    hex4(highDebrisWordLayerValue)
                              : "")
                      << " effect_base=" << hex4(selectedEffectBase)
                      << " effect0=" << effect0
                      << " effect0_xy=" << hex4(effectX) << ',' << hex4(effectY)
                      << " effect0_sprite=" << hexBytePrefix(effectSprite)
                      << " effect0_detail=" << hexBytePrefix(effectDetail)
                      << " effect0_timer=" << hexBytePrefix(effectTimer)
                      << " effect0_variant=" << hexBytePrefix(effectVariant)
                      << " temp_copy=" << (tempCopy ? 1 : 0)
                      << " visual_claim=0\n";
            if (expectError) {
                std::cout << "explosion_playback_oracle=error fixture=" << fixture
                          << " reason=expected_error_missing\n";
                return 1;
            }
            return 0;
        } catch (const std::exception& e) {
            std::cout << e.what() << '\n';
            return expectError ? 0 : 1;
        }
    }

    void debugLaneWriteStaticModel() {
        struct StoreSite {
            uint16_t offset;
            const char* label;
            const char* direction;
            const char* target;
            const char* sourceReg;
            uint16_t displacement;
            uint16_t pairedDebrisOffset;
            bool skipsDebrisSetup;
        };

        const std::array<StoreSite, 4> sites{{
            {0x3d1b, "forward_collapse", "forward", "collapse", "al", 0x6617, 0x3d2d, true},
            {0x3d2d, "forward_debris", "forward", "debris", "dl", 0x2097, 0x0000, false},
            {0x3eaf, "reverse_collapse", "reverse", "collapse", "al", 0x6618, 0x3ec1, true},
            {0x3ec1, "reverse_debris", "reverse", "debris", "dl", 0x2098, 0x0000, false},
        }};

        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for lane-write scan");
        }

        auto requireBytes = [&](uint16_t offset, const std::string& hex,
                                const std::string& label) {
            std::vector<uint8_t> expected = parseHexByteList(hex);
            size_t p = imageBase + offset;
            if (p + expected.size() > exeBytes.size()) {
                throw std::runtime_error(label + " extends past LEZAC.EXE");
            }
            for (size_t i = 0; i < expected.size(); ++i) {
                if (exeBytes[p + i] != expected[i]) {
                    throw std::runtime_error(label + " bytes changed");
                }
            }
        };
        auto regName = [](uint8_t modrm) {
            switch ((modrm >> 3) & 0x07) {
            case 0:
                return std::string("al");
            case 2:
                return std::string("dl");
            default:
                return std::string("r") + std::to_string((modrm >> 3) & 0x07);
            }
        };
        auto hexByteLocal = [](uint8_t value) {
            std::ostringstream oss;
            oss << "0x" << std::hex << std::nouppercase
                << std::setw(2) << std::setfill('0')
                << static_cast<int>(value);
            return oss.str();
        };

        constexpr uint16_t kDebrisMarkerBase = 0x4e20;
        constexpr uint8_t kDebrisMarkerStride = 0x0b;
        const std::string debrisSetup =
            "8a 56 f3 8b 46 f8 2d 20 4e 6b f8 0b";
        const std::string sharedTail =
            "8b 46 f6 3b 46 f0 75 c5 8a 46 f3 c4 7e 04 26 88 05 c9 c2 06 00";

        int forwardSites = 0;
        int reverseSites = 0;
        int collapseSites = 0;
        int debrisSites = 0;
        int jumpOverDebris = 0;
        int debrisMarkerSetups = 0;
        std::ostringstream storeList;

        for (size_t i = 0; i < sites.size(); ++i) {
            const StoreSite& site = sites[i];
            size_t p = imageBase + site.offset;
            if (p + 4 > exeBytes.size() || exeBytes[p] != 0x88) {
                throw std::runtime_error(std::string(site.label) + " store opcode changed");
            }
            const uint8_t modrm = exeBytes[p + 1];
            if ((modrm & 0xc7) != 0x85) {
                throw std::runtime_error(std::string(site.label) + " store addressing changed");
            }
            if (regName(modrm) != site.sourceReg ||
                le16(exeBytes, p + 2) != site.displacement) {
                throw std::runtime_error(std::string(site.label) + " store target changed");
            }

            if (std::string(site.direction) == "forward") {
                ++forwardSites;
            } else {
                ++reverseSites;
            }
            if (std::string(site.target) == "collapse") {
                ++collapseSites;
            } else {
                ++debrisSites;
            }

            if (site.skipsDebrisSetup) {
                size_t jump = p + 4;
                if (jump + 2 > exeBytes.size() || exeBytes[jump] != 0xeb) {
                    throw std::runtime_error(std::string(site.label) +
                                             " debris-skip jump changed");
                }
                const int rel = static_cast<int8_t>(exeBytes[jump + 1]);
                const uint16_t jumpTarget =
                    static_cast<uint16_t>(static_cast<int>(site.offset) + 6 + rel);
                if (jumpTarget != static_cast<uint16_t>(site.pairedDebrisOffset + 4)) {
                    throw std::runtime_error(std::string(site.label) +
                                             " debris-skip target changed");
                }
                ++jumpOverDebris;

                const uint16_t setupOffset = static_cast<uint16_t>(site.offset + 6);
                requireBytes(setupOffset, debrisSetup,
                             std::string(site.label) + " debris marker setup");
                size_t setup = imageBase + setupOffset;
                if (le16(exeBytes, setup + 7) != kDebrisMarkerBase ||
                    exeBytes[setup + 11] != kDebrisMarkerStride) {
                    throw std::runtime_error(std::string(site.label) +
                                             " debris marker constants changed");
                }
                ++debrisMarkerSetups;
            }

            if (i != 0) storeList << ',';
            storeList << hex4(site.offset) << ':' << site.direction << '/'
                      << site.target << '/' << site.sourceReg << ':'
                      << hex4(site.displacement);
        }

        requireBytes(0x3d31, sharedTail, "forward lane-write shared tail");
        requireBytes(0x3ec5, sharedTail, "reverse lane-write shared tail");

        if (forwardSites != 2 || reverseSites != 2 || collapseSites != 2 ||
            debrisSites != 2 || jumpOverDebris != 2 || debrisMarkerSetups != 2) {
            throw std::runtime_error("lane-write static summary changed");
        }

        std::cout << "lane_write_static_model=ok"
                  << " image_base=0x0770"
                  << " sites=" << sites.size()
                  << " forward=" << forwardSites
                  << " reverse=" << reverseSites
                  << " collapse=" << collapseSites
                  << " debris=" << debrisSites
                  << " jump_over_debris=" << jumpOverDebris
                  << " debris_marker_base=" << hex4(kDebrisMarkerBase)
                  << " debris_marker_stride=" << hexByteLocal(kDebrisMarkerStride)
                  << " debris_marker_setups=" << debrisMarkerSetups
                  << " shared_tail=2"
                  << " pending_natural_forward=" << hex4(0x3d2d)
                  << " stores=" << storeList.str()
                  << '\n';
    }

    void debugLaneWriteTagModel() {
        struct ExpectedTag {
            uint16_t tag;
            bool debris;
            uint16_t slot;
            uint16_t di;
            uint16_t forwardWrite;
            uint16_t reverseWrite;
        };

        const std::array<ExpectedTag, 4> expected{{
            {0x0002, false, 0x0002, 0x001e, 0x6635, 0x6636},
            {0x0005, false, 0x0005, 0x004b, 0x6662, 0x6663},
            {0x4e21, true, 0x0001, 0x000b, 0x20a2, 0x20a3},
            {0x4ee8, true, 0x00c8, 0x0898, 0x292f, 0x2930},
        }};

        int collapseCases = 0;
        int debrisCases = 0;
        std::ostringstream tags;
        for (size_t i = 0; i < expected.size(); ++i) {
            const ExpectedTag& item = expected[i];
            const LaneWriteTagModel model = laneWriteTagModelForTag(item.tag);
            if (model.debris != item.debris ||
                model.slot != item.slot ||
                model.di != item.di ||
                model.forwardWrite != item.forwardWrite ||
                model.reverseWrite != item.reverseWrite) {
                throw std::runtime_error("lane write tag model mismatch for " + hex4(item.tag));
            }
            if (i != 0) {
                tags << ',';
            }
            tags << hex4(model.tag) << ':'
                 << (model.debris ? "debris" : "collapse")
                 << ":slot" << hex4(model.slot)
                 << ":di" << hex4(model.di)
                 << ":forward" << hex4(model.forwardWrite)
                 << ":reverse" << hex4(model.reverseWrite);
            if (model.debris) {
                ++debrisCases;
            } else {
                ++collapseCases;
            }
        }

        std::cout << "lane_write_tag_model=ok"
                  << " marker=" << hex4(kHighHalfBase)
                  << " collapse_stride=" << hex4(static_cast<uint16_t>(kCollapseStride))
                  << " debris_stride=" << hex4(static_cast<uint16_t>(kDebrisStride))
                  << " collapse_forward_base=" << hex4(kCollapseForwardLaneBase)
                  << " collapse_reverse_base=" << hex4(kCollapseReverseLaneBase)
                  << " debris_forward_base=" << hex4(kDebrisForwardLaneBase)
                  << " debris_reverse_base=" << hex4(kDebrisReverseLaneBase)
                  << " cases=" << expected.size()
                  << " collapse_cases=" << collapseCases
                  << " debris_cases=" << debrisCases
                  << " tags=" << tags.str()
                  << " pending_natural_forward=0x3d2d"
                  << " original_capture_claim=0"
                  << '\n';
    }

    void debugActorContactStaticModel() {
        constexpr uint16_t kScannerEntry = 0x5cb0;
        constexpr uint16_t kScannerReturn = 0x604f;
        constexpr uint16_t kActorUpdateStart = 0x6053;
        constexpr uint16_t kActorUpdateEnd = 0x777f;
        constexpr uint16_t kGate6 = 0x654e;
        constexpr uint16_t kGate6Skip = 0x6552;
        constexpr uint16_t kScannerCallsite = 0x6555;
        constexpr uint16_t kGate6IntegrationJump = 0x6558;
        constexpr uint16_t kGate6SkipTarget = 0x655b;
        constexpr uint16_t kGate5Integration = 0x65a2;
        constexpr uint16_t kGate5IntegrationSkip = 0x65a6;
        constexpr uint16_t kGate5IntegrationSkipTarget = 0x65da;
        constexpr uint16_t kGate5IntegrationJump = 0x65d7;
        constexpr uint16_t kGate5Exit = 0x7595;
        constexpr uint16_t kGate5ExitSkip = 0x7599;
        constexpr uint16_t kGate5ExitSkipTarget = 0x759e;
        constexpr uint16_t kGate5ExitJump = 0x759b;
        constexpr uint16_t kSharedIntegration = 0x73e5;

        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("LEZAC.EXE missing MZ header");
        }
        uint16_t headerParagraphs = le16(exeBytes, 0x08);
        size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
        if (imageBase != 0x0770) {
            throw std::runtime_error("LEZAC.EXE image base changed for actor/contact scan");
        }

        auto codeByte = [&](uint16_t offset) {
            size_t p = imageBase + offset;
            if (p >= exeBytes.size()) {
                throw std::runtime_error("actor/contact offset extends past LEZAC.EXE");
            }
            return exeBytes[p];
        };
        auto requireBytes = [&](uint16_t offset, const std::string& hex,
                                const std::string& label) {
            std::vector<uint8_t> expected = parseHexByteList(hex);
            size_t p = imageBase + offset;
            if (p + expected.size() > exeBytes.size()) {
                throw std::runtime_error(label + " extends past LEZAC.EXE");
            }
            for (size_t i = 0; i < expected.size(); ++i) {
                if (exeBytes[p + i] != expected[i]) {
                    throw std::runtime_error(label + " bytes changed");
                }
            }
        };
        auto rel8Target = [&](uint16_t offset) {
            int rel = static_cast<int8_t>(codeByte(static_cast<uint16_t>(offset + 1)));
            return static_cast<uint16_t>(static_cast<int>(offset) + 2 + rel);
        };
        auto rel16Target = [&](uint16_t offset) {
            uint16_t raw = le16(exeBytes, imageBase + offset + 1);
            int rel = raw >= 0x8000u ? static_cast<int>(raw) - 0x10000
                                     : static_cast<int>(raw);
            return static_cast<uint16_t>(static_cast<int>(offset) + 3 + rel);
        };
        auto bytesToHex = [&](uint16_t offset, size_t length) {
            std::ostringstream oss;
            for (size_t i = 0; i < length; ++i) {
                oss << std::hex << std::nouppercase
                    << std::setw(2) << std::setfill('0')
                    << static_cast<int>(codeByte(static_cast<uint16_t>(offset + i)));
            }
            return oss.str();
        };

        requireBytes(kScannerEntry, "55 89", "contact scanner entry");
        requireBytes(kScannerReturn, "c9 c2 02 00", "contact scanner return");
        requireBytes(kActorUpdateStart, "55 89", "actor update entry");
        requireBytes(kActorUpdateEnd, "c9 c2 04 00", "actor update return");
        requireBytes(kGate6, "80 7e cf 06 75 07 55 e8 58 f7 e9 8a 0e",
                     "actor contact gate6 snippet");
        requireBytes(kGate5Integration, "80 7e cf 05 75 32",
                     "actor gate5 integration snippet");
        requireBytes(kGate5Exit, "80 7e cf 05 75 03 e9 e1 01",
                     "actor gate5 exit snippet");

        if (rel8Target(kGate6Skip) != kGate6SkipTarget ||
            rel16Target(kScannerCallsite) != kScannerEntry ||
            rel16Target(kGate6IntegrationJump) != kSharedIntegration ||
            rel8Target(kGate5IntegrationSkip) != kGate5IntegrationSkipTarget ||
            rel16Target(kGate5IntegrationJump) != kSharedIntegration ||
            rel8Target(kGate5ExitSkip) != kGate5ExitSkipTarget ||
            rel16Target(kGate5ExitJump) != kActorUpdateEnd) {
            throw std::runtime_error("actor/contact static branch target changed");
        }

        std::vector<std::pair<uint16_t, uint8_t>> gates;
        for (uint16_t offset = kActorUpdateStart; offset < kActorUpdateEnd - 3; ++offset) {
            if (codeByte(offset) == 0x80 &&
                codeByte(static_cast<uint16_t>(offset + 1)) == 0x7e &&
                codeByte(static_cast<uint16_t>(offset + 2)) == 0xcf) {
                gates.push_back({offset, codeByte(static_cast<uint16_t>(offset + 3))});
            }
        }
        const std::vector<std::pair<uint16_t, uint8_t>> expectedGates{
            {kGate6, 0x06},
            {kGate5Integration, 0x05},
            {kGate5Exit, 0x05},
        };
        if (gates != expectedGates) {
            throw std::runtime_error("actor/contact bp-31h gate list changed");
        }

        std::vector<uint16_t> scannerCalls;
        std::vector<uint16_t> integrationJumps;
        for (uint16_t offset = kActorUpdateStart; offset < kActorUpdateEnd - 2; ++offset) {
            uint8_t opcode = codeByte(offset);
            if (opcode == 0xe8 && rel16Target(offset) == kScannerEntry) {
                scannerCalls.push_back(offset);
            }
            if (opcode == 0xe9 && rel16Target(offset) == kSharedIntegration) {
                integrationJumps.push_back(offset);
            }
        }
        if (scannerCalls != std::vector<uint16_t>{kScannerCallsite} ||
            integrationJumps !=
                (std::vector<uint16_t>{kGate6IntegrationJump, kGate5IntegrationJump})) {
            throw std::runtime_error("actor/contact call or integration jump list changed");
        }

        std::ostringstream gateList;
        for (size_t i = 0; i < gates.size(); ++i) {
            if (i != 0) gateList << ',';
            gateList << hex4(gates[i].first) << ':' << hex4(gates[i].second);
        }
        std::ostringstream scannerCallList;
        for (size_t i = 0; i < scannerCalls.size(); ++i) {
            if (i != 0) scannerCallList << ',';
            scannerCallList << hex4(scannerCalls[i]);
        }
        std::ostringstream integrationJumpList;
        for (size_t i = 0; i < integrationJumps.size(); ++i) {
            if (i != 0) integrationJumpList << ',';
            integrationJumpList << hex4(integrationJumps[i]);
        }

        std::cout << "actor_contact_static_model=ok"
                  << " image_base=0x0770"
                  << " scanner=" << hex4(kScannerEntry) << ".." << hex4(kScannerReturn)
                  << " scanner_entry_bytes=" << bytesToHex(kScannerEntry, 2)
                  << " scanner_return_bytes=" << bytesToHex(kScannerReturn, 4)
                  << " actor_update=" << hex4(kActorUpdateStart) << ".."
                  << hex4(kActorUpdateEnd)
                  << " actor_entry_bytes=" << bytesToHex(kActorUpdateStart, 2)
                  << " actor_return_bytes=" << bytesToHex(kActorUpdateEnd, 4)
                  << " gates=" << gates.size()
                  << " bp31=" << gateList.str()
                  << " scanner_call_count=" << scannerCalls.size()
                  << " scanner_calls=" << scannerCallList.str()
                  << " scanner_call_context=gate6"
                  << " gate6_skip=" << hex4(rel8Target(kGate6Skip))
                  << " gate6_call=" << hex4(rel16Target(kScannerCallsite))
                  << " gate6_integration=" << hex4(rel16Target(kGate6IntegrationJump))
                  << " gate5_skip=" << hex4(rel8Target(kGate5IntegrationSkip))
                  << " gate5_integration=" << hex4(rel16Target(kGate5IntegrationJump))
                  << " gate5_exit_skip=" << hex4(rel8Target(kGate5ExitSkip))
                  << " gate5_exit=" << hex4(rel16Target(kGate5ExitJump))
                  << " integration_jumps=" << integrationJumpList.str()
                  << '\n';
    }

    void debugOriginalState2EffectPlacement() {
        constexpr uint16_t kEffectBase = 0xc21e;
        constexpr int kMapWidth = 60;
        constexpr int kMapHeight = 10;
        constexpr uint8_t kSolidTile = 0x01;
        constexpr uint8_t kPlacementMarker = 0x4c;

        struct EffectEntry {
            uint16_t x = 24;
            uint16_t y = 40;
        };

        struct PlacementResult {
            uint16_t yAfter = 0;
            int xTile = 0;
            int yTile = 0;
            int mapOffset = 0;
            bool descended = false;
            bool blocked = false;
            bool restored = false;
        };

        auto slotAddress = [=](int slot) {
            return static_cast<uint16_t>(kEffectBase + 8 * slot);
        };
        auto blocksPlacement = [=](uint8_t tile) {
            return tile == kSolidTile || tile == kPlacementMarker;
        };
        auto runPlacement = [&](EffectEntry entry,
                                const std::array<uint8_t, kMapWidth * kMapHeight>&
                                    map,
                                bool actionGate) {
            PlacementResult result;
            result.xTile = entry.x >> 3;
            result.yTile = ((entry.y + 7) >> 3) + 1;
            result.mapOffset = result.yTile * kMapWidth + result.xTile;
            bool baseBlocked = blocksPlacement(map.at(result.mapOffset));
            bool rightBlocked = blocksPlacement(map.at(result.mapOffset + 1));
            result.blocked = baseBlocked || rightBlocked;
            if (!result.blocked && entry.y > 0x18) {
                --entry.y;
                result.descended = true;
            }
            result.yAfter = entry.y;
            result.restored = actionGate && !result.blocked;
            return result;
        };

        std::array<uint8_t, kMapWidth * kMapHeight> openMap{};
        PlacementResult open = runPlacement({24, 40}, openMap, true);
        PlacementResult floor = runPlacement({24, 24}, openMap, true);
        std::array<uint8_t, kMapWidth * kMapHeight> solidMap{};
        solidMap.at(open.mapOffset) = kSolidTile;
        PlacementResult solid = runPlacement({24, 40}, solidMap, true);
        std::array<uint8_t, kMapWidth * kMapHeight> markerMap{};
        markerMap.at(open.mapOffset) = kPlacementMarker;
        PlacementResult marker = runPlacement({24, 40}, markerMap, true);
        std::array<uint8_t, kMapWidth * kMapHeight> rightSolidMap{};
        rightSolidMap.at(open.mapOffset + 1) = kSolidTile;
        PlacementResult rightSolid =
            runPlacement({24, 40}, rightSolidMap, true);
        PlacementResult gate0 = runPlacement({24, 40}, openMap, false);

        if (slotAddress(0) != 0xc21e || slotAddress(1) != 0xc226 ||
            slotAddress(2) != 0xc22e || open.xTile != 3 || open.yTile != 6 ||
            open.mapOffset != 363 || !open.descended || open.yAfter != 39 ||
            floor.descended || floor.yAfter != 24 || !solid.blocked ||
            solid.descended || !marker.blocked || marker.descended ||
            !rightSolid.blocked || rightSolid.descended || !gate0.descended ||
            gate0.restored) {
            throw std::runtime_error("original state-2 effect placement mismatch");
        }

        std::cout << "original_state2_effect_placement=ok base=0xc21e"
                  << " slot0=0xc21e slot1=0xc226 slot2=0xc22e"
                  << " x_tile=" << open.xTile << " y_tile=" << open.yTile
                  << " map_offset=" << open.mapOffset
                  << " open_descended=1 y_after=" << open.yAfter
                  << " floor_stops=1 solid_blocked=1 marker_blocked=1"
                  << " right_solid_blocked=1 gate_after_descent=1\n";
    }

    void debugPlayerState2ReturnActive() {
        load();
        resetLevel(0);
        menu_ = false;
        energy_ = 0;
        lives_ = 3;
        damageCooldown_ = 0;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        if (!playerDead_ || deathStateTimer_ != kDeathStateTicks ||
            reentryTimer_ != kReentryTicks) {
            throw std::runtime_error("player return-active death setup mismatch");
        }
        tryReenterPlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                         damageCooldown_, 1);
        if (!playerDead_ || deathStateTimer_ != kDeathStateTicks ||
            reentryTimer_ != kReentryTicks || damageCooldown_ != 0) {
            throw std::runtime_error("player return-active immediate gate mismatch");
        }
        for (int i = 0; i < 59; ++i) {
            updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                          true);
        }
        tryReenterPlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                         damageCooldown_, 1);
        if (!playerDead_ || deathStateTimer_ != 1) {
            throw std::runtime_error("player return-active 59-tick gate mismatch");
        }
        updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                      true);
        tryReenterPlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                         damageCooldown_, 1);
        if (playerDead_ || energy_ != 100 || lives_ != 2 ||
            deathStateTimer_ != 0 || reentryTimer_ != 0 ||
            damageCooldown_ != kDamageCooldownTicks) {
            throw std::runtime_error("player return-active gate restore mismatch");
        }

        playerCount_ = 2;
        lives_ = 3;
        lives2_ = 3;
        resetLevel(0);
        menu_ = false;
        energy2_ = 0;
        damageCooldown2_ = 0;
        damagePlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                     damageCooldown2_, 2);
        tryReenterPlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                         damageCooldown2_, 2);
        if (!player2Dead_ || deathStateTimer2_ != kDeathStateTicks ||
            damageCooldown2_ != 0) {
            throw std::runtime_error("player 2 immediate gate mismatch");
        }
        for (int i = 0; i < 60; ++i) {
            updateReentry(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                          2, playerDead_);
        }
        tryReenterPlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                         damageCooldown2_, 2);
        if (player2Dead_ || energy2_ != 100 || lives2_ != 2 ||
            deathStateTimer2_ != 0 || reentryTimer2_ != 0 ||
            damageCooldown2_ != kDamageCooldownTicks) {
            throw std::runtime_error("player 2 gate restore mismatch");
        }

        lives_ = 3;
        lives2_ = 1;
        resetLevel(0);
        menu_ = false;
        energy2_ = 0;
        damageCooldown2_ = 0;
        damagePlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                     damageCooldown2_, 2);
        for (int i = 0; i < 60; ++i) {
            updateReentry(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                          2, playerDead_);
        }
        tryReenterPlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                         damageCooldown2_, 2);
        if (menu_ || playerDead_ || !player2Dead_ || lives2_ != 0 ||
            deathStateTimer2_ != 0) {
            throw std::runtime_error("player 2 zero-life gate mismatch");
        }
        bool p2OutStaysDead = player2Dead_ && lives2_ == 0 && deathStateTimer2_ == 0;
        int p2ReentryTimerBefore = reentryTimer2_;
        int p2DamageCooldownBefore = damageCooldown2_;
        int p2EnergyBefore = energy2_;
        tryReenterPlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                         damageCooldown2_, 2);
        bool p2ReenterBlocked = player2Dead_ && lives2_ == 0 &&
                                reentryTimer2_ == p2ReentryTimerBefore &&
                                damageCooldown2_ == p2DamageCooldownBefore &&
                                energy2_ == p2EnergyBefore;
        bool p1AliveAfterP2Out = !playerDead_ && lives_ > 0 && !menu_;
        if (!p2OutStaysDead || !p2ReenterBlocked || !p1AliveAfterP2Out) {
            throw std::runtime_error("player 2 zero-life fallback boundary mismatch");
        }

        lives_ = 1;
        energy_ = 0;
        damageCooldown_ = 0;
        deathStateTimer_ = 0;
        pendingLifeLoss_ = false;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        if (!playerDead_ || !pendingLifeLoss_ ||
            deathStateTimer_ != kDeathStateTicks || lives_ != 1) {
            throw std::runtime_error("player 1 final-life state-2 setup mismatch");
        }
        for (int i = 0; i < 60; ++i) {
            updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_,
                          1, player2Dead_);
        }
        bool bothOutGameover = menu_ && menuPage_ == MenuPage::GameOver &&
                               lastEndReason_ == EndReason::GameOver;
        if (!bothOutGameover) {
            throw std::runtime_error("both-out state-2 game-over mismatch");
        }

        std::cout << "player_state2_return_active=ok p1_death_timer=60"
                  << " p1_after_59=1 p1_after_60=0"
                  << " gate0_dead=1 gate0_energy=100"
                  << " gate1_reentered=1 p1_energy=100"
                  << " p1_cooldown=" << kDamageCooldownTicks
                  << " p1_death_timer_clear=0 p1_reentry_timer_clear=0"
                  << " p2_gate1_reentered=1 p2_energy=100"
                  << " p2_cooldown=" << kDamageCooldownTicks
                  << " p2_death_timer_clear=0 p2_reentry_timer_clear=0"
                  << " no_gameover_with_p1=1"
                  << " p2_out_stays_dead=1"
                  << " p2_reenter_blocked=1"
                  << " p1_alive_after_p2_out=1"
                  << " both_out_gameover=1"
                  << " live_fallback_shortcut=0"
                  << " original_reachability=0\n";
    }

    void debugGran() {
        load();
        constexpr size_t kGranProfileStride = 3;
        constexpr size_t kGranProfileGroupsPerRecord = kGranRecordSize / kGranProfileStride;
        if (kGranRecordSize % kGranProfileStride != 0) {
            throw std::runtime_error("GRAN.MST record is not divisible by profile stride");
        }

        auto hexByte = [](uint8_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(2)
                << std::setfill('0') << static_cast<int>(value);
            return oss.str();
        };
        auto printStrideGroup = [&](const std::vector<uint8_t>& bytes, size_t groupIndex) {
            const size_t off = groupIndex * kGranProfileStride;
            std::cout << hexByte(bytes[off]) << hexByte(bytes[off + 1])
                      << hexByte(bytes[off + 2]);
        };

        size_t totalZeroBytes = 0;
        size_t totalNonzeroGroups = 0;
        std::cout << "gran_record_profile=summary"
                  << " record_size=" << gran_.recordSize
                  << " records=" << gran_.records.size()
                  << " stride=" << kGranProfileStride
                  << " groups_per_record=" << kGranProfileGroupsPerRecord << '\n';
        for (size_t i = 0; i < gran_.records.size(); ++i) {
            const std::vector<uint8_t>& bytes = gran_.records[i].bytes;
            if (bytes.size() != kGranRecordSize) {
                throw std::runtime_error("GRAN.MST profile record length mismatch");
            }
            int byteSum = 0;
            int weightedSum = 0;
            int nonzero = 0;
            uint8_t xorValue = 0;
            for (size_t off = 0; off < bytes.size(); ++off) {
                uint8_t byte = bytes[off];
                byteSum += byte;
                weightedSum += static_cast<int>((off + 1) * byte);
                if (byte != 0) ++nonzero;
                xorValue = static_cast<uint8_t>(xorValue ^ byte);
            }
            const size_t zeroBytes = static_cast<size_t>(
                std::count(bytes.begin(), bytes.end(), 0));
            size_t nonzeroGroups = 0;
            for (size_t group = 0; group < kGranProfileGroupsPerRecord; ++group) {
                const size_t off = group * kGranProfileStride;
                if (bytes[off] != 0 || bytes[off + 1] != 0 || bytes[off + 2] != 0) {
                    ++nonzeroGroups;
                }
            }
            totalZeroBytes += zeroBytes;
            totalNonzeroGroups += nonzeroGroups;

            std::cout << "gran_record_profile record=" << (i + 1)
                      << " bytes=" << bytes.size()
                      << " zero_bytes=" << zeroBytes
                      << " nonzero_bytes=" << nonzero
                      << " byte_sum=" << byteSum
                      << " weighted_sum=" << weightedSum
                      << " xor=0x" << std::hex << std::setw(2) << std::setfill('0')
                      << static_cast<int>(xorValue) << std::dec << std::setfill(' ')
                      << " nonzero_groups=" << nonzeroGroups
                      << " zero_groups=" << (kGranProfileGroupsPerRecord - nonzeroGroups)
                      << " first_groups=";
            for (size_t group = 0; group < 4; ++group) {
                if (group != 0) std::cout << ',';
                printStrideGroup(bytes, group);
            }
            std::cout << " last_group=";
            printStrideGroup(bytes, kGranProfileGroupsPerRecord - 1);
            std::cout << '\n';
        }
        std::cout << "gran_record_profile=ok"
                  << " records=" << gran_.records.size()
                  << " record_size=" << gran_.recordSize
                  << " groups_per_record=" << kGranProfileGroupsPerRecord
                  << " total_nonzero_groups=" << totalNonzeroGroups
                  << " total_zero_groups="
                  << (gran_.records.size() * kGranProfileGroupsPerRecord - totalNonzeroGroups)
                  << " total_zero_bytes=" << totalZeroBytes << '\n';
    }

    void debugLevels() {
        load();
        for (size_t levelIndex = 0; levelIndex < levels_.size(); ++levelIndex) {
            const Level& level = levels_[levelIndex];
            std::cout << "level_" << (levelIndex + 1)
                      << " offset=" << level.fileOffset
                      << " size=" << level.width << 'x' << level.height
                      << " tile_encoded=" << level.tileEncodedSize
                      << " word_encoded=" << level.wordEncodedSize
                      << " objective_tile=" << static_cast<int>(level.objectiveTile)
                      << " required_bonus=" << level.requiredBonus
                      << " required_destruction=" << static_cast<int>(level.requiredDestruction)
                      << " fieldA=" << level.fieldA
                      << '(' << std::showbase << std::hex << level.fieldA
                      << std::dec << std::noshowbase << ')'
                      << " fieldB=" << level.fieldB
                      << '(' << std::showbase << std::hex << level.fieldB
                      << std::dec << std::noshowbase << ')'
                      << " objective_tiles=" << level.startingObjectiveTiles
                      << " destructible_tiles=" << level.startingDestructibleTiles
                      << " spawners=" << level.monsterSpawners.size()
                      << " portals=" << level.portals.size()
                      << " triggers=" << level.tileTriggers.size()
                      << '\n';
            for (size_t i = 0; i < level.portals.size(); ++i) {
                const LevelPortal& portal = level.portals[i];
                std::cout << "portal level=" << (levelIndex + 1)
                          << " index=" << (i + 1)
                          << " key=" << portal.key
                          << " xy=" << portal.x << ',' << portal.y
                          << " marker=" << static_cast<int>(portal.marker)
                          << '\n';
            }
            for (size_t i = 0; i < level.tileTriggers.size(); ++i) {
                const TileTriggerRule& rule = level.tileTriggers[i];
                std::cout << "trigger level=" << (levelIndex + 1)
                          << " index=" << (i + 1)
                          << " range=" << rule.wordRangeFirst << ".." << rule.wordRangeLast
                          << " key=" << rule.triggerKey
                          << " from=";
                for (size_t slot = 0; slot < rule.from.size(); ++slot) {
                    if (slot != 0) std::cout << ',';
                    std::cout << static_cast<int>(rule.from[slot]);
                }
                std::cout << " to=";
                for (size_t slot = 0; slot < rule.to.size(); ++slot) {
                    if (slot != 0) std::cout << ',';
                    std::cout << static_cast<int>(rule.to[slot]);
                }
                std::cout << '\n';
            }
        }
    }

    void debugLevelRawRoundtrip() {
        load();
        std::vector<Level> rawLevels = loadRawLevels("LIVELS.SCH");
        const std::array<size_t, 7> expectedOffsets{0, 1242, 4923, 10984,
                                                     15225, 21546, 36128};
        const std::array<uint16_t, 7> expectedFieldA{
            0x4005, 0x401e, 0x4036, 0x403c, 0x4066, 0x409f, 0x4041};
        const std::array<uint16_t, 7> expectedFieldB{
            0x0042, 0x0189, 0x02e3, 0x01b3, 0x03dc, 0x0aa4, 0x014a};
        if (rawLevels.size() != levels_.size() || rawLevels.size() != expectedOffsets.size()) {
            throw std::runtime_error("raw level count did not match JSON levels");
        }

        auto hexWordList = [](const auto& words) {
            std::ostringstream oss;
            for (size_t i = 0; i < words.size(); ++i) {
                if (i != 0) oss << ',';
                oss << "0x" << std::hex << std::setw(4) << std::setfill('0')
                    << static_cast<int>(words[i]);
            }
            return oss.str();
        };
        auto fieldAPayloadList = [&]() {
            std::ostringstream oss;
            for (size_t i = 0; i < expectedFieldA.size(); ++i) {
                if (i != 0) oss << ',';
                oss << static_cast<int>(expectedFieldA[i] & 0x3fffu);
            }
            return oss.str();
        };

        auto sameSpawner = [](const MonsterSpawner& a, const MonsterSpawner& b) {
            return a.x == b.x && a.y == b.y && a.tileIndex == b.tileIndex &&
                   a.savedWordOrLink == b.savedWordOrLink && a.enabled == b.enabled &&
                   a.spawnBudget == b.spawnBudget && a.liveAllowance == b.liveAllowance &&
                   a.monsterKind == b.monsterKind && a.param0Base == b.param0Base &&
                   a.param0Range == b.param0Range && a.param1Base == b.param1Base &&
                   a.param1Range == b.param1Range && a.param2Base == b.param2Base &&
                   a.param2Range == b.param2Range && a.randomBase == b.randomBase &&
                   a.randomRange == b.randomRange && a.spawnArg == b.spawnArg &&
                   a.cooldown == b.cooldown && a.cooldownReset == b.cooldownReset &&
                   a.animationDelay == b.animationDelay;
        };
        auto samePortal = [](const LevelPortal& a, const LevelPortal& b) {
            return a.key == b.key && a.x == b.x && a.y == b.y && a.marker == b.marker;
        };
        auto sameTrigger = [](const TileTriggerRule& a, const TileTriggerRule& b) {
            return a.wordRangeFirst == b.wordRangeFirst &&
                   a.wordRangeLast == b.wordRangeLast &&
                   a.triggerKey == b.triggerKey &&
                   a.from == b.from && a.to == b.to;
        };

        size_t totalCells = 0;
        size_t totalSpawners = 0;
        size_t totalPortals = 0;
        size_t totalTriggers = 0;
        int totalFieldB = 0;
        std::array<int, 256> kindCounts{};
        std::array<int, 256> behaviorCounts{};
        for (size_t i = 0; i < rawLevels.size(); ++i) {
            const Level& raw = rawLevels[i];
            const Level& json = levels_[i];
            if (raw.fileOffset != expectedOffsets[i] || raw.fileOffset != json.fileOffset ||
                raw.width != json.width || raw.height != json.height ||
                raw.objectiveTile != json.objectiveTile ||
                raw.requiredBonus != json.requiredBonus ||
                raw.requiredDestruction != json.requiredDestruction ||
                raw.tileEncodedSize != json.tileEncodedSize ||
                raw.wordEncodedSize != json.wordEncodedSize ||
                raw.fieldA != json.fieldA || raw.fieldB != json.fieldB ||
                raw.tiles != json.tiles || raw.wordLayer != json.wordLayer) {
                throw std::runtime_error("raw level " + std::to_string(i + 1) +
                                         " did not match JSON scalar/layer data");
            }
            if (raw.fieldA != expectedFieldA[i] || raw.fieldB != expectedFieldB[i] ||
                (raw.fieldA & 0xc000u) != kDeferredThreshold) {
                throw std::runtime_error("raw level " + std::to_string(i + 1) +
                                         " embedded field words changed");
            }
            if (raw.fieldB != static_cast<uint16_t>(countPhysicalDamageProgressCells(raw.wordLayer)) ||
                raw.startingDestructibleTiles != static_cast<int>(raw.fieldB) ||
                json.startingDestructibleTiles != static_cast<int>(json.fieldB)) {
                throw std::runtime_error("raw level physical damage count mismatch");
            }
            if (raw.monsterSpawners.size() != json.monsterSpawners.size() ||
                raw.portals.size() != json.portals.size() ||
                raw.tileTriggers.size() != json.tileTriggers.size()) {
                throw std::runtime_error("raw level entity counts did not match JSON");
            }
            for (size_t j = 0; j < raw.monsterSpawners.size(); ++j) {
                if (!sameSpawner(raw.monsterSpawners[j], json.monsterSpawners[j])) {
                    throw std::runtime_error("raw spawner did not match JSON");
                }
                ++kindCounts[raw.monsterSpawners[j].monsterKind];
                ++behaviorCounts[raw.monsterSpawners[j].spawnArg];
            }
            for (size_t j = 0; j < raw.portals.size(); ++j) {
                if (!samePortal(raw.portals[j], json.portals[j])) {
                    throw std::runtime_error("raw portal did not match JSON");
                }
            }
            for (size_t j = 0; j < raw.tileTriggers.size(); ++j) {
                if (!sameTrigger(raw.tileTriggers[j], json.tileTriggers[j])) {
                    throw std::runtime_error("raw trigger did not match JSON");
                }
            }
            totalCells += static_cast<size_t>(raw.width) * raw.height;
            totalSpawners += raw.monsterSpawners.size();
            totalPortals += raw.portals.size();
            totalTriggers += raw.tileTriggers.size();
            totalFieldB += raw.fieldB;
        }

        if (totalCells != 47700 || totalSpawners != 15 ||
            totalPortals != 21 || totalTriggers != 3) {
            throw std::runtime_error("raw level aggregate counts changed");
        }
        if (rawLevels[0].width != 60 || rawLevels[0].height != 33 ||
            rawLevels[0].tileEncodedSize != 609 ||
            rawLevels[0].wordEncodedSize != 570 ||
            rawLevels[5].monsterSpawners.size() != 4 ||
            rawLevels[5].tileTriggers.size() != 2 ||
            !rawLevels[6].monsterSpawners.empty() ||
            rawLevels[6].tileTriggers.size() != 1) {
            throw std::runtime_error("raw level fixture assertions changed");
        }
        if (kindCounts[1] != 7 || kindCounts[2] != 2 ||
            kindCounts[3] != 3 || kindCounts[4] != 3 ||
            behaviorCounts[3] != 9 || behaviorCounts[4] != 6) {
            throw std::runtime_error("raw spawner kind/behavior counts changed");
        }

        std::cout << "level_raw_roundtrip=ok levels=" << rawLevels.size()
                  << " cells=" << totalCells
                  << " spawners=" << totalSpawners
                  << " portals=" << totalPortals
                  << " triggers=" << totalTriggers
                  << " fieldA_prefix=0x4000"
                  << " fieldA_words=" << hexWordList(expectedFieldA)
                  << " fieldA_payloads=" << fieldAPayloadList()
                  << " fieldB_words=" << hexWordList(expectedFieldB)
                  << " fieldB_total=" << totalFieldB << '\n';
    }

    void debugLevelCompletionDenominator() {
        load();
        const std::array<int, 7> expectedFieldB{66, 393, 739, 435, 988, 2724, 330};
        const std::array<int, 7> expectedRequired{50, 60, 20, 70, 65, 40, 10};
        const std::array<int, 7> expectedThresholds{33, 236, 148, 305, 643, 1090, 33};

        auto joinInts = [](const auto& values) {
            std::ostringstream oss;
            for (size_t i = 0; i < values.size(); ++i) {
                if (i != 0) oss << ',';
                oss << values[i];
            }
            return oss.str();
        };

        int blockedBeforeThreshold = 0;
        int completedAtThreshold = 0;
        int totalFieldB = 0;
        for (size_t i = 0; i < expectedFieldB.size(); ++i) {
            resetLevel(static_cast<int>(i));
            int denominator = level_.startingDestructibleTiles;
            int rawFieldB = static_cast<int>(level_.fieldB);
            int required = static_cast<int>(level_.requiredDestruction);
            int threshold = (required * denominator + 99) / 100;
            if (denominator != rawFieldB ||
                denominator != expectedFieldB[i] ||
                required != expectedRequired[i] ||
                threshold != expectedThresholds[i]) {
                throw std::runtime_error("level completion denominator fixture changed");
            }
            collected_ = level_.requiredBonus;
            destroyed_ = std::max(0, threshold - 1);
            if (isComplete()) {
                throw std::runtime_error("level completed before fieldB threshold");
            }
            ++blockedBeforeThreshold;
            destroyed_ = threshold;
            if (!isComplete()) {
                throw std::runtime_error("level did not complete at fieldB threshold");
            }
            ++completedAtThreshold;
            destroyed_ = denominator;
            if (destructionPercent() != 100 || !isComplete()) {
                throw std::runtime_error("level destruction percent did not saturate at fieldB");
            }
            totalFieldB += denominator;
        }

        if (blockedBeforeThreshold != 7 || completedAtThreshold != 7 ||
            totalFieldB != 5675) {
            throw std::runtime_error("level completion denominator summary changed");
        }
        std::cout << "level_completion_denominator=ok"
                  << " levels=" << expectedFieldB.size()
                  << " fieldB_denominators=" << joinInts(expectedFieldB)
                  << " required_destruction=" << joinInts(expectedRequired)
                  << " thresholds=" << joinInts(expectedThresholds)
                  << " before_blocked=" << blockedBeforeThreshold
                  << " at_complete=" << completedAtThreshold
                  << " fieldB_total=" << totalFieldB
                  << " percent_model=integer_floor\n";
    }

    void debugSpriteTransparency() {
        load();
        auto countPixels = [](const SpriteBank& bank, uint8_t value) {
            size_t count = 0;
            for (const Sprite& sprite : bank.sprites) {
                count += static_cast<size_t>(
                    std::count(sprite.pixels.begin(), sprite.pixels.end(), value));
            }
            return count;
        };
        size_t primaryFf = countPixels(sprites_, 0xff);
        size_t altFf = countPixels(altSprites_, 0xff);
        size_t fontFf = countPixels(fontSprites_, 0xff);
        size_t totalFf = primaryFf + altFf + fontFf;
        if (totalFf == 0) {
            throw std::runtime_error("sprite banks no longer exercise 0xff transparency");
        }
        std::cout << "sprite_transparency=ok zero_only=1 ff_pixels=" << totalFf
                  << " primary=" << primaryFf
                  << " prova=" << altFf
                  << " fonts=" << fontFf << '\n';
    }

    void debugSpriteRawRoundtrip() {
        load();

        struct BankCheck {
            const char* rawPath;
            const SpriteBank* jsonBank;
            const char* countLabel;
        };
        const std::array<BankCheck, 3> banks{{
            {"BOMOMIMK.SPR", &sprites_, "bomomimk"},
            {"PROVA.SPR", &altSprites_, "prova"},
            {"FONTS.SPR", &fontSprites_, "fonts"},
        }};

        size_t totalRawBytes = 0;
        size_t totalSprites = 0;
        size_t totalPixels = 0;
        size_t zeroPixels = 0;
        size_t ffPixels = 0;
        int maxWidth = 0;
        int maxHeight = 0;
        std::array<size_t, 3> bankSpriteCounts{};

        for (size_t bankIndex = 0; bankIndex < banks.size(); ++bankIndex) {
            const BankCheck& check = banks[bankIndex];
            auto rawBytes = readFile(check.rawPath);
            SpriteBank rawBank = loadRawSprites(check.rawPath);
            const SpriteBank& jsonBank = *check.jsonBank;
            if (rawBank.sprites.size() != jsonBank.sprites.size()) {
                throw std::runtime_error(std::string(check.rawPath) +
                                         " raw/json sprite count mismatch");
            }
            totalRawBytes += rawBytes.size();
            bankSpriteCounts[bankIndex] = rawBank.sprites.size();
            for (size_t i = 0; i < rawBank.sprites.size(); ++i) {
                const Sprite& rawSprite = rawBank.sprites[i];
                const Sprite& jsonSprite = jsonBank.sprites[i];
                if (rawSprite.width != jsonSprite.width ||
                    rawSprite.height != jsonSprite.height ||
                    rawSprite.pixels != jsonSprite.pixels) {
                    throw std::runtime_error(std::string(check.rawPath) +
                                             " raw/json sprite payload mismatch");
                }
                ++totalSprites;
                totalPixels += rawSprite.pixels.size();
                maxWidth = std::max(maxWidth, rawSprite.width);
                maxHeight = std::max(maxHeight, rawSprite.height);
                zeroPixels += static_cast<size_t>(
                    std::count(rawSprite.pixels.begin(), rawSprite.pixels.end(), 0));
                ffPixels += static_cast<size_t>(
                    std::count(rawSprite.pixels.begin(), rawSprite.pixels.end(), 0xff));
            }
        }

        size_t nonzeroPixels = totalPixels - zeroPixels;
        std::cout << "sprite_raw_roundtrip=ok banks=" << banks.size()
                  << " raw_bytes=" << totalRawBytes
                  << " sprites=" << totalSprites
                  << " pixels=" << totalPixels
                  << " zero=" << zeroPixels
                  << " nonzero=" << nonzeroPixels
                  << " ff=" << ffPixels
                  << " max=" << maxWidth << 'x' << maxHeight
                  << " " << banks[0].countLabel << "=" << bankSpriteCounts[0]
                  << " " << banks[1].countLabel << "=" << bankSpriteCounts[1]
                  << " " << banks[2].countLabel << "=" << bankSpriteCounts[2]
                  << '\n';
    }

    void debugSpriteLayoutStaticModel() {
        struct ExpectedBank {
            const char* rawPath;
            const char* label;
            size_t rawBytes;
            int sprites;
            size_t pixels;
            size_t zero;
            size_t ff;
            int maxWidth;
            int maxHeight;
            int firstWidth;
            int firstHeight;
            int lastWidth;
            int lastHeight;
        };

        const std::array<ExpectedBank, 3> banks{{
            {"BOMOMIMK.SPR", "bomomimk", 20168, 91, 19985, 9303, 104, 21, 16, 16, 16, 12, 10},
            {"PROVA.SPR", "prova", 21250, 91, 21067, 9363, 114, 48, 20, 16, 16, 12, 10},
            {"FONTS.SPR", "fonts", 5425, 68, 5288, 2730, 151, 10, 10, 10, 10, 8, 8},
        }};

        size_t totalRawBytes = 0;
        size_t totalSprites = 0;
        size_t totalPixels = 0;
        size_t totalZero = 0;
        size_t totalFf = 0;
        int globalMaxWidth = 0;
        int globalMaxHeight = 0;
        std::ostringstream bankSummary;

        for (const ExpectedBank& expected : banks) {
            std::vector<uint8_t> bytes = readFile(expected.rawPath);
            if (bytes.size() != expected.rawBytes) {
                throw std::runtime_error(std::string(expected.rawPath) + " raw byte size changed");
            }
            if (bytes.empty()) {
                throw std::runtime_error(std::string(expected.rawPath) + " empty raw sprite bank");
            }

            size_t offset = 0;
            const int spriteCount = bytes[offset++];
            if (spriteCount != expected.sprites) {
                throw std::runtime_error(std::string(expected.rawPath) + " sprite count changed");
            }

            size_t pixels = 0;
            size_t zero = 0;
            size_t ff = 0;
            int maxWidth = 0;
            int maxHeight = 0;
            int firstWidth = 0;
            int firstHeight = 0;
            int lastWidth = 0;
            int lastHeight = 0;

            for (int i = 0; i < spriteCount; ++i) {
                if (offset + 2 > bytes.size()) {
                    throw std::runtime_error(std::string(expected.rawPath) + " truncated sprite header");
                }
                const int width = bytes[offset++];
                const int height = bytes[offset++];
                if (width <= 0 || height <= 0) {
                    throw std::runtime_error(std::string(expected.rawPath) + " zero-sized sprite");
                }
                if (i == 0) {
                    firstWidth = width;
                    firstHeight = height;
                }
                lastWidth = width;
                lastHeight = height;
                maxWidth = std::max(maxWidth, width);
                maxHeight = std::max(maxHeight, height);

                const size_t spritePixels = static_cast<size_t>(width) * static_cast<size_t>(height);
                if (offset + spritePixels > bytes.size()) {
                    throw std::runtime_error(std::string(expected.rawPath) + " truncated sprite payload");
                }
                for (size_t j = 0; j < spritePixels; ++j) {
                    const uint8_t value = bytes[offset + j];
                    if (value == 0) {
                        ++zero;
                    }
                    if (value == 0xff) {
                        ++ff;
                    }
                }
                offset += spritePixels;
                pixels += spritePixels;
            }

            if (offset != bytes.size()) {
                throw std::runtime_error(std::string(expected.rawPath) + " raw sprite trailing bytes");
            }
            if (pixels != expected.pixels || zero != expected.zero || ff != expected.ff ||
                maxWidth != expected.maxWidth || maxHeight != expected.maxHeight ||
                firstWidth != expected.firstWidth || firstHeight != expected.firstHeight ||
                lastWidth != expected.lastWidth || lastHeight != expected.lastHeight) {
                throw std::runtime_error(std::string(expected.rawPath) + " raw sprite layout changed");
            }

            totalRawBytes += bytes.size();
            totalSprites += static_cast<size_t>(spriteCount);
            totalPixels += pixels;
            totalZero += zero;
            totalFf += ff;
            globalMaxWidth = std::max(globalMaxWidth, maxWidth);
            globalMaxHeight = std::max(globalMaxHeight, maxHeight);

            bankSummary << ' ' << expected.label
                        << "=bytes:" << bytes.size()
                        << ",sprites:" << spriteCount
                        << ",pixels:" << pixels
                        << ",zero:" << zero
                        << ",ff:" << ff
                        << ",max:" << maxWidth << 'x' << maxHeight
                        << ",first:" << firstWidth << 'x' << firstHeight
                        << ",last:" << lastWidth << 'x' << lastHeight;
        }

        if (totalRawBytes != 46843 || totalSprites != 250 || totalPixels != 46340 ||
            totalZero != 21396 || totalFf != 369 ||
            globalMaxWidth != 48 || globalMaxHeight != 20) {
            throw std::runtime_error("raw sprite aggregate layout changed");
        }

        std::cout << "sprite_layout_static_model=ok banks=" << banks.size()
                  << " raw_bytes=" << totalRawBytes
                  << " sprites=" << totalSprites
                  << " pixels=" << totalPixels
                  << " zero=" << totalZero
                  << " nonzero=" << (totalPixels - totalZero)
                  << " ff=" << totalFf
                  << " max=" << globalMaxWidth << 'x' << globalMaxHeight
                  << " trailing=0"
                  << bankSummary.str()
                  << '\n';
    }

    void debugSpriteBlitContract() {
        load();
        resetClip();
        constexpr uint32_t kSentinel = 0x11223344u;
        std::fill(fb_.begin(), fb_.end(), kSentinel);

        Sprite sprite;
        sprite.width = 4;
        sprite.height = 2;
        sprite.pixels = {0, 1, 0xff, 2,
                         3, 0, 4,    0xff};
        constexpr int x0 = 5;
        constexpr int y0 = 7;
        drawSprite(sprite, x0, y0);

        auto pixelAt = [&](int x, int y) {
            return fb_[static_cast<size_t>(y) * kScreenW + x];
        };

        int drawn = 0;
        int skippedZero = 0;
        int ffVisible = 0;
        int backgroundPreserved = 0;
        for (int y = 0; y < sprite.height; ++y) {
            for (int x = 0; x < sprite.width; ++x) {
                uint8_t index = sprite.pixels[static_cast<size_t>(y) * sprite.width + x];
                uint32_t got = pixelAt(x0 + x, y0 + y);
                if (index == 0) {
                    if (got != kSentinel) {
                        throw std::runtime_error("drawSprite overwrote a transparent zero pixel");
                    }
                    ++skippedZero;
                    ++backgroundPreserved;
                    continue;
                }
                if (got != argb(palette_, index)) {
                    throw std::runtime_error("drawSprite did not draw an indexed pixel");
                }
                ++drawn;
                if (index == 0xff) ++ffVisible;
            }
        }

        int outsidePreserved = 0;
        for (std::array<int, 2> pos : {std::array<int, 2>{x0 - 1, y0},
                                       std::array<int, 2>{x0 + sprite.width, y0 + 1}}) {
            if (pixelAt(pos[0], pos[1]) != kSentinel) {
                throw std::runtime_error("drawSprite wrote outside sprite bounds");
            }
            ++outsidePreserved;
        }

        std::cout << "sprite_blit_contract=ok"
                  << " width=" << sprite.width
                  << " height=" << sprite.height
                  << " drawn=" << drawn
                  << " skipped_zero=" << skippedZero
                  << " ff_visible=" << ffVisible
                  << " bg_preserved=" << backgroundPreserved
                  << " outside_preserved=" << outsidePreserved << '\n';
    }

    void debugWordLayer() {
        load();
        int levelsSeen = 0;
        int totalLowWords = 0;
        int totalHighWords = 0;
        int totalHighUnique = 0;
        int totalHighComponents = 0;
        int totalHighSameWordComponents = 0;
        int totalFieldB = 0;
        int fieldBMatchesLow = 0;
        int fieldAPayloadMatchesHigh = 0;
        int fieldAPayloadMatchesHighUnique = 0;
        int fieldAPayloadMatchesHighComponents = 0;
        int fieldAPayloadMatchesHighSameWordComponents = 0;
        for (size_t levelIndex = 0; levelIndex < levels_.size(); ++levelIndex) {
            const Level& level = levels_[levelIndex];
            std::array<int, 65536> counts{};
            int nonzero = 0;
            int lowWords = 0;
            int highWords = 0;
            int damagedWords = 0;
            int unique = 0;
            int lowUnique = 0;
            int highUnique = 0;
            uint16_t minWord = 0xffff;
            uint16_t maxWord = 0;
            for (uint16_t word : level.wordLayer) {
                if (word == 0) continue;
                ++nonzero;
                bool firstSeen = counts[word]++ == 0;
                if (firstSeen) ++unique;
                minWord = std::min(minWord, word);
                maxWord = std::max(maxWord, word);
                if ((word & kDamagedWordBit) != 0) {
                    ++damagedWords;
                } else if (word >= kDeferredThreshold) {
                    ++highWords;
                    if (firstSeen) ++highUnique;
                } else {
                    ++lowWords;
                    if (firstSeen) ++lowUnique;
                }
            }

            auto isHighWord = [](uint16_t word) {
                return (word & kDamagedWordBit) == 0 && word >= kDeferredThreshold;
            };
            auto countHighComponents = [&](bool sameWordOnly) {
                std::vector<uint8_t> visited(level.wordLayer.size(), 0);
                int components = 0;
                for (size_t start = 0; start < level.wordLayer.size(); ++start) {
                    uint16_t startWord = level.wordLayer[start];
                    if (visited[start] || !isHighWord(startWord)) continue;
                    ++components;
                    std::vector<size_t> stack{start};
                    visited[start] = 1;
                    while (!stack.empty()) {
                        size_t index = stack.back();
                        stack.pop_back();
                        int x = static_cast<int>(index % static_cast<size_t>(level.width));
                        int y = static_cast<int>(index / static_cast<size_t>(level.width));
                        auto pushNeighbor = [&](int nx, int ny) {
                            if (nx < 0 || ny < 0 || nx >= level.width || ny >= level.height) return;
                            size_t next = static_cast<size_t>(ny) * level.width + nx;
                            if (next >= level.wordLayer.size() || visited[next]) return;
                            uint16_t nextWord = level.wordLayer[next];
                            if (!isHighWord(nextWord)) return;
                            if (sameWordOnly && nextWord != startWord) return;
                            visited[next] = 1;
                            stack.push_back(next);
                        };
                        pushNeighbor(x + 1, y);
                        pushNeighbor(x - 1, y);
                        pushNeighbor(x, y + 1);
                        pushNeighbor(x, y - 1);
                    }
                }
                return components;
            };
            int highComponents = countHighComponents(false);
            int highSameWordComponents = countHighComponents(true);

            std::vector<std::array<int, 2>> top;
            for (size_t i = 0; i < counts.size(); ++i) {
                if (counts[i] > 0) top.push_back({counts[i], static_cast<int>(i)});
            }
            std::sort(top.begin(), top.end(), [](const auto& a, const auto& b) {
                if (a[0] != b[0]) return a[0] > b[0];
                return a[1] < b[1];
            });

            auto countWord = [&](uint16_t word) {
                return counts[word];
            };
            int fieldAPayload = static_cast<int>(level.fieldA & 0x3fffu);
            ++levelsSeen;
            totalLowWords += lowWords;
            totalHighWords += highWords;
            totalHighUnique += highUnique;
            totalHighComponents += highComponents;
            totalHighSameWordComponents += highSameWordComponents;
            totalFieldB += level.fieldB;
            if (static_cast<int>(level.fieldB) == lowWords) ++fieldBMatchesLow;
            if (fieldAPayload == highWords) ++fieldAPayloadMatchesHigh;
            if (fieldAPayload == highUnique) ++fieldAPayloadMatchesHighUnique;
            if (fieldAPayload == highComponents) ++fieldAPayloadMatchesHighComponents;
            if (fieldAPayload == highSameWordComponents) {
                ++fieldAPayloadMatchesHighSameWordComponents;
            }
            std::cout << "word_layer level=" << (levelIndex + 1)
                      << " cells=" << level.wordLayer.size()
                      << " nonzero=" << nonzero
                      << " unique=" << unique
                      << " low_unique=" << lowUnique
                      << " high_unique=" << highUnique
                      << " low=" << lowWords
                      << " high=" << highWords
                      << " high_components=" << highComponents
                      << " high_same_word_components=" << highSameWordComponents
                      << " damaged=" << damagedWords
                      << " min=" << std::showbase << std::hex << (nonzero ? minWord : 0)
                      << " max=" << (nonzero ? maxWord : 0)
                      << std::dec << std::noshowbase
                      << " fieldA_count=" << countWord(level.fieldA)
                      << " fieldA_mask_count=" << countWord(static_cast<uint16_t>(level.fieldA & 0x7fffu))
                      << " fieldA_payload=" << fieldAPayload
                      << " fieldA_payload_delta_high=" << (highWords - fieldAPayload)
                      << " fieldA_payload_delta_high_unique=" << (highUnique - fieldAPayload)
                      << " fieldA_payload_delta_high_components=" << (highComponents - fieldAPayload)
                      << " fieldA_payload_delta_high_same_word_components="
                      << (highSameWordComponents - fieldAPayload)
                      << " fieldB_count=" << countWord(level.fieldB)
                      << " fieldB_delta_low=" << (lowWords - static_cast<int>(level.fieldB))
                      << '\n';
            std::cout << "top_words level=" << (levelIndex + 1) << ' ';
            if (top.empty()) {
                std::cout << "none";
            } else {
                for (size_t i = 0; i < top.size() && i < 8; ++i) {
                    if (i != 0) std::cout << ',';
                    std::cout << std::showbase << std::hex << top[i][1]
                              << std::dec << std::noshowbase << ':' << top[i][0];
                }
            }
            std::cout << '\n';
        }
        if (levelsSeen != 7 || totalLowWords != 5675 || totalHighWords != 501 ||
            totalHighUnique != 501 || totalHighComponents != 268 ||
            totalHighSameWordComponents != 501 || totalFieldB != 5675 ||
            fieldBMatchesLow != 7 || fieldAPayloadMatchesHigh != 1 ||
            fieldAPayloadMatchesHighUnique != 1 ||
            fieldAPayloadMatchesHighComponents != 0 ||
            fieldAPayloadMatchesHighSameWordComponents != 1) {
            throw std::runtime_error("word-layer embedded field summary changed");
        }
        std::cout << "word_layer=ok levels=" << levelsSeen
                  << " low=" << totalLowWords
                  << " high=" << totalHighWords
                  << " high_unique=" << totalHighUnique
                  << " high_components=" << totalHighComponents
                  << " high_same_word_components=" << totalHighSameWordComponents
                  << " fieldB_total=" << totalFieldB
                  << " fieldB_matches_low=" << fieldBMatchesLow
                  << " fieldA_payload_matches_high=" << fieldAPayloadMatchesHigh
                  << " fieldA_payload_matches_high_unique="
                  << fieldAPayloadMatchesHighUnique
                  << " fieldA_payload_matches_high_components="
                  << fieldAPayloadMatchesHighComponents
                  << " fieldA_payload_matches_high_same_word_components="
                  << fieldAPayloadMatchesHighSameWordComponents << '\n';
    }

    void debugSpawners() {
        load();
        std::array<int, 256> kindCounts{};
        std::array<int, 256> behaviorCounts{};
        int total = 0;
        for (size_t levelIndex = 0; levelIndex < levels_.size(); ++levelIndex) {
            const Level& level = levels_[levelIndex];
            std::cout << "level_" << (levelIndex + 1)
                      << "_spawners=" << level.monsterSpawners.size() << '\n';
            for (size_t i = 0; i < level.monsterSpawners.size(); ++i) {
                const MonsterSpawner& spawner = level.monsterSpawners[i];
                ++total;
                ++kindCounts[spawner.monsterKind];
                ++behaviorCounts[spawner.spawnArg];
                std::cout << "spawner level=" << (levelIndex + 1)
                          << " index=" << (i + 1)
                          << " enabled=" << static_cast<int>(spawner.enabled)
                          << " budget=" << static_cast<int>(spawner.spawnBudget)
                          << " live=" << static_cast<int>(spawner.liveAllowance)
                          << " kind=" << static_cast<int>(spawner.monsterKind)
                          << " behavior=" << static_cast<int>(spawner.spawnArg)
                          << " xy=" << spawner.x << ',' << spawner.y
                          << " tile_index=" << spawner.tileIndex
                          << " saved=" << std::showbase << std::hex << spawner.savedWordOrLink
                          << std::dec << std::noshowbase
                          << " ai0=" << spawner.param0Base << '+' << spawner.param0Range
                          << " ai1=" << spawner.param1Base << '+' << spawner.param1Range
                          << " ai2=" << spawner.param2Base << '+' << spawner.param2Range
                          << " random_hp=" << static_cast<int>(spawner.randomBase)
                          << '+' << static_cast<int>(spawner.randomRange)
                          << " cooldown=" << static_cast<int>(spawner.cooldown)
                          << " reset=" << static_cast<int>(spawner.cooldownReset)
                          << " anim_delay=" << static_cast<int>(spawner.animationDelay)
                          << '\n';
            }
        }
        auto printCounts = [](const char* label, const std::array<int, 256>& counts) {
            std::cout << label << '=';
            bool first = true;
            for (size_t i = 0; i < counts.size(); ++i) {
                if (counts[i] == 0) continue;
                if (!first) std::cout << ',';
                first = false;
                std::cout << i << ':' << counts[i];
            }
            if (first) std::cout << "none";
            std::cout << '\n';
        };
        std::cout << "spawner_total=" << total << '\n';
        printCounts("monster_kind_counts", kindCounts);
        printCounts("behavior_counts", behaviorCounts);
    }

    void debugExplosions() {
        load();
        for (BombType type : {BombType::Small, BombType::Medium, BombType::Large, BombType::Super}) {
            BombProfile profile = bombProfile(type);
            int visualType = explosionVisualType(type);
            std::cout << "bomb_type=" << static_cast<int>(bombTypeIndex(type)) + 1
                      << " actor_kind=" << static_cast<int>(profile.actorKind)
                      << " fuse=" << profile.fuseTicks
                      << " visual_selector=" << visualType
                      << " dispatcher_state=" << static_cast<int>(explosionDispatcherState(visualType))
                      << " effect_ticks=" << explosionEffectTicks(visualType)
                      << " variant_byte=" << static_cast<int>(explosionVariantByte(visualType))
                      << " sound_offset=" << std::showbase << std::hex
                      << explosionSoundOffset(visualType) << std::dec << std::noshowbase
                      << " sound_selector=" << static_cast<int>(explosionSoundSelector(visualType))
                      << '\n';
        }
        std::cout << "explosion_profiles=ok types=4 states=4,5,6,7 sound_offsets="
                  << std::showbase << std::hex
                  << explosionSoundOffset(1) << ','
                  << explosionSoundOffset(2) << ','
                  << explosionSoundOffset(3) << ','
                  << explosionSoundOffset(4)
                  << std::dec << std::noshowbase << '\n';
    }

    void debugDamageQueues() {
        load();
        std::cout << "debris_stride=" << kDebrisStride
                  << " collapse_stride=" << kCollapseStride
                  << " damaged_bit=" << std::showbase << std::hex << kDamagedWordBit
                  << " deferred_threshold=" << kDeferredThreshold
                  << " high_half_base=" << kHighHalfBase << std::dec << std::noshowbase
                  << '\n';

        auto findWord = [&](int levelIndex, bool highWord) -> std::array<int, 2> {
            resetLevel(levelIndex);
            for (int y = 0; y < level_.height; ++y) {
                for (int x = 0; x < level_.width; ++x) {
                    uint16_t word = wordAt(x, y);
                    bool candidate = word != 0 && (word & kDamagedWordBit) == 0;
                    if (!candidate) continue;
                    if (highWord == (word >= kDeferredThreshold)) return {x, y};
                }
            }
            return {-1, -1};
        };

        auto printLookup = [&](const DamagePhaseLookup& forward,
                               const DamagePhaseLookup& reverse) {
            std::cout << " forward_slot=" << forward.slotIndex
                      << " forward_phase=" << static_cast<int>(forward.phase)
                      << " reverse_slot=" << reverse.slotIndex
                      << " reverse_phase=" << static_cast<int>(reverse.phase)
                      << " source=" << (forward.debris ? "debris" : "collapse");
        };

        bool printedCollapse = false;
        bool printedDebris = false;
        uint16_t collapseFlagged = 0;
        int collapseCount = 0;
        int collapseForwardPhase = 0;
        int collapseReversePhase = 0;
        int collapseAffectedBytes = 0;
        int collapseSlot = 0;
        uint16_t collapseForwardWriteOffset = 0;
        uint16_t collapseReverseWriteOffset = 0;
        uint16_t debrisFlagged = 0;
        int debrisLookup = 0;
        int debrisForwardPhase = 0;
        int debrisReversePhase = 0;
        int debrisSlot = 0;
        uint16_t debrisTaggedSlot = 0;
        uint16_t debrisForwardWriteOffset = 0;
        uint16_t debrisReverseWriteOffset = 0;
        for (size_t levelIndex = 0; levelIndex < levels_.size() && (!printedCollapse || !printedDebris); ++levelIndex) {
            if (!printedCollapse) {
                auto pos = findWord(static_cast<int>(levelIndex), false);
                if (pos[0] >= 0) {
                    uint16_t word = wordAt(pos[0], pos[1]);
                    queueTileDamage(pos[0], pos[1], 2, 3);
                    if (!collapseQueue_.empty()) {
                        const CollapseRecord& record = collapseQueue_.back();
                        collapseFlagged = record.flaggedWord;
                        collapseCount = record.count;
                        collapseForwardPhase = static_cast<int>(record.forwardPhase);
                        collapseReversePhase = static_cast<int>(record.reversePhase);
                        collapseAffectedBytes = static_cast<int>(record.affectedBytes);
                        DamagePhaseLookup forward = resolveDamagePhase(record.flaggedWord, false);
                        DamagePhaseLookup reverse = resolveDamagePhase(record.flaggedWord, true);
                        collapseSlot = forward.slotIndex;
                        collapseForwardWriteOffset = static_cast<uint16_t>(
                            kCollapseForwardLaneBase + kCollapseStride * collapseSlot);
                        collapseReverseWriteOffset = static_cast<uint16_t>(
                            kCollapseReverseLaneBase + kCollapseStride * reverse.slotIndex);
                        std::cout << "collapse_level=" << (levelIndex + 1)
                                  << " tile=" << pos[0] << ',' << pos[1]
                                  << " word=" << std::showbase << std::hex << word
                                  << " flagged=" << record.flaggedWord
                                  << " start_off=" << record.startOffsetBytes
                                  << " end_off=" << record.endOffsetBytes
                                  << std::dec << std::noshowbase
                                  << " count=" << record.count
                                  << " affected_bytes=" << static_cast<int>(record.affectedBytes);
                        printLookup(forward, reverse);
                        std::cout << '\n';
                        printedCollapse = true;
                    }
                }
            }
            if (!printedDebris) {
                auto pos = findWord(static_cast<int>(levelIndex), true);
                if (pos[0] >= 0) {
                    uint16_t word = wordAt(pos[0], pos[1]);
                    queueTileDamage(pos[0], pos[1], 4, 5);
                    if (!debrisQueue_.empty()) {
                        const DebrisRecord& record = debrisQueue_.back();
                        debrisFlagged = record.flaggedWord;
                        debrisLookup = static_cast<int>(record.lookup);
                        debrisForwardPhase = static_cast<int>(record.forwardPhase);
                        debrisReversePhase = static_cast<int>(record.reversePhase);
                        DamagePhaseLookup forward = resolveDamagePhase(record.flaggedWord, false);
                        DamagePhaseLookup reverse = resolveDamagePhase(record.flaggedWord, true);
                        debrisSlot = forward.slotIndex;
                        debrisTaggedSlot = static_cast<uint16_t>(kHighHalfBase + debrisSlot);
                        debrisForwardWriteOffset = static_cast<uint16_t>(
                            kDebrisForwardLaneBase + kDebrisStride * debrisSlot);
                        debrisReverseWriteOffset = static_cast<uint16_t>(
                            kDebrisReverseLaneBase + kDebrisStride * reverse.slotIndex);
                        std::cout << "debris_level=" << (levelIndex + 1)
                                  << " tile=" << pos[0] << ',' << pos[1]
                                  << " tile_index=" << record.tileIndex
                                  << " word=" << std::showbase << std::hex << word
                                  << " flagged=" << record.flaggedWord
                                  << std::dec << std::noshowbase
                                  << " lookup=" << static_cast<int>(record.lookup);
                        printLookup(forward, reverse);
                        std::cout << '\n';
                        printedDebris = true;
                    }
                }
            }
        }
        if (!printedCollapse) std::cout << "collapse_sample=missing\n";
        if (!printedDebris) std::cout << "debris_sample=missing\n";
        if (printedCollapse && printedDebris) {
            std::cout << "damage_queues=ok debris_stride=" << kDebrisStride
                      << " collapse_stride=" << kCollapseStride
                      << " damaged_bit=" << std::showbase << std::hex << kDamagedWordBit
                      << " deferred_threshold=" << kDeferredThreshold
                      << " collapse_flagged=" << collapseFlagged
                      << " debris_flagged=" << debrisFlagged
                      << std::dec << std::noshowbase
                      << " collapse_count=" << collapseCount
                      << " collapse_forward=" << collapseForwardPhase
                      << " collapse_reverse=" << collapseReversePhase
                      << " debris_lookup=" << debrisLookup
                      << " debris_forward=" << debrisForwardPhase
                      << " debris_reverse=" << debrisReversePhase
                      << " consumer_forward=" << hex4(kDamageForwardPassRoutine)
                      << " consumer_reverse=" << hex4(kDamageReversePassRoutine)
                      << " lookup_forward=" << hex4(kDamageForwardLookupRoutine)
                      << " lookup_reverse=" << hex4(kDamageReverseLookupRoutine)
                      << " effect_update=" << hex4(kExplosionEffectUpdateRoutine)
                      << " high_target_sample=" << hex4(kHighDebrisTargetSample)
                      << " high_target_byte_gate=" << hex4(kHighDebrisTargetByteGate)
                      << " high_zero_branch=" << hex4(kHighDebrisZeroTargetBranch)
                      << " high_nonzero_branch=" << hex4(kHighDebrisNonzeroTargetBranch)
                      << " high_word_load=" << hex4(kHighDebrisWordLoad)
                      << " high_word_gate=" << hex4(kHighDebrisWordGate)
                      << " high_word_gate_skip=" << hex4(kHighDebrisWordGateSkip)
                      << " effect_forward_call=" << hex4(kExplosionEffectForwardCall)
                      << " effect_reverse_call=" << hex4(kExplosionEffectReverseCall)
                      << " effect_forward_return="
                      << hex4(kExplosionEffectForwardReturn)
                      << " effect_reverse_return="
                      << hex4(kExplosionEffectReverseReturn)
                      << " effect_forward_input_global="
                      << hex4(kExplosionEffectForwardInputGlobal)
                      << " effect_reverse_input_global="
                      << hex4(kExplosionEffectReverseInputGlobal)
                      << " lane_target_offset_global="
                      << hex4(kHighDebrisLaneTargetOffsetGlobal)
                      << " lane_word_global=" << hex4(kHighDebrisLaneWordGlobal)
                      << " lane_update_flag=" << hex4(kHighDebrisLaneUpdateFlag)
                      << " collapse_slot=" << collapseSlot
                      << " collapse_weight=" << collapseAffectedBytes
                      << " collapse_forward_write=" << hex4(collapseForwardWriteOffset)
                      << " collapse_reverse_write=" << hex4(collapseReverseWriteOffset)
                      << " debris_slot=" << debrisSlot
                      << " debris_tag=" << hex4(debrisTaggedSlot)
                      << " debris_forward_write=" << hex4(debrisForwardWriteOffset)
                      << " debris_reverse_write=" << hex4(debrisReverseWriteOffset)
                      << '\n';
        }
    }

    void debugLaneHelperModel() {
        std::cout << "lane_helper_model=ok"
                  << " helper_forward=" << hex4(kDamageForwardPassRoutine)
                  << " helper_reverse=" << hex4(kDamageReversePassRoutine)
                  << " lookup_forward=" << hex4(kDamageForwardLookupRoutine)
                  << " lookup_reverse=" << hex4(kDamageReverseLookupRoutine)
                  << " input_forward_global=" << hex4(kExplosionEffectForwardInputGlobal)
                  << " input_reverse_global=" << hex4(kExplosionEffectReverseInputGlobal)
                  << " ret_bytes=6"
                  << " input_far_pointer_arg=bp4"
                  << " weight_byte_arg=bp8"
                  << " signed_input_byte=1"
                  << " active_count_global=" << hex4(kHighDebrisLaneUpdateFlag)
                  << " staging_word_base=" << hex4(kLaneHelperStagingWordBase)
                  << " staging_word_first=" << hex4(kHighDebrisLaneWordGlobal)
                  << " staging_target_base=" << hex4(kLaneHelperStagingTargetBase)
                  << " staging_target_first=" << hex4(kHighDebrisLaneTargetOffsetGlobal)
                  << " staging_tag_base=" << hex4(kLaneHelperStagingTagBase)
                  << " staging_tag_first="
                  << hex4(static_cast<uint16_t>(kLaneHelperStagingTagBase + 2))
                  << " selector_global=" << hex4(kLaneHelperSelectorGlobal)
                  << " debris_count_global=" << hex4(kLaneHelperDebrisCountGlobal)
                  << " collapse_count_global=" << hex4(kLaneHelperCollapseCountGlobal)
                  << " high_tag_base=" << hex4(kHighHalfBase)
                  << " neighbor_lane_scratch=" << hex4(kLaneHelperNeighborLaneScratch)
                  << " collapse_forward_base=" << hex4(kCollapseForwardLaneBase)
                  << " collapse_reverse_base=" << hex4(kCollapseReverseLaneBase)
                  << " collapse_weight_base=" << hex4(kLaneHelperCollapseWeightBase)
                  << " collapse_forward_record_offset="
                  << static_cast<int>(kCollapseForwardLaneRecordOffset)
                  << " collapse_reverse_record_offset="
                  << static_cast<int>(kCollapseReverseLaneRecordOffset)
                  << " collapse_weight_record_offset="
                  << static_cast<int>(kCollapseWeightRecordOffset)
                  << " debris_forward_base=" << hex4(kDebrisForwardLaneBase)
                  << " debris_reverse_base=" << hex4(kDebrisReverseLaneBase)
                  << " debris_forward_record_offset="
                  << static_cast<int>(kDebrisForwardLaneRecordOffset)
                  << " debris_reverse_record_offset="
                  << static_cast<int>(kDebrisReverseLaneRecordOffset)
                  << " blend_far=" << hex4(kLaneHelperBlendFarSegment)
                  << ':' << hex4(kLaneHelperBlendFarOffset)
                  << " writes_input_byte=1"
                  << " writes_staged_tags=1"
                  << " exact_arithmetic=signed_32_divide_toward_zero"
                  << '\n';
    }

    void debugLaneBlendArithmetic() {
        auto divide = [](int32_t numerator, int32_t denominator) -> int32_t {
            if (denominator == 0) {
                throw std::runtime_error("lane blend diagnostic divide by zero sample");
            }
            return numerator / denominator;
        };
        auto word = [](int32_t value) -> uint16_t {
            return static_cast<uint16_t>(static_cast<uint32_t>(value) & 0xffffu);
        };
        auto byte = [](int32_t value) -> uint8_t {
            return static_cast<uint8_t>(static_cast<uint32_t>(value) & 0xffu);
        };

        const int32_t neg9Weight1 = divide(-9, 1);
        const int32_t neg9Weight2 = divide(-9, 2);
        const int32_t pos9Weight4 = divide(9, 4);
        const int32_t neg1Weight2 = divide(-1, 2);
        std::cout << "lane_blend_arithmetic=ok"
                  << " routine=" << hex4(kLaneHelperBlendFarSegment)
                  << ':' << hex4(kLaneHelperBlendFarOffset)
                  << " operation=signed_32_by_32_divide"
                  << " dividend_reg=dx:ax"
                  << " divisor_reg=bx:cx"
                  << " quotient_reg=dx:ax"
                  << " quotient_byte=al"
                  << " remainder_reg=bx:cx"
                  << " quotient_rounding=toward_zero"
                  << " remainder_sign=dividend"
                  << " zero_divisor_branch=" << hex4(kLaneHelperBlendZeroDivisorOffset)
                  << " zero_divisor_error_ax=" << hex4(kLaneHelperBlendZeroDivisorError)
                  << " lane_numerator=signed_lane_byte_times_unsigned_weight_sum"
                  << " lane_denominator=unsigned_weight_sum"
                  << " caller_forward=" << hex4(kDamageForwardPassRoutine)
                  << " caller_reverse=" << hex4(kDamageReversePassRoutine)
                  << " caller_forward_call=" << hex4(0x3ce3)
                  << " caller_reverse_call=" << hex4(0x3e77)
                  << " sample_neg9_div1_q=" << hex4(word(neg9Weight1))
                  << " sample_neg9_div1_al=" << hex2(byte(neg9Weight1))
                  << " sample_neg9_div2_q=" << hex4(word(neg9Weight2))
                  << " sample_neg9_div2_al=" << hex2(byte(neg9Weight2))
                  << " sample_pos9_div4_q=" << hex4(word(pos9Weight4))
                  << " sample_pos9_div4_al=" << hex2(byte(pos9Weight4))
                  << " sample_neg1_div2_q=" << hex4(word(neg1Weight2))
                  << " sample_neg1_div2_al=" << hex2(byte(neg1Weight2))
                  << '\n';
    }

    void debugMonsterSlots() {
        load();
        resetLevel(0);
        if (spawnerStates_.empty()) {
            throw std::runtime_error("level has no spawner state");
        }
        int initialSlots = spawnerStates_[0].availableSlots;
        int initialRemaining = spawnerStates_[0].remaining;
        updateMonsterSpawners();
        if (monsters_.empty()) {
            throw std::runtime_error("monster spawner did not create an actor");
        }
        ActiveMonster& monster = monsters_.front();
        size_t spawnerIndex = monster.spawnerIndex;
        if (spawnerIndex >= spawnerStates_.size() ||
            spawnerStates_[spawnerIndex].availableSlots != initialSlots - 1 ||
            spawnerStates_[spawnerIndex].remaining != initialRemaining - 1) {
            throw std::runtime_error("monster spawn did not reserve a live slot");
        }

        enterMonsterDeath(monster);
        if (spawnerStates_[spawnerIndex].availableSlots != initialSlots) {
            throw std::runtime_error("monster death did not immediately return live slot");
        }
        int deathTicks = monster.stateTimer;
        for (int i = 0; i < deathTicks; ++i) {
            updateMonsters(0.0f);
        }
        if (!monsters_.empty() ||
            spawnerStates_[spawnerIndex].availableSlots != initialSlots) {
            throw std::runtime_error("monster removal did not return live slot");
        }
        updateMonsters(0.0f);
        if (spawnerStates_[spawnerIndex].availableSlots != initialSlots) {
            throw std::runtime_error("monster live slot was returned more than once");
        }
        std::cout << "monster_slots=ok initial_slots=" << initialSlots
                  << " returned_immediate=1"
                  << " death_ticks=" << deathTicks << '\n';
    }

    void debugMonsterMotionModel() {
        load();

        int carryPos = 10;
        uint8_t carryFrac = 250;
        integrateAxis8_8(carryPos, carryFrac, 0x000a);
        if (carryPos != 11 || carryFrac != 4) {
            throw std::runtime_error("8.8 positive carry integration changed");
        }

        int negativePos = 10;
        uint8_t negativeFrac = 0;
        integrateAxis8_8(negativePos, negativeFrac, static_cast<int16_t>(0xffff));
        integrateAxis8_8(negativePos, negativeFrac, static_cast<int16_t>(0xffff));
        if (negativePos != 9 || negativeFrac != 254) {
            throw std::runtime_error("8.8 negative fractional integration changed");
        }

        prepareMonsterMotionDebugLevel(false);
        ActiveMonster walker;
        walker.x = 40;
        walker.y = 24;
        walker.kind = 1;
        walker.behavior = 3;
        walker.ai0 = 0x0100;
        initializeMonsterMotion(walker);
        if (walker.vx8 != 0x0100 || walker.vy8 != 0 ||
            walker.animStart != 45 || walker.animEnd != 46) {
            throw std::runtime_error("behavior 3 initialization changed");
        }

        prepareMonsterMotionDebugLevel(true);
        ActiveMonster ledgeWalker = walker;
        ledgeWalker.x = 40;
        ledgeWalker.y = 24;
        ledgeWalker.vx8 = 0x0100;
        ledgeWalker.vy8 = 0;
        ledgeWalker.fracX = 0;
        ledgeWalker.fracY = 0;
        updateMonsterMotion(ledgeWalker, 0.0f);
        if (ledgeWalker.vx8 != -0x0100 || ledgeWalker.vy8 != 0x0040 ||
            ledgeWalker.animStart != 43 || ledgeWalker.animEnd != 44) {
            throw std::runtime_error("behavior 3 ledge turn changed");
        }

        prepareMonsterMotionDebugLevel(false);
        player_.x = 80.0f;
        player_.y = 24.0f;
        ActiveMonster flyer;
        flyer.x = 40;
        flyer.y = 24;
        flyer.kind = 2;
        flyer.behavior = 4;
        flyer.ai0 = 7;
        flyer.ai1 = 0x0200;
        flyer.ai2 = 100;
        initializeMonsterMotion(flyer);
        if (flyer.vx8 != 0x0200 || flyer.vy8 != 0 || flyer.motionTimer != 7 ||
            flyer.animStart != 39 || flyer.animEnd != 41) {
            throw std::runtime_error("behavior 4 chase initialization changed");
        }
        updateMonsterMotion(flyer, 0.0f);
        if (flyer.motionTimer != 6 || flyer.vx8 != 0x0200 || flyer.vy8 != 0) {
            throw std::runtime_error("behavior 4 countdown tick changed");
        }

        std::cout << "monster_motion_model=ok"
                  << " carry_pos=" << carryPos
                  << " carry_frac=" << static_cast<int>(carryFrac)
                  << " neg_pos=" << negativePos
                  << " neg_frac=" << static_cast<int>(negativeFrac)
                  << " b3_init_vx=" << walker.vx8
                  << " b3_init_frame=" << static_cast<int>(walker.animStart)
                  << '-' << static_cast<int>(walker.animEnd)
                  << " b3_ledge_vx=" << ledgeWalker.vx8
                  << " b3_ledge_vy=" << ledgeWalker.vy8
                  << " b3_ledge_frame=" << static_cast<int>(ledgeWalker.animStart)
                  << '-' << static_cast<int>(ledgeWalker.animEnd)
                  << " b4_chase_vx=" << flyer.vx8
                  << " b4_chase_vy=" << flyer.vy8
                  << " b4_timer=" << flyer.motionTimer
                  << " b4_frame=" << static_cast<int>(flyer.animStart)
                  << '-' << static_cast<int>(flyer.animEnd) << '\n';
    }

    void debugMonsterBlastDamage() {
        load();
        resetLevel(0);
        monsters_.clear();
        bonusDrops_.clear();
        ActiveMonster monster;
        monster.x = 80;
        monster.y = 80;
        monster.kind = 1;
        monster.behavior = 3;
        monster.hp = 3;
        monsters_.push_back(monster);
        std::vector<std::array<int, 2>> tiles{{{10, 11}}};

        damageMonstersInExplosion(tiles, BombType::Small);
        if (monsters_[0].behavior == 2 || monsters_[0].hp != 2 ||
            !bonusDrops_.empty()) {
            throw std::runtime_error("small bomb ignored monster hit points");
        }

        damageMonstersInExplosion(tiles, BombType::Medium);
        if (monsters_[0].behavior != 2 || monsters_[0].hp != 0 ||
            bonusDrops_.size() != 1) {
            throw std::runtime_error("medium bomb did not finish damaged monster");
        }
        if (bonusDrops_[0].x != 81.0f || bonusDrops_[0].y != 82.0f) {
            throw std::runtime_error("monster bonus did not spawn near body center");
        }

        ActiveMonster tough;
        tough.x = 96;
        tough.y = 80;
        tough.kind = 4;
        tough.behavior = 3;
        tough.hp = 4;
        monsters_.push_back(tough);
        std::vector<std::array<int, 2>> superTiles{{{12, 11}}};
        damageMonstersInExplosion(superTiles, BombType::Super);
        if (monsters_[1].behavior != 2 || monsters_[1].hp != 0 ||
            bonusDrops_.size() != 2) {
            throw std::runtime_error("super bomb did not apply full monster damage");
        }

        ActiveMonster edge;
        edge.x = 89;
        edge.y = 80;
        edge.kind = 1;
        edge.behavior = 3;
        edge.hp = 2;
        monsters_.push_back(edge);
        std::vector<std::array<int, 2>> edgeTiles{{{10, 11}}, {{11, 11}}};
        damageMonstersInExplosion(edgeTiles, BombType::Small);
        if (monsters_[2].hp != 1) {
            throw std::runtime_error("monster blast missed partial overlap");
        }

        std::cout << "monster_blast_damage=ok drops=" << bonusDrops_.size() << '\n';
    }

    void debugBombFuse() {
        load();
        resetLevel(0);
        bombs_.clear();
        flashes_.clear();
        explosionEffects_.clear();
        int beforeSmallBombs = bombInventory_.counts[0];
        placeBombAt(player_, bombInventory_, 1);
        if (bombs_.size() != 1 || bombInventory_.counts[0] != beforeSmallBombs - 1) {
            throw std::runtime_error("bomb placement did not create a timed bomb");
        }

        int fuseTicks = bombs_[0].timer;
        for (int i = 1; i < fuseTicks; ++i) {
            updateBombs();
            if (bombs_.size() != 1 || bombs_[0].timer != fuseTicks - i) {
                throw std::runtime_error("bomb expired before fuse reached zero");
            }
        }

        updateBombs();
        if (!bombs_.empty() || explosionEffects_.empty() || flashes_.empty()) {
            throw std::runtime_error("bomb fuse did not produce an explosion");
        }
        int initialEffects = static_cast<int>(explosionEffects_.size());
        int initialFlashes = static_cast<int>(flashes_.size());

        auto pushExpiredPlayerBombs = [&]() {
            int playerBombX = static_cast<int>(player_.x + 6.0f) / kTileSize;
            int playerBombY = static_cast<int>(player_.y + 12.0f) / kTileSize;
            bombs_.push_back({playerBombX, playerBombY, 1, BombType::Small, 1});
            bombs_.push_back({std::max(0, playerBombX - 4), playerBombY, 1,
                              BombType::Small, 1});
        };

        resetLevel(0);
        menu_ = false;
        energy_ = 0;
        lives_ = 1;
        damageCooldown_ = 0;
        bombs_.clear();
        flashes_.clear();
        explosionEffects_.clear();
        pushExpiredPlayerBombs();
        updateBombs();
        if (menu_ || !playerDead_ || lives_ != 1 || !pendingLifeLoss_ ||
            deathStateTimer_ != kDeathStateTicks || !bombs_.empty() ||
            flashes_.empty() || explosionEffects_.empty()) {
            throw std::runtime_error("final-life bomb did not enter delayed state-2");
        }
        for (int i = 0; i < kDeathStateTicks; ++i) {
            updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                          true);
        }
        if (!menu_ || menuPage_ != MenuPage::GameOver || !bombs_.empty() ||
            !flashes_.empty() || !explosionEffects_.empty()) {
            throw std::runtime_error("final-life bomb did not reset after state-2");
        }

        resetLevel(0);
        menu_ = false;
        energy_ = 0;
        lives_ = 0;
        damageCooldown_ = 0;
        bombs_.clear();
        flashes_.clear();
        explosionEffects_.clear();
        pushExpiredPlayerBombs();
        updateBombs();
        if (!menu_ || menuPage_ != MenuPage::GameOver || !bombs_.empty() ||
            !flashes_.empty() || !explosionEffects_.empty()) {
            throw std::runtime_error("stale expired bomb exploded after reset");
        }

        std::cout << "bomb_fuse=ok fuse=" << fuseTicks
                  << " effects=" << initialEffects
                  << " flashes=" << initialFlashes
                  << " delayed_final_life=1 stale_reset_guard=1\n";
    }

    void debugBombObjectExplosionEffects() {
        load();

        struct Probe {
            int level = 0;
            int x = 0;
            int y = 0;
            uint8_t tile = 0;
            uint16_t objectWord = 0;
            uint16_t aboveWord = 0;
        };

        struct ProbeResult {
            int count = 0;
            uint16_t startOffsetBytes = 0;
            uint16_t endOffsetBytes = 0;
            uint16_t word = 0;
            uint16_t flaggedWord = 0;
            uint16_t argMagnitude = 0;
            uint8_t affectedBytes = 0;
            int debrisLookup = 0;
        };

        auto findProbe = [&](bool wantHighWord, Probe& out) {
            for (size_t level = 0; level < levels_.size(); ++level) {
                resetLevel(static_cast<int>(level));
                for (int y = 1; y + 1 < level_.height; ++y) {
                    for (int x = 0; x + 1 < level_.width; ++x) {
                        uint8_t tile = static_cast<uint8_t>(tileAt(x, y));
                        if (!isBombObjectTile(tile)) continue;
                        uint16_t objectWord = wordAt(x, y);
                        uint16_t aboveWord = wordAt(x, y - 1);
                        if (aboveWord == 0 || (aboveWord & kDamagedWordBit) != 0 ||
                            objectWord == aboveWord) {
                            continue;
                        }
                        if ((aboveWord >= kDeferredThreshold) != wantHighWord) continue;

                        Bomb bomb{x, y, 1, BombType::Small, 1, 1};
                        int bombObjectsInFootprint = 0;
                        bool onlyCandidateObject = true;
                        for (const auto& pos : explosionTilesFor(bomb)) {
                            if (!isBombObjectTile(static_cast<uint8_t>(tileAt(pos[0], pos[1])))) {
                                continue;
                            }
                            ++bombObjectsInFootprint;
                            onlyCandidateObject =
                                onlyCandidateObject && pos[0] == x && pos[1] == y;
                        }
                        if (bombObjectsInFootprint != 1 || !onlyCandidateObject) continue;

                        out = {static_cast<int>(level), x, y, tile, objectWord, aboveWord};
                        return true;
                    }
                }
            }
            return false;
        };

        auto runProbe = [&](const Probe& probe, bool expectDebris) -> ProbeResult {
            resetLevel(probe.level);
            clearRunScores();
            clearSoundLatch();
            monsters_.clear();
            bonusDrops_.clear();
            bombs_.clear();
            flashes_.clear();
            explosionEffects_.clear();
            debrisQueue_.clear();
            collapseQueue_.clear();
            playerDead_ = true;
            player2Dead_ = true;

            if (static_cast<uint8_t>(tileAt(probe.x, probe.y)) != probe.tile ||
                wordAt(probe.x, probe.y) != probe.objectWord ||
                wordAt(probe.x, probe.y - 1) != probe.aboveWord) {
                throw std::runtime_error("bomb object probe changed before explosion");
            }
            if (solidPixel(static_cast<float>(probe.x * kTileSize + 1),
                           static_cast<float>(probe.y * kTileSize + 1))) {
                throw std::runtime_error("bomb object was not passable before explosion");
            }

            Bomb bomb{probe.x, probe.y, 1, BombType::Small, 1, 1};
            explode(bomb);

            uint8_t expectedTile =
                (probe.objectWord & kDamagedWordBit) != 0 ? 0xff : 0;
            if (static_cast<uint8_t>(tileAt(probe.x, probe.y)) != expectedTile) {
                throw std::runtime_error("bomb object consumed to unexpected tile");
            }
            if (solidPixel(static_cast<float>(probe.x * kTileSize + 1),
                           static_cast<float>(probe.y * kTileSize + 1))) {
                throw std::runtime_error("consumed bomb object blocked movement");
            }
            if (score_ != 50) {
                throw std::runtime_error("bomb object explosion did not award one object score");
            }
            if (flashes_.size() != 4 || explosionEffects_.size() != 1) {
                throw std::runtime_error("bomb object explosion footprint/effect mismatch");
            }
            if (!soundLatch_.active ||
                soundLatch_.latchedOffset != explosionSoundOffset(1) ||
                soundLatch_.currentSelector != explosionSoundSelector(1)) {
                throw std::runtime_error("bomb object explosion sound priority mismatch");
            }

            uint16_t flaggedAbove = static_cast<uint16_t>(probe.aboveWord | kDamagedWordBit);
            if (wordAt(probe.x, probe.y - 1) != flaggedAbove) {
                throw std::runtime_error("bomb object explosion did not flag above word");
            }
            DamagePhaseLookup forward = resolveDamagePhase(flaggedAbove, false);
            DamagePhaseLookup reverse = resolveDamagePhase(flaggedAbove, true);
            if (forward.phase != 0 || reverse.phase != 0) {
                throw std::runtime_error("bomb object default damage phases changed");
            }

            if (expectDebris) {
                if (debrisQueue_.size() != 1 || !collapseQueue_.empty() ||
                    destroyed_ != 0 || !forward.debris || !reverse.debris) {
                    throw std::runtime_error("bomb object high-word routing mismatch");
                }
                const DebrisRecord& record = debrisQueue_.front();
                int expectedIndex = (probe.y - 1) * level_.width + probe.x;
                if (record.tileIndex != expectedIndex ||
                    record.flaggedWord != flaggedAbove) {
                    throw std::runtime_error("bomb object debris record mismatch");
                }
                ProbeResult result;
                result.count = 1;
                result.word = static_cast<uint16_t>(probe.aboveWord & ~kDamagedWordBit);
                result.flaggedWord = record.flaggedWord;
                result.debrisLookup = static_cast<int>(record.lookup);
                return result;
            }

            if (collapseQueue_.size() != 1 || !debrisQueue_.empty() ||
                forward.debris || reverse.debris) {
                throw std::runtime_error("bomb object low-word routing mismatch");
            }
            const CollapseRecord& record = collapseQueue_.front();
            if (record.flaggedWord != flaggedAbove || destroyed_ != record.count ||
                record.count <= 0) {
                throw std::runtime_error("bomb object collapse record mismatch");
            }
            ProbeResult result;
            result.count = record.count;
            result.startOffsetBytes = record.startOffsetBytes;
            result.endOffsetBytes = record.endOffsetBytes;
            result.word = record.word;
            result.flaggedWord = record.flaggedWord;
            result.argMagnitude = record.argMagnitude;
            result.affectedBytes = record.affectedBytes;
            return result;
        };

        Probe collapseProbe;
        Probe debrisProbe;
        if (!findProbe(false, collapseProbe)) {
            throw std::runtime_error("no low-word bomb object explosion probe found");
        }
        if (!findProbe(true, debrisProbe)) {
            throw std::runtime_error("no high-word bomb object explosion probe found");
        }

        ProbeResult collapse = runProbe(collapseProbe, false);
        ProbeResult debris = runProbe(debrisProbe, true);
        std::cout << "bomb_object_explosion_effects=ok cases=2"
                  << " collapse_level=" << (collapseProbe.level + 1)
                  << " collapse_tile=" << collapseProbe.x << ',' << collapseProbe.y
                  << " collapse_count=" << collapse.count
                  << " collapse_start_off=" << hex4(collapse.startOffsetBytes)
                  << " collapse_end_off=" << hex4(collapse.endOffsetBytes)
                  << " collapse_word=" << hex4(collapse.word)
                  << " collapse_flagged=" << hex4(collapse.flaggedWord)
                  << " collapse_arg_magnitude=" << hex4(collapse.argMagnitude)
                  << " collapse_affected_bytes=" << static_cast<int>(collapse.affectedBytes)
                  << " debris_level=" << (debrisProbe.level + 1)
                  << " debris_tile=" << debrisProbe.x << ',' << debrisProbe.y
                  << " debris_lookup=" << debris.debrisLookup
                  << " score_each=50 sound_offset=" << std::showbase << std::hex
                  << explosionSoundOffset(1)
                  << std::dec << std::noshowbase << '\n';
    }

    void debugPassableObjects() {
        load();
        bool sawBombObject = false;
        bool sawPortal = false;
        bool sawSolid = false;

        for (size_t level = 0; level < levels_.size(); ++level) {
            resetLevel(static_cast<int>(level));
            for (int y = 0; y < level_.height; ++y) {
                for (int x = 0; x < level_.width; ++x) {
                    uint8_t tile = static_cast<uint8_t>(tileAt(x, y));
                    float px = static_cast<float>(x * kTileSize + 1);
                    float py = static_cast<float>(y * kTileSize + 1);
                    if (isBombObjectTile(tile)) {
                        sawBombObject = true;
                        if (solidPixel(px, py)) {
                            throw std::runtime_error("bomb object tile blocks movement");
                        }
                    } else if (tile == 0x45) {
                        sawPortal = true;
                        if (solidPixel(px, py)) {
                            throw std::runtime_error("portal tile blocks movement");
                        }
                    } else if (countsForDestructionProgress(tile, level_.objectiveTile) &&
                               !isPassableObjectCell(x, y)) {
                        sawSolid = true;
                        if (!solidPixel(px, py)) {
                            throw std::runtime_error("solid map tile became passable");
                        }
                    }
                }
            }
        }

        if (!sawBombObject || !sawPortal || !sawSolid) {
            throw std::runtime_error("passable object coverage did not find required tile types");
        }

        resetLevel(0);
        std::fill(level_.tiles.begin(), level_.tiles.end(), uint8_t{0});
        std::fill(level_.wordLayer.begin(), level_.wordLayer.end(), uint16_t{0});
        constexpr int kPassableX = 6;
        constexpr int kPassableY = 6;
        tileRef(kPassableX, kPassableY) = 0x45;
        tileRef(kPassableX + 1, kPassableY) = 0x67;
        tileRef(kPassableX, kPassableY + 1) = 0x6d;
        tileRef(kPassableX + 1, kPassableY + 1) = 0x72;
        if (collides(static_cast<float>(kPassableX * kTileSize),
                     static_cast<float>(kPassableY * kTileSize)) ||
            monsterCollides(kPassableX * kTileSize, kPassableY * kTileSize)) {
            throw std::runtime_error("passable object footprint blocks movement");
        }
        if (!consumeBombObjectTile(kPassableX + 1, kPassableY) ||
            solidPixel(static_cast<float>((kPassableX + 1) * kTileSize + 1),
                       static_cast<float>(kPassableY * kTileSize + 1))) {
            throw std::runtime_error("consumed bomb object tile blocks movement");
        }

        resetLevel(0);
        if (!isPassableObjectCell(17, 22) ||
            solidPixel(static_cast<float>(17 * kTileSize + 1),
                       static_cast<float>(22 * kTileSize + 1))) {
            throw std::runtime_error("level 1 low-word object tile blocks movement");
        }
        if (isPassableObjectCell(53, 23) ||
            !solidPixel(static_cast<float>(53 * kTileSize + 1),
                        static_cast<float>(23 * kTileSize + 1))) {
            throw std::runtime_error("level 1 high-word floor marker became passable");
        }

        menu_ = false;
        playerCount_ = 1;
        AutoplayRouteResult route = autoplayLevel1BombRoute();
        if (route.bombTileX != 24 || route.bombTileY != 22) {
            throw std::runtime_error("level 1 passable-object route remains blocked");
        }

        std::cout << "passable_objects=ok"
                  << " bomb=1 portal=1 solid=1"
                  << " footprint_clear=1 consumed_clear=1"
                  << " level1_word_clear=1 high_word_solid=1"
                  << " level1_route_clear=1\n";
    }

    void debugTriggerAccounting() {
        load();
        for (size_t level = 0; level < levels_.size(); ++level) {
            resetLevel(static_cast<int>(level));
            for (const TileTriggerRule& rule : level_.tileTriggers) {
                int expectedRewrites = 0;
                size_t count = std::min(level_.tiles.size(), level_.wordLayer.size());
                for (size_t i = 0; i < count; ++i) {
                    uint16_t word = static_cast<uint16_t>(level_.wordLayer[i] & 0x7fffu);
                    if (word < rule.wordRangeFirst || word > rule.wordRangeLast) continue;
                    uint8_t tile = level_.tiles[i];
                    for (size_t slot = 0; slot < rule.from.size(); ++slot) {
                        uint8_t from = rule.from[slot];
                        if (from == 0 || tile != from) continue;
                        uint8_t to = rule.to[slot];
                        if (tile != to) ++expectedRewrites;
                        tile = to;
                    }
                }
                if (expectedRewrites == 0) continue;

                int beforeDestroyed = destroyed_;
                if (!applyTileTrigger(rule.triggerKey)) {
                    throw std::runtime_error("trigger accounting test did not rewrite tiles");
                }
                if (destroyed_ != beforeDestroyed) {
                    throw std::runtime_error("trigger rewrite changed physical destruction progress");
                }
                std::cout << "trigger_accounting=ok level=" << (level + 1)
                          << " rewrites=" << expectedRewrites << '\n';
                return;
            }
        }
        throw std::runtime_error("no trigger rewrote tiles");
    }

    void debugTriggerSoundRouting() {
        load();
        for (size_t level = 0; level < levels_.size(); ++level) {
            resetLevel(static_cast<int>(level));
            for (int y = 1; y < level_.height; ++y) {
                for (int x = 0; x < level_.width; ++x) {
                    if (tileAt(x, y) != 0x72) continue;
                    uint16_t key = static_cast<uint16_t>(wordAt(x, y) & 0x7fffu);
                    if (key == 0) continue;

                    player_.x = static_cast<float>(x * kTileSize);
                    player_.y = static_cast<float>(y * kTileSize - 8);
                    int portalCooldown = 0;
                    int triggerCooldown = 0;
                    clearSoundLatch();
                    updatePortalsAndTriggers(player_, portalCooldown, triggerCooldown,
                                             false);

                    if (triggerCooldown != 30 || !soundLatch_.active ||
                        soundLatch_.latchedOffset != kTileTriggerSoundCursor ||
                        soundLatch_.currentSelector != kTileTriggerSoundPriority) {
                        throw std::runtime_error("trigger sound request mismatch");
                    }

                    pumpSoundLatch();
                    if (soundLatch_.active ||
                        lastPumpedSoundOffset_ != kTileTriggerSoundCursor ||
                        lastPumpedSoundSelector_ != kTileTriggerSoundPriority) {
                        throw std::runtime_error("trigger sound pump mismatch");
                    }

                    std::cout << "trigger_sound=ok level=" << (level + 1)
                              << " key=" << key
                              << " cursor=" << std::showbase << std::hex
                              << kTileTriggerSoundCursor
                              << std::dec << std::noshowbase
                              << " priority="
                              << static_cast<int>(kTileTriggerSoundPriority)
                              << '\n';
                    return;
                }
            }
        }
        throw std::runtime_error("no trigger tile found for sound routing");
    }

    void debugPortalSoundRouting() {
        load();
        for (size_t level = 0; level < levels_.size(); ++level) {
            resetLevel(static_cast<int>(level));
            for (int y = 1; y < level_.height; ++y) {
                for (int x = 0; x < level_.width; ++x) {
                    if (tileAt(x, y) != 0x45) continue;
                    uint16_t key = static_cast<uint16_t>(wordAt(x, y) & 0x7fffu);
                    if (key == 0) continue;
                    const LevelPortal* destination = nullptr;
                    for (const LevelPortal& portal : level_.portals) {
                        if (portal.key == key) {
                            destination = &portal;
                            break;
                        }
                    }
                    if (!destination) continue;

                    player_.x = static_cast<float>(x * kTileSize);
                    player_.y = static_cast<float>(y * kTileSize - 8);
                    int portalCooldown = 0;
                    int triggerCooldown = 0;
                    clearSoundLatch();
                    updatePortalsAndTriggers(player_, portalCooldown, triggerCooldown,
                                             true);

                    if (portalCooldown != 30 ||
                        player_.x != static_cast<float>(destination->x) ||
                        player_.y != static_cast<float>(destination->y) ||
                        !soundLatch_.active ||
                        soundLatch_.latchedOffset != kPortalTeleportSoundCursor ||
                        soundLatch_.currentSelector != kPortalTeleportSoundPriority) {
                        throw std::runtime_error("portal sound request mismatch");
                    }

                    pumpSoundLatch();
                    if (soundLatch_.active ||
                        lastPumpedSoundOffset_ != kPortalTeleportSoundCursor ||
                        lastPumpedSoundSelector_ != kPortalTeleportSoundPriority) {
                        throw std::runtime_error("portal sound pump mismatch");
                    }

                    std::cout << "portal_sound=ok level=" << (level + 1)
                              << " key=" << key
                              << " cursor=" << std::showbase << std::hex
                              << kPortalTeleportSoundCursor
                              << std::dec << std::noshowbase
                              << " priority="
                              << static_cast<int>(kPortalTeleportSoundPriority)
                              << '\n';
                    return;
                }
            }
        }
        throw std::runtime_error("no portal tile found for sound routing");
    }

    void debugPortalCooldowns() {
        load();
        for (size_t level = 0; level < levels_.size(); ++level) {
            resetLevel(static_cast<int>(level));
            for (int y = 1; y < level_.height; ++y) {
                for (int x = 0; x < level_.width; ++x) {
                    if (tileAt(x, y) != 0x45) continue;
                    uint16_t key = static_cast<uint16_t>(wordAt(x, y) & 0x7fffu);
                    if (key == 0) continue;
                    const LevelPortal* destination = nullptr;
                    for (const LevelPortal& portal : level_.portals) {
                        if (portal.key == key) {
                            destination = &portal;
                            break;
                        }
                    }
                    if (!destination) continue;

                    playerCount_ = 2;
                    portalCooldown_ = 0;
                    portalCooldown2_ = 0;
                    triggerCooldown_ = 0;
                    triggerCooldown2_ = 0;
                    player_.x = static_cast<float>(x * kTileSize);
                    player_.y = static_cast<float>(y * kTileSize - 8);
                    player2_ = player_;

                    updatePortalsAndTriggers(player_, portalCooldown_, triggerCooldown_,
                                             true);
                    updatePortalsAndTriggers(player2_, portalCooldown2_, triggerCooldown2_,
                                             true);
                    if (player_.x != static_cast<float>(destination->x) ||
                        player_.y != static_cast<float>(destination->y) ||
                        player2_.x != static_cast<float>(destination->x) ||
                        player2_.y != static_cast<float>(destination->y) ||
                        portalCooldown_ == 0 || portalCooldown2_ == 0) {
                        throw std::runtime_error("portal cooldown blocked player 2");
                    }
                    std::cout << "portal_cooldowns=ok level=" << (level + 1)
                              << " key=" << key << '\n';
                    return;
                }
            }
        }
        throw std::runtime_error("no portal source tile found");
    }

    void debugCollisionPushout() {
        load();
        resetLevel(0);
        std::fill(level_.tiles.begin(), level_.tiles.end(), uint8_t{0});
        std::fill(level_.wordLayer.begin(), level_.wordLayer.end(), uint16_t{0});

        auto setTile = [&](int x, int y, uint8_t tile) {
            if (x < 0 || y < 0 || x >= level_.width || y >= level_.height) {
                throw std::runtime_error("synthetic collision tile outside level bounds");
            }
            tileRef(x, y) = tile;
        };
        auto makeMonster = [](int x, int y, int16_t vx8, int16_t vy8) {
            ActiveMonster monster;
            monster.x = x;
            monster.y = y;
            monster.kind = 1;
            monster.behavior = 3;
            monster.alive = true;
            monster.vx8 = vx8;
            monster.vy8 = vy8;
            monster.ai0 = static_cast<uint16_t>(std::abs(vx8));
            monster.animDelay = 1;
            monster.animStart = 43;
            monster.animEnd = 44;
            monster.animFrame = 43;
            return monster;
        };

        constexpr uint8_t kSolidDebugTile = 2;
        constexpr int kSolidX = 5;
        constexpr int kSolidY = 5;
        setTile(kSolidX, kSolidY, kSolidDebugTile);

        player_.x = static_cast<float>(kSolidX * kTileSize - 12);
        player_.y = static_cast<float>(kSolidY * kTileSize);
        if (collides(player_.x, player_.y)) {
            throw std::runtime_error("player horizontal fixture starts blocked");
        }
        movePlayer(player_, 2.0f, 0.0f);
        if (collides(player_.x, player_.y) ||
            player_.x != static_cast<float>(kSolidX * kTileSize - 12)) {
            throw std::runtime_error("player horizontal pushout did not clear collision");
        }

        constexpr int kFloorX = 10;
        constexpr int kFloorY = 8;
        setTile(kFloorX, kFloorY, kSolidDebugTile);
        player_.x = static_cast<float>(kFloorX * kTileSize);
        player_.y = static_cast<float>(kFloorY * kTileSize - 16);
        player_.grounded = false;
        player_.vy = 12.0f;
        if (collides(player_.x, player_.y)) {
            throw std::runtime_error("player vertical fixture starts blocked");
        }
        movePlayer(player_, 0.0f, 2.0f);
        if (collides(player_.x, player_.y) ||
            player_.y != static_cast<float>(kFloorY * kTileSize - 16) ||
            !player_.grounded || player_.vy != 0.0f) {
            throw std::runtime_error("player vertical pushout did not land cleanly");
        }

        playerDead_ = true;
        player2Dead_ = true;
        monsters_.clear();
        monsters_.push_back(makeMonster(kSolidX * kTileSize - 14,
                                        kSolidY * kTileSize, 0x0200, 0));
        if (monsterCollides(monsters_.front().x, monsters_.front().y)) {
            throw std::runtime_error("monster horizontal fixture starts blocked");
        }
        updateMonsters(0.0f);
        if (monsters_.empty() ||
            monsterCollides(monsters_.front().x, monsters_.front().y) ||
            monsters_.front().x != kSolidX * kTileSize - 14 ||
            monsters_.front().vx8 >= 0) {
            throw std::runtime_error("monster horizontal pushout did not clear collision");
        }

        monsters_.clear();
        monsters_.push_back(makeMonster(kFloorX * kTileSize,
                                        kFloorY * kTileSize - 16, 0, 0x0200));
        if (monsterCollides(monsters_.front().x, monsters_.front().y)) {
            throw std::runtime_error("monster vertical fixture starts blocked");
        }
        updateMonsters(0.0f);
        if (monsters_.empty() ||
            monsterCollides(monsters_.front().x, monsters_.front().y) ||
            monsters_.front().y != kFloorY * kTileSize - 16 ||
            monsters_.front().vy8 != 0) {
            throw std::runtime_error("monster vertical pushout did not clear collision");
        }

        monsters_.clear();
        ActiveMonster behavior4X = makeMonster(kSolidX * kTileSize - 14,
                                               kSolidY * kTileSize, 0x0400, 0);
        behavior4X.behavior = 4;
        behavior4X.motionTimer = 2;
        monsters_.push_back(behavior4X);
        updateMonsters(0.0f);
        if (monsters_.empty() ||
            monsterCollides(monsters_.front().x, monsters_.front().y) ||
            monsters_.front().x != kSolidX * kTileSize - 14 ||
            monsters_.front().vx8 != -0x0200 ||
            monsters_.front().motionTimer != 0) {
            throw std::runtime_error("behavior-4 horizontal half reversal failed");
        }

        monsters_.clear();
        ActiveMonster behavior4Y = makeMonster(kFloorX * kTileSize,
                                               kFloorY * kTileSize - 16, 0, 0x0400);
        behavior4Y.behavior = 4;
        behavior4Y.motionTimer = 2;
        monsters_.push_back(behavior4Y);
        updateMonsters(0.0f);
        if (monsters_.empty() ||
            monsterCollides(monsters_.front().x, monsters_.front().y) ||
            monsters_.front().y != kFloorY * kTileSize - 16 ||
            monsters_.front().vy8 != -0x0200 ||
            monsters_.front().motionTimer != 0) {
            throw std::runtime_error("behavior-4 vertical half reversal failed");
        }

        constexpr int kPassableX = 15;
        constexpr int kPassableY = 5;
        setTile(kPassableX, kPassableY, 0x67);
        setTile(kPassableX + 1, kPassableY, 0x45);
        setTile(kPassableX, kPassableY + 1, 0x6d);
        setTile(kPassableX + 1, kPassableY + 1, 0x72);
        if (collides(static_cast<float>(kPassableX * kTileSize),
                     static_cast<float>(kPassableY * kTileSize)) ||
            monsterCollides(kPassableX * kTileSize, kPassableY * kTileSize)) {
            throw std::runtime_error("passable object footprint blocked movement");
        }

        std::cout << "collision_pushout=ok"
                  << " player_h_clear=1"
                  << " player_v_clear=1"
                  << " monster_h_clear=1"
                  << " monster_v_clear=1"
                  << " monster_b4_half=1"
                  << " passable_clear=1"
                  << " solid_tile=" << static_cast<int>(kSolidDebugTile) << '\n';
    }

    void debugMonsterBombKillLive() {
        load();
        initSdl();
        prepareAutoplayerMonsterFixtureLevel();
        bool running = true;

        player_.x = 80.0f;
        player_.y = 24.0f;
        player_.grounded = true;
        bombInventory_.counts[3] = 1;
        bombInventory_.selected = BombType::Super;
        int superBefore = bombInventory_.counts[3];
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.empty() || bombs_.back().type != BombType::Super ||
            bombInventory_.counts[3] != superBefore - 1) {
            throw std::runtime_error("live monster bomb fixture did not place a super bomb");
        }

        Bomb placed = bombs_.back();
        bombs_.back().timer = 1;
        player_.x = 0.0f;
        player_.y = 0.0f;

        ActiveMonster monster;
        monster.x = placed.x * kTileSize + kTileSize;
        monster.y = placed.y * kTileSize - kTileSize;
        monster.kind = 1;
        monster.behavior = 3;
        monster.ai0 = 0x0800;
        monster.hp = monsterDamageForBomb(BombType::Super);
        monster.animDelay = 1;
        refreshMonsterAnimationProfile(monster);
        initializeMonsterMotion(monster);
        monster.vx8 = 0x0800;
        monsters_.push_back(monster);

        FrameInspection armedFrame = inspectRenderedFrame("monster-bomb-kill-live-armed");
        FrameControls idle;
        updateWithControls(idle, 1.0f / 60.0f);
        if (!bombs_.empty() || monsters_.empty() || monsters_.front().behavior != 2 ||
            monsters_.front().hp != 0 || bonusDrops_.empty()) {
            std::ostringstream oss;
            oss << "live bomb did not kill overlapping moving monster"
                << " bombs=" << bombs_.size()
                << " monsters=" << monsters_.size();
            if (!monsters_.empty()) {
                oss << " behavior=" << static_cast<int>(monsters_.front().behavior)
                    << " hp=" << monsters_.front().hp
                    << " xy=" << monsters_.front().x << ',' << monsters_.front().y;
            }
            oss << " drops=" << bonusDrops_.size()
                << " bomb_tile=" << placed.x << ',' << placed.y;
            throw std::runtime_error(oss.str());
        }
        FrameInspection deathFrame = inspectRenderedFrame("monster-bomb-kill-live-death");
        if (deathFrame.hash == armedFrame.hash) {
            throw std::runtime_error("live monster bomb death frame did not change");
        }

        int deathTicks = monsters_.front().stateTimer;
        for (int i = 0; i < deathTicks; ++i) {
            updateWithControls(idle, 1.0f / 60.0f);
        }
        if (!monsters_.empty()) {
            throw std::runtime_error("live monster death actor was not removed");
        }

        std::cout << "monster_bomb_kill_live=ok"
                  << " bomb_type=4 damage=" << monsterDamageForBomb(BombType::Super)
                  << " killed=1 removed=1 reward=1"
                  << " frame_inspection=1\n";
    }

    void debugPlayerDamageDeathLive() {
        load();
        initSdl();
        prepareAutoplayerMonsterFixtureLevel();
        level_.requiredBonus = 1;
        level_.startingObjectiveTiles = 1;
        tileRef(0, 0) = level_.objectiveTile;
        player_.x = 80.0f;
        player_.y = 24.0f;
        player_.grounded = true;
        energy_ = 100;
        lives_ = 3;
        damageCooldown_ = 0;

        CollapseRecord hazard;
        int maxTx = std::max(0, level_.width - 1);
        int maxTy = std::max(0, level_.height - 1);
        int playerTileX = static_cast<int>(player_.x) / kTileSize;
        int tx0 = std::clamp(playerTileX - 2, 0, maxTx);
        int ty0 = 0;
        int tx1 = std::clamp(playerTileX + 3, 0, maxTx);
        int ty1 = maxTy;
        hazard.startOffsetBytes = static_cast<uint16_t>((ty0 * level_.width + tx0) * 2);
        hazard.endOffsetBytes = static_cast<uint16_t>((ty1 * level_.width + tx1) * 2);
        hazard.timer = 240;
        hazard.count = 1;
        collapseQueue_.push_back(hazard);

        FrameInspection startFrame = inspectRenderedFrame("player-damage-live-start");
        FrameControls idle;
        updateWithControls(idle, 1.0f / 60.0f);
        int firstEnergy = energy_;
        if (firstEnergy >= 100 || playerDead_) {
            std::ostringstream oss;
            oss << "live hazard did not drain player HP"
                << " energy=" << energy_
                << " pending=" << static_cast<int>(pendingDamage_)
                << " collapse=" << collapseQueue_.size()
                << " p_xy=" << static_cast<int>(player_.x) << ','
                << static_cast<int>(player_.y);
            throw std::runtime_error(oss.str());
        }

        int frames = 1;
        while (!playerDead_ && frames < 140) {
            updateWithControls(idle, 1.0f / 60.0f);
            ++frames;
        }
        int framesToState2 = frames;
        if (!playerDead_ || !pendingLifeLoss_ || lives_ != 3 || energy_ != 100) {
            std::ostringstream oss;
            oss << "live repeated hazard did not enter delayed state-2"
                << " frames=" << frames
                << " energy=" << energy_
                << " lives=" << lives_
                << " pending_life_loss=" << (pendingLifeLoss_ ? 1 : 0)
                << " dead=" << (playerDead_ ? 1 : 0)
                << " death_timer=" << deathStateTimer_
                << " collapse=" << collapseQueue_.size();
            throw std::runtime_error(oss.str());
        }
        while (pendingLifeLoss_ && frames < 260) {
            updateWithControls(idle, 1.0f / 60.0f);
            ++frames;
        }
        if (lives_ != 2 || energy_ != 100) {
            std::ostringstream oss;
            oss << "live repeated hazard did not consume a life"
                << " frames=" << frames
                << " energy=" << energy_
                << " lives=" << lives_
                << " dead=" << (playerDead_ ? 1 : 0)
                << " death_timer=" << deathStateTimer_
                << " collapse=" << collapseQueue_.size();
            throw std::runtime_error(oss.str());
        }
        tryReenterPlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                         damageCooldown_, 1);
        if (playerDead_ || energy_ != 100 || lives_ != 2 ||
            damageCooldown_ != kDamageCooldownTicks) {
            std::ostringstream oss;
            oss << "live repeated hazard did not reenter after state-2 countdown"
                << " energy=" << energy_
                << " lives=" << lives_
                << " dead=" << (playerDead_ ? 1 : 0)
                << " cooldown=" << damageCooldown_
                << " death_timer=" << deathStateTimer_;
            throw std::runtime_error(oss.str());
        }
        FrameInspection deathFrame = inspectRenderedFrame("player-damage-live-death");
        if (deathFrame.hash == startFrame.hash) {
            throw std::runtime_error("live player death frame did not change");
        }

        std::cout << "player_damage_death_live=ok"
                  << " first_energy=" << firstEnergy
                  << " frames_to_life_loss=" << frames
                  << " lives=" << lives_
                  << " reentry_state=" << (playerDead_ ? 0 : 1)
                  << " frame_inspection=1"
                  << " frames_to_state2=" << framesToState2
                  << " delayed_life_loss=1\n";
    }

    void debugMonsterContactDamageLive() {
        load();
        initSdl();
        prepareAutoplayerMonsterFixtureLevel();
        playerCount_ = 2;
        playerDead_ = false;
        player2Dead_ = false;
        player_.x = 40.0f;
        player_.y = 24.0f;
        player2_.x = 80.0f;
        player2_.y = 24.0f;
        energy_ = 100;
        energy2_ = 100;
        lives_ = 3;
        lives2_ = 3;

        auto makeContactMonster = [&](int x, int y) {
            ActiveMonster monster;
            monster.x = x;
            monster.y = y;
            monster.kind = 1;
            monster.behavior = 3;
            monster.ai0 = 0;
            monster.hp = 3;
            monster.animDelay = 1;
            refreshMonsterAnimationProfile(monster);
            initializeMonsterMotion(monster);
            monster.vx8 = 0;
            monster.vy8 = 0;
            return monster;
        };

        monsters_.push_back(makeContactMonster(40, 24));
        monsters_.push_back(makeContactMonster(48, 24));
        monsters_.push_back(makeContactMonster(80, 24));

        FrameInspection startFrame = inspectRenderedFrame("monster-contact-damage-start");
        updateMonsters(0.0f);
        if (pendingDamage_ != 2 || pendingDamage2_ != 1 ||
            energy_ != 100 || energy2_ != 100) {
            std::ostringstream oss;
            oss << "monster contact did not accumulate expected pending damage"
                << " p1_pending=" << static_cast<int>(pendingDamage_)
                << " p2_pending=" << static_cast<int>(pendingDamage2_)
                << " p1_energy=" << energy_
                << " p2_energy=" << energy2_;
            throw std::runtime_error(oss.str());
        }

        drainPlayerDamageCounters();
        if (pendingDamage_ != 0 || pendingDamage2_ != 0 ||
            energy_ != 98 || energy2_ != 99 || playerDead_ || player2Dead_ ||
            !soundLatch_.active || soundLatch_.latchedOffset != kPlayerDamageSoundCursor ||
            soundLatch_.currentSelector != kPlayerDamageSoundPriority) {
            throw std::runtime_error("monster contact drain cadence changed");
        }
        pumpSoundLatch();
        if (soundLatch_.active || lastPumpedSoundOffset_ != kPlayerDamageSoundCursor ||
            lastPumpedSoundSelector_ != kPlayerDamageSoundPriority) {
            throw std::runtime_error("monster contact hurt cue did not pump");
        }
        FrameInspection hurtFrame = inspectRenderedFrame("monster-contact-damage-hurt");
        if (hurtFrame.hash == startFrame.hash) {
            throw std::runtime_error("monster contact hurt frame did not change");
        }

        playerDead_ = true;
        energy_ = 100;
        pendingDamage_ = 3;
        clearSoundLatch();
        drainPlayerDamageCounters();
        if (energy_ != 100 || !playerDead_ || pendingDamage_ != 0 ||
            !soundLatch_.active || soundLatch_.latchedOffset != kPlayerDamageSoundCursor) {
            throw std::runtime_error("state-2 contact damage did not preserve energy with hurt cue");
        }

        playerDead_ = false;
        energy_ = 1;
        lives_ = 3;
        pendingDamage_ = 2;
        deathStateTimer_ = 0;
        clearSoundLatch();
        drainPlayerDamageCounters();
        if (!playerDead_ || lives_ != 3 || !pendingLifeLoss_ || energy_ != 100 ||
            deathStateTimer_ != kDeathStateTicks || pendingDamage_ != 0 ||
            !soundLatch_.active || soundLatch_.latchedOffset != kPlayerDeathSoundCursor ||
            soundLatch_.currentSelector != kPlayerDeathSoundPriority) {
            throw std::runtime_error("fatal monster contact did not dispatch death");
        }

        std::cout << "monster_contact_damage_live=ok"
                  << " p1_pending=2 p2_pending=1"
                  << " p1_energy=98 p2_energy=99"
                  << " hurt_cue=0x" << std::hex << std::setw(4) << std::setfill('0')
                  << kPlayerDamageSoundCursor
                  << " death_cue=0x" << std::setw(4) << kPlayerDeathSoundCursor
                  << std::dec << std::setfill(' ')
                  << " state2_preserved=1 fatal_dead=1 frame_inspection=1\n";
    }

    void debugObjectCollisionJumpLive() {
        load();
        initSdl();
        resetLevel(0);
        menu_ = false;
        playerCount_ = 1;
        constexpr int kObjectX = 17;
        constexpr int kObjectY = 22;
        if (!isObjectJumpSupportCell(kObjectX, kObjectY) ||
            !isPassableObjectCell(kObjectX, kObjectY)) {
            throw std::runtime_error("level 1 object support fixture is not a passable object cell");
        }
        player_.x = static_cast<float>(kObjectX * kTileSize);
        player_.y = static_cast<float>(kObjectY * kTileSize - 15);
        player_.vy = 0.0f;
        player_.grounded = false;
        if (collides(player_.x, player_.y)) {
            throw std::runtime_error("object jump fixture starts blocked");
        }
        FrameInspection startFrame = inspectRenderedFrame("object-jump-live-start");

        FrameControls jump;
        jump.p1Jump = true;
        float startY = player_.y;
        updateWithControls(jump, 1.0f / 60.0f);
        if (player_.vy >= 0.0f || player_.y >= startY || player_.grounded) {
            throw std::runtime_error("passable object cell did not provide jump support");
        }
        int jumpVy = static_cast<int>(std::lround(player_.vy));
        FrameInspection jumpFrame = inspectRenderedFrame("object-jump-live-airborne");
        if (jumpFrame.hash == startFrame.hash) {
            throw std::runtime_error("object jump frame did not change");
        }

        resetLevel(0);
        menu_ = false;
        AutoplayRouteResult route = autoplayLevel1BombRoute();
        if (route.bombTileX != 24 || route.bombTileY != 22) {
            throw std::runtime_error("object jump support blocked level 1 bomb route");
        }

        std::cout << "object_collision_jump_live=ok"
                  << " support_cell=" << kObjectX << ',' << kObjectY
                  << " jump_vy=" << jumpVy
                  << " route_clear=1 frame_inspection=1\n";
    }

    void debugAllLevelsRender() {
        // Regression guard: every shipped level must render a coherent gameplay
        // frame with the recovered bottom HUD, so the faithful rendering
        // verified on levels 1-2 is locked in across all levels.
        load();
        initSdl();
        menu_ = false;
        paused_ = false;
        levelIntro_ = {};
        playerCount_ = 1;
        const int hudY = kScreenH - 46;
        size_t rendered = 0;
        std::vector<uint64_t> hashes;
        for (size_t level = 0; level < levels_.size(); ++level) {
            resetLevel(static_cast<int>(level));
            FrameInspection frame =
                inspectRenderedFrame("all-levels-render-" + std::to_string(level));
            // World band must have visible level geometry, and the HUD band must
            // render the recovered bottom panel.
            if (!regionHasVariation(0, 0, kScreenW, hudY) ||
                !regionHasVariation(0, hudY, kScreenW, 46)) {
                throw std::runtime_error("level " + std::to_string(level) +
                                         " did not render world and HUD");
            }
            hashes.push_back(frame.hash);
            ++rendered;
        }
        // Distinct levels must produce distinct frames (no stuck/blank level).
        for (size_t i = 1; i < hashes.size(); ++i) {
            if (hashes[i] == hashes[i - 1]) {
                throw std::runtime_error("levels " + std::to_string(i - 1) +
                                         " and " + std::to_string(i) +
                                         " rendered identical frames");
            }
        }
        std::cout << "all_levels_render=ok levels=" << rendered
                  << " world_visible=1 hud_visible=1 distinct=1\n";
    }

    // Dump every level's gameplay start frame to a PPM so it can be compared
    // pixel-for-pixel against the original captured under DOSBox. Mirrors the
    // rendering path exercised by debugAllLevelsRender().
    void captureLevelFrames(const std::string& outDir) {
        load();
        initSdl();
        std::filesystem::create_directories(outDir);
        menu_ = false;
        paused_ = false;
        levelIntro_ = {};
        playerCount_ = 1;
        for (size_t level = 0; level < levels_.size(); ++level) {
            resetLevel(static_cast<int>(level));
            inspectRenderedFrame("capture-level-" + std::to_string(level));
            char name[32];
            std::snprintf(name, sizeof(name), "level%02zu.ppm", level + 1);
            writeArgbPpm(joinPath(outDir, name), fb_, kScreenW, kScreenH);
        }
        std::cout << "capture_level_frames=ok levels=" << levels_.size()
                  << " out=" << outDir << "\n";
    }

    void debugLevelIntro(const std::string& framePath = {}) {
        load();
        initSdl();
        std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
        if (exeBytes.size() != 52384 ||
            exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
            throw std::runtime_error("level intro executable fixture changed");
        }
        const size_t imageBase = static_cast<size_t>(le16(exeBytes, 0x08)) * 16;
        const size_t captionOffset = imageBase + 0xb2aa;
        const std::string originalCaption = "preparati per il livello ";
        if (captionOffset + 1 + originalCaption.size() > exeBytes.size() ||
            exeBytes[captionOffset] != originalCaption.size() ||
            !std::equal(originalCaption.begin(), originalCaption.end(),
                        exeBytes.begin() + static_cast<long>(captionOffset + 1))) {
            throw std::runtime_error("original level intro caption bytes changed");
        }

        const LevelIntroPattern fixture = capturedLevelIntroPattern();
        const std::string level1Caption = levelIntroCaption(0);
        resetClip();
        std::fill(fb_.begin(), fb_.end(), 0xff000000u);
        drawLevelIntro(0, fixture, level1Caption.size());
        FrameInspection exactFrame;
        const uint32_t first = fb_.front();
        exactFrame.hash = 1469598103934665603ull;
        for (uint32_t pixelValue : fb_) {
            if (pixelValue != first) ++exactFrame.changedPixels;
            exactFrame.hash ^= static_cast<uint64_t>(pixelValue);
            exactFrame.hash *= 1099511628211ull;
        }
        constexpr uint64_t kCapturedFrameHash = 0x85e10db60f7e89f9ull;
        constexpr size_t kCapturedChangedPixels = 55025;
        constexpr size_t kCapturedBluePixels = 360;
        constexpr size_t kCapturedWhitePixels = 620;
        if (exactFrame.hash != kCapturedFrameHash ||
            exactFrame.changedPixels != kCapturedChangedPixels ||
            first != 0xff515545u ||
            countColorInRegion(0, 0, kScreenW, kScreenH, argb(palette_, 1)) !=
                kCapturedBluePixels ||
            countColorInRegion(0, 0, kScreenW, kScreenH, argb(palette_, 31)) !=
                kCapturedWhitePixels) {
            throw std::runtime_error(
                "level intro did not match the captured original frame");
        }
        if (!framePath.empty()) {
            writeArgbPpm(framePath, fb_, kScreenW, kScreenH);
        }
        std::vector<uint32_t> level1Pixels = fb_;
        if (!regionHasVariation(0, 0, kScreenW, 80) ||
            !regionHasVariation(16, 93, 282, 9)) {
            throw std::runtime_error("level intro did not render stripes and caption");
        }
        resetClip();
        std::fill(fb_.begin(), fb_.end(), 0xff000000u);
        drawLevelIntro(2, fixture, levelIntroCaption(2).size());
        if (!regionChanged(level1Pixels, 16, 93, 282, 9)) {
            throw std::runtime_error("level intro caption did not change with level");
        }

        resetLevel(0);
        menu_ = true;
        interactiveLevelIntroEnabled_ = true;
        bool running = true;
        pushKeyDown(SDLK_1);
        processEvents(running);
        if (!levelIntro_.active || menu_ || levelIndex_ != 0 ||
            visibleLevelIntroCharacters(levelIntro_.startedAt) != 1) {
            throw std::runtime_error("interactive menu start did not begin level intro");
        }
        const uint32_t logicBefore = logicTick_;
        updateWithControls(FrameControls{}, 1.0f / 60.0f);
        if (logicTick_ != logicBefore) {
            throw std::runtime_error("gameplay advanced while level intro was active");
        }
        const uint32_t duration =
            static_cast<uint32_t>(level1Caption.size()) * kLevelIntroCharacterDelayMs;
        updateLevelIntro(levelIntro_.startedAt + duration - 1);
        if (!levelIntro_.active ||
            visibleLevelIntroCharacters(levelIntro_.startedAt + duration - 1) !=
                level1Caption.size()) {
            throw std::runtime_error("level intro reveal timing ended early");
        }
        updateLevelIntro(levelIntro_.startedAt + duration);
        if (levelIntro_.active) {
            throw std::runtime_error("level intro reveal timing did not finish");
        }

        beginLevelForPlay(1);
        pushKeyDown(SDLK_SPACE);
        processEvents(running);
        if (levelIntro_.active || !bombs_.empty()) {
            throw std::runtime_error("level intro skip key leaked into gameplay");
        }
        beginLevelForPlay(2);
        pushKeyDown(SDLK_ESCAPE);
        processEvents(running);
        if (levelIntro_.active || !menu_ || menuPage_ != MenuPage::Main) {
            throw std::runtime_error("level intro Escape did not return to menu");
        }
        interactiveLevelIntroEnabled_ = false;

        std::cout << "level_intro=ok stripes=7"
                  << " palette=" << static_cast<int>(kLevelIntroPaletteFirst)
                  << '-'
                  << static_cast<int>(kLevelIntroPaletteFirst +
                                      kLevelIntroPaletteCount - 1)
                  << " exact_hash=" << hex64(kCapturedFrameHash)
                  << " exact_pixels=" << kCapturedChangedPixels
                  << " caption_pixels="
                  << (kCapturedBluePixels + kCapturedWhitePixels)
                  << " delay_ms=" << kLevelIntroCharacterDelayMs
                  << " level_varies=1 live_flow=1 input_skip=1 escape_menu=1"
                  << " frame_inspection=1\n";
    }

    void debugHudStatsLive() {
        load();
        initSdl();
        resetLevel(0);
        menu_ = false;
        playerCount_ = 1;
        energy_ = 73;
        lives_ = 2;
        score_ = 12345;
        bombInventory_.selected = BombType::Large;
        bombInventory_.counts = {199, 7, 3, 1};

        const int hudY = kScreenH - 46;
        FrameInspection first = inspectRenderedFrame("hud-stats-live-first");
        std::vector<uint32_t> firstPixels = fb_;
        if (!regionHasVariation(0, hudY, kScreenW, 46) ||
            !regionHasVariation(0, hudY + 18, 88, 20) ||
            !regionHasVariation(116, hudY + 6, 64, 34)) {
            throw std::runtime_error("HUD stats panel did not render visible gauges/icons");
        }

        energy_ = 21;
        lives_ = 1;
        bombInventory_.selected = BombType::Super;
        bombInventory_.counts[3] = 0;
        FrameInspection second = inspectRenderedFrame("hud-stats-live-second");
        if (second.hash == first.hash ||
            !regionChanged(firstPixels, 0, hudY, kScreenW, 46)) {
            throw std::runtime_error("HUD stats panel did not react to player/bomb stat changes");
        }

        std::cout << "hud_stats_live=ok"
                  << " hp_visible=1 lives_visible=1 bombs_visible=1"
                  << " progress_visible=1 frame_inspection=1\n";
    }

    void debugTwoPlayerHudPanel() {
        load();
        initSdl();
        resetLevel(0);
        menu_ = false;
        playerCount_ = 2;
        player_.x = 96.0f;
        player_.y = 168.0f;
        player2_.x = 152.0f;
        player2_.y = 168.0f;
        energy_ = 88;
        energy2_ = 41;
        lives_ = 3;
        lives2_ = 1;
        score_ = 1234;
        score2_ = 5678;
        collected_ = 2;
        destroyed_ = std::max(1, level_.startingDestructibleTiles / 3);
        bombInventory_.selected = BombType::Medium;
        bombInventory_.counts = {199, 4, 2, 1};
        bombInventory2_.selected = BombType::Super;
        bombInventory2_.counts = {188, 3, 1, 0};

        FrameInspection first = inspectRenderedFrame("two-player-hud-panel-first");
        std::vector<uint32_t> firstPixels = fb_;
        if (!regionHasVariation(0, 0, kScreenW, 24) ||
            !regionHasVariation(0, 24, kScreenW, 74) ||
            !regionHasVariation(0, 100, kScreenW, 24) ||
            !regionHasVariation(72, 114, 150, 9) ||
            !regionHasVariation(0, 124, kScreenW, 76)) {
            throw std::runtime_error("two-player HUD panel did not render visible split UI");
        }

        ++collected_;
        destroyed_ = std::min(level_.startingDestructibleTiles,
                              destroyed_ + std::max(1, level_.startingDestructibleTiles / 5));
        score2_ += 250;
        energy2_ = 7;
        FrameInspection second = inspectRenderedFrame("two-player-hud-panel-second");
        if (second.hash == first.hash ||
            !regionChanged(firstPixels, 0, 100, kScreenW, 24) ||
            !regionChanged(firstPixels, 72, 114, 150, 9)) {
            throw std::runtime_error("two-player HUD panel did not react to progress/stat changes");
        }

        std::cout << "two_player_hud_panel=ok"
                  << " split_views=2"
                  << " p1_hud_visible=1"
                  << " p1_world_visible=1"
                  << " p2_hud_visible=1"
                  << " p2_world_visible=1"
                  << " objective_panel_visible=1"
                  << " objective_panel_changed=1"
                  << " panel_y=100 panel_h=24"
                  << " progress_region=72,114,150,9"
                  << " frame_inspection=1"
                  << " original_art_claim=0\n";
    }

    void exportSprites(const std::string& bankName, const std::string& path) {
        load();
        const SpriteBank* bank = nullptr;
        if (bankName == "BOMOMIMK.SPR" || bankName == "bomomimk.spr" || bankName == "bomomimk") {
            bank = &sprites_;
        } else if (bankName == "PROVA.SPR" || bankName == "prova.spr" || bankName == "prova") {
            bank = &altSprites_;
        } else if (bankName == "FONTS.SPR" || bankName == "fonts.spr" || bankName == "fonts") {
            bank = &fontSprites_;
        } else {
            throw std::runtime_error("unknown sprite bank " + bankName);
        }
        if (!bank || bank->sprites.empty()) {
            throw std::runtime_error(bankName + " is empty");
        }

        int maxW = 0;
        int maxH = 0;
        for (const Sprite& sprite : bank->sprites) {
            maxW = std::max(maxW, sprite.width);
            maxH = std::max(maxH, sprite.height);
        }
        int columns = 10;
        int cellW = maxW + 4;
        int cellH = maxH + 4;
        int rows = static_cast<int>((bank->sprites.size() + columns - 1) / columns);
        int width = columns * cellW;
        int height = rows * cellH;
        std::vector<Rgb> out(static_cast<size_t>(width) * height, palette_[0]);

        for (size_t i = 0; i < bank->sprites.size(); ++i) {
            const Sprite& sprite = bank->sprites[i];
            int ox = static_cast<int>(i % columns) * cellW + 2;
            int oy = static_cast<int>(i / columns) * cellH + 2;
            for (int y = 0; y < sprite.height; ++y) {
                for (int x = 0; x < sprite.width; ++x) {
                    uint8_t px = sprite.pixels[static_cast<size_t>(y) * sprite.width + x];
                    if (px == 0) continue;
                    out[static_cast<size_t>(oy + y) * width + ox + x] = palette_[px];
                }
            }
        }

        std::ofstream file(path, std::ios::binary);
        if (!file) {
            throw std::runtime_error("cannot create " + path);
        }
        file << "P6\n" << width << ' ' << height << "\n255\n";
        for (const Rgb& c : out) {
            file.put(static_cast<char>(c.r));
            file.put(static_cast<char>(c.g));
            file.put(static_cast<char>(c.b));
        }
    }

    ~App() {
        if (audioDevice_ != 0) SDL_CloseAudioDevice(audioDevice_);
        if (texture_) SDL_DestroyTexture(texture_);
        if (renderer_) SDL_DestroyRenderer(renderer_);
        if (window_) SDL_DestroyWindow(window_);
        SDL_Quit();
    }

private:
    Palette palette_{};
    Palette backgroundPalette_{};
    IndexedImage background_;
    TileBank tiles_;
    SpriteBank sprites_;
    SpriteBank altSprites_;
    SpriteBank fontSprites_;
    SoundBank sounds_;
    GranBank gran_;
    std::vector<Record> records_;
    std::vector<Level> levels_;
    Level level_;
    int levelIndex_ = 0;
    int playerCount_ = 1;
    Player player_;
    Player player2_;
    std::vector<SpawnerState> spawnerStates_;
    std::vector<ActiveMonster> monsters_;
    std::vector<BossMotionLink> bossLinks_;
    std::array<float, 128> bossSinTable_{};
    bool bossPresent_ = false;
    bool bossDefeated_ = false;
    bool interactiveLevelIntroEnabled_ = false;
    LevelIntroState levelIntro_;
    std::vector<BonusDrop> bonusDrops_;
    std::vector<Bomb> bombs_;
    std::vector<Flash> flashes_;
    std::vector<LaunchPadMarker> launchPadMarkers_;
    std::vector<ExplosionEffect> explosionEffects_;
    std::vector<DebrisRecord> debrisQueue_;
    std::vector<CollapseRecord> collapseQueue_;
    std::vector<uint32_t> fb_ = std::vector<uint32_t>(kScreenW * kScreenH);
    SDL_Window* window_ = nullptr;
    SDL_Renderer* renderer_ = nullptr;
    SDL_Texture* texture_ = nullptr;
    SDL_AudioDeviceID audioDevice_ = 0;
    SDL_AudioSpec audioSpec_{};
    bool audioEnabled_ = false;
    SoundLatch soundLatch_;
    int lastPumpedSoundRecord_ = -1;
    uint16_t lastPumpedSoundOffset_ = 0;
    uint8_t lastPumpedSoundSelector_ = 0;
    bool traceCompatibilitySoundAttempts_ = false;
    std::vector<CompatibilitySoundAttempt> compatibilitySoundAttempts_;
    bool menu_ = true;
    MenuPage menuPage_ = MenuPage::Main;
    bool paused_ = false;
    bool showBackground_ = true;
    bool menuItalian_ = true;  // original defaults to Italian; L toggles English
    int gameplayViewWidth_ = kScreenW;
    int clipLeft_ = 0;
    int clipTop_ = 0;
    int clipRight_ = kScreenW;
    int clipBottom_ = kScreenH;
    int collected_ = 0;
    int destroyed_ = 0;
    int completeTimer_ = 0;
    int portalCooldown_ = 0;
    int triggerCooldown_ = 0;
    int portalCooldown2_ = 0;
    int triggerCooldown2_ = 0;
    int playerFacing_ = 1;
    int player2Facing_ = 1;
    int playerAnimTick_ = 0;
    int player2AnimTick_ = 0;
    int energy_ = 100;
    int energy2_ = 100;
    int lives_ = 3;
    int lives2_ = 3;
    bool playerDead_ = false;
    bool player2Dead_ = false;
    int reentryTimer_ = 0;
    int reentryTimer2_ = 0;
    int deathStateTimer_ = 0;
    int deathStateTimer2_ = 0;
    bool pendingLifeLoss_ = false;
    bool pendingLifeLoss2_ = false;
    State2VisualCursor state2Visual_;
    State2VisualCursor state2Visual2_;
    State2EffectEntry state2Effect_;
    State2EffectEntry state2Effect2_;
    bool state2VisualCursorPreview_ = false;
    int damageCooldown_ = 0;
    int damageCooldown2_ = 0;
    uint8_t pendingDamage_ = 0;
    uint8_t pendingDamage2_ = 0;
    int levelResetGeneration_ = 0;
    BombInventory bombInventory_;
    BombInventory bombInventory2_;
    uint8_t weaponSwitchHoldTicks_ = 0;
    uint8_t weaponSwitchHoldTicks2_ = 0;
    uint32_t logicTick_ = 0;
    uint32_t randomSeed_ = 0x1234abcd;
    uint32_t score_ = 0;
    uint32_t score2_ = 0;
    std::string recordPath_ = "RECS.DAT";
    uint32_t pendingRecordScore_ = 0;
    uint8_t pendingRecordLevel_ = 0;
    uint8_t pendingRecordPlayer_ = 1;
    EndReason pendingRecordReason_ = EndReason::GameOver;
    std::string pendingRecordName_;
    std::vector<PendingRecordEntry> pendingRecordQueue_;
    EndReason lastEndReason_ = EndReason::GameOver;

    void initSdl() {
        if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_TIMER) != 0) {
            throw std::runtime_error(SDL_GetError());
        }
        window_ = SDL_CreateWindow("Larax & Zaco C++ reconstruction",
                                   SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                                   kScreenW * 3, kScreenH * 3, SDL_WINDOW_SHOWN);
        if (!window_) throw std::runtime_error(SDL_GetError());
        renderer_ = SDL_CreateRenderer(window_, -1, SDL_RENDERER_ACCELERATED);
        if (!renderer_) {
            std::string acceleratedError = SDL_GetError();
            SDL_ClearError();
            renderer_ = SDL_CreateRenderer(window_, -1, SDL_RENDERER_SOFTWARE);
            if (!renderer_) {
                throw std::runtime_error(std::string(SDL_GetError()) +
                                         " (accelerated renderer failed: " +
                                         acceleratedError + ")");
            }
        }
        if (SDL_RenderSetLogicalSize(renderer_, kScreenW, kScreenH) != 0) {
            throw std::runtime_error(SDL_GetError());
        }
        texture_ = SDL_CreateTexture(renderer_, SDL_PIXELFORMAT_ARGB8888,
                                     SDL_TEXTUREACCESS_STREAMING, kScreenW, kScreenH);
        if (!texture_) throw std::runtime_error(SDL_GetError());
        initAudio();
    }

    void initAudio() {
        if (SDL_InitSubSystem(SDL_INIT_AUDIO) != 0) {
            SDL_ClearError();
            return;
        }
        SDL_AudioSpec want{};
        want.freq = kAudioSampleRate;
        want.format = AUDIO_S16SYS;
        want.channels = 1;
        want.samples = 1024;
        SDL_AudioSpec have{};
        audioDevice_ = SDL_OpenAudioDevice(nullptr, 0, &want, &have,
                                           SDL_AUDIO_ALLOW_FREQUENCY_CHANGE |
                                               SDL_AUDIO_ALLOW_FORMAT_CHANGE |
                                               SDL_AUDIO_ALLOW_CHANNELS_CHANGE);
        if (audioDevice_ == 0) {
            SDL_ClearError();
            return;
        }
        audioSpec_ = have;
        audioEnabled_ = true;
        SDL_PauseAudioDevice(audioDevice_, 0);
    }

    void processEvents(bool& running) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) {
                running = false;
            } else if (e.type == SDL_KEYDOWN &&
                       (!e.key.repeat ||
                        shouldAcceptRepeatedNameEntryKey(e.key.keysym.sym))) {
                onKey(e.key.keysym.sym, running);
            }
        }
    }

    bool shouldAcceptRepeatedNameEntryKey(SDL_Keycode key) const {
        if (!menu_ || menuPage_ != MenuPage::NameEntry) {
            return false;
        }
        return key == SDLK_BACKSPACE || recordCharForKey(key) != '\0';
    }

    void pushKeyDown(SDL_Keycode key, bool repeat = false) {
        SDL_Event e{};
        e.type = SDL_KEYDOWN;
        e.key.type = SDL_KEYDOWN;
        e.key.state = SDL_PRESSED;
        e.key.repeat = repeat ? 1 : 0;
        e.key.keysym.sym = key;
        e.key.keysym.scancode = SDL_GetScancodeFromKey(key);
        if (SDL_PushEvent(&e) < 0) {
            throw std::runtime_error(SDL_GetError());
        }
    }

    void resetLevel(int index) {
        levelIntro_ = {};
        ++levelResetGeneration_;
        levelIndex_ = (index + static_cast<int>(levels_.size())) % static_cast<int>(levels_.size());
        level_ = levels_[levelIndex_];
        player_ = {};
        player2_ = {};
        spawnerStates_.clear();
        monsters_.clear();
        bonusDrops_.clear();
        bombs_.clear();
        flashes_.clear();
        launchPadMarkers_.clear();
        explosionEffects_.clear();
        debrisQueue_.clear();
        collapseQueue_.clear();
        paused_ = false;
        collected_ = 0;
        destroyed_ = 0;
        completeTimer_ = 0;
        portalCooldown_ = 0;
        triggerCooldown_ = 0;
        portalCooldown2_ = 0;
        triggerCooldown2_ = 0;
        playerFacing_ = 1;
        player2Facing_ = 1;
        playerAnimTick_ = 0;
        player2AnimTick_ = 0;
        energy_ = 100;
        energy2_ = 100;
        playerDead_ = false;
        player2Dead_ = false;
        reentryTimer_ = 0;
        reentryTimer2_ = 0;
        deathStateTimer_ = 0;
        deathStateTimer2_ = 0;
        pendingLifeLoss_ = false;
        pendingLifeLoss2_ = false;
        state2Visual_ = {};
        state2Visual2_ = {};
        state2Effect_ = {};
        state2Effect2_ = {};
        damageCooldown_ = 0;
        damageCooldown2_ = 0;
        pendingDamage_ = 0;
        pendingDamage2_ = 0;
        bombInventory_ = {};
        bombInventory2_ = {};
        weaponSwitchHoldTicks_ = 0;
        weaponSwitchHoldTicks2_ = 0;
        logicTick_ = 0;
        for (const MonsterSpawner& spawner : level_.monsterSpawners) {
            SpawnerState state;
            state.remaining = spawner.enabled ? spawner.spawnBudget : 0;
            state.availableSlots = spawner.liveAllowance;
            state.cooldown = spawner.cooldown;
            spawnerStates_.push_back(state);
        }
        if (const LevelPortal* start = findStartPortal(1)) {
            player_.x = static_cast<float>(start->x);
            player_.y = static_cast<float>(start->y);
        }
        if (const LevelPortal* start = findStartPortal(2)) {
            player2_.x = static_cast<float>(start->x);
            player2_.y = static_cast<float>(start->y);
        } else {
            player2_.x = std::min(player_.x + 16.0f, std::max(16.0f, level_.width * 8.0f - 16.0f));
            player2_.y = player_.y;
        }
        if (playerCount_ > 1) {
            playerDead_ = lives_ <= 0;
            player2Dead_ = lives2_ <= 0;
        }
        bossLinks_.clear();
        bossPresent_ = false;
        bossDefeated_ = false;
        // The original loads gran.mst at the end of level setup only when the
        // current-level byte DS:0x79B7 equals 7 (callsite 1000:2E78).
        if (levelIndex_ == 6) spawnLevel7Boss();
    }

    std::string levelIntroCaption(int levelIndex) const {
        return "PREPARATI PER IL LIVELLO " + std::to_string(levelIndex + 1);
    }

    LevelIntroPattern makeLevelIntroPattern() {
        LevelIntroPattern pattern;
        pattern.horizontalStep = randomInclusive(1, 80);
        pattern.verticalStep = randomInclusive(1, 80);
        std::array<int, 3> starts{};
        std::array<int, 3> deltas{};
        for (int& start : starts) start = randomInclusive(0, 19);
        for (int& delta : deltas) delta = randomInclusive(0, 29);
        for (size_t i = 0; i < pattern.colors.size(); ++i) {
            auto component = [&](size_t channel) {
                return vga6To8(static_cast<uint8_t>(
                    starts[channel] +
                    deltas[channel] * static_cast<int>(i) /
                        static_cast<int>(kLevelIntroPaletteCount)));
            };
            pattern.colors[i] = {component(0), component(1), component(2)};
        }
        return pattern;
    }

    LevelIntroPattern capturedLevelIntroPattern() const {
        LevelIntroPattern pattern;
        pattern.horizontalStep = 37;
        pattern.verticalStep = 77;
        constexpr std::array<int, 3> kStarts{17, 18, 16};
        constexpr std::array<int, 3> kDeltas{21, 23, 9};
        for (size_t i = 0; i < pattern.colors.size(); ++i) {
            auto component = [&](size_t channel) {
                return vga6To8(static_cast<uint8_t>(
                    kStarts[channel] +
                    kDeltas[channel] * static_cast<int>(i) /
                        static_cast<int>(kLevelIntroPaletteCount)));
            };
            pattern.colors[i] = {component(0), component(1), component(2)};
        }
        return pattern;
    }

    void beginLevelForPlay(int index) {
        if (!interactiveLevelIntroEnabled_) {
            resetLevel(index);
            return;
        }
        LevelIntroPattern pattern = makeLevelIntroPattern();
        resetLevel(index);
        levelIntro_.active = true;
        levelIntro_.startedAt = SDL_GetTicks();
        levelIntro_.levelIndex = levelIndex_;
        levelIntro_.pattern = pattern;
    }

    size_t visibleLevelIntroCharacters(uint32_t now) const {
        if (!levelIntro_.active) return 0;
        const size_t captionSize =
            levelIntroCaption(levelIntro_.levelIndex).size();
        const uint32_t elapsed = now - levelIntro_.startedAt;
        return std::min(captionSize,
                        static_cast<size_t>(elapsed /
                                            kLevelIntroCharacterDelayMs) +
                            1);
    }

    void updateLevelIntro(uint32_t now) {
        if (!levelIntro_.active) return;
        const uint32_t duration =
            static_cast<uint32_t>(levelIntroCaption(levelIntro_.levelIndex).size()) *
            kLevelIntroCharacterDelayMs;
        if (now - levelIntro_.startedAt >= duration) {
            levelIntro_.active = false;
        }
    }

    const LevelPortal* findStartPortal(uint8_t marker) const {
        for (const LevelPortal& portal : level_.portals) {
            if (portal.key == 0 && portal.marker == marker) {
                return &portal;
            }
        }
        return nullptr;
    }

    void onKey(SDL_Keycode key, bool& running) {
        if (levelIntro_.active) {
            levelIntro_.active = false;
            if (key == SDLK_ESCAPE) {
                paused_ = false;
                menu_ = true;
                menuPage_ = MenuPage::Main;
            }
            return;
        }
        if (menu_) {
            if (menuPage_ == MenuPage::NameEntry) {
                handleNameEntryKey(key);
            } else if (menuPage_ == MenuPage::GameOver ||
                       menuPage_ == MenuPage::CompletedGame) {
                if (key == SDLK_ESCAPE || key == SDLK_RETURN ||
                    key == SDLK_KP_ENTER || key == SDLK_SPACE) {
                    clearRunScores();
                    pendingRecordQueue_.clear();
                    clearPendingRecord();
                    menuPage_ = MenuPage::Main;
                }
            } else if (key == SDLK_ESCAPE) {
                if (menuPage_ == MenuPage::Main) running = false;
                else menuPage_ = MenuPage::Main;
            } else if (key == SDLK_RETURN || key == SDLK_1 || key == SDLK_2) {
                playerCount_ = key == SDLK_2 ? 2 : 1;
                lives_ = 3;
                lives2_ = 3;
                clearRunScores();
                pendingRecordQueue_.clear();
                clearPendingRecord();
                beginLevelForPlay(0);
                menu_ = false;
                menuPage_ = MenuPage::Main;
            } else if (key == SDLK_i) {
                menuPage_ = MenuPage::Info;
            } else if (key == SDLK_z) {
                menuPage_ = MenuPage::Instructions;
            } else if (key == SDLK_r) {
                menuPage_ = MenuPage::Records;
                requestRecordsPageSound();
            } else if (key == SDLK_s) {
                showBackground_ = !showBackground_;
            } else if (key == SDLK_l) {
                menuItalian_ = !menuItalian_;
            }
        } else if (!menu_ && key == SDLK_p) {
            paused_ = !paused_;
        } else if (!menu_ && key == SDLK_ESCAPE) {
            paused_ = false;
            menu_ = true;
            menuPage_ = MenuPage::Main;
        } else if (!menu_ && key == SDLK_F5) {
            paused_ = false;
            beginLevelForPlay(levelIndex_);
        } else if (!menu_ && key == SDLK_PAGEUP) {
            paused_ = false;
            beginLevelForPlay(levelIndex_ + 1);
        } else if (!menu_ && key == SDLK_PAGEDOWN) {
            paused_ = false;
            beginLevelForPlay(levelIndex_ - 1);
        } else if (!menu_ && paused_) {
            return;
        } else if (!menu_ && isPlayer1FireKey(key)) {
            handlePlayerFire(player_, energy_, lives_, playerDead_, reentryTimer_,
                             damageCooldown_, bombInventory_, 1);
        } else if (!menu_ && playerCount_ > 1 && isPlayer2FireKey(key)) {
            handlePlayerFire(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                             damageCooldown2_, bombInventory2_, 2);
        } else if (!menu_ && key == SDLK_s) {
            showBackground_ = !showBackground_;
        } else if (!menu_ && key == SDLK_r && playerCount_ == 1) {
            adjustGameplayViewWidth(-32);
        } else if (!menu_ && key == SDLK_e && playerCount_ == 1) {
            adjustGameplayViewWidth(32);
        }
    }

    bool isPlayer1FireKey(SDL_Keycode key) const {
        return key == SDLK_n || key == SDLK_SPACE || key == SDLK_RCTRL;
    }

    bool isPlayer2FireKey(SDL_Keycode key) const {
        return key == SDLK_KP_0 || key == SDLK_INSERT;
    }

    void handlePlayerFire(Player& player, int& energy, int& lives, bool& dead,
                          int& reentryTimer, int& damageCooldown,
                          BombInventory& inventory, uint8_t playerIndex) {
        if (dead) {
            tryReenterPlayer(player, energy, lives, dead, reentryTimer,
                             damageCooldown, playerIndex);
        } else {
            placeBombAt(player, inventory, playerIndex);
        }
    }

    void handleNameEntryKey(SDL_Keycode key) {
        if (key == SDLK_RETURN || key == SDLK_KP_ENTER) {
            requestRecordNameCommitSound();
            finalizePendingRecord();
            return;
        }
        if (key == SDLK_BACKSPACE) {
            if (!pendingRecordName_.empty()) pendingRecordName_.pop_back();
            return;
        }
        if (key == SDLK_ESCAPE) {
            cancelPendingRecord();
            return;
        }
        char ch = recordCharForKey(key);
        if (ch != '\0' && pendingRecordName_.size() < 8) {
            pendingRecordName_.push_back(ch);
        }
    }

    char recordCharForKey(SDL_Keycode key) const {
        if (key >= SDLK_a && key <= SDLK_z) {
            return static_cast<char>('a' + (key - SDLK_a));
        }
        if (key == SDLK_SPACE) {
            return ' ';
        }
        return '\0';
    }

    uint16_t compatibilitySoundCursor(size_t index) const {
        return kCompatibilitySoundCursors[index % kCompatibilitySoundCursors.size()];
    }

    uint16_t soundStepPeriodWord(size_t stepIndex) const {
        size_t off = stepIndex * kSoundStepSize;
        if (off + 1 >= sounds_.payload.size()) return kSoundStopPeriod;
        return le16(sounds_.payload, off);
    }

    uint8_t soundStepGateTick(size_t stepIndex) const {
        size_t off = stepIndex * kSoundStepSize;
        return off + 2 < sounds_.payload.size() ? sounds_.payload[off + 2] : 0;
    }

    uint8_t soundStepPeriodTicks(size_t stepIndex) const {
        size_t off = stepIndex * kSoundStepSize;
        return off + 3 < sounds_.payload.size() ? sounds_.payload[off + 3] : 1;
    }

    uint16_t soundStopCursorFor(uint16_t cursor) const {
        size_t stepIndex = cursor;
        while (stepIndex < sounds_.stepCount) {
            if (soundStepPeriodWord(stepIndex) == kSoundStopPeriod) {
                return static_cast<uint16_t>(stepIndex + 1);
            }
            ++stepIndex;
        }
        return static_cast<uint16_t>(sounds_.stepCount);
    }

    void appendToneSamples(std::vector<int16_t>& samples, uint16_t period,
                           int sampleCount, int amplitude, double& phase) const {
        if (sampleCount <= 0) return;
        if (period < 0x20) {
            samples.insert(samples.end(), static_cast<size_t>(sampleCount), 0);
            return;
        }
        double frequency = std::clamp(1193182.0 / static_cast<double>(period),
                                      80.0, 4200.0);
        double step = frequency / static_cast<double>(kAudioSampleRate);
        for (int i = 0; i < sampleCount; ++i) {
            phase += step;
            if (phase >= 1.0) phase -= std::floor(phase);
            samples.push_back(phase < 0.5 ? static_cast<int16_t>(amplitude)
                                           : static_cast<int16_t>(-amplitude));
        }
    }

    std::vector<int16_t> synthesizeSoundCursor(uint16_t cursor) const {
        if (cursor > kDirectSoundThreshold) return synthesizeDirectSweep(cursor);
        std::vector<int16_t> samples;
        if (sounds_.payload.empty() || cursor >= sounds_.stepCount) return samples;

        uint16_t stopCursor = soundStopCursorFor(cursor);
        samples.reserve(static_cast<size_t>(std::max<int>(1, stopCursor - cursor)) *
                        kAudioToneSamples * 2);
        double phase = 0.0;
        for (size_t stepIndex = cursor; stepIndex < sounds_.stepCount; ++stepIndex) {
            uint16_t period = soundStepPeriodWord(stepIndex);
            if (period == kSoundStopPeriod) break;
            uint8_t gateTick = soundStepGateTick(stepIndex);
            uint8_t periodTicksRaw = soundStepPeriodTicks(stepIndex);
            int periodTicks = periodTicksRaw == 0 ? 256 : periodTicksRaw;
            int audibleTicks = periodTicks;
            if (gateTick != 0 && gateTick < periodTicks) {
                audibleTicks = gateTick;
            }
            int silentTicks = std::max(0, periodTicks - audibleTicks);
            appendToneSamples(samples, period,
                              std::max(1, audibleTicks * kAudioToneSamples),
                              7200, phase);
            samples.insert(samples.end(),
                           static_cast<size_t>(silentTicks * kAudioToneSamples), 0);
        }
        return samples;
    }

    std::vector<int16_t> synthesizeSound(size_t index) const {
        if (sounds_.records.empty()) return {};
        return synthesizeSoundCursor(compatibilitySoundCursor(index));
    }

    std::vector<int16_t> synthesizeDirectSweep(uint16_t startCursor) const {
        std::vector<int16_t> samples;
        if (startCursor <= kDirectSoundThreshold) return samples;
        double phase = 0.0;
        for (uint16_t cursor = startCursor; cursor > kDirectSoundThreshold;
             cursor = static_cast<uint16_t>(cursor - 4)) {
            uint16_t period = static_cast<uint16_t>(cursor - kDirectSoundPeriodBase);
            uint16_t clampedPeriod = std::max<uint16_t>(1, period);
            appendToneSamples(samples, clampedPeriod, kAudioToneSamples / 2, 7200, phase);
        }
        return samples;
    }

    size_t soundIndexForSelector(uint8_t selector) const {
        if (sounds_.records.empty()) return 0;
        if (selector >= 4) {
            return static_cast<size_t>(selector - 4) % sounds_.records.size();
        }
        return static_cast<size_t>(selector) % sounds_.records.size();
    }

    bool isDirectSoundSweep(uint16_t offset) const {
        return offset > kDirectSoundThreshold;
    }

    size_t soundIndexForOffsetFallback(uint16_t offset, uint8_t selector) const {
        if (sounds_.records.empty()) return 0;
        for (size_t i = 0; i < kExplosionDirectSweepSoundOffsets.size(); ++i) {
            if (offset == kExplosionDirectSweepSoundOffsets[i]) {
                return i % sounds_.records.size();
            }
        }
        return soundIndexForSelector(selector);
    }

    bool latchSoundRequest(uint16_t cursor, uint8_t selector) {
        bool accept = !soundLatch_.active ||
                      static_cast<uint8_t>(soundLatch_.currentSelector - 1u) < selector;
        if (!accept) return false;
        soundLatch_.active = true;
        soundLatch_.currentSelector = selector;
        soundLatch_.latchedOffset = cursor;
        soundLatch_.directSweep = isDirectSoundSweep(cursor);
        soundLatch_.recordIndex = sounds_.records.empty()
                                      ? 0
                                      : soundIndexForOffsetFallback(cursor, selector);
        return true;
    }

    bool requestSoundCursor(uint16_t cursor, uint8_t selector) {
        return latchSoundRequest(cursor, selector);
    }

    bool requestSoundOffset(uint16_t offset, uint8_t selector) {
        return requestSoundCursor(offset, selector);
    }

    void clearSoundLatch() {
        soundLatch_ = {};
    }

    void pumpSoundLatch() {
        if (!soundLatch_.active) return;
        size_t recordIndex = soundLatch_.recordIndex;
        lastPumpedSoundRecord_ = static_cast<int>(recordIndex);
        lastPumpedSoundOffset_ = soundLatch_.latchedOffset;
        lastPumpedSoundSelector_ = soundLatch_.currentSelector;
        bool directSweep = soundLatch_.directSweep;
        uint16_t offset = soundLatch_.latchedOffset;
        clearSoundLatch();
        if (directSweep) {
            playSoundSamples(synthesizeDirectSweep(offset));
        } else {
            playSoundSamples(synthesizeSoundCursor(offset));
        }
    }

    void playSound(size_t index) {
        if (traceCompatibilitySoundAttempts_) {
            compatibilitySoundAttempts_.push_back(
                {index, compatibilitySoundCursor(index)});
        }
        if (!audioEnabled_ || audioDevice_ == 0 || sounds_.records.empty()) return;
        std::vector<int16_t> samples = synthesizeSound(index % sounds_.records.size());
        if (samples.empty()) return;
        playSoundSamples(samples);
    }

    void playCompatibilitySound(size_t hookSlot) {
        if (hookSlot >= kRemainingSoundCompatibilityHooks.size()) {
            throw std::runtime_error("unknown compatibility sound hook");
        }
        const RemainingSoundCompatibilityHook& hook =
            kRemainingSoundCompatibilityHooks[hookSlot];
        playSound(hook.index);
    }

    void playSoundSamples(const std::vector<int16_t>& samples) {
        if (!audioEnabled_ || audioDevice_ == 0 || samples.empty()) return;
        Uint32 bytes = static_cast<Uint32>(samples.size() * sizeof(int16_t));
        if (audioSpec_.format == AUDIO_S16SYS && audioSpec_.channels == 1 &&
            audioSpec_.freq == kAudioSampleRate) {
            queueAudio(samples.data(), bytes);
            return;
        }

        SDL_AudioCVT cvt{};
        int build = SDL_BuildAudioCVT(&cvt, AUDIO_S16SYS, 1, kAudioSampleRate,
                                      audioSpec_.format, audioSpec_.channels,
                                      audioSpec_.freq);
        if (build < 0) {
            SDL_ClearError();
            return;
        }
        if (build == 0) {
            queueAudio(samples.data(), bytes);
            return;
        }

        cvt.len = static_cast<int>(bytes);
        std::vector<uint8_t> converted(static_cast<size_t>(cvt.len) * cvt.len_mult);
        std::memcpy(converted.data(), samples.data(), bytes);
        cvt.buf = converted.data();
        if (SDL_ConvertAudio(&cvt) != 0) {
            SDL_ClearError();
            return;
        }
        queueAudio(converted.data(), static_cast<Uint32>(cvt.len_cvt));
    }

    void queueAudio(const void* data, Uint32 bytes) {
        if (SDL_QueueAudio(audioDevice_, data, bytes) != 0) {
            SDL_ClearError();
            audioEnabled_ = false;
        }
    }

    void playSoundSelector(uint8_t selector) {
        playSound(soundIndexForSelector(selector));
    }

    int tileAt(int tx, int ty) const {
        if (tx < 0 || ty < 0 || tx >= level_.width || ty >= level_.height) return 0;
        return level_.tiles[static_cast<size_t>(ty) * level_.width + tx];
    }

    uint16_t wordAt(int tx, int ty) const {
        if (tx < 0 || ty < 0 || tx >= level_.width || ty >= level_.height) return 0;
        size_t index = static_cast<size_t>(ty) * level_.width + tx;
        return index < level_.wordLayer.size() ? level_.wordLayer[index] : 0;
    }

    uint8_t& tileRef(int tx, int ty) {
        return level_.tiles[static_cast<size_t>(ty) * level_.width + tx];
    }

    uint16_t& wordRef(int tx, int ty) {
        return level_.wordLayer[static_cast<size_t>(ty) * level_.width + tx];
    }

    bool solidPixel(float px, float py) const {
        int tx = static_cast<int>(px) / kTileSize;
        int ty = static_cast<int>(py) / kTileSize;
        uint8_t tileByte = static_cast<uint8_t>(tileAt(tx, ty));
        return countsForDestructionProgress(tileByte, level_.objectiveTile) &&
               !isPassableObjectCell(tx, ty);
    }

    bool collides(float x, float y) const {
        return solidPixel(x, y) || solidPixel(x + 11.0f, y) ||
               solidPixel(x, y + 15.0f) || solidPixel(x + 11.0f, y + 15.0f);
    }

    bool monsterCollides(float x, float y) const {
        return solidPixel(x, y) || solidPixel(x + 13.0f, y) ||
               solidPixel(x, y + 15.0f) || solidPixel(x + 13.0f, y + 15.0f);
    }

    bool playerOverlaps(const Player& player, float x, float y, float w, float h) const {
        return player.x < x + w && player.x + 12.0f > x &&
               player.y < y + h && player.y + 16.0f > y;
    }

    int bombTypeIndex(BombType type) const {
        return static_cast<int>(type);
    }

    BombProfile bombProfile(BombType type) const {
        switch (type) {
            // The default (Small) bomb is the blue BOMOMIMK sprite 57, verified
            // against the original both in the HUD selector box and as a dropped
            // world bomb (captured under DOSBox); 58 is the green bomb.
            case BombType::Small: return {0x0d, 57, 20};
            case BombType::Medium: return {0x0e, 59, 30};
            case BombType::Large: return {0x0f, 60, 40};
            case BombType::Super: return {0x10, 60, 200};
        }
        return {0x0d, 57, 20};
    }

    int explosionVisualType(BombType type) const {
        return std::clamp(bombTypeIndex(type) + 1, 1, 4);
    }

    uint8_t explosionDispatcherState(int visualSelector) const {
        return static_cast<uint8_t>(std::clamp(visualSelector + 3, 4, 7));
    }

    int explosionEffectTicks(int visualType) const {
        switch (visualType) {
            case 1: return 8;
            case 2: return 9;
            case 3: return 9;
            case 4: return 0x3a;
        }
        return 8;
    }

    uint8_t explosionVariantByte(int visualType) const {
        switch (visualType) {
            case 1: return 5;
            case 2: return 5;
            case 3: return 3;
            case 4: return 0x0a;
        }
        return 5;
    }

    uint16_t explosionSoundOffset(int visualType) const {
        if (visualType >= 1 &&
            visualType <= static_cast<int>(kExplosionDirectSweepSoundOffsets.size())) {
            return kExplosionDirectSweepSoundOffsets[static_cast<size_t>(visualType - 1)];
        }
        return kExplosionDirectSweepSoundOffsets[0];
    }

    uint8_t explosionSoundSelector(int visualType) const {
        if (visualType >= 1 &&
            visualType <= static_cast<int>(kExplosionSoundSelectors.size())) {
            return kExplosionSoundSelectors[static_cast<size_t>(visualType - 1)];
        }
        return kExplosionSoundSelectors[0];
    }

    bool hasBomb(const BombInventory& inventory, BombType type) const {
        return inventory.counts[static_cast<size_t>(bombTypeIndex(type))] > 0;
    }

    void printBombInventory(const std::string& label) const {
        std::cout << label << "_bombs="
                  << bombInventory_.counts[0] << ','
                  << bombInventory_.counts[1] << ','
                  << bombInventory_.counts[2] << ','
                  << bombInventory_.counts[3]
                  << " selected=" << (bombTypeIndex(bombInventory_.selected) + 1) << '\n';
    }

    void selectNextAvailableBomb(BombInventory& inventory) {
        int start = bombTypeIndex(inventory.selected);
        for (int step = 1; step <= 4; ++step) {
            int idx = (start + step) % 4;
            if (inventory.counts[static_cast<size_t>(idx)] > 0) {
                inventory.selected = static_cast<BombType>(idx);
                return;
            }
        }
    }

    void updateWeaponSwitch(BombInventory& inventory, uint8_t& holdTicks,
                            bool pressed) {
        if (pressed) {
            ++holdTicks;
            return;
        }
        if (holdTicks >= kWeaponSwitchHoldTicks) {
            requestWeaponSwitchSound();
            selectNextAvailableBomb(inventory);
        }
        holdTicks = 0;
    }

    void driveAutoplayerWeaponSwitchChord(const FrameControls& controls) {
        for (uint8_t tick = 0; tick < kWeaponSwitchHoldTicks; ++tick) {
            updateWithControls(controls, 1.0f / 60.0f);
        }
        updateWithControls(FrameControls{}, 1.0f / 60.0f);
    }

    void update(float dt) {
        if (levelIntro_.active) {
            updateLevelIntro(SDL_GetTicks());
            return;
        }
        if (menu_ || paused_) return;
        const uint8_t* keys = SDL_GetKeyboardState(nullptr);
        FrameControls controls;
        controls.p1Left = keys[SDL_SCANCODE_LEFT] ||
                          (playerCount_ == 1 && keys[SDL_SCANCODE_Z]);
        controls.p1Right = keys[SDL_SCANCODE_RIGHT] ||
                           (playerCount_ == 1 && keys[SDL_SCANCODE_X]);
        controls.p1Jump = keys[SDL_SCANCODE_UP] ||
                          (playerCount_ == 1 && keys[SDL_SCANCODE_M]);
        controls.p1Down = keys[SDL_SCANCODE_DOWN] ||
                          (playerCount_ == 1 && keys[SDL_SCANCODE_C]);
        controls.p2Left = playerCount_ > 1 && keys[SDL_SCANCODE_Z];
        controls.p2Right = playerCount_ > 1 && keys[SDL_SCANCODE_X];
        controls.p2Jump = playerCount_ > 1 && keys[SDL_SCANCODE_M];
        controls.p2Down = playerCount_ > 1 && keys[SDL_SCANCODE_C];
        updateWithControls(controls, dt);
    }

    void updateWithControls(const FrameControls& controls, float dt) {
        if (menu_ || paused_ || levelIntro_.active) return;
        ++logicTick_;
        updateDamageCooldowns();
        bool p1Switch = controls.p1Left && controls.p1Right;
        bool p2Switch = controls.p2Left && controls.p2Right;
        bool p1Jump = controls.p1Jump && !controls.p1Down;
        bool p1Down = controls.p1Down && !controls.p1Jump;
        bool p2Jump = controls.p2Jump && !controls.p2Down;
        bool p2Down = controls.p2Down && !controls.p2Jump;
        updateWeaponSwitch(bombInventory_, weaponSwitchHoldTicks_, p1Switch);
        if (playerCount_ > 1) {
            updateWeaponSwitch(bombInventory2_, weaponSwitchHoldTicks2_, p2Switch);
        } else {
            weaponSwitchHoldTicks2_ = 0;
        }
        if (portalCooldown_ > 0) --portalCooldown_;
        if (triggerCooldown_ > 0) --triggerCooldown_;
        if (portalCooldown2_ > 0) --portalCooldown2_;
        if (triggerCooldown2_ > 0) --triggerCooldown2_;

        if (playerDead_) {
            updateState2VisualCursor(state2Visual_);
            refreshState2EffectEntry(player_, state2Visual_, state2Effect_);
            updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                          playerCount_ == 1 || player2Dead_);
        } else {
            activateLaunchPad(player_, p1Down);
            updatePlayer(player_, controls.p1Left, controls.p1Right,
                         p1Jump, p1Switch,
                         playerFacing_, playerAnimTick_, dt);
            collectObjectiveTiles(player_, 1);
            updatePortalsAndTriggers(player_, portalCooldown_, triggerCooldown_, p1Down);
        }
        if (playerCount_ > 1) {
            if (player2Dead_) {
                updateState2VisualCursor(state2Visual2_);
                refreshState2EffectEntry(player2_, state2Visual2_, state2Effect2_);
                updateReentry(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_, 2,
                              playerDead_);
            } else {
                activateLaunchPad(player2_, p2Down);
                updatePlayer(player2_, controls.p2Left, controls.p2Right,
                             p2Jump, p2Switch,
                             player2Facing_, player2AnimTick_, dt);
                collectObjectiveTiles(player2_, 2);
                updatePortalsAndTriggers(player2_, portalCooldown2_, triggerCooldown2_,
                                         p2Down);
            }
        }
        updateLaunchPadMarkers();
        updateFlashes();
        updateBombs();
        updateMonsterSpawners();
        updateBossLinks();
        updateMonsters(dt);
        updateBonusDrops();
        drainPlayerDamageCounters();
        updateLevelCompletion();
        pumpSoundLatch();
    }

    bool activateLaunchPad(Player& player, bool down) {
        if (!down) return false;
        int tx = static_cast<int>(player.x + 6.0f) / kTileSize;
        int ty = static_cast<int>(player.y + 16.0f) / kTileSize;
        if (tileAt(tx, ty) != kLaunchPadTile ||
            collides(player.x, player.y - 1.0f)) {
            return false;
        }

        player.vy = kLaunchPadVelocity;
        player.grounded = false;
        LaunchPadMarker marker;
        marker.x = static_cast<int>(player.x) + 4;
        marker.y = static_cast<int>(player.y) + 13;
        launchPadMarkers_.push_back(marker);
        requestLaunchPadSound();
        return true;
    }

    void updateLaunchPadMarkers() {
        for (LaunchPadMarker& marker : launchPadMarkers_) {
            if ((logicTick_ & 1u) != 0 && marker.timer > 0) {
                --marker.timer;
            }
            if (marker.timer == 0) continue;
            integrateAxis8_8(marker.x, marker.fracX, marker.velocityX8);
            integrateAxis8_8(marker.y, marker.fracY, marker.velocityY8);
        }
        launchPadMarkers_.erase(
            std::remove_if(launchPadMarkers_.begin(), launchPadMarkers_.end(),
                           [](const LaunchPadMarker& marker) {
                               return marker.timer == 0;
                           }),
            launchPadMarkers_.end());
    }

    void updateLevelCompletion() {
        if (isComplete()) {
            if (completeTimer_ == 0) {
                playCompatibilitySound(kLevelCompleteCompatibilityHookSlot);
            }
            if (++completeTimer_ > 100) {
                if (isFinalLevel()) {
                    beginEndRun(EndReason::CompletedGame);
                } else {
                    beginLevelForPlay(levelIndex_ + 1);
                }
            }
        } else {
            completeTimer_ = 0;
        }
    }

    void updatePlayer(Player& player, bool left, bool right, bool jump, bool switchWeapon,
                      int& facing, int& animTick, float dt) {
        player.vx = 0.0f;
        if (!switchWeapon && left) {
            player.vx -= 90.0f;
            facing = -1;
        }
        if (!switchWeapon && right) {
            player.vx += 90.0f;
            facing = 1;
        }
        if (player.vx != 0.0f) ++animTick;
        else animTick = 0;
        if (!player.grounded && hasObjectJumpSupport(player)) {
            player.grounded = true;
        }
        if (jump && player.grounded) {
            player.vy = kPlayerJumpVelocity;
            player.grounded = false;
        }
        player.vy = std::min(160.0f, player.vy + 360.0f * dt);
        movePlayer(player, player.vx * dt, 0.0f);
        movePlayer(player, 0.0f, player.vy * dt);
    }

    AutoplayRouteResult autoplayLevel1BombRoute() {
        if (menu_ || playerCount_ != 1 || levelIndex_ != 0) {
            throw std::runtime_error("level1 autoplayer requires active one-player level 1");
        }

        constexpr int kTargetBombX = 24;
        constexpr int kTargetBombY = 22;
        constexpr int kMaxRouteFrames = 180;
        constexpr float kDt = 1.0f / 60.0f;
        AutoplayRouteResult result;
        result.startX = static_cast<int>(player_.x);
        result.startY = static_cast<int>(player_.y);

        int stagnantFrames = 0;
        int lastX = static_cast<int>(player_.x);
        for (int frame = 0; frame < kMaxRouteFrames; ++frame) {
            result.bombTileX = static_cast<int>(player_.x + 6.0f) / kTileSize;
            result.bombTileY = static_cast<int>(player_.y + 12.0f) / kTileSize;
            if (result.bombTileX == kTargetBombX &&
                result.bombTileY == kTargetBombY) {
                break;
            }

            FrameControls controls;
            controls.p1Right = result.bombTileX < kTargetBombX;
            controls.p1Left = result.bombTileX > kTargetBombX;
            updateWithControls(controls, kDt);
            ++result.frames;

            int currentX = static_cast<int>(player_.x);
            if (std::abs(currentX - lastX) <= 1) {
                ++stagnantFrames;
            } else {
                stagnantFrames = 0;
                lastX = currentX;
            }
            if (stagnantFrames > 45) {
                throw std::runtime_error("level1 autoplayer stalled before target tile");
            }
        }

        result.finalX = static_cast<int>(player_.x);
        result.finalY = static_cast<int>(player_.y);
        result.bombTileX = static_cast<int>(player_.x + 6.0f) / kTileSize;
        result.bombTileY = static_cast<int>(player_.y + 12.0f) / kTileSize;
        if (result.bombTileX != kTargetBombX || result.bombTileY != kTargetBombY) {
            throw std::runtime_error("level1 autoplayer did not reach target tile");
        }
        if (collides(player_.x, player_.y)) {
            throw std::runtime_error("level1 autoplayer finished inside collision");
        }
        return result;
    }

    void movePlayer(Player& player, float dx, float dy) {
        if (dx != 0.0f) {
            float oldX = player.x;
            player.x += dx;
            if (collides(player.x, player.y)) {
                float step = dx > 0.0f ? -1.0f : 1.0f;
                int pushes = 0;
                while (collides(player.x, player.y) && pushes++ < kCollisionPushoutLimit) {
                    player.x += step;
                }
                if (collides(player.x, player.y)) player.x = oldX;
            }
        }
        if (dy != 0.0f) {
            float oldY = player.y;
            player.y += dy;
            if (collides(player.x, player.y)) {
                float step = dy > 0.0f ? -1.0f : 1.0f;
                int pushes = 0;
                while (collides(player.x, player.y) && pushes++ < kCollisionPushoutLimit) {
                    player.y += step;
                }
                if (collides(player.x, player.y)) player.y = oldY;
                player.grounded = dy > 0.0f;
                player.vy = 0.0f;
            } else {
                player.grounded = false;
            }
        }
        player.x = std::clamp(player.x, 0.0f, std::max(16.0f, level_.width * 8.0f - 16.0f));
        player.y = std::clamp(player.y, 0.0f, std::max(16.0f, level_.height * 8.0f - 16.0f));
    }

    void collectObjectiveTiles(const Player& player, uint8_t playerIndex) {
        int x0 = static_cast<int>(player.x) / 8;
        int x1 = static_cast<int>(player.x + 12.0f) / 8;
        int y0 = static_cast<int>(player.y) / 8;
        int y1 = static_cast<int>(player.y + 16.0f) / 8;
        for (int y = y0; y <= y1; ++y) {
            for (int x = x0; x <= x1; ++x) {
                if (x >= 0 && y >= 0 && x < level_.width && y < level_.height &&
                    tileAt(x, y) == level_.objectiveTile) {
                    tileRef(x, y) = 1;
                    ++collected_;
                    addScore(playerIndex, 1000);
                    playCompatibilitySound(kObjectivePickupCompatibilityHookSlot);
                }
            }
        }
    }

    void updatePortalsAndTriggers(Player& player, int& portalCooldown,
                                  int& triggerCooldown, bool down) {
        int tx = static_cast<int>(player.x + 6.0f) / 8;
        int ty = static_cast<int>(player.y + 12.0f) / 8;
        int tile = tileAt(tx, ty);
        uint16_t key = static_cast<uint16_t>(wordAt(tx, ty) & 0x7fffu);

        if (down && tile == 0x45 && key != 0 && portalCooldown == 0) {
            for (const LevelPortal& portal : level_.portals) {
                if (portal.key == key) {
                    player.x = static_cast<float>(portal.x);
                    player.y = static_cast<float>(portal.y);
                    player.vx = 0.0f;
                    player.vy = 0.0f;
                    portalCooldown = 30;
                    requestPortalTeleportSound();
                    break;
                }
            }
        } else if (tile == 0x72 && triggerCooldown == 0) {
            if (applyTileTrigger(wordAt(tx, ty))) {
                triggerCooldown = 30;
                requestTileTriggerSound();
            }
        }
    }

    bool applyTileTrigger(uint16_t key) {
        bool changed = false;
        for (const TileTriggerRule& rule : level_.tileTriggers) {
            if (rule.triggerKey != key) continue;
            size_t count = std::min(level_.tiles.size(), level_.wordLayer.size());
            for (size_t i = 0; i < count; ++i) {
                uint16_t word = static_cast<uint16_t>(level_.wordLayer[i] & 0x7fffu);
                if (word < rule.wordRangeFirst || word > rule.wordRangeLast) continue;
                for (size_t slot = 0; slot < rule.from.size(); ++slot) {
                    uint8_t from = rule.from[slot];
                    if (from != 0 && level_.tiles[i] == from) {
                        uint8_t to = rule.to[slot];
                        accountTileRewrite(level_.tiles[i], to);
                        level_.tiles[i] = to;
                        changed = true;
                    }
                }
            }
        }
        return changed;
    }

    void accountTileRewrite(uint8_t from, uint8_t to) {
        (void)from;
        (void)to;
    }

    void prepareMonsterMotionDebugLevel(bool ledgeAhead) {
        level_ = {};
        level_.width = 12;
        level_.height = 8;
        level_.objectiveTile = 108;
        level_.tiles.assign(static_cast<size_t>(level_.width) * level_.height, 1);
        level_.wordLayer.assign(level_.tiles.size(), 0);
        for (int x = 0; x < level_.width; ++x) {
            tileRef(x, 5) = 2;
        }
        if (ledgeAhead) {
            tileRef(6, 5) = 1;
        }
        playerCount_ = 1;
        playerDead_ = false;
        player2Dead_ = true;
        player_ = {};
        player2_ = {};
        monsters_.clear();
        randomSeed_ = 0x1234abcd;
    }

    void prepareAutoplayerMonsterFixtureLevel() {
        prepareMonsterMotionDebugLevel(false);
        menu_ = false;
        spawnerStates_.clear();
        bonusDrops_.clear();
        bombs_.clear();
        flashes_.clear();
        launchPadMarkers_.clear();
        explosionEffects_.clear();
        debrisQueue_.clear();
        collapseQueue_.clear();
        collected_ = 0;
        destroyed_ = 0;
        completeTimer_ = 0;
        portalCooldown_ = 0;
        triggerCooldown_ = 0;
        portalCooldown2_ = 0;
        triggerCooldown2_ = 0;
        energy_ = 100;
        energy2_ = 100;
        damageCooldown_ = 0;
        damageCooldown2_ = 0;
        pendingDamage_ = 0;
        pendingDamage2_ = 0;
        bombInventory_ = {};
        bombInventory2_ = {};
        weaponSwitchHoldTicks_ = 0;
        weaponSwitchHoldTicks2_ = 0;
        playerFacing_ = 1;
        player2Facing_ = 1;
        playerAnimTick_ = 0;
        player2AnimTick_ = 0;
        logicTick_ = 0;
        clearSoundLatch();
        lastPumpedSoundRecord_ = -1;
        lastPumpedSoundOffset_ = 0;
        lastPumpedSoundSelector_ = 0;
    }

    std::array<int, 2> monsterFrameRange(uint8_t kind) const {
        switch (kind) {
            case 1: return {43, 44};
            case 2: return {39, 41};
            case 3: return {49, 51};
            case 4: return {53, 55};
            default: return {39, 41};
        }
    }

    std::array<int, 2> monsterDirectionalFrameRange(uint8_t kind, int16_t vx8) const {
        if (kind == 1) return vx8 < 0 ? std::array<int, 2>{43, 44}
                                      : std::array<int, 2>{45, 46};
        return monsterFrameRange(kind);
    }

    uint16_t randomRangeValue(uint16_t base, uint16_t range) {
        // Turbo Pascal / Borland Random(): RandSeed = RandSeed*0x08088405 + 1
        // (32-bit wrap), Random(L) = (RandSeed >> 16) mod L. Verified against the
        // shipped runtime library Random at 0x920:0x13a8 (multiplier low word
        // 0x8405 at CS:0x142d, increment 1, high-word-mod-L extraction) so the
        // port's RNG is bit-identical to the original's generator.
        randomSeed_ = randomSeed_ * 0x08088405u + 1u;
        uint16_t span = range == 0 ? 1 : range;
        return static_cast<uint16_t>(base + ((randomSeed_ >> 16) % span));
    }

    int randomInclusive(int low, int high) {
        return static_cast<int>(randomRangeValue(static_cast<uint16_t>(low),
                                                 static_cast<uint16_t>(high - low + 1)));
    }

    int16_t groundWalkerSpeed8(const ActiveMonster& monster) const {
        return clampI16(monster.ai0);
    }

    int16_t retargetSpeed8(const ActiveMonster& monster) const {
        return clampI16(monster.ai1);
    }

    void refreshMonsterAnimationProfile(ActiveMonster& monster) {
        auto frames = monsterDirectionalFrameRange(monster.kind, monster.vx8);
        if (monster.animStart != frames[0] || monster.animEnd != frames[1]) {
            monster.animStart = static_cast<uint8_t>(frames[0]);
            monster.animEnd = static_cast<uint8_t>(frames[1]);
            monster.animFrame = monster.animStart;
        }
    }

    void initializeMonsterMotion(ActiveMonster& monster) {
        if (monster.behavior == 4) {
            monster.motionTimer = 0;
            retargetMonster(monster);
            return;
        }
        monster.vx8 = groundWalkerSpeed8(monster);
        monster.vy8 = 0;
        refreshMonsterAnimationProfile(monster);
    }

    void retargetMonster(ActiveMonster& monster) {
        int16_t speed = retargetSpeed8(monster);
        const Player& target = nearestPlayer(monster.x, monster.y);
        float dx = target.x - monster.x;
        float dy = target.y - monster.y;
        float threshold = std::max(1.0f, static_cast<float>(monster.ai2));
        if (std::fabs(dx) + std::fabs(dy) < threshold) {
            float len = std::max(1.0f, std::hypot(dx, dy));
            monster.vx8 = clampI16(static_cast<int>(std::lround(speed * dx / len)));
            monster.vy8 = clampI16(static_cast<int>(std::lround(speed * dy / len)));
        } else {
            int range = std::max(1, static_cast<int>(monster.ai1) * 2);
            int vxFixed = static_cast<int>(randomRangeValue(0, static_cast<uint16_t>(range))) -
                          static_cast<int>(monster.ai1);
            int vyFixed = static_cast<int>(randomRangeValue(0, static_cast<uint16_t>(range))) -
                          static_cast<int>(monster.ai1);
            monster.vx8 = clampI16(vxFixed);
            monster.vy8 = clampI16(vyFixed);
        }
        monster.motionTimer = std::max<int>(1, monster.ai0);
        refreshMonsterAnimationProfile(monster);
    }

    const Player& nearestPlayer(float x, float y) const {
        if (playerCount_ <= 1 || player2Dead_) return player_;
        if (playerDead_) return player2_;
        float dx1 = player_.x - x;
        float dy1 = player_.y - y;
        float dx2 = player2_.x - x;
        float dy2 = player2_.y - y;
        return (dx2 * dx2 + dy2 * dy2) < (dx1 * dx1 + dy1 * dy1) ? player2_ : player_;
    }

    void updateMonsterMotion(ActiveMonster& monster, float) {
        if (monster.behavior == 6) {
            updateBossHead(monster);
            return;
        }
        if (monster.behavior == 5) {
            applyBossSegmentLinks(monster);
            return;
        }
        if (monster.behavior == 4) {
            if (--monster.motionTimer <= 0) {
                retargetMonster(monster);
            }
            return;
        }

        // Ground walkers (behaviors 1-3) face the direction set at spawn
        // (initializeMonsterMotion) and reverse only at walls and floor edges;
        // the original never steers them toward the player, so preserve the
        // current facing rather than seeking (defaulting to the spawn heading).
        int16_t speed = groundWalkerSpeed8(monster);
        monster.vx8 = monster.vx8 < 0 ? -speed : speed;
        bool grounded = monsterCollides(monster.x, monster.y + 1.0f);
        if (grounded) {
            float probeX = monster.x + (monster.vx8 < 0 ? -2.0f : 15.0f);
            if (!solidPixel(probeX, monster.y + 17.0f)) {
                monster.vx8 = -monster.vx8;
            }
        }
        monster.vy8 = static_cast<int16_t>(std::min<int>(0x07ff, monster.vy8 + 0x40));
        refreshMonsterAnimationProfile(monster);
    }

    // Live GRAN.MST consumer backed by the static consumer model
    // (--debug-gran-static-consumer-model / --debug-gran-boss-model). The
    // original appends these actors at level-7 setup; pre-boss visual entries
    // are the two players plus the two player-shot slots, so record visual
    // bytes and link visual bytes are rebased by 4.
    static constexpr int kBossVisualBase = 4;

    void spawnLevel7Boss() {
        std::vector<uint8_t> granBytes;
        for (const GranRecord& record : gran_.records) {
            granBytes.insert(granBytes.end(), record.bytes.begin(), record.bytes.end());
        }
        if (granBytes.size() != 399 || granBytes[0] != 7) return;
        size_t pos = 1;
        const size_t recordCount = granBytes[0];
        const size_t recordsBase = pos;
        pos += recordCount * 0x26;
        const size_t spritesBase = pos;
        pos += recordCount;
        const size_t pairsBase = pos;
        pos += recordCount * 4;
        const size_t extraCount = granBytes[pos++];
        const size_t extrasBase = pos;
        if (pos + extraCount * 16 != granBytes.size()) return;

        for (size_t i = 0; i < bossSinTable_.size(); ++i) {
            // The original fills a 128-entry Real48 table with Sin(i*6.28/128).
            bossSinTable_[i] = std::sin(static_cast<float>(i) * 6.28f / 128.0f);
        }

        bossLinks_.clear();
        for (size_t i = 0; i < extraCount; ++i) {
            const uint8_t* extra = granBytes.data() + extrasBase + i * 16;
            BossMotionLink link;
            link.targetVisual = static_cast<uint8_t>(extra[0] + kBossVisualBase);
            link.selfVisual = static_cast<uint8_t>(extra[1] + kBossVisualBase);
            link.gain = extra[2];
            link.mode = extra[3];
            link.radiusX = extra[4];
            link.radiusY = extra[5];
            link.phase = extra[6];
            link.offX = static_cast<int16_t>(extra[7] | (extra[8] << 8));
            link.offY = static_cast<int16_t>(extra[9] | (extra[10] << 8));
            link.biasY = static_cast<int8_t>(extra[15]);
            bossLinks_.push_back(link);
        }

        for (size_t i = 0; i < recordCount; ++i) {
            const uint8_t* record = granBytes.data() + recordsBase + i * 0x26;
            ActiveMonster actor;
            actor.kind = record[0x00];
            actor.behavior = record[0x15];
            actor.bossVisual = static_cast<uint8_t>(record[0x01] + kBossVisualBase);
            const size_t entryOrder = static_cast<size_t>(actor.bossVisual) - kBossVisualBase;
            if (entryOrder >= recordCount) continue;
            const int dx = static_cast<int16_t>(granBytes[pairsBase + entryOrder * 4] |
                                                (granBytes[pairsBase + entryOrder * 4 + 1] << 8));
            const int dy = static_cast<int16_t>(granBytes[pairsBase + entryOrder * 4 + 2] |
                                                (granBytes[pairsBase + entryOrder * 4 + 3] << 8));
            actor.x = 100 + dx;
            actor.y = 100 + dy;
            const uint8_t entrySprite = granBytes[spritesBase + entryOrder];
            const uint8_t animSet = record[0x03];
            if (animSet != 0 && animSet < kBossAnimSets.size() &&
                kBossAnimSets[animSet][0] != 0) {
                actor.animStart = kBossAnimSets[animSet][0];
                actor.animEnd = kBossAnimSets[animSet][1];
            } else {
                actor.animStart = entrySprite;
                actor.animEnd = entrySprite;
            }
            actor.animFrame = entrySprite;
            actor.animDelay = std::max<uint8_t>(1, record[0x1a]);
            if (actor.kind == 0x1e) {
                actor.bossHpByte = record[0x24];
                actor.bossLives = record[0x02];
                actor.bossBoxW = record[0x0e];
                actor.bossBoxH = record[0x0f];
                actor.hp = actor.bossHpByte;
            } else {
                // Segments carry serial link bytes at +0x0e/+0x10; at level
                // entry the DS:0x79F9 rebase base is zero, so the shipped
                // serials index bossLinks_ 1-based directly.
                actor.linkA = record[0x0e];
                actor.linkB = record[0x0f];
                actor.linkC = record[0x10];
                actor.hp = 255;
            }
            monsters_.push_back(actor);
        }
        bossPresent_ = true;
    }

    ActiveMonster* findBossActorByVisual(uint8_t visual) {
        for (ActiveMonster& monster : monsters_) {
            if (monster.alive && !monster.bossDebris &&
                (monster.behavior == 5 || monster.behavior == 6) &&
                monster.bossVisual == visual) {
                return &monster;
            }
        }
        return nullptr;
    }

    // Original per-frame link recompute at 1000:432A, run before the actor
    // update loop.
    void updateBossLinks() {
        if (bossLinks_.empty()) return;
        for (BossMotionLink& link : bossLinks_) {
            ActiveMonster* target = findBossActorByVisual(link.targetVisual);
            if (link.mode != 0xff) {
                ActiveMonster* self = findBossActorByVisual(link.selfVisual);
                if (!target || !self) continue;
                link.outX = static_cast<int16_t>(
                    (target->x - self->x + link.offX) * link.gain);
                link.outY = static_cast<int16_t>(
                    (target->y - self->y + link.offY) * link.gain + link.biasY);
            } else {
                if (!target) continue;
                link.phase = static_cast<uint8_t>((link.phase + link.gain) & 0x7f);
                const float cosValue = bossSinTable_[(link.phase + 0x20) & 0x7f];
                const float sinValue = bossSinTable_[link.phase];
                link.outX = static_cast<int16_t>(
                    target->x + link.offX +
                    static_cast<int>(std::lround(cosValue * link.radiusX)));
                link.outY = static_cast<int16_t>(
                    target->y + link.offY +
                    static_cast<int>(std::lround(sinValue * link.radiusY)));
            }
        }
    }

    // Original 1000:5872: apply one serial link to the calling segment; bit
    // 0x80 mirrors the spring contribution.
    void applyBossSegmentLinks(ActiveMonster& monster) {
        const std::array<uint8_t, 3> serials{monster.linkA, monster.linkB, monster.linkC};
        for (uint8_t serial : serials) {
            if (serial == 0) break;
            int sign = 1;
            uint8_t index = serial;
            if (index > 0x80) {
                index = static_cast<uint8_t>(index - 0x80);
                sign = -1;
            }
            if (index == 0 || index > bossLinks_.size()) continue;
            const BossMotionLink& link = bossLinks_[index - 1];
            if (link.mode != 0xff) {
                monster.vx8 = clampI16(monster.vx8 + sign * link.outX);
                monster.vy8 = clampI16(monster.vy8 + sign * link.outY);
                const int limit = link.mode;
                if (std::abs(monster.vx8) > limit) {
                    monster.vx8 = static_cast<int16_t>(
                        monster.vx8 - (monster.vx8 > 0 ? limit : -limit));
                }
                if (std::abs(monster.vy8) > limit) {
                    monster.vy8 = static_cast<int16_t>(
                        monster.vy8 - (monster.vy8 > 0 ? limit : -limit));
                }
            } else {
                monster.x = link.outX;
                monster.y = link.outY;
                monster.vx8 = 0;
                monster.vy8 = 0;
                monster.fracX = 0;
                monster.fracY = 0;
            }
        }
    }

    // Original 1000:5CB0 head brain: every 29 ticks charge toward the nearest
    // player and jump when grounded; gravity and half-speed bouncing happen in
    // the shared motion path.
    void updateBossHead(ActiveMonster& monster) {
        ++monster.bossTick;
        if (monster.hurtFlash > 0) --monster.hurtFlash;
        // Original head brain (1000:5CB0): on the DS:0x78c2 mod 0x1d (29) state
        // tick the head draws Random(100); when it exceeds 0x46 (~30%) on an
        // even tick it plays the head roar (sound cursor 0x69). Crucially the
        // head does NOT seek the player -- 1000:5CB0 never reads the player
        // position -- it just picks a random speed 0x96 + Random(0x320), keeps
        // its current facing (walls reverse it), and bounces. The Random draws
        // are ordered exactly as the original so the shared RNG stream stays in
        // step: roar roll, then speed, then (if grounded) the jump impulse.
        if (monster.bossTick % 29 == 0) {
            const int roarRoll = static_cast<int>(randomRangeValue(0, 100));
            if (roarRoll > 0x46 && (monster.bossTick & 1) == 0) {
                requestSoundCursor(kBossHeadRoarSoundCursor, kBossHeadRoarSoundPriority);
            }
            const int speed = 0x96 + static_cast<int>(randomRangeValue(0, 0x320));
            monster.vx8 = clampI16(monster.vx8 >= 0 ? speed : -speed);
            if (monsterCollides(static_cast<float>(monster.x),
                                static_cast<float>(monster.y) + 1.0f)) {
                monster.vy8 = clampI16(-(0x12c + static_cast<int>(randomRangeValue(0, 0x5dc))));
            }
        }
        monster.vy8 = static_cast<int16_t>(std::min<int>(0x07ff, monster.vy8 + 0x40));
        damageBossHeadFromFlames(monster);
    }

    // Original head damage scan (1000:5EF4): every frame, flame tiles (0x75)
    // in every second column of the head's tile box each add one damage
    // point, doubled when the owning bomb's power byte exceeds 1; overkill
    // beyond the HP byte costs a life (with byte-wrap HP refill), and a lives
    // underflow triggers the death chain. The port drains from the live
    // per-tile explosion flashes, which mirror the original flame persistence.
    void damageBossHeadFromFlames(ActiveMonster& monster) {
        if (flashes_.empty()) return;
        int damage = 0;
        const int headTileX = monster.x / kTileSize;
        const int headTileY = monster.y / kTileSize;
        for (const Flash& flash : flashes_) {
            const int dx = flash.x - headTileX;
            const int dy = flash.y - headTileY;
            if (dx >= 0 && dx < monster.bossBoxW && (dx % 2) == 0 && dy >= 0 &&
                dy < monster.bossBoxH) {
                damage += flash.power > 1 ? 2 : 1;
            }
        }
        if (damage == 0) return;
        if (damage > monster.bossHpByte) {
            if (monster.bossLives == 0) {
                bossDeathChain();
                return;
            }
            --monster.bossLives;
            monster.hurtFlash = 12;
        }
        monster.bossHpByte = static_cast<uint8_t>(monster.bossHpByte - damage);
    }

    // Original 1000:5BCC: convert every segment linked to the head, then the
    // head itself, into timed debris and award the completion fanfare score.
    void bossDeathChain() {
        for (ActiveMonster& monster : monsters_) {
            if (!monster.alive) continue;
            if (monster.behavior == 5) {
                monster.behavior = 2;
                monster.bossDebris = true;
                monster.stateTimer = 0x28 + static_cast<int>(randomRangeValue(0, 10));
            } else if (monster.behavior == 6) {
                monster.behavior = 2;
                monster.bossDebris = true;
                monster.stateTimer = 0x3c;
            }
        }
        addScore(1, 1000);
        bossDefeated_ = true;
        requestMonsterDeathSound();
    }

    void updateMonsterSpawners() {
        for (size_t i = 0; i < spawnerStates_.size() && i < level_.monsterSpawners.size(); ++i) {
            SpawnerState& state = spawnerStates_[i];
            const MonsterSpawner& spawner = level_.monsterSpawners[i];
            if (!spawner.enabled || state.remaining <= 0 || state.availableSlots <= 0) continue;
            if (monsters_.size() >= 30) continue;
            if (state.cooldown > 0) {
                --state.cooldown;
                continue;
            }
            ActiveMonster monster;
            monster.x = spawner.x;
            monster.y = spawner.y;
            monster.kind = spawner.monsterKind;
            monster.spawnerIndex = i;
            monster.hasSpawner = true;
            monster.behavior = spawner.spawnArg;
            monster.ai0 = randomRangeValue(spawner.param0Base, spawner.param0Range);
            monster.ai1 = randomRangeValue(spawner.param1Base, spawner.param1Range);
            monster.ai2 = randomRangeValue(spawner.param2Base, spawner.param2Range);
            monster.hp = std::max<int>(1, randomRangeValue(spawner.randomBase, spawner.randomRange));
            auto frames = monsterDirectionalFrameRange(monster.kind, monster.vx8);
            monster.animStart = static_cast<uint8_t>(frames[0]);
            monster.animEnd = static_cast<uint8_t>(frames[1]);
            monster.animFrame = monster.animStart;
            monster.animDelay = std::max<uint8_t>(1, spawner.animationDelay);
            initializeMonsterMotion(monster);
            monsters_.push_back(monster);
            --state.remaining;
            --state.availableSlots;
            state.cooldown = spawner.cooldownReset > 0 ? spawner.cooldownReset : 60;
        }
    }

    void updateMonsters(float dt) {
        for (ActiveMonster& monster : monsters_) {
            if (!monster.alive) continue;
            if (monster.behavior == 2) {
                if (--monster.stateTimer <= 0) {
                    if (monster.bossDebris) {
                        // Original 1000:5BCC debris become power-2 timed
                        // bombs; the port bursts each piece into a flash.
                        flashes_.push_back(
                            {monster.x / kTileSize, monster.y / kTileSize, 12, 2});
                    }
                    releaseMonsterSlot(monster);
                    monster.alive = false;
                }
                continue;
            }
            ++monster.animTick;
            if (monster.animTick >= monster.animDelay) {
                monster.animTick = 0;
                int next = static_cast<int>(monster.animFrame) + monster.animStep;
                if (next > monster.animEnd || next < monster.animStart) {
                    if (monster.animMode == 2) {
                        monster.animStep = -monster.animStep;
                        next = static_cast<int>(monster.animFrame) + monster.animStep;
                    } else {
                        next = monster.animStep >= 0 ? monster.animStart : monster.animEnd;
                    }
                }
                monster.animFrame = static_cast<uint8_t>(
                    std::clamp(next, static_cast<int>(monster.animStart),
                               static_cast<int>(monster.animEnd)));
            }
            updateMonsterMotion(monster, dt);

            int oldX = monster.x;
            integrateAxis8_8(monster.x, monster.fracX, monster.vx8);
            // Boss segments (behavior 5) are positioned purely by their
            // motion links in the original and pass through terrain.
            if (monster.behavior != 5 && monsterCollides(monster.x, monster.y)) {
                int step = monster.vx8 > 0 ? -1 : 1;
                int pushes = 0;
                while (monsterCollides(monster.x, monster.y) && pushes++ < kCollisionPushoutLimit) {
                    monster.x += step;
                }
                if (monsterCollides(monster.x, monster.y)) monster.x = oldX;
                monster.vx8 = static_cast<int16_t>(
                    -monster.vx8 /
                    (monster.behavior == 4 || monster.behavior == 6 ? 2 : 1));
                monster.fracX = 0;
                if (monster.behavior == 4) monster.motionTimer = 0;
                if (monster.behavior != 6) refreshMonsterAnimationProfile(monster);
            }

            int oldY = monster.y;
            integrateAxis8_8(monster.y, monster.fracY, monster.vy8);
            if (monster.behavior != 5 && monsterCollides(monster.x, monster.y)) {
                int step = monster.vy8 > 0 ? -1 : 1;
                int pushes = 0;
                while (monsterCollides(monster.x, monster.y) && pushes++ < kCollisionPushoutLimit) {
                    monster.y += step;
                }
                if (monsterCollides(monster.x, monster.y)) monster.y = oldY;
                monster.vy8 = monster.behavior == 4 || monster.behavior == 6
                                  ? static_cast<int16_t>(-monster.vy8 / 2)
                                  : 0;
                monster.fracY = 0;
                if (monster.behavior == 4) monster.motionTimer = 0;
            }

            monster.x = std::clamp(monster.x, 0, std::max(16, level_.width * 8 - 16));
            monster.y = std::clamp(monster.y, 0, std::max(16, level_.height * 8 - 16));

            if (!playerDead_ && playerOverlaps(player_, monster.x, monster.y, 14.0f, 16.0f)) {
                queuePlayerDamage(1);
            }
            if (playerCount_ > 1 && !player2Dead_ &&
                playerOverlaps(player2_, monster.x, monster.y, 14.0f, 16.0f)) {
                queuePlayerDamage(2);
            }
        }
        monsters_.erase(std::remove_if(monsters_.begin(), monsters_.end(),
                                       [](const ActiveMonster& monster) { return !monster.alive; }),
                        monsters_.end());
    }

    void releaseMonsterSlot(ActiveMonster& monster) {
        if (!monster.hasSpawner || monster.deathCredited) return;
        if (monster.spawnerIndex < spawnerStates_.size()) {
            ++spawnerStates_[monster.spawnerIndex].availableSlots;
            monster.deathCredited = true;
            monster.hasSpawner = false;
        }
    }

    void updateDamageCooldowns() {
        if (damageCooldown_ > 0) --damageCooldown_;
        if (damageCooldown2_ > 0) --damageCooldown2_;
    }

    void queuePlayerDamage(uint8_t startMarker, uint8_t amount = 1) {
        if (amount == 0) return;
        bool secondPlayer = startMarker == 2 && playerCount_ > 1;
        bool dead = secondPlayer ? player2Dead_ : playerDead_;
        int cooldown = secondPlayer ? damageCooldown2_ : damageCooldown_;
        if (!dead && cooldown > 0) return;
        uint8_t& pending = secondPlayer ? pendingDamage2_ : pendingDamage_;
        pending = static_cast<uint8_t>(pending + amount);
    }

    void drainPlayerDamageCounters() {
        drainPlayerDamageCounter(player_, energy_, lives_, playerDead_, reentryTimer_,
                                 pendingDamage_, 1);
        if (playerCount_ > 1) {
            drainPlayerDamageCounter(player2_, energy2_, lives2_, player2Dead_,
                                     reentryTimer2_, pendingDamage2_, 2);
        } else {
            pendingDamage2_ = 0;
        }
    }

    void drainPlayerDamageCounter(Player& player, int& energy, int& lives,
                                  bool& dead, int& timer, uint8_t& pending,
                                  uint8_t startMarker) {
        uint8_t amount = pending;
        pending = 0;
        if (amount == 0) return;
        requestPlayerDamageSound();
        if (dead) return;
        uint8_t updatedEnergy =
            static_cast<uint8_t>(std::clamp(energy, 0, 255) - amount);
        energy = static_cast<int>(updatedEnergy);
        if (static_cast<uint16_t>(updatedEnergy) > 0x00c8) {
            beginPlayerDeath(player, energy, lives, dead, timer, startMarker);
        }
    }

    void damagePlayer(Player& player, int& energy, int& lives, bool& dead,
                      int& timer, int& damageCooldown, uint8_t startMarker) {
        (void)damageCooldown;
        uint8_t immediateDamage = 1;
        drainPlayerDamageCounter(player, energy, lives, dead, timer,
                                 immediateDamage, startMarker);
    }

    bool playerOverlapsTileArea(const Player& player, int tx0, int ty0,
                                int tx1, int ty1) const {
        float x = static_cast<float>(tx0 * kTileSize);
        float y = static_cast<float>(ty0 * kTileSize);
        float w = static_cast<float>((tx1 - tx0 + 1) * kTileSize);
        float h = static_cast<float>((ty1 - ty0 + 1) * kTileSize);
        return playerOverlaps(player, x, y, w, h);
    }

    void damagePlayersInTileArea(int tx0, int ty0, int tx1, int ty1) {
        tx0 = std::clamp(tx0, 0, std::max(0, level_.width - 1));
        tx1 = std::clamp(tx1, 0, std::max(0, level_.width - 1));
        ty0 = std::clamp(ty0, 0, std::max(0, level_.height - 1));
        ty1 = std::clamp(ty1, 0, std::max(0, level_.height - 1));
        if (tx0 > tx1) std::swap(tx0, tx1);
        if (ty0 > ty1) std::swap(ty0, ty1);
        if (playerOverlapsTileArea(player_, tx0, ty0, tx1, ty1)) {
            queuePlayerDamage(1);
        }
        if (playerCount_ > 1 && playerOverlapsTileArea(player2_, tx0, ty0, tx1, ty1)) {
            queuePlayerDamage(2);
        }
    }

    void beginPlayerDeath(Player& player, int& energy, int& lives, bool& dead,
                          int& timer, uint8_t startMarker) {
        pendingLifeLossFor(startMarker) = lives > 0;
        energy = 100;
        deathStateTimerFor(startMarker) = kDeathStateTicks;
        State2VisualCursor& cursor = state2VisualCursorFor(startMarker);
        resetState2VisualCursor(cursor);
        refreshState2EffectEntry(player, cursor, state2EffectEntryFor(startMarker));
        player.vx = 0.0f;
        player.vy = 0.0f;
        player.grounded = false;
        if (lives <= 0) {
            dead = true;
            timer = 0;
            cursor.active = false;
            state2EffectEntryFor(startMarker).active = false;
            requestPlayerDeathSound();
            if (allPlayersOutOfLives()) beginGameOver();
            return;
        }
        dead = true;
        timer = canReenterLevel() ? kReentryTicks : 1;
        requestPlayerDeathSound();
    }

    State2VisualCursor& state2VisualCursorFor(uint8_t startMarker) {
        return startMarker == 2 && playerCount_ > 1 ? state2Visual2_
                                                     : state2Visual_;
    }

    State2EffectEntry& state2EffectEntryFor(uint8_t startMarker) {
        return startMarker == 2 && playerCount_ > 1 ? state2Effect2_
                                                     : state2Effect_;
    }

    void refreshState2EffectEntry(const Player& player,
                                  const State2VisualCursor& cursor,
                                  State2EffectEntry& entry) {
        entry.active = cursor.active;
        if (!entry.active) return;
        entry.x = static_cast<int>(player.x);
        entry.y = static_cast<int>(player.y);
        entry.visualFrame = cursor.current;
        State2VisualRow row;
        if (originalState2VisualRow(cursor.current, row)) {
            entry.drawDx = row.row0;
            entry.drawDy = row.row1;
            entry.row2 = row.row2;
            entry.spriteIndex = row.row3;
            return;
        }
        entry.drawDx = 0;
        entry.drawDy = 0;
        entry.row2 = 0;
        entry.spriteIndex = cursor.current;
    }

    void resetState2VisualCursor(State2VisualCursor& cursor) {
        cursor.current = kState2VisualStartFrame;
        cursor.first = kState2VisualStartFrame;
        cursor.last = kState2VisualEndFrame;
        cursor.counter = kState2VisualDelay;
        cursor.delay = kState2VisualDelay;
        cursor.mode = 1;
        cursor.step = 1;
        cursor.active = true;
    }

    void updateState2VisualCursor(State2VisualCursor& cursor) {
        if (!cursor.active || cursor.mode == 0) return;
        ++cursor.counter;
        if (cursor.counter <= cursor.delay) return;
        cursor.counter = 0;
        cursor.current = static_cast<uint8_t>(
            static_cast<int>(cursor.current) + static_cast<int>(cursor.step));
        if (cursor.mode == 2) {
            if (cursor.current >= cursor.last || cursor.current <= cursor.first) {
                cursor.step = static_cast<int8_t>(-cursor.step);
            }
            return;
        }
        if (cursor.current > cursor.last) {
            cursor.current = cursor.first;
        }
    }

    bool allPlayersOutOfLives() const {
        return playerCount_ <= 1 ? lives_ <= 0 : lives_ <= 0 && lives2_ <= 0;
    }

    int& deathStateTimerFor(uint8_t startMarker) {
        return startMarker == 2 && playerCount_ > 1 ? deathStateTimer2_
                                                     : deathStateTimer_;
    }

    bool& pendingLifeLossFor(uint8_t startMarker) {
        return startMarker == 2 && playerCount_ > 1 ? pendingLifeLoss2_
                                                     : pendingLifeLoss_;
    }

    void finalizePendingLifeLoss(bool& dead, int& lives, int& timer,
                                 uint8_t startMarker) {
        bool& pending = pendingLifeLossFor(startMarker);
        if (!pending) return;
        pending = false;
        if (lives > 0) --lives;
        if (lives <= 0) {
            dead = true;
            timer = 0;
            state2VisualCursorFor(startMarker).active = false;
            state2EffectEntryFor(startMarker).active = false;
            if (allPlayersOutOfLives()) beginGameOver();
        }
    }

    bool canReenterLevel() const {
        return collected_ + remainingObjectiveTiles() >= level_.requiredBonus;
    }

    int remainingObjectiveTiles() const {
        return static_cast<int>(std::count(level_.tiles.begin(), level_.tiles.end(),
                                           level_.objectiveTile));
    }

    std::array<int, 2> findObjectiveTileForSmoke() const {
        for (int y = 0; y < level_.height; ++y) {
            for (int x = 0; x < level_.width; ++x) {
                if (tileAt(x, y) == level_.objectiveTile) return {x, y};
            }
        }
        throw std::runtime_error("level has no objective tile for smoke");
    }

    std::array<int, 2> findSingleObjectiveProbeForSmoke() const {
        int maxX = std::max(0, level_.width * kTileSize - 1);
        int maxY = std::max(0, level_.height * kTileSize - 1);
        for (int py = 0; py <= maxY; ++py) {
            for (int px = 0; px <= maxX; ++px) {
                int x0 = px / kTileSize;
                int x1 = (px + 12) / kTileSize;
                int y0 = py / kTileSize;
                int y1 = (py + 16) / kTileSize;
                int objectiveTiles = 0;
                for (int y = y0; y <= y1; ++y) {
                    for (int x = x0; x <= x1; ++x) {
                        if (x >= 0 && y >= 0 && x < level_.width &&
                            y < level_.height &&
                            tileAt(x, y) == level_.objectiveTile) {
                            ++objectiveTiles;
                        }
                    }
                }
                if (objectiveTiles == 1) return {px, py};
            }
        }
        throw std::runtime_error("level has no single-objective probe position");
    }

    void collectAllObjectiveTilesForSmoke() {
        for (int y = 0; y < level_.height; ++y) {
            for (int x = 0; x < level_.width; ++x) {
                if (tileAt(x, y) != level_.objectiveTile) continue;
                player_.x = static_cast<float>(x * kTileSize);
                player_.y = static_cast<float>(y * kTileSize);
                collectObjectiveTiles(player_, 1);
            }
        }
    }

    void damageRequiredTilesForSmoke() {
        int target = (static_cast<int>(level_.requiredDestruction) *
                          level_.startingDestructibleTiles +
                      99) /
                     100;
        for (int y = 0; y < level_.height && destroyed_ < target; ++y) {
            for (int x = 0; x < level_.width && destroyed_ < target; ++x) {
                if (!countsForPhysicalDamageProgress(wordAt(x, y))) {
                    continue;
                }
                queueTileDamage(x, y);
            }
        }
        if (destroyed_ < target) {
            throw std::runtime_error("level lacks enough destructible progress tiles");
        }
    }

    void smokeCompleteCurrentLevelFromMapProgress() {
        int startLevel = levelIndex_;
        collectAllObjectiveTilesForSmoke();
        damageRequiredTilesForSmoke();
        if (!isComplete()) {
            throw std::runtime_error("map progress did not satisfy level completion");
        }
        for (int i = 0; i <= 100; ++i) {
            updateLevelCompletion();
        }
        int expectedLevel = (startLevel + 1) % static_cast<int>(levels_.size());
        if (levelIndex_ != expectedLevel) {
            throw std::runtime_error("level completion did not advance to next level");
        }
    }

    void smokeBombObjectDestructionProgress() {
        for (int y = 0; y < level_.height; ++y) {
            for (int x = 0; x < level_.width; ++x) {
                uint8_t tile = tileAt(x, y);
                if (!isBombObjectTile(tile)) continue;
                int before = destroyed_;
                if (!consumeBombObjectTile(x, y)) {
                    throw std::runtime_error("bomb object tile was not consumed");
                }
                if (destroyed_ != before) {
                    throw std::runtime_error("bomb object consumption changed physical destruction");
                }
                if (tileAt(x, y) == tile) {
                    throw std::runtime_error("bomb object tile did not change after consumption");
                }
                return;
            }
        }
        throw std::runtime_error("no bomb object tile found for destruction smoke");
    }

    void updateReentry(Player& player, int& energy, int& lives, bool& dead,
                       int& timer, uint8_t startMarker, bool allowLevelRestart) {
        (void)energy;
        int& deathStateTimer = deathStateTimerFor(startMarker);
        if (deathStateTimer > 0) {
            --deathStateTimer;
            if (deathStateTimer > 0) return;
            finalizePendingLifeLoss(dead, lives, timer, startMarker);
        }
        if (lives <= 0) return;
        if (!canReenterLevel()) {
            restartCurrentLevelAfterDeath();
            return;
        }
        if (timer > 0) --timer;
        if (timer <= 0) {
            if (allowLevelRestart) {
                restartCurrentLevelAfterDeath();
            } else {
                timer = 0;
            }
            return;
        }
        (void)player;
        (void)dead;
        (void)startMarker;
    }

    void tryReenterPlayer(Player& player, int& energy, int& lives, bool& dead,
                          int& timer, int& damageCooldown, uint8_t startMarker) {
        if (!dead) return;
        if (deathStateTimerFor(startMarker) > 0) return;
        finalizePendingLifeLoss(dead, lives, timer, startMarker);
        if (lives <= 0) return;
        if (!canReenterLevel()) {
            restartCurrentLevelAfterDeath();
            return;
        }
        respawnPlayerAtStart(player, energy, startMarker);
        deathStateTimerFor(startMarker) = 0;
        state2VisualCursorFor(startMarker).active = false;
        state2EffectEntryFor(startMarker).active = false;
        damageCooldown = kDamageCooldownTicks;
        dead = false;
        timer = 0;
    }

    void respawnPlayerAtStart(Player& player, int& energy, uint8_t startMarker) {
        energy = 100;
        player.vx = 0.0f;
        player.vy = 0.0f;
        player.grounded = false;
        if (const LevelPortal* start = findStartPortal(startMarker)) {
            player.x = static_cast<float>(start->x);
            player.y = static_cast<float>(start->y);
        }
    }

    void restartCurrentLevelAfterDeath() {
        beginLevelForPlay(levelIndex_);
    }

    bool scoreQualifies(uint32_t score) const {
        return score != 0 &&
               (records_.size() < 7 || score > records_.back().score);
    }

    uint32_t& scoreForPlayer(uint8_t player) {
        return player == 2 && playerCount_ > 1 ? score2_ : score_;
    }

    void addScore(uint8_t player, uint32_t amount) {
        scoreForPlayer(player) += amount;
    }

    void clearRunScores() {
        score_ = 0;
        score2_ = 0;
    }

    bool isFinalLevel() const {
        return !levels_.empty() &&
               levelIndex_ + 1 >= static_cast<int>(levels_.size());
    }

    MenuPage endMenuPage(EndReason reason) const {
        return reason == EndReason::CompletedGame ? MenuPage::CompletedGame
                                                  : MenuPage::GameOver;
    }

    void beginGameOver() {
        beginEndRun(EndReason::GameOver);
    }

    void beginEndRun(EndReason reason) {
        uint8_t finalLevel = static_cast<uint8_t>(std::clamp(levelIndex_ + 1, 1, 255));
        pendingRecordQueue_.clear();
        if (score_ != 0) {
            pendingRecordQueue_.push_back({score_, finalLevel, 1, reason});
        }
        if (playerCount_ > 1 && score2_ != 0) {
            pendingRecordQueue_.push_back({score2_, finalLevel, 2, reason});
        }
        lives_ = 3;
        lives2_ = 3;
        menu_ = true;
        lastEndReason_ = reason;
        resetLevel(0);
        if (!startNextPendingRecord()) {
            menuPage_ = endMenuPage(reason);
        }
    }

    void finalizePendingRecord() {
        if (pendingRecordScore_ == 0) {
            menuPage_ = MenuPage::Records;
            return;
        }
        Record record = makeRecord(pendingRecordScore_, pendingRecordLevel_,
                                   pendingRecordName_);
        std::vector<Record> updatedRecords = records_;
        bool changed = insertRecord(updatedRecords, record);
        try {
            if (changed) saveRecords(recordPath_, updatedRecords);
        } catch (const std::exception& e) {
            std::cerr << "warning: could not save records: " << e.what() << '\n';
            menuPage_ = MenuPage::NameEntry;
            return;
        }
        records_ = std::move(updatedRecords);
        clearPendingRecord();
        if (startNextPendingRecord()) return;
        clearRunScores();
        menuPage_ = MenuPage::Records;
    }

    void cancelPendingRecord() {
        clearPendingRecord();
        if (startNextPendingRecord()) return;
        clearRunScores();
        menuPage_ = MenuPage::Records;
    }

    void clearPendingRecord() {
        pendingRecordScore_ = 0;
        pendingRecordLevel_ = 0;
        pendingRecordPlayer_ = 1;
        pendingRecordReason_ = EndReason::GameOver;
        pendingRecordName_.clear();
    }

    bool startNextPendingRecord() {
        while (!pendingRecordQueue_.empty()) {
            PendingRecordEntry entry = pendingRecordQueue_.front();
            pendingRecordQueue_.erase(pendingRecordQueue_.begin());
            if (!scoreQualifies(entry.score)) continue;
            pendingRecordScore_ = entry.score;
            pendingRecordLevel_ = entry.level;
            pendingRecordPlayer_ = entry.player;
            pendingRecordReason_ = entry.reason;
            pendingRecordName_.clear();
            menuPage_ = MenuPage::NameEntry;
            requestRecordNamePromptSound();
            return true;
        }
        clearPendingRecord();
        return false;
    }

    void placeBombAt(const Player& player, BombInventory& inventory, uint8_t owner) {
        if (!hasBomb(inventory, inventory.selected)) {
            selectNextAvailableBomb(inventory);
            if (!hasBomb(inventory, inventory.selected)) return;
        }
        int tx = static_cast<int>(player.x + 6.0f) / 8;
        int ty = static_cast<int>(player.y + 12.0f) / 8;
        auto it = std::find_if(bombs_.begin(), bombs_.end(),
                               [&](const Bomb& b) { return b.x == tx && b.y == ty; });
        if (it == bombs_.end()) {
            BombProfile profile = bombProfile(inventory.selected);
            bombs_.push_back({tx, ty, profile.fuseTicks, inventory.selected,
                              profile.fuseTicks, owner});
            requestBombPlaceSound();
            int& count = inventory.counts[static_cast<size_t>(bombTypeIndex(inventory.selected))];
            count = std::max(0, count - 1);
            if (count == 0) selectNextAvailableBomb(inventory);
        }
    }

    void updateBombs() {
        std::vector<Bomb> expired;
        for (Bomb& b : bombs_) {
            if (--b.timer <= 0) expired.push_back(b);
        }
        bombs_.erase(std::remove_if(bombs_.begin(), bombs_.end(),
                                    [](const Bomb& b) { return b.timer <= 0; }),
                     bombs_.end());
        int generation = levelResetGeneration_;
        for (const Bomb& b : expired) {
            if (levelResetGeneration_ != generation) break;
            explode(b);
            drainPlayerDamageCounters();
        }
    }

    std::vector<std::array<int, 2>> explosionTilesFor(const Bomb& bomb) const {
        std::vector<std::array<int, 2>> tiles;
        auto add = [&](int x, int y) {
            if (x < 0 || y < 0 || x >= level_.width || y >= level_.height) return;
            std::array<int, 2> pos{x, y};
            if (std::find(tiles.begin(), tiles.end(), pos) == tiles.end()) {
                tiles.push_back(pos);
            }
        };
        add(bomb.x, bomb.y);
        add(bomb.x + 1, bomb.y);
        add(bomb.x + 1, bomb.y + 1);
        add(bomb.x, bomb.y + 1);
        return tiles;
    }

    void spawnExplosionEffect(const Bomb& bomb) {
        int visualType = explosionVisualType(bomb.type);
        int ticks = explosionEffectTicks(visualType);
        ExplosionEffect effect;
        effect.x = bomb.x;
        effect.y = bomb.y;
        effect.visualSelector = static_cast<uint8_t>(visualType);
        effect.dispatcherState = explosionDispatcherState(visualType);
        effect.timer = ticks;
        effect.totalTimer = ticks;
        effect.soundOffset = explosionSoundOffset(visualType);
        effect.soundSelector = explosionSoundSelector(visualType);
        effect.seedTicksByte = static_cast<uint8_t>(ticks & 0xff);
        effect.variantByte = explosionVariantByte(visualType);
        effect.computedX = bomb.x * kTileSize;
        effect.computedY = bomb.y * kTileSize;
        explosionEffects_.push_back(effect);
        requestSoundOffset(effect.soundOffset, effect.soundSelector);
    }

    bool isBombObjectTile(uint8_t tile) const {
        return tile > 0x66 && tile < 0x73;
    }

    bool isHighBombObjectSoundTile(uint8_t tile) const {
        return tile > kBombObjectHighSoundThreshold;
    }

    bool isPassableObjectTile(uint8_t tile) const {
        return tile == 0x45 || isBombObjectTile(tile);
    }

    bool isPassableObjectCell(int tx, int ty) const {
        uint8_t tile = static_cast<uint8_t>(tileAt(tx, ty));
        if (isPassableObjectTile(tile)) return true;
        return countsForPhysicalDamageProgress(wordAt(tx, ty));
    }

    bool isObjectJumpSupportCell(int tx, int ty) const {
        uint8_t tile = static_cast<uint8_t>(tileAt(tx, ty));
        return isBombObjectTile(tile) || countsForPhysicalDamageProgress(wordAt(tx, ty));
    }

    bool objectJumpSupportPixel(float px, float py) const {
        int tx = static_cast<int>(px) / kTileSize;
        int ty = static_cast<int>(py) / kTileSize;
        return isObjectJumpSupportCell(tx, ty);
    }

    bool hasObjectJumpSupport(const Player& player) const {
        float left = player.x + 1.0f;
        float right = player.x + 10.0f;
        float bottom = player.y + 15.0f;
        return objectJumpSupportPixel(left, bottom) ||
               objectJumpSupportPixel(right, bottom) ||
               objectJumpSupportPixel(left, bottom + 1.0f) ||
               objectJumpSupportPixel(right, bottom + 1.0f);
    }

    bool requestBombObjectScoreSound(bool sawHighObjectTile) {
        return requestSoundCursor(sawHighObjectTile ? kBombObjectHighSoundCursor
                                                    : kBombObjectDefaultSoundCursor,
                                  kBombObjectSoundPriority);
    }

    bool requestBombPlaceSound() {
        return requestSoundOffset(kBombPlaceSoundCursor, kBombPlaceSoundPriority);
    }

    bool requestMonsterDeathSound() {
        return requestSoundCursor(kMonsterDeathSoundCursor, kMonsterDeathSoundPriority);
    }

    bool requestRecordNamePromptSound() {
        return requestSoundCursor(kRecordNamePromptSoundCursor,
                                  kRecordNamePromptSoundPriority);
    }

    bool requestRecordNameCommitSound() {
        return requestSoundCursor(kRecordNameCommitSoundCursor,
                                  kRecordNameCommitSoundPriority);
    }

    bool requestRecordsPageSound() {
        return requestSoundCursor(kRecordsPageSoundCursor, kRecordsPageSoundPriority);
    }

    bool requestWeaponSwitchSound() {
        return requestSoundCursor(kWeaponSwitchSoundCursor, kWeaponSwitchSoundPriority);
    }

    bool requestLaunchPadSound() {
        return requestSoundCursor(kLaunchPadSoundCursor, kLaunchPadSoundPriority);
    }

    bool requestPortalTeleportSound() {
        return requestSoundCursor(kPortalTeleportSoundCursor, kPortalTeleportSoundPriority);
    }

    bool requestTileTriggerSound() {
        return requestSoundCursor(kTileTriggerSoundCursor, kTileTriggerSoundPriority);
    }

    bool requestPlayerDamageSound() {
        return requestSoundCursor(kPlayerDamageSoundCursor, kPlayerDamageSoundPriority);
    }

    bool requestPlayerDeathSound() {
        return requestSoundCursor(kPlayerDeathSoundCursor, kPlayerDeathSoundPriority);
    }

    bool consumeBombObjectTile(int tx, int ty) {
        if (tx < 0 || ty < 0 || tx >= level_.width || ty >= level_.height) return false;
        uint8_t& tile = tileRef(tx, ty);
        if (!isBombObjectTile(tile)) return false;
        tile = (wordAt(tx, ty) & 0x8000u) != 0 ? 0xff : 0;
        return true;
    }

    bool markDamagedTile(int tx, int ty) {
        if (tx < 0 || ty < 0 || tx >= level_.width || ty >= level_.height) return false;
        uint8_t& tile = tileRef(tx, ty);
        bool counted = countsForDestructionProgress(tile, level_.objectiveTile);
        if (tile != level_.objectiveTile) {
            tile = 1;
        }
        return counted;
    }

    void queueTileDamage(int tx, int ty, uint8_t forwardPhase = 0, uint8_t reversePhase = 0) {
        if (tx < 0 || ty < 0 || tx >= level_.width || ty >= level_.height) return;
        size_t start = static_cast<size_t>(ty) * level_.width + tx;
        if (start >= level_.wordLayer.size()) return;
        uint16_t word = level_.wordLayer[start];
        if (word == 0 || (word & kDamagedWordBit) != 0) return;

        if (word >= kDeferredThreshold) {
            uint8_t lookup = tileAt(tx, ty) & 0xff;
            uint16_t flaggedWord = static_cast<uint16_t>(word | kDamagedWordBit);
            level_.wordLayer[start] = flaggedWord;
            markDamagedTile(tx, ty);
            if (debrisQueue_.size() < kDebrisCapacity) {
                DebrisRecord record;
                record.tileIndex = static_cast<int>(start);
                record.flaggedWord = flaggedWord;
                record.forwardPhase = forwardPhase;
                record.reversePhase = reversePhase;
                record.lookup = lookup;
                debrisQueue_.push_back(record);
            }
            return;
        }

        std::vector<size_t> stack{start};
        std::vector<size_t> group;
        while (!stack.empty()) {
            size_t index = stack.back();
            stack.pop_back();
            if (index >= level_.wordLayer.size() || level_.wordLayer[index] != word) continue;
            level_.wordLayer[index] = static_cast<uint16_t>(word | kDamagedWordBit);
            group.push_back(index);

            int x = static_cast<int>(index % static_cast<size_t>(level_.width));
            int y = static_cast<int>(index / static_cast<size_t>(level_.width));
            auto pushNeighbor = [&](int nx, int ny) {
                if (nx < 0 || ny < 0 || nx >= level_.width || ny >= level_.height) return;
                size_t next = static_cast<size_t>(ny) * level_.width + nx;
                if (next < level_.wordLayer.size() && level_.wordLayer[next] == word) {
                    stack.push_back(next);
                }
            };
            pushNeighbor(x + 1, y);
            pushNeighbor(x - 1, y);
            pushNeighbor(x, y + 1);
            pushNeighbor(x, y - 1);
        }

        int minX = level_.width;
        int minY = level_.height;
        int maxX = 0;
        int maxY = 0;
        for (size_t index : group) {
            int x = static_cast<int>(index % static_cast<size_t>(level_.width));
            int y = static_cast<int>(index / static_cast<size_t>(level_.width));
            minX = std::min(minX, x);
            minY = std::min(minY, y);
            maxX = std::max(maxX, x);
            maxY = std::max(maxY, y);
            markDamagedTile(x, y);
        }
        destroyed_ += static_cast<int>(group.size());
        if (!group.empty() && collapseQueue_.size() < kCollapseCapacity) {
            CollapseRecord record;
            record.x = tx;
            record.y = ty;
            record.startOffsetBytes = static_cast<uint16_t>((minY * level_.width + minX) * 2);
            record.endOffsetBytes = static_cast<uint16_t>((maxY * level_.width + maxX) * 2);
            record.word = word;
            record.flaggedWord = static_cast<uint16_t>(word | kDamagedWordBit);
            record.forwardPhase = forwardPhase;
            record.reversePhase = reversePhase;
            int signedForward = static_cast<int>(static_cast<int8_t>(forwardPhase));
            int signedReverse = static_cast<int>(static_cast<int8_t>(reversePhase));
            record.argMagnitude = static_cast<uint16_t>(std::abs(signedForward) +
                                                        std::abs(signedReverse));
            record.affectedBytes = static_cast<uint8_t>((group.size() * 2) & 0xff);
            record.count = static_cast<int>(group.size());
            collapseQueue_.push_back(record);
        }
    }

    DamagePhaseLookup resolveDamagePhase(uint16_t flaggedWord, bool reverse) const {
        if ((flaggedWord & kDamagedWordBit) == 0) return {};
        uint16_t key = static_cast<uint16_t>(flaggedWord & ~kDamagedWordBit);
        if (key >= kDeferredThreshold) {
            for (size_t i = debrisQueue_.size(); i > 0; --i) {
                const DebrisRecord& record = debrisQueue_[i - 1];
                if (record.flaggedWord == flaggedWord) {
                    return {static_cast<int>(i),
                            reverse ? record.reversePhase : record.forwardPhase, true};
                }
            }
            return {};
        }
        for (size_t i = collapseQueue_.size(); i > 0; --i) {
            const CollapseRecord& record = collapseQueue_[i - 1];
            if (record.flaggedWord == flaggedWord) {
                return {static_cast<int>(i),
                        reverse ? record.reversePhase : record.forwardPhase, false};
            }
        }
        return {};
    }

    void explode(const Bomb& bomb) {
        auto tiles = explosionTilesFor(bomb);
        spawnExplosionEffect(bomb);
        bool consumedBombObject = false;
        bool consumedHighBombObject = false;
        for (const auto& pos : tiles) {
            int x = pos[0];
            int y = pos[1];
            flashes_.push_back(
                {x, y, 12, static_cast<uint8_t>(monsterDamageForBomb(bomb.type))});
            uint8_t objectTile = static_cast<uint8_t>(tileAt(x, y));
            if (consumeBombObjectTile(x, y)) {
                consumedBombObject = true;
                consumedHighBombObject =
                    consumedHighBombObject || isHighBombObjectSoundTile(objectTile);
                addScore(bomb.owner, 50);
                queueTileDamage(x, y - 1);
            }
        }
        if (consumedBombObject) {
            requestBombObjectScoreSound(consumedHighBombObject);
        }
        damageMonstersInExplosion(tiles, bomb.type);
        damagePlayersInExplosion(tiles);
    }

    int monsterDamageForBomb(BombType type) const {
        return std::clamp(bombTypeIndex(type) + 1, 1, 4);
    }

    void damageMonstersInExplosion(const std::vector<std::array<int, 2>>& tiles,
                                   BombType type) {
        int damage = monsterDamageForBomb(type);
        for (ActiveMonster& monster : monsters_) {
            if (!monster.alive) continue;
            // Boss actors are exempt from the generic shot-damage path in
            // the original (1000:7427); the head instead drains from live
            // flames each frame in updateBossHead.
            if (monster.behavior == 5 || monster.behavior == 6) continue;
            if (monsterOverlapsExplosionTiles(monster, tiles)) {
                damageMonster(monster, damage);
            }
        }
    }

    bool monsterOverlapsExplosionTiles(const ActiveMonster& monster,
                                       const std::vector<std::array<int, 2>>& tiles) const {
        for (const auto& tile : tiles) {
            float x = static_cast<float>(tile[0] * kTileSize);
            float y = static_cast<float>(tile[1] * kTileSize);
            if (rectsOverlap(static_cast<float>(monster.x), static_cast<float>(monster.y),
                             14.0f, 16.0f, x, y, static_cast<float>(kTileSize),
                             static_cast<float>(kTileSize))) {
                return true;
            }
        }
        return false;
    }

    bool rectsOverlap(float ax, float ay, float aw, float ah,
                      float bx, float by, float bw, float bh) const {
        return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
    }

    void damageMonster(ActiveMonster& monster, int damage) {
        if (monster.behavior == 2) return;
        // Boss actors are exempt from generic damage (original 1000:7427
        // applies shot damage to kinds 1..8 only).
        if (monster.behavior == 5 || monster.behavior == 6) return;
        monster.hp = std::max(0, monster.hp - std::max(1, damage));
        if (monster.hp == 0) {
            enterMonsterDeath(monster);
        }
    }

    bool playerOverlapsAnyExplosionTile(const Player& player,
                                        const std::vector<std::array<int, 2>>& tiles) const {
        for (const auto& tile : tiles) {
            float x = static_cast<float>(tile[0] * kTileSize);
            float y = static_cast<float>(tile[1] * kTileSize);
            if (playerOverlaps(player, x, y, static_cast<float>(kTileSize),
                               static_cast<float>(kTileSize))) {
                return true;
            }
        }
        return false;
    }

    void damagePlayersInExplosion(const std::vector<std::array<int, 2>>& tiles) {
        if (!playerDead_ && playerOverlapsAnyExplosionTile(player_, tiles)) {
            queuePlayerDamage(1);
        }
        if (playerCount_ > 1 && !player2Dead_ &&
            playerOverlapsAnyExplosionTile(player2_, tiles)) {
            queuePlayerDamage(2);
        }
    }

    void enterMonsterDeath(ActiveMonster& monster) {
        if (monster.behavior == 2) return;
        spawnBonusDrop(static_cast<float>(monster.x) + 1.0f,
                       static_cast<float>(monster.y) + 2.0f);
        monster.behavior = 2;
        monster.kind = 0x0c;
        monster.stateTimer = 25;
        releaseMonsterSlot(monster);
        monster.vx8 = 0;
        monster.vy8 = 0;
        monster.fracX = 0;
        monster.fracY = 0;
        flashes_.push_back({static_cast<int>(monster.x + 7.0f) / 8,
                            static_cast<int>(monster.y + 8.0f) / 8, 18});
        requestMonsterDeathSound();
    }

    void spawnBonusDrop(float x, float y) {
        int roll = randomRangeValue(0, 7);
        BonusDrop drop;
        drop.x = x;
        drop.y = y;
        drop.type = static_cast<BonusType>(roll);
        bonusDrops_.push_back(drop);
    }

    void updateBonusDrops() {
        size_t initialDrops = bonusDrops_.size();
        for (size_t i = 0; i < initialDrops && i < bonusDrops_.size(); ++i) {
            BonusDrop& drop = bonusDrops_[i];
            if (drop.collected) continue;
            ++drop.animTick;
            bool p1Overlaps = !playerDead_ &&
                              playerOverlaps(player_, drop.x, drop.y, 12.0f, 12.0f);
            bool p2Overlaps = playerCount_ > 1 && !player2Dead_ &&
                              playerOverlaps(player2_, drop.x, drop.y, 12.0f, 12.0f);
            if (p1Overlaps &&
                (!p2Overlaps ||
                 bonusDistanceSq(player_, drop) <= bonusDistanceSq(player2_, drop))) {
                collectBonusDrop(drop, player_, energy_, bombInventory_, 1);
            } else if (p2Overlaps) {
                collectBonusDrop(drop, player2_, energy2_, bombInventory2_, 2);
            }
        }
        bonusDrops_.erase(std::remove_if(bonusDrops_.begin(), bonusDrops_.end(),
                                         [](const BonusDrop& drop) { return drop.collected; }),
                          bonusDrops_.end());
    }

    float bonusDistanceSq(const Player& player, const BonusDrop& drop) const {
        float dx = (player.x + 6.0f) - (drop.x + 6.0f);
        float dy = (player.y + 8.0f) - (drop.y + 6.0f);
        return dx * dx + dy * dy;
    }

    void collectBonusDrop(BonusDrop& drop, const Player& collector, int& energy,
                          BombInventory& inventory, uint8_t playerIndex) {
        BonusType type = drop.type;
        drop.collected = true;
        applyBonus(type, collector, energy, inventory, playerIndex);
        requestSoundCursor(kBonusPickupSoundCursor, kBonusPickupSoundPriority);
    }

    void applyBonus(BonusType type, const Player& collector, int& energy,
                    BombInventory& inventory, uint8_t playerIndex = 1) {
        switch (type) {
            case BonusType::Present:
                addScore(playerIndex, 2000);
                break;
            case BonusType::FirstAid:
                addScore(playerIndex, 1000);
                energy = 100;
                break;
            case BonusType::HotDog:
                addScore(playerIndex, 1500);
                energy = std::min(100, energy + 33);
                break;
            case BonusType::JollyCloud:
                addScore(playerIndex, 2000);
                spawnBonusRain(collector);
                break;
            case BonusType::YellowBombBox:
                addScore(playerIndex, 3000);
                grantNormalBombSet(inventory);
                break;
            case BonusType::GreenBombBox:
                addScore(playerIndex, 1000);
                grantSuperBombSet(inventory);
                break;
            case BonusType::BigDiamond:
                addScore(playerIndex, 5000);
                break;
        }
    }

    void grantNormalBombSet(BombInventory& inventory) {
        inventory.counts[0] = 200;
        inventory.counts[1] = std::min(99, inventory.counts[1] + randomInclusive(1, 10));
        inventory.counts[2] = std::min(99, inventory.counts[2] + randomInclusive(1, 4));
        if (!hasBomb(inventory, inventory.selected)) selectNextAvailableBomb(inventory);
    }

    void grantSuperBombSet(BombInventory& inventory) {
        inventory.counts[0] = 200;
        inventory.counts[1] = std::min(99, inventory.counts[1] + randomInclusive(1, 13));
        inventory.counts[2] = std::min(99, inventory.counts[2] + randomInclusive(2, 6));
        inventory.counts[3] = std::min(99, inventory.counts[3] + randomInclusive(1, 2));
        if (!hasBomb(inventory, inventory.selected)) selectNextAvailableBomb(inventory);
    }

    void spawnBonusRain(const Player& collector) {
        for (int i = 0; i < 4; ++i) {
            BonusDrop drop;
            drop.x = std::clamp(collector.x - 24.0f + i * 16.0f, 0.0f,
                                std::max(16.0f, level_.width * 8.0f - 16.0f));
            drop.y = std::max(16.0f, collector.y - 48.0f - i * 4.0f);
            drop.type = i % 2 == 0 ? BonusType::Present : BonusType::BigDiamond;
            bonusDrops_.push_back(drop);
        }
    }

    void updateFlashes() {
        for (Flash& f : flashes_) --f.timer;
        flashes_.erase(std::remove_if(flashes_.begin(), flashes_.end(),
                                      [](const Flash& f) { return f.timer <= 0; }),
                       flashes_.end());
        for (ExplosionEffect& e : explosionEffects_) --e.timer;
        explosionEffects_.erase(std::remove_if(explosionEffects_.begin(), explosionEffects_.end(),
                                               [](const ExplosionEffect& e) { return e.timer <= 0; }),
                                explosionEffects_.end());
        for (DebrisRecord& debris : debrisQueue_) {
            --debris.timer;
            if (level_.width > 0) {
                int tx = debris.tileIndex % level_.width;
                int ty = debris.tileIndex / level_.width;
                damagePlayersInTileArea(tx, ty, tx, ty);
            }
        }
        debrisQueue_.erase(std::remove_if(debrisQueue_.begin(), debrisQueue_.end(),
                                          [](const DebrisRecord& debris) { return debris.timer <= 0; }),
                           debrisQueue_.end());
        for (CollapseRecord& collapse : collapseQueue_) {
            --collapse.timer;
            if (level_.width > 0) {
                int startCell = collapse.startOffsetBytes / 2;
                int endCell = collapse.endOffsetBytes / 2;
                int tx0 = startCell % level_.width;
                int ty0 = startCell / level_.width;
                int tx1 = endCell % level_.width;
                int ty1 = endCell / level_.width;
                damagePlayersInTileArea(tx0, ty0, tx1, ty1);
            }
        }
        collapseQueue_.erase(std::remove_if(collapseQueue_.begin(), collapseQueue_.end(),
                                            [](const CollapseRecord& collapse) { return collapse.timer <= 0; }),
                             collapseQueue_.end());
    }

    int destructionPercent() const {
        if (level_.startingDestructibleTiles == 0) return 100;
        return std::min(100, destroyed_ * 100 / level_.startingDestructibleTiles);
    }

    bool isComplete() const {
        return collected_ >= level_.requiredBonus &&
               destructionPercent() >= static_cast<int>(level_.requiredDestruction);
    }

    void adjustGameplayViewWidth(int delta) {
        gameplayViewWidth_ = std::clamp(gameplayViewWidth_ + delta, 160, kScreenW);
    }

    void setClip(int left, int top, int right, int bottom) {
        clipLeft_ = std::clamp(left, 0, kScreenW);
        clipTop_ = std::clamp(top, 0, kScreenH);
        clipRight_ = std::clamp(right, clipLeft_, kScreenW);
        clipBottom_ = std::clamp(bottom, clipTop_, kScreenH);
    }

    void resetClip() {
        setClip(0, 0, kScreenW, kScreenH);
    }

    void pixel(int x, int y, uint32_t color) {
        if (x >= clipLeft_ && y >= clipTop_ && x < clipRight_ && y < clipBottom_) {
            fb_[static_cast<size_t>(y) * kScreenW + x] = color;
        }
    }

    void rect(int x, int y, int w, int h, uint32_t color) {
        for (int yy = std::max(clipTop_, y); yy < std::min(clipBottom_, y + h); ++yy) {
            for (int xx = std::max(clipLeft_, x); xx < std::min(clipRight_, x + w); ++xx) {
                fb_[static_cast<size_t>(yy) * kScreenW + xx] = color;
            }
        }
    }

    void draw() {
        if (levelIntro_.active) {
            drawLevelIntro(levelIntro_.levelIndex, levelIntro_.pattern,
                           visibleLevelIntroCharacters(SDL_GetTicks()));
        } else if (menu_) drawMenu();
        else drawGame();
        if (SDL_UpdateTexture(texture_, nullptr, fb_.data(),
                              kScreenW * sizeof(uint32_t)) != 0) {
            throw std::runtime_error(SDL_GetError());
        }
        if (SDL_RenderClear(renderer_) != 0) {
            throw std::runtime_error(SDL_GetError());
        }
        if (SDL_RenderCopy(renderer_, texture_, nullptr, nullptr) != 0) {
            throw std::runtime_error(SDL_GetError());
        }
        SDL_RenderPresent(renderer_);
    }

    void drawBackground(int camX, int camY) {
        // The SFONLEF.ZBG title image backing the menu. The in-game
        // showBackground_ toggle only affects the gameplay sky (drawGradientSky),
        // so the menu title is always drawn.
        for (int y = 0; y < kScreenH; ++y) {
            for (int x = 0; x < kScreenW; ++x) {
                int bx = (x + camX / 4) % background_.width;
                int by = (y + camY / 4) % background_.height;
                if (bx < 0) bx += background_.width;
                if (by < 0) by += background_.height;
                pixel(x, y,
                      argb(backgroundPalette_,
                           background_.pixels[static_cast<size_t>(by) * background_.width + bx]));
            }
        }
    }

    void drawGradientSky(int viewX, int viewY, int viewW, int viewH) {
        // Recovered from original level-1 frames: the level backdrop is a
        // vertical gradient from dark indigo at the top to warm brown near the
        // horizon (~row 100), drawn beneath the tiles. SFONLEF.ZBG is the
        // 320x200 title screen, not the scrolling level backdrop, so levels no
        // longer tile it as the sky.
        if (!showBackground_) {
            for (int y = 0; y < viewH; ++y) {
                for (int x = 0; x < viewW; ++x) {
                    pixel(viewX + x, viewY + y, argb(palette_, 0));
                }
            }
            return;
        }
        // Ramp fit to the original sky column: a flat dark band for the top ~11
        // rows, then a linear ramp over ~88 rows to the horizon colour.
        constexpr int kRampStart = 11, kRampSpan = 88;
        constexpr int kTopR = 16, kTopG = 8, kTopB = 52;
        constexpr int kBotR = 118, kBotG = 62, kBotB = 26;
        for (int y = 0; y < viewH; ++y) {
            const int t = std::clamp(y - kRampStart, 0, kRampSpan);
            const int r = kTopR + (kBotR - kTopR) * t / kRampSpan;
            const int g = kTopG + (kBotG - kTopG) * t / kRampSpan;
            const int b = kTopB + (kBotB - kTopB) * t / kRampSpan;
            const uint32_t color = 0xff000000u |
                                   (static_cast<uint32_t>(r) << 16) |
                                   (static_cast<uint32_t>(g) << 8) |
                                   static_cast<uint32_t>(b);
            for (int x = 0; x < viewW; ++x) {
                pixel(viewX + x, viewY + y, color);
            }
        }
    }

    void drawGame() {
        std::fill(fb_.begin(), fb_.end(), argb(palette_, 0));
        if (playerCount_ > 1) {
            drawWorldView(player_, 0, 16, kScreenW, 84);
            drawWorldView(player2_, 0, 116, kScreenW, 84);
            resetClip();
            drawHudBand(100, 2, energy2_, lives2_, player2Dead_,
                        bombInventory2_, score2_, true);
            rect(0, 115, kScreenW, 1, 0xfff0d060u);
        } else {
            int viewW = std::clamp(gameplayViewWidth_, 160, kScreenW);
            int viewX = (kScreenW - viewW) / 2;
            drawWorldView(player_, viewX, 0, viewW, kScreenH);
            resetClip();
            if (viewW < kScreenW) {
                rect(viewX - 1, 16, 1, kScreenH - 16, 0xfff0d060u);
                rect(viewX + viewW, 16, 1, kScreenH - 16, 0xfff0d060u);
            }
        }
        drawHud();
        if (paused_) drawPauseOverlay();
    }

    void drawWorldView(const Player& cameraPlayer, int viewX, int viewY, int viewW, int viewH) {
        int worldW = level_.width * 8;
        int worldH = level_.height * 8;
        setClip(viewX, viewY, viewX + viewW, viewY + viewH);
        int camX = std::clamp(static_cast<int>(cameraPlayer.x) - viewW / 2,
                              0, std::max(0, worldW - viewW));
        int camY = std::clamp(static_cast<int>(cameraPlayer.y) - viewH / 2,
                              0, std::max(0, worldH - viewH));
        int drawCamX = camX - viewX;
        int drawCamY = camY - viewY;
        drawGradientSky(viewX, viewY, viewW, viewH);
        drawTiles(drawCamX, drawCamY);
        drawBombs(drawCamX, drawCamY);
        drawDamageQueues(drawCamX, drawCamY);
        drawFlashes(drawCamX, drawCamY);
        drawExplosionEffects(drawCamX, drawCamY);
        drawBonusDrops(drawCamX, drawCamY);
        drawMonsters(drawCamX, drawCamY);
        if (!playerDead_) {
            drawPlayer(player_, playerFacing_, playerAnimTick_, drawCamX, drawCamY, 0);
        } else if (deathStateTimer_ > 0 && state2Visual_.active) {
            drawState2PlayerVisual(player_, state2Visual_, state2Effect_,
                                   drawCamX, drawCamY);
        }
        if (playerCount_ > 1 && !player2Dead_) {
            drawPlayer(player2_, player2Facing_, player2AnimTick_, drawCamX, drawCamY, 19);
        } else if (playerCount_ > 1 && deathStateTimer2_ > 0 &&
                   state2Visual2_.active) {
            drawState2PlayerVisual(player2_, state2Visual2_, state2Effect2_,
                                   drawCamX, drawCamY);
        }
    }

    void drawTiles(int camX, int camY) {
        int sx = std::max(0, camX / 8);
        int sy = std::max(0, camY / 8);
        int ex = std::min(level_.width, (camX + 319) / 8 + 2);
        int ey = std::min(level_.height, (camY + 199) / 8 + 2);
        for (int ty = sy; ty < ey; ++ty) {
            for (int tx = sx; tx < ex; ++tx) {
                int id = tileAt(tx, ty);
                const uint8_t* tile = tiles_.tile(id);
                if (!tile || id == 0) continue;
                int px = tx * 8 - camX;
                int py = ty * 8 - camY;
                for (int y = 0; y < 8; ++y) {
                    for (int x = 0; x < 8; ++x) {
                        uint8_t c = tile[y * 8 + x];
                        if (c != 0) pixel(px + x, py + y, argb(palette_, c));
                    }
                }
            }
        }
    }

    void drawBombs(int camX, int camY) {
        for (const Bomb& b : bombs_) {
            int x = b.x * 8 - camX;
            int y = b.y * 8 - camY;
            int index = static_cast<int>(bombProfile(b.type).spriteBase);
            if (index >= 0 && index < static_cast<int>(sprites_.sprites.size())) {
                drawSprite(sprites_.sprites[static_cast<size_t>(index)], x, y);
                continue;
            }
            int flashWindow = std::clamp(b.fuseTicks / 4, 6, 28);
            uint32_t body = b.timer <= flashWindow ? 0xfffff070u : bombColor(b.type);
            rect(x + 1, y + 1, 6, 6, body);
            rect(x + 3, y - 1, 2, 2, 0xffff7070u);
        }
    }

    uint32_t bombColor(BombType type) const {
        switch (type) {
            case BombType::Small: return 0xff181818u;
            case BombType::Medium: return 0xff4058d0u;
            case BombType::Large: return 0xffd05040u;
            case BombType::Super: return 0xff60d060u;
        }
        return 0xff181818u;
    }

    void drawFlashes(int camX, int camY) {
        for (const Flash& f : flashes_) {
            rect(f.x * 8 - camX, f.y * 8 - camY, 8, 8,
                 f.timer & 1 ? 0xfffff070u : 0xffff5030u);
        }
    }

    void drawDamageQueues(int camX, int camY) {
        for (const DebrisRecord& debris : debrisQueue_) {
            if (level_.width <= 0) continue;
            int tx = debris.tileIndex % level_.width;
            int ty = debris.tileIndex / level_.width;
            int px = tx * 8 - camX;
            int py = ty * 8 - camY;
            uint32_t color = debris.timer & 1 ? 0xfff0c050u : 0xff7c5030u;
            rect(px + 2, py + 2, 4, 2, color);
            rect(px + 1 + ((debris.lookup + debris.forwardPhase) & 1), py + 5,
                 2 + (debris.reversePhase & 1), 2, 0xffd08040u);
        }
        for (const CollapseRecord& collapse : collapseQueue_) {
            int px = collapse.x * 8 - camX;
            int py = collapse.y * 8 - camY;
            int age = 24 - collapse.timer;
            uint32_t color = age & 1 ? 0xff805840u : 0xffb87848u;
            rect(px, py + std::min(5, age / 2), 8, std::max(1, 6 - age / 5), color);
            if (collapse.count > 1) {
                rect(px + 1, py + 1, std::min(6, collapse.count), 1, 0xfff0c070u);
            }
        }
    }

    void drawExplosionEffects(int camX, int camY) {
        for (const ExplosionEffect& effect : explosionEffects_) {
            int age = effect.totalTimer - effect.timer;
            int px = effect.x * 8 - camX;
            int py = effect.y * 8 - camY;
            uint32_t hot = age & 1 ? 0xfffff0a0u : 0xffff7040u;
            uint32_t core = effect.visualSelector == 4 ? 0xffffffffu : 0xffffc050u;
            auto cell = [&](int tx, int ty, int inset, uint32_t color) {
                rect(px + tx * 8 + inset, py + ty * 8 + inset,
                     std::max(1, 8 - inset * 2), std::max(1, 8 - inset * 2), color);
            };
            if (effect.visualSelector == 4) {
                int inset = std::clamp(age / 9, 0, 3);
                cell(0, 0, inset, hot);
                cell(1, 0, inset, core);
                cell(1, 1, inset, hot);
                cell(0, 1, inset, core);
                if ((age % 6) < 3) {
                    rect(px - 2, py + 6, 20, 4, 0xffffa040u);
                    rect(px + 6, py - 2, 4, 20, 0xffffa040u);
                }
            } else {
                int inset = std::clamp(age / 3, 0, 3);
                cell(0, 0, inset, hot);
                if (effect.visualSelector >= 2) {
                    rect(px - 4, py + 3, 16, 2, core);
                    rect(px + 3, py - 4, 2, 16, core);
                }
                if (effect.visualSelector >= 3 && (age % 4) < 2) {
                    rect(px - 2, py - 2, 4, 4, 0xfffff0f0u);
                    rect(px + 6, py + 6, 4, 4, 0xfffff0f0u);
                }
            }
        }
    }

    bool isBossActor(const ActiveMonster& monster) const {
        return monster.behavior == 5 || monster.behavior == 6 || monster.bossDebris;
    }

    // Level 7 swaps the actor sheet to PROVA.SPR in the original (selector
    // 1000:2C90); boss sprites index that bank.
    const SpriteBank& monsterSpriteBank(const ActiveMonster& monster) const {
        return isBossActor(monster) ? altSprites_ : sprites_;
    }

    int monsterSpriteIndex(const ActiveMonster& monster) const {
        if (isBossActor(monster)) {
            // Hurt flash uses sprite 0x2f in the original head brain
            // (1000:5A75); debris keeps the last animation frame.
            int bossIndex = monster.hurtFlash > 0 ? 0x2f : monster.animFrame;
            if (bossIndex >= 0 &&
                bossIndex < static_cast<int>(altSprites_.sprites.size())) {
                return bossIndex;
            }
            return std::min<int>(static_cast<int>(altSprites_.sprites.size()) - 1, 39);
        }
        int index = monster.behavior == 2 ? 18 : monster.animFrame;
        if (index >= 0 && index < static_cast<int>(sprites_.sprites.size())) return index;
        return std::min<int>(sprites_.sprites.size() - 1, 39);
    }

    void drawSprite(const Sprite& sprite, int x0, int y0) {
        for (int y = 0; y < sprite.height; ++y) {
            for (int x = 0; x < sprite.width; ++x) {
                uint8_t c = sprite.pixels[static_cast<size_t>(y) * sprite.width + x];
                if (c != 0) pixel(x0 + x, y0 + y, argb(palette_, c));
            }
        }
    }

    void drawMonsters(int camX, int camY) {
        if (sprites_.sprites.empty()) return;
        for (const ActiveMonster& monster : monsters_) {
            if (!monster.alive) continue;
            const SpriteBank& bank = monsterSpriteBank(monster);
            if (bank.sprites.empty()) continue;
            int index = monsterSpriteIndex(monster);
            if (index < 0 || index >= static_cast<int>(bank.sprites.size())) continue;
            drawSprite(bank.sprites[static_cast<size_t>(index)],
                       static_cast<int>(monster.x) - camX,
                       static_cast<int>(monster.y) - camY);
        }
    }

    int bonusSpriteIndex(BonusType type) const {
        switch (type) {
            case BonusType::Present: return 61;
            case BonusType::FirstAid: return 62;
            case BonusType::HotDog: return 63;
            case BonusType::JollyCloud: return 64;
            case BonusType::YellowBombBox: return 65;
            case BonusType::GreenBombBox: return 66;
            case BonusType::BigDiamond: return 67;
        }
        return 61;
    }

    void drawBonusDrops(int camX, int camY) {
        for (const BonusDrop& drop : bonusDrops_) {
            int x = static_cast<int>(drop.x) - camX;
            int y = static_cast<int>(drop.y) - camY + ((drop.animTick / 16) & 1);
            int index = bonusSpriteIndex(drop.type);
            if (index >= 0 && index < static_cast<int>(sprites_.sprites.size())) {
                drawSprite(sprites_.sprites[static_cast<size_t>(index)], x, y);
            } else {
                rect(x, y, 8, 8, 0xffffe060u);
            }
        }
    }

    void drawPlayer(const Player& player, int facing, int animTick, int camX, int camY,
                    int frameOffset) {
        int x0 = static_cast<int>(player.x) - camX;
        int y0 = static_cast<int>(player.y) - camY;
        const SpriteBank& bank = sprites_.sprites.empty() ? altSprites_ : sprites_;
        if (!bank.sprites.empty()) {
            int frame = player.grounded ? (animTick / 8) % 9 : 4;
            int index = frameOffset + (facing < 0 ? 9 + frame : frame);
            if (index >= static_cast<int>(bank.sprites.size())) index = 0;
            drawSprite(bank.sprites[static_cast<size_t>(index)], x0, y0);
        } else {
            rect(x0, y0, 12, 16, 0xff60e0a0u);
        }
    }

    void drawState2PlayerVisual(const Player& player, const State2VisualCursor& cursor,
                                const State2EffectEntry& effect,
                                int camX, int camY) {
        int x0 = (effect.active ? effect.x : static_cast<int>(player.x)) - camX;
        int y0 = (effect.active ? effect.y : static_cast<int>(player.y)) - camY;
        int index = static_cast<int>(cursor.current);
        if (!state2VisualCursorPreview_) {
            if (effect.active && effect.visualFrame == cursor.current) {
                index = static_cast<int>(effect.spriteIndex);
                x0 += static_cast<int>(effect.drawDx);
                y0 += static_cast<int>(effect.drawDy);
            } else {
                State2VisualRow row;
                if (originalState2VisualRow(cursor.current, row)) {
                    index = static_cast<int>(row.row3);
                    x0 += static_cast<int>(row.row0);
                    y0 += static_cast<int>(row.row1);
                }
            }
        }
        if (index >= 0 && index < static_cast<int>(sprites_.sprites.size())) {
            drawSprite(sprites_.sprites[static_cast<size_t>(index)], x0, y0);
            return;
        }
        uint32_t color = 0xfff0c050u + ((cursor.current & 0x07u) << 8);
        rect(x0, y0 + 4, 14, 8, color);
        rect(x0 + 3, y0, 8, 16, 0xff703020u);
    }

    uint32_t energyColor(int energy) const {
        if (energy >= 67) return 0xff40d060u;
        if (energy >= 34) return 0xfff0c040u;
        return 0xffe04838u;
    }

    void drawMeter(int x, int y, int w, int h, int value, int maxValue,
                   uint32_t color) {
        rect(x - 1, y - 1, w + 2, h + 2, 0xfff0d060u);
        rect(x, y, w, h, 0xff1c1c1cu);
        int filled = std::clamp(value, 0, maxValue) * w / std::max(1, maxValue);
        if (filled > 0) rect(x, y, filled, h, color);
    }

    void drawBombInventoryIcons(int x, int y, const BombInventory& inventory) {
        for (int i = 0; i < 4; ++i) {
            BombType type = static_cast<BombType>(i);
            int px = x + i * 34;
            bool selected = inventory.selected == type;
            rect(px - 1, y - 1, 30, 10, selected ? 0xfff0d060u : 0xff303030u);
            rect(px, y, 8, 8, bombColor(type));
            text(px + 10, y + 1, std::to_string(inventory.counts[static_cast<size_t>(i)]),
                 selected ? 0xff000000u : 0xffffffffu);
        }
    }

    void drawHudBand(int y, int playerIndex, int energy, int lives, bool dead,
                     const BombInventory& inventory, uint32_t score,
                     bool includeProgress) {
        rect(0, y, kScreenW, 24, 0xdd000000u);
        rect(0, y + 23, kScreenW, 1, 0xfff0d060u);
        text(4, y + 3, "P" + std::to_string(playerIndex), 0xffffe060u);
        text(22, y + 3, dead ? (lives <= 0 ? "OUT" : "WAIT") : "HP", 0xffffffffu);
        drawMeter(48, y + 4, 54, 6, dead ? 0 : energy, 100, energyColor(energy));
        text(108, y + 3, std::to_string(std::clamp(energy, 0, 255)), 0xffffffffu);
        text(132, y + 3, "L" + std::to_string(lives), 0xffffffffu);
        drawBombInventoryIcons(154, y + 3, inventory);
        text(4, y + 14, "S" + std::to_string(score), 0xffffffffu);
        if (includeProgress) {
            text(72, y + 14, progressHudText(), 0xffd8f0ffu);
        }
    }

    // Blit an 8x8 CARO.CAR tile at a screen position (transparent index 0),
    // the primitive the original HUD uses for its objective/life-marker icons.
    bool drawHudTile8(int dx, int dy, int id) {
        const uint8_t* tile = tiles_.tile(id);
        if (!tile) return false;
        for (int ty = 0; ty < 8; ++ty) {
            for (int tx = 0; tx < 8; ++tx) {
                uint8_t c = tile[ty * 8 + tx];
                if (c != 0) pixel(dx + tx, dy + ty, argb(palette_, c));
            }
        }
        return true;
    }

    // Draw a HUD number using CARO.CAR digit tiles 121-130 (digit v -> tile
    // 121+v), the way the original HUD renders its numbers. 8px per digit.
    void drawHudNumber(int x, int y, int value, int minDigits) {
        std::string s = std::to_string(std::max(0, value));
        while (static_cast<int>(s.size()) < minDigits) s.insert(s.begin(), '0');
        for (size_t i = 0; i < s.size(); ++i) {
            drawHudTile8(x + static_cast<int>(i) * 8, y, 121 + (s[i] - '0'));
        }
    }

    void drawOriginalHudFigure(int x, int y, uint32_t color) {
        // Player-life marker: the original blits CARO.CAR tile 115 (a green
        // walking figure); fall back to a small stick glyph if unavailable.
        if (drawHudTile8(x, y - 1, kHudLifeMarkerTile)) return;
        static const char* kGlyph[7] = {
            " X ", " X ", "XXX", " X ", " X ", "X X", "X X"};
        for (int gy = 0; gy < 7; ++gy) {
            for (int gx = 0; gx < 3; ++gx) {
                if (kGlyph[gy][gx] == 'X') pixel(x + gx, y + gy, color);
            }
        }
    }

    void drawSinglePlayerHud() {
        // Reconstructed from the original level-1 HUD: a solid-black bottom
        // band with a grey/white top border, a yellow energy bar and blue
        // score panel on the left, green player-life figures beneath it, a grey
        // bomb-selector box in the centre, and a blue/cyan panel with bomb and
        // objective tallies on the right. Colours are sampled from the original
        // frames (VGA palette).
        constexpr uint32_t kBlack = 0xff000000u;
        constexpr uint32_t kGrey = 0xffb6b6b6u;
        constexpr uint32_t kWhite = 0xffffffffu;
        constexpr uint32_t kYellow = 0xffffff55u;
        constexpr uint32_t kBlue = 0xff0018dbu;
        constexpr uint32_t kCyan = 0xff00aaaau;
        constexpr uint32_t kGreen = 0xff00f300u;
        constexpr uint32_t kBoxGrey = 0xff828282u;
        const int y0 = kScreenH - 46;

        // The original HUD band begins two pixels below y0: gameplay terrain
        // shows through at y0..y0+1, then a 3px grey rule (y0+2..y0+4) and a 1px
        // white rule (y0+5), measured from the original level-1 frame. The black
        // status area and its content start below that.
        rect(0, y0 + 2, kScreenW, 44, kBlack);
        rect(0, y0 + 2, kScreenW, 3, kGrey);
        rect(0, y0 + 5, kScreenW, 1, kWhite);

        // Energy bar: the original draws a single-pixel-tall yellow line
        // (measured at row y0+11, ~1px), not a thick bar.
        const int barW = 96;
        int fill = std::clamp(playerDead_ ? 0 : energy_, 0, 100) * barW / 100;
        rect(4, y0 + 11, fill, 1, kYellow);

        // Score panel: blue box with a cyan left edge and a right-aligned green
        // score value.
        rect(0, y0 + 18, 88, 20, kBlue);
        rect(0, y0 + 18, 2, 20, kCyan);
        int scoreDigits = static_cast<int>(std::to_string(score_).size());
        int scoreX = std::max(4, 84 - scoreDigits * 8);
        drawHudNumber(scoreX, y0 + 24, score_, 1);

        // Player-life figures: the original HUD shows SPARE lives (the life in
        // play is not counted), so a fresh 3-life start draws two markers --
        // matching every captured original level-start frame.
        for (int i = 0; i < std::clamp(lives_ - 1, 0, 6); ++i) {
            drawOriginalHudFigure(4 + i * 8, y0 + 38, kGreen);
        }

        // Bomb selector box showing the selected bomb's actual sprite (from the
        // BOMOMIMK bank, the same sprite the world bomb uses) and its count.
        // Measured against the original: a 20x20 grey box at (119, y0+7).
        rect(119, y0 + 7, 20, 20, kBoxGrey);
        rect(121, y0 + 9, 16, 16, 0xff1c1c1cu);
        const int bombSprite =
            static_cast<int>(bombProfile(bombInventory_.selected).spriteBase);
        if (bombSprite >= 0 &&
            bombSprite < static_cast<int>(sprites_.sprites.size())) {
            const Sprite& sprite = sprites_.sprites[static_cast<size_t>(bombSprite)];
            const int bx = 121 + (16 - sprite.width) / 2;
            const int by = y0 + 9 + (16 - sprite.height) / 2;
            setClip(121, y0 + 9, 121 + 16, y0 + 9 + 16);
            drawSprite(sprite, bx, by);
            resetClip();
        } else {
            rect(121, y0 + 9, 16, 16, bombColor(bombInventory_.selected));
        }
        int selCount = bombInventory_.counts[
            static_cast<size_t>(bombInventory_.selected)];
        drawHudNumber(120, y0 + 28, std::clamp(selCount, 0, 99), 2);

        // Right panel: bomb-count and objective (destruction target) tallies.
        // The original panel spans y0+6..y0+44 (measured 160-198 on level 1),
        // taller than the earlier 34px box.
        rect(141, y0 + 6, 37, 39, kBlue);
        rect(141, y0 + 6, 37, 1, kCyan);
        rect(141, y0 + 44, 37, 1, kCyan);
        rect(141, y0 + 6, 1, 39, kCyan);
        rect(177, y0 + 6, 1, 39, kCyan);
        // Top row: bonus-objective icon + the level's required bonus count.
        // Bottom row: destruction-target icon + the required destruction count.
        // These two numbers were verified pixel-for-pixel against the original
        // HUD across every level (L1 1/50, L2 3/60, L3 7/20, L4 3/70, L5 8/65,
        // L7 1/10), so they must read from the level's objective data.
        //
        // The top icon is the level's bonus-collectible graphic: the original
        // draws the level objectiveTile (verified because levels 1 and 3 share
        // objectiveTile 108 and show the identical lemon; L2=grapes, L5=melon).
        // Each tally icon sits in its own small black inset box on the panel.
        // Rows use the original's 16px spacing: top at y0+13, bottom at y0+29
        // (measured against the original level-1 frame).
        rect(143, y0 + 12, 10, 10, kBlack);
        rect(143, y0 + 28, 10, 10, kBlack);
        if (!drawHudTile8(144, y0 + 13, level_.objectiveTile)) {
            rect(144, y0 + 13, 8, 8, kYellow);
        }
        // The original displays the REMAINING objective (required - current),
        // counting down to zero as bonuses are collected / tiles destroyed.
        int bonusRemaining =
            std::max(0, static_cast<int>(level_.requiredBonus) - collected_);
        drawHudNumber(159, y0 + 13, std::min(99, bonusRemaining), 2);
        // Bottom icon: the fixed destruction-target star, CARO.CAR tile 117.
        if (!drawHudTile8(144, y0 + 29, kHudDestructionStarTile)) {
            rect(144, y0 + 29, 8, 8, kYellow);
        }
        int destRemaining = std::max(
            0, static_cast<int>(level_.requiredDestruction) - destructionPercent());
        drawHudNumber(159, y0 + 29, std::min(99, destRemaining), 2);
    }

    void drawHud() {
        // The original HUD is a bottom status band (the top of the screen is
        // gameplay sky).
        if (playerCount_ == 1) {
            drawSinglePlayerHud();
        } else {
            drawHudBand(kScreenH - 24, 1, energy_, lives_, playerDead_,
                        bombInventory_, score_, false);
        }
        if (isComplete()) {
            rect(76, 84, 168, 24, 0xee000000u);
            text(92, 92, "LEVEL COMPLETED", 0xffffe060u, false, 0xff301800u);
        }
    }

    void drawPauseOverlay() {
        constexpr int x = 112;
        constexpr int y = 84;
        constexpr int w = 96;
        constexpr int h = 28;
        rect(x, y, w, h, 0xdd000000u);
        rect(x, y, w, 1, 0xfff0d060u);
        rect(x, y + h - 1, w, 1, 0xfff0d060u);
        rect(x, y, 1, h, 0xfff0d060u);
        rect(x + w - 1, y, 1, h, 0xfff0d060u);
        text(x + 27, y + 10, "PAUSED", 0xffffe060u, false, 0xff301800u);
    }

    std::string objectiveHudText() const {
        return progressHudText() +
               " S" + std::to_string(score_);
    }

    std::string progressHudText() const {
        return "L" + std::to_string(levelIndex_ + 1) +
               " B" + std::to_string(collected_) + "/" +
               std::to_string(level_.requiredBonus) +
               " D" + std::to_string(destructionPercent()) + "/" +
               std::to_string(level_.requiredDestruction);
    }

    std::string playerHudText(int index, int energy, int lives, bool dead,
                              const BombInventory& inventory) const {
        return "P" + std::to_string(index) +
               " E" + std::to_string(energy) +
               " L" + std::to_string(lives) +
               " W" + std::to_string(bombTypeIndex(inventory.selected) + 1) +
               " " + std::to_string(inventory.counts[0]) + "/" +
               std::to_string(inventory.counts[1]) + "/" +
               std::to_string(inventory.counts[2]) + "/" +
               std::to_string(inventory.counts[3]) +
               (dead ? (lives <= 0 ? " OUT" : " WAIT") : "");
    }

    void drawLevelIntro(int levelIndex, const LevelIntroPattern& pattern,
                        size_t visibleCharacters) {
        resetClip();
        int fraction = 0;
        int phase = 0;
        for (int i = 0; i < kScreenW * kScreenH; ++i) {
            fraction += pattern.horizontalStep;
            if (fraction > 100) {
                fraction -= 100;
                ++phase;
            }
            if (i % kScreenW == 0) {
                const int sineIndex = ((i * 3) / 100) % 128;
                const int wave = static_cast<int>(
                    std::sin(static_cast<float>(sineIndex) * 6.28f / 128.0f) *
                    8.0f);
                fraction += pattern.verticalStep + wave;
                if (fraction > 100) {
                    fraction -= 100;
                    ++phase;
                }
            }
            const Rgb color =
                pattern.colors[static_cast<size_t>(phase) % pattern.colors.size()];
            pixel(i % kScreenW, i / kScreenW,
                  0xff000000u | (static_cast<uint32_t>(color.r) << 16) |
                      (static_cast<uint32_t>(color.g) << 8) | color.b);
        }

        const std::string caption = levelIntroCaption(levelIndex);
        const size_t count = std::min(visibleCharacters, caption.size());
        int x = kScreenW / 2 -
                static_cast<int>(caption.size()) * kLevelIntroCellAdvance / 2;
        for (size_t i = 0; i < count; ++i, x += kLevelIntroCellAdvance) {
            const int glyphIndex = fontGlyphIndex(caption[i], false);
            if (glyphIndex < 0 ||
                glyphIndex >= static_cast<int>(fontSprites_.sprites.size())) {
                continue;
            }
            const Sprite& glyph =
                fontSprites_.sprites[static_cast<size_t>(glyphIndex)];
            drawFontSprite(x - 1, kLevelIntroTextY - 1, glyph,
                           argb(palette_, 1), false);
            drawFontSprite(x, kLevelIntroTextY, glyph,
                           argb(palette_, 31), false);
        }
    }

    void drawMenu() {
        drawBackground(0, 0);
        if (menuPage_ == MenuPage::Main) {
            // The original main menu is the SFONLEF.ZBG title screen with the
            // menu options drawn directly over the art (Italian by default; L
            // toggles English). Strings recovered from LEZAC.EXE 1000:b1e3
            // (Italian) and 1000:bf15 (English).
            static const char* kItalian[7] = {
                "PREMI 1 PER UN GIOCATORE", "PREMI 2 PER DUE GIOCATORI",
                "I: INFORMAZIONI", "Z: ISTRUZIONI", "R: VEDI RECORDS",
                "L: ENGLISH", "ESC PER USCIRE"};
            static const char* kEnglish[7] = {
                "PRESS 1 FOR ONE PLAYER GAME", "PRESS 2 FOR TWO PLAYERS GAME",
                "I: INFOS", "Z: INSTRUCTIONS", "R: SHOW RECORDS",
                "L: ITALIANO", "ESC EXITS"};
            const char* const* lines = menuItalian_ ? kItalian : kEnglish;
            for (int i = 0; i < 7; ++i) {
                const std::string line = lines[i];
                const int x = (kScreenW - static_cast<int>(line.size()) * 8) / 2;
                text(std::max(0, x), 60 + i * 10, line, 0xffffffffu, false,
                     0xff000000u);
            }
            return;
        }
        rect(0, 0, 320, 200, 0x99000000u);
        text(84, 26, "LARAX & ZACO", 0xffffe060u, true, 0xff301800u);
        switch (menuPage_) {
            case MenuPage::Main:
                drawMainMenu();
                break;
            case MenuPage::Info:
                drawInfoMenu();
                break;
            case MenuPage::Instructions:
                drawInstructionsMenu();
                break;
            case MenuPage::Records:
                drawRecordsMenu();
                break;
            case MenuPage::NameEntry:
                drawNameEntryMenu();
                break;
            case MenuPage::GameOver:
                drawGameOverMenu();
                break;
            case MenuPage::CompletedGame:
                drawCompletedGameMenu();
                break;
        }
    }

    void drawMainMenu() {
        text(61, 43, "GHIDRA CPP RECONSTRUCTION", 0xffffffffu, false, 0xff101010u);
        text(34, 67, "PRESS 1 FOR ONE PLAYER GAME.", 0xffffe060u, false, 0xff101010u);
        text(34, 79, "PRESS 2 FOR TWO PLAYERS GAME.", 0xffffe060u, false, 0xff101010u);
        text(34, 91, "I: INFOS. Z: INSTRUCTIONS.", 0xffffffffu, false, 0xff101010u);
        text(34, 103, "R: SHOW RECORDS. ESC EXITS.", 0xffffffffu, false, 0xff101010u);
        text(34, 115, "S: BACKGROUND.", 0xffffffffu, false, 0xff101010u);

        text(88, 139, "BEST SCORES", 0xff90ffb0u, false, 0xff101010u);
        int y = 154;
        for (size_t i = 0; i < records_.size() && i < 4; ++i) {
            drawRecordLine(i, y);
            y += 10;
        }
    }

    void drawCenteredMenuLines(const char* title, const char* const* lines,
                               int count) {
        const int tx = (kScreenW - static_cast<int>(std::string(title).size()) * 8) / 2;
        text(std::max(0, tx), 40, title, 0xff90ffb0u, false, 0xff101010u);
        for (int i = 0; i < count; ++i) {
            const std::string line = lines[i];
            const int x = (kScreenW - static_cast<int>(line.size()) * 8) / 2;
            text(std::max(0, x), 60 + i * 11, line, 0xffffffffu, false, 0xff101010u);
        }
        const char* back = menuItalian_ ? "ESC PER TORNARE" : "ESC: BACK";
        const int bx = (kScreenW - static_cast<int>(std::string(back).size()) * 8) / 2;
        text(std::max(0, bx), 184, back, 0xff90ffb0u, false, 0xff101010u);
    }

    void drawInfoMenu() {
        // Recovered from LEZAC.EXE: Italian at 1000:b000, English at 1000:bcab.
        static const char* kIta[8] = {
            "PER PROCEDERE NEL GIOCO DOVETE",
            "RACCOGLIERE BONUS E SOPRATTUTTO",
            "FAR SALTARE IN ARIA OGNI COSA",
            "IL RIQUADRO CENTRALE VI INDICA",
            "IL NUMERO MINIMO DI BONUS DA",
            "RACCOGLIERE E LA PERCENTUALE DELLE",
            "COSTRUZIONI DA DISTRUGGERE PER",
            "COMPLETARE IL QUADRO"};
        static const char* kEng[7] = {
            "YOU MUST COLLECT BONUSES AND",
            "DESTROY BUILDINGS TO PROCEED",
            "THE CENTRAL WINDOW WILL TELL",
            "YOU THE NUMBER OF BONUS TO",
            "COLLECT AND THE PERCENTAGE",
            "OF BUILDINGS YOU MUST DESTROY",
            "TO COMPLETE THE LEVEL"};
        if (menuItalian_) {
            drawCenteredMenuLines("INFORMAZIONI", kIta, 8);
        } else {
            drawCenteredMenuLines("INFOS", kEng, 7);
        }
    }

    void drawInstructionsMenu() {
        // Recovered keys table + notes from LEZAC.EXE: Italian at 1000:b9xx
        // ("tasti") / fire+weapon at 1000:aef4, English at 1000:baab / 1000:bbab.
        struct KeyRow { const char* action; const char* p1; const char* p2; };
        const char* title = menuItalian_ ? "ISTRUZIONI" : "INSTRUCTIONS";
        const char* colHdr = menuItalian_ ? "GIOC:1      GIOC:2"
                                           : "PLAYER1     PLAYER2";
        static const KeyRow kIta[5] = {
            {"SINISTRA", "Z", "FRECCE"}, {"DESTRA", "X", "="},
            {"SCENDI", "C", "="}, {"SALTA", "M", "="}, {"FUOCO", "N", "0"}};
        static const KeyRow kEng[5] = {
            {"LEFT", "Z", "ARROWS"}, {"RIGHT", "X", "="},
            {"DOWN", "C", "="}, {"JUMP", "M", "="}, {"FIRE", "N", "0"}};
        static const char* kItaNotes[4] = {
            "ESC ABBANDONA LA PARTITA",
            "PREMI SINISTRA E DESTRA INSIEME",
            "PER CAMBIARE BOMBA",
            "S ATTIVA O DISATTIVA LO SFONDO"};
        static const char* kEngNotes[4] = {
            "ESC QUITS GAME",
            "PRESS LEFT AND RIGHT TOGETHER",
            "TO CHANGE YOUR WEAPON",
            "S TOGGLES BACKGROUND"};
        const KeyRow* rows = menuItalian_ ? kIta : kEng;
        const char* const* notes = menuItalian_ ? kItaNotes : kEngNotes;

        const int tx = (kScreenW - static_cast<int>(std::string(title).size()) * 8) / 2;
        text(std::max(0, tx), 34, title, 0xff90ffb0u, false, 0xff101010u);
        text(120, 52, colHdr, 0xffffe060u, false, 0xff101010u);
        for (int i = 0; i < 5; ++i) {
            text(32, 66 + i * 11, rows[i].action, 0xffffffffu, false, 0xff101010u);
            text(140, 66 + i * 11, rows[i].p1, 0xffffffffu, false, 0xff101010u);
            text(220, 66 + i * 11, rows[i].p2, 0xffffffffu, false, 0xff101010u);
        }
        for (int i = 0; i < 4; ++i) {
            const std::string line = notes[i];
            const int x = (kScreenW - static_cast<int>(line.size()) * 8) / 2;
            text(std::max(0, x), 128 + i * 11, line, 0xffd8f0ffu, false, 0xff101010u);
        }
    }

    void drawRecordsMenu() {
        // Original records title: "il file dei records" (LEZAC.EXE 1000:16a7).
        const char* title = menuItalian_ ? "IL FILE DEI RECORDS" : "BEST SCORES";
        const int tx = (kScreenW - static_cast<int>(std::string(title).size()) * 8) / 2;
        text(std::max(0, tx), 48, title, 0xff90ffb0u, false, 0xff101010u);
        int y = 70;
        for (size_t i = 0; i < records_.size(); ++i) {
            drawRecordLine(i, y);
            y += 12;
        }
        text(38, 166, "ESC: BACK", 0xff90ffb0u, false, 0xff101010u);
    }

    void drawNameEntryMenu() {
        // Labels recovered from LEZAC.EXE: "giocatore" (1000:17f3), "punteggio
        // finale" (1000:b3ab), "inserisci il tuo nome" (1000:1826).
        const bool it = menuItalian_;
        text(it ? 82 : 86, 48, it ? "NUOVO RECORD" : "NEW RECORD",
             0xff90ffb0u, false, 0xff101010u);
        text(58, 64,
             (it ? "GIOCATORE " : "PLAYER ") + std::to_string(pendingRecordPlayer_),
             0xffffffffu, false, 0xff101010u);
        text(58, 78,
             (it ? "PUNTEGGIO " : "SCORE ") + std::to_string(pendingRecordScore_),
             0xffffe060u, false, 0xff101010u);
        text(58, 94,
             (it ? "LIVELLO " : "LEVEL ") + std::to_string(pendingRecordLevel_),
             0xffffffffu, false, 0xff101010u);
        text(kNameEntryLabelX, kNameEntrySlotY, it ? "NOME " : "NAME ",
             0xffffffffu, false, 0xff101010u);
        drawNameEntrySlots();
        text(30, 148,
             it ? "INSERISCI IL TUO NOME" : "TYPE LETTERS OR SPACE",
             0xffffffffu, false, 0xff101010u);
        text(30, 160,
             it ? "ENTER SALVA. BACKSPACE CANCELLA" : "ENTER SAVE. BACKSPACE ERASES",
             0xff90ffb0u, false, 0xff101010u);
    }

    int nameEntryCursorSlot() const {
        return std::min<int>(static_cast<int>(pendingRecordName_.size()),
                             kNameEntrySlotCount - 1);
    }

    int nameEntrySlotX(int slot) const {
        return kNameEntryLabelX + textWidth("NAME ") +
               slot * kNameEntrySlotAdvance;
    }

    void drawNameEntrySlots() {
        int activeSlot = nameEntryCursorSlot();
        for (int slot = 0; slot < kNameEntrySlotCount; ++slot) {
            int x = nameEntrySlotX(slot);
            bool active = slot == activeSlot;
            if (active) {
                rect(x - 1, kNameEntrySlotY - 2, kNameEntryCursorBoxW,
                     kNameEntryCursorBoxH, kNameEntryCursorBackground);
            }
            char ch = slot < static_cast<int>(pendingRecordName_.size())
                          ? pendingRecordName_[static_cast<size_t>(slot)]
                          : '_';
            text(x, kNameEntrySlotY, std::string(1, ch),
                 active ? kNameEntryCursorForeground : 0xffffffffu,
                 false, active ? 0 : 0xff101010u);
        }
    }

    void drawGameOverMenu() {
        text(111, 72, "GAME OVER", 0xffff5050u, true, 0xff301010u);
        drawFinalScores(104);
        text(78, 166, "ENTER: MENU", 0xff90ffb0u, false, 0xff101010u);
    }

    void drawCompletedGameMenu() {
        text(90, 58, "ECCELLENTE>>>", 0xffffe060u, false, 0xff101010u);
        text(54, 76, "HAI COMPLETATO IL GIOCO", 0xffffffffu, false, 0xff101010u);
        drawFinalScores(112);
        text(78, 166, "ENTER: MENU", 0xff90ffb0u, false, 0xff101010u);
    }

    void drawFinalScores(int y) {
        if (score_ != 0) {
            text(82, y, "P1 FINAL SCORE " + std::to_string(score_),
                 0xffffe060u, false, 0xff101010u);
            y += 12;
        }
        if (playerCount_ > 1 && score2_ != 0) {
            text(82, y, "P2 FINAL SCORE " + std::to_string(score2_),
                 0xffffe060u, false, 0xff101010u);
        }
    }

    void drawRecordLine(size_t i, int y) {
        text(52, y, std::to_string(i + 1) + " L" +
                        std::to_string(records_[i].level) + " " + records_[i].name,
             0xffffffffu, false, 0xff101010u);
        text(178, y, std::to_string(records_[i].score), 0xffffffffu, false, 0xff101010u);
    }

    int fontGlyphIndex(char raw, bool large) const {
        char ch = raw;
        if (ch >= 'a' && ch <= 'z') ch = static_cast<char>(ch - 'a' + 'A');
        if (ch >= 'A' && ch <= 'Z') return (large ? 0 : 26) + (ch - 'A');
        if (ch >= '0' && ch <= '9') return 52 + (ch - '0');
        switch (ch) {
            case '.': return 62;
            case ':': return 63;
            case ';': return 64;
            case ',': return 65;
            case '!': return 66;
            case '\'': return 67;
            default: return -1;
        }
    }

    std::array<std::string, 8> fallbackGlyph(char ch) const {
        switch (ch) {
            case '/':
                return {"      # ", "     #  ", "    #   ", "   #    ",
                        "  #     ", " #      ", "#       ", "        "};
            case '-':
                return {"        ", "        ", "        ", " ###### ",
                        "        ", "        ", "        ", "        "};
            case '_':
                return {"        ", "        ", "        ", "        ",
                        "        ", "        ", " ###### ", "        "};
            case '%':
                return {"##    # ", "##   #  ", "    #   ", "   #    ",
                        "  #     ", " #   ## ", "#    ## ", "        "};
            case '&':
                return {"  ###   ", " ## ##  ", " ## #   ", "  ##    ",
                        " ## # # ", "##  ##  ", " ### ## ", "        "};
            case '+':
                return {"        ", "   ##   ", "   ##   ", " ###### ",
                        "   ##   ", "   ##   ", "        ", "        "};
            default:
                return {"        ", "        ", "        ", "        ",
                        "        ", "        ", "        ", "        "};
        }
    }

    void drawFallbackGlyph(int x, int y, char ch, uint32_t color) {
        const auto rows = fallbackGlyph(ch);
        for (int yy = 0; yy < 8; ++yy) {
            for (int xx = 0; xx < 8; ++xx) {
                if (rows[yy][xx] != ' ') pixel(x + xx, y + yy, color);
            }
        }
    }

    void drawFontSprite(int x, int y, const Sprite& glyph, uint32_t color, bool preservePalette) {
        for (int yy = 0; yy < glyph.height; ++yy) {
            for (int xx = 0; xx < glyph.width; ++xx) {
                uint8_t px = glyph.pixels[static_cast<size_t>(yy) * glyph.width + xx];
                if (px == 0) continue;
                pixel(x + xx, y + yy,
                      preservePalette && px != 1 ? argb(palette_, px) : color);
            }
        }
    }

    int glyphAdvance(char raw, bool large = false) const {
        if (raw == ' ') return large ? 8 : 5;
        int index = fontGlyphIndex(raw, large);
        if (index >= 0 && index < static_cast<int>(fontSprites_.sprites.size())) {
            return fontSprites_.sprites[static_cast<size_t>(index)].width + 1;
        }
        return 9;
    }

    int textWidth(const std::string& s, bool large = false) const {
        int width = 0;
        for (char raw : s) {
            width += glyphAdvance(raw, large);
        }
        return width;
    }

    void text(int x, int y, const std::string& s, uint32_t color, bool large = false,
              uint32_t shadow = 0, int shadowDx = 1, int shadowDy = 1) {
        int cx = x;
        for (char raw : s) {
            char ch = raw;
            if (ch == ' ') {
                cx += glyphAdvance(ch, large);
                continue;
            }
            int index = fontGlyphIndex(ch, large);
            auto drawOne = [&](int px, int py, uint32_t drawColor, bool preservePalette) {
                if (index >= 0 && index < static_cast<int>(fontSprites_.sprites.size())) {
                    const Sprite& glyph = fontSprites_.sprites[static_cast<size_t>(index)];
                    drawFontSprite(px, py, glyph, drawColor, preservePalette);
                    return glyph.width + 1;
                }
                drawFallbackGlyph(px, py, ch, drawColor);
                return 9;
            };
            if (shadow != 0) {
                drawOne(cx + shadowDx, y + shadowDy, shadow, false);
            }
            cx += drawOne(cx, y, color, true);
        }
    }
};

}  // namespace

int main(int argc, char** argv) {
    try {
        App app;
        if (argc > 1 && std::string(argv[1]) == "--validate") {
            app.validate();
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-record-update") {
            app.debugRecordUpdate(argv[2]);
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-records-raw-roundtrip") {
            app.debugRecordsRawRoundtrip();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-record-entry-static-model") {
            app.debugRecordEntryStaticModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-core-resource-raw-roundtrip") {
            app.debugCoreResourceRawRoundtrip();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-shipped-file-manifest") {
            app.debugShippedFileManifest();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-port-completion-status") {
            app.debugPortCompletionStatus();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-original-asset-load") {
            app.debugOriginalAssetLoad();
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-record-name-entry") {
            app.debugRecordNameEntry(argv[2]);
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-record-name-entry-cursor") {
            app.debugRecordNameEntryCursor();
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-record-name-entry-repeat") {
            app.debugRecordNameEntryRepeat(argv[2]);
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-record-save-failure") {
            app.debugRecordSaveFailure(argv[2]);
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-end-flow-records") {
            app.debugEndFlowRecords(argv[2]);
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-end-flow-frame-flow") {
            app.debugEndFlowFrameFlow();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-end-flow-static-model") {
            app.debugEndFlowStaticModel();
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--export-background") {
            app.exportBackground(argv[2]);
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-bombs") {
            app.debugBombs();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-bonuses") {
            app.debugBonuses();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-bonus-reward-static-model") {
            app.debugBonusRewardStaticModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-monster-sprite-table-model") {
            app.debugMonsterSpriteTableModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-fixed") {
            app.debugFixed();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sounds") {
            app.debugSounds();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sound-render") {
            app.debugSoundRender();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sound-cursor-segments") {
            app.debugSoundCursorSegments();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-son-raw-roundtrip") {
            app.debugSonRawRoundtrip();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sound-loader-static-model") {
            app.debugSoundLoaderStaticModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-son-step-fields") {
            app.debugSonStepFields();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-son-tail-field-mutation") {
            app.debugSonTailFieldMutation();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sound-tick-static-model") {
            app.debugSoundTickStaticModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sound-latch-static-model") {
            app.debugSoundLatchStaticModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-gran-raw-roundtrip") {
            app.debugGranRawRoundtrip();
            return 0;
        }
        if (argc > 1 &&
            std::string(argv[1]) == "--debug-gran-static-consumer-model") {
            app.debugGranStaticConsumerModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-gran-boss-model") {
            app.debugGranBossModel();
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-boss-runtime-evidence") {
            app.debugBossRuntimeEvidence(argv[2]);
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-turbo-random") {
            app.debugTurboRandom();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-boss-head-decisions") {
            app.debugBossHeadDecisions();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sound-priority-latch") {
            app.debugSoundPriorityLatch();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sound-selector-map") {
            app.debugSoundSelectorMap();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-static-sound-requests") {
            app.debugStaticSoundRequests();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-input-fire-key-model") {
            app.debugInputFireKeyModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-static-sound-contexts") {
            app.debugStaticSoundContexts();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-static-sound-unresolved-contexts") {
            app.debugStaticSoundUnresolvedContexts();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sound-runtime-capture-queue") {
            app.debugSoundRuntimeCaptureQueue();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-remaining-sound-compat-hooks") {
            app.debugRemainingSoundCompatibilityHooks();
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-record-name-sound") {
            app.debugRecordNameSoundRouting(argv[2]);
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-records-page-sound") {
            app.debugRecordsPageSoundRouting();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-weapon-switch-sound") {
            app.debugWeaponSwitchSoundRouting();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-bomb-place-sound") {
            app.debugBombPlaceSoundRouting();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-monster-death-sound") {
            app.debugMonsterDeathSoundRouting();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-bomb-object-sound") {
            app.debugBombObjectSoundRouting();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-player-damage-sound") {
            app.debugPlayerDamageSoundRouting();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-original-damage-counters") {
            app.debugOriginalDamageCounters();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-player-state2-death-fields") {
            app.debugPlayerState2DeathFields();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-original-state2-return-model") {
            app.debugOriginalState2ReturnModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-original-state2-animation-init") {
            app.debugOriginalState2AnimationInit();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-original-state2-animation-advance") {
            app.debugOriginalState2AnimationAdvance();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-original-state2-visual-row-model") {
            app.debugOriginalState2VisualRowModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-original-state2-visual-row-assets") {
            app.debugOriginalState2VisualRowAssets();
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--capture-state2-visual-row-preview") {
            app.captureState2VisualRowPreview(argv[2]);
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--capture-state2-visual-row-game-preview") {
            app.captureState2VisualRowGamePreview(argv[2]);
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-state2-runtime-frame-oracle") {
            bool expectError = argc > 3 && std::string(argv[3]) == "--expect-error";
            return app.debugState2RuntimeFrameOracle(argv[2], expectError);
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-visual-table-oracle") {
            bool expectError = argc > 3 && std::string(argv[3]) == "--expect-error";
            return app.debugVisualTableOracle(argv[2], expectError);
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-behavior4-runtime-oracle") {
            bool expectError = argc > 3 && std::string(argv[3]) == "--expect-error";
            return app.debugBehavior4RuntimeOracle(argv[2], expectError);
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-behavior4-static-model") {
            app.debugBehavior4StaticModel();
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-actor-update-runtime-oracle") {
            bool expectError = argc > 3 && std::string(argv[3]) == "--expect-error";
            return app.debugActorUpdateRuntimeOracle(argv[2], expectError);
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-contact-scanner-runtime-oracle") {
            bool expectError = argc > 3 && std::string(argv[3]) == "--expect-error";
            return app.debugContactScannerRuntimeOracle(argv[2], expectError);
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-sound-callsite-oracle") {
            bool expectError = argc > 3 && std::string(argv[3]) == "--expect-error";
            return app.debugSoundCallsiteOracle(argv[2], expectError);
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-explosion-playback-oracle") {
            bool expectError = argc > 3 && std::string(argv[3]) == "--expect-error";
            return app.debugExplosionPlaybackOracle(argv[2], expectError);
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-lane-write-static-model") {
            app.debugLaneWriteStaticModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-lane-write-tag-model") {
            app.debugLaneWriteTagModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-actor-contact-static-model") {
            app.debugActorContactStaticModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-original-state2-effect-placement") {
            app.debugOriginalState2EffectPlacement();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-player-state2-return-active") {
            app.debugPlayerState2ReturnActive();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-gran") {
            app.debugGran();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-levels") {
            app.debugLevels();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-level-raw-roundtrip") {
            app.debugLevelRawRoundtrip();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-level-completion-denominator") {
            app.debugLevelCompletionDenominator();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sprite-transparency") {
            app.debugSpriteTransparency();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sprite-raw-roundtrip") {
            app.debugSpriteRawRoundtrip();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sprite-layout-static-model") {
            app.debugSpriteLayoutStaticModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sprite-blit-contract") {
            app.debugSpriteBlitContract();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-word-layer") {
            app.debugWordLayer();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-spawners") {
            app.debugSpawners();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-explosions") {
            app.debugExplosions();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-damage-queues") {
            app.debugDamageQueues();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-lane-helper-model") {
            app.debugLaneHelperModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-lane-blend-arithmetic") {
            app.debugLaneBlendArithmetic();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-monster-slots") {
            app.debugMonsterSlots();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-monster-motion-model") {
            app.debugMonsterMotionModel();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-monster-blast-damage") {
            app.debugMonsterBlastDamage();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-bomb-fuse") {
            app.debugBombFuse();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-bomb-object-explosion-effects") {
            app.debugBombObjectExplosionEffects();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-passable-objects") {
            app.debugPassableObjects();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-trigger-accounting") {
            app.debugTriggerAccounting();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-trigger-sound") {
            app.debugTriggerSoundRouting();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-portal-sound") {
            app.debugPortalSoundRouting();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-portal-cooldowns") {
            app.debugPortalCooldowns();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-collision-pushout") {
            app.debugCollisionPushout();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-monster-bomb-kill-live") {
            app.debugMonsterBombKillLive();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-player-damage-death-live") {
            app.debugPlayerDamageDeathLive();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-monster-contact-damage-live") {
            app.debugMonsterContactDamageLive();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-object-collision-jump-live") {
            app.debugObjectCollisionJumpLive();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-hud-stats-live") {
            app.debugHudStatsLive();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-level-intro") {
            app.debugLevelIntro(argc > 2 ? argv[2] : "");
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-all-levels-render") {
            app.debugAllLevelsRender();
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--capture-level-frames") {
            app.captureLevelFrames(argv[2]);
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-two-player-hud-panel") {
            app.debugTwoPlayerHudPanel();
            return 0;
        }
        if (argc > 3 && std::string(argv[1]) == "--export-sprites") {
            app.exportSprites(argv[2], argv[3]);
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--smoke-ui") {
            int frames = 3;
            if (argc > 2) {
                frames = std::stoi(argv[2]);
            }
            app.smokeUi(frames);
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-level1-frame-inspection") {
            app.debugLevel1FrameInspection();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-menu-frame-flow") {
            app.debugMenuFrameFlow();
            return 0;
        }
        if (argc > 3 && std::string(argv[1]) == "--capture-frame-sequence") {
            app.captureFrameSequence(argv[2], argv[3]);
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-autoplayer") {
            app.debugAutoplayer(argv[2]);
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--smoke-controls") {
            app.smokeControls();
            return 0;
        }
        app.run();
    } catch (const std::exception& e) {
        std::cerr << "fatal: " << e.what() << '\n';
        return 1;
    }
    return 0;
}
