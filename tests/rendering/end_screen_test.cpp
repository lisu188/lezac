#include "rendering/game_renderer.hpp"
#include "ui/level_flow.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>

using namespace lezac;

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

void checkModels() {
    const std::array<std::array<uint32_t, 2>, 8> scores{{
        {{0, 0}}, {{1, 0}}, {{0, 1}}, {{10, 20}},
        {{0x7fffffffu, 0}}, {{0x80000000u, 0}}, {{0xffffffffu, 0}}, {{0x80000000u, 1}}}};
    const std::array<size_t, 8> counts{{2, 3, 3, 4, 3, 2, 2, 3}};
    for (size_t c = 0; c < scores.size(); ++c) {
        for (bool italian : {false, true}) {
            const auto lines = ui::LevelFlow::gameOverLines(italian, scores[c]);
            require(lines.size() == counts[c], "score count mismatch");
            require(lines[0].text == "GAME OVER" && lines[0].y == 77 &&
                    lines[0].cell == 11 && lines[0].glyphColor == 31 && lines[0].shadowColor == 25,
                    "game over title mismatch");
            require(lines[1].text == (italian ? "PUNTEGGIO FINALE" : "FINAL SCORE") &&
                    lines[1].y == 97 && lines[1].cell == 11 && lines[1].glyphColor == 244 &&
                    lines[1].shadowColor == 25, "final score heading mismatch");
            size_t index = 2;
            for (size_t p = 0; p < 2; ++p) {
                if (scores[c][p] == 0 || scores[c][p] >= 0x80000000u) continue;
                const auto& line = lines[index];
                require(line.text == (italian ? std::string("GIOCATORE") : std::string("PLAYER")) +
                            std::to_string(p + 1) + ": " + std::to_string(scores[c][p]) &&
                        line.y == 121 + static_cast<int>(index - 2) * 11 && line.cell == 9 &&
                        line.glyphColor == 244 && line.shadowColor == 25 && line.player == static_cast<int>(p),
                        "score line mismatch");
                ++index;
            }
        }
    }
    const std::array<std::array<int, 2>, 8> calls{{
        {{1, 80}}, {{1, 80}}, {{0, 19}}, {{0, 19}}, {{0, 19}}, {{0, 29}}, {{0, 29}}, {{0, 29}}}};
    size_t call = 0;
    const auto generated = ui::LevelFlow::makeLevelIntroPattern([&](int low, int high) {
        require(call < calls.size() && calls[call][0] == low && calls[call][1] == high,
                "random call order mismatch");
        ++call;
        return high;
    });
    require(call == 8 && generated.horizontalStep == 80 && generated.verticalStep == 80 &&
            generated.colors[0].r == 77 && generated.colors[6].r == 174,
            "random pattern mismatch");
}

void writePpm(const std::filesystem::path& path, const std::vector<uint32_t>& pixels) {
    std::ofstream out(path, std::ios::binary);
    require(bool(out), "cannot create PPM");
    out << "P6\n320 200\n255\n";
    for (uint32_t color : pixels) {
        const char rgb[]{static_cast<char>(color >> 16), static_cast<char>(color >> 8), static_cast<char>(color)};
        out.write(rgb, 3);
    }
    require(bool(out), "PPM write failed");
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 3, "expected fixture directory and output directory");
        checkModels();
        const auto assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
        rendering::PresentationState presentation;
        presentation.setPalette(assets.palette());
        rendering::Canvas canvas;
        rendering::TextRenderer text(canvas, presentation.palette(), assets.fontSprites());
        rendering::GameRenderer renderer(canvas, text, assets, presentation);
        const std::vector<resources::Record> records;
        const std::string name;
        const std::array<ui::LevelIntroPattern, 2> patterns{{
            {49, 60, {{{69, 73, 36}, {81, 73, 44}, {93, 73, 52}, {105, 77, 60},
                       {117, 77, 69}, {130, 81, 77}, {142, 81, 85}}}},
            {17, 57, {{{32, 0, 40}, {48, 12, 48}, {65, 24, 60}, {81, 36, 69},
                       {97, 48, 81}, {113, 60, 89}, {130, 73, 101}}}}}};
        const std::filesystem::path out(argv[2]);
        require(!std::filesystem::exists(out), "output directory already exists");
        std::filesystem::create_directories(out);
        for (size_t i = 0; i < patterns.size(); ++i) {
            renderer.drawMenu({ui::MenuPage::GameOver, true, records, 0, 0, 0, name, 1,
                               {{0, 0}}, 63, static_cast<size_t>(-1), patterns[i]});
            writePpm(out / ("game-over-" + std::to_string(i + 1) + ".ppm"), canvas.pixels());
            std::ifstream input(std::filesystem::path(argv[1]) / ("end_screen_" + std::to_string(i + 1) + ".rgb"),
                                std::ios::binary);
            require(bool(input), "missing RGB oracle");
            std::vector<uint8_t> expected(192000);
            input.read(reinterpret_cast<char*>(expected.data()), static_cast<std::streamsize>(expected.size()));
            require(input.gcount() == static_cast<std::streamsize>(expected.size()) &&
                    input.peek() == std::char_traits<char>::eof(), "RGB oracle size mismatch");
            size_t differences = 0;
            for (size_t pixel = 0; pixel < canvas.pixels().size(); ++pixel) {
                const uint32_t reference = 0xff000000u | (uint32_t(expected[pixel * 3]) << 16) |
                    (uint32_t(expected[pixel * 3 + 1]) << 8) | expected[pixel * 3 + 2];
                if (canvas.pixels()[pixel] != reference) ++differences;
            }
            if (differences != 0) throw std::runtime_error("original frame " + std::to_string(i + 1) +
                                                          " differing pixels=" + std::to_string(differences));
            const auto previous = canvas.pixels();
            renderer.drawMenu({ui::MenuPage::GameOver, true, records, 0, 0, 0, name, 1,
                               {{0, 0}}, 63, static_cast<size_t>(-1), patterns[i]});
            require(previous == canvas.pixels(), "redraw changed the frozen pattern");
        }
        std::cout << "end_screen=ok original_frames=2 compared_pixels=128000 differing_pixels=0 masks=0"
                     " score_cases=8 rng_calls=8 timing_parity=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "end_screen failed: " << error.what() << '\n';
        return 1;
    }
}
