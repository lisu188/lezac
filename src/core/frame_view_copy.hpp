#pragma once

#include "core/dos_time.hpp"
#include "core/timer_irq.hpp"

#include <bit>
#include <functional>
#include <stdexcept>

namespace lezac::core {

struct FrameViewCopySnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment = 0;
    uint64_t dispatchedInstructions = 0, transferredWords = 0;
    bool returned = false;
    bool operator==(const FrameViewCopySnapshot&) const = default;
};

// Original driver 08AC:03C8..0416. REP dispatch budgets are not CPU work credits.
class FrameViewCopyOperation {
public:
    using CopyBudget = std::function<uint16_t(uint16_t)>;

    FrameViewCopyOperation(DosGetTimeRegisters registers, uint16_t gameSegment)
        : state_{registers, gameSegment} {
        if (registers.cs != driver() || registers.ds != static_cast<uint16_t>(gameSegment + 0xaa2) ||
            registers.ip != 0x03c8)
            throw std::invalid_argument("View copy entry differs");
    }
    explicit FrameViewCopyOperation(FrameViewCopySnapshot state) : state_(state) {
        if (!state.returned && (state.registers.cs != driver() || !instruction(state.registers.ip)))
            throw std::invalid_argument("View copy resume instruction differs");
    }
    const FrameViewCopySnapshot& snapshot() const noexcept { return state_; }
    bool returned() const noexcept { return state_.returned; }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus, const CopyBudget& copyBudget) {
        uint64_t consumed = 0;
        while (consumed < budget && !returned()) {
            advanceOne(bus, copyBudget);
            ++state_.dispatchedInstructions;
            ++consumed;
        }
        return consumed;
    }

