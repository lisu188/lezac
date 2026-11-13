#include "rendering/sdl_display.hpp"
#include "rendering/canvas.hpp"

#include <SDL.h>
#include <stdexcept>
#include <string>
#include <utility>

namespace lezac::rendering {

void SdlDisplay::WindowDeleter::operator()(SDL_Window* value) const noexcept { SDL_DestroyWindow(value); }
void SdlDisplay::RendererDeleter::operator()(SDL_Renderer* value) const noexcept { SDL_DestroyRenderer(value); }
void SdlDisplay::TextureDeleter::operator()(SDL_Texture* value) const noexcept { SDL_DestroyTexture(value); }
SdlDisplay::~SdlDisplay() = default;

void SdlDisplay::initialize() {
    std::unique_ptr<SDL_Window, WindowDeleter> window(SDL_CreateWindow(
        "Larax & Zaco C++ reconstruction", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        kScreenW * 3, kScreenH * 3, SDL_WINDOW_SHOWN));
    if (!window) throw std::runtime_error(SDL_GetError());
    std::unique_ptr<SDL_Renderer, RendererDeleter> renderer(
        SDL_CreateRenderer(window.get(), -1, SDL_RENDERER_ACCELERATED));
    if (!renderer) {
        std::string acceleratedError = SDL_GetError();
        SDL_ClearError();
        renderer.reset(SDL_CreateRenderer(window.get(), -1, SDL_RENDERER_SOFTWARE));
        if (!renderer) {
            throw std::runtime_error(std::string(SDL_GetError()) +
                                     " (accelerated renderer failed: " + acceleratedError + ")");
        }
    }
    if (SDL_RenderSetLogicalSize(renderer.get(), kScreenW, kScreenH) != 0) {
        throw std::runtime_error(SDL_GetError());
    }
    std::unique_ptr<SDL_Texture, TextureDeleter> texture(SDL_CreateTexture(
        renderer.get(), SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_STREAMING, kScreenW, kScreenH));
    if (!texture) throw std::runtime_error(SDL_GetError());

    // Replace a complete display, releasing old children before their SDL parents.
    texture_ = std::move(texture);
    renderer_ = std::move(renderer);
    window_ = std::move(window);
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
