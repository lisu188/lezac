#pragma once

#include <cstdint>

namespace lezac::core {

class TurboRandom {
public:
    explicit constexpr TurboRandom(uint32_t seed = 0) : seed_(seed) {}

    constexpr uint32_t seed() const {
        return seed_;
    }

    constexpr void setSeed(uint32_t seed) {
        seed_ = seed;
    }

    constexpr uint16_t range(uint16_t base, uint16_t range) {
        seed_ = seed_ * 0x08088405u + 1u;
        const uint16_t span = range == 0 ? 1 : range;
        return static_cast<uint16_t>(base + ((seed_ >> 16) % span));
    }

private:
    uint32_t seed_ = 0;
};

}
