#pragma once

#include "rendering/canvas.hpp"
#include "rendering/presentation_state.hpp"
#include "rendering/render_views.hpp"
#include "rendering/text_renderer.hpp"
#include "resources/asset_catalog.hpp"

namespace lezac::rendering {

class GameRenderer {
public:
    GameRenderer(Canvas& canvas, TextRenderer& text, const resources::AssetCatalog& assets,
                 const PresentationState& presentation)
        : canvas_(canvas), text_(text), assets_(assets), presentation_(presentation) {}
    void drawGame(const WorldRenderView& world, const HudView& hud);
    void drawWorldView(const WorldRenderView& world, const gameplay::Player& cameraPlayer,
                       int viewX, int viewY, int viewW, int viewH);
    void drawHud(const HudView& hud);
    void drawMenu(const MenuView& menu);
    void drawLevelIntro(int levelIndex, const ui::LevelIntroPattern& pattern, size_t visibleCharacters);
    void drawLevelOutro(const OutroView& outro);
    void drawPauseOverlay();
    bool isBossActor(const gameplay::ActiveMonster& monster) const;
    const resources::SpriteBank& monsterSpriteBank(const gameplay::ActiveMonster& monster) const;
    int monsterSpriteIndex(const gameplay::ActiveMonster& monster) const;
    uint32_t bombColor(gameplay::BombType type) const;
    int nameEntryCursorSlot(const std::string& name) const;
    int nameEntrySlotX(int slot) const;
private:
    Canvas& canvas_;
    TextRenderer& text_;
    const resources::AssetCatalog& assets_;
    const PresentationState& presentation_;
};

}
