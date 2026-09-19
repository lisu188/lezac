#pragma once

#include <cstdint>

namespace lezac::ui {
// Domain keys keep character identity separate from the platform event system.
enum class Key : int32_t {
    Unknown = 0, Backspace = 8, Return = 13, Escape = 27, Space = 32,
    One = '1', Two = '2', A = 'a', B = 'b', C = 'c', D = 'd', E = 'e',
    F = 'f', G = 'g', H = 'h', I = 'i', J = 'j', K = 'k', L = 'l',
    M = 'm', N = 'n', O = 'o', P = 'p', Q = 'q', R = 'r', S = 's',
    T = 't', U = 'u', V = 'v', W = 'w', X = 'x', Y = 'y', Z = 'z',
    KeypadEnter = 256, F5, PageUp, PageDown, RightControl, Keypad0, Insert,
};
struct KeyInput { Key key = Key::Unknown; bool repeat = false; };
}