private:
    static constexpr uint32_t Arithmetic = 0x8d5;
    FrameViewCopySnapshot state_;
    uint16_t driver() const { return static_cast<uint16_t>(state_.gameSegment + 0x8ac); }
    static bool instruction(uint16_t ip) {
        switch (ip) {
        case 0x3c8: case 0x3cb: case 0x3cc: case 0x3cf: case 0x3d1: case 0x3d5:
        case 0x3d9: case 0x3dc: case 0x3e0: case 0x3e2: case 0x3e6: case 0x3e8:
        case 0x3ec: case 0x3ef: case 0x3f1: case 0x3f5: case 0x3f8: case 0x3fc:
        case 0x3ff: case 0x403: case 0x405: case 0x407: case 0x409: case 0x40b:
        case 0x40e: case 0x410: case 0x412: case 0x413: case 0x416: return true;
        default: return false;
        }
    }
    static uint32_t valueFlags(uint16_t value) {
        return (value == 0 ? 0x40u : 0u) | (value & 0x8000 ? 0x80u : 0u) |
            (std::popcount(static_cast<uint8_t>(value)) % 2 == 0 ? 4u : 0u);
    }
    uint16_t arithmetic(uint16_t left, uint16_t right, bool subtract = false) {
        const uint32_t wide = subtract ? uint32_t{left} - right : uint32_t{left} + right;
        const auto value = static_cast<uint16_t>(wide);
        uint32_t flags = valueFlags(value) | ((left ^ right ^ value) & 16u);
        if (subtract ? left < right : wide > 65535u) flags |= 1;
        if (subtract ? ((left ^ right) & (left ^ value) & 0x8000) :
                       (~(left ^ right) & (left ^ value) & 0x8000)) flags |= 0x800;
        state_.registers.flags = (state_.registers.flags & ~Arithmetic) | flags;
        return value;
    }
    void advanceOne(const TimerIrqBus& bus, const CopyBudget& copyBudget) {
        auto& r = state_.registers;
        const auto pop = [&] { const auto value = bus.readWord(r.ss, r.sp);
            r.sp = static_cast<uint16_t>(r.sp + 2u); return value; };
        switch (r.ip) {
        case 0x3c8: r.dx = 0x3da; r.ip = 0x3cb; break;
        case 0x3cb: r.sp = static_cast<uint16_t>(r.sp - 2u); bus.writeWord(r.ss, r.sp, r.ds); r.ip = 0x3cc; break;
        case 0x3cc: r.ax = 0xa000; r.ip = 0x3cf; break;
        case 0x3cf: r.es = r.ax; r.ip = 0x3d1; break;
        case 0x3d1: r.di = bus.readWord(r.ds, 0xc1f4); r.ip = 0x3d5; break;
        case 0x3d5: r.si = bus.readWord(r.ds, 0xc214); r.ip = 0x3d9; break;
        case 0x3d9: r.ax = bus.readWord(r.ds, 0xc1ec); r.ip = 0x3dc; break;
        case 0x3dc: r.bx = bus.readWord(r.ds, 0xc20c); r.ip = 0x3e0; break;
        case 0x3e0: {
            const uint32_t product = uint32_t{r.ax} * r.bx;
            r.ax = static_cast<uint16_t>(product); r.dx = static_cast<uint16_t>(product >> 16);
            // Pinned DOSBox normal-core materialization of otherwise undefined MUL flags.
            r.flags = (r.flags & ~uint32_t{0x841}) | (r.dx ? 0x801u : 0u) | (r.ax == 0 ? 0x40u : 0u);
            r.ip = 0x3e2; break;
        }
        case 0x3e2: r.ax = arithmetic(r.ax, bus.readWord(r.ds, 0xc20a)); r.ip = 0x3e6; break;
        case 0x3e6: r.si = arithmetic(r.si, r.ax); r.ip = 0x3e8; break;
        case 0x3e8: r.dx = bus.readWord(r.ds, 0xc1ec); r.ip = 0x3ec; break;
        case 0x3ec: r.dx = arithmetic(r.dx, 8, true); r.ip = 0x3ef; break;
        case 0x3ef: {
            const auto old = r.dx; r.dx = static_cast<uint16_t>(old >> 1);
            r.flags = (r.flags & ~Arithmetic) | valueFlags(r.dx) | 16u |
                (old & 1u) | (old & 0x8000 ? 0x800u : 0u);
            r.ip = 0x3f1; break;
        }
        case 0x3f1: r.bx = bus.readWord(r.ds, 0xc206); r.ip = 0x3f5; break;
        case 0x3f5: r.bx = arithmetic(r.bx, 8); r.ip = 0x3f8; break;
        case 0x3f8: r.cx = bus.readWord(r.ds, 0xc1ee); r.ip = 0x3fc; break;
        case 0x3fc: r.cx = arithmetic(r.cx, 8, true); r.ip = 0x3ff; break;
        case 0x3ff: r.ds = bus.readWord(r.ds, 0xc212); r.ip = 0x403; break;
        case 0x403: r.ax = r.cx; r.ip = 0x405; break;
        case 0x405: r.cx = r.dx; r.ip = 0x407; break;
        case 0x407: {
            const auto count = r.cx ? copyBudget(r.cx) : uint16_t{0};
            if ((r.cx && !count) || count > r.cx)
                throw std::invalid_argument("View copy REP budget differs");
            const auto step = r.flags & 0x400 ? -2 : 2;
            for (uint32_t i = 0; i < count; ++i) {
                const auto value = bus.readWord(r.ds, r.si);
                bus.writeWord(r.es, r.di, value);
                r.si = static_cast<uint16_t>(r.si + step);
                r.di = static_cast<uint16_t>(r.di + step);
            }
            r.cx = static_cast<uint16_t>(r.cx - count);
            state_.transferredWords += count;
            if (!r.cx) r.ip = 0x409;
            break;
        }
        case 0x409: r.di = arithmetic(r.di, r.bx); r.ip = 0x40b; break;
        case 0x40b: r.si = arithmetic(r.si, 8); r.ip = 0x40e; break;
        case 0x40e: r.cx = r.ax; r.ip = 0x410; break;
        case 0x410: r.cx = static_cast<uint16_t>(r.cx - 1u); r.ip = r.cx ? 0x403 : 0x412; break;
        case 0x412: r.ds = pop(); r.ip = 0x413; break;
        case 0x413: r.dx = 0x3da; r.ip = 0x416; break;
        case 0x416: r.ip = pop(); r.cs = pop(); state_.returned = true; break;
        default: throw std::domain_error("View copy reached an unrecovered instruction");
        }
    }
};

} // namespace lezac::core
