#include "rendering/presentation_state.hpp"
#include <iostream>
#include <stdexcept>
#include <vector>

int main() {
    using lezac::rendering::PresentationState;
    unsigned objectives = 0, scores = 0;
    for (unsigned dirty = 0; dirty < 4; ++dirty) {
        PresentationState presentation;
        auto state = presentation.snapshot();
        state.hudPreviousCollected = (dirty & 1) != 0 ? 1 : 0;
        state.hudPreviousDestruction = (dirty & 2) != 0 ? 1 : 0;
        presentation.restore(state);
        std::vector<uint16_t> actual, expected;
        if (dirty != 0) expected.push_back(0xd028);
        if ((dirty & 1) != 0) expected.insert(expected.end(), {0xd01f, 0xd016});
        if ((dirty & 2) != 0) expected.insert(expected.end(), {0xe428, 0xe41f, 0xe416});
        presentation.prepareHudObjectives(1, 0, 0, 10, 10, [&](uint16_t value) { actual.push_back(value); });
        if (actual != expected) throw std::runtime_error("objective shared-word write order differs");
        ++objectives;
    }
    for (int count : {1, 2}) for (uint8_t phase : {uint8_t{0}, uint8_t{1}, uint8_t{2}, uint8_t{255}})
        for (unsigned gate = 0; gate < 4; ++gate) for (uint16_t x : {uint16_t{0}, uint16_t{180}, uint16_t{65535}})
            for (bool moving : {false, true}) {
                PresentationState presentation;
                auto state = presentation.snapshot();
                for (auto& reel : state.hudScores) {
                    reel.phase = phase;
                    if (moving) reel.target[0] = 64;
                }
                presentation.restore(state);
                std::vector<uint16_t> actual, expected;
                for (int player = 0; player < count; ++player) {
                    if ((gate & (1u << player)) != 0) continue;
                    expected.push_back(static_cast<uint16_t>(player * 46));
                    if (phase < 2) for (unsigned digit = 0; digit <= 9; ++digit)
                        expected.push_back(static_cast<uint16_t>(0xdc00u + x + digit * 9));
                }
                presentation.updateHudScores(count, {{0, 0}}, {{(gate & 1) != 0, (gate & 2) != 0}}, {{0, 0}},
                    [&](uint16_t value) { actual.push_back(value); }, {{x, x}});
                if (actual != expected) throw std::runtime_error("score shared-word write order differs");
                ++scores;
            }
    if (objectives != 4 || scores != 192) throw std::runtime_error("HUD scratch coverage differs");
    std::cout << "hud_scratch=ok objective_cases=4 score_cases=192 ordered_writes=1 whole_game_claim=0\n";
}
