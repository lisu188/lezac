#include "rendering/game_renderer.hpp"
#include "app/input_mapper.hpp"
#include "resources/asset_catalog.hpp"
#include "ui/ui_controller.hpp"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>

namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

void checkMainMenuChoices() {
    using namespace lezac::ui;
    const auto ignored = {Key::Unknown, Key::Backspace, Key::Return, Key::Space,
        Key::A, Key::B, Key::C, Key::D, Key::E, Key::F, Key::G, Key::H, Key::J,
        Key::K, Key::M, Key::N, Key::O, Key::P, Key::Q, Key::S, Key::T, Key::U,
        Key::V, Key::W, Key::X, Key::Y, Key::KeypadEnter, Key::F5, Key::PageUp,
        Key::PageDown, Key::RightControl, Key::Keypad0, Key::Insert};
    for (bool italian : {true, false}) {
        for (int readiness = 0; readiness < 3; ++readiness) {
            for (bool background : {true, false}) {
                UiController ui;
                RecordStore records;
                bool running = true;
                int callbacks = 0;
                int players = 0;
                UiActions actions;
                actions.prepareNewGame = [&](int value) { players = value; ++callbacks; };
                actions.beginLevel = [&](int) { ++callbacks; };
                actions.clearScores = [&] { ++callbacks; };
                actions.recordsPageSound = [&] { ++callbacks; };
                UiState initial;
                initial.italian = italian;
                initial.showBackground = background;
                ui.restoreSnapshot(initial);
                uint32_t now = 0;
                if (readiness != 0) {
                    ui.beginMainMenu(100);
                    now = 100 + kMainMenuFadeDurationMs;
                    if (readiness == 1) {
                        now += static_cast<uint32_t>(mainMenuStepCount(italian)) * kMainMenuCharacterDelayMs;
                    } else {
                        ui.onKey(Key::Return, running, 0, 1, records, actions, now);
                        require(ui.snapshot().mainMenu.textSkipped && callbacks == 0,
                                "typing Return was not a consumed skip");
                    }
                }
                const auto before = ui.snapshot();
                require(ui.mainMenuProgress(now).waitingForKey, "choice fixture not ready");
                for (const auto key : ignored) {
                    ui.onKey(key, running, 0, 1, records, actions, now);
                    const auto after = ui.snapshot();
                    require(running && callbacks == 0 && after.menu && after.page == MenuPage::Main &&
                            after.italian == before.italian && after.paused == before.paused &&
                            after.showBackground == before.showBackground && after.lastEndReason == before.lastEndReason &&
                            after.mainMenu.active == before.mainMenu.active &&
                            after.mainMenu.startedAt == before.mainMenu.startedAt &&
                            after.mainMenu.fadeEnd == before.mainMenu.fadeEnd &&
                            after.mainMenu.textSkipped == before.mainMenu.textSkipped,
                            "unsupported ready-menu key changed state or invoked a callback");
                }
                for (const auto key : {Key::One, Key::Two}) {
                    ui.restoreSnapshot(before);
                    players = 0;
                    const int count = callbacks;
                    ui.onKey(key, running, 0, 1, records, actions, now);
                    require(!ui.snapshot().menu && players == (key == Key::Two ? 2 : 1) && callbacks == count + 3,
                            "fresh 1/2 selection failed after ignored keys");
                }
                for (const auto key : {Key::I, Key::Z, Key::R, Key::L, Key::Escape}) {
                    ui.restoreSnapshot(before);
                    running = true;
                    const int count = callbacks;
                    ui.onKey(key, running, 0, 1, records, actions, now);
                    const auto page = key == Key::I ? MenuPage::Info : key == Key::Z ? MenuPage::Instructions :
                                      key == Key::R ? MenuPage::Records : MenuPage::Main;
                    require(ui.snapshot().menu && ui.snapshot().page == page &&
                            running == (key != Key::Escape) &&
                            ui.snapshot().italian == (key == Key::L ? !italian : italian) &&
                            ui.snapshot().showBackground == background && callbacks == count + (key == Key::R ? 1 : 0),
                            "accepted ready-menu command changed behavior");
                }
            }
        }
    }
}
}

