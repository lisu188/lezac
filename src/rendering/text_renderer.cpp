#include "rendering/text_renderer.hpp"
#include "rendering/color.hpp"

namespace lezac::rendering {

int TextRenderer::fontGlyphIndex(char raw, bool large) const{
        char ch = raw;
        if (ch >= 'a' && ch <= 'z') ch = static_cast<char>(ch - 'a' + 'A');
        if (ch >= 'A' && ch <= 'Z') return (large ? 0 : 26) + (ch - 'A');
        if (ch >= '0' && ch <= '9') return 52 + (ch - '0');
        switch (ch) {
            case '.': return 62;
            case ':': return 63;
            case ';': return 64;
            case ',': return 65;
            case '!': return 66;
            case '\'': return 67;
            default: return -1;
        }
    }

std::array<std::string, 8> TextRenderer::fallbackGlyph(char ch) const{
        switch (ch) {
            case '/':
                return {"      # ", "     #  ", "    #   ", "   #    ",
                        "  #     ", " #      ", "#       ", "        "};
            case '-':
                return {"        ", "        ", "        ", " ###### ",
                        "        ", "        ", "        ", "        "};
            case '_':
                return {"        ", "        ", "        ", "        ",
                        "        ", "        ", " ###### ", "        "};
            case '%':
                return {"##    # ", "##   #  ", "    #   ", "   #    ",
                        "  #     ", " #   ## ", "#    ## ", "        "};
            case '&':
                return {"  ###   ", " ## ##  ", " ## #   ", "  ##    ",
                        " ## # # ", "##  ##  ", " ### ## ", "        "};
            case '+':
                return {"        ", "   ##   ", "   ##   ", " ###### ",
                        "   ##   ", "   ##   ", "        ", "        "};
            default:
                return {"        ", "        ", "        ", "        ",
                        "        ", "        ", "        ", "        "};
        }
    }

void TextRenderer::drawFallbackGlyph(int x, int y, char ch, uint32_t color){
        const auto rows = fallbackGlyph(ch);
        for (int yy = 0; yy < 8; ++yy) {
            for (int xx = 0; xx < 8; ++xx) {
                if (rows[yy][xx] != ' ') canvas_.pixel(x + xx, y + yy, color);
            }
        }
    }

void TextRenderer::drawFontSprite(int x, int y, const Sprite& glyph, uint32_t color,
                        bool preservePalette, bool nativePalette){
        for (int yy = 0; yy < glyph.height; ++yy) {
            for (int xx = 0; xx < glyph.width; ++xx) {
                uint8_t px = glyph.pixels[static_cast<size_t>(yy) * glyph.width + xx];
                if (px == 0) continue;
                if (nativePalette) {
                    // Blit every glyph index through the game palette exactly as
                    // the original does (no recolour, no synthetic outline).
                    canvas_.pixel(x + xx, y + yy, argb(palette_, px));
                    continue;
                }
                canvas_.pixel(x + xx, y + yy,
                      preservePalette && px != 1 ? argb(palette_, px) : color);
            }
        }
    }

int TextRenderer::glyphAdvance(char raw, bool large) const{
        if (raw == ' ') return large ? 8 : 5;
        int index = fontGlyphIndex(raw, large);
        if (index >= 0 && index < static_cast<int>(fontSprites_.sprites.size())) {
            return fontSprites_.sprites[static_cast<size_t>(index)].width + 1;
        }
        return 9;
    }

int TextRenderer::textWidth(const std::string& s, bool large) const{
        int width = 0;
        for (char raw : s) {
            width += glyphAdvance(raw, large);
        }
        return width;
    }

void TextRenderer::text(int x, int y, const std::string& s, uint32_t color, bool large,
              uint32_t shadow, int shadowDx, int shadowDy,
              bool nativePalette){
        int cx = x;
        for (char raw : s) {
            char ch = raw;
            if (ch == ' ') {
                cx += glyphAdvance(ch, large);
                continue;
            }
            int index = fontGlyphIndex(ch, large);
            auto drawOne = [&](int px, int py, uint32_t drawColor, bool preservePalette) {
                if (index >= 0 && index < static_cast<int>(fontSprites_.sprites.size())) {
                    const Sprite& glyph = fontSprites_.sprites[static_cast<size_t>(index)];
                    drawFontSprite(px, py, glyph, drawColor, preservePalette,
                                   nativePalette);
                    return glyph.width + 1;
                }
                drawFallbackGlyph(px, py, ch, drawColor);
                return 9;
            };
            if (shadow != 0 && !nativePalette) {
                drawOne(cx + shadowDx, y + shadowDy, shadow, false);
            }
            cx += drawOne(cx, y, color, true);
        }
    }

void TextRenderer::drawSprite(const Sprite& sprite, int x0, int y0){
        for (int y = 0; y < sprite.height; ++y) {
            for (int x = 0; x < sprite.width; ++x) {
                uint8_t c = sprite.pixels[static_cast<size_t>(y) * sprite.width + x];
                if (c != 0) canvas_.pixel(x0 + x, y0 + y, argb(palette_, c));
            }
        }
    }

}
