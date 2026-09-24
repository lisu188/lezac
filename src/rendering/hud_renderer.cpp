#include "rendering/game_renderer.hpp"
#include "rendering/color.hpp"
#include <algorithm>
#include <cmath>
#include <string>
#include <stdexcept>

namespace lezac::rendering {
using namespace gameplay;
using namespace resources;
using namespace ui;

namespace {
// CARO.CAR tile index used by the reconstructed bottom HUD: the fixed
// destruction-target star (verified from the original HUD icon renderer, which
// blits 8x8 CARO tiles, not BOMOMIMK sprites, for the objective icons).
constexpr int kHudDestructionStarTile = 117;
constexpr int kHudLifeMarkerTile = 115;  // green walking figure
class HudPainter {
public:
    HudPainter(Canvas& canvas, TextRenderer& text, const AssetCatalog& assets,
               const PresentationState& presentation, const GameRenderer& renderer,
               const HudView& hud)
        : canvas_(canvas), text_(text), assets_(assets), presentation_(presentation),
          renderer_(renderer), hud_(hud) {}
    uint32_t energyColor(int energy) const {
        if (energy >= 67) return 0xff40d060u;
        if (energy >= 34) return 0xfff0c040u;
        return 0xffe04838u;
    }

    void drawMeter(int x, int y, int w, int h, int value, int maxValue,
                   uint32_t color) {
        canvas_.rect(x - 1, y - 1, w + 2, h + 2, 0xfff0d060u);
        canvas_.rect(x, y, w, h, 0xff1c1c1cu);
        int filled = std::clamp(value, 0, maxValue) * w / std::max(1, maxValue);
        if (filled > 0) canvas_.rect(x, y, filled, h, color);
    }

    void drawBombInventoryIcons(int x, int y, const BombInventory& inventory) {
        for (int i = 0; i < 4; ++i) {
            BombType type = static_cast<BombType>(i);
            int px = x + i * 34;
            bool selected = inventory.selected == type;
            canvas_.rect(px - 1, y - 1, 30, 10, selected ? 0xfff0d060u : 0xff303030u);
            canvas_.rect(px, y, 8, 8, renderer_.bombColor(type));
            text_.text(px + 10, y + 1, std::to_string(inventory.counts[static_cast<size_t>(i)]),
                 selected ? 0xff000000u : 0xffffffffu);
        }
    }

    // Blit an 8x8 CARO.CAR tile at a screen position (transparent index 0),
    // the primitive the original HUD uses for its objective/life-marker icons.
    bool drawHudTile8(int dx, int dy, int id) {
        const uint8_t* tile = assets_.tiles().tile(id);
        if (!tile) return false;
        for (int ty = 0; ty < 8; ++ty) {
            for (int tx = 0; tx < 8; ++tx) {
                uint8_t c = tile[ty * 8 + tx];
                if (c != 0) canvas_.pixel(dx + tx, dy + ty, argb(presentation_.palette(), c));
            }
        }
        return true;
    }

    // Draw a HUD number using CARO.CAR digit tiles 121-130 (digit v -> tile
    // 121+v), the way the original HUD renders its numbers. 8px per digit.
    void drawHudNumber(int x, int y, int value, int minDigits) {
        std::string s = std::to_string(std::max(0, value));
        while (static_cast<int>(s.size()) < minDigits) s.insert(s.begin(), '0');
        for (size_t i = 0; i < s.size(); ++i) {
            drawHudTile8(x + static_cast<int>(i) * 9, y, 121 + (s[i] - '0'));
        }
    }

    void drawHudScore(int x, int y, const lezac::core::HudScoreReel& score) {
        bool leading = true;
        for (int digit = 8; digit >= 0; --digit) {
            const auto offset = score.current[static_cast<size_t>(digit)];
            if (digit != 0 && leading && offset == 0) continue;
            leading = false;
            const size_t source = 121 * 64 + offset;
            if (source + 64 > assets_.tiles().pixels.size()) throw std::runtime_error("HUD score atlas overread");
            for (int row = 0; row < 8; ++row) {
                for (int column = 0; column < 8; ++column) {
                    canvas_.pixel(x + (8 - digit) * 9 + column, y + row, argb(presentation_.palette(), assets_.tiles().pixels[source + row * 8 + column]));
                }
            }
        }
    }

    void drawOriginalHudFigure(int x, int y, uint32_t color) {
        // Player-life marker: the original blits CARO.CAR tile 115 (a green
        // walking figure); fall back to a small stick glyph if unavailable.
        if (drawHudTile8(x, y - 1, kHudLifeMarkerTile)) return;
        static const char* kGlyph[7] = {
            " X ", " X ", "XXX", " X ", " X ", "X X", "X X"};
        for (int gy = 0; gy < 7; ++gy) {
            for (int gx = 0; gx < 3; ++gx) {
                if (kGlyph[gy][gx] == 'X') canvas_.pixel(x + gx, y + gy, color);
            }
        }
    }

