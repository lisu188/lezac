#pragma once

#include <cstdint>
#include <functional>

namespace lezac::app {

inline constexpr double kGovernedTickMs = 40.8;
inline constexpr uint32_t kEventPollDelayMs = 4;
inline constexpr int kMaxCatchUpTicks = 5;

struct GovernedLoopCallbacks {
    std::function<void(bool&)> processEvents;
    std::function<void(float)> tickAndPresent;
    std::function<bool()> stop;
    std::function<uint32_t()> now;
    std::function<void(uint32_t)> delay;
};

struct GovernedLoopStats {
    long droppedTicks = 0;
    long maxTickGapMs = 0;
};

// Owns cadence and statistics only. The application supplies all SDL and game work.
class GovernedLoop {
public:
    long pump(bool& running, const GovernedLoopCallbacks& callbacks);
    const GovernedLoopStats& stats() const { return stats_; }

private:
    GovernedLoopStats stats_;
};

}
