#include "core/crt_delay.hpp"
#include "resources/io.hpp"
#include "resources/json.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

using lezac::core::CrtDelayBus;
using lezac::core::CrtDelayOperation;
using lezac::core::CrtDelayRegisters;
using lezac::resources::extractInt;
using lezac::resources::extractObjectArray;
using lezac::resources::extractString;

namespace {
void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}
uint16_t word(const std::string& object, const std::string& key) {
    const int value = extractInt(object, key, -1);
    require(value >= 0 && value <= 65535, "invalid fixture register: " + key);
    return static_cast<uint16_t>(value);
}
CrtDelayRegisters registers(const std::string& json) {
    return {word(json, "ax"), word(json, "bx"), word(json, "cx"), word(json, "dx"),
        word(json, "di"), word(json, "bp"), word(json, "cs"), word(json, "ds"),
        word(json, "es"), word(json, "ss"), word(json, "sp"), word(json, "ip"), word(json, "flags")};
}
std::vector<uint16_t> inputs(const std::string& fixture, const std::string& key) {
    std::vector<uint16_t> values;
    for (const auto& object : extractObjectArray(fixture, key)) values.push_back(word(object, "value"));
    require(!values.empty(), "empty input script");
    return values;
}

struct Memory {
    std::vector<uint8_t> bytes = std::vector<uint8_t>(1024 * 1024);
    std::vector<uint16_t> calibration, com1;
    uint64_t calibrationReads = 0, com1Reads = 0;

    static uint32_t address(uint16_t segment, uint16_t offset) {
        return (uint32_t{segment} * 16 + offset) & 0xfffff;
    }
    void store(uint32_t at, uint16_t value) {
        bytes[at] = static_cast<uint8_t>(value);
        bytes[(at + 1) & 0xfffff] = static_cast<uint8_t>(value >> 8);
    }
    CrtDelayBus bus() {
        return {
            [&](uint16_t segment, uint16_t offset) {
                const auto at = address(segment, offset);
                if (at == 0x400) {
                    bytes[at] = static_cast<uint8_t>(com1[std::min<uint64_t>(com1Reads++, com1.size() - 1)]);
                }
                return bytes[at];
            },
            [&](uint16_t segment, uint16_t offset) {
                const auto at = address(segment, offset);
                if (at == 0x22988) store(at, calibration[std::min<uint64_t>(calibrationReads++, calibration.size() - 1)]);
                return static_cast<uint16_t>(bytes[at] | (uint16_t{bytes[(at + 1) & 0xfffff]} << 8));
            },
            [&](uint16_t segment, uint16_t offset, uint16_t value) { store(address(segment, offset), value); }
        };
    }
};

void compare(const CrtDelayOperation& operation, const Memory& memory, const std::string& expected,
             uint32_t stackAddress, const std::string& label) {
    const auto& state = operation.snapshot();
    const auto mask = static_cast<uint32_t>(std::stoul(extractString(expected, "defined_flags_hex"), nullptr, 16));
    auto wanted = registers(expected);
    require(state.definedFlags == mask, label + ": defined flag mask differs");
    require(((state.registers.flags ^ wanted.flags) & mask) == 0, label + ": defined flags differ");
    wanted.flags = state.registers.flags;
    require(state.registers == wanted, label + ": registers differ");
    require(state.dispatchedInstructions == static_cast<uint64_t>(extractInt(expected, "dispatch")), label + ": dispatch differs");
    require(memory.calibrationReads == static_cast<uint64_t>(extractInt(expected, "calibration_reads")) &&
            memory.com1Reads == static_cast<uint64_t>(extractInt(expected, "com1_reads")), label + ": live read counts differ");
    const auto stack = lezac::resources::parseHexByteList(extractString(expected, "stack_window"));
    require(stack.size() == 8 && std::equal(stack.begin(), stack.end(), memory.bytes.begin() + stackAddress),
            label + ": stack bytes differ");
}

