#pragma once

#include "rendering/canvas.hpp"
#include <algorithm>
#include <cstddef>
#include <cstdint>

namespace lezac::rendering {

struct ScreenClearCursor {
    uint16_t destinationOffset = 0;
    uint16_t rowStartOffset = 0;
    uint16_t columnsRemaining = 0;
    uint16_t rowsRemaining = 0;
    bool operator==(const ScreenClearCursor&) const = default;
};

// Full-screen case of CS:07c5: progress is retained between REP STOSB writes.
// Cursor values describe the next pixel, not intervening row epilogue instructions.
class ScreenClear {
public:
    static constexpr size_t pixelCount = static_cast<size_t>(kScreenW) * kScreenH;
    static_assert(pixelCount <= UINT16_MAX);

    void begin(uint8_t paletteIndex, uint32_t color) {
        completed_ = 0;
        paletteIndex_ = paletteIndex;
        color_ = color;
    }
    bool finished() const { return completed_ == pixelCount; }
    ScreenClearCursor cursor() const {
        const size_t row = completed_ / kScreenW;
        return {static_cast<uint16_t>(completed_), static_cast<uint16_t>(row * kScreenW),
                static_cast<uint16_t>(finished() ? 0 : kScreenW - completed_ % kScreenW),
                static_cast<uint16_t>(kScreenH - row)};
    }
    size_t advance(Canvas& canvas, size_t pixelBudget) {
        const size_t count = std::min(pixelBudget, pixelCount - completed_);
        if (count == 0) return 0;
        canvas.resetClip();
        for (size_t i = 0; i < count; ++i, ++completed_)
            canvas.indexedPixel(static_cast<int>(completed_ % kScreenW),
                                static_cast<int>(completed_ / kScreenW), paletteIndex_, color_);
        return count;
    }

private:
    size_t completed_ = pixelCount;
    uint8_t paletteIndex_ = 0;
    uint32_t color_ = 0xff000000u;
};

}
