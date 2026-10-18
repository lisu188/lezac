#include "rendering/game_renderer.hpp"
#include "rendering/color.hpp"
#include "rendering/world_camera.hpp"
#include <algorithm>
#include <cmath>
#include <string>
#include <stdexcept>

namespace lezac::rendering {
using namespace gameplay;
using namespace resources;
using namespace ui;

namespace {
void fillViewFrame(Canvas& canvas, const Palette& palette, int left, int width,
                   uint8_t outline, uint8_t inner) {
    canvas.indexedRect(left, 0, width, 160, outline, argb(palette, outline));
    canvas.indexedRect(left + 1, 1, width - 2, 158, inner, argb(palette, inner));
}

class WorldPainter {
public:
    WorldPainter(Canvas& canvas, TextRenderer& text, const AssetCatalog& assets,
                 const PresentationState& presentation, const GameRenderer& renderer,
                 const WorldRenderView& world)
        : canvas_(canvas), text_(text), assets_(assets), presentation_(presentation),
          renderer_(renderer), world_(world) {}
    void drawGradientSky(int viewX, int viewY, int viewW, int viewH,
                         int camX, int camY) {
        if (!world_.showBackground) {
            for (int y = 0; y < viewH; ++y) {
                for (int x = 0; x < viewW; ++x) {
                    canvas_.indexedPixel(viewX + x, viewY + y, 0, argb(presentation_.palette(), 0));
                }
            }
            return;
        }
        if (presentation_.backdropBuffer().empty()) return;
        for (int y = 0; y < viewH; ++y) {
            const size_t n0 = static_cast<size_t>(camY / 8 + y) * presentation_.backdropPitch() +
                            camX / 4;
            for (int x = 0; x < viewW; ++x) {
                const uint8_t index = presentation_.backdropByte(n0 + x, world_.level.tiles);
                if (index >= 176 && index <= 214)
                    canvas_.pixel(viewX + x, viewY + y, presentation_.backdropColor(index));
                else
                    canvas_.indexedPixel(viewX + x, viewY + y, index, presentation_.backdropColor(index));
            }
        }
    }

    void drawGame() {
        canvas_.resetClip();
        // Original frames are painted only by setup/resize, not by each view copy.
        refreshRetainedViewColors(0, kScreenW);
        const auto initialLayout = ViewportLayout::initialize(world_.playerCount, world_.viewWidth);
        const auto& layout = world_.viewportLayout ? *world_.viewportLayout : initialLayout;
        for (int player = 0; player < world_.playerCount; ++player) {
            if (world_.players[static_cast<size_t>(player)].globalState == 0) continue;
            drawWorldView(world_.players[static_cast<size_t>(player)].player,
                          layout.left[static_cast<size_t>(player)] + 4, 4, layout.pitch - 8, 152);
        }
        canvas_.resetClip();
    }

    void refreshRetainedViewColors(int left, int width) {
        // VGA keeps the old indices, but DAC changes still affect their RGB.
        const auto& indices = canvas_.paletteIndices();
        const auto& indexed = canvas_.indexedPixels();
        auto& pixels = canvas_.pixels();
        for (int y = 0; y < 160; ++y) for (int x = left; x < left + width; ++x) {
            const size_t at = static_cast<size_t>(y * kScreenW + x);
            if (indexed[at]) pixels[at] = argb(presentation_.palette(), indices[at]);
        }
    }

