#include "gameplay/actor_models.hpp"

#include <array>
#include <cstdio>
#include <cstdint>
#include <iostream>
#include <vector>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

int main() {
#ifdef _WIN32
    if (_setmode(_fileno(stdout), _O_BINARY) == -1) return 1;
#endif
    constexpr std::array<uint8_t, 3> masses{1, 9, 221};
    constexpr std::array<uint8_t, 7> weights{0, 1, 2, 8, 18, 128, 254};
    std::vector<uint8_t> records;
    records.reserve(65536 * 8);
    for (uint8_t mass : masses) {
        for (uint8_t weight : weights) {
            records.clear();
            for (int ownRaw = 0; ownRaw < 256; ++ownRaw) {
                const auto ownX = static_cast<int8_t>(ownRaw);
                const auto ownY = static_cast<int8_t>(-static_cast<int>(ownX));
                for (int incomingRaw = 0; incomingRaw < 256; ++incomingRaw) {
                    const auto incomingX = static_cast<int8_t>(incomingRaw);
                    const auto incomingY = static_cast<int8_t>(-static_cast<int>(incomingX));
                    const auto resultX = lezac::gameplay::blendFlameVelocity(ownX, incomingX, mass, weight);
                    const auto resultY = lezac::gameplay::blendFlameVelocity(ownY, incomingY, mass, weight);
                    for (uint8_t value : {static_cast<uint8_t>(ownX), static_cast<uint8_t>(ownY),
                                         static_cast<uint8_t>(incomingX), static_cast<uint8_t>(incomingY),
                                         mass, weight, static_cast<uint8_t>(resultX),
                                         static_cast<uint8_t>(resultY)}) {
                        records.push_back(value);
                    }
                }
            }
            std::cout.write(reinterpret_cast<const char*>(records.data()),
                            static_cast<std::streamsize>(records.size()));
        }
    }
    return std::cout ? 0 : 1;
}
