#pragma once

#include <cstdint>

namespace lezac::gameplay {

constexpr int32_t signedCollapseEndpoint(uint16_t value) {
    return value < 0x8000u ? value : static_cast<int32_t>(value) - 0x10000;
}

// 1000:508B uses signed endpoint do/while loops, not movement's fixed counts.
// Some original endpoint combinations do not terminate; no clamp is introduced.
template <typename Visitor>
void visitCollapseRemovalWords(uint16_t first, uint16_t right, uint16_t last,
                               uint16_t width, Visitor&& visitor) {
    do {
        uint16_t cursor = first;
        do {
            visitor(static_cast<uint16_t>(cursor >> 1));
            cursor = static_cast<uint16_t>(cursor + 2u);
        } while (signedCollapseEndpoint(cursor) <= signedCollapseEndpoint(right));
        first = static_cast<uint16_t>(first + 2u * width);
        right = static_cast<uint16_t>(right + 2u * width);
    } while (signedCollapseEndpoint(right) <= signedCollapseEndpoint(last));
}

constexpr uint16_t collapseActorCell(uint16_t lastWordOffset, uint16_t distance) {
    return static_cast<uint16_t>((lastWordOffset >> 1) - distance);
}

}  // namespace lezac::gameplay
