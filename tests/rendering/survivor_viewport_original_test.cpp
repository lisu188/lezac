#include "diagnostics/survivor_viewport_fixture.hpp"
#include "rendering/game_renderer.hpp"
#include "resources/asset_catalog.hpp"
#include "ui/ui_controller.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>

using namespace lezac;
namespace {
void require(bool valid, const char* reason) {
    if (!valid) throw std::runtime_error(reason);
}
void rgb(std::ostream& out, uint32_t pixel) {
    out.put(static_cast<char>(pixel >> 16)); out.put(static_cast<char>(pixel >> 8)); out.put(static_cast<char>(pixel));
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 2 || argc == 3, "Expected survivor viewport fixture and optional pixel dump");
        const auto fixture = diagnostics::readSurvivorViewportFixture(argv[1]);
        const auto assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
        auto level = assets.levels().front();
        level.tiles = fixture.map;
        size_t spriteOffset = 0;
        for (size_t index = 0; index < assets.sprites().sprites.size(); ++index) {
            const auto& sprite = assets.sprites().sprites[index];
            const size_t at = (index + 1) * 4;
            require(at + 4 <= fixture.descriptors.size() && fixture.descriptors[at] == sprite.width &&
                    fixture.descriptors[at + 1] == sprite.height &&
                    (fixture.descriptors[at + 2] | fixture.descriptors[at + 3] << 8) == static_cast<int>(spriteOffset),
                    "Original survivor sprite backing differs");
            spriteOffset += static_cast<size_t>(sprite.width * sprite.height);
        }
        const gameplay::State2EffectEntry effect;
        const std::vector<gameplay::Bomb> bombs;
        const std::vector<gameplay::ActiveMonster> monsters;
        const std::vector<gameplay::BonusDrop> bonuses;
        const std::vector<gameplay::Flash> flashes;
        const std::vector<gameplay::LaunchPadMarker> markers;
        const std::vector<gameplay::TransientActor> transients;
        const std::vector<gameplay::SharedActorEntry> order;
        const rendering::HudAmmoPanel ammo;
        std::ofstream dump;
        if (argc == 3) {
            dump.open(argv[2], std::ios::binary);
            require(dump.good(), "Cannot create survivor pixel dump");
            dump.write("LZSVPIX1", 8);
        }
        uint64_t pixels = 0, differences = 0, hudChecks = 0;
        for (size_t index = 0; index < fixture.profiles.size(); ++index) {
            const auto& profile = fixture.profiles[index];
            rendering::Canvas canvas;
            rendering::PresentationState presentation;
            presentation.setPalette(assets.palette());
            presentation.initializeBackdropBufferForPitch(160);
            presentation.restoreBackdrop(fixture.backdrop);
            rendering::TextRenderer text(canvas, presentation.palette(), assets.fontSprites());
            rendering::GameRenderer renderer(canvas, text, assets, presentation);
            auto layout = rendering::ViewportLayout::initialize(2, 320);
            int remaining = 2, selectedWidth = 320;
            gameplay::Player first, second;
            gameplay::State2VisualCursor firstCursor, secondCursor;
            ui::UiController controller;
            controller.setMenu(false);
            ui::RecordStore records;
            ui::UiActions actions;
            actions.canAdjustViewWidth = [&] { return remaining == 1; };
            actions.adjustViewWidth = [&](int delta) {
                if (!layout.adjustWidth(remaining, delta)) return;
                selectedWidth = layout.pitch;
                renderer.resizePlayfield(layout.pitch);
            };
            bool running = true;
            for (size_t phase = 0; phase < profile.stages.size(); ++phase) {
                const auto& stage = profile.stages[phase];
                if (phase == 0) continue;
                first.x = static_cast<float>(diagnostics::survivorVisualWord(stage, 0, 0));
                first.y = static_cast<float>(diagnostics::survivorVisualWord(stage, 0, 2));
                second.x = static_cast<float>(diagnostics::survivorVisualWord(stage, 1, 0));
                second.y = static_cast<float>(diagnostics::survivorVisualWord(stage, 1, 2));
                first.spriteIndex = diagnostics::survivorSpriteIndex(fixture, stage, 0);
                second.spriteIndex = diagnostics::survivorSpriteIndex(fixture, stage, 1);
                firstCursor.active = stage.states[0] == 2;
                secondCursor.active = stage.states[1] == 2;
                const auto before = canvas.pixels();
                if (phase == 1 || phase == 7) {
                    layout = rendering::ViewportLayout::initialize(remaining, selectedWidth);
                    renderer.initializePlayfield(remaining, selectedWidth);
                } else if (phase == 2 && profile.reserve == 0) {
                    --remaining;
                    renderer.clearEliminatedViewport(profile.lost - 1);
                } else if (phase == 4) {
                    controller.onKey(ui::Key::E, running, 0, 2, records, actions);
                } else if (phase == 5) {
                    for (int step = 0; step < (profile.target - 160) / 8; ++step)
                        controller.onKey(ui::Key::R, running, 0, 2, records, actions);
                } else if (phase == 8) {
                    presentation.initializeBackdropBufferForPitch(layout.pitch);
                    require(presentation.backdropBuffer() == stage.backdrop, "Original survivor backdrop regeneration differs");
                }
                if (phase == 1 || phase == 3 || phase == 6 || phase == 9) {
                    rendering::WorldRenderView world{level, 0, 2,
                        {{{first, stage.states[0] != 1, stage.reserves[0] == 255 ? -1 : stage.reserves[0], firstCursor, effect, stage.states[0]},
                          {second, stage.states[1] != 1, stage.reserves[1] == 255 ? -1 : stage.reserves[1], secondCursor, effect, stage.states[1]}}},
                        bombs, monsters, bonuses, flashes, markers, transients, order, selectedWidth, true, 0, false, false, &layout};
                    rendering::HudView hud{2, {{{{}, 0, 2, ammo}, {{}, 0, 2, ammo}}},
                        level.objectiveTile, level.requiredBonus, level.requiredDestruction, 0, 0, false, false};
                    renderer.drawGame(world, hud);
                }
                require(remaining == stage.remaining && layout.pitch == stage.geometry[1] &&
                        presentation.backdropPitch() == stage.geometry[2] && selectedWidth == stage.geometry[4] * 8 &&
                        layout.left[0] == stage.geometry[5] - 1284 && layout.left[1] == stage.geometry[6] - 1284,
                        "Original survivor layout/latch state differs");
                for (size_t at = 0; at < 51200; ++at) {
                    ++pixels;
                    differences += canvas.pixels()[at] != presentation.backdropColor(stage.pixels[at]);
                }
                if (phase == 2 || phase == 4 || phase == 5) {
                    for (size_t at = 51200; at < 64000; ++at) {
                        ++hudChecks;
                        require(canvas.pixels()[at] == before[at], "Survivor clear/resize overwrote the HUD");
                    }
                }
                if (dump.is_open() && ((index == 0 && (phase == 2 || phase == 6)) || (index == 4 && phase == 6))) {
                    dump.put(static_cast<char>(index)); dump.put(static_cast<char>(phase));
                    for (size_t at = 0; at < 51200; ++at) rgb(dump, presentation.backdropColor(stage.pixels[at]));
                    for (size_t at = 0; at < 51200; ++at) rgb(dump, canvas.pixels()[at]);
                }
            }
        }
        if (dump.is_open()) { dump.flush(); require(dump.good(), "Survivor pixel dump failed"); }
        std::cout << "survivor_viewport=" << (differences ? "failed" : "ok") << " profiles=8 stages=72 pixels=" << pixels
                  << " differences=" << differences << " retained_hud_checks=" << hudChecks
                  << " native_app_claim=0 whole_game_claim=0\n";
        return differences ? 1 : 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
