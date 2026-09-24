#pragma once
#include "ui/input.hpp"
#include "gameplay/frame_controls.hpp"
#include <SDL.h>
namespace lezac::app {
class InputMapper {
public:
    static ui::Key key(SDL_Keycode key);
    static gameplay::FrameControls controlsFromKeyboard(const uint8_t* keys, int playerCount);
};
}
