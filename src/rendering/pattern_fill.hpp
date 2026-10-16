#pragma once

#include "rendering/canvas.hpp"
#include "ui/models.hpp"
#include <cstddef>
#include <cstdint>

namespace lezac::rendering {

enum class PatternFillStage : uint8_t { Horizontal, Vertical, Write, Finished };

struct PatternFillCursor {
    uint16_t destinationOffset = 0;
    int16_t fraction = 0;
    uint16_t phase = 0;
    PatternFillStage stage = PatternFillStage::Finished;
    bool operator==(const PatternFillCursor&) const = default;
};

// Semantic boundaries in CS:01fc..030a, not instruction counts or IRQ timing.
class PatternFill {
public:
    static constexpr size_t pixelCount = static_cast<size_t>(kScreenW) * kScreenH;
    static_assert(pixelCount <= 0xffffu);
    void begin(const ui::LevelIntroPattern& pattern);
    bool finished() const { return cursor_.stage == PatternFillStage::Finished; }
    PatternFillCursor cursor() const { return cursor_; }
    size_t advancePixels(Canvas& canvas, size_t budget);
    size_t advanceStages(Canvas& canvas, size_t budget);
private:
    void step(Canvas& canvas);
    void addFraction(int amount);
    ui::LevelIntroPattern pattern_{};
    PatternFillCursor cursor_{static_cast<uint16_t>(pixelCount), 0, 0, PatternFillStage::Finished};
};

}
