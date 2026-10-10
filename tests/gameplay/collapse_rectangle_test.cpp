#include "gameplay/collapse_rectangle.hpp"

#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>

using lezac::gameplay::CollapseRectangle;

static void require(bool condition) {
    if (!condition) throw std::runtime_error("collapse rectangle regression");
}

static std::vector<uint16_t> cells(const CollapseRectangle& rectangle, int direction) {
    std::vector<uint16_t> result;
    rectangle.visit(direction, [&](uint16_t cell) { result.push_back(cell); });
    return result;
}

int main() {
    try {
    CollapseRectangle square(2440, 2562, 60);
    require(cells(square, 1) == std::vector<uint16_t>({1221, 1220, 1281, 1280}));
    require(cells(square, 60) == std::vector<uint16_t>({1281, 1280, 1221, 1220}));
    require(cells(square, -60) == std::vector<uint16_t>({1220, 1221, 1280, 1281}));
    require(cells(square, -1) == cells(square, 0));
    square.translate(1);
    require(cells(square, 1) == std::vector<uint16_t>({1222, 1221, 1282, 1281}));
    CollapseRectangle crossing(116, 118, 60);
    crossing.translate(1);
    require(cells(crossing, 0) == std::vector<uint16_t>({59, 60}));
    require(crossing.topRight == 60);
    CollapseRectangle wrapping(65532, 65534, 60);
    wrapping.translate(1);
    require(cells(wrapping, 0) == std::vector<uint16_t>({32767, 0}));
    wrapping.translate(1);
    require(cells(wrapping, 0) == std::vector<uint16_t>({0, 1}));
    CollapseRectangle underflow(80, 80, 60);
    underflow.translate(-60);
    require(underflow.first == 65516 && cells(underflow, 0) == std::vector<uint16_t>({32748}));
    CollapseRectangle narrow(10, 12, 1);
    require(cells(narrow, 1) == std::vector<uint16_t>({6, 5}));
    CollapseRectangle zeroCount(2, 0, 60);
    uint32_t count = 0;
    uint16_t first = 0, last = 0;
    zeroCount.visit(0, [&](uint16_t cell) { if (!count) first = cell; last = cell; ++count; });
    require(count == 65536 && first == 1 && last == 0);
    std::cout << "collapse_rectangle_unit=ok fixed_dimensions=1 directional_order=1 word_cursor_wrap=1 zero_count_loop=1\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