    void drawWorldView(const Player& cameraPlayer, int viewX, int viewY, int viewW, int viewH) {
        canvas_.setClip(viewX, viewY, viewX + viewW, viewY + viewH);
        const auto camera = cameraForViewport(static_cast<int>(cameraPlayer.x),
            static_cast<int>(cameraPlayer.y), world_.level.width, world_.level.height,
            viewW + 8, world_.cameraShakeOffset);
        const int camX = camera.pixelX(), camY = camera.pixelY();
        const int fineX = camera.fineX;
        int drawCamX = camX - viewX;
        int drawCamY = camY - viewY;
        drawGradientSky(viewX, viewY, viewW, viewH, camX, camY);
        const auto& visualOrder = world_.visualOrder;
        auto drawForeground = [&](int xCamera, int yCamera) {
            drawTiles(xCamera, yCamera);
            drawFlashes(xCamera, yCamera);
            if (!world_.players[0].dead) {
                drawPlayer(world_.players[0].player, xCamera, yCamera);
            } else if (world_.players[0].lives >= 0 && world_.players[0].state2Cursor.active) {
                drawState2PlayerVisual(world_.players[0].player, world_.players[0].state2Cursor, world_.players[0].state2Effect, xCamera, yCamera);
            }
            if (world_.playerCount > 1 && !world_.players[1].dead) {
                drawPlayer(world_.players[1].player, xCamera, yCamera);
            } else if (world_.playerCount > 1 && world_.players[1].lives >= 0 && world_.players[1].state2Cursor.active) {
                drawState2PlayerVisual(world_.players[1].player, world_.players[1].state2Cursor, world_.players[1].state2Effect, xCamera, yCamera);
            }
            // Driver 08AC:0207..02E9 draws visual slots in increasing order,
            // with the two player slots preceding every non-player actor.
            for (const auto& entry : visualOrder) {
                switch (entry.kind) {
                    case SharedActorKind::Bomb: drawBombs(xCamera, yCamera, entry.order); break;
                    case SharedActorKind::Monster: drawMonsters(xCamera, yCamera, entry.order); break;
                    case SharedActorKind::Reward: drawBonusDrops(xCamera, yCamera, entry.order); break;
                    case SharedActorKind::Effect: {
                        const auto& actor = world_.transientActors[entry.index];
                        text_.drawSprite(assets_.sprites().sprites.at(actor.spriteIndex), actor.x - xCamera, actor.y - yCamera);
                        break;
                    }
                    case SharedActorKind::Marker: {
                        const auto& marker = world_.launchPadMarkers[entry.index];
                        const auto& bank = world_.levelIndex == 6 ? assets_.altSprites() : assets_.sprites();
                        text_.drawSprite(bank.sprites.at(marker.frame - 1), marker.x - xCamera, marker.y - yCamera);
                        break;
                    }
                }
            }
        };
        // 18AC:03C8 copies viewW pixels from a viewW+8-pitch buffer without
        // clipping fine X after shake. Its right tail aliases the next row's
        // left foreground; the backdrop was already copied at the fine origin.
        const int rowPitch = viewW + 8;
        int remaining = viewW;
        int screenX = viewX;
        int sourceX = fineX;
        while (remaining > 0) {
            const int rowCarry = sourceX / rowPitch;
            const int span = std::min(remaining, rowPitch - sourceX % rowPitch);
            canvas_.setClip(screenX, viewY, screenX + span, viewY + viewH);
            drawForeground(drawCamX - rowCarry * rowPitch, drawCamY + rowCarry);
            screenX += span;
            sourceX += span;
            remaining -= span;
        }
        canvas_.setClip(viewX, viewY, viewX + viewW, viewY + viewH);
    }

    void drawTiles(int camX, int camY) {
        int sx = std::max(0, camX / 8);
        int sy = std::max(0, camY / 8);
        int ex = std::min(world_.level.width, (camX + 319) / 8 + 2);
        int ey = std::min(world_.level.height, (camY + 199) / 8 + 2);
        for (int ty = sy; ty < ey; ++ty) {
            for (int tx = sx; tx < ex; ++tx) {
                int id = tileAt(tx, ty);
                const uint8_t* tile = assets_.tiles().tile(id);
                if (!tile || id == 0) continue;
                int px = tx * 8 - camX;
                int py = ty * 8 - camY;
                for (int y = 0; y < 8; ++y) {
                    for (int x = 0; x < 8; ++x) {
                        uint8_t c = tile[y * 8 + x];
                        if (c != 0) canvas_.indexedPixel(px + x, py + y, c, argb(presentation_.palette(), c));
                    }
                }
            }
        }
    }

    void drawBombs(int camX, int camY, uint64_t onlyOrder = 0) {
        for (const Bomb& b : world_.bombs) {
            if (onlyOrder && b.actorOrder != onlyOrder) continue;
            int x = (b.moving ? b.pixelX : b.x * 8) - camX;
            int y = (b.moving ? b.pixelY : b.y * 8) - camY;
            int index = static_cast<int>(bombProfile(b.type).spriteBase);
            if (index >= 0 && index < static_cast<int>(assets_.sprites().sprites.size())) {
                text_.drawSprite(assets_.sprites().sprites[static_cast<size_t>(index)], x, y);
                continue;
            }
            int flashWindow = std::clamp(b.fuseTicks / 4, 6, 28);
            uint32_t body = b.timer <= flashWindow ? 0xfffff070u : renderer_.bombColor(b.type);
            canvas_.rect(x + 1, y + 1, 6, 6, body);
            canvas_.rect(x + 3, y - 1, 2, 2, 0xffff7070u);
        }
    }

    void drawFlashes(int camX, int camY) {
        for (const Flash& f : world_.flashes) {
            canvas_.rect(f.x * 8 - camX, f.y * 8 - camY, 8, 8,
                 f.timer & 1 ? 0xfffff070u : 0xffff5030u);
        }
    }

