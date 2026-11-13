#pragma once

#include "core/random.hpp"
#include "resources/levels.hpp"
#include <cstddef>
#include <cstdint>
#include <optional>

namespace lezac::gameplay {

inline constexpr uint8_t kJollyCloudRainTicks = 46;

inline std::optional<size_t> advanceJollyCloudRain(uint8_t& remaining, resources::Level& level,
                                                 uint16_t& nextFragmentWord, core::TurboRandom& random) {
    if (remaining == 0) return std::nullopt;
    --remaining;  // 1000:81BF..81CD calls the producer even on the final decrement.
    const auto width = static_cast<uint16_t>(level.width);
    const size_t cell = width + random.range(0, width);
    if (level.tiles.at(cell) != 0) return std::nullopt;
    uint8_t tile = static_cast<uint8_t>(random.range(103, 9));
    if (tile == level.objectiveTile) ++tile;
    level.tiles.at(cell) = tile;
    level.wordLayer.at(cell) = nextFragmentWord++;
    // 1000:3F27..3FA5 consumes the marker before the seeder's capacity check.
    return cell;
}

}
