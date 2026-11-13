#include "rendering/canvas.hpp"
#include "rendering/color.hpp"
#include <iostream>
#include <stdexcept>

using namespace lezac;

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
}

int main() {
    try {
        rendering::Canvas canvas;
        resources::Palette palette{};
        for (size_t i = 0; i < palette.size(); ++i)
            palette[i] = {static_cast<uint8_t>(i), static_cast<uint8_t>(i * 17), static_cast<uint8_t>(255 - i)};
        for (int y = 0; y < rendering::kScreenH; ++y) for (int x = 0; x < rendering::kScreenW; ++x) {
            const auto at = static_cast<size_t>(y * rendering::kScreenW + x);
            if (at % 5 == 0) canvas.pixel(x, y, 0xff123456u);
            else canvas.indexedPixel(x, y, static_cast<uint8_t>(at), 0xffabcdefu);
        }
        const auto indices = canvas.paletteIndices();
        const auto indexed = canvas.indexedPixels();
        canvas.setClip(100, 100, 101, 101);
        require(canvas.resolvePalette(palette), "changed palette was not detected");
        for (size_t at = 0; at < canvas.pixels().size(); ++at)
            require(canvas.pixels()[at] == (indexed[at] ? rendering::argb(palette, indices[at]) : 0xff123456u),
                    "palette refresh clipped indexed pixels or changed direct RGB");
        require(canvas.paletteIndices() == indices && canvas.indexedPixels() == indexed,
                "palette refresh lost index ownership");
        require(!canvas.resolvePalette(palette), "unchanged palette requested another presentation");
        const auto before = canvas.pixels();
        canvas.pixel(0, 0, 0xff000000u);
        require(canvas.pixels() == before, "palette refresh reset the drawing clip");
        canvas.resetClip();
        canvas.pixel(1, 0, 0xff765432u);
        palette[1] = {12, 34, 56};
        require(canvas.resolvePalette(palette), "second palette write was not detected");
        require(canvas.pixels()[1] == 0xff765432u && canvas.indexedPixels()[1] == 0,
                "direct RGB overwrite kept old palette ownership");
        canvas.clear(0xff112233u);
        require(!canvas.resolvePalette(palette), "cleared canvas retained indexed ownership");
        std::cout << "canvas_palette=ok indices=256 pixels=64000 rgb_preserved=1 ownership_preserved=1 clip_preserved=1 idempotent=1\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
