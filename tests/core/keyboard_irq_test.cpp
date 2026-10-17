#include "core/keyboard_irq.hpp"
#include "core/keyboard_controller.hpp"
#include "core/pic_work_clock.hpp"

#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <tuple>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool value, const char* message) {if (!value) throw std::runtime_error(message);}
struct Reader {
    std::ifstream input;
    explicit Reader(const char* path) : input(path, std::ios::binary) {require(input.good(), "Keyboard corpus missing");}
    uint64_t number(unsigned size) {
        uint64_t result = 0;
        for (unsigned index = 0; index < size; ++index) {
            const int value = input.get(); require(value >= 0, "Keyboard corpus truncated");
            result |= uint64_t{static_cast<uint8_t>(value)} << (index * 8);
        }
        return result;
    }
    uint8_t byte() {return static_cast<uint8_t>(number(1));}
    uint16_t word() {return static_cast<uint16_t>(number(2));}
    uint32_t dword() {return static_cast<uint32_t>(number(4));}
    std::vector<uint8_t> bytes(size_t count) {
        std::vector<uint8_t> result(count);
        input.read(reinterpret_cast<char*>(result.data()), static_cast<std::streamsize>(count));
        require(input.good(), "Keyboard corpus payload truncated"); return result;
    }
    void end() {require(input.get() < 0, "Keyboard corpus has trailing data");}
};
using Port = std::tuple<uint8_t, uint16_t, uint8_t>;
struct Memory {
    std::vector<uint8_t> bytes = std::vector<uint8_t>(1048576);
    std::vector<Port> ports;
    TimerIrqBus bus;
    std::function<uint8_t(uint16_t)> readPort;
    std::function<void(uint16_t, uint8_t)> writePort;
    Memory() {
        bus.readByte = [&](uint16_t s, uint16_t o) {return bytes.at(s * 16u + o);};
        bus.readWord = [&](uint16_t s, uint16_t o) {return static_cast<uint16_t>(bus.readByte(s, o) |
            uint16_t{bus.readByte(s, static_cast<uint16_t>(o + 1u))} << 8);};
        bus.readDword = [&](uint16_t s, uint16_t o) {return uint32_t{bus.readWord(s, o)} |
            uint32_t{bus.readWord(s, static_cast<uint16_t>(o + 2u))} << 16;};
        bus.writeByte = [&](uint16_t s, uint16_t o, uint8_t v) {bytes.at(s * 16u + o) = v;};
        bus.writeWord = [&](uint16_t s, uint16_t o, uint16_t v) {
            bus.writeByte(s, o, static_cast<uint8_t>(v)); bus.writeByte(s, static_cast<uint16_t>(o + 1u), static_cast<uint8_t>(v >> 8));};
        bus.writeDword = [&](uint16_t s, uint16_t o, uint32_t v) {
            bus.writeWord(s, o, static_cast<uint16_t>(v)); bus.writeWord(s, static_cast<uint16_t>(o + 2u), static_cast<uint16_t>(v >> 16));};
        bus.inByte = [&](uint16_t port) {
            require(static_cast<bool>(readPort), "Unexpected keyboard port read");
            const auto value = readPort(port); ports.emplace_back(uint8_t{1}, port, value); return value;};
        bus.outByte = [&](uint16_t port, uint8_t value) {
            ports.emplace_back(uint8_t{2}, port, value); if (writePort) writePort(port, value);};
    }
    void load(uint16_t segment, uint16_t offset, const std::vector<uint8_t>& raw) {
        for (size_t index = 0; index < raw.size(); ++index)
            bus.writeByte(segment, static_cast<uint16_t>(offset + index), raw[index]);
    }
    bool matches(uint16_t segment, uint16_t offset, const std::vector<uint8_t>& raw) const {
        for (size_t index = 0; index < raw.size(); ++index)
            if (bus.readByte(segment, static_cast<uint16_t>(offset + index)) != raw[index]) return false;
        return true;
    }
};
struct State {
    TimerIrqRegisters r;
    std::vector<uint8_t> stack, bios, held, opcode, hardwareBuffer;
    std::array<uint64_t, 13> hardware{};
    std::array<uint16_t, 5> pic{};
};
State state(Reader& in) {
    State result;
    auto& r = result.r;
    for (auto* value : {&r.ax, &r.bx, &r.cx, &r.dx, &r.si, &r.di, &r.bp, &r.cs, &r.ds, &r.es, &r.ss, &r.sp, &r.ip}) *value = in.word();
    r.flags = in.dword();
    result.stack = in.bytes(128); result.bios = in.bytes(152); result.held = in.bytes(10);
    result.opcode = in.bytes(8); result.hardwareBuffer = in.bytes(32);
    for (auto& value : result.hardware) value = in.number(8);
    for (auto& value : result.pic) value = in.word();
    return result;
}
bool registers(TimerIrqRegisters actual, TimerIrqRegisters expected, uint32_t mask) {
    actual.flags &= mask; expected.flags &= mask; return actual == expected;
}

