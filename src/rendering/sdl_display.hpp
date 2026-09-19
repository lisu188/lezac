#pragma once

#include <memory>

struct SDL_Window;
struct SDL_Renderer;
struct SDL_Texture;

namespace lezac::rendering {

class Canvas;

class SdlDisplay {
public:
    SdlDisplay() = default;
    ~SdlDisplay();
    SdlDisplay(const SdlDisplay&) = delete;
    SdlDisplay& operator=(const SdlDisplay&) = delete;
    void initialize();
    void present(const Canvas& canvas);

private:
    struct WindowDeleter { void operator()(SDL_Window*) const; };
    struct RendererDeleter { void operator()(SDL_Renderer*) const; };
    struct TextureDeleter { void operator()(SDL_Texture*) const; };
    std::unique_ptr<SDL_Window, WindowDeleter> window_;
    std::unique_ptr<SDL_Renderer, RendererDeleter> renderer_;
    std::unique_ptr<SDL_Texture, TextureDeleter> texture_;
};

}
