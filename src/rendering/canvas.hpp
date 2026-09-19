#pragma once

#include <cstdint>
#include <vector>

namespace lezac::rendering {

inline constexpr int kScreenW = 320;
inline constexpr int kScreenH = 200;

class Canvas {
public:
    void setClip(int left, int top, int right, int bottom);
    void resetClip();
    void pixel(int x, int y, uint32_t color);
    void rect(int x, int y, int w, int h, uint32_t color);

    const std::vector<uint32_t>& pixels() const { return fb_; }
    std::vector<uint32_t>& pixels() { return fb_; }

private:
    std::vector<uint32_t> fb_ = std::vector<uint32_t>(kScreenW * kScreenH);
    int clipLeft_ = 0;
    int clipTop_ = 0;
    int clipRight_ = kScreenW;
    int clipBottom_ = kScreenH;
};

}
