#include "rendering/game_renderer.hpp"
#include "resources/asset_catalog.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace lezac;
int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("Expected original view initialization oracle");
        std::ifstream input(argv[1], std::ios::binary);
        const auto byte = [&]() {
            const int value = input.get();
            if (value < 0) throw std::runtime_error("Missing or truncated initialization oracle");
            return static_cast<uint8_t>(value);
        };
        for (const char expected : std::string("LZVGIN01"))
            if (byte() != expected) throw std::runtime_error("Initialization oracle version differs");
        if (byte() != 2 || byte() != 0 || byte() != 0 || byte() != 0)
            throw std::runtime_error("Initialization oracle domain differs");
        const auto assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
        unsigned compared = 0, differences = 0, ownershipDifferences = 0;
        for (int players : {1, 2}) {
            if (byte() != players) throw std::runtime_error("Initialization player count differs");
            std::vector<uint8_t> expected(64000);
            for (auto& value : expected) value = byte();
            for (int phase : {0, 1}) {
                auto palette = assets.palette();
                if (phase) for (auto& entry : palette) {
                    const auto rotate = [](uint8_t component, unsigned step) {
                        const auto value = static_cast<uint8_t>(((component >> 2) + step) & 63);
                        return static_cast<uint8_t>((value << 2) | (value >> 4));
                    };
                    entry.r = rotate(entry.r, 9);
                    entry.g = rotate(entry.g, 15);
                    entry.b = rotate(entry.b, 21);
                }
                rendering::PresentationState presentation;
                presentation.setPalette(palette);
                rendering::Canvas canvas;
                canvas.clear(0xffb63892u);
                rendering::TextRenderer text(canvas, presentation.palette(), assets.fontSprites());
                rendering::GameRenderer renderer(canvas, text, assets, presentation);
                renderer.initializePlayfield(players, 320);
                for (size_t at = 0; at < expected.size(); ++at) {
                    const auto& entry = palette[expected[at]];
                    const uint32_t color = 0xff000000u | (uint32_t{entry.r} << 16) | (uint32_t{entry.g} << 8) | entry.b;
                    differences += canvas.pixels()[at] != color;
                    ownershipDifferences += canvas.indexedPixels()[at] != 1 || canvas.paletteIndices()[at] != expected[at];
                    ++compared;
                }
            }
        }
        if (input.get() >= 0) throw std::runtime_error("Initialization oracle has trailing bytes");
        std::cout << "render_view_initialization=" << (differences || ownershipDifferences ? "failed" : "ok")
                  << " cases=2 palette_modes=2 pixels=" << compared << " differences=" << differences
                  << " ownership_differences=" << ownershipDifferences << '\n';
        return differences || ownershipDifferences ? 1 : 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
