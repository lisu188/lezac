#pragma once

#include <array>
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

}
