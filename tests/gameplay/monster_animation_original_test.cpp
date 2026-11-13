#include "diagnostics/monster_animation_fixture.hpp"

#include <iostream>

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("expected original animation fixture");
        lezac::diagnostics::replayMonsterAnimationFixture(argv[1],
            [](const lezac::gameplay::ActiveMonster&) {},
            [](lezac::gameplay::ActiveMonster& monster) {
                return lezac::gameplay::advanceMonsterAnimation(monster);
            });
        std::cout << "monster_animation_original=ok cases=53 updates=636 compiled_helper=1 production_app=0 seeded=1 natural_route=0 whole_game_claim=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "monster_animation_original failed: " << error.what() << '\n';
        return 1;
    }
}
