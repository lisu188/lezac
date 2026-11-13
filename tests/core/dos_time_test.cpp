#include "core/dos_time.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using namespace lezac::core;

static_assert(dosTimeFromBiosTicks(0) == DosTimeFields{});
static_assert(dosTimeFromBiosTicks(1) == DosTimeFields{0, 0, 0, 5});
static_assert(dosTimeFromBiosTicks(0x33333334) == DosTimeFields{0, 0, 0, 4});

namespace {
void require(bool value, const std::string& message) {
    if (!value) throw std::runtime_error(message);
}

struct Reader {
    std::vector<uint8_t> bytes;
    std::size_t cursor = 0;
    uint32_t number(unsigned count) {
        require(count <= 4 && count <= bytes.size() - cursor, "projection truncated");
        uint32_t result = 0;
        for (unsigned index = 0; index < count; ++index) result |= uint32_t{bytes[cursor++]} << (index * 8);
        return result;
    }
    uint16_t word() { return static_cast<uint16_t>(number(2)); }
    std::vector<uint8_t> take(std::size_t count) {
        require(count <= bytes.size() - cursor, "projection bytes truncated");
        std::vector<uint8_t> result(bytes.begin() + cursor, bytes.begin() + cursor + count);
        cursor += count;
        return result;
    }
};

struct Expected {
    DosGetTimeRegisters registers;
    uint32_t mask, bios, pspStack;
    std::vector<uint8_t> stack;
};

Expected readState(Reader& reader) {
    DosGetTimeRegisters r;
    r.ax = reader.word(); r.bx = reader.word(); r.cx = reader.word(); r.dx = reader.word();
    r.si = reader.word(); r.di = reader.word(); r.bp = reader.word(); r.cs = reader.word();
    r.ds = reader.word(); r.es = reader.word(); r.ss = reader.word(); r.sp = reader.word(); r.ip = reader.word();
    r.flags = reader.number(4);
    const auto mask = reader.number(4), bios = reader.number(4), pspStack = reader.number(4);
    const auto length = reader.number(1);
    return {r, mask, bios, pspStack, reader.take(length)};
}

struct Memory {
    std::array<uint8_t, 65536> stack{};
    uint16_t ss = 0, psp = 0, entrySp = 0;
    uint32_t bios = 0, pspStack = 0;
    unsigned biosReads = 0, wordReads = 0, wordWrites = 0, dwordWrites = 0;