void original(const char* path) {
    Reader in(path);
    require(in.bytes(8) == std::vector<uint8_t>({'L','Z','K','I','R','Q','0','1'}), "IRQ1 corpus version differs");
    const auto cases = in.dword(); require(cases > 0 && cases < 256, "IRQ1 case bound differs");
    uint64_t comparisons = 0, instructions = 0, portEvents = 0;
    for (uint32_t index = 0; index < cases; ++index) {
        const auto count = in.dword(); require(count > 0 && count < 512, "IRQ1 window bound differs");
        const auto stackBase = in.word(), stackSegment = in.word(), game = in.word(), data = in.word();
        const auto chainIp = in.word(), chainCs = in.word(), bios15Ip = in.word(), bios15Cs = in.word();
        const auto idToggle = in.dword(); const auto scan = in.byte();
        require(chainIp == 0xe987 && chainCs == 0xf000 && bios15Ip == 0x11c0 && bios15Cs == 0xf000,
                "IRQ1 callback profile differs");
        std::vector<State> states;
        for (uint32_t at = 0; at < count; ++at) states.push_back(state(in));
        std::vector<Port> expectedPorts;
        for (size_t at = 0; at + 1 < states.size(); ++at) {
            const auto& current = states[at];
            if (current.opcode[0] == 0xe4)
                expectedPorts.emplace_back(uint8_t{1}, uint16_t{current.opcode[1]}, static_cast<uint8_t>(states[at + 1].r.ax));
            else if (current.opcode[0] == 0xe6)
                expectedPorts.emplace_back(uint8_t{2}, uint16_t{current.opcode[1]}, static_cast<uint8_t>(current.r.ax));
        }
        for (bool restore : {false, true}) {
            Memory memory;
            memory.load(stackSegment, stackBase, states.front().stack);
            memory.load(0x40, 0, states.front().bios);
            memory.load(data, 0x1b78, states.front().held);
            memory.bus.writeWord(data, 0x1b60, chainIp); memory.bus.writeWord(data, 0x1b62, chainCs);
            memory.bus.writeWord(0, 0x54, bios15Ip); memory.bus.writeWord(0, 0x56, bios15Cs);
            auto hardware = states.front().hardware;
            require(hardware[7] == scan, "IRQ1 initial hardware byte differs");
            KeyboardControllerSnapshot keyboardState;
            std::copy(states.front().hardwareBuffer.begin(), states.front().hardwareBuffer.end(), keyboardState.buffer.begin());
            keyboardState.used = static_cast<uint32_t>(hardware[0]); keyboardState.pos = static_cast<uint32_t>(hardware[1]);
            keyboardState.repeatKey = static_cast<KeyboardHardwareKey>(hardware[2]);
            keyboardState.repeatWait = static_cast<uint32_t>(hardware[3]); keyboardState.repeatPause = static_cast<uint32_t>(hardware[4]);
            keyboardState.repeatRate = static_cast<uint32_t>(hardware[5]); keyboardState.command = static_cast<KeyboardControllerCommand>(hardware[6]);
            keyboardState.port60 = static_cast<uint8_t>(hardware[7]); keyboardState.port60Changed = hardware[8] != 0;
            keyboardState.active = hardware[9] != 0; keyboardState.scanning = hardware[10] != 0;
            keyboardState.scheduled = hardware[11] != 0; keyboardState.port61 = static_cast<uint8_t>(hardware[12]);
            KeyboardController keyboard(keyboardState);
            KeyboardControllerBus keyboardBus;
            keyboardBus.scheduleTransfer = [](float delay) {require(delay == 0.300f, "Original keyboard transfer delay differs");};
            PicWorkClockSnapshot pic;
            pic.pitDelay = 1000.0f / (1193182.0f / 65536.0f);
            pic.activeIrq = static_cast<uint8_t>(states.front().pic[0]);
            pic.inserviceLines = states.front().pic[3];
            PicWorkClock clock(pic);
            memory.readPort = [&](uint16_t port) {
                require(port == 0x60, "IRQ1 unexpected IN port");
                return keyboard.readPort(port, keyboardBus);
            };
            memory.writePort = [&](uint16_t port, uint8_t value) {
                require(port == 0x20 && value == 0x20, "IRQ1 unexpected OUT port/value");
                clock.nonspecificMasterEoi();
            };
            KeyboardIrqOperation operation(states.front().r, game, idToggle);
            for (size_t at = 0; at < states.size(); ++at) {
                const auto& expected = states[at];
                ++comparisons;
                const uint32_t flagsMask = at + 1 == states.size() ? 0x7fd5u | idToggle | 2u : 0x700u;
                if (!registers(operation.snapshot().registers, expected.r, flagsMask)) {
                    std::cerr << "irq_case=" << index << " state=" << at << " restore=" << restore
                              << " actual_ip=" << operation.snapshot().registers.ip << " expected_ip=" << expected.r.ip << '\n';
                    throw std::runtime_error("Original IRQ1 registers differ");
                }
                require(memory.matches(stackSegment, stackBase, expected.stack), "Original IRQ1 stack differs");
                require(memory.matches(0x40, 0, expected.bios), "Original IRQ1 BIOS memory differs");
                require(memory.matches(data, 0x1b78, expected.held), "Original IRQ1 held-control bank differs");
                const auto& k = keyboard.snapshot();
                const std::array<uint64_t, 5> owned{k.used, k.pos, k.port60, k.port60Changed, k.scheduled};
                const std::array<size_t, 5> fields{0, 1, 7, 8, 11};
                for (size_t field = 0; field < fields.size(); ++field)
                    require(owned[field] == expected.hardware[fields[field]], "Original IRQ1 port-owned hardware state differs");
                require(std::equal(k.buffer.begin(), k.buffer.end(), expected.hardwareBuffer.begin()),
                        "External input changed inside IRQ1 window");
                require(clock.snapshot().activeIrq == expected.pic[0] && clock.snapshot().inserviceLines == expected.pic[3],
                        "Original IRQ1 PIC EOI state differs");
                if (at + 1 < states.size()) {
                    require(operation.advance(1, memory.bus) == 1, "IRQ1 dispatch stopped early");
                    ++instructions;
                    if (restore) {
                        operation = KeyboardIrqOperation(operation.snapshot());
                        keyboard = KeyboardController(keyboard.snapshot());
                    }
                }
            }
            require(operation.returned() && !operation.needsBiosIdle(), "Original IRQ1 did not return");
            require(memory.ports == expectedPorts, "Original IRQ1 ordered I/O differs");
            require(operation.advance(1, memory.bus) == 0, "Returned IRQ1 dispatched again");
            portEvents += memory.ports.size();
        }
    }
    in.end();
    std::cout << "keyboard_irq_original=ok cases=" << cases << " comparisons=" << comparisons
              << " instructions=" << instructions << " ordered_io=" << portEvents
              << " snapshot_restore=1 irq_eligibility_claim=0 app_cadence_claim=0 whole_game_claim=0\n";
}

