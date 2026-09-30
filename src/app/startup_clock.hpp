#pragma once

#include "core/random.hpp"
#include <chrono>
#include <ctime>
#include <stdexcept>

namespace lezac::app {

inline uint32_t sampleStartupRandomSeed() {
    const auto now = std::chrono::system_clock::now();
    const auto seconds = std::chrono::floor<std::chrono::seconds>(now);
    const auto epochSeconds = std::chrono::system_clock::to_time_t(seconds);
    const auto hundredth = std::chrono::duration_cast<std::chrono::milliseconds>(now - seconds).count() / 10;
    std::tm local{};
#ifdef _WIN32
    if (localtime_s(&local, &epochSeconds) != 0)
#else
    if (localtime_r(&epochSeconds, &local) == nullptr)
#endif
        throw std::runtime_error("cannot sample the startup local clock");
    return core::dosTimeRandomSeed(static_cast<uint8_t>(local.tm_hour),
                                   static_cast<uint8_t>(local.tm_min),
                                   static_cast<uint8_t>(local.tm_sec),
                                   static_cast<uint8_t>(hundredth));
}

}
