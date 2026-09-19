#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>
#include <array>

namespace lezac::resources {

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
    std::vector<uint8_t> encodedTiles;
    std::vector<uint8_t> encodedWords;
    std::vector<MonsterSpawner> monsterSpawners;
    std::vector<LevelPortal> portals;
    std::vector<TileTriggerRule> tileTriggers;
    int startingObjectiveTiles = 0;
    int startingDestructibleTiles = 0;
};

std::vector<uint8_t> decodeLevelRle3(const std::vector<uint8_t>& encoded, size_t targetSize);
MonsterSpawner parseMonsterSpawner(const std::array<uint8_t, 30>& rec);
LevelPortal parseLevelPortal(const std::array<uint8_t, 7>& rec);
TileTriggerRule parseTileTriggerRule(const std::array<uint8_t, 14>& rec);
std::vector<Level> loadRawLevels(const std::string& path);
std::vector<Level> loadLevels(const std::string& path);

}
