#include "ui/level_flow.hpp"
#include "core/random.hpp"

#include <algorithm>
#include <array>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

struct ResultsRun {
    lezac::ui::LevelFlow flow;
    std::array<uint32_t, 2> scores{{850, 0}};
    std::array<lezac::core::HudScoreReel, 2> reels{};
    lezac::core::TurboRandom random{3146821024u};
    std::vector<std::string> events;

    explicit ResultsRun(uint32_t start = 0) {
        reels[0].setValue(scores[0]);
        while (reels[0].phase < 2) reels[0].advance();
        flow.beginOutro(start, 34, {{true, false}}, {{{{200, 20, 5, 0}}, {{0, 0, 0, 0}}}}, scores, reels);
    }

    void update(uint32_t now) {
        flow.updateOutro(now, true, [] {},
            [&](size_t player, uint32_t award) {
                scores[player] += award;
                reels[player].setValue(scores[player]);
                reels[player].prepareTargets();
                events.push_back("score");
            },
            [&](size_t player) {
                reels[player].advance();
                events.push_back("reel");
            },
            [&](size_t) {
                random.range(0, 4);
                events.push_back("rng");
            });
    }

    uint32_t awardStart() const {
        const auto schedule = flow.levelOutroSchedule(true);
        const auto found = std::find_if(schedule.begin(), schedule.end(),
            [](const auto& segment) { return segment.player == 0; });
        require(found != schedule.end(), "no active-player award segment");
        require(found->end - found->start == 615, "native 41-step duration changed");
        return found->start;
    }
};
}

int main() {
    try {
        ResultsRun run;
        const auto start = run.awardStart();
        require(run.flow.outro().destBonus == 340 && run.flow.outro().bombBonus[0] == 4500,
                "results confused destroyed-block count with percent");
        run.update(499);
        require(!run.flow.outro().preludeApplied, "native results prelude bypassed the 500ms delay");
        run.update(500);
        require(run.flow.outro().preludeApplied, "native results prelude did not run after its delay");
        run.update(start - 1);
        require(run.scores[0] == 850 && run.events.empty(), "results awarded before the player line finished");
        run.update(start);
        require(run.scores[0] == 5690 && run.flow.outro().awarded[0] == 4840 &&
                run.events == std::vector<std::string>({"score", "reel"}) &&
                run.random.seed() == 3146821024u, "native whole award / first advance order changed");
        require(run.reels[0].target == std::array<uint16_t, 9>{{0, 576, 384, 320, 0, 0, 0, 0, 0}} &&
                run.reels[0].current == std::array<uint16_t, 9>{{0, 328, 528, 8, 0, 0, 0, 0, 0}},
                "first native result-reel step changed");
        run.update(start + 14);
        require(run.events.size() == 2, "RNG ran before its 15ms delay");
        run.update(start + 15);
        require(run.events == std::vector<std::string>({"score", "reel", "rng", "reel"}) &&
                run.random.seed() == 2958681121u, "native delayed RNG / next advance order changed");
        run.update(start + 15);
        require(run.events.size() == 4, "duplicate host update repeated a reel step");
        for (uint32_t step = 2; step <= 41; ++step) run.update(start + step * 15);
        require(run.reels[0].phase == 2 && run.reels[0].current == run.reels[0].target &&
                run.random.seed() == 2602717913u && run.scores[0] == 5690 &&
                run.events.size() == 83 && run.flow.outro().advancedSteps[0] == 41 &&
                run.flow.outro().completedDelays[0] == 41 && !run.flow.outro().awaitKey,
                "native final reel / RNG / score or trailing pause changed");
        const auto finish = run.flow.levelOutroSchedule(true).back().end;
        run.update(finish - 1);
        require(!run.flow.outro().awaitKey, "trailing 200ms pause ended early");
        run.update(finish);
        require(run.flow.outro().awaitKey, "results did not block for acknowledgment");
        run.flow.finishOutro([&](size_t, uint32_t) { throw std::runtime_error("results awarded twice"); });

        ResultsRun batched;
        batched.update(batched.flow.levelOutroSchedule(true).back().end);
        require(batched.scores == run.scores && batched.events == run.events &&
                batched.random.seed() == run.random.seed() && batched.reels[0].current == run.reels[0].current,
                "host batching changed native reel/RNG ordering");
        ResultsRun wrapped(UINT32_MAX - 100);
        wrapped.update(UINT32_MAX - 100 + wrapped.flow.levelOutroSchedule(true).back().end);
        require(wrapped.events == run.events && wrapped.random.seed() == run.random.seed(),
                "results clock rollover changed the sequence");

        lezac::ui::LevelFlow zero;
        zero.beginOutro(0, 0, {{true, false}}, {}, {{0, 0}}, {});
        require(zero.outro().reelSteps[0] == 1, "zero bonus omitted the native settled-check iteration");
        unsigned awards = 0, advances = 0, draws = 0;
        zero.updateOutro(zero.levelOutroSchedule(true).back().end, true, [] {},
            [&](size_t player, uint32_t amount) { require(player == 0 && amount == 0, "zero award changed"); ++awards; },
            [&](size_t player) { require(player == 0, "inactive player advanced"); ++advances; },
            [&](size_t) { ++draws; });
        require(awards == 1 && advances == 1 && draws == 1, "zero or inactive-player sequence changed");
        zero.finishOutro([&](size_t, uint32_t) { throw std::runtime_error("zero awarded twice"); });

        lezac::ui::LevelFlow wordWrap;
        wordWrap.beginOutro(0, 65535, {{true, false}}, {{{{0, 99, 99, 99}}, {{0, 0, 0, 0}}}}, {{0, 0}}, {});
        require(wordWrap.outro().destBonus == 65526 && wordWrap.outro().bombBonus[0] == -4744,
                "native low-word destruction or signed bomb sum changed");
        std::cout << "level_results=ok count_bonus=1 whole_award=1 reel_steps=41 rng_draws=41"
                     " delayed_rng=1 batching=1 rollover=1 zero_bonus=1 word_wrap=1 original_runtime_claim=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
