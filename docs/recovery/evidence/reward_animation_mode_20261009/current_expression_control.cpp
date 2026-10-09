#include "gameplay/actor_models.hpp"
#include <iostream>
using namespace lezac::gameplay;
int main() {
    int cases = 0, mismatches = 0;
    for (int mode = 0; mode < 4; ++mode) for (int counter : {0, 255}) for (int step : {-1, 1}) {
        ActiveMonster monster;
        monster.animCursor = 254; monster.animStart = 3; monster.animEnd = 9;
        monster.animTick = counter; monster.animDelay = 254;
        monster.animMode = mode; monster.animStep = step;
        BonusDrop reward;
reward.animation = {static_cast<uint8_t>(monster.animCursor + 1),
                static_cast<uint8_t>(monster.animStart + 1), static_cast<uint8_t>(monster.animEnd + 1),
                static_cast<uint8_t>(monster.animTick), static_cast<uint8_t>(monster.animDelay),
                0, static_cast<int8_t>(monster.animStep)};
        const std::array<uint8_t, 7> expected{{255, 4, 10, static_cast<uint8_t>(counter), 254, 0, static_cast<uint8_t>(step)}};
        ++cases;
        if (reward.animation.packed() != expected) ++mismatches;
    }
    std::cout << "reward_animation_expression cases=" << cases << " mismatches=" << mismatches << " actual_app=0\n";
    return mismatches ? 1 : 0;
}