    void drawMonsters(int camX, int camY, uint64_t onlyOrder = 0) {
        if (assets_.sprites().sprites.empty()) return;
        for (const ActiveMonster& monster : world_.monsters) {
            if (onlyOrder && monster.actorOrder != onlyOrder) continue;
            if (!monster.alive) continue;
            // Level 7 swaps the actor sheet to PROVA.SPR in the original (selector
            // 1000:2C90); boss sprites index that bank.
            const SpriteBank& bank = renderer_.monsterSpriteBank(monster);
            if (bank.sprites.empty()) continue;
            int index = renderer_.monsterSpriteIndex(monster);
            if (index < 0 || index >= static_cast<int>(bank.sprites.size())) continue;
            // monster.y is collision-space; the sprite is drawn at the visual
            // y = collision y + hotspot (the original re-adds actor +0x14 at
            // write-back).
            text_.drawSprite(bank.sprites[static_cast<size_t>(index)],
                       static_cast<int>(monster.x) - camX,
                       renderer_.monsterVisualY(monster) - camY);
        }
    }

    void drawBonusDrops(int camX, int camY, uint64_t onlyOrder = 0) {
        for (const BonusDrop& drop : world_.bonusDrops) {
            if (onlyOrder && drop.actorOrder != onlyOrder) continue;
            int x = static_cast<int>(drop.x) - camX;
            int y = static_cast<int>(drop.y) - camY;
            int index = bonusSpriteIndex(drop.type);
            if (index >= 0 && index < static_cast<int>(assets_.sprites().sprites.size())) {
                text_.drawSprite(assets_.sprites().sprites[static_cast<size_t>(index)], x, y);
            } else {
                canvas_.rect(x, y, 8, 8, 0xffffe060u);
            }
        }
    }

    void drawPlayer(const Player& player, int camX, int camY) {
        int x0 = static_cast<int>(player.x) - camX;
        int y0 = static_cast<int>(player.y) - camY;
        const SpriteBank& bank = world_.levelIndex == 6 || assets_.sprites().sprites.empty() ? assets_.altSprites() : assets_.sprites();
        if (!bank.sprites.empty()) {
            int index = player.spriteIndex;
            if (index >= static_cast<int>(bank.sprites.size())) index = 0;
            const auto& sprite = bank.sprites[static_cast<size_t>(index)];
            if (player.singlePixelSprite) {
                if (!sprite.pixels.empty() && sprite.pixels.front()) {
                    canvas_.indexedPixel(x0, y0, sprite.pixels.front(), argb(presentation_.palette(), sprite.pixels.front()));
                }
            } else {
                text_.drawSprite(sprite, x0, y0);
            }
        } else {
            canvas_.rect(x0, y0, 12, 16, 0xff60e0a0u);
        }
    }

