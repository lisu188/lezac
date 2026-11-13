#pragma once

#include "gameplay/falling_fragment.hpp"

#include <cstdint>

namespace lezac::gameplay {

// 1000:5565..5576 takes a signed absolute value after word subtraction.
inline constexpr uint16_t collapseMagnitudeDelta(uint16_t previous, uint16_t current) noexcept {
    const uint16_t difference = static_cast<uint16_t>(previous - current);
    const uint16_t sign = (difference & 0x8000u) != 0 ? uint16_t{0xffff} : uint16_t{0};
    return static_cast<uint16_t>((difference ^ sign) - sign);
}

// Original fifteen-byte collapse bank, starting at DS:6620 (slot 1).
struct CollapseRecord {
    int x = 0, y = 0;
    uint16_t startOffsetBytes = 0, endOffsetBytes = 0, word = 0, flaggedWord = 0;
    uint8_t forwardPhase = 0, reversePhase = 0;
    int8_t subX = 0, subY = 0;
    uint8_t flags = 0, restTicks = 0;
    uint16_t argMagnitude = 0;
    uint8_t affectedBytes = 0;
    int count = 0;

    bool operator==(const CollapseRecord&) const = default;
};

// The low eleven-byte bank starts at DS:209E; mass is at DS:78D6 + index.
struct FlameRecord {
    uint16_t cell = 0;
    int8_t vx = 0, vy = 0, subX = 0, subY = 0;
    uint8_t timer = 0, glyph = 0x75, variant = 0, mass = 1;
    uint16_t retainedWord = 0;  // +2 is not initialized by the flame seeder.

    bool operator==(const FlameRecord&) const = default;
};

}  // namespace lezac::gameplay
