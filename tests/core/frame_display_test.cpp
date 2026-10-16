#include "core/interruptible_frame_display.hpp"
#include "core/frame_pacing_calculation.hpp"
#include "core/frame_pacing_operation.hpp"

#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace lezac::core;

namespace {
void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}
struct Reader {
    std::ifstream stream;
    explicit Reader(const char* path) : stream(path, std::ios::binary) { require(stream.good(), "projection missing"); }
    uint32_t number(unsigned bytes) {
        uint32_t value = 0;
        for (unsigned i = 0; i < bytes; ++i) {
            const auto byte = stream.get(); require(byte >= 0, "projection truncated");
            value |= static_cast<uint32_t>(byte) << (i * 8);
        }
        return value;
    }
    uint16_t word() { return static_cast<uint16_t>(number(2)); }
    uint64_t wide() {
        const uint64_t low = number(4);
        return low | (uint64_t{number(4)} << 32);
    }
    void magic(const std::string& expected) {
        for (const char byte : expected) require(stream.get() == byte, "projection version differs");
    }
    template<std::size_t N> std::array<uint8_t, N> bytes() {
        std::array<uint8_t, N> result;
        for (auto& value : result) value = static_cast<uint8_t>(number(1));
        return result;
    }
    void end() { require(stream.get() < 0, "projection tail differs"); }
};
struct State {
    DosGetTimeRegisters registers;
    uint32_t mask;
    std::array<uint8_t, 128> stack;
    std::array<uint8_t, 5> globals;
};
State readState(Reader& input) {
    DosGetTimeRegisters r;
    r.ax = input.word(); r.bx = input.word(); r.cx = input.word(); r.dx = input.word();
    r.si = input.word(); r.di = input.word(); r.bp = input.word(); r.cs = input.word();
    r.ds = input.word(); r.es = input.word(); r.ss = input.word(); r.sp = input.word(); r.ip = input.word();
    r.flags = input.number(4);
    return {r, input.number(4), input.bytes<128>(), input.bytes<5>()};
}
DosGetTimeRegisters initial(unsigned index) {
    return {0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x9abc, 0x1000, 0x1aa2, 0xbeef,
        0x8000, 0xfe06, 0x7966, 0x202u | (index % 3 == 0 ? 0x400u : 0u) | (index % 2 ? 0x8d5u : 0u)};
}
struct Memory {
    std::array<uint8_t, 128> stack{};
    std::array<uint8_t, 5> globals{};
    std::array<uint8_t, 11> timing{};
    std::array<uint8_t, 8> pacing{};
    uint8_t com1 = 0xf8;
    uint32_t ticks = 100;
    uint32_t pspStack = 0;
    uint8_t motor = 2, drive = 0xa5, port61 = 0, latch = 0;
    uint16_t base = 0xfdb6;
    explicit Memory(uint16_t denominator, uint16_t numerator, unsigned index) {
        for (unsigned i = 0; i < stack.size(); ++i) stack[i] = static_cast<uint8_t>(index + i);
        globals = {static_cast<uint8_t>(denominator), static_cast<uint8_t>(denominator >> 8),
            static_cast<uint8_t>(numerator), static_cast<uint8_t>(numerator >> 8), 0x5a};
    }
    uint8_t read(uint16_t segment, uint16_t offset) const {
        if (segment == 0x8000 && static_cast<uint16_t>(offset - base) < stack.size()) return stack[static_cast<uint16_t>(offset - base)];
        if (segment == 0x1aa2 && offset >= 0x78c6 && offset <= 0x78c9) return globals[offset - 0x78c6];
        if (segment == 0x1aa2 && offset == 0x79b5) return globals[4];
        if (segment == 0x1aa2 && offset == 0x79c4) return latch;
        if (segment == 0x1aa2 && offset >= 0x78c2 && offset <= 0x78c3) return pacing[offset - 0x78c2];
        if (segment == 0x1aa2 && offset >= 0x78ca && offset <= 0x78cd) return pacing[offset - 0x78ca + 2];
        if (segment == 0x1aa2 && offset >= 0x7f68 && offset <= 0x7f69) return pacing[offset - 0x7f68 + 6];
        if (segment == 0x40 && offset == 0) return com1;
        if (segment == 0 && offset >= 0x84 && offset <= 0x87) return static_cast<uint8_t>(0xf0001000u >> ((offset - 0x84) * 8));
        if (segment == 0x1aa2 && offset >= 0x79a4 && offset <= 0x79ac) return timing[offset - 0x79a4 + 2];
        if (segment == 0x1aa2 && offset >= 0x2074 && offset <= 0x2075) return timing[offset - 0x2074];
        if (segment == 0x0ff0 && offset >= 0x2e && offset <= 0x31) return static_cast<uint8_t>(pspStack >> ((offset - 0x2e) * 8));
        if (segment == 0 && offset >= 0x70 && offset <= 0x73) return static_cast<uint8_t>(0x10000fbeu >> ((offset - 0x70) * 8));
        if (segment == 0x40 && offset >= 0x6c && offset <= 0x6f) return static_cast<uint8_t>(ticks >> ((offset - 0x6c) * 8));
        if (segment == 0x40 && offset == 0x40) return motor;
        if (segment == 0x40 && offset == 0x3f) return drive;
        throw std::domain_error("read outside declared display/IRQ memory");
    }
    void write(uint16_t segment, uint16_t offset, uint8_t value) {
        if (segment == 0x8000 && static_cast<uint16_t>(offset - base) < stack.size()) stack[static_cast<uint16_t>(offset - base)] = value;
        else if (segment == 0x1aa2 && offset == 0x79b5) globals[4] = value;
        else if (segment == 0x1aa2 && offset == 0x79c4) latch = value;
        else if (segment == 0x1aa2 && offset >= 0x78c2 && offset <= 0x78c3) pacing[offset - 0x78c2] = value;
        else if (segment == 0x1aa2 && offset >= 0x78ca && offset <= 0x78cd) pacing[offset - 0x78ca + 2] = value;
        else if (segment == 0x1aa2 && offset >= 0x79a4 && offset <= 0x79ac) timing[offset - 0x79a4 + 2] = value;
        else if (segment == 0x1aa2 && offset >= 0x2074 && offset <= 0x2075) timing[offset - 0x2074] = value;
        else if (segment == 0x0ff0 && offset >= 0x2e && offset <= 0x31) {
            const auto shift = (offset - 0x2e) * 8;
            pspStack = (pspStack & ~(uint32_t{255} << shift)) | (uint32_t{value} << shift);
        }
        else if (segment == 0x40 && offset >= 0x6c && offset <= 0x6f) {
            const auto shift = (offset - 0x6c) * 8;
            ticks = (ticks & ~(uint32_t{255} << shift)) | (uint32_t{value} << shift);
        } else if (segment == 0x40 && offset == 0x40) motor = value;
        else if (segment == 0x40 && offset == 0x3f) drive = value;
        else throw std::domain_error("write outside declared display/IRQ memory");
    }
    TimerIrqBus bus() {
        return {
            [&](uint16_t s, uint16_t o) { return read(s, o); },
            [&](uint16_t s, uint16_t o) { return static_cast<uint16_t>(read(s, o) | (uint16_t{read(s, static_cast<uint16_t>(o + 1u))} << 8)); },
            [&](uint16_t s, uint16_t o) { uint32_t v = 0; for (unsigned i = 0; i < 4; ++i) v |= uint32_t{read(s, static_cast<uint16_t>(o + i))} << (8 * i); return v; },
            [&](uint16_t s, uint16_t o, uint8_t v) { write(s, o, v); },
            [&](uint16_t s, uint16_t o, uint16_t v) { for (unsigned i = 0; i < 2; ++i) write(s, static_cast<uint16_t>(o + i), static_cast<uint8_t>(v >> (8 * i))); },
            [&](uint16_t s, uint16_t o, uint32_t v) { for (unsigned i = 0; i < 4; ++i) write(s, static_cast<uint16_t>(o + i), static_cast<uint8_t>(v >> (8 * i))); },
            [&](uint16_t port) { require(port == 0x61, "unexpected IRQ input port"); return port61; },
            [&](uint16_t port, uint8_t value) { require(port == 0x20 || port == 0x61, "unexpected IRQ output port"); if (port == 0x61) port61 = value; }
        };
    }
};
void compare(const FrameDisplayOperation& operation, const Memory& memory, State expected, const std::string& context) {
    auto actual = operation.snapshot().registers;
    require(((actual.flags ^ expected.registers.flags) & expected.mask) == 0, context + " defined CPU flags differ");
    actual.flags = expected.registers.flags = 0;
    require(actual == expected.registers, context + " CPU registers differ ip=" + std::to_string(actual.ip));
    require(memory.stack == expected.stack && memory.globals == expected.globals, context + " stack or display memory differs");
}
void instructions(const char* path) {
    Reader input(path); input.magic("LZFDIR01");
    const auto count = input.number(4);
    require(count == 256 && input.word() == 0x1000 && input.word() == 0x1aa2 && input.word() == 0x8000 &&
        input.word() == 0xfdb6 && input.word() == 128, "instruction oracle domain differs");
    std::size_t comparisons = 0, runtimeErrors = 0;
    for (unsigned index = 0; index < count; ++index) {
        const auto denominator = input.word(), numerator = input.word();
        const bool error = input.number(1) != 0;
        const auto length = input.number(4); require(length > 0 && length <= 4096, "instruction oracle length differs");
        std::vector<State> states; states.reserve(length);
        for (unsigned i = 0; i < length; ++i) states.push_back(readState(input));
        for (bool restore : {false, true}) {
            Memory memory(denominator, numerator, index);
            FrameDisplayOperation operation(initial(index), 0x1000);
            const auto bus = memory.bus();
            for (unsigned step = 0; step < length; ++step) {
                compare(operation, memory, states[step], "case=" + std::to_string(index) + " state=" + std::to_string(step));
                ++comparisons;
                const auto snapshot = operation.snapshot();
                require(operation.advance(0, bus) == 0 && operation.snapshot() == snapshot, "zero budget changed display state");
                if (step + 1 < length) require(operation.advance(1, bus) == 1, "instruction work differs");
                if (restore) operation = FrameDisplayOperation(operation.snapshot());
            }
            require(operation.finished() && operation.returned() == !error && operation.advance(1, bus) == 0 &&
                operation.snapshot().dispatchedInstructions == length - 1, "display terminal or work differs");
            if (error) require(operation.snapshot().registers.ax == 200 && operation.snapshot().registers.ip == 0xe2,
                "runtime error handoff differs");
        }
        runtimeErrors += error;
    }
    input.end();
    std::cout << "frame_display_instructions=ok cases=" << count << " comparisons=" << comparisons
        << " runtime_error_cases=" << runtimeErrors << " restore_modes=2 natural_gameplay_claim=0\n";
}
void endpoints(const char* path) {
    Reader input(path); input.magic("LZFDEN01");
    const auto count = input.number(4); require(count == 196608, "endpoint oracle domain differs");
    for (unsigned index = 0; index < count; ++index) {
        const auto denominator = input.word(), numerator = input.word();
        require(denominator == std::array<uint16_t, 3>{1, 66, 65535}[index / 65536] && numerator == index % 65536,
            "endpoint input sequence differs");
        const auto expected = readState(input);
        Memory memory(denominator, numerator, numerator);
        FrameDisplayOperation operation(initial(numerator), 0x1000);
        operation.advance(4096, memory.bus());
        require(operation.returned(), "endpoint did not return");
        compare(operation, memory, expected, "endpoint=" + std::to_string(index));
    }
    input.end();
    std::cout << "frame_display_endpoints=ok cases=196608 denominator_profiles=3 numerator_inputs=65536 full_final_flags=1\n";
}
void edges() {
    Memory baseline(148, 120, 0);
    FrameDisplayOperation uninterrupted(initial(0), 0x1000);
    uninterrupted.advance(4096, baseline.bus());
    const auto count = uninterrupted.snapshot().dispatchedInstructions;
    require(count == 653 && baseline.globals[4] == 81, "display edge baseline differs");
    for (unsigned boundary = 0; boundary <= count; ++boundary) {
        Memory memory(148, 120, 0);
        InterruptibleFrameDisplayOperation operation(initial(0), 0x1000, 0x200000);
        const auto bus = memory.bus();
        require(operation.advance(boundary, bus) == boundary, "pre-IRQ display work differs");
        operation.deliverTimerInterrupt(bus);
        const auto interrupted = operation.snapshot();
        bool rejected = false;
        try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { rejected = true; }
        require(rejected && operation.snapshot() == interrupted, "nested display IRQ was accepted");
        while (!operation.finished()) {
            require(operation.advance(1, bus) == 1, "display IRQ did not advance");
            operation = InterruptibleFrameDisplayOperation(operation.snapshot());
        }
        require(operation.returned() && operation.registers() == uninterrupted.snapshot().registers &&
            memory.globals == baseline.globals && memory.ticks == 101 && memory.motor == 1 && memory.drive == 0xa0,
            "interrupted display CPU, globals or BIOS memory differs");
        require(operation.snapshot().timerInstructions == 36 && operation.snapshot().timerDeliveries == 1 &&
            operation.snapshot().dispatchedInstructions == count + 36 &&
            operation.snapshot().display.dispatchedInstructions == count, "interrupted display work differs");
    }
    auto maskedRegisters = initial(0); maskedRegisters.flags &= ~uint32_t{0x200};
    Memory memory(148, 120, 0);
    InterruptibleFrameDisplayOperation masked(maskedRegisters, 0x1000, 0x200000);
    const auto before = masked.snapshot();
    const auto stack = memory.stack;
    bool rejected = false;
    try { masked.deliverTimerInterrupt(memory.bus()); } catch (const std::logic_error&) { rejected = true; }
    require(rejected && masked.snapshot() == before && memory.stack == stack, "masked display IRQ changed state");
    std::cout << "frame_display_edges=ok boundaries=654 irq_executed=1 snapshot_restore=1 masked_irq_rejected=1\n";
}
void composedEdges() {
    auto entry = initial(0);
    entry.ax = 0x2c00; entry.cs = 0xf000; entry.ip = 0x1001; entry.sp = 0xfe00;
    const auto prepare = [&](Memory& memory) {
        const auto bus = memory.bus();
        bus.writeWord(entry.ss, entry.sp, 0x791e);
        bus.writeWord(entry.ss, static_cast<uint16_t>(entry.sp + 2u), 0x1000);
        bus.writeWord(entry.ss, static_cast<uint16_t>(entry.sp + 4u), 0x202);
    };
    std::array<Memory, 2> controls{Memory(148, 120, 0), Memory(148, 120, 0)};
    std::array<DosGetTimeRegisters, 2> expected;
    uint64_t count = 0;
    for (unsigned index = 0; index < controls.size(); ++index) {
        controls[index].ticks += index;
        prepare(controls[index]);
        FramePacingCalculationOperation operation(entry, 0x1000, 0x0ff0, 0x1000, 0x200000);
        operation.advance(4096, controls[index].bus());
        require(operation.returned(), "composed display control did not return");
        expected[index] = operation.registers();
        count = operation.snapshot().dispatchedInstructions;
        require(count == 1007 && controls[index].globals[4] == 81, "composed display control work differs");
    }
    for (unsigned boundary = 0; boundary <= count; ++boundary) {
        Memory memory(148, 120, 0); prepare(memory);
        FramePacingCalculationOperation operation(entry, 0x1000, 0x0ff0, 0x1000, 0x200000);
        const auto bus = memory.bus();
        require(operation.advance(boundary, bus) == boundary, "composed pre-IRQ work differs");
        operation.deliverTimerInterrupt(bus);
        while (!operation.finished()) {
            require(operation.advance(1, bus) == 1, "composed display IRQ did not advance");
            operation = FramePacingCalculationOperation(operation.snapshot());
        }
        const auto profile = boundary == 0 ? 1u : 0u;
        require(operation.returned() && operation.registers() == expected[profile] &&
            memory.globals == controls[profile].globals && memory.timing == controls[profile].timing &&
            memory.pspStack == controls[profile].pspStack && memory.ticks == 101 && memory.motor == 1 && memory.drive == 0xa0,
            "composed IRQ changed sampled clock, display or shared BIOS/PSP state");
        const auto& state = operation.snapshot();
        require(state.dispatchedInstructions == count + 36 && state.display &&
            state.elapsed.timerDeliveries + state.display->timerDeliveries == 1,
            "composed display IRQ work differs");
    }
    std::cout << "frame_pacing_calculation_edges=ok boundaries=1008 irq_executed=1 sampled_once=1 snapshot_restore=1\n";
}
void compareRegisters(DosGetTimeRegisters actual, DosGetTimeRegisters expected, uint32_t mask,
                      const std::string& context) {
    require(((actual.flags ^ expected.flags) & mask) == 0, context + " defined flags differ");
    actual.flags = expected.flags = 0;
    require(actual == expected, context + " registers differ ip=" + std::to_string(actual.ip));
}
DosGetTimeRegisters readRegisters(Reader& input, uint32_t& mask) {
    DosGetTimeRegisters r;
    r.ax = input.word(); r.bx = input.word(); r.cx = input.word(); r.dx = input.word();
    r.si = input.word(); r.di = input.word(); r.bp = input.word(); r.cs = input.word();
    r.ds = input.word(); r.es = input.word(); r.ss = input.word(); r.sp = input.word(); r.ip = input.word();
    r.flags = input.number(4); mask = input.number(4);
    return r;
}
void pacingOracle(const char* path) {
    Reader input(path); input.magic("LZPWAIT1");
    const auto count = input.number(4); require(count == 15, "pacing oracle case domain differs");
    uint64_t comparisons = 0;
    for (unsigned index = 0; index < count; ++index) {
        const auto denominator = input.word(), numerator = input.word();
        const bool error = input.number(1) != 0;
        const auto originalWork = input.wide(); const auto length = input.number(4);
        const auto pacing = input.bytes<8>(); const auto timing = input.bytes<11>();
        require(originalWork < 2000000 && length > 0 && length < 1024, "pacing oracle work domain differs");
        struct Checkpoint {
            uint64_t original, translated;
            State state;
            std::array<uint8_t, 11> timing;
            std::array<uint8_t, 8> pacing;
            uint8_t com1;
            uint32_t psp, ticks;
        };
        std::vector<Checkpoint> checkpoints;
        for (unsigned i = 0; i < length; ++i) {
            const auto original = input.wide(), translated = input.wide();
            auto state = readState(input); const auto expectedTiming = input.bytes<11>();
            const auto expectedPacing = input.bytes<8>(); const auto com1 = static_cast<uint8_t>(input.number(1));
            const auto psp = input.number(4), ticks = input.number(4);
            checkpoints.push_back({original, translated, state, expectedTiming, expectedPacing, com1, psp, ticks});
        }
        const auto counter = static_cast<uint16_t>(pacing[0] | (uint16_t{pacing[1]} << 8));
        const bool due = static_cast<uint16_t>(counter + 1u) % 30 == 0;
        for (bool restore : {false, true}) {
            Memory memory(denominator, numerator, index); memory.pacing = pacing; memory.timing = timing;
            auto entry = initial(index); entry.ip = 0x7903;
            FramePacingOperation operation(entry, 0x1000, 0x0ff0, 0x1000, 0x200000);
            uint64_t previous = 0;
            for (const auto& checkpoint : checkpoints) {
                require(checkpoint.translated == checkpoint.original + (due && checkpoint.original >= 10 ? 326 : 0),
                    "scripted DOS work translation differs");
                require(checkpoint.translated >= previous && checkpoint.translated <= originalWork + 326,
                    "oracle checkpoint order differs");
                const auto work = checkpoint.translated - previous;
                require(operation.advance(work, memory.bus()) == work, "pacing oracle work differs");
                const auto context = "pacing case=" + std::to_string(index) + " position=" + std::to_string(checkpoint.original);
                compareRegisters(operation.registers(), checkpoint.state.registers, checkpoint.state.mask, context);
                require(memory.stack == checkpoint.state.stack, context + " stack differs");
                require(memory.globals == checkpoint.state.globals && memory.timing == checkpoint.timing &&
                    memory.pacing == checkpoint.pacing && memory.com1 == checkpoint.com1 &&
                    memory.pspStack == checkpoint.psp && memory.ticks == checkpoint.ticks, context + " memory differs");
                const auto before = operation.snapshot();
                require(operation.advance(0, memory.bus()) == 0 && operation.snapshot() == before, "pacing zero budget differs");
                if (restore) operation = FramePacingOperation(operation.snapshot());
                previous = checkpoint.translated; ++comparisons;
            }
            require(operation.finished() && operation.returned() == !error &&
                operation.snapshot().dispatchedInstructions == originalWork + (due ? 326 : 0), "pacing oracle terminal differs");
        }
    }
    input.end();
    std::cout << "frame_pacing_oracle=ok cases=15 comparisons=" << comparisons
        << " restore_modes=2 scripted_dos_service=1 natural_gameplay_claim=0\n";
}
void gateOracle(const char* path) {
    Reader input(path); input.magic("LZPGATE1");
    require(input.number(4) == 65536, "gate oracle domain differs");
    for (unsigned counter = 0; counter < 65536; ++counter) {
        require(input.word() == counter, "gate oracle sequence differs");
        const bool due = input.number(1) != 0; const auto work = input.number(1);
        uint32_t mask = 0; const auto expected = readRegisters(input, mask);
        Memory memory(66, 0, counter);
        memory.pacing = {static_cast<uint8_t>(counter), static_cast<uint8_t>(counter >> 8), 0, 0, 0, 0, 1, 0};
        auto entry = initial(counter); entry.ip = 0x7903;
        FramePacingOperation operation(entry, 0x1000, 0x0ff0, 0x1000, 0x200000);
        require(work == (due ? 8u : 9u) && operation.advance(work, memory.bus()) == work, "gate work differs");
        compareRegisters(operation.registers(), expected, mask, "gate counter=" + std::to_string(counter));
        require(static_cast<uint16_t>(memory.pacing[0] | (uint16_t{memory.pacing[1]} << 8)) ==
            static_cast<uint16_t>(counter + 1u), "gate counter wrap differs");
    }
    input.end();
    std::cout << "frame_pacing_gate_oracle=ok counter_inputs=65536 full_endpoint_flags=1\n";
}
void feedbackOracle(const char* path) {
    Reader input(path); input.magic("LZPFEED1");
    require(input.number(4) == 327680, "feedback oracle domain differs");
    const std::array<std::array<uint16_t, 2>, 5> profiles{{{0,0}, {1,2}, {16,2}, {65535,2}, {65535,65535}}};
    for (unsigned index = 0; index < 327680; ++index) {
        const unsigned profile = index / 65536, elapsed = index % 65536;
        require(input.number(1) == profile && input.word() == elapsed, "feedback input sequence differs");
        uint32_t mask = 0; const auto expected = readRegisters(input, mask);
        const auto timing = input.bytes<11>(); const auto delay = input.word();
        const auto [oldDelay, step] = profiles[profile];
        Memory memory(66, 0, elapsed);
        memory.pacing = {0,0,static_cast<uint8_t>(step),static_cast<uint8_t>(step >> 8),
            static_cast<uint8_t>(oldDelay),static_cast<uint8_t>(oldDelay >> 8),1,0};
        memory.timing = {static_cast<uint8_t>(elapsed),static_cast<uint8_t>(elapsed >> 8),17,0xa5,0x5a,0xa5,33,44,59,58,99};
        const auto stack = memory.stack;
        auto entry = initial(elapsed); entry.ip = 0x7903;
        auto snapshot = FramePacingOperation(entry, 0x1000, 0x0ff0, 0x1000, 0x200000).snapshot();
        snapshot.stage = FramePacingStage::FeedbackDelay; snapshot.registers.ip = 0x799a;
        FramePacingOperation operation(snapshot);
        unsigned work = 0;
        while (operation.registers().ip != 0x79df && work++ < 30)
            require(operation.advance(1, memory.bus()) == 1, "feedback did not dispatch");
        require(work < 30, "feedback endpoint not reached");
        compareRegisters(operation.registers(), expected, mask, "feedback input=" + std::to_string(index));
        require(memory.timing == timing && static_cast<uint16_t>(memory.pacing[4] | (uint16_t{memory.pacing[5]} << 8)) == delay &&
            memory.stack == stack, "feedback globals, delay or stack differs");
    }
    input.end();
    std::cout << "frame_pacing_feedback_oracle=ok elapsed_inputs=65536 delay_step_profiles=5 cases=327680 full_endpoint_flags=1\n";
}
void pacingEdges() {
    auto entry = initial(0); entry.ip = 0x7903;
    std::array<Memory, 2> controls{Memory(148, 120, 0), Memory(148, 120, 0)};
    std::array<DosGetTimeRegisters, 2> expected;
    uint64_t count = 0;
    for (unsigned index = 0; index < controls.size(); ++index) {
        controls[index].pacing[0] = 29;
        controls[index].ticks += index;
        FramePacingOperation operation(entry, 0x1000, 0x0ff0, 0x1000, 0x200000);
        operation.advance(4096, controls[index].bus());
        require(operation.returned(), "complete pacing control did not return");
        expected[index] = operation.registers(); count = operation.snapshot().dispatchedInstructions;
        require(count == 1037 && controls[index].globals[4] == 81 && controls[index].pacing[0] == 30,
            "complete pacing control work or counter differs");
    }
    unsigned eligible = 0, masked = 0;
    for (unsigned boundary = 0; boundary <= count; ++boundary) {
        Memory memory(148, 120, 0); memory.pacing[0] = 29;
        FramePacingOperation operation(entry, 0x1000, 0x0ff0, 0x1000, 0x200000);
        const auto bus = memory.bus();
        require(operation.advance(boundary, bus) == boundary, "complete pacing pre-IRQ work differs");
        if (!(operation.registers().flags & 0x200u)) {
            const auto old = operation.snapshot(); const auto stack = memory.stack;
            bool rejected = false;
            try { operation.deliverTimerInterrupt(bus); } catch (const std::logic_error&) { rejected = true; }
            require(rejected && operation.snapshot() == old && memory.stack == stack, "INT21 masked interval changed state");
            ++masked; continue;
        }
        operation.deliverTimerInterrupt(bus);
        while (!operation.finished()) {
            require(operation.advance(1, bus) == 1, "complete pacing IRQ did not advance");
            operation = FramePacingOperation(operation.snapshot());
        }
        const auto profile = boundary <= 11 ? 1u : 0u;
        require(operation.returned() && operation.registers() == expected[profile] &&
            memory.globals == controls[profile].globals && memory.timing == controls[profile].timing &&
            memory.pacing == controls[profile].pacing && memory.pspStack == controls[profile].pspStack && memory.ticks == 101,
            "complete pacing IRQ changed CPU, carried samples or mutable delay");
        const auto& state = operation.snapshot();
        require(state.dispatchedInstructions == count + 36 && state.calculation && state.delay &&
            state.gateInstructions + state.calculation->dispatchedInstructions + state.feedbackInstructions +
                state.delay->dispatchedInstructions + state.timerInstructions == state.dispatchedInstructions,
            "complete pacing work accounting differs");
        ++eligible;
    }
    for (uint16_t counter : {uint16_t{0}, uint16_t{28}, uint16_t{30}, uint16_t{65534}}) {
        Memory memory(148, 120, 0);
        memory.pacing[0] = static_cast<uint8_t>(counter); memory.pacing[1] = static_cast<uint8_t>(counter >> 8);
        FramePacingOperation operation(entry, 0x1000, 0x0ff0, 0x1000, 0x200000);
        operation.advance(4096, memory.bus());
        require(operation.returned() && !operation.snapshot().calculation && operation.snapshot().dispatchedInstructions == 16 &&
            memory.globals[4] == 0x5a && memory.timing == std::array<uint8_t, 11>{}, "pacing skip path measured or lost its ABI");
    }
    Memory wrapped(148, 120, 0); wrapped.pacing[0] = wrapped.pacing[1] = 255;
    FramePacingOperation zero(entry, 0x1000, 0x0ff0, 0x1000, 0x200000);
    zero.advance(4096, wrapped.bus());
    require(zero.returned() && zero.snapshot().calculation && wrapped.pacing[0] == 0 && wrapped.pacing[1] == 0,
        "wrapped zero counter did not measure");
    unsigned delayBoundaries = 0;
    const std::array<std::array<uint16_t, 2>, 3> delayProfiles{{{2,1}, {1,2}, {16,544}}};
    for (auto [delay, calibration] : delayProfiles) {
        Memory control(148, 120, 0);
        control.pacing[4] = static_cast<uint8_t>(delay); control.pacing[5] = static_cast<uint8_t>(delay >> 8);
        control.pacing[6] = static_cast<uint8_t>(calibration); control.pacing[7] = static_cast<uint8_t>(calibration >> 8);
        FramePacingOperation baseline(entry, 0x1000, 0x0ff0, 0x1000, 0x200000);
        baseline.advance(1000000, control.bus());
        const auto work = baseline.snapshot().dispatchedInstructions;
        require(baseline.returned() && work == 20u + uint64_t{delay} * (uint64_t{11} * calibration + 5u),
            "nonzero CRT pacing work differs");
        std::vector<uint64_t> boundaries;
        if (work < 100) for (uint64_t i = 0; i <= work; ++i) boundaries.push_back(i);
        else boundaries = {0, 8, 9, 10, 11, 12, 18, 19, 20, 100, 1000, work / 2, work - 2, work - 1, work};
        for (const auto boundary : boundaries) {
            Memory memory(148, 120, 0); memory.pacing = control.pacing;
            memory.pacing[0] = memory.pacing[1] = 0;
            FramePacingOperation operation(entry, 0x1000, 0x0ff0, 0x1000, 0x200000);
            const auto bus = memory.bus();
            require(operation.advance(boundary, bus) == boundary, "nonzero CRT pre-IRQ work differs");
            operation.deliverTimerInterrupt(bus);
            while (!operation.finished()) {
                require(operation.advance(1, bus) == 1, "nonzero CRT IRQ did not advance");
                operation = FramePacingOperation(operation.snapshot());
            }
            require(operation.returned() && operation.registers() == baseline.registers() && memory.pacing == control.pacing &&
                memory.timing == control.timing && memory.globals == control.globals && memory.ticks == 101 &&
                operation.snapshot().dispatchedInstructions == work + 36, "nonzero CRT IRQ lost context, work or memory");
            ++delayBoundaries;
        }
    }
    std::cout << "frame_pacing_operation_edges=ok eligible_boundaries=" << eligible << " masked_boundaries=" << masked
        << " skip_paths=4 counter_wrap=1 sampled_once=1 snapshot_restore=1 delay_irq_boundaries=" << delayBoundaries << '\n';
}
}
int main(int argc, char** argv) {
    try {
        if (argc == 1) edges();
        else if (argc == 2 && std::string(argv[1]) == "--composition") composedEdges();
        else if (argc == 2 && std::string(argv[1]) == "--pacing") pacingEdges();
        else if (argc == 3 && std::string(argv[1]) == "--instructions") instructions(argv[2]);
        else if (argc == 3 && std::string(argv[1]) == "--endpoints") endpoints(argv[2]);
        else if (argc == 3 && std::string(argv[1]) == "--pacing-oracle") pacingOracle(argv[2]);
        else if (argc == 3 && std::string(argv[1]) == "--gate-oracle") gateOracle(argv[2]);
        else if (argc == 3 && std::string(argv[1]) == "--feedback-oracle") feedbackOracle(argv[2]);
        else throw std::invalid_argument("expected --instructions or --endpoints projection");
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