    void drawState2PlayerVisual(const Player& player, const State2VisualCursor& cursor,
                                const State2EffectEntry& effect,
                                int camX, int camY) {
        // 1000:30A3 leaves the descriptor intact; 1000:60E8 rewrites it only
        // when animation advances, using the current level's sprite bank.
        if (!world_.state2CursorPreview && !world_.state2RowPreview) {
            drawPlayer(player, camX, camY);
            return;
        }
        int x0 = (effect.active ? effect.x : static_cast<int>(player.x)) - camX;
        int y0 = (effect.active ? effect.y : static_cast<int>(player.y)) - camY;
        int index = static_cast<int>(cursor.current);
        // Retain the provisional row/cursor comparison as an explicit debug
        // preview. Gameplay uses the observed descriptor latch above.
        constexpr int kState2SpriteRebase = 6;
        if (!world_.state2CursorPreview) {
            if (effect.active && effect.visualFrame == cursor.current) {
                index = static_cast<int>(effect.spriteIndex) + kState2SpriteRebase;
                x0 += static_cast<int>(effect.drawDx);
                y0 += static_cast<int>(effect.drawDy);
            } else {
                State2VisualRow row;
                if (originalState2VisualRow(cursor.current, row)) {
                    index = static_cast<int>(row.row3) + kState2SpriteRebase;
                    x0 += static_cast<int>(row.row0);
                    y0 += static_cast<int>(row.row1);
                }
            }
        }
        if (index >= 0 && index < static_cast<int>(assets_.sprites().sprites.size())) {
            text_.drawSprite(assets_.sprites().sprites[static_cast<size_t>(index)], x0, y0);
            return;
        }
        uint32_t color = 0xfff0c050u + ((cursor.current & 0x07u) << 8);
        canvas_.rect(x0, y0 + 4, 14, 8, color);
        canvas_.rect(x0 + 3, y0, 8, 16, 0xff703020u);
    }
    int tileAt(int tx, int ty) const {
        if (tx < 0 || ty < 0 || tx >= world_.level.width || ty >= world_.level.height) return 0;
        return world_.level.tiles[static_cast<size_t>(ty) * world_.level.width + tx];
    }
private:
    Canvas& canvas_;
    TextRenderer& text_;
    const AssetCatalog& assets_;
    const PresentationState& presentation_;
    const GameRenderer& renderer_;
    const WorldRenderView& world_;
};
}

void GameRenderer::drawGame(const WorldRenderView& world, const HudView& hud) {
    WorldPainter preview(canvas_, text_, assets_, presentation_, *this, world);
    if (world.state2CursorPreview || world.state2RowPreview) preview.drawGame();
    else {
        canvas_.resetClip();
        preview.refreshRetainedViewColors(0, kScreenW);
        worldRaster_.drawGame(world, presentation_, canvas_);
        canvas_.resetClip();
    }
    drawHud(hud);
}

void GameRenderer::initializePlayfield(int playerCount, int viewWidth) {
    // 2C7A clears VGA after the intro; 2959 paints the configured frames even
    // for an already-out player. Per-frame view gates must not inherit intro pixels.
    canvas_.resetClip();
    canvas_.indexedRect(0, 0, kScreenW, kScreenH, 0, argb(presentation_.palette(), 0));
    if (playerCount == 2) {
        fillViewFrame(canvas_, presentation_.palette(), 0, 160, 15, 28);
        fillViewFrame(canvas_, presentation_.palette(), 160, 160, 4, 12);
    } else if (playerCount == 1) {
        const int width = std::clamp(viewWidth, 168, kScreenW);
        fillViewFrame(canvas_, presentation_.palette(), (kScreenW - width) / 2, width, 15, 28);
    }
}

void GameRenderer::resizePlayfield(int viewWidth) {
    // 820F..8283 clear only the playfield, preserving the existing HUD.
    canvas_.resetClip();
    canvas_.indexedRect(0, 0, kScreenW, 160, 0, argb(presentation_.palette(), 0));
    const int width = std::clamp(viewWidth, 168, kScreenW);
    fillViewFrame(canvas_, presentation_.palette(), (kScreenW - width) / 2, width, 15, 28);
}

void GameRenderer::clearEliminatedViewport(int playerIndex) {
    if (playerIndex < 0 || playerIndex > 1) throw std::invalid_argument("Eliminated viewport index differs");
    // 7CD3..7CE9 clears this physical half only when another player remains.
    canvas_.resetClip();
    canvas_.indexedRect(playerIndex * 160, 0, 160, 160, 0, argb(presentation_.palette(), 0));
}

void GameRenderer::drawWorldView(const WorldRenderView& world, const Player& cameraPlayer,
                                 int viewX, int viewY, int viewW, int viewH) {
    if (world.state2CursorPreview || world.state2RowPreview)
        WorldPainter(canvas_, text_, assets_, presentation_, *this, world)
            .drawWorldView(cameraPlayer, viewX, viewY, viewW, viewH);
    else {
        canvas_.setClip(viewX, viewY, viewX + viewW, viewY + viewH);
        worldRaster_.drawView(world, cameraPlayer, viewX, viewY, viewW, viewH, presentation_, canvas_);
    }
}

bool GameRenderer::isBossActor(const ActiveMonster& monster) const {
    return monster.behavior == 5 || monster.behavior == 6 || monster.bossDebris;
}

const SpriteBank& GameRenderer::monsterSpriteBank(const ActiveMonster& monster) const {
    return isBossActor(monster) ? assets_.altSprites() : assets_.sprites();
}

int GameRenderer::monsterVisualY(const ActiveMonster& monster) const {
    return static_cast<int16_t>(static_cast<int>(monster.y) + monster.hotspotY);
}

int GameRenderer::monsterSpriteIndex(const ActiveMonster& monster) const {
    if (isBossActor(monster)) {
        int bossIndex = monster.animFrame;
        if (bossIndex >= 0 &&
            bossIndex < static_cast<int>(assets_.altSprites().sprites.size())) {
            return bossIndex;
        }
        return std::min<int>(static_cast<int>(assets_.altSprites().sprites.size()) - 1, 39);
    }
    int index = monster.behavior == 2 ? static_cast<int>(monster.corpseSprite)
                                      : monster.animFrame;
    if (index >= 0 && index < static_cast<int>(assets_.sprites().sprites.size())) return index;
    return std::min<int>(assets_.sprites().sprites.size() - 1, 39);
}


uint32_t GameRenderer::bombColor(BombType type) const {
    switch (type) {
        case BombType::Small: return 0xff181818u;
        case BombType::Medium: return 0xff4058d0u;
        case BombType::Large: return 0xffd05040u;
        case BombType::Super: return 0xff60d060u;
    }
    return 0xff181818u;
}

int GameRenderer::nameEntryCursorSlot(const std::string& name) const {
    return std::min<int>(static_cast<int>(name.size()),
                         kNameEntrySlotCount - 1);
}

int GameRenderer::nameEntrySlotX(int slot) const {
    return kNameEntryLabelX + slot * kNameEntrySlotAdvance;
}
}
