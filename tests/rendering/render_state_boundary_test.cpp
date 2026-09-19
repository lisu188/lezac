#include "rendering/game_renderer.hpp"
#include "rendering/presentation_state.hpp"
#include "resources/asset_catalog.hpp"
#include <algorithm>
#include <iostream>
#include <stdexcept>

using namespace lezac;

int main() {
    const auto assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
    rendering::PresentationState presentation;
    presentation.setPalette(assets.palette());
    core::TurboRandom random(0x1234abcd);
    presentation.buildBackdropBuffer(1, random);
    auto level = assets.levels().front();
    presentation.beginLevel(level.tiles.size());
    rendering::Canvas canvas;
    rendering::TextRenderer text(canvas, presentation.palette(), assets.fontSprites());
    rendering::GameRenderer renderer(canvas, text, assets, presentation);
    gameplay::Player player, player2;
    gameplay::State2VisualCursor cursor;
    gameplay::State2EffectEntry effect;
    gameplay::BombInventory inventory;
    std::vector<gameplay::Bomb> bombs(1);
    bombs[0].x = 5; bombs[0].y = 6;
    // Intentionally leave an unadopted actor. Rendering must not assign order.
    std::vector<gameplay::ActiveMonster> monsters;
    std::vector<gameplay::BonusDrop> rewards;
    std::vector<gameplay::Flash> flashes;
    std::vector<gameplay::LaunchPadMarker> markers;
    std::vector<gameplay::TransientActor> transients;
    std::vector<gameplay::SharedActorEntry> visualOrder{{0, gameplay::SharedActorKind::Bomb, 0}};
    rendering::WorldRenderView world{level, 0, 1,
        {{{player, false, 3, cursor, effect}, {player2, false, 3, cursor, effect}}},
        bombs, monsters, rewards, flashes, markers, transients, visualOrder,
        320, true, 0, false, false};
    rendering::HudView hud{1, {{{100, 0, 3, false, inventory}, {100, 0, 3, false, inventory}}},
        level.objectiveTile, level.requiredBonus, level.requiredDestruction, 0, 0, false, false};
    const auto state = presentation.snapshot();
    const auto tiles = level.tiles;
    const auto seed = random.seed();
    renderer.drawGame(world, hud);
    const auto first = canvas.pixels();
    renderer.drawGame(world, hud);
    if (first != canvas.pixels() || std::all_of(first.begin(), first.end(),
            [&](uint32_t pixel) { return pixel == first.front(); }))
        throw std::runtime_error("repeat rendering changed or produced a uniform frame");
    const auto after = presentation.snapshot();
    for (size_t i = 0; i < 256; ++i) {
        if (state.palette[i].r != after.palette[i].r || state.palette[i].g != after.palette[i].g ||
            state.palette[i].b != after.palette[i].b)
            throw std::runtime_error("rendering changed palette state");
    }
    if (after.backdrop != state.backdrop || after.heapPadding != state.heapPadding ||
        after.mapTileCount != state.mapTileCount || after.pitch != state.pitch || after.redPhase != state.redPhase ||
        level.tiles != tiles || random.seed() != seed || bombs[0].actorOrder != 0 || bombs[0].timer != 40)
        throw std::runtime_error("rendering mutated simulation/presentation state");
    level.tiles[0] = 33;
    if (presentation.backdropByte(60008, level.tiles) != 33)
        throw std::runtime_error("backdrop overflow no longer aliases the live map");
    std::cout << "render_state_boundary=ok repeat_pixels=1 nonblank=1 rng_unchanged=1 actor_order_unchanged=1 palette_unchanged=1 live_map_alias=1\n";
}
