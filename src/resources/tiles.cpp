#include "resources/tiles.hpp"

#include "core/constants.hpp"
#include "resources/io.hpp"
#include "resources/json.hpp"

#include <cstddef>
#include <stdexcept>

namespace lezac::resources {

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
    std::size_t payloadSize = data.size() - 2;
    std::size_t expectedSize = static_cast<std::size_t>(bank.count) *
                               lezac::core::kTileSize * lezac::core::kTileSize;
    if (bank.count <= 0 || payloadSize != expectedSize) {
        throw std::runtime_error(path + " raw tile payload size mismatch");
    }
    bank.pixels.insert(bank.pixels.end(), data.begin() + 2, data.end());
    return bank;
}

}
