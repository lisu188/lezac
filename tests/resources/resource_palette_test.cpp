#include "resources/palette.hpp"

#include <cstdio>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

int main() {
    if (lezac::resources::vga6To8(0) != 0 ||
        lezac::resources::vga6To8(15) != 60 ||
        lezac::resources::vga6To8(16) != 65 ||
        lezac::resources::vga6To8(17) != 69 ||
        lezac::resources::vga6To8(32) != 130 ||
        lezac::resources::vga6To8(63) != 255) return 1;

    std::vector<uint8_t> raw(770, 0);
    raw[2] = 0;
    raw[3] = 32;
    raw[4] = 63;
    raw[2 + 255 * 3] = 15;
    raw[2 + 255 * 3 + 1] = 16;
    raw[2 + 255 * 3 + 2] = 17;

    const auto palette = lezac::resources::loadPalette(raw, 2);
    if (palette[0].r != 0 || palette[0].g != 130 || palette[0].b != 255) return 2;
    if (palette[255].r != 60 || palette[255].g != 65 || palette[255].b != 69) return 3;

    bool truncated = false;
    try {
        lezac::resources::loadPalette(std::vector<uint8_t>(767), 0);
    } catch (const std::runtime_error&) {
        truncated = true;
    }
    if (!truncated) return 4;

    const std::string path = "resource_palette_test.tmp.json";
    {
        std::ofstream out(path);
        out << "{\"entries\":[";
        for (int i = 0; i < 256; ++i) {
            if (i) out << ',';
            out << "{\"rgb8\":[" << i << ',' << ((i + 1) & 255) << ','
                << ((i + 2) & 255) << "]}";
        }
        out << "]}";
    }

    const auto jsonPalette = lezac::resources::loadPaletteFile(path);
    std::remove(path.c_str());
    if (jsonPalette[0].r != 0 || jsonPalette[0].g != 1 || jsonPalette[0].b != 2) return 5;
    if (jsonPalette[255].r != 255 || jsonPalette[255].g != 0 || jsonPalette[255].b != 1) return 6;

    std::cout << "resource_palette=ok raw=256 json=256 truncation=1\n";
    return 0;
}
