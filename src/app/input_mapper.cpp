#include "app/input_mapper.hpp"
namespace lezac::app {
bool InputMapper::isBufferedMenuKey(SDL_Keycode key) {
    // Modifiers and locks do not add a character to the original BIOS buffer.
    switch (key) {
        case SDLK_UNKNOWN:
        case SDLK_LSHIFT: case SDLK_RSHIFT:
        case SDLK_LCTRL: case SDLK_RCTRL:
        case SDLK_LALT: case SDLK_RALT:
        case SDLK_LGUI: case SDLK_RGUI:
        case SDLK_CAPSLOCK: case SDLK_NUMLOCKCLEAR: case SDLK_SCROLLLOCK:
            return false;
        default:
            return true;
    }
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
