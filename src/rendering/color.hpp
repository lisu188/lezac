#pragma once
#include "resources/types.hpp"

namespace lezac::rendering {
using resources::Palette;
using resources::Rgb;
inline uint32_t argb(const Palette& palette, uint8_t index) {
    const Rgb c = palette[index];
    return 0xff000000u | (static_cast<uint32_t>(c.r) << 16) |
           (static_cast<uint32_t>(c.g) << 8) | c.b;
}
}
