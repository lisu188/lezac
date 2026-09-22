#include "resources/levels.hpp"

#include "resources/io.hpp"
#include "resources/json.hpp"
#include "resources/binary.hpp"
#include "core/progress.hpp"

#include <algorithm>
#include <stdexcept>
#include <utility>

namespace lezac::resources {

using lezac::core::countPhysicalDamageProgressCells;

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
        level.encodedTiles = getBytes(data, off, level.tileEncodedSize);
        size_t tileCount = static_cast<size_t>(level.width) * level.height;
        level.tiles = decodeLevelRle3(level.encodedTiles, tileCount);

        level.wordEncodedSize = getU16(data, off);
        level.encodedWords = getBytes(data, off, level.wordEncodedSize);
        std::vector<uint8_t> wordBytes = decodeLevelRle3(level.encodedWords, tileCount * 2);
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

}