int main(int argc, char** argv) {
    using namespace lezac;
    using namespace ui;
    try {
        checkMainMenuChoices();
        for (const auto key : {SDLK_UNKNOWN, SDLK_LSHIFT, SDLK_RSHIFT, SDLK_LCTRL, SDLK_RCTRL,
                              SDLK_LALT, SDLK_RALT, SDLK_LGUI, SDLK_RGUI, SDLK_CAPSLOCK,
                              SDLK_NUMLOCKCLEAR, SDLK_SCROLLLOCK})
            require(!app::InputMapper::isBufferedMenuKey(key), "non-buffered key accepted");
        for (const auto key : {SDLK_1, SDLK_2, SDLK_l, SDLK_ESCAPE, SDLK_SPACE, SDLK_F1, SDLK_LEFT, SDLK_KP_0})
            require(app::InputMapper::isBufferedMenuKey(key), "buffered menu key rejected");
        UiController ui;
        RecordStore records;
        int games = 0;
        bool running = true;
        UiActions actions;
        actions.clearScores = [] {};
        actions.prepareNewGame = [&](int) { ++games; };
        actions.beginLevel = [](int) {};
        require(mainMenuStepCount(true) == 158 && mainMenuStepCount(false) == 155, "menu cycle count");
        ui.beginMainMenu(100);
        require(ui.mainMenuProgress(100).fade == 0 && ui.mainMenuProgress(100).steps == 0, "initial fade");
        require(ui.mainMenuProgress(100 + 63 * 22).fade == 63 && !ui.mainMenuProgress(100 + 63 * 22).waitingForKey,
                "last palette step must still wait");
        require(ui.mainMenuProgress(100 + kMainMenuFadeDurationMs).steps == 1, "first text cycle");
        const uint32_t done = 100 + kMainMenuFadeDurationMs + 158 * kMainMenuCharacterDelayMs;
        require(!ui.mainMenuProgress(done - 1).waitingForKey && ui.mainMenuProgress(done).waitingForKey,
                "final text delay boundary");
        ui.onKey(Key::One, running, 0, 1, records, actions, 100);
        require(games == 0 && ui.snapshot().menu && ui.mainMenuProgress(165).steps == 0, "fade key leaked");
        require(ui.mainMenuProgress(166).fade == 63 && ui.mainMenuProgress(187).steps == 0,
                "skipped fade must retain final delay");
        require(ui.mainMenuProgress(188).steps == 1, "queued fade skip boundary");
        ui.onKey(Key::One, running, 0, 1, records, actions, 200);
        require(games == 0 && ui.snapshot().menu && ui.mainMenuProgress(200).waitingForKey, "typing key leaked");
        ui.onKey(Key::L, running, 0, 1, records, actions, 201);
        require(!ui.snapshot().italian && ui.mainMenuProgress(201).fade == 0, "language redraw");
        ui.onKey(Key::Escape, running, 0, 1, records, actions, 300);
        ui.onKey(Key::Escape, running, 0, 1, records, actions, 322);
        require(running && ui.mainMenuProgress(322).waitingForKey, "skip Escape exited menu");
        ui.onKey(Key::One, running, 0, 1, records, actions, 323);
        require(games == 1 && !ui.snapshot().menu, "fresh selection failed");
        ui.onKey(Key::Escape, running, 0, 1, records, actions, 400);
        require(ui.snapshot().menu && ui.mainMenuProgress(400).fade == 0, "game return redraw");
        ui.beginMainMenu(UINT32_MAX - 20);
        require(ui.mainMenuProgress(1).fade == 1, "menu clock rollover");
        ui.beginMainMenu(0);
        ui.onKey(Key::Escape, running, 0, 1, records, actions, kMainMenuFadeDurationMs + 155 * kMainMenuCharacterDelayMs);
        require(!running, "settled Escape did not exit");

        if (argc == 2) {
            const std::filesystem::path output = argv[1];
            require(!std::filesystem::exists(output), "renderer output already exists");
            std::filesystem::create_directories(output);
            const auto assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
            rendering::Canvas canvas;
            rendering::TextRenderer text(canvas, assets.palette(), assets.fontSprites());
            rendering::PresentationState presentation;
            presentation.setPalette(assets.palette());
            rendering::GameRenderer renderer(canvas, text, assets, presentation);
            const std::string name;
            auto capture = [&](const std::string& label, bool italian, size_t steps, uint8_t fade = 63) {
                renderer.drawMenu({MenuPage::Main, italian, assets.initialRecords(), 1, 0, 0,
                                   name, 1, {{0, 0}}, fade, steps});
                std::ofstream out(output / (label + ".ppm"), std::ios::binary);
                out << "P6\n320 200\n255\n";
                for (const auto pixel : canvas.pixels()) {
                    const char rgb[]{static_cast<char>(pixel >> 16), static_cast<char>(pixel >> 8), static_cast<char>(pixel)};
                    out.write(rgb, 3);
                }
                require(static_cast<bool>(out), "frame output failed");
            };
            for (bool italian : {true, false}) {
                const std::string prefix = italian ? "italian" : "english";
                for (size_t step : {size_t(1), size_t(2), size_t(6), mainMenuLines(italian)[0].size() + 5}) {
                    const std::string number = step < 10 ? "0" + std::to_string(step) : std::to_string(step);
                    capture(prefix + "-line0-step" + number, italian, step);
                }
                capture(prefix + "-full", italian, mainMenuStepCount(italian));
                for (uint8_t fade : {uint8_t(0), uint8_t(31), uint8_t(63)})
                    capture(prefix + "-fade" + std::to_string(fade), italian, 0, fade);
            }
        }
        std::cout << "main_menu=ok cells=9 first_y=77 trail=5 languages=2 timing=1 consumed_keys=1 rollover=1 buffered_keys=1"
                     " ignored_choices=33 readiness_modes=3 consumed_enter=1 fresh_choices=2 accepted_choices=7\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
