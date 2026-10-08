#include "resources/sound.hpp"
#include "sound/sound_engine.hpp"
#include <algorithm>
#include <array>
#include <iostream>
#include <initializer_list>
#include <stdexcept>
#include <vector>

using namespace lezac::sound;
using lezac::resources::SoundBank;

namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

uint64_t boundary(uint64_t interrupt) {
    return (interrupt * uint64_t{22050} * 65536 + 1193182 - 1) / 1193182;
}

std::vector<int16_t> through(SoundEngine& engine, uint64_t interrupt) {
    return engine.renderClockedSamples(static_cast<size_t>(
        boundary(interrupt) - engine.clockState().renderedSamples));
}

bool silent(const std::vector<int16_t>& samples) {
    return std::all_of(samples.begin(), samples.end(), [](int16_t value) { return value == 0; });
}

SoundBank synthetic(std::initializer_list<std::array<uint16_t, 3>> entries) {
    SoundBank bank;
    for (const auto& entry : entries) {
        bank.payload.insert(bank.payload.end(), {uint8_t(entry[0]), uint8_t(entry[0] >> 8),
            uint8_t(entry[1]), uint8_t(entry[2]), 0, 0});
    }
    bank.stepCount = entries.size();
    return bank;
}

void sameState(const SoundEngine& a, const SoundEngine& b) {
    const auto x = a.latch(), y = b.latch();
    const auto p = a.interruptState(), q = b.interruptState();
    const auto c = a.clockState(), d = b.clockState();
    const auto s = a.speakerState(), t = b.speakerState();
    require(x.active == y.active && x.latchedOffset == y.latchedOffset &&
            x.currentSelector == y.currentSelector && x.recordIndex == y.recordIndex &&
            x.directSweep == y.directSweep && p.accumulator == q.accumulator &&
            p.gateTick == q.gateTick && p.periodTicks == q.periodTicks &&
            c.pitAccumulator == d.pitAccumulator && c.interrupts == d.interrupts &&
            c.renderedSamples == d.renderedSamples && s.enabled == t.enabled &&
            s.divisor == t.divisor && s.phase == t.phase, "render partition changed state");
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 2, "expected raw sound bank path");
        const auto bank = lezac::resources::loadRawSon(argv[1]);
        SoundEngine idle(bank);
        for (uint64_t i = 1; i <= 1000; ++i) {
            const auto previous = idle.clockState().renderedSamples;
            require(silent(idle.renderClockedSamples(static_cast<size_t>(boundary(i) - previous - 1))),
                    "inactive speaker became audible");
            require(idle.clockState().interrupts == i - 1, "IRQ advanced early");
            require(silent(idle.renderClockedSamples(1)), "inactive boundary became audible");
            const auto clock = idle.clockState();
            require(clock.interrupts == i && clock.renderedSamples == boundary(i) &&
                    clock.pitAccumulator == boundary(i) * 1193182 - i * uint64_t{22050} * 65536,
                    "rational BIOS clock drifted");
            require(idle.interruptState().accumulator == 0, "inactive IRQ changed counters");
        }
        require(idle.renderClockedSamples(0).empty(), "zero render changed clock");

        SoundEngine sweep(bank);
        require(sweep.requestSoundCursor(0xea7e, 5), "initial sweep rejected");
        require(silent(sweep.renderClockedSamples(static_cast<size_t>(boundary(1) - 1))),
                "request programmed a tone before an IRQ");
        require(sweep.latch().active && !sweep.requestSoundCursor(0, 2),
                "rendering cleared pending priority");
        sweep.renderClockedSamples(1);
        require(sweep.latch().latchedOffset == 0xea7a && sweep.speakerState().enabled &&
                sweep.speakerState().divisor == SoundEngine::speakerDivisorForFrequency(60),
                "first sweep IRQ did not program its tone");
        require(!silent(through(sweep, 7)) && sweep.latch().active, "sweep stopped early");
        through(sweep, 8);
        require(!sweep.latch().active && sweep.latch().latchedOffset == 0xea5e &&
                !sweep.speakerState().enabled &&
                sweep.speakerState().divisor == SoundEngine::speakerDivisorForFrequency(32),
                "terminal Sound/NoSound ordering differs");
        require(silent(sweep.renderClockedSamples(100)), "terminal sweep kept sounding");
        require(sweep.requestSoundCursor(0, 2), "stopped sweep blocked a new request");

        constexpr std::array<uint16_t, 16> starts{
            0, 5, 8, 0x12, 0x1a, 0x21, 0x24, 0x27,
            0x2d, 0x31, 0x35, 0x3d, 0x56, 0x69, 0x78, 0xea7e};
        for (uint16_t cursor : starts) {
            SoundEngine whole(bank), pieces(bank);
            whole.requestSoundCursor(cursor, 5);
            pieces.requestSoundCursor(cursor, 5);
            const auto expected = whole.renderClockedSamples(400000);
            std::vector<int16_t> actual;
            constexpr std::array<size_t, 7> chunks{1, 7, 441, 1211, 3, 2205, 89};
            size_t index = 0;
            while (actual.size() < expected.size()) {
                auto chunk = pieces.renderClockedSamples(std::min(
                    chunks[index++ % chunks.size()], expected.size() - actual.size()));
                actual.insert(actual.end(), chunk.begin(), chunk.end());
            }
            require(actual == expected, "render partition changed PCM");
            sameState(whole, pieces);
        }

        const auto ignoredBank = synthetic({{1000, 0, 1}, {18, 0, 1}, {0x7530, 0, 1}});
        SoundEngine ignored(ignoredBank);
        ignored.requestSoundCursor(0, 5);
        through(ignored, 1);
        const auto divisor = ignored.speakerState().divisor;
        through(ignored, 2);
        require(ignored.speakerState().enabled && ignored.speakerState().divisor == divisor,
                "ignored frequency replaced an active tone");
        through(ignored, 3);
        require(!ignored.latch().active && !ignored.speakerState().enabled,
                "bank stop did not disable the speaker");

        const auto gateBank = synthetic({{1000, 1, 3}, {18, 0, 1}, {0x7530, 0, 1}});
        SoundEngine gated(gateBank);
        gated.requestSoundCursor(0, 5);
        through(gated, 1);
        through(gated, 2);
        require(!gated.speakerState().enabled && gated.latch().active,
                "gate silence cleared the latch or left the speaker on");
        through(gated, 4);
        require(!gated.speakerState().enabled && gated.latch().latchedOffset == 2,
                "ignored frequency restarted a gated speaker");

        const auto replacementBank = synthetic({{1000, 2, 3}, {800, 0, 1}, {0x7530, 0, 1}});
        SoundEngine replacement(replacementBank);
        replacement.requestSoundCursor(0, 5);
        through(replacement, 2);
        const auto clockBefore = replacement.clockState();
        require(replacement.interruptState().accumulator == 1 &&
                replacement.requestSoundCursor(1, 6) &&
                replacement.interruptState().accumulator == 1 &&
                replacement.clockState().pitAccumulator == clockBefore.pitAccumulator,
                "replacement reset IRQ or clock phase");
        through(replacement, 3);
        require(replacement.latch().latchedOffset == 1 && !replacement.speakerState().enabled,
                "replacement did not inherit gate phase");
        through(replacement, 4);
        require(replacement.latch().latchedOffset == 2 && replacement.speakerState().enabled &&
                replacement.speakerState().divisor == SoundEngine::speakerDivisorForFrequency(800),
                "replacement did not inherit period phase");

        const auto wrapBank = synthetic({{247, 0, 0}, {0x7530, 0, 1}});
        SoundEngine wrap(wrapBank);
        wrap.requestSoundCursor(0, 5);
        through(wrap, 256);
        require(wrap.latch().active && wrap.latch().latchedOffset == 1 &&
                wrap.interruptState().accumulator == 255, "zero period did not wait 256 IRQs");
        through(wrap, 257);
        require(!wrap.latch().active && wrap.latch().latchedOffset == 2 &&
                !wrap.speakerState().enabled, "zero period wrap did not reach stop");
        std::cout << "clocked_sound=ok boundaries=1000 trajectories=16 terminal_order=1"
                  << " priority_lifetime=1 ignored_commands=2 replacement_phase=1 period_zero=1"
                  << " native_timing_claim=0\n";
    } catch (const std::exception& error) {
        std::cerr << "clocked_sound=failed " << error.what() << '\n';
        return 1;
    }
}
