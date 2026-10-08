#include "resources/sound.hpp"
#include "sound/sound_engine.hpp"
#include <array>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

using namespace lezac::sound;

namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

bool same(SoundInterruptState a, SoundInterruptState b) {
    return a.accumulator == b.accumulator && a.gateTick == b.gateTick &&
           a.periodTicks == b.periodTicks;
}

uint64_t fingerprint = 14695981039346656037ULL;
void hashByte(uint8_t value) {
    fingerprint = (fingerprint ^ value) * 1099511628211ULL;
}
void hashState(const SoundEngine& engine, SoundInterruptAction action) {
    const auto latch = engine.latch();
    const auto irq = engine.interruptState();
    for (uint8_t value : {uint8_t(latch.active), latch.currentSelector,
            uint8_t(latch.latchedOffset), uint8_t(latch.latchedOffset >> 8),
            irq.accumulator, irq.gateTick, irq.periodTicks,
            uint8_t(action.frequency), uint8_t(action.frequency >> 8),
            uint8_t(action.programTone), uint8_t(action.silence)}) hashByte(value);
}

void seed(SoundEngine& engine, uint16_t cursor, SoundInterruptState irq,
          uint8_t selector = 5, bool active = true) {
    engine.restoreLatchForFixture({active, selector, cursor, 1, false});
    engine.restoreInterruptForFixture(irq);
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 2, "expected raw bank path");
        const auto bank = lezac::resources::loadRawSon(argv[1]);
        require(bank.stepCount == 130, "shipped sound bank changed");
        SoundEngine engine(bank);
        uint64_t phaseCases = 0, phaseTone = 0, phaseSilence = 0;
        for (unsigned acc = 0; acc < 256; ++acc) {
            for (unsigned period = 0; period < 256; ++period) {
                for (unsigned gate = 0; gate < 256; ++gate) {
                    seed(engine, 0, {uint8_t(acc), uint8_t(gate), uint8_t(period)});
                    const auto action = engine.advanceSoundInterrupt();
                    const bool advances = uint8_t(acc + 1) == period;
                    const bool silence = !advances && uint8_t(acc + 1) == gate;
                    const auto irq = engine.interruptState();
                    require(action.programTone == advances && action.silence == silence &&
                            action.frequency == (advances ? 247 : 0), "phase action differs");
                    require(engine.latch().active && engine.latch().currentSelector == 5 &&
                            engine.latch().latchedOffset == (advances ? 1 : 0), "phase cursor differs");
                    require(irq.accumulator == (advances ? 0 : uint8_t(acc + 1)) &&
                            irq.gateTick == (advances ? 1 : gate) &&
                            irq.periodTicks == (advances ? 1 : period), "phase state differs");
                    ++phaseCases;
                    phaseTone += action.programTone;
                    phaseSilence += action.silence;
                }
            }
        }
        require(phaseTone == 65536 && phaseSilence == 65280, "phase totals differ");

        uint64_t bankCases = 0;
        constexpr std::array<uint8_t, 4> boundary{0, 1, 2, 255};
        for (uint16_t cursor = 0; cursor < bank.stepCount; ++cursor) {
            for (uint8_t acc : boundary) for (uint8_t period : boundary) for (uint8_t gate : boundary) {
                seed(engine, cursor, {acc, gate, period});
                const auto action = engine.advanceSoundInterrupt();
                const bool advances = uint8_t(acc + 1) == period;
                const uint16_t word = engine.soundStepPeriodWord(cursor);
                const bool stops = advances && word == kSoundStopPeriod;
                const auto irq = engine.interruptState();
                require(engine.latch().active == !stops && engine.latch().currentSelector == 5 &&
                        engine.latch().latchedOffset == cursor + advances, "bank latch differs");
                require(action.programTone == (advances && !stops) &&
                        action.silence == (stops || (!advances && uint8_t(acc + 1) == gate)) &&
                        action.frequency == (advances && !stops ? word : 0), "bank action differs");
                require(irq.accumulator == (advances ? 0 : uint8_t(acc + 1)) &&
                        irq.gateTick == (advances && !stops ? engine.soundStepGateTick(cursor) : gate) &&
                        irq.periodTicks == (stops ? 1 : advances ? engine.soundStepPeriodTicks(cursor) : period),
                        "bank state differs");
                hashState(engine, action);
                ++bankCases;
            }
        }
        const uint64_t bankHash = fingerprint;
        fingerprint = 14695981039346656037ULL;

        uint64_t directCases = 0;
        constexpr std::array<uint8_t, 3> directBoundary{0, 1, 255};
        for (uint32_t cursor = 0xea61; cursor <= 0xffff; ++cursor) {
            for (uint8_t acc : directBoundary) for (uint8_t period : directBoundary) for (uint8_t gate : directBoundary) {
                const SoundInterruptState original{acc, gate, period};
                seed(engine, uint16_t(cursor), original);
                const auto action = engine.advanceSoundInterrupt();
                const bool ended = cursor - 4 <= 0xea60;
                require(engine.latch().active == !ended && engine.latch().currentSelector == 5 &&
                        engine.latch().latchedOffset == cursor - 4, "direct cursor differs");
                require(action.frequency == cursor - 0xea42 && action.programTone &&
                        action.silence == ended, "direct final Sound/NoSound order differs");
                require(same(engine.interruptState(), original), "direct branch changed IRQ counters");
                hashState(engine, action);
                ++directCases;
            }
        }
        const uint64_t directHash = fingerprint;

        for (uint32_t cursor = 0; cursor <= 0xffff; ++cursor) {
            seed(engine, uint16_t(cursor), {255, 2, 0}, 5, false);
            const auto action = engine.advanceSoundInterrupt();
            require(!action.programTone && !action.silence && action.frequency == 0 &&
                    !engine.latch().active && engine.latch().latchedOffset == cursor &&
                    same(engine.interruptState(), {255, 2, 0}), "inactive IRQ mutated state");
        }
        fingerprint = 14695981039346656037ULL;
        for (unsigned current = 0; current < 256; ++current) {
            for (unsigned pending = 0; pending < 256; ++pending) {
                seed(engine, 0xea7e, {255, 7, 0}, uint8_t(current));
                const int previous = uint8_t(current - 1);
                const int signedPrevious = previous < 128 ? previous : previous - 256;
                const int signedPending = pending < 128 ? int(pending) : int(pending) - 256;
                const bool expected = signedPrevious < signedPending;
                const bool accepted = engine.requestSoundCursor(0x21, uint8_t(pending));
                require(accepted == expected,
                        "priority acceptance differs");
                require(same(engine.interruptState(), {255, 7, 0}), "accepted request reset IRQ phase");
                require(engine.latch().latchedOffset == (expected ? 0x21 : 0xea7e) &&
                        engine.latch().currentSelector == (expected ? pending : current), "priority state differs");
                hashByte(uint8_t(accepted));
                hashState(engine, {});
            }
        }
        const uint64_t priorityHash = fingerprint;
        for (unsigned pending = 0; pending < 256; ++pending) {
            seed(engine, 0xea7e, {255, 7, 0}, 0x80, false);
            require(engine.requestSoundCursor(0x21, uint8_t(pending)) &&
                    same(engine.interruptState(), {255, 7, 0}), "inactive priority rejected or reset phase");
        }

        seed(engine, 0xea7e, {0, 2, 1});
        unsigned directTicks = 0;
        while (engine.latch().active) {
            require(!engine.requestSoundCursor(0x24, 2), "lower priority interrupted active sweep");
            engine.advanceSoundInterrupt();
            require(++directTicks <= 8, "observed sweep did not terminate");
        }
        require(directTicks == 8 && engine.latch().latchedOffset == 0xea5e &&
                engine.latch().currentSelector == 5 && same(engine.interruptState(), {0, 2, 1}),
                "observed seed sweep endpoint differs");
        require(engine.requestSoundCursor(0x24, 2), "completed sweep did not release priority");

        unsigned trajectoryCases = 0;
        for (uint16_t cursor : kDebugSoundCursors) {
            seed(engine, cursor, {0, 0, 1});
            unsigned ticks = 0;
            while (engine.latch().active) {
                engine.advanceSoundInterrupt();
                require(++ticks <= 4096, "bank trajectory did not stop");
            }
            require(engine.latch().latchedOffset == engine.soundStopCursorFor(cursor) &&
                    engine.latch().currentSelector == 5 && engine.interruptState().accumulator == 0 &&
                    engine.interruptState().periodTicks == 1, "bank stop endpoint differs");
            ++trajectoryCases;
        }
        seed(engine, 130, {0, 0, 1});
        bool rejectedExtent = false;
        try { engine.advanceSoundInterrupt(); } catch (const std::runtime_error&) { rejectedExtent = true; }
        require(rejectedExtent, "unrecovered bank extent silently substituted a stop");
        std::cout << "sound_interrupt=ok phase_cases=" << phaseCases
                  << " bank_cases=" << bankCases << " direct_cases=" << directCases
                  << " inactive_cases=65536 priority_cases=65536 trajectories=" << trajectoryCases
                  << " observed_seed_ticks=" << directTicks
                  << " bank_hash=" << std::hex << bankHash << " direct_hash=" << directHash << std::dec
                  << " priority_hash=" << std::hex << priorityHash << std::dec
                  << " inactive_priority_cases=256"
                  << " runtime_scheduler_integrated=0 native_irq_claim=0 whole_game_complete=0\n";
    } catch (const std::exception& error) {
        std::cerr << "sound_interrupt_failed: " << error.what() << '\n';
        return 1;
    }
}
