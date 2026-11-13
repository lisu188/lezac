#include "ui/ui_controller.hpp"

#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
}

int main() {
    using namespace lezac;
    using namespace ui;
    try {
        size_t cases = 0;
        for (bool italian : {false, true}) {
            for (uint32_t now : std::array<uint32_t, 4>{{0, 100001, UINT32_MAX - 1, 1}}) {
                for (auto reason : {EndReason::GameOver, EndReason::CompletedGame}) {
                    for (int players : {1, 2}) {
                        for (int prior = 0; prior < 3; ++prior) {
                            for (Key acknowledgement : {Key::Return, Key::One}) {
                                UiController controller;
                                UiState state;
                                state.menu = false;
                                state.italian = italian;
                                state.mainMenu = {prior != 0, now - 11,
                                    prior == 2 ? 0u : kMainMenuFadeDurationMs, prior == 2};
                                controller.restoreSnapshot(state);
                                RecordStore records;
                                records.replaceRecords(std::vector<resources::Record>(7,
                                    resources::makeRecord(100, 1, "old")));
                                bool running = true;
                                std::vector<int> calls;
                                UiActions actions;
                                actions.resetAfterEndRun = [&] { calls.push_back(1); };
                                actions.clearScores = [&] { calls.push_back(2); };
                                actions.prepareNewGame = [&](int count) { calls.push_back(10 + count); };
                                actions.beginLevel = [&](int level) {
                                    require(level == 0, "new game did not start at level one");
                                    calls.push_back(3);
                                };
                                controller.beginEndRun(reason, 0, players, 0, 0, records, actions);
                                require(controller.snapshot().page == UiController::endMenuPage(reason) &&
                                        calls == std::vector<int>{1}, "end screen was skipped");
                                controller.onKey(acknowledgement, running, 0, players, records, actions, now);
                                require(running && controller.snapshot().menu &&
                                        controller.snapshot().page == MenuPage::Main &&
                                        controller.snapshot().italian == italian && !records.hasPendingRecord() &&
                                        calls == std::vector<int>{1, 2},
                                        "end acknowledgement dispatched a menu command");
                                const auto progress = controller.mainMenuProgress(now);
                                controller.onKey(players == 1 ? Key::One : Key::Two, running, 0,
                                                 players, records, actions, now);
                                const bool settled = progress.waitingForKey && progress.fade == 63 &&
                                                     progress.steps == mainMenuStepCount(italian);
                                const bool started = running && !controller.snapshot().menu &&
                                    calls == std::vector<int>{1, 2, 10 + players, 2, 3};
                                if (!settled || !started) {
                                    std::cerr << "end_run_return_probe settled=" << settled
                                              << " immediate_game_started=" << started << '\n';
                                    throw std::runtime_error("end-run return restarted title or consumed next choice");
                                }
                                ++cases;
                            }
                        }
                    }
                }
            }
        }
        for (bool italian : {false, true}) {
            for (auto reason : {EndReason::GameOver, EndReason::CompletedGame}) {
                UiController controller;
                controller.setItalian(italian);
                RecordStore records;
                records.replaceRecords(std::vector<resources::Record>(7, resources::makeRecord(100, 1, "old")));
                UiActions actions;
                actions.resetAfterEndRun = [] {};
                actions.clearScores = [] {};
                bool running = true;
                controller.beginEndRun(reason, 0, 1, 0, 0, records, actions);
                controller.onKey(Key::Return, running, 0, 1, records, actions, 100);
                controller.onKey(Key::L, running, 0, 1, records, actions, 100);
                require(running && controller.snapshot().menu && controller.snapshot().italian != italian &&
                        !controller.mainMenuProgress(100).waitingForKey,
                        "end-run return disabled the existing language-triggered title fade");
            }
        }
        require(cases == 192, "end-run return case count changed");
        std::cout << "end_run_return=ok cases=192 languages=2 clocks=4 reasons=2 configured_players=2"
                     " prior_title_states=3 acknowledgements=2 language_restart=4 whole_game_parity=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
