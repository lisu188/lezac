#pragma once

#include <algorithm>
#include <cstdint>
#include <functional>
#include <optional>

namespace lezac::core {

struct DosClockSample {
    uint8_t minute = 0;
    uint8_t second = 0;
    uint8_t hundredth = 0;
};

struct StartupTimingWords {
    uint16_t characterDelay = 0; // DS:78ce
    uint16_t auxiliaryDelay = 0; // DS:78d0
    uint16_t minimumWord = 0; // DS:78ca
    bool operator==(const StartupTimingWords&) const = default;
};

constexpr uint16_t startupElapsedWord(DosClockSample first, DosClockSample second) {
    const int32_t elapsed = (int32_t{second.minute} - first.minute) * 6000 +
                            (int32_t{second.second} - first.second) * 100 +
                            int32_t{second.hundredth} - first.hundredth;
    return static_cast<uint16_t>(elapsed);
}

constexpr std::optional<StartupTimingWords> startupTimingFromElapsed(uint16_t elapsed) {
    if (elapsed == 0 || elapsed >= 300) return std::nullopt;
    // Original Real48 division and Round, restricted to the accepted domain.
    const auto rounded = [elapsed](uint32_t numerator) {
        return static_cast<uint16_t>((2u * numerator + elapsed) / (2u * elapsed));
    };
    return StartupTimingWords{rounded(8000), rounded(1600), std::max(uint16_t{2}, rounded(200))};
}

inline StartupTimingWords calibrateStartupTiming(
    const std::function<DosClockSample()>& readDosClock,
    const std::function<void(uint16_t)>& crtDelay) {
    crtDelay(500);
    for (;;) {
        const auto first = readDosClock();
        crtDelay(1000);
        const auto second = readDosClock();
        if (const auto words = startupTimingFromElapsed(startupElapsedWord(first, second)))
            return *words;
    }
}

}