void bios(const char* path) {
    Reader in(path);
    require(in.bytes(8) == std::vector<uint8_t>({'L','Z','B','I','O','S','K','1'}), "BIOS keyboard oracle version differs");
    const auto cases = in.dword(); require(cases == 65536, "BIOS keyboard oracle case count differs");
    for (const auto& entry : detail::biosScanAscii) for (auto value : entry)
        require(in.word() == value, "BIOS scan translation table differs");
    Memory memory;
    uint64_t pauses = 0, bytes = 0;
    for (uint32_t index = 0; index < cases; ++index) {
        require(in.word() == index / 256, "BIOS profile order differs");
        const auto scan = in.byte(), action = in.byte(), outputs = in.byte();
        require(scan == index % 256 && action <= 1 && outputs <= 1, "BIOS oracle domain differs");
        const auto initial = in.bytes(152), expected = in.bytes(152);
        std::vector<Port> expectedPorts;
        for (unsigned at = 0; at < outputs; ++at) {const auto port = in.word(); expectedPorts.emplace_back(uint8_t{2}, port, in.byte());}
        memory.load(0x40, 0, initial); memory.ports.clear();
        const auto result = handleBiosKeyboardScan(scan, memory.bus);
        require((result == BiosKeyboardResult::NeedIdle) == (action == 1), "Original BIOS Pause handoff differs");
        if (!memory.matches(0x40, 0, expected)) {
            std::cerr << "bios_case=" << index << " scan=" << unsigned(scan) << '\n';
            throw std::runtime_error("Original BIOS keyboard callback memory differs");
        }
        require(memory.ports == expectedPorts, "Original BIOS keyboard callback I/O differs");
        bytes += expected.size(); pauses += action;
    }
    in.end();
    std::cout << "bios_keyboard_original=ok cases=" << cases << " bytes=" << bytes << " pause_handoffs=" << pauses
              << " original_functions_unchanged=1 full_host_claim=0 whole_game_claim=0\n";
}

