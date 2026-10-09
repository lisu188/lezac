#pragma once

#include <array>
#include <cstdint>

namespace lezac::gameplay {

struct MonsterTileDamage {
    uint16_t footprintCell = 0;
    uint16_t lastFlameCell = 0;
    int8_t delta = 0;
};

struct MonsterObjectConsumption {
    uint8_t glyph;
    uint16_t word;
    uint8_t scratch = 0;
    uint16_t sprite = 0;
    uint16_t score = 0;
    bool seedAbove = false;
    bool consumed = false;
};

// 1000:5AFD resets all three outputs even when the glyph is not consumable.
inline MonsterObjectConsumption queryMonsterObjectConsumption(uint8_t glyph, uint16_t word, uint16_t above) {
    MonsterObjectConsumption result{glyph, word};
    if (glyph <= 0x66 || glyph >= 0x73) return result;
    constexpr std::array<uint16_t, 12> scores{{50, 100, 200, 250, 500, 800, 1000, 1500, 2000, 3000, 5000, 1000}};
    constexpr std::array<uint16_t, 12> sprites{{80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 86}};
    result.scratch = glyph;
    result.sprite = sprites[glyph - 0x67];
    result.score = scores[glyph - 0x67];
    result.seedAbove = above != 0 && above < 0x8000;
    result.consumed = true;
    result.glyph = word < 0x8000 ? 0 : 0xff;
    if (word < 0x8000) result.word = 0;
    return result;
}

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
