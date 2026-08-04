#pragma once

#include "core/constants.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace lezac::resources {

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
        return pixels.data() + static_cast<std::size_t>(id) *
                                   lezac::core::kTileSize * lezac::core::kTileSize;
    }
};

}
