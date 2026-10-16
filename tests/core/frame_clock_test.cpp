#include "core/interruptible_dos_time.hpp"
#include "core/interruptible_frame_clock.hpp"
#include "core/frame_pacing_calculation.hpp"
#include "core/frame_pacing_operation.hpp"
#include "core/pacing_device_clock.hpp"
#include "core/pic_work_clock.hpp"

#include <algorithm>
#include <bit>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <optional>
#include <stdexcept>
#include <string>
#include <tuple>
#include <type_traits>
#include <utility>
#include <vector>

using namespace lezac::core;

namespace {
void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}
struct Reader {
    std::vector<uint8_t> bytes;
    std::size_t cursor = 0;
    uint32_t number(unsigned count) {
        require(cursor <= bytes.size() && count <= 4 && count <= bytes.size() - cursor, "projection truncated");
        uint32_t value = 0;
        for (unsigned i = 0; i < count; ++i) value |= uint32_t{bytes[cursor++]} << (i * 8);
        return value;
    }
    uint16_t word() { return static_cast<uint16_t>(number(2)); }
    uint64_t wide() {
        const uint64_t low = number(4);
        return low | (uint64_t{number(4)} << 32);
    }
    std::vector<uint8_t> take(unsigned count) {
        require(cursor <= bytes.size() && count <= bytes.size() - cursor, "memory projection truncated");
        std::vector<uint8_t> result(bytes.begin() + cursor, bytes.begin() + cursor + count);
        cursor += count;
        return result;
    }
};
using Io = std::tuple<bool, uint16_t, uint8_t>;
struct Memory {
    std::vector<uint8_t> bytes = std::vector<uint8_t>(1048576), known = bytes, writable = bytes;
    std::vector<Io> script;
    std::size_t io = 0;
    bool checkIo = true;
    uint8_t port61 = 0;
    static uint32_t address(uint16_t s, uint16_t o, unsigned i = 0) {
        return (uint32_t{s} * 16 + static_cast<uint16_t>(o + i)) & 0xfffff;
    }
    void seed(uint16_t s, uint16_t o, const std::vector<uint8_t>& data, bool write = false) {
        for (unsigned i = 0; i < data.size(); ++i) {
            const auto at = address(s, o, i);
            require(!known[at] || bytes[at] == data[i], "contradictory aliased initial memory");
            bytes[at] = data[i]; known[at] = 1;
            if (write) writable[at] = 1;
        }
    }
    void seedNumber(uint16_t s, uint16_t o, uint32_t value, unsigned count, bool write = false) {
        std::vector<uint8_t> data;
        for (unsigned i = 0; i < count; ++i) data.push_back(static_cast<uint8_t>(value >> (i * 8)));
        seed(s, o, data, write);
    }
    uint32_t read(uint16_t s, uint16_t o, unsigned count) const {
        uint32_t value = 0;
        for (unsigned i = 0; i < count; ++i) {
            const auto at = address(s, o, i);
            require(known[at], "read outside observed initial memory and computed writes");
            value |= uint32_t{bytes[at]} << (i * 8);
        }
        return value;
    }
    void write(uint16_t s, uint16_t o, uint32_t value, unsigned count) {
        for (unsigned i = 0; i < count; ++i) {
            const auto at = address(s, o, i);
            require(writable[at], "write outside owned memory");
            bytes[at] = static_cast<uint8_t>(value >> (i * 8)); known[at] = 1;
        }
    }
    TimerIrqBus bus(PicWorkClock* clock = nullptr) {
        return {
            [&](uint16_t s, uint16_t o) { return static_cast<uint8_t>(read(s, o, 1)); },
            [&](uint16_t s, uint16_t o) { return static_cast<uint16_t>(read(s, o, 2)); },
            [&](uint16_t s, uint16_t o) { return read(s, o, 4); },
            [&](uint16_t s, uint16_t o, uint8_t v) { write(s, o, v, 1); },
            [&](uint16_t s, uint16_t o, uint16_t v) { write(s, o, v, 2); },
            [&](uint16_t s, uint16_t o, uint32_t v) { write(s, o, v, 4); },
            [&, clock](uint16_t port) {
                if (clock) clock->chargePortRead();
                if (!checkIo) { require(port == 0x61, "unexpected unit input port"); return port61; }
                require(io < script.size() && !std::get<0>(script[io]) && std::get<1>(script[io]) == port,
                        "input port boundary differs");
                return std::get<2>(script[io++]);
            },
            [&, clock](uint16_t port, uint8_t value) {
                if (clock) {
                    clock->chargePortWrite();
                    if (port == 0x20 && value == 0x20) clock->nonspecificMasterEoi();
                }
                if (checkIo) require(io < script.size() && script[io++] == Io{true, port, value}, "ordered output differs");
                if (port == 0x61) port61 = value;
            }
        };
    }
};
struct Expected {
    DosGetTimeRegisters registers;
    uint32_t mask, ticks, pspStack, io;
    uint8_t motor, drive;
    std::vector<uint8_t> stack, globals, frameGlobals, displayGlobals, pacingGlobals;
};
Expected state(Reader& reader, unsigned stackLength, bool display = false, bool pacing = false) {
    DosGetTimeRegisters r;
    r.ax = reader.word(); r.bx = reader.word(); r.cx = reader.word(); r.dx = reader.word();
    r.si = reader.word(); r.di = reader.word(); r.bp = reader.word(); r.cs = reader.word();
    r.ds = reader.word(); r.es = reader.word(); r.ss = reader.word(); r.sp = reader.word(); r.ip = reader.word();
    r.flags = reader.number(4);
    const auto mask = reader.number(4), ticks = reader.number(4), pspStack = reader.number(4);
    const auto motor = static_cast<uint8_t>(reader.number(1)), drive = static_cast<uint8_t>(reader.number(1));
    const auto io = reader.number(4);
    return {r, mask, ticks, pspStack, io, motor, drive, reader.take(stackLength), reader.take(10), reader.take(11),
        display ? reader.take(5) : std::vector<uint8_t>{}, pacing ? reader.take(9) : std::vector<uint8_t>{}};
}
void seedGlobals(Memory& memory, uint16_t data, const std::vector<uint8_t>& globals, bool legacy) {
    if (legacy) { memory.seed(data, 0x79c4, {0}, true); return; }
    unsigned index = 0;
    for (auto [offset, count] : {std::pair{0x78c0, 2}, std::pair{0x79a0, 3}, std::pair{0x79c0, 5}}) {
        memory.seed(data, static_cast<uint16_t>(offset),
            {globals.begin() + index, globals.begin() + index + count}, true);
        index += count;
    }
}
using ClockCases = std::vector<std::vector<PicWorkClockSnapshot>>;
using DeviceClockCases = std::vector<std::vector<PacingDeviceClockSnapshot>>;
template<class Snapshot = PicWorkClockSnapshot>
std::vector<std::vector<Snapshot>> readClocks(Reader reader) {
    constexpr bool Devices = std::is_same_v<Snapshot, PacingDeviceClockSnapshot>;
    require(reader.take(8) == (Devices ? std::vector<uint8_t>({'L','Z','P','D','C','L','0','1'}) :
        std::vector<uint8_t>({'L','Z','P','C','L','K','0','1'})), "clock version differs");
    const auto count = reader.number(4);
    require(count > 0 && count <= 8, "clock case domain differs");
    std::vector<std::vector<Snapshot>> result;
    for (unsigned c = 0; c < count; ++c) {
        const auto stateCount = reader.number(4);
        require(stateCount >= (Devices ? 16u : 326u) && stateCount <= (Devices ? 250001u : 4097u), "clock state domain differs");
        std::vector<Snapshot> states;
        for (unsigned i = 0; i < stateCount; ++i) {
            Snapshot observed;
            auto& state = [&]() -> PicWorkClockSnapshot& {
                if constexpr (Devices) return observed.clock;
                else return observed;
            }();
            state.cycles = std::bit_cast<int64_t>(reader.wide());
            state.cycleLeft = std::bit_cast<int64_t>(reader.wide());
            state.ioDelayRemoved = std::bit_cast<int64_t>(reader.wide());
            state.ticks = reader.wide();
            reader.take(14); // Observed flags, CS:IP and opcode/I/O metadata are not scheduler inputs.
            state.activeLines = reader.word(); state.maskedLines = reader.word();
            state.inserviceLines = reader.word(); state.pending = reader.word();
            state.activeIrq = static_cast<uint8_t>(reader.number(1));
            state.irq0Vector = static_cast<uint8_t>(reader.number(1));
            state.special = reader.number(1) != 0; state.autoEoi = reader.number(1) != 0;
            state.pitDelay = std::bit_cast<float>(reader.number(4));
            state.pitStart = std::bit_cast<double>(reader.wide());
            state.pitCount = reader.number(4); state.pitMode = static_cast<uint8_t>(reader.number(1));
            state.pitUpdate = reader.number(1) != 0;
            const auto events = reader.word(); require(events <= 64, "clock queue cap differs");
            for (unsigned e = 0; e < events; ++e) {
                const auto index = std::bit_cast<float>(reader.number(4));
                const auto kind = static_cast<PicClockEventKind>(reader.number(1));
                state.queue.push_back({index, kind, reader.wide()});
            }
            if constexpr (Devices) {
                for (auto& value : observed.devices) value = reader.wide();
                for (auto& value : observed.delayBits) value = reader.wide();
                const auto tickers = reader.number(1); require(tickers <= 16, "ticker scope differs");
                for (unsigned t = 0; t < tickers; ++t) observed.tickers.push_back(static_cast<uint8_t>(reader.number(1)));
            }
            states.push_back(std::move(observed));
        }
        result.push_back(std::move(states));
    }
    require(reader.cursor == reader.bytes.size(), "clock projection tail differs");
    return result;
}
void compareClock(const PicWorkClock& operation, const PicWorkClockSnapshot& expected, const std::string& context) {
    const auto& actual = operation.snapshot();
    require(actual.cycles == expected.cycles && actual.cycleLeft == expected.cycleLeft &&
        actual.ioDelayRemoved == expected.ioDelayRemoved && actual.ticks == expected.ticks,
        context + " coupled CPU budget or I/O cost differs");
    require(actual.activeLines == expected.activeLines && actual.maskedLines == expected.maskedLines &&
        actual.inserviceLines == expected.inserviceLines && actual.pending == expected.pending &&
        actual.activeIrq == expected.activeIrq && actual.irq0Vector == expected.irq0Vector &&
        actual.special == expected.special && actual.autoEoi == expected.autoEoi,
        context + " coupled IRQ eligibility differs");
    require(std::bit_cast<uint32_t>(actual.pitDelay) == std::bit_cast<uint32_t>(expected.pitDelay) &&
        std::bit_cast<uint64_t>(actual.pitStart) == std::bit_cast<uint64_t>(expected.pitStart),
        context + " coupled PIT phase differs");
    require(actual.pitCount == expected.pitCount && actual.pitMode == expected.pitMode &&
        actual.pitUpdate == expected.pitUpdate, context + " coupled PIT configuration differs");
    require(actual.queue.size() == expected.queue.size(), context + " coupled queue length differs");
    for (unsigned i = 0; i < actual.queue.size(); ++i)
        require(std::bit_cast<uint32_t>(actual.queue[i].index) == std::bit_cast<uint32_t>(expected.queue[i].index) &&
            actual.queue[i].kind == expected.queue[i].kind && actual.queue[i].value == expected.queue[i].value,
            context + " coupled queue event differs");
}
template<class Operation = InterruptibleFrameClockOperation, class Clock = PicWorkClock>
std::size_t original(Reader reader, const std::conditional_t<std::is_same_v<Clock, PacingDeviceClock>, DeviceClockCases, ClockCases>& clocks = {}) {
    constexpr bool DeviceClock = std::is_same_v<Clock, PacingDeviceClock>;
    constexpr bool ThroughPacing = std::is_same_v<Operation, FramePacingOperation>;
    constexpr bool ThroughDisplay = ThroughPacing || std::is_same_v<Operation, FramePacingCalculationOperation>;
    require(reader.take(8) == (ThroughPacing ? std::vector<uint8_t>({'L','Z','F','P','A','C','0','1'}) :
        ThroughDisplay ? std::vector<uint8_t>({'L','Z','F','D','S','P','0','1'}) :
        std::vector<uint8_t>({'L','Z','F','C','L','K','0','1'})), "projection version differs");
    const auto count = reader.number(4);
    require(count > 0 && count <= 256, "case domain differs");
    require(clocks.empty() || clocks.size() == count, "CPU/clock case count differs");
    if constexpr (ThroughPacing && !DeviceClock) require(clocks.empty(), "observed-IRQ mode has no coupled clock proof");
    else require(!clocks.empty(), "independent PIC projection required");
    std::size_t comparisons = 0, delivered = 0, predicted = 0;
    for (unsigned caseIndex = 0; caseIndex < count; ++caseIndex) {
        const auto game = reader.word(), base = reader.word(), psp = reader.word(), ss = reader.word();
        const auto entrySp = reader.word(), stackBase = reader.word(), stackLength = reader.word();
        const auto bankSegment = reader.word(), bankOffset = reader.word(), bankLength = reader.word();
        const auto vectorIp = reader.word(), vectorCs = reader.word();
        const bool legacy = reader.number(1) != 0;
        const auto stateCount = reader.number(4), ioCount = reader.number(4), irqCount = reader.number(4);
        require(stateCount >= 16 && stateCount <= (ThroughPacing ? 250001u : 4097u), "CPU state domain differs");
        require(!ThroughPacing || !legacy, "full pacing requires fixed-stack evidence");
        require(stackLength == (legacy ? 64 : 128), "stack scope differs");
        std::vector<uint32_t> deliveries;
        for (unsigned i = 0; i < irqCount; ++i) deliveries.push_back(reader.number(4));
        const auto bank = reader.take(bankLength);
        std::vector<Expected> states;
        for (unsigned i = 0; i < stateCount; ++i) states.push_back(state(reader, stackLength, ThroughDisplay, ThroughPacing));
        std::vector<Io> io;
        for (unsigned i = 0; i < ioCount; ++i) {
            const bool output = reader.number(1) != 0; const auto port = reader.word();
            io.emplace_back(output, port, static_cast<uint8_t>(reader.number(1)));
        }
        for (bool restore : {false, true}) {
            std::optional<Clock> clock;
            if (!clocks.empty()) {
                require(clocks[caseIndex].size() == stateCount, "CPU/clock state count differs");
                clock.emplace(clocks[caseIndex].front());
            }
            Memory memory; memory.script = io;
            memory.seed(bankSegment, bankOffset, bank);
            memory.seed(ss, legacy ? entrySp : stackBase, states[0].stack, true);
            if (legacy) for (unsigned i = 0; i < 80; ++i)
                memory.writable[Memory::address(ss, static_cast<uint16_t>(entrySp - 80 + i))] = 1;
            seedGlobals(memory, static_cast<uint16_t>(game + 0xaa2), states[0].globals, legacy);
            memory.seedNumber(0, 0x70, uint32_t{vectorIp} | (uint32_t{vectorCs} << 16), 4);
            memory.seedNumber(0x40, 0x6c, states[0].ticks, 4, true);
            memory.seedNumber(0x40, 0x40, states[0].motor, 1, true);
            memory.seedNumber(0x40, 0x3f, states[0].drive, 1, true);
            memory.seedNumber(psp, 0x2e, states[0].pspStack, 4, true);
            const auto data = static_cast<uint16_t>(game + 0xaa2);
            memory.seed(data, 0x2074, {states[0].frameGlobals.begin(), states[0].frameGlobals.begin() + 2}, true);
            memory.seed(data, 0x79a4, {states[0].frameGlobals.begin() + 2, states[0].frameGlobals.end()}, true);
            if constexpr (ThroughDisplay) {
                memory.seed(data, 0x78c6, {states[0].displayGlobals.begin(), states[0].displayGlobals.begin() + 4});
                memory.seed(data, 0x79b5, {states[0].displayGlobals[4]}, true);
            }
            if constexpr (ThroughPacing) {
                memory.seedNumber(0, 0x84, uint32_t{base} | (uint32_t{0xf000} << 16), 4);
                const auto& bytes = states[0].pacingGlobals;
                memory.seed(data, 0x78c2, {bytes.begin(), bytes.begin()+2}, true);
                memory.seed(data, 0x78ca, {bytes.begin()+2, bytes.begin()+6}, true);
                memory.seed(data, 0x7f68, {bytes.begin()+6, bytes.begin()+8});
                memory.seedNumber(0x40, 0, bytes[8], 1);
            }
            Operation operation(states[0].registers, base, psp, game, 0x200000);
            PicWorkClock* workClock = nullptr;
            if (clock) {
                if constexpr (DeviceClock) workClock = &clock->workClock();
                else workClock = &*clock;
            }
            const auto bus = memory.bus(workClock);
            for (unsigned step = 0; step < stateCount; ++step) {
                if (!clock && std::find(deliveries.begin(), deliveries.end(), step) != deliveries.end())
                    operation.deliverTimerInterrupt(bus);
                const auto& expected = states[step];
                auto actual = operation.registers(), wanted = expected.registers;
                const auto context = "case=" + std::to_string(caseIndex) + " state=" + std::to_string(step);
                if (clock) {
                    if constexpr (DeviceClock) {
                        const auto snapshot = clock->snapshot();
                        const auto& expectedClock = clocks[caseIndex][step];
                        compareClock(clock->workClock(), expectedClock.clock, context);
                        require(snapshot.devices == expectedClock.devices && snapshot.delayBits == expectedClock.delayBits &&
                            snapshot.tickers == expectedClock.tickers, context + " clock-device state differs");
                    } else compareClock(*clock, clocks[caseIndex][step], context);
                }
                require(((actual.flags ^ wanted.flags) & expected.mask) == 0, context + " defined flags differ");
                actual.flags = wanted.flags = 0;
                require(actual == wanted, context + " registers differ");
                require(memory.read(0x40, 0x6c, 4) == expected.ticks && memory.read(psp, 0x2e, 4) == expected.pspStack,
                        context + " shared clock or PSP differs");
                require(memory.io == expected.io, context + " I/O count differs");
                if (!legacy) require(memory.read(0x40, 0x40, 1) == expected.motor &&
                    memory.read(0x40, 0x3f, 1) == expected.drive, context + " BIOS disk bytes differ");
                for (unsigned i = 0; i < stackLength; ++i) {
                    const auto at = Memory::address(ss, legacy ? expected.registers.sp : stackBase, i);
                    if (memory.known[at]) require(memory.bytes[at] == expected.stack[i], context + " stack differs");
                }
                if (!legacy) {
                    unsigned index = 0;
                    for (auto [offset, length] : {std::pair{0x78c0,2}, std::pair{0x79a0,3}, std::pair{0x79c0,5}})
                        for (int i = 0; i < length; ++i) require(memory.read(static_cast<uint16_t>(game + 0xaa2),
                            static_cast<uint16_t>(offset + i), 1) == expected.globals[index++], context + " sound memory differs");
                }
                for (unsigned i = 0; i < 11; ++i)
                    require(memory.read(data, static_cast<uint16_t>(i < 2 ? 0x2074 + i : 0x79a4 + i - 2), 1) ==
                            expected.frameGlobals[i], context + " foreground clock memory differs");
                if constexpr (ThroughDisplay) for (unsigned i = 0; i < 5; ++i)
                    require(memory.read(data, static_cast<uint16_t>(i < 4 ? 0x78c6 + i : 0x79b5), 1) ==
                        expected.displayGlobals[i], context + " display calculation memory differs");
                if constexpr (ThroughPacing) {
                    const auto& bytes = expected.pacingGlobals;
                    for (unsigned i = 0; i < 8; ++i)
                        require(memory.read(data, static_cast<uint16_t>(i < 2 ? 0x78c2+i : i < 6 ? 0x78ca+i-2 : 0x7f68+i-6), 1) ==
                            bytes[i], context + " pacing memory differs");
                    require(memory.read(0x40, 0, 1) == bytes[8], context + " calibration BIOS byte differs");
                }
                ++comparisons;
                const auto before = operation.snapshot();
                require(operation.advance(0, bus) == 0 && operation.snapshot() == before, "zero budget changed state");
                if (step + 1 < stateCount) {
                    const auto beforeRegisters = operation.registers();
                    const bool callback = beforeRegisters.cs == 0xf000 &&
                        (operation.interruptInProgress() ? beforeRegisters.ip == 0xfea5 : beforeRegisters.ip == base + 1u);
                    const bool iret = operation.interruptInProgress() ?
                        (beforeRegisters.cs == 0xf000 && beforeRegisters.ip == 0xfeb6) ||
                        (beforeRegisters.cs == game && beforeRegisters.ip == 0x1090) :
                        beforeRegisters.ip == base + 14u;
                    require(operation.advance(1, bus) == 1, "dispatch budget differs");
                    if (clock) {
                        const auto flags = operation.registers().flags;
                        const bool sti = beforeRegisters.cs == 0xf000 && beforeRegisters.ip == base;
                        const bool picExit = (iret || sti) && (flags & 0x200u) && workClock->snapshot().pending;
                        auto boundary = clock->nextDispatch(callback || picExit, flags);
                        while (boundary.kind == PicClockBoundaryKind::NeedMillisecond) {
                            clock->grantMillisecond();
                            boundary = clock->nextDispatch(false, flags);
                        }
                        require(boundary.kind == PicClockBoundaryKind::Ready, context + " unsupported device or IRQ producer");
                        if (boundary.timerDelivered) {
                            operation.deliverTimerInterrupt(bus);
                            ++predicted;
                        }
                    }
                }
                if (restore) {
                    operation = Operation(operation.snapshot());
                    if (clock) *clock = Clock(clock->snapshot());
                }
            }
            require(operation.returned() && operation.advance(1, bus) == 0 && memory.io == ioCount, "terminal state differs");
            const auto& snapshot = operation.snapshot();
            if constexpr (ThroughPacing) {
                require(snapshot.calculation && snapshot.delay && snapshot.dispatchedInstructions == stateCount - 1,
                    "full pacing work or delay terminal differs");
                const auto& calculation = *snapshot.calculation;
                require(calculation.elapsed.dos.dos.dispatchedInstructions == 325 && calculation.elapsed.frame &&
                    calculation.elapsed.frame->dispatchedInstructions == 29 && calculation.display &&
                    snapshot.gateInstructions + calculation.dispatchedInstructions + snapshot.feedbackInstructions +
                        snapshot.delay->dispatchedInstructions + snapshot.timerInstructions == snapshot.dispatchedInstructions,
                    "full pacing instruction composition differs");
                require(snapshot.timerDeliveries + calculation.elapsed.timerDeliveries + calculation.display->timerDeliveries == irqCount,
                    "full pacing observed IRQ count differs");
            } else {
                const auto& elapsed = [&]() -> const InterruptibleFrameClockSnapshot& {
                    if constexpr (ThroughDisplay) return snapshot.elapsed;
                    else return snapshot;
                }();
                uint64_t timerDeliveries = elapsed.timerDeliveries;
                if constexpr (ThroughDisplay) {
                    require(snapshot.display && snapshot.display->display.outcome == FrameDisplayOutcome::Returned &&
                        elapsed.dispatchedInstructions + snapshot.display->dispatchedInstructions == snapshot.dispatchedInstructions,
                        "DOS/elapsed/display work composition differs");
                    timerDeliveries += snapshot.display->timerDeliveries;
                }
                require(elapsed.dos.dos.dispatchedInstructions == 325 &&
                    elapsed.frame && elapsed.frame->dispatchedInstructions == 29 &&
                    snapshot.dispatchedInstructions == stateCount - 1 && timerDeliveries == irqCount,
                    "shared work accounting differs");
            }
        }
        delivered += irqCount;
    }
    require(reader.cursor == reader.bytes.size(), "projection tail differs");
    std::cout << (ThroughPacing ? "frame_pacing_original=ok cases=" : ThroughDisplay ? "frame_pacing_calculation_original=ok cases=" : "frame_clock_original=ok cases=")
              << count << " comparisons=" << comparisons
              << " delivered_irqs=" << delivered << " irq_instructions_skipped=0 output_state_injected=0 scheduler_claim=0"
              << " coupled_clock=" << !clocks.empty() << " predicted_irqs=" << predicted
              << " later_cpu_flags_injected=0 whole_game_clock_claim=0\n";
    if constexpr (ThroughPacing) std::cout << "observed_irq_boundaries_external=" << !DeviceClock
        << " irq_eligibility_claim=" << DeviceClock << "\n";
    return comparisons;
}
void unit() {
    for (unsigned boundary = 0; boundary < 325; ++boundary) {
        Memory memory; memory.checkIo = false;
        constexpr uint16_t ss = 0x8000, sp = 0xfe00, game = 0x1000, psp = 0x0ff0;
        memory.seed(ss, static_cast<uint16_t>(sp - 80), std::vector<uint8_t>(128), true);
        memory.write(ss, sp, 0x100, 2); memory.write(ss, sp + 2, 0x9000, 2); memory.write(ss, sp + 4, 0x202, 2);
        memory.seedNumber(0, 0x70, 0x10000fbe, 4);
        memory.seedNumber(0x40, 0x6c, 0xffffffff, 4, true);
        memory.seedNumber(0x40, 0x40, 2, 1, true); memory.seedNumber(0x40, 0x3f, 0xa5, 1, true);
        memory.seedNumber(psp, 0x2e, 0, 4, true);
        memory.seed(game + 0xaa2, 0x79c4, {0}, true);
        DosGetTimeRegisters r; r.ax = 0x2c00; r.cs = 0xf000; r.ip = 0x1001; r.ss = ss; r.sp = sp;
        InterruptibleDosTimeOperation operation(r, 0x1000, psp, game, 0x200000);
        const auto bus = memory.bus();
        require(operation.advance(boundary, bus) == boundary, "pre-IRQ work differs");
        operation.deliverTimerInterrupt(bus);
        const auto interrupted = operation.snapshot();
        bool rejected = false;
        try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { rejected = true; }
        require(rejected && operation.snapshot() == interrupted, "nested timer was accepted");
        require(operation.advance(1000, bus) == 361 - boundary && operation.returned(), "composed return work differs");
        const auto result = operation.registers();
        const auto time = dosTimeFromBiosTicks(boundary == 0 ? 0 : 0xffffffff);
        require(result.cx == ((uint16_t{time.hour} << 8) | time.minute) &&
                result.dx == ((uint16_t{time.second} << 8) | time.hundredth), "DOS resampled the IRQ-updated clock");
        require(memory.read(0x40, 0x6c, 4) == 0 && memory.read(0x40, 0x40, 1) == 1 &&
                memory.read(0x40, 0x3f, 1) == 0xa0, "IRQ clock wrap or BIOS side effects differ");
        require(result.ip == 0x100 && result.cs == 0x9000 && result.sp == sp + 6 &&
                operation.snapshot().timerInstructions == 36 && operation.snapshot().timerDeliveries == 1,
                "interrupted CPU context or work differs");
        rejected = false;
        try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { rejected = true; }
        require(rejected, "timer accepted after completed DOS service");
    }
    std::cout << "interruptible_dos_time_unit=ok boundaries=325 shared_counter=1 sampled_once=1 irq_executed=1 scheduler_claim=0\n";
}