    // One player's HUD column: energy bar, score panel and life figures at
    // `xoff`, plus the bomb-selector box and its count panel at `xoff + 119`.
    // The original two-player HUD is exactly the single-player left column
    // drawn twice -- player 2's copy at xoff 180 (energy track x180..281,
    // score panel x180..267, bomb box x299..318, lives at x180..196), all
    // measured from an original two-player capture.
    void drawPlayerHudColumn(int xoff, int energy, uint32_t score, int lives,
                             bool dead, const BombInventory& inventory) {
        constexpr uint32_t kGrey = 0xffb6b6b6u;
        constexpr uint32_t kYellow = 0xffffff55u;
        constexpr uint32_t kBlue = 0xff0018dbu;
        constexpr uint32_t kCyan = 0xff00aaaau;
        constexpr uint32_t kGreen = 0xff00f300u;
        constexpr uint32_t kBoxGrey = 0xffa2a2a2u;
        const int y0 = kScreenH - 46;

        // Energy bar: a 102x3 grey-framed track (x0..101, spanning y0+10..y0+12)
        // with a 1px-tall yellow fill on the middle row, its width proportional
        // to the player's energy -- full energy fills the inner 100px (x1..100).
        // Measured pixel-for-pixel from the original level-1 frame: the grey
        // frame (182,182,182) surrounds the yellow (255,255,85) on all sides.
        canvas_.rect(xoff, y0 + 10, 102, 3, kGrey);
        const bool ready = hud_.columnReady[xoff == 0 ? 0 : 1];
        int energyFill = ready ? std::clamp(dead ? 0 : energy, 0, 100) : 0;
        if (ready) canvas_.rect(xoff + 1, y0 + 11, 100, 1, argb(presentation_.palette(), 1));
        canvas_.rect(xoff + 1, y0 + 11, energyFill, 1, kYellow);

        // Score panel: an 88x17 cyan-framed box (x0..87, y0+18..y0+34) with a
        // blue interior and a right-aligned green score value. The original
        // frames the blue panel with a 1px cyan (0,170,170) border on all four
        // sides -- not just the left edge -- measured from the level-1 frame.
        canvas_.rect(xoff, y0 + 18, 88, 17, kCyan);
        canvas_.rect(xoff + 1, y0 + 19, 86, 15, kBlue);
        (void)score;
        drawHudScore(xoff, y0 + 22, hud_.scoreReels[xoff == 0 ? 0 : 1]);

        // The stored count is already the original reserve byte: two at a
        // fresh start, zero on the last playable life, and -1 when out.
        for (int i = 0; i < std::clamp(lives, 0, 6); ++i) {
            drawOriginalHudFigure(xoff + i * 9, y0 + 39, kGreen);
        }

        // Bomb selector box showing the selected bomb's actual sprite (from the
        // BOMOMIMK bank, the same sprite the world bomb uses) and its count.
        // Measured against the original: a 20x20 beveled grey box at (119, y0+7)
        // -- a light 1px outer ring (162), a darker 1px inner ring (130), then a
        // 16x16 near-black well (the pixel counts 76/68 match the two rings).
        const int bx0 = xoff + 119;
        canvas_.rect(bx0, y0 + 7, 20, 20, kBoxGrey);
        canvas_.rect(bx0 + 1, y0 + 8, 18, 18, 0xff828282u);
        if (!hud_.columnReady[xoff == 0 ? 0 : 1]) {
            canvas_.rect(bx0, y0 + 27, 20, 9, kBlue);
            return;
        }
        canvas_.rect(bx0 + 2, y0 + 9, 16, 16, 0xff202020u);
        const int bombSprite =
            static_cast<int>(bombProfile(inventory.selected).spriteBase);
        if (bombSprite >= 0 &&
            bombSprite < static_cast<int>(assets_.sprites().sprites.size())) {
            const Sprite& sprite = assets_.sprites().sprites[static_cast<size_t>(bombSprite)];
            const int bx = bx0 + 2 + (16 - sprite.width) / 2;
            const int by = y0 + 9 + (16 - sprite.height) / 2;
            canvas_.setClip(bx0 + 2, y0 + 9, bx0 + 2 + 16, y0 + 9 + 16);
            text_.drawSprite(sprite, bx, by);
            canvas_.resetClip();
        } else {
            canvas_.rect(bx0 + 2, y0 + 9, 16, 16, renderer_.bombColor(inventory.selected));
        }
        int selCount = inventory.counts[static_cast<size_t>(inventory.selected)];
        // Blue count panel beneath the bomb box (x119-138, matching the box
        // width), with the ammo count drawn on it.
        canvas_.rect(bx0, y0 + 27, 20, 9, kBlue);
        drawHudNumber(bx0 + 1, y0 + 28, std::clamp(selCount, 0, 99), 2);
    }

