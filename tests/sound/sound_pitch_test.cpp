#include "sound/sound_engine.hpp"
#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using lezac::resources::SoundBank;
using lezac::sound::SoundEngine;
using lezac::sound::SpeakerToneState;

namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

size_t transitions(const std::vector<int16_t>& samples) {
    size_t count = 0;
    for (size_t i = 1; i < samples.size(); ++i) {
        count += samples[i] != samples[i - 1];
    }
    return count;
}
}

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--divisors") {
            for (uint32_t frequency = 0; frequency <= 0xffff; ++frequency) {
                std::cout << std::hex << std::setw(4) << std::setfill('0')
                          << SoundEngine::speakerDivisorForFrequency(
                                 static_cast<uint16_t>(frequency)) << '\n';
            }
            return 0;
        }
        require(argc == 1, "unexpected sound pitch test argument");
        for (uint32_t frequency = 0; frequency <= 0xffff; ++frequency) {
            const uint16_t expected = frequency <= 18 ? 0 :
                static_cast<uint16_t>(1193181 / frequency);
            require(SoundEngine::speakerDivisorForFrequency(
                        static_cast<uint16_t>(frequency)) == expected,
                    "original speaker DIV conversion differs");
        }

        SoundBank bank;
        SoundEngine engine(bank);
        constexpr int sampleCount = 12800;
        for (uint16_t frequency : {19, 20, 31, 40, 247, 311, 1000, 4000, 5000, 65535}) {
            SpeakerToneState tone;
            std::vector<int16_t> samples;
            engine.appendToneSamples(samples, frequency, sampleCount, 7200, tone);
            require(samples.size() == sampleCount, "tone sample count differs");
            const uint64_t denominator = (1193181 / frequency) * uint64_t{22050};
            for (uint64_t i = 0; i < samples.size(); ++i) {
                const uint64_t phase = ((i + 1) * 1193182) % denominator;
                const int16_t expected = phase * 2 < denominator ? 7200 : -7200;
                require(samples[i] == expected, "synthesized pitch differs from PIT divisor");
            }
        }

        SpeakerToneState tone;
        std::vector<int16_t> samples;
        engine.appendToneSamples(samples, 18, 32, 7200, tone);
        require(!tone.enabled && tone.divisor == 0 &&
                std::all_of(samples.begin(), samples.end(), [](int16_t v) { return v == 0; }),
                "ignored command enabled an idle speaker");
        engine.appendToneSamples(samples, 247, 32, 7200, tone);
        const uint16_t savedDivisor = tone.divisor;
        engine.appendToneSamples(samples, 0, 32, 7200, tone);
        require(tone.enabled && tone.divisor == savedDivisor && samples.back() != 0,
                "ignored command replaced an active speaker");
        tone.enabled = false;
        engine.appendToneSamples(samples, 18, 32, 7200, tone);
        require(!tone.enabled && tone.divisor == savedDivisor && samples.back() == 0,
                "ignored command restarted a gated speaker");

        bank.stepCount = 2;
        bank.payload = {20, 0, 0, 28, 0, 0, 0x30, 0x75, 0, 1, 0, 0};
        samples = engine.synthesizeSoundCursor(0);
        require(samples.size() == 22036 && transitions(samples) == 39 &&
                std::all_of(samples.begin(), samples.end(), [](int16_t v) { return v != 0; }),
                "cursor playback did not use the original 20 Hz pitch");
        bank.stepCount = 3;
        bank.payload = {247, 0, 1, 2, 0, 0, 18, 0, 0, 1, 0, 0,
                        0x30, 0x75, 0, 1, 0, 0};
        samples = engine.synthesizeSoundCursor(0);
        require(samples.size() == 2361 &&
                std::all_of(samples.begin() + 787, samples.end(), [](int16_t v) { return v == 0; }),
                "ignored cursor command restarted a gated speaker");
        samples = engine.synthesizeDirectSweep(0xea74);
        require(samples.size() == 1965 && transitions(samples) == 7,
                "direct sweep did not use frequency commands");
        std::cout << "sound_pitch=ok frequencies=65536 pcm_cases=10 ignored_command_states=3"
                     " cursor_playback=1 direct_sweep=1 original_runtime_claim=0\n";
    } catch (const std::exception& error) {
        std::cerr << "sound_pitch_failed: " << error.what() << '\n';
        return 1;
    }
}
