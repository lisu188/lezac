#include "core/fixed_point.hpp"
#include "core/progress.hpp"
#include "core/random.hpp"

#include <array>
#include <cstdint>
#include <iostream>
#include <vector>

int main() {
    using lezac::core::Fixed8_8Axis;
    using lezac::core::TurboRandom;
    using lezac::core::countPhysicalDamageProgressCells;
    using lezac::core::countsForDestructionProgress;
    using lezac::core::countsForPhysicalDamageProgress;
    using lezac::core::integrateFixed8_8;

    if (countsForDestructionProgress(0, 108) ||
        countsForDestructionProgress(1, 108) ||
        countsForDestructionProgress(0xff, 108) ||
        countsForDestructionProgress(108, 108) ||
        !countsForDestructionProgress(2, 108)) {
        return 1;
    }

    const std::vector<uint16_t> words{0, 1, 0x3fff, 0x4000, 0x8001};
    if (!countsForPhysicalDamageProgress(1) ||
        !countsForPhysicalDamageProgress(0x3fff) ||
        countsForPhysicalDamageProgress(0) ||
        countsForPhysicalDamageProgress(0x4000) ||
        countsForPhysicalDamageProgress(0x8001) ||
        countPhysicalDamageProgressCells(words) != 2) {
        return 1;
    }

    Fixed8_8Axis positive;
    for (int i = 0; i < 4; ++i) integrateFixed8_8(positive, 64);

    Fixed8_8Axis negativeOnce;
    integrateFixed8_8(negativeOnce, -64);

    Fixed8_8Axis negativeFour;
    for (int i = 0; i < 4; ++i) integrateFixed8_8(negativeFour, -64);

    Fixed8_8Axis wholePositive;
    for (int i = 0; i < 4; ++i) integrateFixed8_8(wholePositive, 256);

    Fixed8_8Axis wholeNegative;
    for (int i = 0; i < 4; ++i) integrateFixed8_8(wholeNegative, -256);

    if (positive.position != 1 || positive.fraction != 0 ||
        negativeOnce.position != -1 || negativeOnce.fraction != 192 ||
        negativeFour.position != -1 || negativeFour.fraction != 0 ||
        wholePositive.position != 4 || wholePositive.fraction != 0 ||
        wholeNegative.position != -4 || wholeNegative.fraction != 0) {
        return 1;
    }

    TurboRandom random100(0);
    constexpr std::array<uint16_t, 12> expected100{
        0, 56, 29, 76, 86, 17, 85, 3, 95, 96, 74, 16,
    };
    for (uint16_t expected : expected100) {
        if (random100.range(0, 100) != expected) return 1;
    }

    TurboRandom random1000(0x1234abcdu);
    constexpr std::array<uint16_t, 8> expected1000{
        949, 374, 129, 775, 697, 545, 722, 975,
    };
    for (uint16_t expected : expected1000) {
        if (random1000.range(0, 1000) != expected) return 1;
    }

    TurboRandom zeroRange(0);
    if (zeroRange.range(37, 0) != 37 || zeroRange.seed() != 1) return 1;

    std::cout << "core_progress=ok destruction=1 physical=2 fixed=1 random=1\n";
    return 0;
}
