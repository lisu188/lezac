#pragma once

#include <cstdint>

namespace lezac::core {

struct Fixed8_8Axis {
    int32_t position = 0;
    uint8_t fraction = 0;
};

constexpr int32_t floorDiv256(int32_t value) {
    return value >= 0 ? value / 256 : -((255 - value) / 256);
}

constexpr void integrateFixed8_8(Fixed8_8Axis& axis, int16_t velocity) {
    const int32_t total = static_cast<int32_t>(axis.fraction) + velocity;
    const int32_t delta = floorDiv256(total);
    axis.position += delta;
    axis.fraction = static_cast<uint8_t>(total - delta * 256);
}

}
