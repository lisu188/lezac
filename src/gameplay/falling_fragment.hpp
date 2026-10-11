#pragma once

#include "resources/levels.hpp"
#include <cstddef>
#include <cstdint>
#include <vector>

namespace lezac::gameplay {

// Original 11-byte falling record at DS:2093 + 11*slot, slots 200..1600.
struct DebrisRecord {
    int tileIndex = 0;         // +0 u16: cell index (y*width + x)
    uint16_t flaggedWord = 0;  // +2 u16: word | 0x8000 while airborne
    int8_t velocityX = 0;      // +4 s8: vx, 128 sub-units per tile (lane DS:78D2)
    int8_t velocityY = 0;      // +5 s8: vy (lane DS:78D4)
    int8_t subX = 0;           // +6 s8: x sub-accumulator (lane DS:78D3)
    int8_t subY = 0;           // +7 s8: y sub-accumulator (lane DS:78D5)
    uint8_t restTicks = 0;     // +8 u8: no-move ticks; retire at 100
    uint8_t lookup = 0;        // +9 u8: carried tile code (objectByte at seed)
    uint8_t aux = 0;           // +A u8: bit 7 = cascade spawned by this move
};

inline bool seedFallingFragment(resources::Level& level, std::vector<DebrisRecord>& records,
                                size_t cell, uint8_t velocityX, uint8_t velocityY) {
    auto& word = level.wordLayer.at(cell);
    if (word < 0x4000 || (word & 0x8000) != 0 || 199 + records.size() >= 1600) return false;
    // 1000:374C..37F4 leaves the object byte intact, including on saturation.
    word = static_cast<uint16_t>(word | 0x8000);
    DebrisRecord record;
    record.tileIndex = static_cast<int>(cell);
    record.flaggedWord = word;
    record.velocityX = static_cast<int8_t>(velocityX);
    record.velocityY = static_cast<int8_t>(velocityY);
    record.lookup = level.tiles.at(cell);
    records.push_back(record);
    return true;
}

}
