#include "rendering/sdl_display.hpp"
#include "rendering/canvas.hpp"

#include <SDL.h>
#include <stdexcept>
#include <string>

namespace lezac::rendering {

void SdlDisplay::WindowDeleter::operator()(SDL_Window* value) const { SDL_DestroyWindow(value); }
void SdlDisplay::RendererDeleter::operator()(SDL_Renderer* value) const { SDL_DestroyRenderer(value); }
void SdlDisplay::TextureDeleter::operator()(SDL_Texture* value) const { SDL_DestroyTexture(value); }
SdlDisplay::~SdlDisplay() = default;

void SdlDisplay::initialize() {
    window_.reset(SDL_CreateWindow("Larax & Zaco C++ reconstruction",
                                  SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                                  kScreenW * 3, kScreenH * 3, SDL_WINDOW_SHOWN));
    if (!window_) throw std::runtime_error(SDL_GetError());
    renderer_.reset(SDL_CreateRenderer(window_.get(), -1, SDL_RENDERER_ACCELERATED));
    if (!renderer_) {
        std::string acceleratedError = SDL_GetError();
        SDL_ClearError();
        renderer_.reset(SDL_CreateRenderer(window_.get(), -1, SDL_RENDERER_SOFTWARE));
        if (!renderer_) {
            throw std::runtime_error(std::string(SDL_GetError()) +
                                     " (accelerated renderer failed: " + acceleratedError + ")");
        }
    }
    if (SDL_RenderSetLogicalSize(renderer_.get(), kScreenW, kScreenH) != 0) {
        throw std::runtime_error(SDL_GetError());
    }
    texture_.reset(SDL_CreateTexture(renderer_.get(), SDL_PIXELFORMAT_ARGB8888,
                                    SDL_TEXTUREACCESS_STREAMING, kScreenW, kScreenH));
    if (!texture_) throw std::runtime_error(SDL_GetError());
}

void SdlDisplay::present(const Canvas& canvas) {
    if (SDL_UpdateTexture(texture_.get(), nullptr, canvas.pixels().data(),
                          kScreenW * sizeof(uint32_t)) != 0) {
        throw std::runtime_error(SDL_GetError());
    }
    if (SDL_RenderClear(renderer_.get()) != 0) {
        throw std::runtime_error(SDL_GetError());
    }
    if (SDL_RenderCopy(renderer_.get(), texture_.get(), nullptr, nullptr) != 0) {
        throw std::runtime_error(SDL_GetError());
    }
    SDL_RenderPresent(renderer_.get());
}

}
