#include "rendering/canvas.hpp"

#include <algorithm>
#include <cstddef>

namespace lezac::rendering {

void Canvas::setClip(int left, int top, int right, int bottom) {
    clipLeft_ = std::clamp(left, 0, kScreenW);
    clipTop_ = std::clamp(top, 0, kScreenH);
    clipRight_ = std::clamp(right, clipLeft_, kScreenW);
    clipBottom_ = std::clamp(bottom, clipTop_, kScreenH);
}

void Canvas::resetClip() {
    setClip(0, 0, kScreenW, kScreenH);
}

void Canvas::pixel(int x, int y, uint32_t color) {
    if (x >= clipLeft_ && y >= clipTop_ && x < clipRight_ && y < clipBottom_) {
        const size_t at = static_cast<size_t>(y) * kScreenW + x;
        fb_[at] = color;
        indexedPixels_[at] = 0;
    }
}

void Canvas::rect(int x, int y, int w, int h, uint32_t color) {
    for (int yy = std::max(clipTop_, y); yy < std::min(clipBottom_, y + h); ++yy) {
        for (int xx = std::max(clipLeft_, x); xx < std::min(clipRight_, x + w); ++xx) {
            pixel(xx, yy, color);
        }
    }
}

void Canvas::clear(uint32_t color) {
    std::fill(fb_.begin(), fb_.end(), color);
    std::fill(indexedPixels_.begin(), indexedPixels_.end(), 0);
}

void Canvas::indexedPixel(int x, int y, uint8_t index, uint32_t color) {
    if (x < clipLeft_ || y < clipTop_ || x >= clipRight_ || y >= clipBottom_) return;
    const size_t at = static_cast<size_t>(y) * kScreenW + x;
    fb_[at] = color;
    paletteIndices_[at] = index;
    indexedPixels_[at] = 1;
}

void Canvas::indexedRect(int x, int y, int w, int h, uint8_t index, uint32_t color) {
    for (int yy = std::max(clipTop_, y); yy < std::min(clipBottom_, y + h); ++yy)
        for (int xx = std::max(clipLeft_, x); xx < std::min(clipRight_, x + w); ++xx)
            indexedPixel(xx, yy, index, color);
}

}
