#pragma once

#include "core/dos_time.hpp"
#include "core/timer_irq.hpp"

#include <bit>
#include <cstdint>
#include <stdexcept>

namespace lezac::core {

struct FrameElapsedSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment = 0;
    uint64_t dispatchedInstructions = 0;
    bool returned = false;
    bool operator==(const FrameElapsedSnapshot&) const = default;
};

// Original game:791E..7966, after DOS IRET and before the separate Real48 display work.
class FrameElapsedOperation {
public:
    FrameElapsedOperation(DosGetTimeRegisters registers, uint16_t gameSegment)
        : state_{registers, gameSegment} {
        if (registers.cs != gameSegment || registers.ip != 0x791e ||
            registers.ds != static_cast<uint16_t>(gameSegment + 0xaa2))
            throw std::invalid_argument("Frame elapsed caller entry differs");
    }
    explicit FrameElapsedOperation(FrameElapsedSnapshot state) : state_(state) {}
    const FrameElapsedSnapshot& snapshot() const noexcept { return state_; }
    bool returned() const noexcept { return state_.returned; }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus) {
        uint64_t consumed = 0;
        while (consumed < budget && !returned()) {
            advanceOne(bus);
            ++state_.dispatchedInstructions;
            ++consumed;
            if (state_.registers.cs == state_.gameSegment && state_.registers.ip == 0x7966)
                state_.returned = true;
        }
        return consumed;
    }

private:
    static constexpr uint32_t Arithmetic = 0x8d5;
    static uint32_t valueFlags(uint16_t value, unsigned bits) {
        return (value == 0 ? 0x40u : 0u) | ((value & (1u << (bits - 1))) ? 0x80u : 0u) |
            (std::popcount(static_cast<uint8_t>(value)) % 2 == 0 ? 4u : 0u);
    }
    void clearAh() {
        auto& r = state_.registers;
        r.ax &= 0xff;
        // The pinned host materializes XOR's otherwise undefined AF as zero.
        r.flags = (r.flags & ~Arithmetic) | 0x44u;
    }
    uint16_t arithmetic(uint16_t left, uint16_t right, bool subtract) {
        const uint32_t wide = subtract ? uint32_t{left} - right : uint32_t{left} + right;
        const auto value = static_cast<uint16_t>(wide);
        uint32_t flags = valueFlags(value, 16) | (((left ^ right ^ value) & 0x10) ? 0x10u : 0u);
        if (subtract ? left < right : wide > 65535) flags |= 1;
        if (subtract ? ((left ^ right) & (left ^ value) & 0x8000) :
                       (~(left ^ right) & (left ^ value) & 0x8000)) flags |= 0x800;
        state_.registers.flags = (state_.registers.flags & ~Arithmetic) | flags;
        return value;
    }
    void multiplyAx(int16_t factor) {
        auto& r = state_.registers;
        const int32_t result = int32_t{std::bit_cast<int16_t>(r.ax)} * factor;
        r.ax = static_cast<uint16_t>(result);
        // Pinned DIMULW uses strict bounds and preserves materialized non-CF/OF flags.
        r.flags = (r.flags & ~uint32_t{0x801}) | ((result > -32768 && result < 32767) ? 0u : 0x801u);
    }
    void advanceOne(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        if (r.cs != state_.gameSegment)
            throw std::domain_error("Frame elapsed caller left game code");
        const auto al = [&](uint16_t offset) { r.ax = static_cast<uint16_t>((r.ax & 0xff00) | bus.readByte(r.ds, offset)); };
        switch (r.ip) {
        case 0x791e: bus.writeByte(r.ds, 0x79ab, static_cast<uint8_t>(r.dx >> 8)); r.ip = 0x7922; break;
        case 0x7922: bus.writeByte(r.ds, 0x79ac, static_cast<uint8_t>(r.dx)); r.ip = 0x7926; break;
        case 0x7926: bus.writeByte(r.ds, 0x79aa, static_cast<uint8_t>(r.cx)); r.ip = 0x792a; break;
        case 0x792a: al(0x79a9); r.ip = 0x792d; break;
        case 0x792d: clearAh(); r.ip = 0x792f; break;
        case 0x792f: r.sp = static_cast<uint16_t>(r.sp - 2u); bus.writeWord(r.ss, r.sp, r.ax); r.ip = 0x7930; break;
        case 0x7930: al(0x79ac); r.ip = 0x7933; break;
        case 0x7933: clearAh(); r.ip = 0x7935; break;
        case 0x7935: r.bx = r.ax; r.ip = 0x7937; break;
        case 0x7937: al(0x79a8); r.ip = 0x793a; break;
        case 0x793a: clearAh(); r.ip = 0x793c; break;
        case 0x793c: r.dx = r.ax; r.ip = 0x793e; break;
        case 0x793e: al(0x79ab); r.ip = 0x7941; break;
        case 0x7941: clearAh(); r.ip = 0x7943; break;
        case 0x7943: r.ax = arithmetic(r.ax, r.dx, true); r.ip = 0x7945; break;
        case 0x7945: multiplyAx(100); r.ip = 0x7948; break;
        case 0x7948: r.cx = r.ax; r.ip = 0x794a; break;
        case 0x794a: al(0x79a4); r.ip = 0x794d; break;
        case 0x794d: clearAh(); r.ip = 0x794f; break;
        case 0x794f: r.dx = r.ax; r.ip = 0x7951; break;
        case 0x7951: al(0x79aa); r.ip = 0x7954; break;
        case 0x7954: clearAh(); r.ip = 0x7956; break;
        case 0x7956: r.ax = arithmetic(r.ax, r.dx, true); r.ip = 0x7958; break;
        case 0x7958: multiplyAx(6000); r.ip = 0x795c; break;
        case 0x795c: r.ax = arithmetic(r.ax, r.cx, false); r.ip = 0x795e; break;
        case 0x795e: r.ax = arithmetic(r.ax, r.bx, false); r.ip = 0x7960; break;
        case 0x7960: r.dx = bus.readWord(r.ss, r.sp); r.sp = static_cast<uint16_t>(r.sp + 2u); r.ip = 0x7961; break;
        case 0x7961: r.ax = arithmetic(r.ax, r.dx, true); r.ip = 0x7963; break;
        case 0x7963: bus.writeWord(r.ds, 0x2074, r.ax); r.ip = 0x7966; break;
        default: throw std::domain_error("Frame elapsed caller reached an unrecovered instruction");
        }
    }
    FrameElapsedSnapshot state_;
};

}
