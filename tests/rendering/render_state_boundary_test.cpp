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
    for (int players : {2, 1}) {
        presentation.initializeBackdropBuffer(players);
        const int pitch = players == 2 ? 160 : 320;
        if (presentation.backdropPitch() != pitch || presentation.backdropBuffer().size() != 60000)
            throw std::runtime_error("startup gradient dimensions changed");
        for (size_t i = 0; i < 60000; ++i)
            if (presentation.backdropBuffer()[i] != static_cast<uint8_t>(176 + i / (4 * pitch)))
                throw std::runtime_error("startup gradient bytes changed");
    }
    core::TurboRandom random(0x1234abcd);
    presentation.buildBackdropBuffer(1, random);
    presentation.captureInitialPalette();
    presentation.resetHudForLevel();
    // Explicit presentation transitions happen before painting, including a
    // partially animated score and an in-flight objective palette fade.
    presentation.prepareHudObjectives(29, 1, 75, 1, 100);
    if (presentation.hudDestructionPercent() != 0)
        throw std::runtime_error("HUD destruction sampled outside its 30-tick boundary");
    presentation.prepareHudObjectives(30, 1, 75, 1, 100);
    presentation.updateHudScores(2, {{123, 999}}, {{false, true}}, {{0, 0}});
    presentation.updateHudEnergy(0, 73, 1);
    presentation.updateHudEnergy(0, 11, 2);
    presentation.updateHudEnergy(1, 41, 0);
    if (presentation.hudEnergy()[0].fill != 73 || presentation.hudEnergy()[1].painted)
        throw std::runtime_error("waiting/out player changed HUD energy");
    presentation.updateHudEnergy(1, 41, 1);
    presentation.updateHudEnergy(1, 257, 1);
    presentation.advanceHudPalette();
    if (presentation.hudDestructionPercent() != 75 || !presentation.hudColumnReady()[0] ||
        presentation.hudColumnReady()[1] || presentation.hudScores()[1].phase != 0)
        throw std::runtime_error("HUD presentation lifecycle changed");
    auto level = assets.levels().front();
    presentation.beginLevel(level.tiles.size());
    rendering::Canvas canvas;
    rendering::TextRenderer text(canvas, presentation.palette(), assets.fontSprites());
    rendering::GameRenderer renderer(canvas, text, assets, presentation);
    gameplay::ActiveMonster corpse;
    corpse.kind = 12;
    corpse.behavior = 2;
    corpse.hotspotY = 6;
    for (const auto& sample : std::array<std::array<int, 2>, 4>{{
            {{32760, 32766}}, {{32762, -32768}}, {{32767, -32763}}, {{-32768, -32762}}
        }}) {
        corpse.y = sample[0];
        if (renderer.monsterVisualY(corpse) != sample[1])
            throw std::runtime_error("monster visual Y did not retain its signed word");
    }
    gameplay::Player player, player2;
    gameplay::State2VisualCursor cursor;
    gameplay::State2EffectEntry effect;
    gameplay::BombInventory inventory;
    inventory.counts = {98, 7, 3, 1};
    presentation.sampleHudInventory(0, inventory, 1);
    --inventory.counts[0];
    inventory.selected = gameplay::BombType::Large;
    presentation.sampleHudInventory(0, inventory, 2);
    presentation.sampleHudInventory(0, inventory, 0);
    presentation.sampleHudInventory(1, inventory, 1);
    if (presentation.hudInventories()[0].counts[0] != 98 ||
        presentation.hudInventories()[0].selected != gameplay::BombType::Small ||
        presentation.hudInventories()[1].counts[0] != 97 ||
        presentation.hudInventories()[1].selected != gameplay::BombType::Large)
        throw std::runtime_error("HUD inventory did not retain its pre-player sample");
    std::vector<gameplay::Bomb> bombs(1);
    bombs[0].x = 5; bombs[0].y = 6;
    // Intentionally leave an unadopted actor. Rendering must not assign order.
    std::vector<gameplay::ActiveMonster> monsters;
    std::vector<gameplay::BonusDrop> rewards;
    std::vector<gameplay::Flash> flashes;
    std::vector<gameplay::LaunchPadMarker> markers;
    std::vector<gameplay::TransientActor> transients;
    std::vector<gameplay::SharedActorEntry> visualOrder{{0, gameplay::SharedActorKind::Bomb, 0}};
    rendering::WorldRenderView world{level, 0, 2,
        {{{player, false, 3, cursor, effect}, {player2, false, 3, cursor, effect}}},
        bombs, monsters, rewards, flashes, markers, transients, visualOrder,
        320, true, 0, false, false};
    rendering::HudView hud{2, {{{presentation.hudEnergy()[0], 0, 3, presentation.hudInventories()[0]},
                              {presentation.hudEnergy()[1], 0, 3, presentation.hudInventories()[1]}}},
        level.objectiveTile, level.requiredBonus, level.requiredDestruction, 1,
        presentation.hudDestructionPercent(), false, false, presentation.hudScores(), presentation.hudColumnReady()};
    const auto state = presentation.snapshot();
    // The original HUD samples the low 16-bit frame word, including wrap to
    // zero; the 32-bit application tick is not itself the modulo-30 clock.
    presentation.prepareHudObjectives(static_cast<uint16_t>(65535u), 1, 90, 1, 100);
    if (presentation.hudDestructionPercent() != 75)
        throw std::runtime_error("HUD sampled before frame-word wrap");
    presentation.prepareHudObjectives(static_cast<uint16_t>(65536u), 1, 90, 1, 100);
    if (presentation.hudDestructionPercent() != 90)
        throw std::runtime_error("HUD did not sample at frame-word wrap");
    presentation.prepareHudObjectives(static_cast<uint16_t>(65550u), 1, 10, 1, 100);
    if (presentation.hudDestructionPercent() != 90)
        throw std::runtime_error("HUD sampled the 32-bit tick instead of the frame word");
    presentation.prepareHudObjectives(static_cast<uint16_t>(65566u), 1, 10, 1, 100);
    if (presentation.hudDestructionPercent() != 10)
        throw std::runtime_error("HUD missed the next wrapped sampling boundary");
    presentation.restore(state);
    const auto tiles = level.tiles;
    const auto seed = random.seed();
    renderer.drawGame(world, hud);
    const auto first = canvas.pixels();
    inventory.counts.fill(0);
    inventory.selected = gameplay::BombType::Super;
    for (int playerIndex = 0; playerIndex < 2; ++playerIndex) {
        const int start = 165 * 320 + playerIndex * 180 + 1;
        const int fill = playerIndex == 0 ? 73 : 41;
        if (std::count(first.begin() + start, first.begin() + start + 100, 0xffffff55u) != fill)
            throw std::runtime_error("renderer ignored cached painted energy");
    }
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
    auto checkHud = [](const rendering::PresentationSnapshot& expected,
                       const rendering::PresentationSnapshot& actual) {
        if (actual.outroBackdrop != expected.outroBackdrop || actual.outroIndices != expected.outroIndices ||
            actual.outroIndexedPixels != expected.outroIndexedPixels ||
            actual.hudColumnReady != expected.hudColumnReady ||
            actual.hudPreviousCollected != expected.hudPreviousCollected ||
            actual.hudPreviousDestruction != expected.hudPreviousDestruction ||
            actual.hudDestructionPercent != expected.hudDestructionPercent ||
            actual.hudBonusComplete != expected.hudBonusComplete ||
            actual.hudDestructionComplete != expected.hudDestructionComplete ||
            actual.originalPlayInitialized != expected.originalPlayInitialized ||
            actual.hudPaletteQueue.count != expected.hudPaletteQueue.count)
            throw std::runtime_error("HUD presentation snapshot changed");
        for (size_t i = 0; i < 2; ++i) {
            if (actual.hudInventories[i].counts != expected.hudInventories[i].counts ||
                actual.hudInventories[i].selected != expected.hudInventories[i].selected)
                throw std::runtime_error("rendering changed sampled HUD inventory");
            const auto& ae = actual.hudEnergy[i];
            const auto& ee = expected.hudEnergy[i];
            if (ae.cached != ee.cached || ae.fill != ee.fill || ae.painted != ee.painted)
                throw std::runtime_error("rendering changed cached energy state");
            const auto& a = actual.hudScores[i];
            const auto& e = expected.hudScores[i];
            const auto& aq = actual.hudPaletteQueue.entries[i];
            const auto& eq = expected.hudPaletteQueue.entries[i];
            if (a.value != e.value || a.phase != e.phase || a.current != e.current || a.target != e.target ||
                aq.index != eq.index || aq.current != eq.current || aq.target != eq.target)
                throw std::runtime_error("rendering advanced HUD score/fade state");
        }
    };
    checkHud(state, after);
    auto introState = state;
    introState.hudPaletteQueue.count = 0;
    introState.hudPreviousCollected = 20000;
    introState.hudPreviousDestruction = 200;
    introState.hudDestructionPercent = 0;
    introState.hudBonusComplete = false;
    introState.hudDestructionComplete = false;
    presentation.resetHudObjectivesForLevel();
    checkHud(introState, presentation.snapshot());
    for (size_t i = 0; i < 256; ++i) {
        const auto& expected = state.palette[i];
        const auto& actual = presentation.palette()[i];
        if (actual.r != expected.r || actual.g != expected.g || actual.b != expected.b)
            throw std::runtime_error("pre-intro objective reset changed the palette");
    }
    presentation.restore(state);
    presentation.resetHudForLevel();
    if (presentation.hudBonusComplete() || presentation.hudDestructionComplete())
        throw std::runtime_error("level reset retained completion flags");
    for (const auto& cached : presentation.hudInventories()) {
        if (cached.counts != gameplay::BombInventory{}.counts || cached.selected != gameplay::BombType::Small)
            throw std::runtime_error("level reset retained sampled ammunition");
    }
    for (const auto& energy : presentation.hudEnergy()) {
        if (energy.cached != 255 || energy.fill != 0 || energy.painted)
            throw std::runtime_error("level reset retained cached energy state");
    }
    hud.players[0].energy = presentation.hudEnergy()[0];
    hud.players[1].energy = presentation.hudEnergy()[1];
    renderer.drawHud(hud);
    for (int playerIndex = 0; playerIndex < 2; ++playerIndex) {
        const int start = 165 * 320 + playerIndex * 180 + 1;
        if (!std::all_of(canvas.pixels().begin() + start, canvas.pixels().begin() + start + 100,
                         [](uint32_t pixel) { return pixel == 0xffb6b6b6u; }))
            throw std::runtime_error("unpainted energy row lost its initial grey fill");
    }
    if (presentation.hudScores()[0].current != state.hudScores[0].current ||
        presentation.hudScores()[0].value != 123 || presentation.hudPaletteQueue().count != 0 ||
        presentation.hudColumnReady()[0] || presentation.palette()[245].r != state.initialPalette[245].r)
        throw std::runtime_error("level reset lost score reels or initial palette");
    presentation.clearHudScores();
    presentation.beginOriginalPlay(true);
    if (!std::all_of(presentation.backdropBuffer().begin(), presentation.backdropBuffer().end(),
                     [](uint8_t byte) { return byte == 0; }))
        throw std::runtime_error("first play did not clear the backdrop buffer");
    presentation.writeBackdropPrefix({99});
    presentation.beginOriginalPlay(true);
    if (presentation.backdropBuffer()[0] != 99)
        throw std::runtime_error("later play cleared the persistent backdrop buffer");
    presentation.restore(state);
    checkHud(state, presentation.snapshot());
    level.tiles[0] = 33;
    if (presentation.backdropByte(60008, level.tiles) != 33)
        throw std::runtime_error("backdrop overflow no longer aliases the live map");
    {
        rendering::PresentationState objectives;
        objectives.setPalette(assets.palette());
        objectives.captureInitialPalette();
        objectives.resetHudForLevel();
        objectives.prepareHudObjectives(29, 1, 75, 1, 50);
        if (!objectives.hudBonusComplete() || objectives.hudDestructionComplete())
            throw std::runtime_error("completion bypassed the cached destruction percentage");
        for (int tick = 0; tick < 35; ++tick) objectives.advanceHudPalette();
        if (objectives.hudPaletteQueue().count != 0)
            throw std::runtime_error("objective palette did not drain");
        objectives.prepareHudObjectives(30, 1, 75, 1, 50);
        const auto& queue = objectives.hudPaletteQueue();
        if (!objectives.hudDestructionComplete() || queue.count != 2 ||
            queue.entries[0].index != 246 || queue.entries[1].index != 224)
            throw std::runtime_error("latched objectives did not request the border palette");
        objectives.advanceHudPalette();
        objectives.prepareHudObjectives(31, 0, 0, 1, 50);
        if (!objectives.hudBonusComplete() || !objectives.hudDestructionComplete() ||
            queue.count != 2 || queue.entries[0].current[0] != 61 || queue.entries[1].current[0] != 63)
            throw std::runtime_error("completion latch or dirty-only border replacement changed");
        objectives.advanceHudPalette();
        objectives.prepareHudObjectives(32, 0, 0, 1, 50);
        if (queue.entries[1].current[0] != 61)
            throw std::runtime_error("unchanged objectives restarted the border fade");
        const auto completed = objectives.snapshot();
        objectives.resetHudForLevel();
        if (objectives.hudBonusComplete() || objectives.hudDestructionComplete())
            throw std::runtime_error("completion flags survived level reset");
        objectives.restore(completed);
        checkHud(completed, objectives.snapshot());
        objectives.prepareHudObjectives(60, 0, 0, 1, 50);
        if (!objectives.hudBonusComplete() || !objectives.hudDestructionComplete())
            throw std::runtime_error("completion flags were cleared when counters dropped");
        objectives.resetHudForLevel();
        objectives.prepareHudObjectives(1, 0, 0, 0, 0);
        if (!objectives.hudBonusComplete() || !objectives.hudDestructionComplete() ||
            objectives.hudPaletteQueue().count != 2)
            throw std::runtime_error("zero targets or full palette queue semantics changed");
        for (int tick = 0; tick < 35; ++tick) objectives.advanceHudPalette();
        objectives.prepareHudObjectives(2, 0, 0, 0, 0);
        if (objectives.hudPaletteQueue().count != 0)
            throw std::runtime_error("unchanged objectives invoked the native HUD helper");
        objectives.prepareHudObjectives(3, 1, 0, 0, 0);
        if (objectives.hudPaletteQueue().count != 2 || objectives.hudPaletteQueue().entries[1].index != 224)
            throw std::runtime_error("dirty completed objectives did not request the border");
    }
    {
        rendering::Canvas retained;
        retained.clear(0xff112233u);
        retained.setClip(4, 4, 6, 6);
        retained.indexedPixel(3, 4, 7, 0xff112233u);
        retained.indexedPixel(4, 4, 7, 0xff112233u);
        retained.indexedPixel(5, 4, 8, 0xff112233u);
        retained.indexedRect(4, 5, 2, 1, 9, 0xff112233u);
        retained.pixel(5, 5, 0xff112233u);
        auto colors = presentation.palette();
        colors[7] = {255, 0, 0}; colors[8] = {0, 255, 0}; colors[9] = {0, 0, 255};
        presentation.setPalette(colors);
        presentation.freezeOutroBackdrop(retained);
        const auto saved = presentation.snapshot();
        const auto recolored = presentation.resolveOutroBackdrop();
        presentation.resetHudObjectivesForLevel();
        if (presentation.resolveOutroBackdrop() != recolored)
            throw std::runtime_error("pre-intro reset cleared the frozen results frame");
        presentation.restore(saved);
        if (recolored[4 * 320 + 3] != 0xff112233u || recolored[4 * 320 + 4] != 0xffff0000u ||
            recolored[4 * 320 + 5] != 0xff00ff00u || recolored[5 * 320 + 4] != 0xff0000ffu ||
            recolored[5 * 320 + 5] != 0xff112233u || retained.pixels()[4 * 320 + 4] != 0xff112233u)
            throw std::runtime_error("retained frame lost clipped indexed colors or recolored fixed RGB");
        retained.clear(0);
        if (std::any_of(retained.indexedPixels().begin(), retained.indexedPixels().end(),
                        [](uint8_t indexed) { return indexed != 0; }))
            throw std::runtime_error("canvas clear retained stale palette indices");
        presentation.resetHudForLevel();
        if (!presentation.outroBackdrop().empty())
            throw std::runtime_error("level reset retained the results frame");
        presentation.restore(saved);
        checkHud(saved, presentation.snapshot());
        if (presentation.resolveOutroBackdrop() != recolored)
            throw std::runtime_error("snapshot restore lost indexed results colors");
    }
    std::cout << "render_state_boundary=ok repeat_pixels=1 nonblank=1 rng_unchanged=1 actor_order_unchanged=1 palette_unchanged=1 live_map_alias=1\n";
}
