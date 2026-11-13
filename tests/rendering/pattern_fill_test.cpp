#include "rendering/pattern_fill.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <tuple>
#include <utility>
#include <vector>

using namespace lezac;
using namespace rendering;
namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
struct Reference {
    std::vector<uint32_t> pixels;
    int fraction = 0;
    uint16_t phase = 0;
};
Reference reference(const ui::LevelIntroPattern& pattern, size_t count = PatternFill::pixelCount) {
    Reference result;
    result.pixels.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        result.fraction += pattern.horizontalStep;
        if (result.fraction > 100) { result.fraction -= 100; ++result.phase; }
        if (i % 320 == 0) {
            const int index = static_cast<int>(i * 3 / 100 % 128);
            const int wave = static_cast<int>(std::sin(static_cast<float>(index) * 6.28f / 128.0f) * 8.0f);
            result.fraction += pattern.verticalStep + wave;
            if (result.fraction > 100) { result.fraction -= 100; ++result.phase; }
        }
        const auto color = pattern.colors[result.phase % 7];
        result.pixels.push_back(0xff000000u | (uint32_t(color.r) << 16) | (uint32_t(color.g) << 8) | color.b);
    }
    return result;
}
ui::LevelIntroPattern makePattern(int h, int v) {
    ui::LevelIntroPattern pattern;
    pattern.horizontalStep = h;
    pattern.verticalStep = v;
    for (size_t i = 0; i < 7; ++i)
        pattern.colors[i] = {static_cast<uint8_t>(i * 29 + 5),
                             static_cast<uint8_t>(i * 17 + 3), static_cast<uint8_t>(i * 13 + 7)};
    return pattern;
}
void boundaries() {
    const auto pattern = makePattern(53, 27);
    for (size_t budget : {size_t(0), size_t(1), size_t(319), size_t(320), size_t(321),
                          size_t(33705), size_t(63999), size_t(64000), std::numeric_limits<size_t>::max()}) {
        Canvas canvas;
        canvas.clear(0xffabcdefu);
        PatternFill fill;
        require(fill.finished() && fill.advancePixels(canvas, budget) == 0, "unstarted fill wrote pixels");
        fill.begin(pattern);
        const size_t count = std::min(budget, PatternFill::pixelCount);
        require(fill.advancePixels(canvas, budget) == count, "pixel budget not bounded");
        const auto expected = reference(pattern, count);
        const auto cursor = fill.cursor();
        require(cursor.destinationOffset == count && cursor.fraction == expected.fraction &&
                cursor.phase == expected.phase, "cursor does not describe completed pixel writes");
        for (size_t i = 0; i < PatternFill::pixelCount; ++i)
            require(canvas.pixels()[i] == (i < count ? expected.pixels[i] : 0xffabcdefu),
                    "partial fill changed prefix or suffix");
        const auto before = canvas.pixels();
        require(fill.advanceStages(canvas, 0) == 0 && fill.advancePixels(canvas, 0) == 0 &&
                canvas.pixels() == before && fill.cursor() == cursor, "zero budget advanced work");
        require(fill.advancePixels(canvas, std::numeric_limits<size_t>::max()) == 64000 - count &&
                fill.finished(), "resume lost pending writes");
        fill.begin(pattern);
        require(fill.cursor() == PatternFillCursor{0, 0, 0, PatternFillStage::Horizontal},
                "restart retained old work");
    }
    Canvas canvas;
    canvas.clear(0xffabcdefu);
    PatternFill fill;
    fill.begin(pattern);
    require(fill.advanceStages(canvas, 1) == 1 &&
            fill.cursor() == PatternFillCursor{0, 53, 0, PatternFillStage::Vertical}, "horizontal stage differs");
    require(canvas.pixels().front() == 0xffabcdefu, "arithmetic stage wrote a pixel");
    require(fill.advanceStages(canvas, 1) == 1 &&
            fill.cursor() == PatternFillCursor{0, 80, 0, PatternFillStage::Write}, "row stage differs");
    require(canvas.pixels().front() == 0xffabcdefu, "row stage wrote a pixel");
    require(fill.advancePixels(canvas, 1) == 1 && fill.cursor().destinationOffset == 1,
            "pixel budget restarted a partial arithmetic stage");
    for (auto [destination, stage, fraction, phase] :
         {std::tuple{4678, PatternFillStage::Horizontal, 40, 2483},
          std::tuple{16373, PatternFillStage::Write, 30, 8692},
          std::tuple{30400, PatternFillStage::Vertical, 19, 16138}}) {
        fill.begin(pattern);
        fill.advancePixels(canvas, static_cast<size_t>(destination));
        if (stage != PatternFillStage::Horizontal) fill.advanceStages(canvas, 1);
        require(fill.cursor() == PatternFillCursor{static_cast<uint16_t>(destination),
                    static_cast<int16_t>(fraction), static_cast<uint16_t>(phase), stage},
                "original in-flight arithmetic cursor differs");
    }
    const auto saved = fill.cursor();
    for (auto [h, v] : {std::pair{0, 1}, {-1, 1}, {81, 1}, {1, 0}, {1, -1}, {1, 81}}) {
        bool rejected = false;
        try { fill.begin(makePattern(h, v)); } catch (const std::invalid_argument&) { rejected = true; }
        require(rejected && fill.cursor() == saved, "invalid begin changed retained work");
    }
    fill.begin(pattern);
    require(fill.advanceStages(canvas, std::numeric_limits<size_t>::max()) == 128200 && fill.finished(),
            "unbounded stage budget lost or repeated work");
    const auto completed = canvas.pixels();
    require(fill.advanceStages(canvas, 1) == 0 && fill.advancePixels(canvas, 1) == 0 &&
            canvas.pixels() == completed, "finished stage operation changed its frame");
}
}
int main() {
    try {
        boundaries();
        Canvas canvas;
        PatternFill fill;
        for (int h = 1; h <= 80; ++h) {
            for (int v = 1; v <= 80; ++v) {
                const auto pattern = makePattern(h, v);
                const auto expected = reference(pattern);
                fill.begin(pattern);
                fill.advancePixels(canvas, 319);
                fill.advanceStages(canvas, 5);
                fill.advancePixels(canvas, std::numeric_limits<size_t>::max());
                require(fill.finished() && canvas.pixels() == expected.pixels &&
                        fill.cursor().fraction == expected.fraction && fill.cursor().phase == expected.phase,
                        "full original input domain differs from prior renderer");
            }
        }
        std::cout << "pattern_fill=ok patterns=6400 compared_pixels=409600000 budgets=9"
                     " original_cursor_cases=3 semantic_stages=3 invalid_inputs=6 timing_claim=0\n";
    } catch (const std::exception& error) {
        std::cerr << "pattern_fill failed: " << error.what() << '\n';
        return 1;
    }
}
