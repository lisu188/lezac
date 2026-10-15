#include "rendering/canvas.hpp"
#include "rendering/sdl_display.hpp"
#include <SDL.h>
#include <array>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <type_traits>

struct SDL_Window { bool alive = false; };
struct SDL_Renderer { bool alive = false; SDL_Window* window = nullptr; };
struct SDL_Texture { bool alive = false; SDL_Renderer* renderer = nullptr; };

namespace {
enum class Failure { None, Window, BothRenderers, Accelerated, LogicalSize, Texture, Update, Clear, Copy };
Failure failure = Failure::None;
std::array<SDL_Window, 64> windows;
std::array<SDL_Renderer, 64> renderers;
std::array<SDL_Texture, 64> textures;
size_t nextWindow = 0, nextRenderer = 0, nextTexture = 0;
SDL_Texture* presentedTexture = nullptr;
int fallbackCalls = 0, clears = 0, presents = 0;

void require(bool value) {
    if (!value) throw std::runtime_error("SDL ownership test failed");
}

void releaseCheck(bool value) {
    if (!value) std::abort();
}

void liveCounts(size_t expected) {
    size_t w = 0, r = 0, t = 0;
    for (const auto& item : windows) w += item.alive;
    for (const auto& item : renderers) r += item.alive;
    for (const auto& item : textures) t += item.alive;
    require(w == expected && r == expected && t == expected);
}

template <typename Action>
void rejects(Action action) {
    try { action(); }
    catch (const std::runtime_error& error) {
        require(std::string_view{error.what()}.contains("test-error"));
        return;
    }
    throw std::runtime_error("SDL failure was accepted");
}
}

SDL_Window* SDL_CreateWindow(const char*, int, int, int width, int height, Uint32 flags) {
    require(width == 960 && height == 600 && flags == SDL_WINDOW_SHOWN);
    if (failure == Failure::Window) return nullptr;
    require(nextWindow < windows.size());
    auto* window = &windows[nextWindow++];
    window->alive = true;
    return window;
}

SDL_Renderer* SDL_CreateRenderer(SDL_Window* window, int index, Uint32 flags) {
    require(window && window->alive && index == -1);
    if (flags == SDL_RENDERER_SOFTWARE) ++fallbackCalls;
    else require(flags == SDL_RENDERER_ACCELERATED);
    if (failure == Failure::BothRenderers ||
        (failure == Failure::Accelerated && flags == SDL_RENDERER_ACCELERATED)) return nullptr;
    require(nextRenderer < renderers.size());
    auto* renderer = &renderers[nextRenderer++];
    *renderer = {true, window};
    return renderer;
}

SDL_Texture* SDL_CreateTexture(SDL_Renderer* renderer, Uint32 format, int access, int width, int height) {
    require(renderer && renderer->alive && renderer->window->alive);
    require(format == SDL_PIXELFORMAT_ARGB8888 && access == SDL_TEXTUREACCESS_STREAMING);
    require(width == 320 && height == 200);
    if (failure == Failure::Texture) return nullptr;
    require(nextTexture < textures.size());
    auto* texture = &textures[nextTexture++];
    *texture = {true, renderer};
    return texture;
}

void SDL_DestroyWindow(SDL_Window* window) {
    releaseCheck(window && window->alive);
    for (const auto& renderer : renderers) releaseCheck(!renderer.alive || renderer.window != window);
    window->alive = false;
}
void SDL_DestroyRenderer(SDL_Renderer* renderer) {
    releaseCheck(renderer && renderer->alive && renderer->window->alive);
    for (const auto& texture : textures) releaseCheck(!texture.alive || texture.renderer != renderer);
    renderer->alive = false;
}
void SDL_DestroyTexture(SDL_Texture* texture) {
    releaseCheck(texture && texture->alive && texture->renderer->alive && texture->renderer->window->alive);
    texture->alive = false;
}
int SDL_RenderSetLogicalSize(SDL_Renderer* renderer, int width, int height) {
    require(renderer && renderer->alive && width == 320 && height == 200);
    return failure == Failure::LogicalSize ? -1 : 0;
}
int SDL_UpdateTexture(SDL_Texture* texture, const SDL_Rect*, const void* pixels, int pitch) {
    require(texture && texture->alive && pixels && pitch == 320 * sizeof(uint32_t));
    presentedTexture = texture;
    return failure == Failure::Update ? -1 : 0;
}
int SDL_RenderClear(SDL_Renderer* renderer) {
    require(renderer && renderer->alive);
    return failure == Failure::Clear ? -1 : 0;
}
int SDL_RenderCopy(SDL_Renderer* renderer, SDL_Texture* texture, const SDL_Rect*, const SDL_Rect*) {
    require(renderer && renderer->alive && texture && texture->alive && texture->renderer == renderer);
    return failure == Failure::Copy ? -1 : 0;
}
void SDL_RenderPresent(SDL_Renderer* renderer) { require(renderer && renderer->alive); ++presents; }
const char* SDL_GetError() { return "test-error"; }
void SDL_ClearError() { ++clears; }

static_assert(!std::is_copy_constructible_v<lezac::rendering::SdlDisplay>);
static_assert(!std::is_move_constructible_v<lezac::rendering::SdlDisplay>);

int main(int argc, char** argv) {
    const lezac::rendering::Canvas canvas;
    if (argc == 2 && std::string_view{argv[1]} == "--repeat-only") {
        {
            lezac::rendering::SdlDisplay display;
            display.initialize();
            display.initialize();
            display.present(canvas);
            liveCounts(1);
        }
        liveCounts(0);
        std::cout << "sdl_display_repeated_initialization=ok child_before_parent=1\n";
        return 0;
    }
    require(argc == 1);
    constexpr std::array constructionFailures{Failure::Window, Failure::BothRenderers,
        Failure::LogicalSize, Failure::Texture};
    for (const auto mode : constructionFailures) {
        lezac::rendering::SdlDisplay display;
        failure = mode;
        rejects([&] { display.initialize(); });
        liveCounts(0);
    }
    failure = Failure::None;
    {
        lezac::rendering::SdlDisplay display;
        display.initialize();
        display.present(canvas);
        liveCounts(1);
        for (const auto mode : constructionFailures) {
            auto* previous = presentedTexture;
            failure = mode;
            rejects([&] { display.initialize(); });
            liveCounts(1);
            failure = Failure::None;
            display.present(canvas);
            require(presentedTexture == previous);
        }
        for (int repeat = 0; repeat < 8; ++repeat) {
            auto* previous = presentedTexture;
            display.initialize();
            liveCounts(1);
            display.present(canvas);
            require(presentedTexture != previous && !previous->alive);
        }
        const int fallbackBefore = fallbackCalls, clearsBefore = clears;
        failure = Failure::Accelerated;
        display.initialize();
        display.present(canvas);
        require(fallbackCalls == fallbackBefore + 1 && clears == clearsBefore + 1);
        liveCounts(1);
        for (const auto mode : {Failure::Update, Failure::Clear, Failure::Copy}) {
            const int before = presents;
            failure = mode;
            rejects([&] { display.present(canvas); });
            require(presents == before);
            liveCounts(1);
        }
        failure = Failure::None;
        display.present(canvas);
    }
    liveCounts(0);
    std::cout << "sdl_display_ownership=ok initial_failures=4 replacement_failures=4 repeated_success=8 "
                 "presentation_failures=3 fallback=1 child_before_parent=1 production_app=0\n";
}
