#include "core/progress.hpp"

#include <algorithm>

namespace lezac::core {
namespace {

constexpr uint16_t kDamagedWordBit = 0x8000;
constexpr uint16_t kDeferredThreshold = 0x4000;

}

bool countsForDestructionProgress(uint8_t tile, uint8_t objectiveTile) noexcept {
    return tile > 1 && tile != 0xff && tile != objectiveTile;
}

bool countsForPhysicalDamageProgress(uint16_t word) noexcept {
    return word != 0 && (word & kDamagedWordBit) == 0 && word < kDeferredThreshold;
}

int countPhysicalDamageProgressCells(const std::vector<uint16_t>& words) {
    return static_cast<int>(std::count_if(words.begin(), words.end(),
                                          countsForPhysicalDamageProgress));
}

}
