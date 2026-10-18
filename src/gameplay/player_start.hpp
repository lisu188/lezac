#pragma once

#include "resources/levels.hpp"

#include <span>
#include <utility>

namespace lezac::gameplay {

// 1000:056B selects the first matching marker bit, independently of portal key.
inline std::pair<uint16_t, uint16_t> playerStart(std::span<const resources::LevelPortal> portals,
                                               uint8_t marker) {
    for (const auto& portal : portals)
        if ((portal.marker & marker) != 0) return {portal.x, portal.y};
    return {uint16_t{17}, uint16_t{17}};
}

}
