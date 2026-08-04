#include "resources/sprites.hpp"

#include "resources/io.hpp"
#include "resources/json.hpp"

#include <cstddef>
#include <stdexcept>
#include <utility>

namespace lezac::resources {

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
        if (s.pixels.size() != static_cast<std::size_t>(s.width) * s.height) {
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
    std::size_t offset = 0;
    uint8_t count = data[offset++];
    bank.sprites.reserve(count);
    for (uint8_t i = 0; i < count; ++i) {
        if (offset + 2 > data.size()) {
            throw std::runtime_error(path + " truncated sprite header");
        }
        Sprite sprite;
        sprite.width = data[offset++];
        sprite.height = data[offset++];
        std::size_t pixelCount = static_cast<std::size_t>(sprite.width) * sprite.height;
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

}
