#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <stdexcept>

namespace lezac::core {

struct HudEnergyBar {
    uint8_t cached = 255;
    uint8_t fill = 0;
    bool painted = false;

    void observe(uint16_t value) {
        // 7FAF compares the whole scratch word to the cached byte. 568A
        // skips painting values above 100, even after the cache changed.
        if (cached == value) return;
        cached = static_cast<uint8_t>(value);
        if (value > 100) return;
        fill = static_cast<uint8_t>(value);
        painted = true;
    }
};

struct HudScoreReel {
    uint32_t value = 0;
    std::array<uint16_t, 9> current{};
    std::array<uint16_t, 9> target{};
    uint8_t phase = 2;

    void setValue(uint32_t next) {
        if (value != next) {
            value = next;
            phase = 0;
        }
    }

    void prepareTargets() {
        uint32_t remaining = value;
        std::size_t digit = 0;
        do {
            target[digit++] = static_cast<uint16_t>((remaining % 10) * 64);
            remaining /= 10;
        } while (remaining != 0 && digit < 8);
        phase = 1;
    }

    uint32_t stepsUntilSettled() const {
        HudScoreReel next = *this;
        for (uint32_t steps = 0; steps <= 81; ++steps) {
            if (next.phase >= 2) return steps;
            next.advance();
        }
        throw std::runtime_error("HUD score reel cannot settle within its native cycle");
    }

    void advance() {
        if (phase >= 2) return;
        if (phase == 0) prepareTargets();
        bool changed = false;
        for (std::size_t digit = 0; digit < current.size(); ++digit) {
            if (current[digit] == target[digit]) continue;
            changed = true;
            current[digit] = static_cast<uint16_t>((current[digit] + (digit % 2 == 0 ? 16 : 8)) % 640);
        }
        if (!changed) phase = 2;
    }
};

struct HudPaletteQueue {
    struct Entry {
        uint8_t index = 0;
        std::array<uint8_t, 3> current{};
        std::array<uint8_t, 3> target{};
    };
    std::array<Entry, 2> entries{};
    uint8_t count = 0;

    bool request(uint8_t index, std::array<uint8_t, 3> current, std::array<uint8_t, 3> target) {
        std::size_t slot = count;
        for (std::size_t i = 0; i < count; ++i) {
            if (entries[i].index == index) slot = i;
        }
        if (slot >= entries.size()) return false;
        if (slot == count) ++count;
        entries[slot] = {index, current, target};
        return true;
    }

    template <typename WriteColor>
    void advance(WriteColor writeColor) {
        const uint8_t limit = count;
        for (uint8_t i = 0; i < limit; ++i) {
            auto& entry = entries[i];
            bool changed = false;
            for (std::size_t c = 0; c < 3; ++c) {
                if (entry.current[c] == entry.target[c]) continue;
                changed = true;
                entry.current[c] = static_cast<uint8_t>(entry.current[c] + (entry.current[c] < entry.target[c] ? 2 : -2));
            }
            if (!changed && i + 1 == count) --count;
            writeColor(entry.index, entry.current);
        }
    }
};

}
