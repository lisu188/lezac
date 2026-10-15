#include "ui/ui_controller.hpp"

#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
}

int main() {
    using namespace lezac::ui;
    try {
        int cases = 0;
        for (int players : {1, 2}) for (bool paused : {false, true}) {
            for (bool qualifies : {false, true}) {
                UiController ui;
                RecordStore records;
                std::vector<std::string> events;
                uint32_t score = qualifies ? 100 : 0, score2 = qualifies ? 200 : 0;
                UiActions actions;
                actions.clearScores = [&] { score = score2 = 0; events.push_back("clear"); };
                actions.prepareNewGame = [&](int count) { events.push_back("prepare" + std::to_string(count)); };
                actions.beginLevel = [&](int index) { events.push_back("level" + std::to_string(index)); };
                actions.resetAfterEndRun = [&] {
                    require(ui.snapshot().menu && !ui.snapshot().paused, "abort callback saw gameplay or pause");
                    events.push_back("end");
                };
                actions.recordPromptSound = [&] { events.push_back("prompt"); };
                actions.abortRun = [&] {
                    events.push_back("abort");
                    ui.beginEndRun(EndReason::GameOver, 4, players, score, score2, records, actions);
                };
                ui.setMenu(false);
                ui.setPaused(paused);
                bool running = true;
                ui.onKey(Key::Escape, running, 4, players, records, actions, 100);
                require(running && ui.snapshot().menu && !ui.snapshot().paused &&
                        ui.snapshot().lastEndReason == EndReason::GameOver,
                        "gameplay Escape did not end the run");
                require(events == (qualifies ? std::vector<std::string>{"abort", "end", "prompt"} :
                                               std::vector<std::string>{"abort", "end"}),
                        "abort callbacks ran out of order or cleared scores");
                if (qualifies) {
                    require(ui.snapshot().page == MenuPage::NameEntry && records.pending().score == 100 &&
                            records.pending().level == 5 && records.pending().player == 1,
                            "abort lost current score, level or first-player record");
                    const auto beforeNameEscape = events;
                    ui.onKey(Key::Escape, running, 4, players, records, actions, 101);
                    require(ui.snapshot().page == MenuPage::NameEntry && records.pending().score == 100 &&
                            records.pending().player == 1 && events == beforeNameEscape,
                            "name entry Escape changed first-player pending state");
                    // Explicit fixture teardown is not an original-game key action.
                    ui.cancelPendingRecord(records, actions);
                    if (players == 2) {
                        require(records.pending().score == 200 && records.pending().player == 2 &&
                                records.pending().level == 5, "abort lost second-player record");
                        const auto beforeSecondEscape = events;
                        ui.onKey(Key::Escape, running, 4, players, records, actions, 102);
                        require(ui.snapshot().page == MenuPage::NameEntry && records.pending().score == 200 &&
                                records.pending().player == 2 && events == beforeSecondEscape,
                                "name entry Escape changed second-player pending state");
                        ui.cancelPendingRecord(records, actions);
                    }
                    require(ui.snapshot().page == MenuPage::Records && score == 0 && score2 == 0,
                            "record fixture teardown did not finish existing end flow");
                    ui.onKey(Key::Escape, running, 4, players, records, actions, 103);
                } else {
                    require(ui.snapshot().page == MenuPage::GameOver, "zero-score abort skipped Game Over");
                    const auto before = events;
                    ui.onKey(Key::One, running, 4, players, records, actions, 101);
                    require(events == before && ui.snapshot().page == MenuPage::GameOver,
                            "new-game key bypassed Game Over acknowledgement");
                    ui.onKey(Key::Return, running, 4, players, records, actions, 102);
                }
                require(running && ui.snapshot().page == MenuPage::Main, "abort flow did not return to menu");
                ui.onKey(Key::Two, running, 4, players, records, actions, 104);
                require(!ui.snapshot().menu && events[events.size() - 3] == "prepare2" &&
                        events[events.size() - 2] == "clear" && events.back() == "level0",
                        "new game after abort did not use the existing startup sequence");
                ++cases;
            }
        }
        std::cout << "abort_run=ok cases=" << cases << " pause_cleared=1 game_over=1 records=1"
                     " player_order=1,2 current_level=1 acknowledgement=1 restart=1"
                     " name_escape_ignored=1 fixture_teardown=1 original_record_claim=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
