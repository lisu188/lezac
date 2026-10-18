#pragma once

#include "core/frame_camera.hpp"

#include <array>
#include <bit>
#include <cstdint>
#include <stdexcept>

namespace lezac::rendering {

struct WorldCameraInput {
    uint16_t x, y;
    uint16_t mapWidth, centerX, centerTiles, maximumX, maximumY, shake;
};

struct WorldCamera {
    uint16_t coarseX = 0, coarseY = 0, mapOffset = 0, fineX = 0, fineY = 0;

    int pixelX() const noexcept { return std::bit_cast<int16_t>(coarseX) + int{fineX}; }
    int pixelY() const noexcept { return std::bit_cast<int16_t>(coarseY) + int{fineY}; }
    bool operator==(const WorldCamera&) const = default;
};

// The live renderer supplies only the camera's seven context words and its
// coordinates. The original operation owns a bounded local Pascal stack;
// neither a diagnostic RAM image nor a copy of the live world is needed.
inline WorldCamera calculateWorldCamera(const WorldCameraInput& input) {
    constexpr uint16_t game = 0x1000, data = 0x1aa2, stack = 0x7000;
    constexpr uint16_t stackBase = 0x3fa0, entrySp = 0x3fe4;
    std::array<uint16_t, 40> words{};
    WorldCamera result;
    const auto stackWord = [&](uint16_t offset) -> uint16_t& {
        if (offset < stackBase || (offset & 1) || (offset - stackBase) / 2 >= int(words.size()))
            throw std::logic_error("World camera left its owned stack");
        return words[static_cast<size_t>((offset - stackBase) / 2)];
    };
    stackWord(entrySp) = 0x7a25;
    stackWord(entrySp + 2) = input.y;
    stackWord(entrySp + 4) = input.x;
    const auto contextWord = [&](uint16_t offset) -> uint16_t& {
        switch (offset) {
        case 0xc216: return result.coarseX;
        case 0xc218: return result.coarseY;
        case 0xc1f0: return result.mapOffset;
        case 0xc20a: return result.fineX;
        case 0xc20c: return result.fineY;
        default: throw std::logic_error("World camera wrote outside its context");
        }
    };
    core::TimerIrqBus bus;
    bus.readWord = [&](uint16_t segment, uint16_t offset) -> uint16_t {
        if (segment == stack) return stackWord(offset);
        if (segment != data) throw std::logic_error("World camera read an unowned segment");
        switch (offset) {
        case 0xc204: return input.mapWidth;
        case 0x78bc: return input.centerX;
        case 0x78be: return input.centerTiles;
        case 0x2094: return input.maximumX;
        case 0x2096: return input.maximumY;
        case 0x2098: return input.shake;
        case 0x1afa: return 0x200;
        default: return contextWord(offset);
        }
    };
    bus.writeWord = [&](uint16_t segment, uint16_t offset, uint16_t value) {
        if (segment == stack) stackWord(offset) = value;
        else if (segment == data) contextWord(offset) = value;
        else throw std::logic_error("World camera wrote an unowned segment");
    };
    core::DosGetTimeRegisters registers;
    registers.cs = game;
    registers.ds = data;
    registers.ss = stack;
    registers.sp = entrySp;
    registers.ip = 0x3587;
    registers.flags = 0x202;
    core::FrameCameraOperation operation(registers, game);
    operation.advance(512, bus);
    if (!operation.returned() || operation.snapshot().registers.sp != entrySp + 6 ||
            operation.snapshot().registers.ip != 0x7a25)
        throw std::logic_error("World camera did not return through its owned caller");
    return result;
}

inline WorldCamera cameraForViewport(int x, int y, int mapWidth, int mapHeight,
                                     int pitch, uint16_t shake) {
    if (pitch < 160 || pitch > 320 || pitch % 8 || mapWidth <= 0 || mapWidth > 32767 ||
            mapHeight <= 0 || mapHeight > 32767)
        throw std::invalid_argument("World camera geometry differs");
    const int center = ((pitch / 8 - 2) / 2) * 8;
    return calculateWorldCamera({static_cast<uint16_t>(x), static_cast<uint16_t>(y),
        static_cast<uint16_t>(mapWidth), static_cast<uint16_t>(center),
        static_cast<uint16_t>(center / 8), static_cast<uint16_t>((mapWidth - pitch / 8) * 8),
        static_cast<uint16_t>((mapHeight - 21) * 8), shake});
}

} // namespace lezac::rendering
