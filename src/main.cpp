#include <SDL.h>

#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <cstddef>
#include <cstdint>
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
#include <vector>

namespace {

constexpr int kScreenW = 320;
constexpr int kScreenH = 200;
constexpr int kBackgroundW = 321;
constexpr int kBackgroundH = 388;
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
constexpr int kCollisionPushoutLimit = 1024;
constexpr int kAudioSampleRate = 22050;
constexpr int kAudioToneSamples = kAudioSampleRate / 28;
constexpr size_t kSoundStepSize = 6;
constexpr uint16_t kSoundStopPeriod = 0x7530;
constexpr uint16_t kDirectSoundThreshold = 0xea60;
constexpr uint16_t kDirectSoundPeriodBase = 0xea42;
constexpr std::array<uint16_t, 6> kCompatibilitySoundCursors{
    0x0000, 0x0008, 0x0012, 0x001a, 0x0021, 0x0027,
};
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
constexpr uint16_t kPlayerDamageSoundCursor = 0x002d;
constexpr uint8_t kPlayerDamageSoundPriority = 4;
constexpr uint16_t kPlayerDeathSoundCursor = 0x0056;
constexpr uint8_t kPlayerDeathSoundPriority = 5;

struct Rgb {
    uint8_t r = 0;
    uint8_t g = 0;
    uint8_t b = 0;
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
    uint16_t soundOffset = 0xea74;
    uint8_t soundSelector = 4;
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
};

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

std::vector<Record> loadRecords(const std::string& path) {
    auto json = readTextFile(path);
    std::vector<Record> records;
    auto recordObjects = extractObjectArray(json, "records");
    for (const auto& recJson : recordObjects) {
        Record r;
        r.score = static_cast<uint32_t>(extractInt(recJson, "score"));
        r.level = static_cast<uint8_t>(extractInt(recJson, "level"));
        r.name = extractString(recJson, "decoded_name", "nessuno");
        records.push_back(r);
    }
    return records;
}

std::string encodeRecordName(const std::string& name) {
    std::string out = name.empty() ? "PLAYER" : name;
    out.resize(8, ':');
    for (char& ch : out) {
        if (ch == ' ') ch = ':';
    }
    return out;
}

void saveRecords(const std::string& path, const std::vector<Record>& records) {
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
        std::string name = encodeRecordName(records[i].name);
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
            records[i].name != before[i].name) {
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
        bool p2Left = false;
        bool p2Right = false;
        bool p2Jump = false;
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
    void load() {
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

    void run() {
        load();
        initSdl();
        resetLevel(0);
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
        int player2BombX = static_cast<int>(player2_.x + 6.0f) / 8;
        int player2BombY = static_cast<int>(player2_.y + 12.0f) / 8;
        int player1SmallBombs = bombInventory_.counts[0];
        int player2SmallBombs = bombInventory2_.counts[0];
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.size() != twoPlayerBombs + 1 ||
            bombs_.back().x != player2BombX || bombs_.back().y != player2BombY) {
            throw std::runtime_error("N key did not place player 2 bomb in two-player mode");
        }
        if (bombInventory_.counts[0] != player1SmallBombs ||
            bombInventory2_.counts[0] != player2SmallBombs - 1) {
            throw std::runtime_error("N key did not consume player 2 inventory only");
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
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (!player2Dead_ || energy2_ != 100 ||
            bombs_.size() != beforePlayer2ReentryBombs || damageCooldown2_ != 0) {
            throw std::runtime_error("N key bypassed player 2 state-2 death gate");
        }
        for (int i = 0; i < kDeathStateTicks; ++i) {
            updateReentry(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_, 2,
                          playerDead_);
        }
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (player2Dead_ || energy2_ != 100 || lives2_ != 2 ||
            bombs_.size() != beforePlayer2ReentryBombs || damageCooldown2_ <= 0) {
            throw std::runtime_error("N key did not reenter player 2 after death");
        }
        size_t afterPlayer2ReentryBombs = bombs_.size();
        int player2BombsAfterReentry = bombInventory2_.counts[0];
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.size() != afterPlayer2ReentryBombs + 1 ||
            bombInventory2_.counts[0] != player2BombsAfterReentry - 1) {
            throw std::runtime_error("N key did not fire for player 2 after reentry");
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
        pushKeyDown(SDLK_n);
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

        bool background = showBackground_;
        pushKeyDown(SDLK_s);
        processEvents(running);
        if (showBackground_ == background) {
            throw std::runtime_error("background toggle key did not change state");
        }

        int viewWidth = gameplayViewWidth_;
        pushKeyDown(SDLK_r);
        processEvents(running);
        if (gameplayViewWidth_ >= viewWidth) {
            throw std::runtime_error("R key did not reduce playfield width");
        }

        pushKeyDown(SDLK_e);
        processEvents(running);
        if (gameplayViewWidth_ != viewWidth) {
            throw std::runtime_error("E key did not restore playfield width");
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
        std::cout << "control_smoke=ok\n";
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
            int p1Dead = 0;
            int p2x = -1;
            int p2y = -1;
            int p2BombX = -1;
            int p2BombY = -1;
            int p2Dead = 0;
            size_t bombs = 0;
            size_t flashes = 0;
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
                     << " p1_dead=" << frame.p1Dead
                     << " p2_xy=" << frame.p2x << ',' << frame.p2y
                     << " p2_bomb_tile=" << frame.p2BombX << ',' << frame.p2BombY
                     << " p2_dead=" << frame.p2Dead
                     << " bombs=" << frame.bombs
                     << " flashes=" << frame.flashes
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

    void debugAutoplayer(const std::string& scenario) {
        if (scenario == "level1_bomb_route") {
            debugAutoplayerLevel1BombRoute(scenario);
        } else if (scenario == "death_reentry") {
            debugAutoplayerDeathReentry(scenario);
        } else if (scenario == "death_visuals") {
            debugAutoplayerDeathVisuals(scenario);
        } else if (scenario == "level_transition") {
            debugAutoplayerLevelTransition(scenario);
        } else if (scenario == "portal_weapon_route") {
            debugAutoplayerPortalWeaponRoute(scenario);
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
        } else if (scenario == "collapse_playback_route") {
            debugAutoplayerCollapsePlaybackRoute(scenario);
        } else if (scenario == "two_player_route") {
            debugAutoplayerTwoPlayerRoute(scenario);
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

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " death_state_ticks=" << kDeathStateTicks
                  << " lives=" << lives_
                  << " energy=" << energy_
                  << " reentered=1 frame_inspection=1\n";
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

        FrameInspection deathStartFrame =
            inspectRenderedFrame("autoplayer-death-visual-frame-4a");
        if (deathStartFrame.hash == startFrame.hash) {
            throw std::runtime_error("death visual initial frame did not change rendering");
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

        std::cout << "autoplayer=ok"
                  << " scenario=" << scenario
                  << " death_state_ticks=" << kDeathStateTicks
                  << " start_frame=0x" << std::hex << static_cast<int>(kState2VisualStartFrame)
                  << " tick1_frame=0x" << static_cast<int>(kState2VisualStartFrame + 1)
                  << " tick5_frame=0x" << static_cast<int>(kState2VisualStartFrame + 2)
                  << std::dec
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
        updateWithControls(switchControls, 1.0f / 60.0f);
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
                  << " portal_key=" << portalKey
                  << " portal_from=" << sourceX << ',' << sourceY
                  << " portal_to=" << destination->x << ',' << destination->y
                  << " cooldown=" << portalCooldown_
                  << " frame_inspection=1\n";
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
            lastPumpedSoundOffset_ != 0x0008 || lastPumpedSoundSelector_ != 5) {
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
        updateWithControls(switchControls, 1.0f / 60.0f);
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
            lastPumpedSoundOffset_ != 0x0008 || lastPumpedSoundSelector_ != 5) {
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
        updateWithControls(switchControls, 1.0f / 60.0f);
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
        placeBombAt(player2_, bombInventory2_, 2);
        if (bombs_.size() != bombsBefore + 1 || bombs_.back().owner != 2 ||
            bombs_.back().x != bombTileX || bombs_.back().y != bombTileY ||
            bombInventory2_.counts[0] != p2SmallBefore - 1) {
            throw std::runtime_error("two-player autoplayer did not place player 2 bomb");
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
                  << " bombs=1 frame_inspection=1\n";
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
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (player2Dead_ || lives2_ != 2 || energy2_ != 100 ||
            damageCooldown2_ <= 0 || state2Visual2_.active) {
            throw std::runtime_error("two-player progression did not reenter player 2");
        }
        FrameInspection reentryFrame = inspectRenderedFrame("autoplayer-two-progress-reentry");
        if (reentryFrame.hash == p2DeathFrame.hash) {
            throw std::runtime_error("two-player progression reentry frame did not change");
        }

        size_t bombsBefore = bombs_.size();
        int p2SmallBefore = bombInventory2_.counts[0];
        int p2BombX = static_cast<int>(player2_.x + 6.0f) / kTileSize;
        int p2BombY = static_cast<int>(player2_.y + 12.0f) / kTileSize;
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (bombs_.size() != bombsBefore + 1 || bombs_.back().owner != 2 ||
            bombs_.back().x != p2BombX || bombs_.back().y != p2BombY ||
            bombInventory2_.counts[0] != p2SmallBefore - 1) {
            throw std::runtime_error("two-player progression did not place p2 bomb after reentry");
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
        bool changed = insertRecord(testRecords, {999999u, 9u, "TEST"});
        if (!changed) {
            throw std::runtime_error("test record was not inserted");
        }
        saveRecords(path, testRecords);
        auto reloaded = loadRecords(path);
        if (reloaded.empty() || reloaded[0].score != 999999u ||
            reloaded[0].level != 9u || reloaded[0].name != "TEST") {
            throw std::runtime_error("saved test record did not round-trip");
        }
        std::cout << "record_update=ok top=" << reloaded[0].score
                  << " level=" << static_cast<int>(reloaded[0].level)
                  << " name=" << reloaded[0].name << '\n';
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
            if (data.size() < 768) {
                throw std::runtime_error("SFONLEF.ZBG raw file is too small");
            }
            size_t off = 768;
            while (off < data.size()) {
                uint8_t cmd = data[off++];
                if (cmd >= 0xc0) {
                    if (off >= data.size()) {
                        throw std::runtime_error("SFONLEF.ZBG raw RLE run is truncated");
                    }
                    pixels.insert(pixels.end(), cmd & 0x3f, data[off++]);
                } else {
                    pixels.push_back(cmd);
                }
            }
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
            backgroundPixelMetrics.sum != 12770002 ||
            backgroundPixelMetrics.xorValue != 0xd2 ||
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

    void debugRecordNameEntry(const std::string& path) {
        load();
        recordPath_ = path;
        saveRecords(recordPath_, records_);
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
        std::string savedText = readTextFile(path);
        if (savedText.find("\"encoded_name\": \"test::::\"") == std::string::npos) {
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
        savedText = readTextFile(path);
        if (capped.empty() || capped[0].score != 1000000u ||
            capped[0].name != "ab cdefg" ||
            savedText.find("\"encoded_name\": \"ab:cdefg\"") == std::string::npos) {
            throw std::runtime_error("name-entry cap or space encoding changed");
        }
        std::cout << "record_name_entry=ok top=" << reloaded[0].score
                  << " name=" << reloaded[0].name
                  << " padded=test:::: capped=" << capped[0].name
                  << " encoded_space=ab:cdefg\n";
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
        if (!soundLatch_.active || soundLatch_.latchedOffset != 0x0008 ||
            soundLatch_.currentSelector != 5 || soundLatch_.directSweep) {
            throw std::runtime_error("bonus pickup did not queue recovered sound cursor");
        }
        pumpSoundLatch();
        if (soundLatch_.active || lastPumpedSoundOffset_ != 0x0008 ||
            lastPumpedSoundSelector_ != 5) {
            throw std::runtime_error("bonus pickup sound cursor did not pump");
        }
        std::cout << "bonuses=ok sprites=" << spriteScores.size()
                  << " rain=" << bonusDrops_.size()
                  << " sound_cursor=0x8 sound_priority=5\n";
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
            uint8_t unknown4 = 0;
            uint8_t unknown5 = 0;
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
        int unknownPairNonzeroSteps = 0;
        for (size_t i = 0; i < sounds_.stepCount; ++i) {
            StepFields fields = step(i);
            if (fields.periodWord == kSoundStopPeriod) {
                stopCursors.push_back(static_cast<uint16_t>(i + 1));
            }
            if (fields.unknown4 != 0 || fields.unknown5 != 0) {
                ++unknownPairNonzeroSteps;
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
                      << " unknown4=" << hex2(fields.unknown4)
                      << " unknown5=" << hex2(fields.unknown5)
                      << " stop=" << (fields.periodWord == kSoundStopPeriod ? 1 : 0)
                      << '\n';
        };

        std::cout << "son_step_fields=summary steps=" << sounds_.stepCount
                  << " step_size=" << kSoundStepSize
                  << " stop_sentinels=" << stopCursors.size()
                  << " unknown_pair_nonzero_steps=" << unknownPairNonzeroSteps
                  << " period_word=bytes0-1"
                  << " gate_tick=byte2"
                  << " period_ticks=byte3"
                  << " unknown4=byte4"
                  << " unknown5=byte5\n";
        printStep("first", 0);
        printStep("first_stop", stopCursors.front() - 1);
        printStep("final_stop", stopCursors.back() - 1);
        std::cout << "son_step_fields=ok steps=" << sounds_.stepCount
                  << " first_period=" << hex4(step(0).periodWord)
                  << " first_stop_cursor=" << hex4(stopCursors.front())
                  << " final_stop_cursor=" << hex4(stopCursors.back())
                  << " unknown_pair_nonzero_steps=" << unknownPairNonzeroSteps
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
        int unknownPairNonzeroSteps = 0;
        int mutatedSteps = 0;
        for (size_t step = 0; step < sounds_.stepCount; ++step) {
            size_t off = step * kSoundStepSize;
            if (sounds_.payload[off + 4] != 0 || sounds_.payload[off + 5] != 0) {
                ++unknownPairNonzeroSteps;
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
                  << " unknown_pair_nonzero_steps=" << unknownPairNonzeroSteps
                  << " ignored_tail_bytes=4,5\n";
    }

    void debugGranRawRoundtrip() {
        load();
        auto rawBytes = readFile("GRAN.MST");
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
        if (gran_.recordSize != kGranRecordSize ||
            gran_.records.size() != kExpectedGranRecords) {
            throw std::runtime_error("GRAN.MST JSON shape mismatch");
        }

        std::vector<uint8_t> jsonPayload;
        jsonPayload.reserve(kExpectedGranPayloadSize);
        for (const GranRecord& record : gran_.records) {
            if (record.bytes.size() != kGranRecordSize) {
                throw std::runtime_error("GRAN.MST JSON record length mismatch");
            }
            jsonPayload.insert(jsonPayload.end(), record.bytes.begin(), record.bytes.end());
        }
        if (jsonPayload.size() != rawBytes.size() ||
            !std::equal(jsonPayload.begin(), jsonPayload.end(), rawBytes.begin())) {
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
                  << " record_size=" << gran_.recordSize
                  << " records=" << kExpectedGranRecords
                  << " payload_size=" << jsonPayload.size()
                  << " json_records=" << gran_.records.size()
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
        printCase("inactive_accept", latchSoundRequest(0xea74, 4));
        printCase("lower_rejected", latchSoundRequest(0xea7e, 2));
        printCase("same_refresh", latchSoundRequest(0xea88, 4));
        printCase("higher_replaces", latchSoundRequest(0xeace, 7));
        printCase("one_below_high_rejected", latchSoundRequest(0xea88, 6));
        clearSoundLatch();
        printCase("cleared_accepts", latchSoundRequest(0xea7e, 1));

        if (!soundLatch_.active || soundLatch_.currentSelector != 1 ||
            soundLatch_.latchedOffset != 0xea7e || !soundLatch_.directSweep) {
            throw std::runtime_error("sound latch final state mismatch");
        }
        pumpSoundLatch();
        if (soundLatch_.active || lastPumpedSoundRecord_ != 1 ||
            lastPumpedSoundOffset_ != 0xea7e || lastPumpedSoundSelector_ != 1) {
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
        if (!isDirectSoundSweep(0xea74) || !isDirectSoundSweep(0xea7e) ||
            !isDirectSoundSweep(0xea88) || !isDirectSoundSweep(0xeace) ||
            soundIndexForOffsetFallback(0xea74, 4) != 0 ||
            soundIndexForOffsetFallback(0xea7e, 5) != 1 ||
            soundIndexForOffsetFallback(0xea88, 6) != 2 ||
            soundIndexForOffsetFallback(0xeace, 7) != 3) {
            throw std::runtime_error("explosion selector map mismatch");
        }
        std::cout << "sound_selector_map=ok\n";
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
        auto bareHex2 = [](uint8_t value) {
            std::ostringstream oss;
            oss << std::hex << std::nouppercase << std::setw(2)
                << std::setfill('0') << static_cast<int>(value);
            return oss.str();
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
                  << " draw_offset_candidate=16,16"
                  << " row2_constant=0x7d"
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
            int candidateSprite = 0;
            std::string currentFile;
            std::string candidateFile;
            FrameInspection currentInspection;
            FrameInspection candidateInspection;
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
        auto renderGamePreview = [&](const std::string& file, bool rowCandidate) {
            state2VisualRowCandidatePreview_ = rowCandidate;
            drawGame();
            FrameInspection inspection = inspectBuffer(file);
            writeArgbPpm(joinPath(outDir, file), fb_, kScreenW, kScreenH);
            return inspection;
        };

        std::vector<GamePreviewFrame> previews;
        std::ostringstream currentSequence;
        std::ostringstream candidateSequence;
        int candidateMinusCurrent = 0;
        bool candidateHashMismatch = true;
        for (uint8_t frame = kState2VisualStartFrame;
             frame <= kState2VisualEndFrame; ++frame) {
            State2VisualRow row;
            if (!originalState2VisualRow(frame, row)) {
                throw std::runtime_error("state-2 visual game preview row missing");
            }
            GamePreviewFrame preview;
            preview.visualFrame = frame;
            preview.currentSprite = static_cast<int>(frame);
            preview.candidateSprite = static_cast<int>(row.row3);
            if (frame == kState2VisualStartFrame) {
                candidateMinusCurrent = preview.candidateSprite - preview.currentSprite;
            } else {
                currentSequence << ',';
                candidateSequence << ',';
            }
            currentSequence << preview.currentSprite;
            candidateSequence << preview.candidateSprite;

            state2Visual_.current = frame;
            state2Visual_.first = kState2VisualStartFrame;
            state2Visual_.last = kState2VisualEndFrame;
            state2Visual_.counter = kState2VisualDelay;
            state2Visual_.delay = kState2VisualDelay;
            state2Visual_.active = true;
            std::string frameSuffix = bareHex2(frame);
            preview.currentFile = "state2_game_current_" + frameSuffix + ".ppm";
            preview.candidateFile = "state2_game_row3_" + frameSuffix + ".ppm";
            preview.currentInspection =
                renderGamePreview(preview.currentFile, false);
            preview.candidateInspection =
                renderGamePreview(preview.candidateFile, true);
            candidateHashMismatch =
                candidateHashMismatch &&
                preview.currentInspection.hash != preview.candidateInspection.hash;
            previews.push_back(std::move(preview));
        }
        state2VisualRowCandidatePreview_ = false;

        std::ofstream manifest(joinPath(outDir, "manifest.txt"));
        if (!manifest) {
            throw std::runtime_error("cannot create " + joinPath(outDir, "manifest.txt"));
        }
        manifest << "scenario=state2_visual_row_game_preview\n";
        manifest << "source=lezac_cpp\n";
        manifest << "bank=BOMOMIMK\n";
        manifest << "candidate_renderer=debug_only\n";
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
                     << " candidate_sprite=" << preview.candidateSprite
                     << " candidate_file=" << preview.candidateFile
                     << " candidate_hash=" << hex64(preview.candidateInspection.hash)
                     << " candidate_changed_pixels="
                     << preview.candidateInspection.changedPixels << '\n';
        }

        std::cout << "state2_visual_row_game_preview=ok"
                  << " frames=" << previews.size()
                  << " outputs=" << (previews.size() * 2)
                  << " current_sprites=" << currentSequence.str()
                  << " candidate_sprites=" << candidateSequence.str()
                  << " candidate_minus_current=" << candidateMinusCurrent
                  << " candidate_hash_mismatch=" << (candidateHashMismatch ? 1 : 0)
                  << " candidate_renderer=debug_only"
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
                    records[parsed.first] = parsed.second;
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
            auto visualIt = records.find("visual");
            auto effectBeforeIt = records.find("effect_before");
            auto effectAfterIt = records.find("effect_after");
            if (actorIt == records.end()) fail("actor_missing");
            if (visualIt == records.end()) fail("visual_missing");
            if (effectBeforeIt == records.end()) fail("effect_before_missing");
            if (effectAfterIt == records.end()) fail("effect_after_missing");

            const auto& actor = actorIt->second;
            const auto& visual = visualIt->second;
            const auto& effectBefore = effectBeforeIt->second;
            const auto& effectAfter = effectAfterIt->second;
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
            uint8_t visualFrame = static_cast<uint8_t>(
                parseHex16(requireField(visual, "frame", "visual"),
                           "visual.frame"));
            if (visualFrame != animCurrent) {
                fail("visual_frame_mismatch actor=" + hex2(animCurrent) +
                     " visual=" + hex2(visualFrame));
            }
            constexpr uint16_t kFrameEntryBase = 0xc322;
            uint16_t rowAddress = parseHex16(requireField(visual, "row_addr", "visual"),
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
                parseRowBytes(requireField(visual, "row", "visual"), "visual.row");

            auto requireByte = [&](uint16_t address) -> uint8_t {
                if (!present[address]) {
                    fail("missing_byte address=" + bareHex4(address));
                }
                return memory[address];
            };
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

            std::string bank = normalizeBank(requireField(visual, "bank", "visual"));
            int spriteIndex = parseInt(requireField(visual, "sprite_index", "visual"),
                                       "visual.sprite_index");
            if (spriteIndex < 0 || spriteIndex >= bankCount(bank)) {
                fail("sprite_index_out_of_range bank=" + bank +
                     " index=" + std::to_string(spriteIndex));
            }
            std::string spriteSource =
                visual.count("sprite_source") ? visual.at("sprite_source") : "runtime";
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
                spriteSource != "runtime_draw_call" && spriteSource != "static_table") {
                fail("bad_sprite_source value=" + spriteSource);
            }
            int drawDx = parseInt(requireField(visual, "draw_dx", "visual"),
                                  "visual.draw_dx");
            int drawDy = parseInt(requireField(visual, "draw_dy", "visual"),
                                  "visual.draw_dy");

            int effectBeforeSlot = parseInt(
                requireField(effectBefore, "slot", "effect_before"),
                "effect_before.slot");
            int effectAfterSlot = parseInt(
                requireField(effectAfter, "slot", "effect_after"),
                "effect_after.slot");
            if (effectBeforeSlot != effectAfterSlot) {
                fail("effect_slot_changed before=" + std::to_string(effectBeforeSlot) +
                     " after=" + std::to_string(effectAfterSlot));
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
            if (effectBeforeFrame != visualFrame) {
                fail("effect_before_frame_mismatch expected=" + hex2(visualFrame) +
                     " actual=" + hex2(effectBeforeFrame));
            }

            std::cout << "visual_table_oracle=ok fixture=" << fixture
                      << " scenario=" << scenario
                      << " runtime_cs=" << hex4(runtimeCs)
                      << " runtime_ds=" << hex4(runtimeDs)
                      << " actor_slot=" << actorSlot
                      << " actor_state=" << actorState
                      << " anim_current=" << hex2(animCurrent)
                      << " anim_range=" << hex2(animFirst) << ".." << hex2(animLast)
                      << " anim_mode=" << animMode
                      << " visual_frame=" << hex2(visualFrame)
                      << " row_addr=" << hex4(rowAddress)
                      << " row=" << rowString(memoryRow)
                      << " bank=" << bank
                      << " sprite_index=" << spriteIndex
                      << " sprite_source=" << spriteSource
                      << " draw_offset=" << drawDx << ',' << drawDy
                      << " effect_slot=" << effectBeforeSlot
                      << " effect_before_xy=" << hex4(effectBeforeX) << ','
                      << hex4(effectBeforeY)
                      << " effect_after_xy=" << hex4(effectAfterX) << ','
                      << hex4(effectAfterY)
                      << " effect_after_frame=" << hex2(effectAfterFrame)
                      << " breaks=" << breakCount
                      << " temp_copy=" << (tempCopy ? 1 : 0)
                      << " visual_claim=0\n";
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

        std::cout << "player_state2_return_active=ok p1_death_timer=60"
                  << " p1_after_59=1 p1_after_60=0"
                  << " gate0_dead=1 gate0_energy=100"
                  << " gate1_reentered=1 p1_energy=100"
                  << " p1_cooldown=" << kDamageCooldownTicks
                  << " p1_death_timer_clear=0 p1_reentry_timer_clear=0"
                  << " p2_gate1_reentered=1 p2_energy=100"
                  << " p2_cooldown=" << kDamageCooldownTicks
                  << " p2_death_timer_clear=0 p2_reentry_timer_clear=0"
                  << " no_gameover_with_p1=1\n";
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
                    updatePortalsAndTriggers(player_, portalCooldown, triggerCooldown);

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
                    updatePortalsAndTriggers(player_, portalCooldown, triggerCooldown);

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

                    updatePortalsAndTriggers(player_, portalCooldown_, triggerCooldown_);
                    updatePortalsAndTriggers(player2_, portalCooldown2_, triggerCooldown2_);
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

        FrameInspection first = inspectRenderedFrame("hud-stats-live-first");
        std::vector<uint32_t> firstPixels = fb_;
        if (!regionHasVariation(0, 0, kScreenW, 24) ||
            !regionHasVariation(48, 3, 56, 8) ||
            !regionHasVariation(154, 2, 132, 12)) {
            throw std::runtime_error("HUD stats panel did not render visible gauges/icons");
        }

        energy_ = 21;
        lives_ = 1;
        bombInventory_.selected = BombType::Super;
        bombInventory_.counts[3] = 0;
        FrameInspection second = inspectRenderedFrame("hud-stats-live-second");
        if (second.hash == first.hash ||
            !regionChanged(firstPixels, 0, 0, kScreenW, 24)) {
            throw std::runtime_error("HUD stats panel did not react to player/bomb stat changes");
        }

        std::cout << "hud_stats_live=ok"
                  << " hp_visible=1 lives_visible=1 bombs_visible=1"
                  << " progress_visible=1 frame_inspection=1\n";
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
    std::vector<BonusDrop> bonusDrops_;
    std::vector<Bomb> bombs_;
    std::vector<Flash> flashes_;
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
    bool menu_ = true;
    MenuPage menuPage_ = MenuPage::Main;
    bool showBackground_ = true;
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
    bool state2VisualRowCandidatePreview_ = false;
    int damageCooldown_ = 0;
    int damageCooldown2_ = 0;
    uint8_t pendingDamage_ = 0;
    uint8_t pendingDamage2_ = 0;
    int levelResetGeneration_ = 0;
    BombInventory bombInventory_;
    BombInventory bombInventory2_;
    bool weaponSwitchHeld_ = false;
    bool weaponSwitchHeld2_ = false;
    uint32_t logicTick_ = 0;
    uint32_t randomSeed_ = 0x1234abcd;
    uint32_t score_ = 0;
    uint32_t score2_ = 0;
    std::string recordPath_ = "RECS.DAT.json";
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
            } else if (e.type == SDL_KEYDOWN && !e.key.repeat) {
                onKey(e.key.keysym.sym, running);
            }
        }
    }

    void pushKeyDown(SDL_Keycode key) {
        SDL_Event e{};
        e.type = SDL_KEYDOWN;
        e.key.type = SDL_KEYDOWN;
        e.key.state = SDL_PRESSED;
        e.key.repeat = 0;
        e.key.keysym.sym = key;
        e.key.keysym.scancode = SDL_GetScancodeFromKey(key);
        if (SDL_PushEvent(&e) < 0) {
            throw std::runtime_error(SDL_GetError());
        }
    }

    void resetLevel(int index) {
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
        damageCooldown_ = 0;
        damageCooldown2_ = 0;
        pendingDamage_ = 0;
        pendingDamage2_ = 0;
        bombInventory_ = {};
        bombInventory2_ = {};
        weaponSwitchHeld_ = false;
        weaponSwitchHeld2_ = false;
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
                resetLevel(0);
                menu_ = false;
                menuPage_ = MenuPage::Main;
            } else if (key == SDLK_i) {
                menuPage_ = MenuPage::Info;
            } else if (key == SDLK_z) {
                menuPage_ = MenuPage::Instructions;
            } else if (key == SDLK_r) {
                menuPage_ = MenuPage::Records;
            } else if (key == SDLK_s) {
                showBackground_ = !showBackground_;
            }
        } else if (!menu_ && (key == SDLK_SPACE || key == SDLK_RCTRL)) {
            if (playerDead_) {
                tryReenterPlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                                 damageCooldown_, 1);
            } else {
                placeBombAt(player_, bombInventory_, 1);
            }
        } else if (!menu_ && key == SDLK_n) {
            if (playerCount_ > 1) {
                if (player2Dead_) {
                    tryReenterPlayer(player2_, energy2_, lives2_, player2Dead_,
                                     reentryTimer2_, damageCooldown2_, 2);
                } else {
                    placeBombAt(player2_, bombInventory2_, 2);
                }
            } else if (playerDead_) {
                tryReenterPlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                                 damageCooldown_, 1);
            } else {
                placeBombAt(player_, bombInventory_, 1);
            }
        } else if (!menu_ && key == SDLK_s) {
            showBackground_ = !showBackground_;
        } else if (!menu_ && key == SDLK_r && playerCount_ == 1) {
            adjustGameplayViewWidth(-32);
        } else if (!menu_ && key == SDLK_e && playerCount_ == 1) {
            adjustGameplayViewWidth(32);
        } else if (!menu_ && key == SDLK_F5) {
            resetLevel(levelIndex_);
        } else if (!menu_ && key == SDLK_ESCAPE) {
            menu_ = true;
            menuPage_ = MenuPage::Main;
        } else if (!menu_ && key == SDLK_PAGEUP) {
            resetLevel(levelIndex_ + 1);
        } else if (!menu_ && key == SDLK_PAGEDOWN) {
            resetLevel(levelIndex_ - 1);
        }
    }

    void handleNameEntryKey(SDL_Keycode key) {
        if (key == SDLK_RETURN || key == SDLK_KP_ENTER) {
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
        switch (offset) {
            case 0xea74: return 0;
            case 0xea7e: return 1 % sounds_.records.size();
            case 0xea88: return 2 % sounds_.records.size();
            case 0xeace: return 3 % sounds_.records.size();
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
        if (!audioEnabled_ || audioDevice_ == 0 || sounds_.records.empty()) return;
        std::vector<int16_t> samples = synthesizeSound(index % sounds_.records.size());
        if (samples.empty()) return;
        playSoundSamples(samples);
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
            case BombType::Small: return {0x0d, 58, 20};
            case BombType::Medium: return {0x0e, 59, 30};
            case BombType::Large: return {0x0f, 60, 40};
            case BombType::Super: return {0x10, 60, 200};
        }
        return {0x0d, 58, 20};
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
        switch (visualType) {
            case 1: return 0xea74;
            case 2: return 0xea7e;
            case 3: return 0xea88;
            case 4: return 0xeace;
        }
        return 0xea74;
    }

    uint8_t explosionSoundSelector(int visualType) const {
        switch (visualType) {
            case 1: return 4;
            case 2: return 5;
            case 3: return 6;
            case 4: return 7;
        }
        return 4;
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

    void updateWeaponSwitch(BombInventory& inventory, bool& held, bool pressed) {
        if (pressed && !held) {
            selectNextAvailableBomb(inventory);
        }
        held = pressed;
    }

    void update(float dt) {
        if (menu_) return;
        const uint8_t* keys = SDL_GetKeyboardState(nullptr);
        FrameControls controls;
        controls.p1Left = keys[SDL_SCANCODE_LEFT] ||
                          (playerCount_ == 1 && keys[SDL_SCANCODE_Z]);
        controls.p1Right = keys[SDL_SCANCODE_RIGHT] ||
                           (playerCount_ == 1 && keys[SDL_SCANCODE_X]);
        controls.p1Jump = keys[SDL_SCANCODE_UP] ||
                          (playerCount_ == 1 && keys[SDL_SCANCODE_M]);
        controls.p2Left = playerCount_ > 1 && keys[SDL_SCANCODE_Z];
        controls.p2Right = playerCount_ > 1 && keys[SDL_SCANCODE_X];
        controls.p2Jump = playerCount_ > 1 && keys[SDL_SCANCODE_M];
        updateWithControls(controls, dt);
    }

    void updateWithControls(const FrameControls& controls, float dt) {
        if (menu_) return;
        ++logicTick_;
        updateDamageCooldowns();
        bool p1Switch = controls.p1Left && controls.p1Right;
        bool p2Switch = controls.p2Left && controls.p2Right;
        updateWeaponSwitch(bombInventory_, weaponSwitchHeld_, p1Switch);
        if (playerCount_ > 1) {
            updateWeaponSwitch(bombInventory2_, weaponSwitchHeld2_, p2Switch);
        } else {
            weaponSwitchHeld2_ = false;
        }
        if (portalCooldown_ > 0) --portalCooldown_;
        if (triggerCooldown_ > 0) --triggerCooldown_;
        if (portalCooldown2_ > 0) --portalCooldown2_;
        if (triggerCooldown2_ > 0) --triggerCooldown2_;

        if (playerDead_) {
            updateState2VisualCursor(state2Visual_);
            updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                          playerCount_ == 1 || player2Dead_);
        } else {
            updatePlayer(player_, controls.p1Left, controls.p1Right,
                         controls.p1Jump, p1Switch,
                         playerFacing_, playerAnimTick_, dt);
            collectObjectiveTiles(player_, 1);
            updatePortalsAndTriggers(player_, portalCooldown_, triggerCooldown_);
        }
        if (playerCount_ > 1) {
            if (player2Dead_) {
                updateState2VisualCursor(state2Visual2_);
                updateReentry(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_, 2,
                              playerDead_);
            } else {
                updatePlayer(player2_, controls.p2Left, controls.p2Right,
                             controls.p2Jump, p2Switch,
                             player2Facing_, player2AnimTick_, dt);
                collectObjectiveTiles(player2_, 2);
                updatePortalsAndTriggers(player2_, portalCooldown2_, triggerCooldown2_);
            }
        }
        updateFlashes();
        updateBombs();
        updateMonsterSpawners();
        updateMonsters(dt);
        updateBonusDrops();
        drainPlayerDamageCounters();
        updateLevelCompletion();
        pumpSoundLatch();
    }

    void updateLevelCompletion() {
        if (isComplete()) {
            if (completeTimer_ == 0) playSound(5);
            if (++completeTimer_ > 100) {
                if (isFinalLevel()) {
                    beginEndRun(EndReason::CompletedGame);
                } else {
                    resetLevel(levelIndex_ + 1);
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
            player.vy = -135.0f;
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
                    playSound(0);
                }
            }
        }
    }

    void updatePortalsAndTriggers(Player& player, int& portalCooldown,
                                  int& triggerCooldown) {
        int tx = static_cast<int>(player.x + 6.0f) / 8;
        int ty = static_cast<int>(player.y + 12.0f) / 8;
        int tile = tileAt(tx, ty);
        uint16_t key = static_cast<uint16_t>(wordAt(tx, ty) & 0x7fffu);

        if (tile == 0x45 && key != 0 && portalCooldown == 0) {
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
        weaponSwitchHeld_ = false;
        weaponSwitchHeld2_ = false;
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
        randomSeed_ = randomSeed_ * 1664525u + 1013904223u;
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
        if (monster.behavior == 4) {
            if (--monster.motionTimer <= 0) {
                retargetMonster(monster);
            }
            return;
        }

        int16_t speed = groundWalkerSpeed8(monster);
        if (monster.vx8 == 0) {
            const Player& target = nearestPlayer(monster.x, monster.y);
            monster.vx8 = target.x < monster.x ? -speed : speed;
        } else {
            monster.vx8 = monster.vx8 < 0 ? -speed : speed;
        }
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
            if (monsterCollides(monster.x, monster.y)) {
                int step = monster.vx8 > 0 ? -1 : 1;
                int pushes = 0;
                while (monsterCollides(monster.x, monster.y) && pushes++ < kCollisionPushoutLimit) {
                    monster.x += step;
                }
                if (monsterCollides(monster.x, monster.y)) monster.x = oldX;
                monster.vx8 = static_cast<int16_t>(-monster.vx8 / (monster.behavior == 4 ? 2 : 1));
                monster.fracX = 0;
                if (monster.behavior == 4) monster.motionTimer = 0;
                refreshMonsterAnimationProfile(monster);
            }

            int oldY = monster.y;
            integrateAxis8_8(monster.y, monster.fracY, monster.vy8);
            if (monsterCollides(monster.x, monster.y)) {
                int step = monster.vy8 > 0 ? -1 : 1;
                int pushes = 0;
                while (monsterCollides(monster.x, monster.y) && pushes++ < kCollisionPushoutLimit) {
                    monster.y += step;
                }
                if (monsterCollides(monster.x, monster.y)) monster.y = oldY;
                monster.vy8 = monster.behavior == 4 ? static_cast<int16_t>(-monster.vy8 / 2) : 0;
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
        resetState2VisualCursor(state2VisualCursorFor(startMarker));
        player.vx = 0.0f;
        player.vy = 0.0f;
        player.grounded = false;
        if (lives <= 0) {
            dead = true;
            timer = 0;
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
        resetLevel(levelIndex_);
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
        Record record;
        record.score = pendingRecordScore_;
        record.level = pendingRecordLevel_;
        record.name = pendingRecordName_.empty() ? "PLAYER" : pendingRecordName_;
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
            playSound(2);
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
            flashes_.push_back({x, y, 12});
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
        playSound(4);
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
        requestSoundCursor(0x0008, 5);
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
        if (menu_) drawMenu();
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
        if (!showBackground_) {
            rect(0, 0, kScreenW, kScreenH, argb(palette_, 0));
            return;
        }
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

    void drawGame() {
        std::fill(fb_.begin(), fb_.end(), argb(palette_, 0));
        if (playerCount_ > 1) {
            drawWorldView(player_, 0, 16, kScreenW, 84);
            drawWorldView(player2_, 0, 116, kScreenW, 84);
            resetClip();
            drawHudBand(100, 2, energy2_, lives2_, player2Dead_,
                        bombInventory2_, score2_, false);
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
        drawBackground(drawCamX, drawCamY);
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
            drawState2PlayerVisual(player_, state2Visual_, drawCamX, drawCamY);
        }
        if (playerCount_ > 1 && !player2Dead_) {
            drawPlayer(player2_, player2Facing_, player2AnimTick_, drawCamX, drawCamY, 19);
        } else if (playerCount_ > 1 && deathStateTimer2_ > 0 &&
                   state2Visual2_.active) {
            drawState2PlayerVisual(player2_, state2Visual2_, drawCamX, drawCamY);
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

    int monsterSpriteIndex(const ActiveMonster& monster) const {
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
            int index = monsterSpriteIndex(monster);
            if (index < 0 || index >= static_cast<int>(sprites_.sprites.size())) continue;
            drawSprite(sprites_.sprites[static_cast<size_t>(index)],
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
                                int camX, int camY) {
        int x0 = static_cast<int>(player.x) - camX;
        int y0 = static_cast<int>(player.y) - camY;
        int index = static_cast<int>(cursor.current);
        if (state2VisualRowCandidatePreview_) {
            State2VisualRow row;
            if (originalState2VisualRow(cursor.current, row)) {
                index = static_cast<int>(row.row3);
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

    void drawHud() {
        drawHudBand(0, 1, energy_, lives_, playerDead_, bombInventory_, score_,
                    playerCount_ == 1);
        if (isComplete()) {
            rect(76, 84, 168, 24, 0xee000000u);
            text(92, 92, "LEVEL COMPLETED", 0xffffe060u, false, 0xff301800u);
        }
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

    void drawMenu() {
        drawBackground(0, 0);
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

    void drawInfoMenu() {
        text(119, 48, "INFOS", 0xff90ffb0u, false, 0xff101010u);
        text(38, 68, "RELEASED APR.23 1996", 0xffffffffu, false, 0xff101010u);
        text(38, 80, "ZANOBI SOFTWARE", 0xffffffffu, false, 0xff101010u);
        text(38, 92, "VGA DOS PLATFORM STRATEGY GAME", 0xffffe060u, false, 0xff101010u);
        text(38, 112, "COLLECT BONUSES AND DESTROY", 0xffffffffu, false, 0xff101010u);
        text(38, 124, "STRUCTURES WITH FOUR BOMB TYPES.", 0xffffffffu, false, 0xff101010u);
        text(38, 156, "ESC: BACK", 0xff90ffb0u, false, 0xff101010u);
    }

    void drawInstructionsMenu() {
        text(82, 48, "INSTRUCTIONS", 0xff90ffb0u, false, 0xff101010u);
        text(32, 68, "ARROWS OR Z X: MOVE", 0xffffffffu, false, 0xff101010u);
        text(32, 80, "UP OR M: JUMP", 0xffffffffu, false, 0xff101010u);
        text(32, 92, "N SPACE RCTRL: PLACE BOMB", 0xffffe060u, false, 0xff101010u);
        text(32, 104, "LEFT AND RIGHT: SWITCH BOMB", 0xffffffffu, false, 0xff101010u);
        text(32, 116, "S: BACKGROUND ON OR OFF", 0xffffffffu, false, 0xff101010u);
        text(32, 128, "E R: PLAYFIELD WIDTH", 0xffffffffu, false, 0xff101010u);
        text(32, 140, "PAGEUP PAGEDOWN: TEST LEVELS", 0xffffffffu, false, 0xff101010u);
        text(32, 156, "ESC: BACK", 0xff90ffb0u, false, 0xff101010u);
    }

    void drawRecordsMenu() {
        text(90, 48, "BEST SCORES", 0xff90ffb0u, false, 0xff101010u);
        int y = 70;
        for (size_t i = 0; i < records_.size(); ++i) {
            drawRecordLine(i, y);
            y += 12;
        }
        text(38, 166, "ESC: BACK", 0xff90ffb0u, false, 0xff101010u);
    }

    void drawNameEntryMenu() {
        text(86, 48, "NEW RECORD", 0xff90ffb0u, false, 0xff101010u);
        text(58, 64, "PLAYER " + std::to_string(pendingRecordPlayer_),
             0xffffffffu, false, 0xff101010u);
        text(58, 78, "SCORE " + std::to_string(pendingRecordScore_),
             0xffffe060u, false, 0xff101010u);
        text(58, 94, "LEVEL " + std::to_string(pendingRecordLevel_),
             0xffffffffu, false, 0xff101010u);
        std::string name = pendingRecordName_;
        while (name.size() < 8) name.push_back('_');
        text(58, 120, "NAME " + name, 0xffffffffu, false, 0xff101010u);
        text(42, 148, "TYPE LETTERS OR SPACE", 0xffffffffu, false, 0xff101010u);
        text(42, 160, "ENTER SAVE. BACKSPACE ERASES", 0xff90ffb0u, false, 0xff101010u);
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

    void text(int x, int y, const std::string& s, uint32_t color, bool large = false,
              uint32_t shadow = 0, int shadowDx = 1, int shadowDy = 1) {
        int cx = x;
        for (char raw : s) {
            char ch = raw;
            if (ch == ' ') {
                cx += large ? 8 : 5;
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
        if (argc > 1 && std::string(argv[1]) == "--debug-core-resource-raw-roundtrip") {
            app.debugCoreResourceRawRoundtrip();
            return 0;
        }
        if (argc > 2 && std::string(argv[1]) == "--debug-record-name-entry") {
            app.debugRecordNameEntry(argv[2]);
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
        if (argc > 1 && std::string(argv[1]) == "--debug-son-step-fields") {
            app.debugSonStepFields();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-son-tail-field-mutation") {
            app.debugSonTailFieldMutation();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-gran-raw-roundtrip") {
            app.debugGranRawRoundtrip();
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
        if (argc > 1 && std::string(argv[1]) == "--debug-sprite-transparency") {
            app.debugSpriteTransparency();
            return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--debug-sprite-raw-roundtrip") {
            app.debugSpriteRawRoundtrip();
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