    uint16_t word(uint16_t offset) const {
        return static_cast<uint16_t>(stack[offset] | (uint16_t{stack[static_cast<uint16_t>(offset + 1)]} << 8));
    }
    void put(uint16_t offset, uint16_t value) {
        stack[offset] = static_cast<uint8_t>(value);
        stack[static_cast<uint16_t>(offset + 1)] = static_cast<uint8_t>(value >> 8);
    }
    DosGetTimeBus bus() {
        return {
            [&] { ++biosReads; return bios; },
            [&](uint16_t segment, uint16_t offset) {
                require(segment == ss && wordReads < 4, "unexpected stack read");
                const uint16_t expected = wordReads == 0 ? static_cast<uint16_t>(entrySp - 2) :
                    static_cast<uint16_t>(entrySp + (wordReads - 1) * 2);
                require(offset == expected, "stack read address differs");
                ++wordReads;
                return word(offset);
            },
            [&](uint16_t segment, uint16_t offset, uint16_t value) {
                require(segment == ss && offset == static_cast<uint16_t>(entrySp - 2) && wordWrites == 0,
                        "unexpected stack write");
                ++wordWrites;
                put(offset, value);
            },
            [&](uint16_t segment, uint16_t offset, uint32_t value) {
                require(segment == psp && offset == 0x2e && dwordWrites == 0, "unexpected PSP write");
                ++dwordWrites;
                pspStack = value;
            }
        };
    }
};

void compare(const DosGetTimeOperation& operation, const Memory& memory, const Expected& expected,
             const std::string& context) {
    auto actual = operation.snapshot().registers;
    auto wanted = expected.registers;
    require(((actual.flags ^ wanted.flags) & expected.mask) == 0, context + " defined flags differ");
    actual.flags = wanted.flags = 0;
    require(actual == wanted, context + " registers differ");
    require(operation.snapshot().definedFlags == expected.mask, context + " flag scope differs");
    require(memory.pspStack == expected.pspStack, context + " PSP differs");
    for (std::size_t index = 0; index < expected.stack.size(); ++index)
        require(memory.stack[static_cast<uint16_t>(actual.sp + index)] == expected.stack[index], context + " stack differs");
}

std::size_t original(Reader reader) {
    require(reader.take(8) == std::vector<uint8_t>({'L','Z','D','O','S','T','0','1'}), "projection version differs");
    const auto cases = reader.number(4);
    require(cases == 20, "original case count differs");
    std::size_t comparisons = 0, external = 0;
    for (unsigned caseIndex = 0; caseIndex < cases; ++caseIndex) {
        const auto run = reader.word(), call = reader.word(), base = reader.word(), psp = reader.word();
        const auto ss = reader.word(), sp = reader.word();
        const auto id = reader.number(4), bios = reader.number(4), pspStack = reader.number(4);
        const auto stateCount = reader.word(), externalCount = reader.word();
        external += externalCount;
        require(stateCount == 326, "full DOS window differs");
        const auto initial = reader.take(64);
        std::vector<Expected> states;
        for (unsigned index = 0; index < stateCount; ++index) states.push_back(readState(reader));
        for (bool restoreEveryStep : {false, true}) {
            Memory memory;
            memory.ss = ss; memory.psp = psp; memory.entrySp = sp; memory.bios = bios; memory.pspStack = pspStack;
            for (unsigned index = 0; index < initial.size(); ++index)
                memory.stack[static_cast<uint16_t>(sp + index)] = initial[index];
            const auto bus = memory.bus();
            DosGetTimeOperation operation(states.front().registers, base, psp, id);
            for (unsigned index = 0; index < stateCount; ++index) {
                const auto context = "run=" + std::to_string(run) + " call=" + std::to_string(call) +
                    " state=" + std::to_string(index);
                // BIOS is external input. No reference register, PSP or stack output is injected.
                memory.bios = states[index].bios;
                const auto unchanged = operation.snapshot();
                require(operation.advance(0, bus) == 0 && operation.snapshot() == unchanged, "zero budget changed state");
                compare(operation, memory, states[index], context);
                ++comparisons;
                if (index + 1 < stateCount) require(operation.advance(1, bus) == 1, "instruction budget differs");
                if (restoreEveryStep) operation = DosGetTimeOperation(operation.snapshot());
            }
            require(operation.returned() && operation.snapshot().dispatchedInstructions == 325, "terminal work differs");
            require(operation.advance(100, bus) == 0, "returned callback consumed work");
            require(memory.biosReads == 1 && memory.wordReads == 4 && memory.wordWrites == 1 && memory.dwordWrites == 1,
                    "memory access footprint differs");
        }
    }
    require(reader.cursor == reader.bytes.size() && external == 36, "projection tail or IRQ scope differs");
    return comparisons;
}

void unit() {
    Memory memory;
    memory.ss = 0x1234; memory.psp = 0x1200; memory.entrySp = 0; memory.bios = 1;
    memory.put(0, 0xabcd); memory.put(2, 0x4567); memory.put(4, 0x0246);
    DosGetTimeRegisters registers;
    registers.ax = 0x2c55; registers.cs = 0xf000; registers.ip = 0x1001;
    registers.ss = memory.ss; registers.flags = 0x80200603;
    DosGetTimeOperation operation(registers, 0x1000, memory.psp, 0x200000);
    const auto bus = memory.bus();
    require(operation.advance(1, bus) == 1 && memory.pspStack == 0x1234ffee &&
            operation.snapshot().registers.dx == 5, "atomic callback or wrapped PSP differs");
    memory.bios = 0xffffffff;
    require(operation.advance(9999, bus) == 324 && operation.returned(), "bounded return work differs");
    const auto result = operation.snapshot().registers;
    require(result.cx == 0 && result.dx == 5 && result.sp == 6 && result.ip == 0xabcd && result.cs == 0x4567,
            "sampled clock or wrapped stack changed");
    require(result.flags == 0x80000246, "IRET ID toggle, high flags or low flags differ");
    const auto fields = dosTimeFromBiosTicks(912321);
    require(fields == DosTimeFields{13, 55, 9, 68} && fields.gameClockSample().minute == 55, "game clock adapter differs");
    for (unsigned invalid : {0u, 1u, 2u}) {
        auto changed = registers;
        if (invalid == 0) changed.ip = 0;
        if (invalid == 1) changed.ax = 0;
        bool rejected = false;
        try { DosGetTimeOperation bad(changed, 0x1000, memory.psp, invalid == 2 ? 1 : 0x200000); }
        catch (const std::invalid_argument&) { rejected = true; }
        require(rejected, "invalid callback entry accepted");
    }
}
}

int main(int argc, char** argv) {
    try {
        unit();
        if (argc == 1) {
            std::cout << "dos_time_unit=ok wrapped_stack=1 sampled_once=1 flags=1 app_integrated=0\n";
        } else {
            require(argc == 2, "expected projection path");
            std::ifstream stream(argv[1], std::ios::binary);
            require(stream.good(), "projection missing");
            Reader reader{{std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()}};
            const auto count = original(std::move(reader));
            std::cout << "dos_time_original=ok windows=20 comparisons=" << count
                << " component_states=6520 external_irq_instructions=36 irq_replayed=0 app_integrated=0\n";
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
