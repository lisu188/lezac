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
        fb_[static_cast<size_t>(y) * kScreenW + x] = color;
    }
}

void Canvas::rect(int x, int y, int w, int h, uint32_t color) {
    for (int yy = std::max(clipTop_, y); yy < std::min(clipBottom_, y + h); ++yy) {
        for (int xx = std::max(clipLeft_, x); xx < std::min(clipRight_, x + w); ++xx) {
            fb_[static_cast<size_t>(yy) * kScreenW + xx] = color;
        }
    }
}

}
