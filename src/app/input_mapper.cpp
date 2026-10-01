#include "app/input_mapper.hpp"
#include <utility>
namespace lezac::app {
bool InputMapper::isBufferedMenuKey(SDL_Keycode key, uint16_t modifiers) {
    // Modifiers and locks do not add a character to the original BIOS buffer.
    switch (key) {
        case SDLK_UNKNOWN:
        case SDLK_LSHIFT: case SDLK_RSHIFT:
        case SDLK_LCTRL: case SDLK_RCTRL:
        case SDLK_LALT: case SDLK_RALT:
        case SDLK_LGUI: case SDLK_RGUI:
        case SDLK_CAPSLOCK: case SDLK_NUMLOCKCLEAR: case SDLK_SCROLLLOCK:
        case SDLK_F11: case SDLK_F12:
            return false;
        default: break;
    }
    if (modifiers & KMOD_ALT) {
        if (key == SDLK_TAB || key == SDLK_RETURN ||
            (key >= SDLK_KP_1 && key <= SDLK_KP_0)) return false;
    } else if (modifiers & KMOD_CTRL) {
        switch (key) {
            case SDLK_1: case SDLK_3: case SDLK_4: case SDLK_5:
            case SDLK_7: case SDLK_8: case SDLK_9: case SDLK_0:
            case SDLK_EQUALS: case SDLK_SEMICOLON: case SDLK_QUOTE:
            case SDLK_BACKQUOTE: case SDLK_COMMA: case SDLK_PERIOD: case SDLK_SLASH:
                return false;
            default: break;
        }
    }
    return true;
}

std::optional<ui::Key> InputMapper::bufferedMenuKeyDown(SDL_Keycode code, uint16_t modifiers) {
    if (code == SDLK_LALT || code == SDLK_RALT) {
        altStateObserved_ = true;
        altHeld_ = true;
        return std::nullopt;
    }
    if (altStateObserved_)
        modifiers = static_cast<uint16_t>((modifiers & ~KMOD_ALT) | (altHeld_ ? KMOD_LALT : 0));
    if ((modifiers & KMOD_ALT) && code >= SDLK_KP_1 && code <= SDLK_KP_0) {
        const int digit = code == SDLK_KP_0 ? 0 : code - SDLK_KP_1 + 1;
        altAccumulator_ = static_cast<uint8_t>(altAccumulator_ * 10 + digit);
        return std::nullopt;
    }
    if (!isBufferedMenuKey(code, modifiers)) return std::nullopt;
    return mainMenuKey(code, modifiers);
}

std::optional<ui::Key> InputMapper::bufferedMenuKeyUp(SDL_Keycode code) {
    if (code != SDLK_LALT && code != SDLK_RALT) return std::nullopt;
    // The observed BIOS clears its one Alt flag on either release, not the last.
    altStateObserved_ = true;
    altHeld_ = false;
    const uint8_t character = std::exchange(altAccumulator_, 0);
    if (character == 0) return std::nullopt;
    return static_cast<ui::Key>(character);
}
ui::Key InputMapper::key(SDL_Keycode key) {
    if (key >= SDLK_a && key <= SDLK_z) return static_cast<ui::Key>(static_cast<int>(ui::Key::A) + key - SDLK_a);
    switch (key) {
        case SDLK_BACKSPACE: return ui::Key::Backspace;
        case SDLK_RETURN: return ui::Key::Return;
        case SDLK_ESCAPE: return ui::Key::Escape;
        case SDLK_SPACE: return ui::Key::Space;
        case SDLK_1: return ui::Key::One;
        case SDLK_2: return ui::Key::Two;
        case SDLK_KP_ENTER: return ui::Key::KeypadEnter;
        case SDLK_F5: return ui::Key::F5;
        case SDLK_PAGEUP: return ui::Key::PageUp;
        case SDLK_PAGEDOWN: return ui::Key::PageDown;
        case SDLK_RCTRL: return ui::Key::RightControl;
        case SDLK_KP_0: return ui::Key::Keypad0;
        case SDLK_INSERT: return ui::Key::Insert;
        default: return ui::Key::Unknown;
    }
}

ui::Key InputMapper::mainMenuKey(SDL_Keycode code, uint16_t modifiers) {
    const bool shift = (modifiers & KMOD_SHIFT) != 0;
    const bool caps = (modifiers & KMOD_CAPS) != 0;
    if (modifiers & KMOD_ALT) {
        // CRT.ReadKey exposes the second extended byte as a menu character.
        switch (code) {
            case SDLK_F2: return ui::Key::I; // BIOS scan 0x69.
            case SDLK_F5: return ui::Key::L; // BIOS scan 0x6c.
            case SDLK_3: return ui::Key::Z;  // BIOS scan 0x7a.
            default: return ui::Key::Unknown;
        }
    }
    if (modifiers & KMOD_CTRL)
        return code == SDLK_ESCAPE ? ui::Key::Escape : ui::Key::Unknown;
    if (code >= SDLK_a && code <= SDLK_z && shift != caps) return ui::Key::Unknown;
    if ((code == SDLK_1 || code == SDLK_2) && shift) return ui::Key::Unknown;
    if (code == SDLK_KP_1 || code == SDLK_KP_2) {
        const bool num = (modifiers & KMOD_NUM) != 0;
        // Original physical-key captures select a digit with either flag set.
        if (!num && !shift) return ui::Key::Unknown;
        return code == SDLK_KP_1 ? ui::Key::One : ui::Key::Two;
    }
    return key(code);
}

gameplay::FrameControls InputMapper::controlsFromKeyboard(const uint8_t* keys, int playerCount) {
    gameplay::FrameControls controls;
    // Original banks at 1000:6175/61DE. Arrows remain a single-player alias.
    controls.p1Left = keys[SDL_SCANCODE_Z] ||
                      (playerCount == 1 && keys[SDL_SCANCODE_LEFT]);
    controls.p1Right = keys[SDL_SCANCODE_X] ||
                       (playerCount == 1 && keys[SDL_SCANCODE_RIGHT]);
    controls.p1Jump = keys[SDL_SCANCODE_M] ||
                      (playerCount == 1 && keys[SDL_SCANCODE_UP]);
    controls.p1Down = keys[SDL_SCANCODE_C] ||
                      (playerCount == 1 && keys[SDL_SCANCODE_DOWN]);
    controls.p2Left = playerCount > 1 && keys[SDL_SCANCODE_LEFT];
    controls.p2Right = playerCount > 1 && keys[SDL_SCANCODE_RIGHT];
    controls.p2Jump = playerCount > 1 && keys[SDL_SCANCODE_UP];
    controls.p2Down = playerCount > 1 && keys[SDL_SCANCODE_DOWN];
    return controls;
}
}
