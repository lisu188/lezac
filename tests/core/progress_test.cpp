#include "core/progress.hpp"

#include <cstdint>
#include <iostream>
#include <vector>

int main() {
    using lezac::core::countPhysicalDamageProgressCells;
    using lezac::core::countsForDestructionProgress;
    using lezac::core::countsForPhysicalDamageProgress;

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

    std::cout << "core_progress=ok destruction=1 physical=2\n";
    return 0;
}
