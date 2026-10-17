#pragma once

#include <algorithm>
#include <array>

namespace lezac::rendering {

// DS:C1EC and DS:79F0/79F2 survive elimination until an explicit frame setup.
struct ViewportLayout {
    int pitch = 320;
    std::array<int, 2> left{};

    static ViewportLayout initialize(int remainingPlayers, int selectedWidth) {
        if (remainingPlayers == 2) return {160, {{0, 160}}};
        const int width = std::clamp(selectedWidth, 168, 320);
        const int origin = (320 - width) / 2;
        return {width, {{origin, origin}}};
    }

    bool adjustWidth(int remainingPlayers, int delta) {
        if (remainingPlayers != 1 || (delta != -8 && delta != 8) ||
            (delta < 0 && pitch <= 168) || (delta > 0 && pitch >= 320)) return false;
        pitch += delta;
        left.fill((320 - pitch) / 2);
        return true;
    }
};

}
