#pragma once

#include <cstdint>
#include <vector>

namespace lezac::core {

bool countsForDestructionProgress(uint8_t tile, uint8_t objectiveTile) noexcept;
bool countsForPhysicalDamageProgress(uint16_t word) noexcept;
int countPhysicalDamageProgressCells(const std::vector<uint16_t>& words);

}
