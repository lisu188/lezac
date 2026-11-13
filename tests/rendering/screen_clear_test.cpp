#include "rendering/screen_clear.hpp"
#include "rendering/game_renderer.hpp"
#include "resources/io.hpp"
#include "resources/json.hpp"
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>

using namespace lezac;
namespace fs = std::filesystem;

namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

fs::path createRunDirectory(const fs::path& root) {
    fs::create_directories(root);
    for (uint64_t i = 0;; ++i) {
        const auto candidate = root / ("run-" + std::to_string(i));
        if (fs::create_directory(candidate)) return candidate;
    }
}

void checkBudgets() {
    using namespace rendering;
    for (size_t budget : {size_t(0), size_t(1), size_t(319), size_t(320), size_t(321),
                          size_t(33705), size_t(63999), size_t(64000), std::numeric_limits<size_t>::max()}) {
        Canvas canvas;
        canvas.clear(0xffabcdefu);
        ScreenClear clear;
        require(clear.finished() && clear.advance(canvas, 1) == 0, "unstarted clear wrote a pixel");
        clear.begin(9, 0xff123456u);
        require(!clear.finished(), "begin did not restart clear");
        const auto before = canvas.pixels();
        require(clear.advance(canvas, 0) == 0 && canvas.pixels() == before, "zero budget changed canvas");
        canvas.setClip(100, 100, 101, 101);
        const size_t written = std::min(budget, ScreenClear::pixelCount);
        require(clear.advance(canvas, budget) == written, "budget was not bounded");
        const auto cursor = clear.cursor();
        require(cursor.destinationOffset == written, "destination offset differs");
        require(cursor.rowStartOffset == written / 320 * 320, "row start differs");
        require(cursor.columnsRemaining == (written == 64000 ? 0 : 320 - written % 320), "column count differs");
        require(cursor.rowsRemaining == 200 - written / 320, "row count differs");
        for (size_t i = 0; i < 64000; ++i) {
            require(canvas.pixels()[i] == (i < written ? 0xff123456u : 0xffabcdefu), "prefix or suffix changed");
            require(canvas.indexedPixels()[i] == (i < written ? 1 : 0), "indexed coverage changed");
            if (i < written) require(canvas.paletteIndices()[i] == 9, "palette index was lost");
        }
        require(clear.advance(canvas, std::numeric_limits<size_t>::max()) == 64000 - written,
                "resumed clear lost work");
        require(clear.finished() && clear.advance(canvas, 100) == 0, "finished clear restarted");
        for (uint32_t pixel : canvas.pixels()) require(pixel == 0xff123456u, "resume left an old pixel");
        clear.begin(0, 0xff000000u);
        require(clear.cursor() == ScreenClearCursor{0, 0, 320, 200}, "restart retained old cursor");
    }
}

void writePpm(const fs::path& path, const rendering::Canvas& canvas) {
    std::ofstream out(path, std::ios::binary);
    out << "P6\n320 200\n255\n";
    for (uint32_t color : canvas.pixels()) {
        const char rgb[]{static_cast<char>(color >> 16), static_cast<char>(color >> 8), static_cast<char>(color)};
        out.write(rgb, 3);
    }
    require(bool(out), "PPM output failed");
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 3, "expected fixture and output roots");
        const fs::path fixtures(argv[1]);
        const auto out = createRunDirectory(argv[2]);
        checkBudgets();
        const auto manifestBytes = resources::readFile((fixtures / "screen_clear_original.json").string());
        const std::string manifest(manifestBytes.begin(), manifestBytes.end());
        const auto cases = resources::extractObjectArray(manifest, "cases");
        require(cases.size() == 2, "expected two independent original clear frames");
        const auto assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
        rendering::PresentationState presentation;
        presentation.setPalette(assets.palette());
        rendering::Canvas canvas;
        rendering::TextRenderer text(canvas, presentation.palette(), assets.fontSprites());
        rendering::GameRenderer renderer(canvas, text, assets, presentation);
        const auto records = resources::loadRawRecords((fixtures / "record_adjacent_zero.dat").string());
        size_t compared = 0;
        for (const auto& item : cases) {
            ui::LevelIntroPattern pattern;
            pattern.horizontalStep = resources::extractInt(item, "horizontal_step");
            pattern.verticalStep = resources::extractInt(item, "vertical_step");
            const auto colors = resources::extractObjectArray(item, "colors");
            require(colors.size() == pattern.colors.size(), "invalid background palette");
            for (size_t i = 0; i < colors.size(); ++i)
                pattern.colors[i] = {static_cast<uint8_t>(resources::extractInt(colors[i], "r")),
                                     static_cast<uint8_t>(resources::extractInt(colors[i], "g")),
                                     static_cast<uint8_t>(resources::extractInt(colors[i], "b"))};
            const rendering::MenuView menu{ui::MenuPage::NameEntry, true, records, 1, 0, 1,
                "q", 1, {{0, 0}}, 63, static_cast<size_t>(-1), pattern};
            renderer.drawMenu(menu);
            rendering::ScreenClear clear;
            clear.begin(0, 0xff000000u);
            const size_t destination = static_cast<size_t>(resources::extractInt(item, "destination_offset"));
            require(destination >= 320 && destination <= rendering::ScreenClear::pixelCount,
                    "invalid original clear offset");
            require(clear.advance(canvas, 320) == 320 && clear.advance(canvas, destination - 320) == destination - 320,
                    "chunked clear did not reach interrupted offset");
            const auto cursor = clear.cursor();
            require(cursor.destinationOffset == destination &&
                    cursor.columnsRemaining == resources::extractInt(item, "columns_remaining") &&
                    cursor.rowStartOffset == resources::extractInt(item, "row_start") &&
                    cursor.rowsRemaining == resources::extractInt(item, "rows_remaining"),
                    "cursor differs from original interrupt stack");
            const auto expected = resources::readFile((fixtures / resources::extractString(item, "rgb_file")).string());
            require(expected.size() == 192000, "invalid original frame size");
            for (size_t i = 0; i < 64000; ++i) {
                const uint32_t color = 0xff000000u | (uint32_t(expected[i * 3]) << 16) |
                    (uint32_t(expected[i * 3 + 1]) << 8) | expected[i * 3 + 2];
                require(canvas.pixels()[i] == color, "interrupted original pixel differs");
            }
            const auto frozen = canvas.pixels();
            require(clear.advance(canvas, 0) == 0 && canvas.pixels() == frozen, "stopped clear changed frame");
            writePpm(out / (resources::extractString(item, "name") + ".ppm"), canvas);
            compared += canvas.pixels().size();
        }
        std::cout << "screen_clear=ok original_frames=2 compared_pixels=" << compared
                  << " differing_pixels=0 masks=0 budgets=9 interrupt_schedule_claim=0 full_app_claim=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "screen_clear failed: " << error.what() << '\n';
        return 1;
    }
}
