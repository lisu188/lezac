#include "gameplay/actor_models.hpp"

#include <array>
#include <cstdint>
#include <iostream>

using lezac::gameplay::ActorAnimation;

int main() {
    constexpr std::array<std::array<uint8_t, 7>, 6> originalMode3{{
        {{43, 43, 46, 2, 2, 2, 255}},
        {{42, 43, 46, 0, 2, 2, 1}},
        {{42, 43, 46, 1, 2, 2, 1}},
        {{42, 43, 46, 2, 2, 2, 1}},
        {{43, 43, 46, 0, 2, 2, 255}},
        {{43, 43, 46, 1, 2, 2, 255}},
    }};
    const ActorAnimation backup{43, 43, 46, 2, 2, 2, -1};
    int matches = 0, oldMismatches = 0;
    for (const uint8_t mode : {uint8_t{0}, uint8_t{3}}) {
        ActorAnimation correct{9, 6, 9, 0, 0, mode, 1};
        ActorAnimation old = correct;
        for (size_t sample = 0; sample < originalMode3.size(); ++sample) {
            correct.advance(backup);
            old.advance(ActorAnimation{});
            const auto expected = mode == 0 ? std::array<uint8_t, 7>{{9, 6, 9, 0, 0, 0, 1}}
                                            : originalMode3[sample];
            if (correct.packed() != expected || backup.packed() != originalMode3[0]) return 1;
            ++matches;
            if (mode == 3 && old.packed() != expected) ++oldMismatches;
        }
    }
    if (matches != 12 || oldMismatches != 6) return 2;
    std::cout << "transient_backup_call_control=ok original_updates=12 correct_matches=12 "
                 "old_mode3_mismatches=6 production_app_executed=0\n";
}
