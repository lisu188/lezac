#pragma once

#include "core/fixed_point.hpp"
#include <algorithm>
#include <cstdint>

namespace lezac::gameplay::detail {

inline int16_t clampI16(int value) {
    return static_cast<int16_t>(std::clamp(value, -32768, 32767));
}

inline void integrateAxis8_8(int& position, uint8_t& fraction, int16_t velocity) {
    core::Fixed8_8Axis axis{position, fraction};
    core::integrateFixed8_8(axis, velocity);
    position = axis.position;
    fraction = axis.fraction;
}

}
