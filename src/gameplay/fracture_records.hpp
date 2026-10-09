#pragma once

#include <cstdint>

namespace lezac::gameplay {

// Original eleven-byte fragment bank, starting at DS:292B (slot 200).
struct DebrisRecord {
    int tileIndex = 0;
    uint16_t flaggedWord = 0;
    int8_t velocityX = 0, velocityY = 0, subX = 0, subY = 0;
    uint8_t restTicks = 0, lookup = 0, aux = 0;
};

// Original fifteen-byte collapse bank, starting at DS:6620 (slot 1).
struct CollapseRecord {
    int x = 0, y = 0;
    uint16_t startOffsetBytes = 0, endOffsetBytes = 0, word = 0, flaggedWord = 0;
    uint8_t forwardPhase = 0, reversePhase = 0;
    int8_t subX = 0, subY = 0;
    uint8_t flags = 0, restTicks = 0;
    uint16_t argMagnitude = 0;
    uint8_t affectedBytes = 0;
    int count = 0;
};

// The low eleven-byte bank starts at DS:209E; mass is at DS:78D6 + index.
struct FlameRecord {
    uint16_t cell = 0;
    int8_t vx = 0, vy = 0, subX = 0, subY = 0;
    uint8_t timer = 0, glyph = 0x75, variant = 0, mass = 1;
    uint16_t retainedWord = 0;  // +2 is not initialized by the flame seeder.
};

}  // namespace lezac::gameplay
