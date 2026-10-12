#pragma once

#include <array>
#include <cstdint>

namespace lezac::gameplay {

struct MonsterTileDamage {
    uint16_t footprintCell = 0;
    uint16_t lastFlameCell = 0;
    int8_t delta = 0;
};

// Generic kinds 1..8 call 56B6 with cutoff 0 and body-damage unit 1.
template <typename TileAt>
MonsterTileDamage queryMonsterTileDamage(int column, int row, int width, const TileAt& tileAt) {
    MonsterTileDamage result;
    result.footprintCell = static_cast<uint16_t>(row * width + column);
    constexpr std::array<std::array<int, 2>, 4> offsets{{{{0, 0}}, {{1, 0}}, {{1, 1}}, {{0, 1}}}};
    int damage = 0;
    for (const auto& offset : offsets) {
        const int x = column + offset[0], y = row + offset[1];
        const uint8_t glyph = tileAt(x, y);
        if (glyph == 0x75) {
            damage += 2;
            result.lastFlameCell = static_cast<uint16_t>(y * width + x);
        } else if (glyph >= 1 && glyph <= 0x4c) ++damage;
    }
    result.delta = static_cast<int8_t>(-damage);
    return result;
}

} // namespace lezac::gameplay