    void drawSinglePlayerHud() {
        // Reconstructed from the original level-1 HUD: a solid-black bottom
        // band beneath the view frame, a yellow energy bar and blue score
        // panel on the left, green player-life figures beneath it, a grey
        // bomb-selector box in the centre, and a blue/cyan panel with bomb and
        // objective tallies on the right. Colours are sampled from the original
        // frames (VGA palette). The grey/white rule above the band is the view
        // frame's bottom border, drawn by drawViewFrame.
        canvas_.rect(0, 160, kScreenW, 40, 0xff000000u);
        drawPlayerHudColumn(0, hud_.players[0].energy, hud_.players[0].score, hud_.players[0].lives, hud_.players[0].dead,
                            hud_.players[0].inventory);
        drawHudObjectivePanel();
    }

    void drawHudObjectivePanel() {
        constexpr uint32_t kBlack = 0xff000000u;
        constexpr uint32_t kYellow = 0xffffff55u;
        constexpr uint32_t kBlue = 0xff0018dbu;
        constexpr uint32_t kCyan = 0xff00aaaau;
        const int y0 = kScreenH - 46;
        // Centre panel: bomb-count and objective (destruction target) tallies.
        // The original panel spans y0+6..y0+44 (measured 160-198 on level 1),
        // taller than the earlier 34px box.
        canvas_.rect(141, y0 + 6, 37, 39, argb(presentation_.palette(), 224));
        canvas_.rect(141, y0 + 6, 37, 1, kCyan);
        canvas_.rect(141, y0 + 44, 37, 1, kCyan);
        canvas_.rect(141, y0 + 6, 1, 39, kCyan);
        canvas_.rect(177, y0 + 6, 1, 39, kCyan);
        // Top row: bonus-objective icon + the level's required bonus count.
        // Bottom row: destruction-target icon + the required destruction count.
        // These two numbers were verified pixel-for-pixel against the original
        // HUD across every level (L1 1/50, L2 3/60, L3 7/20, L4 3/70, L5 8/65,
        // L7 1/10), so they must read from the level's objective data.
        //
        // The top icon is the level's bonus-collectible graphic: the original
        // draws the level objectiveTile (verified because levels 1 and 3 share
        // objectiveTile 108 and show the identical lemon; L2=grapes, L5=melon).
        // Each tally icon sits in its own small black inset box on the panel.
        // Rows use the original's 16px spacing: top at y0+13, bottom at y0+29
        // (measured against the original level-1 frame).
        // Each icon sits in an 8x8 black well framed by a 1px darker-blue border
        // (4,4,166) against the panel blue (measured: 36px frame per box).
        canvas_.rect(143, y0 + 11, 10, 10, argb(presentation_.palette(), 245));
        canvas_.rect(144, y0 + 12, 8, 8, kBlack);
        canvas_.rect(143, y0 + 27, 10, 10, argb(presentation_.palette(), 246));
        canvas_.rect(144, y0 + 28, 8, 8, kBlack);
        if (!drawHudTile8(144, y0 + 12, hud_.objectiveTile)) {
            canvas_.rect(144, y0 + 12, 8, 8, kYellow);
        }
        // The original displays the REMAINING objective (required - current),
        // counting down to zero as bonuses are collected / tiles destroyed.
        int bonusRemaining =
            std::max(0, static_cast<int>(hud_.requiredBonus) - hud_.collected);
        drawHudNumber(159, y0 + 12, std::min(99, bonusRemaining), 2);
        // Bottom icon: the fixed destruction-target star, CARO.CAR tile 117.
        if (!drawHudTile8(144, y0 + 28, kHudDestructionStarTile)) {
            canvas_.rect(144, y0 + 28, 8, 8, kYellow);
        }
        int destRemaining = std::max(
            0, static_cast<int>(hud_.requiredDestruction) - hud_.destructionPercent);
        drawHudNumber(159, y0 + 28, std::min(99, destRemaining), 2);
    }

    void drawHud() {
        // The original HUD is a bottom status band (the top of the screen is
        // gameplay sky). Two-player mode doubles the per-player column (player
        // 2's copy shifted 180px right) around the shared centre objective
        // panel, exactly as measured from the original two-player capture.
        if (hud_.playerCount == 1) {
            drawSinglePlayerHud();
        } else {
            canvas_.rect(0, 160, kScreenW, 40, 0xff000000u);
            drawPlayerHudColumn(0, hud_.players[0].energy, hud_.players[0].score, hud_.players[0].lives, hud_.players[0].dead,
                                hud_.players[0].inventory);
            drawPlayerHudColumn(180, hud_.players[1].energy, hud_.players[1].score, hud_.players[1].lives, hud_.players[1].dead,
                                hud_.players[1].inventory);
            drawHudObjectivePanel();
        }
        if (hud_.complete && !hud_.outroActive) {
            canvas_.rect(76, 84, 168, 24, 0xee000000u);
            text_.text(92, 92, "LEVEL COMPLETED", 0xffffe060u, false, 0xff301800u);
        }
    }
private:
    Canvas& canvas_;
    TextRenderer& text_;
    const AssetCatalog& assets_;
    const PresentationState& presentation_;
    const GameRenderer& renderer_;
    const HudView& hud_;
};
}

void GameRenderer::drawHud(const HudView& hud) {
    HudPainter(canvas_, text_, assets_, presentation_, *this, hud).drawHud();
}

}
