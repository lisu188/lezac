#pragma once

#include <array>
#include <cstdint>
#include <functional>
#include <stdexcept>

namespace lezac::core {

// Numeric identities are the pinned host's physical-key tokens, not scan bytes.
enum class KeyboardHardwareKey : uint8_t {
    None, Digit1, Digit2, Digit3, Digit4, Digit5, Digit6, Digit7, Digit8, Digit9, Digit0,
    Q, W, E, R, T, Y, U, I, O, P, A, S, D, F, G, H, J, K, L, Z, X, C, V, B, N, M,
    F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12,
    Escape, Tab, Backspace, Enter, Space, LeftAlt, RightAlt, LeftControl, RightControl,
    LeftShift, RightShift, CapsLock, ScrollLock, NumLock,
    Grave, Minus, Equals, Backslash, LeftBracket, RightBracket, Semicolon, Quote,
    Period, Comma, Slash, Extra, PrintScreen, Pause, Insert, Home, PageUp, Delete,
    End, PageDown, Left, Up, Down, Right,
    Keypad1, Keypad2, Keypad3, Keypad4, Keypad5, Keypad6, Keypad7, Keypad8, Keypad9,
    Keypad0, KeypadDivide, KeypadMultiply, KeypadMinus, KeypadPlus, KeypadEnter, KeypadPeriod, Last
};
enum class KeyboardControllerCommand : uint8_t {None, SetLeds, SetTypeRate, SetOutPort};
struct KeyboardControllerSnapshot {
    std::array<uint8_t, 32> buffer{};
    uint32_t used = 0, pos = 0;
    KeyboardHardwareKey repeatKey = KeyboardHardwareKey::None;
    uint32_t repeatWait = 0, repeatPause = 500, repeatRate = 33;
    KeyboardControllerCommand command = KeyboardControllerCommand::None;
    uint8_t port60 = 0;
    bool port60Changed = false, active = true, scanning = true, scheduled = false;
    uint8_t port61 = 0;
    bool operator==(const KeyboardControllerSnapshot&) const = default;
};
struct KeyboardControllerBus {
    std::function<void(float)> scheduleTransfer;
    std::function<void()> removeTransfers;
    std::function<void()> activateIrq1;
    std::function<bool()> a20Enabled;
    std::function<void(bool)> setA20, setGate2;
    std::function<void(uint8_t)> setSpeakerType;
};

// VGA/AT controller behavior; PIC time, memory mapping and sound sinks belong to the caller.
class KeyboardController {
public:
    explicit KeyboardController(KeyboardControllerSnapshot state = {}) : state_(state) {
        if (state.used > 32 || state.pos >= 32 || state.repeatKey >= KeyboardHardwareKey::Last ||
            state.repeatWait > 1000 || (state.repeatWait && state.repeatKey == KeyboardHardwareKey::None) ||
            state.repeatPause < 250 || state.repeatPause > 1000 || state.repeatPause % 250 ||
            state.repeatRate < 33 || state.repeatRate > 500 || state.command > KeyboardControllerCommand::SetOutPort)
            throw std::invalid_argument("Keyboard controller state differs from the pinned profile");
    }
    const KeyboardControllerSnapshot& snapshot() const noexcept {return state_;}
    void clearBuffer(const KeyboardControllerBus& bus) {
        state_.used = state_.pos = 0;
        bus.removeTransfers();
        state_.scheduled = false;
    }
    void transferBuffer(const KeyboardControllerBus& bus) {
        state_.scheduled = false;
        if (!state_.used) return;
        setPort60(state_.buffer[state_.pos], bus);
        state_.pos = (state_.pos + 1u) % 32u;
        --state_.used;
    }
    void addKey(KeyboardHardwareKey key, bool pressed, const KeyboardControllerBus& bus) {
        const auto token = static_cast<unsigned>(key);
        if (key == KeyboardHardwareKey::None || key >= KeyboardHardwareKey::Last)
            throw std::domain_error("Unsupported physical keyboard token");
        if (key == KeyboardHardwareKey::PrintScreen) return;
        if (key == KeyboardHardwareKey::Pause) {
            addBuffer(0xe1, bus);
            addBuffer(static_cast<uint8_t>(29u | (pressed ? 0u : 128u)), bus);
            addBuffer(static_cast<uint8_t>(69u | (pressed ? 0u : 128u)), bus);
            return;
        }
        auto scan = scans[token];
        if (pressed) {
            state_.repeatWait = state_.repeatKey == key ? state_.repeatRate : state_.repeatPause;
            state_.repeatKey = key;
        } else {
            if (state_.repeatKey == key) {state_.repeatKey = KeyboardHardwareKey::None; state_.repeatWait = 0;}
            scan = static_cast<uint8_t>(scan + 128u);
        }
        if (key == KeyboardHardwareKey::RightAlt || key == KeyboardHardwareKey::RightControl ||
            (key >= KeyboardHardwareKey::Insert && key <= KeyboardHardwareKey::Right) ||
            key == KeyboardHardwareKey::KeypadDivide || key == KeyboardHardwareKey::KeypadEnter)
            addBuffer(0xe0, bus);
        addBuffer(scan, bus);
    }
    void tick(const KeyboardControllerBus& bus) {
        if (state_.repeatWait && !--state_.repeatWait) addKey(state_.repeatKey, true, bus);
    }
    uint8_t readPort(uint16_t port, const KeyboardControllerBus& bus) {
        switch (port) {
        case 0x60:
            state_.port60Changed = false;
            if (!state_.scheduled && state_.used) schedule(bus);
            return state_.port60;
        case 0x61: state_.port61 ^= 0x30; return state_.port61;
        case 0x64: return static_cast<uint8_t>(0x1cu | (state_.port60Changed ? 1u : 0u));
        default: throw std::domain_error("Unsupported keyboard port read");
        }
    }
    void writePort(uint16_t port, uint8_t value, const KeyboardControllerBus& bus) {
        if (port == 0x60) {writePort60(value, bus); return;}
        if (port == 0x61) {
            const auto changed = state_.port61 ^ value;
            if (changed & 3u) {
                if (changed & 1u) bus.setGate2((value & 1u) != 0);
                bus.setSpeakerType(static_cast<uint8_t>(value & 3u));
            }
            state_.port61 = value;
            return;
        }
        if (port != 0x64) throw std::domain_error("Unsupported keyboard port write");
        switch (value) {
        case 0xae:
            state_.active = true;
            if (state_.used && !state_.scheduled && !state_.port60Changed) schedule(bus);
            break;
        case 0xad: state_.active = false; break;
        case 0xd0: setPort60(bus.a20Enabled() ? 2 : 0, bus); break;
        case 0xd1: state_.command = KeyboardControllerCommand::SetOutPort; break;
        default: break;
        }
    }

private:
    void schedule(const KeyboardControllerBus& bus) {state_.scheduled = true; bus.scheduleTransfer(0.300f);}
    void setPort60(uint8_t value, const KeyboardControllerBus& bus) {
        state_.port60Changed = true; state_.port60 = value; bus.activateIrq1();
    }
    void addBuffer(uint8_t value, const KeyboardControllerBus& bus) {
        if (state_.used == 32) return;
        state_.buffer[(state_.pos + state_.used) % 32u] = value;
        ++state_.used;
        if (!state_.scheduled && !state_.port60Changed) schedule(bus);
    }
    void writePort60(uint8_t value, const KeyboardControllerBus& bus) {
        switch (state_.command) {
        case KeyboardControllerCommand::None:
            clearBuffer(bus);
            switch (value) {
            case 0xed: state_.command = KeyboardControllerCommand::SetLeds; break;
            case 0xf3: state_.command = KeyboardControllerCommand::SetTypeRate; break;
            case 0xf4: state_.scanning = true; break;
            case 0xf5:
            case 0xf6: state_.scanning = false; break;
            default: break;
            }
            addBuffer(0xfa, bus);
            return;
        case KeyboardControllerCommand::SetOutPort:
            bus.setA20((value & 2u) != 0); state_.command = KeyboardControllerCommand::None;
            return;
        case KeyboardControllerCommand::SetTypeRate:
            state_.repeatPause = 250u * (1u + ((value >> 5) & 3u));
            state_.repeatRate = rates[value & 31u];
            break;
        case KeyboardControllerCommand::SetLeds: break;
        }
        state_.command = KeyboardControllerCommand::None;
        clearBuffer(bus);
        addBuffer(0xfa, bus);
    }
    inline static constexpr std::array<uint8_t, 103> scans{
        0,2,3,4,5,6,7,8,9,10,11,16,17,18,19,20,21,22,23,24,25,30,31,32,33,34,35,36,37,38,
        44,45,46,47,48,49,50,59,60,61,62,63,64,65,66,67,68,87,88,1,15,14,28,57,56,56,29,29,42,54,
        58,70,69,41,12,13,43,26,27,39,40,52,51,53,86,0,0,82,71,73,83,79,81,75,72,80,77,
        79,80,81,75,76,77,71,72,73,82,53,55,74,78,28,83};
    inline static constexpr std::array<uint16_t, 32> rates{
        33,37,42,46,50,54,58,63,67,75,83,92,100,109,118,125,133,149,167,182,200,217,233,
        250,270,303,333,370,400,435,476,500};
    KeyboardControllerSnapshot state_;
};

}
