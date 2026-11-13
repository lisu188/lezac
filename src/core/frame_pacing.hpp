#pragma once

#include <cstdint>

namespace lezac::core {

// Original CS:7903..7919; the wrapping counter also samples at zero.
constexpr bool advanceFramePacingCounter(uint16_t& counter) {
    counter = static_cast<uint16_t>(counter + 1u);
    return counter % 30u == 0;
}

// Original CS:799a..79cd. Elapsed is a raw centisecond word over 30 frames.
constexpr uint16_t adjustOriginalFrameDelay(uint16_t delay, uint16_t elapsed, uint16_t step) {
    if (elapsed > 125 && delay > 0)
        return delay > step ? static_cast<uint16_t>(delay - step) : uint16_t{0};
    if (elapsed < 120) return static_cast<uint16_t>(delay + step);
    return delay;
}

}
