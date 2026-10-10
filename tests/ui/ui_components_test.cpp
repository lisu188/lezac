#include "ui/ui_controller.hpp"
#include "ui/level_flow.hpp"

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
        UiController ui;
        RecordStore records;
        std::vector<std::string> events;
        UiActions actions;
        actions.clearScores = [&] { events.push_back("clear"); };
        actions.prepareNewGame = [&](int players) { events.push_back("prepare" + std::to_string(players)); };
        actions.beginLevel = [&](int index) {
            require(ui.snapshot().menu, "new-game callback must precede leaving menu");
            events.push_back("level" + std::to_string(index));
        };
        actions.resetAfterEndRun = [&] {
            require(ui.snapshot().menu && ui.snapshot().lastEndReason == EndReason::GameOver,
                    "end-run callback must observe the new menu state");
            events.push_back("reset");
        };
        actions.recordPromptSound = [&] { events.push_back("prompt"); };
        actions.recordCommitSound = [&] { events.push_back("commit"); };
        actions.recordsPageSound = [&] { events.push_back("records"); };
        actions.firePlayer = [&](int player) { events.push_back("fire" + std::to_string(player)); };
        actions.adjustViewWidth = [&](int delta) { events.push_back("width" + std::to_string(delta)); };
        bool running = true;
        ui.onKey(Key::Two, running, 4, 1, records, actions);
        require(events == std::vector<std::string>({"prepare2", "clear", "level0"}),
                "new-game callback order changed");
        require(!ui.snapshot().menu, "new game must leave menu");
        ui.onKey(Key::P, running, 0, 2, records, actions);
        ui.onKey(Key::Space, running, 0, 2, records, actions);
        require(events.size() == 3, "pause leaked a fire key");
        ui.onKey(Key::P, running, 0, 2, records, actions);
        ui.onKey(Key::Insert, running, 0, 2, records, actions);
        require(events.back() == "fire2", "player-two fire mapping changed");
        ui.beginEndRun(EndReason::GameOver, 2, 2, 100, 200, records, actions);
        require(ui.snapshot().page == MenuPage::GameOver && !records.hasPendingRecord() && events.back() == "reset",
                "name entry bypassed the end-screen acknowledgement");
        ui.onKey(Key::One, running, 2, 2, records, actions);
        require(events[events.size() - 2] == "reset" && events.back() == "prompt",
                "record prompt preceded reset");
        require(records.pending().player == 1 && records.pending().level == 3,
                "pending record order or level changed");
        require(ui.shouldAcceptRepeatedNameEntryKey(Key::A) &&
                ui.shouldAcceptRepeatedNameEntryKey(Key::Backspace) &&
                !ui.shouldAcceptRepeatedNameEntryKey(Key::Return) &&
                !ui.shouldAcceptRepeatedNameEntryKey(Key::Escape), "repeat policy changed");
        for (int i = 0; i < 10; ++i) ui.handleNameEntryKey(Key::A, records, actions);
        require(records.pending().name == "aaaaaaaa", "name entry cap changed");
        ui.handleNameEntryKey(Key::Backspace, records, actions);
        ui.handleNameEntryKey(Key::Space, records, actions);
        require(records.pending().name == "aaaaaaa ", "name editing changed");
        ui.cancelPendingRecord(records, actions);
        require(records.pending().player == 2 && records.pending().name.empty(),
                "cancellation did not advance to the next player");

        LevelFlow flow;
        std::vector<std::pair<int, int>> randomCalls;
        const auto pattern = LevelFlow::makeLevelIntroPattern([&](int low, int high) {
            randomCalls.emplace_back(low, high); return low;
        });
        require(randomCalls == std::vector<std::pair<int, int>>({
            {1, 80}, {1, 80}, {0, 19}, {0, 19}, {0, 19}, {0, 29}, {0, 29}, {0, 29}}),
            "intro shared RNG draw order changed");
        flow.beginIntro(0, pattern, UINT32_MAX - 40);
        require(flow.visibleLevelIntroCharacters(40) == 2, "intro clock rollover changed");
        const uint32_t introDuration = static_cast<uint32_t>(levelIntroCaption(0).size()) * kLevelIntroCharacterDelayMs;
        require(!flow.introWaitingForKey(40) &&
                !flow.introWaitingForKey(UINT32_MAX - 40 + introDuration - 1) &&
                flow.introWaitingForKey(UINT32_MAX - 40 + introDuration), "intro final delay boundary changed");
        flow.skipIntroTyping();
        require(flow.intro().active && flow.introWaitingForKey(40) &&
                flow.visibleLevelIntroCharacters(40) == levelIntroCaption(0).size(), "intro skip ended blocking wait");
        flow.beginIntro(1, pattern, 100);
        require(!flow.intro().typingSkipped && !flow.introWaitingForKey(100), "intro skip leaked to next level");
        flow.beginOutro(0, 10, {{true, true}}, {{{{0, 2, 0, 0}}, {{0, 3, 0, 0}}}}, {{0, 0}}, {});
        const auto schedule = flow.levelOutroSchedule(true);
        events.clear();
        std::array<uint32_t, 2> scores{};
        auto award = [&](size_t player, uint32_t amount) {
            scores[player] += amount; events.push_back("score" + std::to_string(player));
        };
        flow.updateOutro(schedule.back().end, true, [] {}, award,
                         [&](size_t player) { events.push_back("reel" + std::to_string(player)); },
                         [&](size_t) { events.push_back("rng"); });
        std::vector<std::string> expected;
        for (size_t player = 0; player < 2; ++player) {
            expected.push_back("score" + std::to_string(player));
            for (uint32_t step = 0; step < flow.outro().reelSteps[player]; ++step) {
                expected.push_back("reel" + std::to_string(player));
                expected.push_back("rng");
            }
        }
        require(scores == std::array<uint32_t, 2>{{300, 400}} && events == expected,
                "outro award/RNG callback sequence changed");
        flow.finishOutro(award);
        require(events == expected && !flow.outro().active, "outro awarded twice");
        std::cout << "ui_components=ok input=1 records=1 timing=1 callback_order=1 rng_order=1\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
