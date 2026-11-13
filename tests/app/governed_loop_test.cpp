#include "app/governed_loop.hpp"

#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

using lezac::app::GovernedLoop;

namespace {

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

void checkCadence(uint32_t start) {
    uint32_t now = start;
    int updates = 0, events = 0, sleeps = 0, samples = 0;
    bool running = true;
    GovernedLoop loop;
    const long ticks = loop.pump(running, {
        [&](bool&) { ++events; },
        [&](float dt) {
            require(std::abs(dt - 0.0408f) < 0.000001f, "tick duration changed");
            ++updates;
        },
        [&] { return static_cast<uint32_t>(now - start) >= 164; },
        [&] { ++samples; return now; },
        [&](uint32_t ms) {
            require(ms == 4, "event poll delay changed");
            now += ms;
            ++sleeps;
        }
    });
    require(ticks == 3 && updates == 3, "nominal cadence or rollover changed");
    require(events == 41 && sleeps == 41 && samples == 42, "sampling boundary changed");
    require(loop.stats().droppedTicks == 0 && loop.stats().maxTickGapMs == 44,
            "nominal cadence statistics changed");
}

void checkCatchUp(GovernedLoop& loop, uint32_t elapsed, long expectedTicks, long dropped) {
    uint32_t now = 0;
    bool running = true;
    std::string order;
    const long ticks = loop.pump(running, {
        [&](bool&) { now += elapsed; order += 'E'; },
        [&](float) { order += "TPO"; },
        [&] { return !order.empty(); },
        [&] { return now; },
        [&](uint32_t ms) { now += ms; order += 'S'; }
    });
    std::string expected = "E";
    for (long i = 0; i < expectedTicks; ++i) expected += "TPO";
    expected += 'S';
    require(ticks == expectedTicks && order == expected, "catch-up or callback order changed");
    require(loop.stats().droppedTicks == dropped
                && loop.stats().maxTickGapMs == static_cast<long>(elapsed),
            "catch-up statistics changed");
}

void checkStops(GovernedLoop& loop) {
    for (bool initiallyRunning : {false, true}) {
        bool running = initiallyRunning;
        int stops = 0, samples = 0;
        const long ticks = loop.pump(running, {
            [](bool&) { throw std::runtime_error("events after initial stop"); },
            [](float) { throw std::runtime_error("tick after initial stop"); },
            [&] { ++stops; return true; },
            [&] { ++samples; return 0u; },
            [](uint32_t) { throw std::runtime_error("delay after initial stop"); }
        });
        require(ticks == 0 && samples == 1 && stops == (initiallyRunning ? 1 : 0),
                "initial stop or running short-circuit changed");
        require(loop.stats().droppedTicks == 0 && loop.stats().maxTickGapMs == 0,
                "statistics did not reset between runs");
    }
    uint32_t now = 0;
    bool running = true, stop = false;
    int stops = 0, ticksSeen = 0, sleeps = 0;
    const long ticks = loop.pump(running, {
        [&](bool&) { stop = true; now += 1000; },
        [&](float) { ++ticksSeen; },
        [&] { ++stops; return stop; },
        [&] { return now; },
        [&](uint32_t) { ++sleeps; }
    });
    require(ticks == 5 && ticksSeen == 5 && stops == 2 && sleeps == 1,
            "stop predicate was resampled inside an entered iteration");
}

void checkQuit(bool quitInTick) {
    uint32_t now = 0;
    bool running = true;
    std::string order;
    GovernedLoop loop;
    const long ticks = loop.pump(running, {
        [&](bool& active) {
            if (!quitInTick) active = false;
            now += quitInTick ? 1000 : 44;
            order += 'E';
        },
        [&](float) { running = false; order += "TPO"; },
        [] { return false; },
        [&] { return now; },
        [&](uint32_t) { order += 'S'; }
    });
    const long expectedTicks = quitInTick ? 5 : 1;
    std::string expected = "E";
    for (long i = 0; i < expectedTicks; ++i) expected += "TPO";
    expected += 'S';
    require(ticks == expectedTicks && order == expected,
            "quit skipped the entered iteration's remaining ticks or delay");
}

void checkException(bool throwInTick) {
    uint32_t now = 0;
    bool running = true;
    std::string order;
    GovernedLoop loop;
    bool caught = false;
    try {
        loop.pump(running, {
            [&](bool&) {
                order += 'E';
                now += 1000;
                if (!throwInTick) throw std::runtime_error("callback marker");
            },
            [&](float) { order += 'T'; throw std::runtime_error("callback marker"); },
            [] { return false; },
            [&] { order += 'C'; return now; },
            [&](uint32_t) { order += 'S'; }
        });
    } catch (const std::runtime_error& error) {
        caught = std::string(error.what()) == "callback marker";
    }
    require(caught && order == (throwInTick ? "CECT" : "CE"),
            "callback exception was swallowed or work continued after it");
    require(loop.stats().droppedTicks == (throwInTick ? 19 : 0)
                && loop.stats().maxTickGapMs == 0,
            "partial statistics on exception changed");
}

}

int main() {
    checkCadence(0);
    checkCadence(std::numeric_limits<uint32_t>::max() - 20u);
    GovernedLoop loop;
    checkCatchUp(loop, 203, 4, 0);
    checkCatchUp(loop, 204, 5, 0);
    checkCatchUp(loop, 205, 5, 0);
    checkCatchUp(loop, 1000, 5, 19);
    checkStops(loop);
    checkQuit(false);
    checkQuit(true);
    checkException(false);
    checkException(true);
    std::cout << "governed_loop=ok cadence=1 rollover=1 cap_boundaries=4 stop_boundaries=3"
                 " quit_boundaries=2 exceptions=2 stats_reset=1\n";
}
