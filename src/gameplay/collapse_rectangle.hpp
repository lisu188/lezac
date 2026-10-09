#pragma once

#include <cstdint>

namespace lezac::gameplay {

// 1000:5181..51B9 derives these counts once, before either motion phase.
class CollapseRectangle {
public:
    CollapseRectangle(uint16_t startOffset, uint16_t endOffset, uint16_t levelWidth)
        : first(startOffset >> 1), last(endOffset >> 1), width_(levelWidth) {
        topRight = static_cast<uint16_t>(first + last % width_ - first % width_);
        columns_ = static_cast<uint16_t>(topRight - first + 1);
        rows_ = static_cast<uint16_t>(static_cast<uint16_t>(last - topRight) / width_ + 1);
    }

    template <typename Visitor>
    void visit(int direction, Visitor&& visitor) const {
        uint16_t row = static_cast<uint16_t>(first * 2u);
        int columnStep = 2, rowStep = width_ * 2;
        // 4EE7 tests vertical motion first, including when level width is one.
        if (direction == -width_) {
        } else if (direction == width_) {
            row = static_cast<uint16_t>(last * 2u);
            columnStep = -2;
            rowStep = -rowStep;
        } else if (direction == 1) {
            row = static_cast<uint16_t>(topRight * 2u);
            columnStep = -2;
        }
        // x86 LOOP with CX=0 executes 65536 iterations, not an empty range.
        const uint32_t columns = columns_ ? columns_ : 65536u;
        const uint32_t rows = rows_ ? rows_ : 65536u;
        for (uint32_t y = 0; y < rows; ++y) {
            uint16_t cursor = row;
            for (uint32_t x = 0; x < columns; ++x) {
                visitor(static_cast<uint16_t>(cursor >> 1));
                cursor = static_cast<uint16_t>(cursor + columnStep);
            }
            row = static_cast<uint16_t>(row + rowStep);
        }
    }

    void translate(int delta) {
        first = static_cast<uint16_t>(first + delta);
        topRight = static_cast<uint16_t>(topRight + delta);
        last = static_cast<uint16_t>(last + delta);
    }

    uint16_t first, topRight = 0, last;

private:
    uint16_t width_, columns_ = 0, rows_ = 0;
};

}  // namespace lezac::gameplay
