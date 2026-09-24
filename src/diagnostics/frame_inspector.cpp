#include "diagnostics/frame_inspector.hpp"
#include <algorithm>
#include <stdexcept>

namespace lezac::diagnostics {
using rendering::kScreenW;
using rendering::kScreenH;

FrameInspection FrameInspector::inspectRenderedFrame(const std::string& label) const {
    if (canvas_.pixels().empty()) {
        throw std::runtime_error(label + " frame buffer is empty");
    }
    FrameInspection inspection;
    uint32_t first = canvas_.pixels().front();
    uint64_t hash = 1469598103934665603ull;
    for (uint32_t pixelValue : canvas_.pixels()) {
        if (pixelValue != first) ++inspection.changedPixels;
        hash ^= static_cast<uint64_t>(pixelValue);
        hash *= 1099511628211ull;
    }
    inspection.hash = hash;
    if (inspection.changedPixels == 0) {
        throw std::runtime_error(label + " rendered a uniform frame");
    }
    return inspection;
}

bool FrameInspector::regionHasVariation(int x, int y, int w, int h) const {
    int x0 = std::clamp(x, 0, kScreenW);
    int y0 = std::clamp(y, 0, kScreenH);
    int x1 = std::clamp(x + w, 0, kScreenW);
    int y1 = std::clamp(y + h, 0, kScreenH);
    if (x0 >= x1 || y0 >= y1) return false;
    uint32_t first = canvas_.pixels()[static_cast<size_t>(y0) * kScreenW + x0];
    for (int yy = y0; yy < y1; ++yy) {
        for (int xx = x0; xx < x1; ++xx) {
            if (canvas_.pixels()[static_cast<size_t>(yy) * kScreenW + xx] != first) {
                return true;
            }
        }
    }
    return false;
}

bool FrameInspector::regionChanged(const std::vector<uint32_t>& before, int x, int y,
                   int w, int h) const {
    if (before.size() != canvas_.pixels().size()) return false;
    int x0 = std::clamp(x, 0, kScreenW);
    int y0 = std::clamp(y, 0, kScreenH);
    int x1 = std::clamp(x + w, 0, kScreenW);
    int y1 = std::clamp(y + h, 0, kScreenH);
    if (x0 >= x1 || y0 >= y1) return false;
    for (int yy = y0; yy < y1; ++yy) {
        for (int xx = x0; xx < x1; ++xx) {
            size_t idx = static_cast<size_t>(yy) * kScreenW + xx;
            if (canvas_.pixels()[idx] != before[idx]) {
                return true;
            }
        }
    }
    return false;
}

size_t FrameInspector::countColorInRegion(int x, int y, int w, int h, uint32_t color) const {
    int x0 = std::clamp(x, 0, kScreenW);
    int y0 = std::clamp(y, 0, kScreenH);
    int x1 = std::clamp(x + w, 0, kScreenW);
    int y1 = std::clamp(y + h, 0, kScreenH);
    size_t count = 0;
    for (int yy = y0; yy < y1; ++yy) {
        for (int xx = x0; xx < x1; ++xx) {
            if (canvas_.pixels()[static_cast<size_t>(yy) * kScreenW + xx] == color) {
                ++count;
            }
        }
    }
    return count;
}
}
