#include "gameplay/collapse_rectangle.hpp"
#include "gameplay/collapse_removal.hpp"

#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace {

void require(bool condition) {
    if (!condition) throw std::runtime_error("collapse removal differs");
}

void walk(uint16_t first, uint16_t right, uint16_t last,
          uint16_t start, uint16_t step, uint32_t count) {
    std::vector<uint16_t> actual;
    lezac::gameplay::visitCollapseRemovalWords(first, right, last, 60,
        [&](uint16_t cell) {
            require(actual.size() < 1000);
            actual.push_back(cell);
        });
    require(actual.size() == count);
    for (uint32_t index = 0; index < count; ++index) {
        require(actual[index] == static_cast<uint16_t>(start + index * step));
    }
}

}  // namespace

int runTests() {
    walk(0, 32768, 0, 0, 60, 274);
    walk(65496, 65516, 65496, 32748, 1, 11);
    walk(118, 60, 120, 59, 0, 1);
    walk(2440, 1220, 2440, 1220, 60, 11);
    walk(3906, 1953, 3906, 1953, 60, 17);
    walk(4026, 4026, 4026, 2013, 0, 1);
    walk(65534, 65534, 65534, 32767, 0, 1);
    walk(32764, 32764, 32768, 16382, 0, 1);
    require(lezac::gameplay::signedCollapseEndpoint(32768) == -32768);
    require(lezac::gameplay::signedCollapseEndpoint(65535) == -1);
    require(lezac::gameplay::collapseActorCell(0, 0) == 0);
    require(lezac::gameplay::collapseActorCell(0, 1) == 65535);
    require(lezac::gameplay::collapseActorCell(65496, 0) == 32748);
    require(lezac::gameplay::collapseActorCell(120, 1) == 59);
    require(lezac::gameplay::collapseActorCell(65534, 32768) == 65535);
    lezac::gameplay::CollapseRectangle rectangle(116, 118, 60);
    rectangle.translate(1);
    require(rectangle.first == 59 && rectangle.last == 60 && rectangle.columns() == 2);

    // The visitor stops this test, not the production traversal, after a full cycle.
    struct Stop {};
    uint32_t visits = 0;
    try {
        lezac::gameplay::visitCollapseRemovalWords(32766, 32766, 32766, 60,
            [&](uint16_t cell) {
                require(cell == static_cast<uint16_t>((32766u + 2u * visits) & 65535u) / 2);
                if (++visits == 32769) throw Stop{};
            });
        require(false);
    } catch (const Stop&) {
        require(visits == 32769);
    }
    std::cout << "collapse_removal_unit=ok signed_endpoints=1 mixed_units=1 actor_wrap=1 fixed_columns=1 unclamped_cycle=1\n";
    return 0;
}

int main() {
    try {
        return runTests();
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
