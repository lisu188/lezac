#include "ui/ui_controller.hpp"

#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
}

int main() {
    using namespace lezac::ui;
    try {
        std::vector<Key> acknowledgements{Key::Unknown, Key::Backspace, Key::Return, Key::Escape,
            Key::Space, Key::One, Key::Two, Key::KeypadEnter, Key::F5, Key::PageUp, Key::PageDown,
            Key::RightControl, Key::Keypad0, Key::Insert};
        for (int key = static_cast<int>(Key::A); key <= static_cast<int>(Key::Z); ++key)
            acknowledgements.push_back(static_cast<Key>(key));
        require(acknowledgements.size() == 40, "acknowledgement key count changed");
        size_t cases = 0;
        for (bool italian : {false, true}) {
            for (uint32_t now : std::array<uint32_t, 4>{{0, 100001, UINT32_MAX - 1, 1}}) {
                for (int prior = 0; prior < 3; ++prior) {
                    for (Key acknowledgement : acknowledgements) {
                        for (int players : {1, 2}) {
                            UiController controller;
                            UiState state;
                            state.page = MenuPage::Records;
                            state.italian = italian;
                            state.mainMenu = {prior != 0, now - 11, prior == 2 ? 0u : kMainMenuFadeDurationMs,
                                              prior == 2};
                            controller.restoreSnapshot(state);
                            RecordStore records;
                            bool running = true;
                            std::vector<int> calls;
                            UiActions actions;
                            actions.prepareNewGame = [&](int value) { calls.push_back(value); };
                            actions.clearScores = [&] { calls.push_back(3); };
                            actions.beginLevel = [&](int level) {
                                require(level == 0, "immediate menu choice loaded another level");
                                calls.push_back(4);
                            };
                            actions.recordsPageSound = [] { throw std::runtime_error("acknowledgement reopened records"); };
                            actions.prepareRecordsPage = [] { throw std::runtime_error("acknowledgement regenerated records"); };
                            controller.onKey(acknowledgement, running, 3, 2, records, actions, now);
                            const auto progress = controller.mainMenuProgress(now);
                            require(running && calls.empty() && controller.snapshot().menu &&
                                    controller.snapshot().page == MenuPage::Main &&
                                    controller.snapshot().italian == italian,
                                    "records acknowledgement dispatched a menu command");
                            controller.onKey(players == 1 ? Key::One : Key::Two, running, 3, 2,
                                             records, actions, now);
                            const bool settled = progress.waitingForKey && progress.fade == 63 &&
                                                 progress.steps == mainMenuStepCount(italian);
                            const bool started = running && !controller.snapshot().menu &&
                                                 calls == std::vector<int>{players, 3, 4};
                            if (!settled || !started) {
                                std::cerr << "records_return_probe acknowledgement_settled=" << settled
                                          << " immediate_game_started=" << started << '\n';
                                throw std::runtime_error("records acknowledgement restarted title or consumed next choice");
                            }
                            ++cases;
                        }
                    }
                }
            }
            UiController controller;
            UiState state;
            state.page = MenuPage::Records;
            state.italian = italian;
            controller.restoreSnapshot(state);
            RecordStore records;
            UiActions actions;
            bool running = true;
            controller.onKey(Key::Return, running, 0, 1, records, actions, 100);
            controller.onKey(Key::L, running, 0, 1, records, actions, 100);
            require(running && controller.snapshot().menu && controller.snapshot().page == MenuPage::Main &&
                    controller.snapshot().italian != italian && !controller.mainMenuProgress(100).waitingForKey,
                    "language change lost its existing title restart");
        }
        for (const MenuPage endPage : {MenuPage::GameOver, MenuPage::CompletedGame}) {
            for (const Key acknowledgement : {Key::Return, Key::Escape}) {
                UiController controller;
                UiState state;
                state.page = endPage;
                state.mainMenu = {true, 100, kMainMenuFadeDurationMs, false};
                controller.restoreSnapshot(state);
                RecordStore records;
                UiActions actions;
                actions.clearScores = [] {};
                bool running = true;
                controller.onKey(acknowledgement, running, 0, 1, records, actions, 100);
                require(running && controller.snapshot().page == MenuPage::Main &&
                        controller.mainMenuProgress(100).waitingForKey,
                        "end-screen acknowledgement restarted title animation");
                controller.onKey(Key::Escape, running, 0, 1, records, actions, 100);
                require(!running, "Escape after Game Over acknowledgement did not exit");
            }
        }
        require(cases == 1920, "records return matrix count changed");
        std::cout << "records_return=ok cases=1920 languages=2 acknowledgement_keys=40 clocks=4"
                     " prior_menu_states=3 immediate_player_choices=2 language_restart=2 whole_game_parity=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "records_return failed: " << error.what() << '\n';
        return 1;
    }
}