void boundaryChecks() {
    Memory memory;
    memory.calibration = {1}; memory.com1 = {248};
    memory.store(0x8fe00, 0x79e8); memory.store(0x8fe02, 0x1000); memory.store(0x8fe04, 0);
    CrtDelayRegisters r{};
    r.cs = 0x184a; r.ds = 0x1aa2; r.ss = 0x8000; r.sp = 0xfe00;
    CrtDelayOperation zero{r};
    auto bus = memory.bus();
    bus.readByte = {}; bus.writeWord = {};
    require(zero.advance(4, bus) == 4 && !zero.returned(), "zero argument returned too early");
    memory.store(0x8fe00, 0x1234); memory.store(0x8fe02, 0x4321);
    require(zero.advance(1, bus) == 1 && zero.returned() && zero.snapshot().registers.ip == 0x1234 &&
            zero.snapshot().registers.cs == 0x4321, "far return ignored live stack");
    require(memory.calibrationReads == 0 && memory.com1Reads == 0, "zero delay read timing inputs");

    CrtDelayOperation fault{r};
    require(fault.advance(1, bus) == 1, "entry work differs");
    const auto before = fault.snapshot();
    auto broken = bus;
    broken.readWord = [](uint16_t, uint16_t) -> uint16_t { throw std::runtime_error("read fault"); };
    bool threw = false;
    try { fault.advance(1, broken); } catch (const std::runtime_error&) { threw = true; }
    require(threw && fault.snapshot() == before, "read fault advanced cursor");

    auto invalid = before;
    invalid.registers.ip = 0x7777;
    CrtDelayOperation unknown{invalid};
    require(unknown.advance(0, broken) == 0, "zero budget touched unsupported cursor");
    threw = false;
    try { unknown.advance(1, broken); } catch (const std::domain_error&) { threw = true; }
    require(threw && unknown.snapshot() == invalid, "unsupported control flow was normalized");

    memory.store(0x8fe00, 0x79e8); memory.store(0x8fe02, 0x1000); memory.store(0x8fe04, 1);
    CrtDelayOperation nearReturn{r};
    bus = memory.bus();
    for (unsigned step = 0; nearReturn.snapshot().registers.ip != 0x02c8; ++step) {
        require(step < 100 && nearReturn.advance(1, bus) == 1, "near return not reached");
    }
    memory.store(Memory::address(r.ss, nearReturn.snapshot().registers.sp), 0x02ba);
    require(nearReturn.advance(1, bus) == 1 && nearReturn.snapshot().registers.ip == 0x02ba,
            "near return ignored live stack");
    require(nearReturn.advance(1, bus) == 1 && nearReturn.returned(), "live near return was not followed");
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 2, "expected CRT delay fixture directory");
        const std::filesystem::path root{argv[1]};
        const auto json = lezac::resources::readTextFile((root / "memory-provider.json").string());
        const auto cases = extractObjectArray(json, "cases");
        require(cases.size() == 17, "original case count differs");
        const auto stackAddress = static_cast<uint32_t>(extractInt(json, "stack_window_address"));
        std::size_t snapshotCount = 0;
        uint64_t originalDispatches = 0;
        for (const auto& fixture : cases) {
            const auto name = extractString(fixture, "name");
            const auto snapshots = extractObjectArray(fixture, "snapshots");
            require(!snapshots.empty() && extractInt(snapshots.front(), "dispatch", -1) == 0, "missing entry state");
            for (int mode = 0; mode < 2; ++mode) {
                Memory memory;
                memory.calibration = inputs(fixture, "calibration_inputs");
                memory.com1 = inputs(fixture, "com1_inputs");
                const auto entryStack = lezac::resources::parseHexByteList(extractString(snapshots.front(), "stack_window"));
                require(entryStack.size() == 8 && stackAddress + 8 < memory.bytes.size(), "entry stack outside memory");
                std::copy(entryStack.begin(), entryStack.end(), memory.bytes.begin() + stackAddress);
                CrtDelayOperation operation{registers(snapshots.front())};
                auto bus = memory.bus();
                std::size_t budgetCursor = 0;
                constexpr std::array<uint64_t, 8> budgets{0, 1, 7, 0, 31, 256, 13, 1024};
                for (const auto& expected : snapshots) {
                    const auto target = static_cast<uint64_t>(extractInt(expected, "dispatch"));
                    while (operation.snapshot().dispatchedInstructions < target) {
                        const auto remaining = target - operation.snapshot().dispatchedInstructions;
                        const auto budget = mode == 0 ? remaining : std::min(remaining, budgets[budgetCursor++ % budgets.size()]);
                        require(operation.advance(budget, bus) == budget, name + ": work ended early");
                        if (mode == 1) operation = CrtDelayOperation{operation.snapshot()};
                    }
                    compare(operation, memory, expected, stackAddress, name + ":" + std::to_string(target));
                }
                require(operation.returned(), name + ": original return not reached");
                const auto finished = operation.snapshot();
                CrtDelayBus empty;
                require(operation.advance(std::numeric_limits<uint64_t>::max(), empty) == 0 &&
                        operation.snapshot() == finished, "completed operation performed work");
            }
            snapshotCount += snapshots.size();
            originalDispatches += static_cast<uint64_t>(extractInt(fixture, "dispatches"));
        }
        require(snapshotCount == 758 && originalDispatches == 13273201, "original work coverage differs");
        boundaryChecks();
        std::cout << "crt_delay_original=ok cases=17 snapshots=758 replay_modes=2 "
                     "original_dispatches=13273201 natural_clock=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "crt_delay_original=failed " << error.what() << '\n';
        return 1;
    }
}
