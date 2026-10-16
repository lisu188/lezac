#pragma once

#include <bit>
#include <cstdint>
#include <functional>
#include <stdexcept>

namespace lezac::core {

struct CrtDelayRegisters {
    uint16_t ax = 0, bx = 0, cx = 0, dx = 0, di = 0, bp = 0;
    uint16_t cs = 0, ds = 0, es = 0, ss = 0, sp = 0, ip = 0x029c;
    uint32_t flags = 0x0202;
    bool operator==(const CrtDelayRegisters&) const = default;
};

struct CrtDelayBus {
    std::function<uint8_t(uint16_t, uint16_t)> readByte;
    std::function<uint16_t(uint16_t, uint16_t)> readWord;
    std::function<void(uint16_t, uint16_t, uint16_t)> writeWord;
};

struct CrtDelaySnapshot {
    CrtDelayRegisters registers{};
    uint16_t routineSegment = 0;
    uint64_t dispatchedInstructions = 0;
    uint32_t definedFlags = ~uint32_t{0};
    bool returned = false;
    bool operator==(const CrtDelaySnapshot&) const = default;
};

// Original CRT CS+084a:029c..02c8. Work units are dispatches, not cycles or time.
class CrtDelayOperation {
public:
    explicit CrtDelayOperation(CrtDelayRegisters registers)
        : state_{registers, registers.cs} {
        if (registers.ip != 0x029c) throw std::invalid_argument("CRT delay entry IP differs");
    }
    explicit CrtDelayOperation(CrtDelaySnapshot snapshot) : state_(snapshot) {}

    const CrtDelaySnapshot& snapshot() const noexcept { return state_; }
    bool returned() const noexcept { return state_.returned; }

    uint64_t advance(uint64_t budget, const CrtDelayBus& bus) {
        uint64_t consumed = 0;
        while (consumed < budget && !state_.returned) {
            advanceOne(bus);
            ++state_.dispatchedInstructions;
            ++consumed;
        }
        return consumed;
    }

private:
    static constexpr uint32_t Carry = 0x0001, Parity = 0x0004, Auxiliary = 0x0010;
    static constexpr uint32_t Zero = 0x0040, Sign = 0x0080, Overflow = 0x0800;
    static constexpr uint32_t Arithmetic = Carry | Parity | Auxiliary | Zero | Sign | Overflow;

    static uint32_t valueFlags(uint16_t value, uint16_t signBit) {
        return (value == 0 ? Zero : 0u) | ((value & signBit) ? Sign : 0u) |
            (std::popcount(static_cast<uint8_t>(value)) % 2 == 0 ? Parity : 0u);
    }
    void replaceFlags(uint32_t mask, uint32_t value) {
        auto& registers = state_.registers;
        registers.flags = (registers.flags & ~mask) | value;
        state_.definedFlags |= mask;
    }
    void logic16(uint16_t value) {
        replaceFlags(Arithmetic & ~Auxiliary, valueFlags(value, 0x8000));
        // OR/XOR leave AF undefined; retaining its value is not a fidelity claim.
        state_.definedFlags &= ~Auxiliary;
    }
    void decrement16(uint16_t& word) {
        const uint16_t before = word;
        word = static_cast<uint16_t>(before - 1u);
        replaceFlags(Arithmetic & ~Carry, valueFlags(word, 0x8000) |
            ((before & 0x000f) == 0 ? Auxiliary : 0u) | (before == 0x8000 ? Overflow : 0u));
    }
    void compare8(uint8_t left, uint8_t right) {
        const auto result = static_cast<uint8_t>(left - right);
        replaceFlags(Arithmetic, valueFlags(result, 0x80) | (left < right ? Carry : 0u) |
            (((left ^ right ^ result) & 0x10) ? Auxiliary : 0u) |
            (((left ^ right) & (left ^ result) & 0x80) ? Overflow : 0u));
    }
    void advanceOne(const CrtDelayBus& bus) {
        auto& r = state_.registers;
        if (r.cs != state_.routineSegment) throw std::domain_error("CRT delay left recovered code segment");
        switch (r.ip) {
        case 0x029c: r.bx = r.sp; r.ip = 0x029e; break;
        case 0x029e: r.dx = bus.readWord(r.ss, static_cast<uint16_t>(r.bx + 4u)); r.ip = 0x02a2; break;
        case 0x02a2: logic16(r.dx); r.ip = 0x02a4; break;
        case 0x02a4: r.ip = (r.flags & Zero) ? 0x02ba : 0x02a6; break;
        case 0x02a6: r.ax = 0x0040; r.ip = 0x02a9; break;
        case 0x02a9: r.es = r.ax; r.ip = 0x02ab; break;
        case 0x02ab: r.di = 0; logic16(r.di); r.ip = 0x02ad; break;
        case 0x02ad: r.ax = static_cast<uint16_t>((r.ax & 0xff00u) | bus.readByte(r.es, r.di)); r.ip = 0x02b0; break;
        case 0x02b0: r.cx = bus.readWord(r.ds, 0x7f68); r.ip = 0x02b4; break;
        case 0x02b4: {
            const auto nextSp = static_cast<uint16_t>(r.sp - 2u);
            bus.writeWord(r.ss, nextSp, 0x02b7);
            r.sp = nextSp;
            r.ip = 0x02bd;
            break;
        }
        case 0x02b7: decrement16(r.dx); r.ip = 0x02b8; break;
        case 0x02b8: r.ip = (r.flags & Zero) ? 0x02ba : 0x02b0; break;
        case 0x02ba: {
            const uint16_t returnIp = bus.readWord(r.ss, r.sp);
            const uint16_t returnCs = bus.readWord(r.ss, static_cast<uint16_t>(r.sp + 2u));
            r.sp = static_cast<uint16_t>(r.sp + 6u);
            r.ip = returnIp;
            r.cs = returnCs;
            state_.returned = true;
            break;
        }
        case 0x02bd: r.bx = 4; r.ip = 0x02c0; break;
        case 0x02c0: decrement16(r.bx); r.ip = 0x02c1; break;
        case 0x02c1: r.ip = (r.flags & Zero) ? 0x02c3 : 0x02c0; break;
        case 0x02c3: compare8(static_cast<uint8_t>(r.ax), bus.readByte(r.es, r.di)); r.ip = 0x02c6; break;
        case 0x02c6:
            r.cx = static_cast<uint16_t>(r.cx - 1u);
            r.ip = r.cx != 0 && (r.flags & Zero) ? 0x02bd : 0x02c8;
            break;
        case 0x02c8:
            r.ip = bus.readWord(r.ss, r.sp);
            r.sp = static_cast<uint16_t>(r.sp + 2u);
            break;
        default: throw std::domain_error("CRT delay reached an unrecovered instruction");
        }
    }

    CrtDelaySnapshot state_;
};

}
