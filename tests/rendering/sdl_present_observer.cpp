#include <SDL.h>
#include <dlfcn.h>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <vector>

extern "C" void SDL_RenderPresent(SDL_Renderer* renderer) {
    using Present = void (*)(SDL_Renderer*);
    static const auto realPresent = reinterpret_cast<Present>(dlsym(RTLD_NEXT, "SDL_RenderPresent"));
    int width = 0, height = 0;
    if (!realPresent || SDL_GetRendererOutputSize(renderer, &width, &height) != 0 || width != 960 || height != 600)
        std::abort();
    std::vector<uint32_t> output(static_cast<size_t>(width * height));
    if (SDL_RenderReadPixels(renderer, nullptr, SDL_PIXELFORMAT_ARGB8888, output.data(), width * 4) != 0)
        std::abort();
    std::vector<uint32_t> native(320 * 200);
    uint64_t hash = 1469598103934665603ull;
    for (int y = 0; y < 200; ++y) for (int x = 0; x < 320; ++x) {
        const uint32_t color = output[static_cast<size_t>(y * 3 * width + x * 3)];
        for (int dy = 0; dy < 3; ++dy) for (int dx = 0; dx < 3; ++dx)
            if (output[static_cast<size_t>((y * 3 + dy) * width + x * 3 + dx)] != color) std::abort();
        native[static_cast<size_t>(y * 320 + x)] = color;
        hash = (hash ^ color) * 1099511628211ull;
    }
    const char* path = std::getenv("LEZAC_PRESENT_LAST_FRAME");
    FILE* file = path ? std::fopen(path, "wb") : nullptr;
    if (!file || std::fwrite(native.data(), sizeof(uint32_t), native.size(), file) != native.size() || std::fclose(file))
        std::abort();
    static unsigned count = 0;
    std::printf("sdl_present_observation sequence=%u hash=%llu pixels=64000 exact_scale=3\n", ++count,
                static_cast<unsigned long long>(hash));
    std::fflush(stdout);
    realPresent(renderer);
}
