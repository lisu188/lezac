#include "rendering/pattern_fill.hpp"
#include <algorithm>
#include <array>
#include <stdexcept>

namespace lezac::rendering {
namespace {
// Trunc(8 * original Real48 sine table at DS:7bda), including its 6.28 period.
constexpr std::array<int8_t, 128> rowWave{
    0,0,0,1,1,1,2,2,3,3,3,4,4,4,5,5,
    5,5,6,6,6,6,7,7,7,7,7,7,7,7,7,7,
    7,7,7,7,7,7,7,7,7,7,7,6,6,6,6,5,
    5,5,5,4,4,4,3,3,3,2,2,1,1,1,0,0,
    0,0,0,-1,-1,-1,-2,-2,-3,-3,-3,-4,-4,-4,-5,-5,
    -5,-5,-6,-6,-6,-6,-7,-7,-7,-7,-7,-7,-7,-7,-7,-7,
    -7,-7,-7,-7,-7,-7,-7,-7,-7,-7,-7,-6,-6,-6,-6,-5,
    -5,-5,-5,-4,-4,-4,-3,-3,-3,-2,-2,-1,-1,-1,0,0};
}

void PatternFill::begin(const ui::LevelIntroPattern& pattern) {
    if (pattern.horizontalStep < 1 || pattern.horizontalStep > 80 ||
        pattern.verticalStep < 1 || pattern.verticalStep > 80)
        throw std::invalid_argument("pattern steps outside original domain");
    pattern_ = pattern;
    cursor_ = {0, 0, 0, PatternFillStage::Horizontal};
}

void PatternFill::addFraction(int amount) {
    cursor_.fraction = static_cast<int16_t>(cursor_.fraction + amount);
    if (cursor_.fraction > 100) {
        cursor_.fraction -= 100;
        ++cursor_.phase;
    }
}

void PatternFill::step(Canvas& canvas) {
    const size_t at = cursor_.destinationOffset;
    switch (cursor_.stage) {
        case PatternFillStage::Horizontal:
            addFraction(pattern_.horizontalStep);
            cursor_.stage = at % kScreenW == 0 ? PatternFillStage::Vertical : PatternFillStage::Write;
            break;
        case PatternFillStage::Vertical:
            addFraction(pattern_.verticalStep + rowWave[(at * 3 / 100) % rowWave.size()]);
            cursor_.stage = PatternFillStage::Write;
            break;
        case PatternFillStage::Write: {
            const auto color = pattern_.colors[cursor_.phase % pattern_.colors.size()];
            canvas.pixel(static_cast<int>(at % kScreenW), static_cast<int>(at / kScreenW),
                0xff000000u | (uint32_t(color.r) << 16) | (uint32_t(color.g) << 8) | color.b);
            ++cursor_.destinationOffset;
            cursor_.stage = cursor_.destinationOffset == pixelCount ?
                PatternFillStage::Finished : PatternFillStage::Horizontal;
            break;
        }
        case PatternFillStage::Finished: break;
    }
}

size_t PatternFill::advancePixels(Canvas& canvas, size_t budget) {
    if (budget == 0 || finished()) return 0;
    const size_t count = std::min(budget, pixelCount - cursor_.destinationOffset);
    if (count == 0) return 0;
    canvas.resetClip();
    const size_t end = cursor_.destinationOffset + count;
    while (cursor_.destinationOffset != end) step(canvas);
    return count;
}

size_t PatternFill::advanceStages(Canvas& canvas, size_t budget) {
    if (budget == 0 || finished()) return 0;
    canvas.resetClip();
    size_t count = 0;
    while (count < budget && !finished()) {
        step(canvas);
        ++count;
    }
    return count;
}
}
