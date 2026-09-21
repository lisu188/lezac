#include "core/hud.hpp"

#include <array>
#include <iostream>
#include <stdexcept>
#include <vector>

int main() {
    using lezac::core::HudPaletteQueue;
    using lezac::core::HudScoreReel;
    auto check = [](bool value) { if (!value) throw std::runtime_error("HUD model mismatch"); };
    try {
        HudScoreReel score;
        check(score.value == 0 && score.phase == 2);
        score.setValue(12345678);
        score.advance();
        check(score.phase == 1);
        check(score.target == std::array<uint16_t, 9>{512,448,384,320,256,192,128,64,0});
        check(score.current == std::array<uint16_t, 9>{16,8,16,8,16,8,16,8,0});
        for (int i = 1; i < 56; ++i) score.advance();
        check(score.current == score.target && score.phase == 1);
        score.advance();
        check(score.phase == 2);
        score.setValue(0);
        score.advance();
        check(score.target[0] == 0 && score.target[1] == 448 && score.current[0] == 528);
        for (int i = 1; i < 8; ++i) score.advance();
        check(score.current[0] == 0 && score.phase == 1);
        score.advance();
        check(score.phase == 2);
        score.setValue(99999999);
        for (int i = 0; i < 100; ++i) score.advance();
        check(score.current[0] == 576 && score.current[7] == 576 && score.current[8] == 0);
        score.setValue(100000000);
        score.advance();
        check(score.current[0] == 592 && score.current[1] == 584 && score.target[8] == 0);
        for (int i = 0; i < 8; ++i) score.advance();
        check(score.phase == 2 && score.current == std::array<uint16_t, 9>{});

        HudPaletteQueue queue;
        const std::array<uint8_t, 3> white{63,63,63}, blue{1,1,41};
        check(queue.request(245, white, blue));
        check(queue.request(246, white, blue));
        check(!queue.request(224, white, blue) && queue.count == 2);
        std::vector<unsigned> writes;
        auto write = [&](uint8_t index, const auto&) { writes.push_back(index); };
        queue.advance(write);
        check(queue.entries[0].current == std::array<uint8_t, 3>{61,61,61});
        check(writes == std::vector<unsigned>{245,246});
        for (int i = 1; i < 31; ++i) queue.advance(write);
        check(queue.entries[0].current == blue && queue.entries[1].current == blue && queue.count == 2);
        queue.advance(write);
        check(queue.count == 1);
        queue.advance(write);
        check(queue.count == 0 && writes.size() == 65);
        check(queue.request(245, white, blue));
        check(queue.request(246, white, blue));
        queue.advance(write);
        check(queue.request(245, {9,9,9}, {1,1,1}) && queue.count == 2);
        check(queue.entries[0].current == std::array<uint8_t, 3>{9,9,9});
        queue = {};
        check(queue.request(245, {0,0,0}, {1,1,1}));
        for (int i = 0; i < 6; ++i) queue.advance(write);
        check(queue.count == 1 && queue.entries[0].current == std::array<uint8_t, 3>{0,0,0});
        std::cout << "hud_models=ok reels=1 fades=1 capacity=1 wrap=1\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
