#pragma once

#include <array>
#include <cstdint>
#include <span>

namespace lezac::core {

struct ActorMotionPrefixInput {
    std::array<uint8_t,38> actor{};
    int16_t originalX=0,x=0,y=0,dx=0,dy=0,vx8=0,vy8=0;
    std::array<uint8_t,4> edges{}; // Top, bottom, left, right.
    std::array<uint8_t,4> tiles{}; // DS:2054..2057.
    std::array<uint16_t,3> shared{}; // DS:C1E8, 2072, 2074.
    uint16_t tick=0;
    uint32_t randomSeed=0;
    uint8_t facingRequest=0;
    bool operator==(const ActorMotionPrefixInput&) const = default;
};

enum class ActorMotionPrefixOutcome { Terrain, RuntimeError, DivideError };

struct ActorMotionPrefixResult {
    std::array<uint8_t,38> actor{};
    int16_t x=0,y=0,vx8=0,vy8=0;
    std::array<uint16_t,3> shared{};
    uint32_t randomSeed=0;
    uint8_t facingRequest=0;
    ActorMotionPrefixOutcome outcome=ActorMotionPrefixOutcome::Terrain;
    uint16_t stopIp=0;
    uint64_t instructions=0;
    bool operator==(const ActorMotionPrefixResult&) const = default;
};

// Execute actual 7018..732C instructions on a private live stack. Terrain,
// common integration, target selection and IRQ/work-clock scheduling are owned
// by the caller. Animation bytes are a live view of DS:0058..0257.
ActorMotionPrefixResult actorMotionPrefix(const ActorMotionPrefixInput& input,
    std::span<const uint8_t,512> animationBytes);

} // namespace lezac::core
