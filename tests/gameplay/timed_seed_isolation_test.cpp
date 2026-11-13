#include "gameplay/actor_slots.hpp"
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    try {
        if (argc < 2 || argc > 3) throw std::runtime_error("expected timed fixture and optional negative control");
        const bool reset = argc == 2;
        if (!reset && std::string(argv[2]) != "--without-reset") throw std::runtime_error("invalid negative control");
        std::ifstream input(argv[1], std::ios::binary);
        const std::vector<uint8_t> bytes{std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
        if (bytes.size() != 94784) throw std::runtime_error("timed fixture size changed");
        const auto word = [&](size_t at) { return uint16_t(bytes[at] | (uint16_t(bytes[at + 1]) << 8)); };
        lezac::gameplay::ActorSlots slots;
        size_t corpses = 0;
        for (size_t index = 0; index != 1184; ++index) {
            const size_t at = 64 + index * 80;
            if (word(at) != index || (bytes[at + 2] != 12 && bytes[at + 2] != 13))
                throw std::runtime_error("timed fixture order/kind changed");
            if (reset) slots.resetForLevel({16, 16, 0, 0});
            if (bytes[at + 2] != 12) continue;
            lezac::gameplay::ActiveMonster corpse;
            const uint32_t tick = word(at + 16);
            corpse.kind = 12; corpse.behavior = 2; corpse.actorOrder = 1;
            corpse.stateTimer = 2 * bytes[at + 5] - static_cast<int>(tick & 1u);
            if (!slots.find(1)) {
                const uint8_t timer = lezac::gameplay::corpseTimerFromRemainingUpdates(corpse.stateTimer, tick);
                if (!slots.append(1, {12, timer, 2, 48, 0, 0, 0, 0}, {16, 16, 0, 0}))
                    throw std::runtime_error("seed allocation failed");
            }
            uint8_t timer = slots.actor(1)[2];
            if (timer != bytes[at + 5])
                throw std::runtime_error("physical timer inherited previous case at " + std::to_string(index));
            const bool expired = lezac::gameplay::advanceCorpseMotion(corpse, timer, tick,
                [](int&, int&, int16_t&, int16_t&, uint8_t&, uint8_t&) {});
            if (expired || timer != bytes[at + 34 + 2])
                throw std::runtime_error("seeded raw countdown differs from original at " + std::to_string(index));
            slots.writeCorpse(1, corpse, timer, false, {});
            ++corpses;
        }
        if (corpses != 592) throw std::runtime_error("corpse case coverage changed");
        std::cout << "timed_seed_isolation=ok cases=1184 corpse_cases=" << corpses
                  << " raw_timer_boundaries=1 production_storage=1 full_app=0\n";
    } catch (const std::exception& error) {
        std::cerr << "timed_seed_isolation=failed " << error.what() << '\n';
        return 1;
    }
}
