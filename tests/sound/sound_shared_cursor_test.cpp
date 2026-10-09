#include "sound/sound_engine.hpp"
#include <iostream>
#include <stdexcept>

namespace {
using lezac::sound::SoundEngine;
using lezac::sound::SoundLatch;

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

bool sameLatch(const SoundLatch& a, const SoundLatch& b) {
    return a.active == b.active && a.currentSelector == b.currentSelector &&
        a.latchedOffset == b.latchedOffset && a.recordIndex == b.recordIndex &&
        a.directSweep == b.directSweep;
}

int signedByte(unsigned value) {
    const int byte = static_cast<int>(value & 255u);
    return byte < 128 ? byte : byte - 256;
}
}

int main() {
    try {
        lezac::resources::SoundBank bank;
        SoundEngine sound(bank);
        require(sound.requestSoundCursor(0x69, 12), "default request rejected");
        require(sound.requestAttemptCount() == 0, "counting enabled by default");
        sound.setRequestAttemptCounting(true);
        uint64_t cases = 0;
        for (unsigned active = 0; active != 2; ++active) {
            for (unsigned previous = 0; previous != 256; ++previous) {
                for (unsigned requested = 0; requested != 256; ++requested) {
                    SoundLatch seed;
                    seed.active = active != 0;
                    seed.currentSelector = static_cast<uint8_t>(previous);
                    seed.latchedOffset = 0x69;
                    seed.recordIndex = 3;
                    sound.restoreLatchForFixture(seed);
                    sound.restoreRequestForFixture(0x24, 2);
                    require(sound.requestAttemptCount() == cases, "fixture restore counted as request");
                    const bool expected = !active || signedByte(previous - 1u) < signedByte(requested);
                    const bool accepted = sound.requestSoundOffset(0x3d, static_cast<uint8_t>(requested));
                    ++cases;
                    require(accepted == expected, "signed-byte priority changed");
                    require(sound.requestAttemptCount() == cases, "request attempt not counted");
                    require(sound.requestCursor() == 0x3d && sound.requestSelector() == requested,
                            "request scratch not written on rejection");
                    const auto latched = sound.latch();
                    if (!accepted) require(sameLatch(latched, seed), "rejected request changed latch");
                    const uint16_t cursor = static_cast<uint16_t>(cases * 834u);
                    sound.writeSharedCursor(cursor);
                    require(sound.requestCursor() == cursor && sound.requestSelector() == requested,
                            "shared cursor changed selector");
                    require(sameLatch(sound.latch(), latched), "shared cursor changed accepted latch");
                    require(sound.requestAttemptCount() == cases, "shared cursor counted as request");
                }
            }
        }
        sound.setRequestAttemptCounting(false);
        sound.requestSoundCursor(0x3d, 12);
        require(sound.requestAttemptCount() == cases, "disabled counting changed count");
        const auto beforeClear = sound.latch();
        sound.clearRequestAttemptCount();
        require(sound.requestAttemptCount() == 0 && sameLatch(sound.latch(), beforeClear),
                "count reset changed latch");
        require(cases == 131072, "priority matrix incomplete");
        std::cout << "sound_shared_cursor=ok priority_cases=131072 scratch_writes=131072"
                     " rejected_requests_counted=1 default_counting=0 opt_in_bounded=1 original_runtime_claim=0\n";
    } catch (const std::exception& error) {
        std::cerr << "sound_shared_cursor=failed " << error.what() << '\n';
        return 1;
    }
}
