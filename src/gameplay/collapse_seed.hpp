#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace lezac::gameplay {

struct CollapseSeedGeometry {
    uint16_t firstOffsetBytes = 0;
    uint16_t lastOffsetBytes = 0;
    std::vector<std::size_t> cells;
};

// 1000:37FE..3A46 expands all matching perimeter edges simultaneously, then
// flags matching words inside the rectangle, including disconnected islands.
template<class ReadWord, class WriteWord>
inline CollapseSeedGeometry seedCollapseWordGroupPhysical(int width, uint16_t seed,
                                                          ReadWord readWord, WriteWord writeWord) {
    CollapseSeedGeometry result;
    seed = static_cast<uint16_t>(static_cast<uint16_t>(seed * 2u) >> 1);
    if (width <= 0) return result;
    const uint16_t key = readWord(seed);
    if (key == 0 || key >= 0x4000) return result;
    const uint16_t stride = static_cast<uint16_t>(2 * width);
    uint16_t topLeft = static_cast<uint16_t>(2 * seed - stride - 2);
    uint16_t topRight = static_cast<uint16_t>(2 * seed - stride);
    uint16_t bottomLeft = static_cast<uint16_t>(2 * seed - 2);
    uint16_t bottomRight = static_cast<uint16_t>(2 * seed);
    uint16_t columns = 2, rows = 2;
    auto wordAt = [&](uint16_t offset) -> uint16_t {
        return readWord(static_cast<uint16_t>(offset >> 1));
    };
    auto edgeMatches = [&](uint16_t offset, uint16_t step, uint16_t count) {
        for (uint16_t i = 0; i < count; ++i) {
            if (wordAt(offset) == key) return true;
            offset = static_cast<uint16_t>(offset + step);
        }
        return false;
    };
    for (;;) {
        const bool up = edgeMatches(topLeft, 2, columns);
        const bool left = edgeMatches(topLeft, stride, rows);
        const bool right = edgeMatches(topRight, stride, rows);
        const bool down = edgeMatches(bottomLeft, 2, columns);
        if (!up && !left && !right && !down) break;
        if (up) {
            topLeft = static_cast<uint16_t>(topLeft - stride);
            topRight = static_cast<uint16_t>(topRight - stride);
            ++rows;
        }
        if (down) {
            bottomLeft = static_cast<uint16_t>(bottomLeft + stride);
            bottomRight = static_cast<uint16_t>(bottomRight + stride);
            ++rows;
        }
        if (left) {
            topLeft = static_cast<uint16_t>(topLeft - 2);
            bottomLeft = static_cast<uint16_t>(bottomLeft - 2);
            ++columns;
        }
        if (right) {
            topRight = static_cast<uint16_t>(topRight + 2);
            bottomRight = static_cast<uint16_t>(bottomRight + 2);
            ++columns;
        }
    }
    result.firstOffsetBytes = static_cast<uint16_t>(topLeft + stride + 2);
    result.lastOffsetBytes = static_cast<uint16_t>(bottomRight - stride - 2);
    uint16_t first = result.firstOffsetBytes;
    uint16_t last = static_cast<uint16_t>(topRight + stride - 2);
    do {
        uint16_t offset = first;
        do {
            if (wordAt(offset) == key) {
                const std::size_t cell = offset / 2;
                writeWord(static_cast<uint16_t>(cell), static_cast<uint16_t>(key | 0x8000));
                result.cells.push_back(cell);
            }
            offset = static_cast<uint16_t>(offset + 2);
        } while (static_cast<int16_t>(offset) <= static_cast<int16_t>(last));
        first = static_cast<uint16_t>(first + stride);
        last = static_cast<uint16_t>(last + stride);
    } while (static_cast<int16_t>(last) <= static_cast<int16_t>(result.lastOffsetBytes));
    return result;
}

inline CollapseSeedGeometry seedCollapseWordGroup(std::vector<uint16_t>& words,
                                                   int width, std::size_t seed) {
    if (width <= 0 || seed >= words.size()) return {};
    return seedCollapseWordGroupPhysical(width, static_cast<uint16_t>(seed),
        [&](uint16_t cell) -> uint16_t { return cell < words.size() ? words[cell] : 0; },
        [&](uint16_t cell, uint16_t word) { words[cell] = word; });
}

}
