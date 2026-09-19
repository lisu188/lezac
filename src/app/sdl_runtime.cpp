#include "app/sdl_runtime.hpp"

#include <SDL.h>
#include <stdexcept>

namespace lezac::app {

SdlRuntime::~SdlRuntime() { SDL_Quit(); }

void SdlRuntime::initialize() {
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_TIMER) != 0) {
        throw std::runtime_error(SDL_GetError());
    }
}

}