void edges() {
    for (bool active : {false, true}) for (bool beforeSample : {false, true}) {
        Memory memory; memory.checkIo = false;
        constexpr uint16_t ss = 0x8000, game = 0x1000, psp = 0x0ff0;
        memory.seed(ss, 0xffb0, std::vector<uint8_t>(128), true);
        memory.write(ss, 0, 0x100, 2); memory.write(ss, 2, 0x9000, 2); memory.write(ss, 4, 0x202, 2);
        memory.seedNumber(0, 0x70, 0x10000fbe, 4);
        memory.seedNumber(0x40, 0x6c, 100, 4, true);
        memory.seedNumber(0x40, 0x40, 0, 1, true); memory.seedNumber(0x40, 0x3f, 0, 1, true);
        memory.seedNumber(psp, 0x2e, 0, 4, true);
        std::vector<uint8_t> globals(10);
        globals[0] = 0x61; globals[1] = 0xea; globals[9] = active ? 1 : 0;
        seedGlobals(memory, game + 0xaa2, globals, false);
        DosGetTimeRegisters r; r.ax = 0x2c00; r.cs = 0xf000; r.ip = 0x1001; r.ss = ss;
        InterruptibleDosTimeOperation operation(r, 0x1000, psp, game, 0x200000);
        const auto bus = memory.bus();
        const unsigned dosWork = beforeSample ? 0 : 1;
        operation.advance(dosWork, bus);
        for (unsigned irq = 0; irq < 2; ++irq) {
            operation.deliverTimerInterrupt(bus);
            while (operation.interruptInProgress()) {
                require(operation.advance(1, bus) == 1, "wrapped IRQ did not advance");
                operation = InterruptibleDosTimeOperation(operation.snapshot());
            }
        }
        operation.advance(1000, bus);
        const auto result = operation.registers();
        const auto time = dosTimeFromBiosTicks(beforeSample ? 102 : 100);
        require(operation.returned() && result.sp == 6 && result.ip == 0x100 && result.cs == 0x9000 &&
                result.cx == ((uint16_t{time.hour} << 8) | time.minute) &&
                result.dx == ((uint16_t{time.second} << 8) | time.hundredth), "wrapped/repeated IRQ sampled clock differs");
        require(memory.read(0x40, 0x6c, 4) == 102 && memory.read(psp, 0x2e, 4) == 0x8000ffee &&
                memory.read(game + 0xaa2, 0x79c4, 1) == 0 &&
                operation.snapshot().timerDeliveries == 2 && operation.snapshot().dos.dispatchedInstructions == 325,
                "repeated IRQ lost shared state or PSP ownership");
        if (!active) require(operation.snapshot().timerInstructions == 72, "idle IRQ work differs");

        r.flags &= ~uint32_t{0x200};
        InterruptibleDosTimeOperation masked(r, 0x1000, psp, game, 0x200000);
        const auto oldState = masked.snapshot();
        const auto oldMemory = memory.bytes;
        bool rejected = false;
        try { masked.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { rejected = true; }
        require(rejected && masked.snapshot() == oldState && memory.bytes == oldMemory,
                "masked IRQ changed CPU or memory");
    }
    std::cout << "interruptible_dos_time_edges=ok wrapped_stack=1 repeated_irq=1 active_sound=1 masked_irq_rejected=1\n";
}

void foregroundEdges() {
    for (unsigned boundary = 0; boundary <= 29; ++boundary) {
        Memory memory; memory.checkIo = false;
        constexpr uint16_t ss = 0x8000, sp = 0xfe00, game = 0x1000, data = 0x1aa2, psp = 0x0ff0;
        memory.seed(ss, sp - 80, std::vector<uint8_t>(128), true);
        memory.write(ss, sp, 0x791e, 2); memory.write(ss, sp + 2, game, 2); memory.write(ss, sp + 4, 0x202, 2);
        memory.seedNumber(0, 0x70, 0x10000fbe, 4);
        memory.seedNumber(0x40, 0x6c, 100, 4, true);
        memory.seedNumber(0x40, 0x40, 2, 1, true); memory.seedNumber(0x40, 0x3f, 0xa5, 1, true);
        memory.seedNumber(psp, 0x2e, 0, 4, true);
        memory.seedNumber(data, 0x79c4, 0, 1, true);
        memory.seedNumber(data, 0x2074, 0x1234, 2, true);
        memory.seed(data, 0x79a4, {37, 0, 0, 0, 99, 250, 0, 0, 0}, true);
        DosGetTimeRegisters r; r.ax = 0x2c00; r.cs = 0xf000; r.ip = 0x1001; r.ss = ss; r.sp = sp; r.ds = data;
        InterruptibleFrameClockOperation operation(r, 0x1000, psp, game, 0x200000);
        const auto bus = memory.bus();
        require(operation.advance(325, bus) == 325 && operation.registers().ip == 0x791e && !operation.returned(),
                "DOS IRET did not enter the foreground timing caller");
        require(operation.advance(boundary, bus) == boundary, "foreground boundary differs");
        operation.deliverTimerInterrupt(bus);
        const auto interrupted = operation.snapshot();
        bool rejected = false;
        try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { rejected = true; }
        require(rejected && operation.snapshot() == interrupted, "nested foreground IRQ was accepted");
        while (!operation.returned()) {
            require(operation.advance(1, bus) == 1, "foreground IRQ did not advance");
            operation = InterruptibleFrameClockOperation(operation.snapshot());
        }
        const auto time = dosTimeFromBiosTicks(100);
        const auto elapsed = static_cast<uint16_t>((int32_t{time.minute} - 37) * 6000 +
            (int32_t{time.second} - 99) * 100 + int32_t{time.hundredth} - 250);
        require(operation.registers().ip == 0x7966 && operation.registers().sp == sp + 6 &&
            memory.read(data, 0x2074, 2) == elapsed && operation.registers().ax == elapsed,
            "foreground elapsed store or balanced stack differs");
        require(memory.read(0x40, 0x6c, 4) == 101 && operation.snapshot().timerDeliveries == 1 &&
            operation.snapshot().dispatchedInstructions == 390 &&
            operation.snapshot().frame->dispatchedInstructions == 29,
            "post-DOS IRQ work or shared BIOS tick differs");
    }
    std::cout << "frame_clock_edges=ok foreground_boundaries=30 post_dos_irq=1 sampled_once=1 snapshot_restore=1\n";
}
void elapsedOracle(Reader reader) {
    require(reader.take(8)==std::vector<uint8_t>({'L','Z','F','E','L','0','0','1'}), "elapsed oracle version differs");
    const auto count=reader.number(4);
    const auto cs=reader.word(),ds=reader.word(),ss=reader.word(),base=reader.word(),length=reader.word();
    require(count==3375 && cs==0x1000 && ds==0x1aa2 && ss==0x8000 && length==128,"elapsed oracle domain differs");
    const auto registers = [&] {
        DosGetTimeRegisters r;
        r.ax=reader.word();r.bx=reader.word();r.cx=reader.word();r.dx=reader.word();
        r.si=reader.word();r.di=reader.word();r.bp=reader.word();r.cs=reader.word();
        r.ds=reader.word();r.es=reader.word();r.ss=reader.word();r.sp=reader.word();r.ip=reader.word();
        r.flags=reader.number(4);return r;
    };
    for(unsigned index=0;index<count;++index) {
        const auto input=registers();const auto before=reader.take(11),stack=reader.take(length);
        const auto expected=registers();const auto after=reader.take(11),endStack=reader.take(length);
        for(bool restore:{false,true}) {
            Memory memory;memory.checkIo=false;
            memory.seed(ss,base,stack,true);
            memory.seed(ds,0x2074,{before.begin(),before.begin()+2},true);
            memory.seed(ds,0x79a4,{before.begin()+2,before.end()},true);
            FrameElapsedOperation operation(input,cs);
            const auto bus=memory.bus();
            while(!operation.returned()) {
                require(operation.advance(1,bus)==1,"elapsed oracle did not advance");
                if(restore) operation=FrameElapsedOperation(operation.snapshot());
            }
            require(operation.snapshot().registers==expected && operation.snapshot().dispatchedInstructions==29,
                "elapsed oracle CPU differs case="+std::to_string(index));
            for(unsigned i=0;i<11;++i)
                require(memory.read(ds,static_cast<uint16_t>(i<2?0x2074+i:0x79a4+i-2),1)==after[i],"elapsed oracle memory differs");
            for(unsigned i=0;i<length;++i)
                require(memory.read(ss,static_cast<uint16_t>(base+i),1)==endStack[i],"elapsed oracle stack differs");
        }
    }
    require(reader.cursor==reader.bytes.size(),"elapsed oracle tail differs");
    std::cout<<"frame_elapsed_oracle=ok cases="<<count<<" comparisons="<<count*2
        <<" instructions=29 original_calls_stubbed=0 cpu_flags_full_final=1 natural_gameplay_claim=0\n";
}
}
int main(int argc, char** argv) {
    try {
        unit();
        edges();
        foregroundEdges();
        if (argc == 4 && std::string(argv[1]) == "--device-clock-projection") {
            std::ifstream stream(argv[2], std::ios::binary), clockStream(argv[3], std::ios::binary);
            require(stream.good() && clockStream.good(), "device clock projection missing");
            const auto clocks = readClocks<PacingDeviceClockSnapshot>(Reader{{std::istreambuf_iterator<char>(clockStream),std::istreambuf_iterator<char>()}});
            original<FramePacingOperation, PacingDeviceClock>(Reader{{std::istreambuf_iterator<char>(stream),std::istreambuf_iterator<char>()}}, clocks);
            return 0;
        }
        if (argc == 3 && std::string(argv[1]) == "--observed-irq-projection") {
            std::ifstream stream(argv[2], std::ios::binary); require(stream.good(), "full pacing projection missing");
            original<FramePacingOperation>(Reader{{std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()}});
            return 0;
        }
        if(argc==3 && std::string(argv[1])=="--oracle") {
            std::ifstream stream(argv[2],std::ios::binary);require(stream.good(),"elapsed oracle missing");
            elapsedOracle(Reader{{std::istreambuf_iterator<char>(stream),std::istreambuf_iterator<char>()}});
            return 0;
        }
        if (argc > 1) {
            require(argc == 2 || argc == 3, "expected CPU projection and optional PIC projection");
            std::ifstream stream(argv[1], std::ios::binary); require(stream.good(), "projection missing");
            ClockCases clocks;
            if (argc == 3) {
                std::ifstream clockStream(argv[2], std::ios::binary); require(clockStream.good(), "clock projection missing");
                clocks = readClocks(Reader{{std::istreambuf_iterator<char>(clockStream), std::istreambuf_iterator<char>()}});
            }
            Reader reader{{std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()}};
            const std::vector<uint8_t> displayMagic{'L','Z','F','D','S','P','0','1'};
            if (reader.bytes.size() >= 8 && std::equal(displayMagic.begin(), displayMagic.end(), reader.bytes.begin()))
                original<FramePacingCalculationOperation>(std::move(reader), clocks);
            else original(std::move(reader), clocks);
        }
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
