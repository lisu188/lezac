#pragma once
#include "ui/input.hpp"
#include "gameplay/frame_controls.hpp"
#include <SDL.h>
#include <optional>
namespace lezac::app {
class InputMapper {
public:
    static ui::Key key(SDL_Keycode key);
    static ui::Key mainMenuKey(SDL_Keycode key, uint16_t modifiers);
    static bool isBufferedMenuKey(SDL_Keycode key, uint16_t modifiers = KMOD_NONE);
    std::optional<ui::Key> bufferedMenuKeyDown(SDL_Keycode key, uint16_t modifiers);
    std::optional<ui::Key> bufferedMenuKeyUp(SDL_Keycode key);
    static gameplay::FrameControls controlsFromKeyboard(const uint8_t* keys, int playerCount);
private:
    bool altStateObserved_ = false;
    bool altHeld_ = false;
    uint8_t altAccumulator_ = 0;
};
}
