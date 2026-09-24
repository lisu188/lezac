#pragma once

#include "rendering/canvas.hpp"
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace lezac::diagnostics {

struct FrameInspection {
    size_t changedPixels = 0;
    uint64_t hash = 0;
};

// Inspects the public frame buffer; it cannot reach simulation internals.
class FrameInspector {
public:
    explicit FrameInspector(const rendering::Canvas& canvas) : canvas_(canvas) {}
    FrameInspection inspectRenderedFrame(const std::string& label) const;
    bool regionHasVariation(int x, int y, int w, int h) const;
    bool regionChanged(const std::vector<uint32_t>& before, int x, int y, int w, int h) const;
    size_t countColorInRegion(int x, int y, int w, int h, uint32_t color) const;
private:
    const rendering::Canvas& canvas_;
};

}
