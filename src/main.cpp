#include <SDL.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <regex>
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
constexpr size_t kDebrisCapacity = 0x640;
constexpr size_t kCollapseCapacity = 0x00fa;
constexpr size_t kGranRecordSize = 57;
constexpr int kReentryTicks = 180;
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
    auto recordObjects = extractObjectArray(json, "records");
    for (const auto& recJson : recordObjects) {
        GranRecord record;
        record.bytes = parseHexByteList(extractString(recJson, "bytes_hex"));
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

        energy_ = 1;
        lives_ = 3;
        lives2_ = 3;
        damageCooldown_ = 0;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        int timeoutLevel = levelIndex_;
        float player2XBeforeTimeout = player2_.x;
        float player2YBeforeTimeout = player2_.y;
        for (int i = 0; i < kReentryTicks + 2; ++i) {
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

        energy2_ = 1;
        lives_ = 3;
        lives2_ = 3;
        damageCooldown2_ = 0;
        size_t beforePlayer2ReentryBombs = bombs_.size();
        damagePlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                     damageCooldown2_, 2);
        if (menu_ || !player2Dead_ || lives2_ != 2 || reentryTimer2_ <= 0 ||
            playerDead_) {
            throw std::runtime_error("player 2 death did not enter reentry state");
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

        energy2_ = 1;
        lives_ = 3;
        lives2_ = 1;
        damageCooldown2_ = 0;
        damagePlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                     damageCooldown2_, 2);
        if (menu_ || !player2Dead_ || lives2_ != 0 || lives_ != 3 || playerDead_) {
            throw std::runtime_error("player 2 zero lives ended two-player game");
        }
        size_t afterPlayer2OutBombs = bombs_.size();
        pushKeyDown(SDLK_n);
        processEvents(running);
        if (!player2Dead_ || bombs_.size() != afterPlayer2OutBombs) {
            throw std::runtime_error("player 2 reentered or fired with zero lives");
        }

        energy_ = 1;
        lives_ = 1;
        damageCooldown_ = 0;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
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

        energy_ = 1;
        lives_ = 3;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        if (!playerDead_ || lives_ != 2 || reentryTimer_ <= 0) {
            throw std::runtime_error("player death did not enter reentry state");
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
        energy_ = 1;
        lives_ = 3;
        damageCooldown_ = 0;
        damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                     damageCooldown_, 1);
        pushKeyDown(SDLK_SPACE);
        processEvents(running);
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
        if (energy_ >= 100) {
            throw std::runtime_error("active debris did not drain player energy");
        }
        int afterDebrisEnergy = energy_;
        updateFlashes();
        if (energy_ != afterDebrisEnergy) {
            throw std::runtime_error("damage cooldown did not block repeated debris damage");
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
            draw();
            if (std::all_of(fb_.begin(), fb_.end(),
                            [&](uint32_t px) { return px == fb_.front(); })) {
                throw std::runtime_error("smoke UI rendered a uniform frame");
            }
            SDL_Delay(1);
        }
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
        std::cout << "record_name_entry=ok top=" << reloaded[0].score
                  << " name=" << reloaded[0].name << '\n';
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
        std::cout << "record_save_failure=ok pending=" << pendingRecordScore_ << '\n';
    }

    void debugEndFlowRecords(const std::string& path) {
        load();
        recordPath_ = path;
        saveRecords(recordPath_, records_);

        auto containsRecord = [&](uint32_t score, const std::string& name) {
            auto reloaded = loadRecords(recordPath_);
            return std::any_of(reloaded.begin(), reloaded.end(),
                               [&](const Record& record) {
                                   return record.score == score && record.name == name;
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
                  << finalRecords.size() << '\n';
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

    void debugGran() {
        load();
        std::cout << "gran_record_size=" << gran_.recordSize
                  << " records=" << gran_.records.size()
                  << " words_per_record=" << (gran_.recordSize / 2)
                  << " trailing_byte=yes\n";
        for (size_t i = 0; i < gran_.records.size(); ++i) {
            const std::vector<uint8_t>& bytes = gran_.records[i].bytes;
            std::cout << "gran_" << (i + 1)
                      << "=bytes:" << bytes.size()
                      << " zero_bytes:" << std::count(bytes.begin(), bytes.end(), 0)
                      << " first_bytes:";
            for (size_t off = 0; off < bytes.size() && off < 12; ++off) {
                if (off != 0) std::cout << '-';
                std::cout << std::hex << std::setw(2) << std::setfill('0')
                          << static_cast<int>(bytes[off])
                          << std::dec << std::setfill(' ');
            }
            std::cout << " first_words:";
            for (size_t off = 0; off + 1 < bytes.size() && off < 12; off += 2) {
                if (off != 0) std::cout << ',';
                std::cout << std::showbase << std::hex << le16(bytes, off)
                          << std::dec << std::noshowbase;
            }
            std::cout << " last_byte=" << static_cast<int>(bytes.back()) << '\n';
        }
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
        if (rawLevels.size() != levels_.size() || rawLevels.size() != expectedOffsets.size()) {
            throw std::runtime_error("raw level count did not match JSON levels");
        }

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
                  << " triggers=" << totalTriggers << '\n';
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

    void debugWordLayer() {
        load();
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

        auto printLookup = [&](uint16_t flaggedWord) {
            DamagePhaseLookup forward = resolveDamagePhase(flaggedWord, false);
            DamagePhaseLookup reverse = resolveDamagePhase(flaggedWord, true);
            std::cout << " forward_slot=" << forward.slotIndex
                      << " forward_phase=" << static_cast<int>(forward.phase)
                      << " reverse_slot=" << reverse.slotIndex
                      << " reverse_phase=" << static_cast<int>(reverse.phase)
                      << " source=" << (forward.debris ? "debris" : "collapse");
        };

        bool printedCollapse = false;
        bool printedDebris = false;
        for (size_t levelIndex = 0; levelIndex < levels_.size() && (!printedCollapse || !printedDebris); ++levelIndex) {
            if (!printedCollapse) {
                auto pos = findWord(static_cast<int>(levelIndex), false);
                if (pos[0] >= 0) {
                    uint16_t word = wordAt(pos[0], pos[1]);
                    queueTileDamage(pos[0], pos[1], 2, 3);
                    if (!collapseQueue_.empty()) {
                        const CollapseRecord& record = collapseQueue_.back();
                        std::cout << "collapse_level=" << (levelIndex + 1)
                                  << " tile=" << pos[0] << ',' << pos[1]
                                  << " word=" << std::showbase << std::hex << word
                                  << " flagged=" << record.flaggedWord
                                  << " start_off=" << record.startOffsetBytes
                                  << " end_off=" << record.endOffsetBytes
                                  << std::dec << std::noshowbase
                                  << " count=" << record.count
                                  << " affected_bytes=" << static_cast<int>(record.affectedBytes);
                        printLookup(record.flaggedWord);
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
                        std::cout << "debris_level=" << (levelIndex + 1)
                                  << " tile=" << pos[0] << ',' << pos[1]
                                  << " tile_index=" << record.tileIndex
                                  << " word=" << std::showbase << std::hex << word
                                  << " flagged=" << record.flaggedWord
                                  << std::dec << std::noshowbase
                                  << " lookup=" << static_cast<int>(record.lookup);
                        printLookup(record.flaggedWord);
                        std::cout << '\n';
                        printedDebris = true;
                    }
                }
            }
        }
        if (!printedCollapse) std::cout << "collapse_sample=missing\n";
        if (!printedDebris) std::cout << "debris_sample=missing\n";
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
        if (spawnerStates_[spawnerIndex].availableSlots != initialSlots - 1) {
            throw std::runtime_error("monster death returned live slot before removal");
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
                  << " death_ticks=" << deathTicks << '\n';
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
        std::cout << "bomb_fuse=ok fuse=" << fuseTicks
                  << " effects=" << explosionEffects_.size()
                  << " flashes=" << flashes_.size() << '\n';

        resetLevel(0);
        menu_ = false;
        energy_ = 1;
        lives_ = 1;
        damageCooldown_ = 0;
        bombs_.clear();
        flashes_.clear();
        explosionEffects_.clear();
        int playerBombX = static_cast<int>(player_.x + 6.0f) / kTileSize;
        int playerBombY = static_cast<int>(player_.y + 12.0f) / kTileSize;
        bombs_.push_back({playerBombX, playerBombY, 1, BombType::Small, 1});
        bombs_.push_back({std::max(0, playerBombX - 4), playerBombY, 1, BombType::Small, 1});
        updateBombs();
        if (!menu_ || !bombs_.empty() || !flashes_.empty() || !explosionEffects_.empty()) {
            throw std::runtime_error("stale expired bomb exploded after reset");
        }
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
                               !isPassableObjectTile(tile)) {
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
        std::cout << "passable_objects=ok\n";
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
        bool found = false;
        for (int y = 0; y < level_.height && !found; ++y) {
            for (int x = 0; x < level_.width && !found; ++x) {
                if (!solidPixel(static_cast<float>(x * kTileSize + 1),
                                static_cast<float>(y * kTileSize + 1))) {
                    continue;
                }
                player_.x = static_cast<float>(x * kTileSize);
                player_.y = static_cast<float>(y * kTileSize);
                movePlayer(player_, 1.0f, 0.0f);

                monsters_.clear();
                ActiveMonster monster;
                monster.x = x * kTileSize;
                monster.y = y * kTileSize;
                monster.kind = 1;
                monster.behavior = 3;
                monster.alive = true;
                monster.vx8 = 0x0100;
                monster.vy8 = 0x0100;
                monster.animDelay = 1;
                monster.animStart = 43;
                monster.animEnd = 44;
                monster.animFrame = 43;
                monsters_.push_back(monster);
                updateMonsters(0.0f);
                found = true;
            }
        }
        if (!found) {
            throw std::runtime_error("no solid tile found for collision pushout");
        }
        std::cout << "collision_pushout=ok\n";
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
    int damageCooldown_ = 0;
    int damageCooldown2_ = 0;
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
        damageCooldown_ = 0;
        damageCooldown2_ = 0;
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
        int tile = tileAt(static_cast<int>(px) / kTileSize, static_cast<int>(py) / kTileSize);
        uint8_t tileByte = static_cast<uint8_t>(tile);
        return countsForDestructionProgress(tileByte, level_.objectiveTile) &&
               !isPassableObjectTile(tileByte);
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
        ++logicTick_;
        updateDamageCooldowns();
        const uint8_t* keys = SDL_GetKeyboardState(nullptr);
        bool p1Left = keys[SDL_SCANCODE_LEFT] || (playerCount_ == 1 && keys[SDL_SCANCODE_Z]);
        bool p1Right = keys[SDL_SCANCODE_RIGHT] || (playerCount_ == 1 && keys[SDL_SCANCODE_X]);
        bool p1Jump = keys[SDL_SCANCODE_UP] || (playerCount_ == 1 && keys[SDL_SCANCODE_M]);
        bool p2Left = playerCount_ > 1 && keys[SDL_SCANCODE_Z];
        bool p2Right = playerCount_ > 1 && keys[SDL_SCANCODE_X];
        bool p2Jump = playerCount_ > 1 && keys[SDL_SCANCODE_M];
        bool p1Switch = p1Left && p1Right;
        bool p2Switch = p2Left && p2Right;
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
            updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                          playerCount_ == 1 || player2Dead_);
        } else {
            updatePlayer(player_, p1Left, p1Right, p1Jump, p1Switch,
                         playerFacing_, playerAnimTick_, dt);
            collectObjectiveTiles(player_, 1);
            updatePortalsAndTriggers(player_, portalCooldown_, triggerCooldown_);
        }
        if (playerCount_ > 1) {
            if (player2Dead_) {
                updateReentry(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_, 2,
                              playerDead_);
            } else {
                updatePlayer(player2_, p2Left, p2Right, p2Jump, p2Switch,
                             player2Facing_, player2AnimTick_, dt);
                collectObjectiveTiles(player2_, 2);
                updatePortalsAndTriggers(player2_, portalCooldown2_, triggerCooldown2_);
            }
        }
        updateFlashes();
        updateMonsterSpawners();
        updateMonsters(dt);
        updateBonusDrops();
        updateBombs();
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
        if (jump && player.grounded) {
            player.vy = -135.0f;
            player.grounded = false;
        }
        player.vy = std::min(160.0f, player.vy + 360.0f * dt);
        movePlayer(player, player.vx * dt, 0.0f);
        movePlayer(player, 0.0f, player.vy * dt);
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
                damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                             damageCooldown_, 1);
            }
            if (playerCount_ > 1 && !player2Dead_ &&
                playerOverlaps(player2_, monster.x, monster.y, 14.0f, 16.0f)) {
                damagePlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                             damageCooldown2_, 2);
            }
        }
        monsters_.erase(std::remove_if(monsters_.begin(), monsters_.end(),
                                       [](const ActiveMonster& monster) { return !monster.alive; }),
                        monsters_.end());
    }

    void releaseMonsterSlot(ActiveMonster& monster) {
        if (monster.deathCredited) return;
        if (monster.spawnerIndex < spawnerStates_.size()) {
            ++spawnerStates_[monster.spawnerIndex].availableSlots;
            monster.deathCredited = true;
        }
    }

    void updateDamageCooldowns() {
        if (damageCooldown_ > 0) --damageCooldown_;
        if (damageCooldown2_ > 0) --damageCooldown2_;
    }

    void damagePlayer(Player& player, int& energy, int& lives, bool& dead,
                      int& timer, int& damageCooldown, uint8_t startMarker) {
        if (dead || damageCooldown > 0) return;
        energy = std::max(0, energy - 1);
        if (energy == 0) {
            beginPlayerDeath(player, energy, lives, dead, timer, startMarker);
        } else {
            damageCooldown = kDamageCooldownTicks;
        }
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
        if (!playerDead_ && playerOverlapsTileArea(player_, tx0, ty0, tx1, ty1)) {
            damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                         damageCooldown_, 1);
        }
        if (playerCount_ > 1 && !player2Dead_ &&
            playerOverlapsTileArea(player2_, tx0, ty0, tx1, ty1)) {
            damagePlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                         damageCooldown2_, 2);
        }
    }

    void beginPlayerDeath(Player& player, int& energy, int& lives, bool& dead,
                          int& timer, uint8_t startMarker) {
        if (lives > 0) --lives;
        player.vx = 0.0f;
        player.vy = 0.0f;
        player.grounded = false;
        if (lives == 0) {
            dead = true;
            timer = 0;
            playSound(3);
            if (allPlayersOutOfLives()) beginGameOver();
            return;
        }
        dead = true;
        timer = canReenterLevel() ? kReentryTicks : 1;
        playSound(3);
        (void)startMarker;
    }

    bool allPlayersOutOfLives() const {
        return playerCount_ <= 1 ? lives_ <= 0 : lives_ <= 0 && lives2_ <= 0;
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
        if (lives <= 0) return;
        if (!canReenterLevel()) {
            restartCurrentLevelAfterDeath();
            return;
        }
        respawnPlayerAtStart(player, energy, startMarker);
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
            damagePlayer(player_, energy_, lives_, playerDead_, reentryTimer_,
                         damageCooldown_, 1);
        }
        if (playerCount_ > 1 && !player2Dead_ &&
            playerOverlapsAnyExplosionTile(player2_, tiles)) {
            damagePlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_,
                         damageCooldown2_, 2);
        }
    }

    void enterMonsterDeath(ActiveMonster& monster) {
        if (monster.behavior == 2) return;
        spawnBonusDrop(static_cast<float>(monster.x) + 1.0f,
                       static_cast<float>(monster.y) + 2.0f);
        monster.behavior = 2;
        monster.kind = 0x0c;
        monster.stateTimer = 25;
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
            rect(0, 99, kScreenW, 1, 0xfff0d060u);
            rect(0, 100, kScreenW, 16, 0xcc000000u);
            text(4, 104, progressHudText() + " " +
                            playerHudText(2, energy2_, lives2_, player2Dead_,
                                          bombInventory2_) +
                            " S" + std::to_string(score2_),
                 0xffffffffu);
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
        }
        if (playerCount_ > 1 && !player2Dead_) {
            drawPlayer(player2_, player2Facing_, player2AnimTick_, drawCamX, drawCamY, 19);
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

    void drawHud() {
        rect(0, 0, kScreenW, 16, 0xcc000000u);
        std::string status = playerCount_ > 1
                                 ? playerHudText(1, energy_, lives_, playerDead_,
                                                 bombInventory_) +
                                       " S" + std::to_string(score_)
                                 : objectiveHudText() + " " +
                                       playerHudText(1, energy_, lives_, playerDead_,
                                                     bombInventory_);
        if (playerCount_ == 1) {
            status += " V" + std::to_string(gameplayViewWidth_);
        }
        text(4, 4, status, 0xffffffffu);
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
        if (argc > 1 && std::string(argv[1]) == "--debug-monster-slots") {
            app.debugMonsterSlots();
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
