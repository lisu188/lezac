#include "gameplay/game_session.hpp"
#include "diagnostics/gameplay/gameplay_replay.hpp"
#include <iostream>
#include <stdexcept>
#include <type_traits>

using namespace lezac;
using namespace lezac::gameplay;

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

struct Host {
    const resources::AssetCatalog& assets;
    rendering::Canvas canvas;
    rendering::PresentationState presentation;
    ui::UiController ui;
    ui::RecordStore records;
    ui::LevelFlow flow;
    ui::LevelIntroPattern endPattern{};
    sound::SoundEngine sound;
    sound::SdlAudioOutput audio;
    rendering::TextRenderer text;
    rendering::GameRenderer renderer;
    rendering::ViewportLayout viewport;
    int width = 320;
    int configuredPlayers = 0;
    uint32_t milliseconds = 1000;
    std::vector<std::string> phases;
    std::function<void()> present;
    std::function<void()> presentPalette;
    std::function<void(size_t)> resultReel;
    std::function<void(size_t, uint32_t, uint32_t)> resultTyping;
    std::function<void()> actorPass;
    std::function<void(const Bomb&, const char*)> bombExpiry;
    std::function<void(const ActiveMonster&, bool)> animation;
    std::function<void(uint8_t)> death;
    std::function<void(uint8_t, uint8_t)> health;
    std::function<void(const char*)> reentry;

    explicit Host(const resources::AssetCatalog& catalog)
        : assets(catalog), sound(assets.sounds()), text(canvas, presentation.palette(), assets.fontSprites()),
          renderer(canvas, text, assets, presentation) {
        presentation.setPalette(assets.palette());
        presentation.captureInitialPalette();
        ui.setMenu(false);
    }

    GameplayServices services() {
        return {assets, sound, audio, presentation, ui, records, flow, endPattern, canvas, renderer,
                viewport, width, configuredPlayers, [this] { return milliseconds; }, [] {},
                present, presentPalette, resultReel, resultTyping, actorPass, bombExpiry,
                animation, death, health, reentry};
    }

    template<class Game>
    void observe(Game& game) {
        const auto record = [this, &game](const std::string& phase) {
            const auto view = game.view();
            phases.push_back(phase + ":" + std::to_string(view.logicTick_) + ":" +
                             std::to_string(view.randomSeed_) + ":" +
                             std::to_string(view.actorSlots_.count()) + ":" +
                             std::to_string(view.levelResetGeneration_));
        };
        present = [this, &game, record] {
            record("frame");
            const auto order = game.prepareRenderState();
            const auto world = game.worldRenderView(order);
            renderer.drawGame(world, game.hudView());
        };
        presentPalette = [this, record] {
            record("palette");
            canvas.resolvePalette(presentation.palette());
        };
        actorPass = [record] { record("actors"); };
        death = [record](uint8_t player) { record("death-" + std::to_string(player)); };
        health = [record](uint8_t player, uint8_t value) {
            record("health-" + std::to_string(player) + "-" + std::to_string(value));
        };
        reentry = [record](const char* phase) { record(phase); };
        bombExpiry = [record](const Bomb&, const char* phase) { record(phase); };
    }
};

void hiddenStateEquality() {
    MapPlaneMemory first, second;
    first.beginLevel({}, {}, 64);
    second.beginLevel({}, {}, 65);
    require(first != second, "map comparison omitted retained allocation metadata");

    RetainedRecordQueue<FlameRecord> a, b;
    FlameRecord record{};
    a.push_back(record);
    b.push_back(record);
    a.pop_back();
    b.pop_back();
    b.retainedSlot(0).cell = 7;
    require(a.empty() && b.empty() && a != b, "queue comparison omitted inactive tail records");

    ActorSlots actorA, actorB;
    auto state = actorA.state();
    std::array<uint64_t, ActorStorage::capacity + 1> orders{};
    state.actors.back()[17] = 9;
    actorB.restoreForFixture(state, orders);
    require(actorA != actorB, "actor comparison omitted inactive physical records");
    state.count = 1;
    state.visualCount = 3;
    state.actors[1][1] = 2;
    orders[1] = 41;
    actorA.restoreForFixture(state, orders);
    orders[1] = 42;
    actorB.restoreForFixture(state, orders);
    require(actorA != actorB, "actor comparison omitted physical identity bindings");
}

