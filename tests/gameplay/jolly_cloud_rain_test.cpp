#include "diagnostics/jolly_cloud_probe.hpp"
#include "gameplay/jolly_cloud_rain.hpp"
#include <iostream>

int main() {
    try {
        lezac::diagnostics::runJollyCloudProbe(std::cin, std::cout, [](auto& state, bool initial) {
            if (initial) return;
            lezac::core::TurboRandom random(state.seed);
            const auto cell = lezac::gameplay::advanceJollyCloudRain(state.remaining, state.level, state.nextWord, random);
            state.seed = random.seed();
            if (cell) lezac::gameplay::seedFallingFragment(state.level, state.records, *cell, 0, 0);
        });
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
