#include "app/governed_loop.hpp"

#include <algorithm>

namespace lezac::app {

long GovernedLoop::pump(bool& running, const GovernedLoopCallbacks& callbacks) {
    uint32_t last = callbacks.now();
    uint32_t lastTickAt = last;
    double tickAccumulatorMs = 0.0;
    long ticks = 0;
    stats_.droppedTicks = 0;
    stats_.maxTickGapMs = 0;
    while (running && !callbacks.stop()) {
        callbacks.processEvents(running);
        uint32_t now = callbacks.now();
        tickAccumulatorMs += static_cast<double>(now - last);
        last = now;
        const double cap = kGovernedTickMs * kMaxCatchUpTicks;
        if (tickAccumulatorMs > cap) {
            // Time beyond the catch-up cap is discarded, which silently
            // loses gameplay ticks; count them so a diagnostic can say so
            // instead of reporting a healthy average.
            stats_.droppedTicks +=
                static_cast<long>((tickAccumulatorMs - cap) / kGovernedTickMs);
            tickAccumulatorMs = cap;
        }
        bool ticked = false;
        while (tickAccumulatorMs >= kGovernedTickMs) {
            tickAccumulatorMs -= kGovernedTickMs;
            callbacks.tickAndPresent(static_cast<float>(kGovernedTickMs / 1000.0));
            ++ticks;
            ticked = true;
        }
        if (ticked) {
            const uint32_t gap = now - lastTickAt;
            lastTickAt = now;
            stats_.maxTickGapMs = std::max(stats_.maxTickGapMs,
                                         static_cast<long>(gap));
        }
        callbacks.delay(kEventPollDelayMs);
    }
    return ticks;
}

}
