#pragma once

#include <cstdint>

namespace lezac::core {

struct ActorSteeringVector8 {
    int16_t vx8=0,vy8=0;
    bool operator==(const ActorSteeringVector8&) const = default;
};

// Signed component words and unsigned speed have the original helper's types.
ActorSteeringVector8 actorSteeringVector8(int16_t dx,int16_t dy,uint16_t speed);

} // namespace lezac::core
