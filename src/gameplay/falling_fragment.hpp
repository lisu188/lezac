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

template <typename Records, typename ReadWord, typename ReadObject, typename WriteWord>
inline bool seedFallingFragmentPhysical(Records& records, size_t cell,
                                        uint8_t velocityX, uint8_t velocityY,
                                        ReadWord readWord, ReadObject readObject, WriteWord writeWord) {
    const uint16_t word = readWord(cell);
    if (word < 0x4000 || (word & 0x8000) != 0 || 199 + records.size() >= 1600) return false;
    // 1000:374C..37F4 leaves the object byte intact, including on saturation.
    const auto flaggedWord = static_cast<uint16_t>(word | 0x8000);
    writeWord(cell, flaggedWord);
    DebrisRecord record;
    record.tileIndex = static_cast<int>(cell);
    record.flaggedWord = flaggedWord;
    record.velocityX = static_cast<int8_t>(velocityX);
    record.velocityY = static_cast<int8_t>(velocityY);
    record.lookup = readObject(cell);
    records.push_back(record);
    return true;
}

template <typename Records>
inline bool seedFallingFragment(resources::Level& level, Records& records,
                                size_t cell, uint8_t velocityX, uint8_t velocityY) {
    return seedFallingFragmentPhysical(records, cell, velocityX, velocityY,
        [&](size_t address) { return level.wordLayer.at(address); },
        [&](size_t address) { return level.tiles.at(address); },
        [&](size_t address, uint16_t word) { level.wordLayer.at(address) = word; });
}

}
