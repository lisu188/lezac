#include "core/startup_timing.hpp"
#include "resources/binary.hpp"
#include "resources/io.hpp"
#include "resources/json.hpp"

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using lezac::core::DosClockSample;
using lezac::core::StartupTimingWords;
using lezac::core::startupElapsedWord;
using lezac::core::startupTimingFromElapsed;

static_assert(!startupTimingFromElapsed(0));
static_assert(*startupTimingFromElapsed(98) == StartupTimingWords{82, 16, 2});
static_assert(*startupTimingFromElapsed(99) == StartupTimingWords{81, 16, 2});
static_assert(*startupTimingFromElapsed(128) == StartupTimingWords{63, 13, 2});
static_assert(*startupTimingFromElapsed(299) == StartupTimingWords{27, 5, 2});
static_assert(!startupTimingFromElapsed(300));
static_assert(startupElapsedWord({0, 0, 0}, {10, 55, 37}) == 1);

namespace {

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

DosClockSample sample(const std::string& json) {
    const auto byte = [&](const std::string& key, int maximum) {
        const int value = lezac::resources::extractInt(json, key, -1);
        require(value >= 0 && value <= maximum, "invalid clock sample: " + key);
        return static_cast<uint8_t>(value);
    };
    return {byte("minute", 59), byte("second", 59), byte("hundredth", 99)};
}

struct Event {
    std::string kind;
    uint16_t argument = 0;
    DosClockSample clock{};

    bool operator==(const Event& other) const {
        return kind == other.kind && argument == other.argument &&
            clock.minute == other.clock.minute && clock.second == other.clock.second &&
            clock.hundredth == other.clock.hundredth;
    }
};

} // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2, "expected startup timing fixture directory");
        const std::filesystem::path root{argv[1]};
        const auto gate = lezac::resources::readFile((root / "gate-bits.bin").string());
        const auto table = lezac::resources::readFile((root / "accepted-words.bin").string());
        const auto manifest = lezac::resources::readTextFile((root / "manifest.json").string());
        require(gate.size() == 8192 && table.size() == 299 * 6, "fixture size differs");

        std::size_t accepted = 0;
        for (uint32_t raw = 0; raw < 65536; ++raw) {
            const auto actual = startupTimingFromElapsed(static_cast<uint16_t>(raw));
            const bool expected = (gate[raw / 8] & (1u << (raw % 8))) != 0;
            require(actual.has_value() == expected, "elapsed acceptance differs: " + std::to_string(raw));
            if (expected) {
                const auto offset = accepted * 6;
                const StartupTimingWords words{lezac::resources::le16(table, offset),
                    lezac::resources::le16(table, offset + 2), lezac::resources::le16(table, offset + 4)};
                require(*actual == words, "original arithmetic differs: " + std::to_string(raw));
                ++accepted;
            }
        }
        require(accepted == 299, "accepted input count differs");

        const auto cases = lezac::resources::extractObjectArray(manifest, "cases");
        require(cases.size() == 10, "complete function count differs");
        std::size_t totalEvents = 0;
        for (const auto& fixture : cases) {
            const auto name = lezac::resources::extractString(fixture, "name");
            std::vector<DosClockSample> samples;
            for (const auto& json : lezac::resources::extractObjectArray(fixture, "samples")) {
                samples.push_back(sample(json));
            }
            std::vector<Event> expected;
            for (const auto& json : lezac::resources::extractObjectArray(fixture, "events")) {
                const auto kind = lezac::resources::extractString(json, "kind");
                if (kind == "crt_delay") {
                    const int argument = lezac::resources::extractInt(json, "argument", -1);
                    require(argument == 500 || argument == 1000, "invalid delay event");
                    expected.push_back({kind, static_cast<uint16_t>(argument), {}});
                } else {
                    require(kind == "dos_time", "unknown service event");
                    expected.push_back({kind, 0, sample(json)});
                }
            }
            std::size_t cursor = 0;
            std::vector<Event> actual;
            const auto words = lezac::core::calibrateStartupTiming([&] {
                require(cursor < samples.size(), name + ": clock script exhausted");
                const auto clock = samples[cursor++];
                actual.push_back({"dos_time", 0, clock});
                return clock;
            }, [&](uint16_t argument) { actual.push_back({"crt_delay", argument, {}}); });
            const StartupTimingWords expectedWords{
                static_cast<uint16_t>(lezac::resources::extractInt(fixture, "character_delay")),
                static_cast<uint16_t>(lezac::resources::extractInt(fixture, "auxiliary_delay")),
                static_cast<uint16_t>(lezac::resources::extractInt(fixture, "minimum_word"))};
            require(words == expectedWords, name + ": complete function words differ");
            require(cursor == samples.size(), name + ": unused clock samples");
            require(actual == expected, name + ": original service order differs");
            totalEvents += actual.size();
        }
        require(totalEvents == 55, "original service event count differs");
        std::cout << "startup_timing_original=ok inputs=65536 accepted=299 functions=10 "
                     "service_events=55 natural_startup=0 whole_game_parity=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "startup_timing_original=failed " << error.what() << '\n';
        return 1;
    }
}
