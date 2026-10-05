#pragma once

#include "gameplay/actor_models.hpp"
#include <cstdint>

namespace lezac::rendering {

struct HudAmmoPanel {
    gameplay::BombType icon = gameplay::BombType::Small;
    uint8_t count = 99;
};

}
