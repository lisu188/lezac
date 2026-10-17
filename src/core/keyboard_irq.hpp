#pragma once

#include "core/bios_keyboard.hpp"

namespace lezac::core {

struct KeyboardIrqSnapshot {
    TimerIrqRegisters registers;
    uint16_t gameSegment = 0, dataSegment = 0, biosIrqEntry = 0xe987, biosInterceptEntry = 0x11c0;
    uint32_t idToggleMask = 0;
    uint64_t dispatchedInstructions = 0, biosCallbacks = 0;
    bool biosIdle = false, returned = false;
    bool operator==(const KeyboardIrqSnapshot&) const = default;
};

// Complete game IRQ1 and pinned BIOS wrappers. IRQ eligibility and device I/O belong to the caller.
class KeyboardIrqOperation {
public:
    KeyboardIrqOperation(TimerIrqRegisters registers, uint16_t gameSegment, uint32_t idToggleMask)
        : state_{registers, gameSegment, static_cast<uint16_t>(gameSegment + 0xaa2), 0xe987, 0x11c0, idToggleMask} {
        if (registers.cs != gameSegment || registers.ip != 0x1091 || (registers.flags & 0x200u) ||
            (idToggleMask != 0 && idToggleMask != 0x200000))
            throw std::invalid_argument("Keyboard IRQ entry differs from the pinned original");
    }
    explicit KeyboardIrqOperation(KeyboardIrqSnapshot snapshot) : state_(snapshot) {}
    const KeyboardIrqSnapshot& snapshot() const noexcept {return state_;}
    bool returned() const noexcept {return state_.returned;}
    bool needsBiosIdle() const noexcept {return state_.biosIdle;}
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus) {
        uint64_t consumed = 0;
        while (consumed < budget && !state_.returned) {
            if (state_.biosIdle) {
                if (bus.readByte(0x40, 0x18) & 8u) break;
                // The original callback returns after its idle loop and skips CLI/MOV/OUT.
                state_.registers.ip = static_cast<uint16_t>(state_.registers.ip + 5u);
                state_.biosIdle = false;
                continue;
            }
            instruction(bus);
            ++state_.dispatchedInstructions;
            ++consumed;
        }
        return consumed;
    }

private:
    void push(const TimerIrqBus& bus, uint16_t value) {
        auto& r = state_.registers;
        r.sp = static_cast<uint16_t>(r.sp - 2u); bus.writeWord(r.ss, r.sp, value);
    }
    uint16_t pop(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        const auto value = bus.readWord(r.ss, r.sp); r.sp = static_cast<uint16_t>(r.sp + 2u); return value;
    }
    void iret(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        const auto ip = pop(bus), cs = pop(bus), flags = pop(bus);
        const uint32_t mask = 0x7fd5u | state_.idToggleMask;
        r.flags = (r.flags & ~mask) | (uint32_t{flags} & mask) | 2u; r.ip = ip; r.cs = cs;
    }
    void compare(uint8_t left, uint8_t right) {
        const auto value = static_cast<uint8_t>(left - right);
        const uint32_t flags = (left < right ? 1u : 0u) | (std::popcount(value) % 2 == 0 ? 4u : 0u) |
            ((left ^ right ^ value) & 0x10u) | (value == 0 ? 0x40u : 0u) | (value & 0x80u) |
            (((left ^ right) & (left ^ value) & 0x80u) ? 0x800u : 0u);
        state_.registers.flags = (state_.registers.flags & ~uint32_t{0x8d5}) | flags;
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        if (r.cs == 0xf000) {
            if (r.ip == state_.biosInterceptEntry) {
                if ((r.ax >> 8) != 0x4f) throw std::domain_error("Unrecovered BIOS keyboard intercept");
                bus.writeWord(r.ss, static_cast<uint16_t>(r.sp + 4u),
                              static_cast<uint16_t>(bus.readWord(r.ss, static_cast<uint16_t>(r.sp + 4u)) | 1u));
                r.ip = static_cast<uint16_t>(r.ip + 4u); return;
            }
            if (r.ip == static_cast<uint16_t>(state_.biosInterceptEntry + 4u)) {iret(bus); return;}
            const auto offset = static_cast<uint16_t>(r.ip - state_.biosIrqEntry);
            switch (offset) {
            case 0: push(bus, r.ax); ++r.ip; return;
            case 1: r.ax = static_cast<uint16_t>((r.ax & 0xff00u) | bus.inByte(0x60)); r.ip += 2; return;
            case 3: r.ax = static_cast<uint16_t>((r.ax & 255u) | 0x4f00u); r.ip += 2; return;
            case 5: r.flags |= 1; ++r.ip; return;
            case 6:
                push(bus, static_cast<uint16_t>(r.flags)); push(bus, r.cs); push(bus, static_cast<uint16_t>(r.ip + 2u));
                r.flags &= ~uint32_t{0x300}; r.ip = bus.readWord(0, 0x54); r.cs = bus.readWord(0, 0x56);
                if (r.cs != 0xf000 || r.ip != state_.biosInterceptEntry) throw std::domain_error("BIOS INT15 vector differs");
                return;
            case 8: r.ip = static_cast<uint16_t>(r.ip + ((r.flags & 1u) ? 2u : 6u)); return;
            case 10:
                r.ip = static_cast<uint16_t>(r.ip + 4u);
                state_.biosIdle = handleBiosKeyboardScan(static_cast<uint8_t>(r.ax), bus) == BiosKeyboardResult::NeedIdle;
                ++state_.biosCallbacks; return;
            case 14: r.flags &= ~uint32_t{0x200}; ++r.ip; return;
            case 15: r.ax = static_cast<uint16_t>((r.ax & 0xff00u) | 0x20u); r.ip += 2; return;
            case 17: bus.outByte(0x20, static_cast<uint8_t>(r.ax)); r.ip += 2; return;
            case 19: r.ax = pop(bus); ++r.ip; return;
            case 20: iret(bus); return;
            default: throw std::domain_error("Unrecovered BIOS IRQ1 instruction");
            }
        }
        if (r.cs != state_.gameSegment) throw std::domain_error("Keyboard IRQ left the original code segment");
        static constexpr std::array<uint8_t, 10> scans{0x2c, 0x2d, 0x32, 0x31, 0x2e, 0x4b, 0x4d, 0x52, 0x48, 0x50};
        static constexpr std::array<uint16_t, 10> bank{0x1b79, 0x1b7a, 0x1b78, 0x1b7b, 0x1b7c,
                                                     0x1b7e, 0x1b7f, 0x1b80, 0x1b7d, 0x1b81};
        const bool make = r.ip >= 0x10a5 && r.ip < 0x10f5;
        const bool release = r.ip >= 0x10f7 && r.ip < 0x1147;
        if (make || release) {
            const unsigned at = r.ip - (make ? 0x10a5u : 0x10f7u), index = at / 8, offset = at % 8;
            if (offset == 0) {compare(static_cast<uint8_t>(r.ax), static_cast<uint8_t>(scans[index] + (make ? 0 : 128))); r.ip += 2;}
            else if (offset == 2) r.ip = static_cast<uint16_t>(r.ip + ((r.flags & 0x40u) ? 2u : 6u));
            else if (offset == 4) {bus.writeByte(r.ds, bank[index], static_cast<uint8_t>(r.ax >> 8)); r.ip += 4;}
            else throw std::domain_error("Keyboard compare/store instruction boundary differs");
            return;
        }
        switch (r.ip) {
        case 0x1091: push(bus, r.ax); ++r.ip; break;
        case 0x1092: push(bus, r.bx); ++r.ip; break;
        case 0x1093: push(bus, r.cx); ++r.ip; break;
        case 0x1094: push(bus, r.dx); ++r.ip; break;
        case 0x1095: push(bus, r.si); ++r.ip; break;
        case 0x1096: push(bus, r.di); ++r.ip; break;
        case 0x1097: push(bus, r.ds); ++r.ip; break;
        case 0x1098: push(bus, r.es); ++r.ip; break;
        case 0x1099: push(bus, r.bp); ++r.ip; break;
        case 0x109a: r.bp = r.sp; r.ip += 2; break;
        case 0x109c: r.ax = state_.dataSegment; r.ip += 3; break;
        case 0x109f: r.ds = r.ax; r.ip += 2; break;
        case 0x10a1: r.ax = static_cast<uint16_t>((r.ax & 0xff00u) | bus.inByte(0x60)); r.ip += 2; break;
        case 0x10a3: r.ax = static_cast<uint16_t>((r.ax & 255u) | 0x100u); r.ip += 2; break;
        case 0x10f5: r.ax &= 255u; r.flags = (r.flags & ~uint32_t{0x8d5}) | 0x44u; r.ip += 2; break;
        case 0x1147: push(bus, static_cast<uint16_t>(r.flags)); ++r.ip; break;
        case 0x1148:
            push(bus, r.cs); push(bus, 0x114c); r.ip = bus.readWord(r.ds, 0x1b60); r.cs = bus.readWord(r.ds, 0x1b62);
            if (r.cs != 0xf000 || r.ip != state_.biosIrqEntry) throw std::domain_error("Chained BIOS IRQ1 vector differs");
            break;
        case 0x114c: r.sp = r.bp; r.bp = pop(bus); ++r.ip; break;
        case 0x114d: r.es = pop(bus); ++r.ip; break;
        case 0x114e: r.ds = pop(bus); ++r.ip; break;
        case 0x114f: r.di = pop(bus); ++r.ip; break;
        case 0x1150: r.si = pop(bus); ++r.ip; break;
        case 0x1151: r.dx = pop(bus); ++r.ip; break;
        case 0x1152: r.cx = pop(bus); ++r.ip; break;
        case 0x1153: r.bx = pop(bus); ++r.ip; break;
        case 0x1154: r.ax = pop(bus); ++r.ip; break;
        case 0x1155: iret(bus); state_.returned = true; break;
        default: throw std::domain_error("Unrecovered original keyboard IRQ1 instruction");
        }
    }
    KeyboardIrqSnapshot state_;
};

}