void unit() {
    Memory memory;
    memory.bus.writeWord(0x40, 0x80, 0x1e); memory.bus.writeWord(0x40, 0x82, 0x3e);
    memory.bus.writeWord(0x40, 0x1a, 0x1e); memory.bus.writeWord(0x40, 0x1c, 0x1e);
    memory.bus.writeByte(0x40, 0x96, 0x11);
    require(handleBiosKeyboardScan(0x45, memory.bus) == BiosKeyboardResult::NeedIdle,
            "BIOS Pause was silently completed");
    require(memory.bus.readByte(0x40, 0x18) == 8 && memory.bus.readByte(0x40, 0x96) == 0x10 &&
            memory.ports == std::vector<Port>{{uint8_t{2}, uint16_t{0x20}, uint8_t{0x20}}}, "BIOS Pause handoff effects differ");
    TimerIrqRegisters r;
    r.cs = 0x1000; r.ip = 0x1091; r.flags = 2;
    KeyboardIrqOperation operation(r, 0x1000, 0x200000);
    const auto before = operation.snapshot();
    require(operation.advance(0, memory.bus) == 0 && operation.snapshot() == before, "Zero IRQ budget mutated state");
    auto suspended = before; suspended.biosIdle = true; suspended.registers.cs = 0xf000; suspended.registers.ip = 0xe995;
    operation = KeyboardIrqOperation(suspended);
    require(operation.advance(1, memory.bus) == 0 && operation.snapshot() == suspended, "Pause dispatched during idle");
    memory.bus.writeByte(0x40, 0x18, 0);
    operation.advance(1, memory.bus);
    require(!operation.needsBiosIdle() && operation.snapshot().registers.ip == 0xe99b,
            "Resumed Pause did not skip the already-issued EOI");
    for (bool badFlags : {false, true}) {
        auto bad = r; if (badFlags) bad.flags |= 0x200; else bad.ip = 0x1092;
        bool rejected = false;
        try {KeyboardIrqOperation invalid(bad, 0x1000, 0x200000);} catch (const std::invalid_argument&) {rejected = true;}
        require(rejected, "Invalid IRQ1 entry accepted");
    }
    memory.bus.writeWord(0x40, 0x82, 0x40);
    const auto original = memory.bytes;
    bool rejected = false;
    try {handleBiosKeyboardScan(0x2c, memory.bus);} catch (const std::domain_error&) {rejected = true;}
    require(rejected && memory.bytes == original, "Unsupported BIOS ring mutated state");
    std::cout << "keyboard_irq_unit=ok zero_budget=1 pause_handoff=1 pause_resume=1 invalid_entry=1 invalid_ring=1\n";
}
}

int main(int argc, char** argv) {
    try {
        if (argc == 1) unit();
        else if (argc == 3 && std::string(argv[1]) == "--original") original(argv[2]);
        else if (argc == 3 && std::string(argv[1]) == "--bios") bios(argv[2]);
        else throw std::runtime_error("Expected --original CORPUS or --bios CORPUS");
        return 0;
    } catch (const std::exception& error) {std::cerr << error.what() << '\n'; return 1;}
}
