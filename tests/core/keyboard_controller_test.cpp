#include "core/keyboard_controller.hpp"
#include "core/pic_work_clock.hpp"

#include <bit>
#include <fstream>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool value, const std::string& message) {if (!value) throw std::runtime_error(message);}
struct Effects {
    bool a20 = false;
    std::vector<std::pair<uint8_t, uint32_t>> values;
    KeyboardControllerBus bus() {
        return {[&](float delay) {values.emplace_back(uint8_t{1}, std::bit_cast<uint32_t>(delay));},
            [&] {values.emplace_back(uint8_t{2}, uint32_t{0});}, [&] {values.emplace_back(uint8_t{3}, uint32_t{1});}, [&] {return a20;},
            [&](bool value) {a20 = value; values.emplace_back(uint8_t{4}, uint32_t{value});},
            [&](bool value) {values.emplace_back(uint8_t{5}, uint32_t{value});},
            [&](uint8_t value) {values.emplace_back(uint8_t{6}, uint32_t{value});}};
    }
};
uint64_t integer(std::istream& stream, unsigned bytes) {
    uint64_t result = 0;
    for (unsigned i = 0; i < bytes; ++i) {
        const auto value = stream.get();
        require(value != std::char_traits<char>::eof(), "Truncated keyboard controller oracle");
        result |= uint64_t{static_cast<uint8_t>(value)} << (i * 8u);
    }
    return result;
}
KeyboardControllerSnapshot readState(std::istream& stream) {
    KeyboardControllerSnapshot s;
    for (auto& value : s.buffer) value = static_cast<uint8_t>(integer(stream, 1));
    s.used = static_cast<uint32_t>(integer(stream, 8)); s.pos = static_cast<uint32_t>(integer(stream, 8));
    s.repeatKey = static_cast<KeyboardHardwareKey>(integer(stream, 8));
    s.repeatWait = static_cast<uint32_t>(integer(stream, 8)); s.repeatPause = static_cast<uint32_t>(integer(stream, 8));
    s.repeatRate = static_cast<uint32_t>(integer(stream, 8)); s.command = static_cast<KeyboardControllerCommand>(integer(stream, 8));
    s.port60 = static_cast<uint8_t>(integer(stream, 8)); s.port60Changed = integer(stream, 8) != 0;
    s.active = integer(stream, 8) != 0; s.scanning = integer(stream, 8) != 0; s.scheduled = integer(stream, 8) != 0;
    s.port61 = static_cast<uint8_t>(integer(stream, 8));
    return s;
}
uint16_t action(KeyboardController& controller, const KeyboardControllerBus& bus, uint8_t kind, uint16_t argument, bool pressed) {
    switch (kind) {
    case 1: controller.addKey(static_cast<KeyboardHardwareKey>(argument), pressed, bus); break;
    case 2: controller.writePort(0x60, static_cast<uint8_t>(argument), bus); break;
    case 3: return controller.readPort(0x60, bus);
    case 4: controller.writePort(0x61, static_cast<uint8_t>(argument), bus); break;
    case 5: return controller.readPort(0x61, bus);
    case 6: controller.writePort(0x64, static_cast<uint8_t>(argument), bus); break;
    case 7: return controller.readPort(0x64, bus);
    case 8: controller.transferBuffer(bus); break;
    case 9: controller.clearBuffer(bus); break;
    case 10: controller.tick(bus); break;
    default: throw std::runtime_error("Unknown keyboard controller test action");
    }
    return 0;
}
void portClock(std::istream& stream) {
    std::string magic(8, '\0'); stream.read(magic.data(), 8);
    require(magic == "LZKPORT1" && integer(stream, 4) == 20, "Original port-clock domain differs");
    uint64_t reslices = 0;
    for (unsigned index = 0; index < 20; ++index) {
        const auto flags = static_cast<uint32_t>(integer(stream, 4));
        PicWorkClockSnapshot initial;
        initial.pitDelay = 1000.0f / (1193182.0f / 65536.0f);
        initial.cycles = static_cast<int64_t>(integer(stream, 8)); initial.cycleLeft = static_cast<int64_t>(integer(stream, 8));
        initial.ioDelayRemoved = static_cast<int64_t>(integer(stream, 8)); initial.ticks = integer(stream, 8);
        initial.activeIrq = static_cast<uint8_t>(integer(stream, 2)); initial.pending = static_cast<uint16_t>(integer(stream, 2));
        initial.activeLines = static_cast<uint16_t>(integer(stream, 2)); initial.inserviceLines = static_cast<uint16_t>(integer(stream, 2));
        initial.maskedLines = static_cast<uint16_t>(integer(stream, 2));
        const auto keyboardInitial = readState(stream);
        const auto cycles = static_cast<int64_t>(integer(stream, 8)), left = static_cast<int64_t>(integer(stream, 8));
        const auto ioDelay = static_cast<int64_t>(integer(stream, 8)); const auto ticks = integer(stream, 8);
        std::array<uint16_t, 5> expectedPic{};
        for (auto& value : expectedPic) value = static_cast<uint16_t>(integer(stream, 2));
        const auto expectedKeyboard = readState(stream);
        for (bool restored : {false, true}) {
            PicWorkClock clock(initial);
            KeyboardController controller(keyboardInitial);
            KeyboardControllerBus bus;
            bus.scheduleTransfer = [&](float delay) {
                clock.scheduleDeviceEvent({clock.fractionalTickIndex() + delay, PicClockEventKind::KeyboardTransfer, 0});
            };
            clock.chargePortRead();
            require(controller.readPort(0x60, bus) == expectedKeyboard.port60, "Original port-clock latch differs");
            if (restored) {clock = PicWorkClock(clock.snapshot()); controller = KeyboardController(controller.snapshot());}
            require(clock.nextDispatch(false, flags).kind == PicClockBoundaryKind::Ready, "Original port-clock continuation differs");
            const auto& result = clock.snapshot();
            const std::array<uint16_t, 5> actualPic{result.activeIrq, result.pending, result.activeLines, result.inserviceLines, result.maskedLines};
            require(result.cycles == cycles && result.cycleLeft == left && result.ioDelayRemoved == ioDelay && result.ticks == ticks,
                    "Original port-clock CPU budget differs at case " + std::to_string(index));
            require(actualPic == expectedPic && controller.snapshot() == expectedKeyboard,
                    "Original port-clock device state differs at case " + std::to_string(index));
        }
        reslices += left != initial.cycleLeft;
    }
    require(reslices == 14, "Original port-clock early-slice domain differs");
    std::cout << "keyboard_port_clock_original=ok cases=20 early_core_slices=14 snapshot_restore=1"
              << " later_observations_injected=0 complete_queue_claim=0 full_host_clock_claim=0\n";
}
void original(const std::string& path, bool functionsOnly) {
    std::ifstream stream(path, std::ios::binary);
    std::string magic(8, '\0'); stream.read(magic.data(), 8);
    require(magic == "LZKDEV01", "Keyboard controller oracle magic differs");
    const auto cases = integer(stream, 4);
    require(cases == 31296, "Keyboard controller oracle case count differs");
    uint64_t effects = 0;
    for (uint64_t index = 0; index < cases; ++index) {
        const auto kind = static_cast<uint8_t>(integer(stream, 1));
        const auto argument = static_cast<uint16_t>(integer(stream, 2));
        const bool pressed = integer(stream, 1) != 0;
        const auto initial = readState(stream);
        const bool initialA20 = integer(stream, 1) != 0;
        const auto expected = readState(stream);
        const bool expectedA20 = integer(stream, 1) != 0;
        const auto expectedResult = integer(stream, 2), count = integer(stream, 1);
        std::vector<std::pair<uint8_t, uint32_t>> expectedEffects;
        for (uint64_t i = 0; i < count; ++i) {
            const auto effect = static_cast<uint8_t>(integer(stream, 1));
            expectedEffects.emplace_back(effect, static_cast<uint32_t>(integer(stream, 4)));
        }
        for (bool restored : {false, true}) {
            KeyboardController controller(initial);
            if (restored) controller = KeyboardController(controller.snapshot());
            Effects actual; actual.a20 = initialA20;
            const auto result = action(controller, actual.bus(), kind, argument, pressed);
            const auto label = " at case " + std::to_string(index) + " action " + std::to_string(kind);
            require(controller.snapshot() == expected, "Keyboard controller state differs" + label);
            require(actual.a20 == expectedA20 && result == expectedResult, "Keyboard controller result differs" + label);
            require(actual.values == expectedEffects, "Keyboard controller ordered effects differ" + label);
        }
        effects += count;
    }
    if (!functionsOnly) portClock(stream);
    require(stream.peek() == std::char_traits<char>::eof(), "Keyboard controller oracle has trailing data");
    std::cout << "keyboard_controller_original=ok cases=" << cases << " ordered_effects=" << effects
              << " snapshot_restore=1 original_functions_changed=0 original_host_execution=0 app_cadence_claim=0\n";
}
void unit() {
    static_assert(static_cast<unsigned>(KeyboardHardwareKey::Last) == 103);
    KeyboardControllerSnapshot state; state.repeatPause = 1000; state.repeatRate = 63;
    KeyboardController controller(state);
    Effects effects; const auto bus = effects.bus();
    controller.addKey(KeyboardHardwareKey::Z, true, bus);
    require(controller.snapshot().repeatWait == 1000 && controller.snapshot().used == 1, "Initial physical make differs");
    controller.transferBuffer(bus);
    require(controller.readPort(0x60, bus) == 0x2c && controller.readPort(0x60, bus) == 0x2c,
            "Chained reads did not retain the port latch");
    for (unsigned i = 0; i < 999; ++i) controller.tick(bus);
    require(controller.snapshot().repeatWait == 1 && controller.snapshot().used == 0, "First repeat arrived early");
    controller.tick(bus);
    require(controller.snapshot().repeatWait == 63 && controller.snapshot().used == 1, "First repeat deadline differs");
    controller.addKey(KeyboardHardwareKey::Z, false, bus);
    require(controller.snapshot().repeatWait == 0 && controller.snapshot().repeatKey == KeyboardHardwareKey::None,
            "Physical release retained repeat");
    for (unsigned invalid = 0; invalid < 7; ++invalid) {
        auto bad = state;
        switch (invalid) {
        case 0: bad.used = 33; break;
        case 1: bad.pos = 32; break;
        case 2: bad.repeatKey = KeyboardHardwareKey::Last; break;
        case 3: bad.repeatWait = 1001; break;
        case 4: bad.repeatWait = 1; break;
        case 5: bad.repeatPause = 251; break;
        case 6: bad.command = static_cast<KeyboardControllerCommand>(4); break;
        }
        bool rejected = false;
        try {KeyboardController invalidController(bad);} catch (const std::invalid_argument&) {rejected = true;}
        require(rejected, "Invalid keyboard controller snapshot accepted");
    }
    constexpr std::array<uint32_t, 32> originalRates{33,37,42,46,50,54,58,63,67,75,83,92,100,109,118,125,
        133,149,167,182,200,217,233,250,270,303,333,370,400,435,476,500};
    unsigned rejectedRates = 0, acceptedRates = 0;
    for (uint32_t rate = 0; rate < 1002; ++rate) {
        auto restored = state;
        restored.repeatRate = rate;
        bool rejected = false;
        try {KeyboardController restoredController(restored);} catch (const std::invalid_argument&) {rejected = true;}
        const bool expected = std::find(originalRates.begin(), originalRates.end(), rate) != originalRates.end();
        require(!rejected == expected, "Restored typematic rate membership differs at " + std::to_string(rate));
        rejectedRates += rejected; acceptedRates += !rejected;
    }
    auto malformed = state; malformed.repeatRate = 34; malformed.repeatKey = KeyboardHardwareKey::Z;
    bool rejected = false;
    try {KeyboardController restoredController(malformed);} catch (const std::invalid_argument&) {rejected = true;}
    require(rejected && rejectedRates == 970 && acceptedRates == 32, "Review typematic-rate counterexample was accepted");
    std::cout << "keyboard_controller_unit=ok transfer=1 repeat=1 release=1 double_read=1 snapshot_rejections=7"
              << " rate_rejections=970 rate_values=32 review_rate34_rejected=1\n";
}
}
int main(int argc, char** argv) {
    try {
        if (argc == 3 && std::string(argv[1]) == "--original") original(argv[2], false);
        else if (argc == 3 && std::string(argv[1]) == "--functions") original(argv[2], true);
        else if (argc == 1) unit();
        else throw std::runtime_error("Unknown keyboard controller test arguments");
    } catch (const std::exception& error) {std::cerr << error.what() << '\n'; return 1;}
}
