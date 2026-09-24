#pragma once
#include "rendering/canvas.hpp"
#include "resources/types.hpp"
#include <array>
#include <string>

namespace lezac::rendering {
using resources::Palette;
using resources::Sprite;
using resources::SpriteBank;

class TextRenderer {
public:
    TextRenderer(Canvas& canvas, const Palette& palette, const SpriteBank& fonts)
        : canvas_(canvas), palette_(palette), fontSprites_(fonts) {}
    int fontGlyphIndex(char raw, bool large) const;
    std::array<std::string, 8> fallbackGlyph(char ch) const;
    void drawFallbackGlyph(int x, int y, char ch, uint32_t color);
    void drawFontSprite(int x, int y, const Sprite& glyph, uint32_t color,
                        bool preservePalette, bool nativePalette = false);
    int glyphAdvance(char raw, bool large = false) const;
    int textWidth(const std::string& s, bool large = false) const;
    void text(int x, int y, const std::string& s, uint32_t color, bool large = false,
              uint32_t shadow = 0, int shadowDx = 1, int shadowDy = 1,
              bool nativePalette = false);
    void drawSprite(const Sprite& sprite, int x0, int y0);
private:
    Canvas& canvas_;
    const Palette& palette_;
    const SpriteBank& fontSprites_;
};
}