void compareSessionAndReplay(const resources::AssetCatalog& assets, int level, int players) {
    Host liveHost(assets), replayHost(assets);
    GameSession live(liveHost.services());
    diagnostics::GameplayReplay replay(replayHost.services());
    live.uiActions().prepareNewGame(players);
    replay.uiActions().prepareNewGame(players);
    live.setRandomSeed(0x1234abcd);
    replay.setRandomSeed(0x1234abcd);
    live.resetLevel(level);
    replay.resetLevel(level);
    live.buildBackdropBuffer();
    replay.buildBackdropBuffer();
    require(*live.snapshotOwned() == replay.fixture(), "initial recovered session state differs");
    const auto initial = live.snapshotOwned();
    replay.fixture().player_.x += 32;
    replay.fixture().level_.tiles[0] ^= 1;
    replay.fixture().damageLaneData_[100] ^= 1;
    require(live.view().player_.x == initial->player_.x &&
            live.view().level_.tiles == initial->level_.tiles &&
            live.view().damageLaneData_ == initial->damageLaneData_,
            "detached diagnostic writes reached the live state");
    replay.replaceFixture(*initial);

    liveHost.observe(live);
    replayHost.observe(replay);
    for (int tick = 0; tick < 180; ++tick) {
        const auto copies = live.fixtureCopyCounts();
        FrameControls controls{};
        controls.p1Right = tick < 50;
        controls.p1Left = tick >= 80 && tick < 110;
        controls.p1Jump = tick % 31 == 0;
        controls.p2Left = players == 2 && tick < 40;
        controls.p2Right = players == 2 && tick >= 70 && tick < 110;
        controls.p2Jump = players == 2 && tick % 37 == 0;
        if (tick % 29 == 0) {
            live.setFireLatch(1, true);
            replay.setFireLatch(1, true);
            const auto state = live.view();
            live.fireAtPlayer(1, static_cast<int>(state.player_.x), static_cast<int>(state.player_.y));
            replay.fireAtPlayer(1, static_cast<int>(state.player_.x), static_cast<int>(state.player_.y));
        }
        live.updateWithControls(controls, 1.0f / 60.0f);
        replay.updateWithControls(controls, 1.0f / 60.0f);
        require(live.fixtureCopyCounts().snapshots == copies.snapshots &&
                live.fixtureCopyCounts().restores == copies.restores,
                "live input, tick, callbacks or rendering copied a diagnostic fixture");
        require(*live.snapshotOwned() == replay.fixture(), "complete live/replay state or RNG differs");
        require(liveHost.phases == replayHost.phases, "callback phase ordering or observations differ");
        require(liveHost.canvas.pixels() == replayHost.canvas.pixels(), "rendered live/replay pixels differ");
        if (tick == 90) {
            live.beginLevelForPlay(level);
            replay.beginLevelForPlay(level);
            require(*live.snapshotOwned() == replay.fixture(), "reload changed map ownership, callbacks or RNG");
        }
    }
}
}

int main() {
    static_assert(!std::is_copy_constructible_v<GameSession>);
    static_assert(!std::is_move_constructible_v<GameSession>);
    static_assert(!std::is_copy_assignable_v<GameSession>);
    static_assert(!std::is_move_assignable_v<GameSession>);
    static_assert(!std::is_copy_constructible_v<diagnostics::GameplayReplay>);
    static_assert(!std::is_move_constructible_v<diagnostics::GameplayReplay>);
    static_assert(!std::is_convertible_v<GameSession*, detail::GameplayOperations*>);
    static_assert(!std::is_convertible_v<diagnostics::GameplayReplay*, detail::GameplayOperations*>);
    static_assert(std::is_const_v<std::remove_reference_t<decltype(GameplayView::monsters_)>>);
    static_assert(std::is_const_v<std::remove_reference_t<decltype(GameplayView::actorSlots_)>>);
    static_assert(std::is_const_v<std::remove_reference_t<decltype(GameplayView::mapPlaneMemory_)>>);
    hiddenStateEquality();
    const auto assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
    compareSessionAndReplay(assets, 0, 1);
    compareSessionAndReplay(assets, 1, 2);
    compareSessionAndReplay(assets, 6, 1);
    std::cout << "gameplay_owned_fixture_api=ok complete_state_ticks=540 inactive_tails=1 rng=1 phase_order=1 live_fixture_copies=0\n";
}
