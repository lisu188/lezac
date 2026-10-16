#include "core/frame_pacing.hpp"
#include "resources/binary.hpp"
#include "resources/io.hpp"
#include "resources/json.hpp"

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

using lezac::core::adjustOriginalFrameDelay;
using lezac::core::advanceFramePacingCounter;

static_assert(adjustOriginalFrameDelay(16, 119, 2) == 18);
static_assert(adjustOriginalFrameDelay(16, 120, 2) == 16);
static_assert(adjustOriginalFrameDelay(16, 125, 2) == 16);
static_assert(adjustOriginalFrameDelay(16, 126, 2) == 14);
static_assert(adjustOriginalFrameDelay(1, 126, 2) == 0);
static_assert(adjustOriginalFrameDelay(65535, 119, 2) == 1);
static_assert(adjustOriginalFrameDelay(16, 65535, 2) == 14);
static_assert([] { uint16_t counter = 65535; return advanceFramePacingCounter(counter) && counter == 0; }());

namespace {
void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}
uint16_t word(const std::string& object, const std::string& key) {
    const int value = lezac::resources::extractInt(object, key, -1);
    require(value >= 0 && value <= 65535, "invalid fixture word: " + key);
    return static_cast<uint16_t>(value);
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 2, "expected frame-pacing fixture directory");
        const std::filesystem::path root{argv[1]};
        const auto bits = lezac::resources::readFile((root / "counter-bits.bin").string());
        const auto table = lezac::resources::readFile((root / "delay-words.bin").string());
        require(bits.size() == 8192 && table.size() == 65536 * 2, "oracle size differs");
        for (uint32_t raw = 0; raw < 65536; ++raw) {
            auto counter = static_cast<uint16_t>(raw);
            const bool sample = advanceFramePacingCounter(counter);
            require(counter == static_cast<uint16_t>(raw + 1), "counter wrap differs");
            require(sample == ((bits[raw / 8] & (1u << (raw % 8))) != 0), "original clock cadence differs");
            require(adjustOriginalFrameDelay(16, static_cast<uint16_t>(raw), 2) ==
                    lezac::resources::le16(table, raw * 2), "original feedback differs: " + std::to_string(raw));
        }
        const auto oracle = lezac::resources::readTextFile((root / "oracle.json").string());
        const auto cases = lezac::resources::extractObjectArray(oracle, "feedback_cases");
        require(cases.size() == 240, "feedback case count differs");
        for (const auto& test : cases) {
            require(adjustOriginalFrameDelay(word(test, "delay"), word(test, "elapsed"), word(test, "step")) ==
                    word(test, "result"), "original threshold/wrap case differs");
        }
        const auto replays = lezac::resources::readTextFile((root / "replays.json").string());
        const auto runs = lezac::resources::extractObjectArray(replays, "runs");
        require(runs.size() == 2, "natural capture count differs");
        std::size_t frames = 0, measurements = 0;
        for (const auto& run : runs) {
            uint16_t counter = 0, delay = word(run, "initial_delay");
            const auto capturedFrames = lezac::resources::extractObjectArray(run, "frames");
            for (const auto& frame : capturedFrames) {
                const bool sample = advanceFramePacingCounter(counter);
                const int elapsed = lezac::resources::extractInt(frame, "elapsed", -2);
                require(sample == (elapsed >= 0), "natural DOS sample cadence differs");
                if (sample) {
                    require(elapsed <= 65535, "natural elapsed word outside range");
                    delay = adjustOriginalFrameDelay(delay, static_cast<uint16_t>(elapsed), 2);
                    ++measurements;
                } else {
                    require(elapsed == -1, "unexpected natural elapsed sample");
                }
                require(counter == word(frame, "counter") && delay == word(frame, "delay"), "natural pacing differs");
                ++frames;
            }
            require(capturedFrames.size() == word(run, "completed_frames") && delay == word(run, "final_delay"),
                    "natural terminal pacing state differs");
        }
        require(frames == 299 && measurements == 9, "natural coverage differs");
        std::cout << "frame_pacing_original=ok counter_inputs=65536 elapsed_inputs=65536 "
                     "feedback_cases=240 natural_frames=299 measurements=9 live_clock_integrated=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "frame_pacing_original=failed " << error.what() << '\n';
        return 1;
    }
}
