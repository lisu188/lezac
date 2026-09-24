#include "app/input_mapper.hpp"
namespace lezac::app {
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
