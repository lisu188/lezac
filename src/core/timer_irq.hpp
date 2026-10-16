#pragma once

#include <bit>
#include <cstdint>
#include <functional>
#include <stdexcept>

namespace lezac::core {

struct TimerIrqRegisters {
    uint16_t ax = 0, bx = 0, cx = 0, dx = 0, si = 0, di = 0, bp = 0;
    uint16_t cs = 0, ds = 0, es = 0, ss = 0, sp = 0, ip = 0;
    uint32_t flags = 0x0202;
    bool operator==(const TimerIrqRegisters&) const = default;
};

struct TimerIrqBus {
    std::function<uint8_t(uint16_t, uint16_t)> readByte;
    std::function<uint16_t(uint16_t, uint16_t)> readWord;
    std::function<uint32_t(uint16_t, uint16_t)> readDword;
    std::function<void(uint16_t, uint16_t, uint8_t)> writeByte;
    std::function<void(uint16_t, uint16_t, uint16_t)> writeWord;
    std::function<void(uint16_t, uint16_t, uint32_t)> writeDword;
    std::function<uint8_t(uint16_t)> inByte;
    std::function<void(uint16_t, uint8_t)> outByte;
};

struct TimerIrqSnapshot {
    TimerIrqRegisters registers{};
    uint16_t gameSegment = 0, dataSegment = 0, crtSegment = 0;
    uint16_t biosSegment = 0xf000, biosEntry = 0xfea5;
    uint32_t idToggleMask = 0;
    uint32_t definedFlags = 0x0700;
    uint64_t dispatchedInstructions = 0;
    bool biosWrapper = true, returned = false;
    bool operator==(const TimerIrqSnapshot&) const = default;
};

// Pinned DOSBox IRQ0 callback and unchanged LEZAC INT1C/Sound/NoSound instructions.
// Hardware IRQ delivery and PIC/I/O cycle scheduling belong to the caller.
// BIOS entry flags must be materialized by the caller's interrupt delivery.
class TimerIrqOperation {
public:
    TimerIrqOperation(TimerIrqRegisters registers, uint16_t gameSegment, uint32_t idToggleMask,
                      bool biosWrapper = true)
        : state_{registers, gameSegment, static_cast<uint16_t>(gameSegment + 0x0aa2),
                 static_cast<uint16_t>(gameSegment + 0x084a), 0xf000, 0xfea5,
                 idToggleMask, 0x0700, 0, biosWrapper} {
        if ((idToggleMask != 0 && idToggleMask != 0x200000) ||
            (biosWrapper ? registers.cs != 0xf000 || registers.ip != 0xfea5 :
                           registers.cs != gameSegment || registers.ip != 0x0fbe))
            throw std::invalid_argument("Timer IRQ entry differs");
    }
    explicit TimerIrqOperation(TimerIrqSnapshot snapshot) : state_(snapshot) {}

    const TimerIrqSnapshot& snapshot() const noexcept { return state_; }
    bool returned() const noexcept { return state_.returned; }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus) {
        uint64_t consumed = 0;
        while (consumed < budget && !state_.returned) {
            advanceOne(bus);
            ++state_.dispatchedInstructions;
            ++consumed;
        }
        return consumed;
    }

private:
    static constexpr uint32_t Carry = 1, Parity = 4, Auxiliary = 0x10, Zero = 0x40;
    static constexpr uint32_t Sign = 0x80, Overflow = 0x800, Arithmetic = 0x8d5;
    static uint32_t valueFlags(uint16_t value, unsigned bits) {
        return (value == 0 ? Zero : 0u) | ((value & (1u << (bits - 1))) ? Sign : 0u) |
            (std::popcount(static_cast<uint8_t>(value)) % 2 == 0 ? Parity : 0u);
    }
    void replaceFlags(uint32_t mask, uint32_t flags) {
        auto& r = state_.registers;
        r.flags = (r.flags & ~mask) | flags;
        state_.definedFlags |= mask;
    }
    uint16_t arithmetic(uint16_t left, uint16_t right, unsigned bits, bool subtract,
                        bool preserveCarry = false) {
        const uint32_t mask = bits == 8 ? 0xffu : 0xffffu;
        const uint32_t sign = 1u << (bits - 1);
        const uint32_t wide = subtract ? uint32_t{left} - right : uint32_t{left} + right;
        const uint16_t value = static_cast<uint16_t>(wide & mask);
        uint32_t flags = valueFlags(value, bits) | (((left ^ right ^ value) & 0x10) ? Auxiliary : 0u);
        if (subtract ? left < right : wide > mask) flags |= Carry;
        if (subtract ? ((left ^ right) & (left ^ value) & sign) :
                       (~(left ^ right) & (left ^ value) & sign)) flags |= Overflow;
        replaceFlags(Arithmetic & (preserveCarry ? ~Carry : ~uint32_t{0}), flags & (preserveCarry ? ~Carry : ~uint32_t{0}));
        return value;
    }
    void logic8(uint8_t value) {
        replaceFlags(Arithmetic & ~Auxiliary, valueFlags(value, 8));
        state_.definedFlags &= ~Auxiliary;
    }
    void shiftAx() {
        auto& r = state_.registers;
        const uint16_t before = r.ax;
        r.ax = static_cast<uint16_t>(r.ax << 1);
        replaceFlags(Arithmetic & ~Auxiliary, valueFlags(r.ax, 16) | ((before & 0x8000) ? Carry : 0u) |
            (((before ^ r.ax) & 0x8000) ? Overflow : 0u));
        state_.definedFlags &= ~Auxiliary;
    }
    void setAl(uint8_t value) { auto& r = state_.registers; r.ax = static_cast<uint16_t>((r.ax & 0xff00) | value); }
    void push(const TimerIrqBus& bus, uint16_t word) {
        auto& r = state_.registers;
        const auto sp = static_cast<uint16_t>(r.sp - 2u);
        bus.writeWord(r.ss, sp, word);
        r.sp = sp;
    }
    uint16_t pop(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        const auto word = bus.readWord(r.ss, r.sp);
        r.sp = static_cast<uint16_t>(r.sp + 2u);
        return word;
    }
    void farCall(const TimerIrqBus& bus, uint16_t ip, uint16_t returnIp) {
        auto& r = state_.registers;
        push(bus, r.cs); push(bus, returnIp);
        r.cs = state_.crtSegment; r.ip = ip;
    }
    void farReturn(const TimerIrqBus& bus, uint16_t discard) {
        auto& r = state_.registers;
        const auto ip = pop(bus), cs = pop(bus);
        r.ip = ip; r.cs = cs; r.sp = static_cast<uint16_t>(r.sp + discard);
    }
    void iret(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        const auto ip = pop(bus), cs = pop(bus), flags = pop(bus);
        const uint32_t mask = 0x7fd5u | state_.idToggleMask;
        r.ip = ip; r.cs = cs; r.flags = (r.flags & ~mask) | (uint32_t{flags} & mask) | 2u;
        state_.definedFlags |= mask | 2u;
    }
    void les(const TimerIrqBus& bus, uint16_t segment, uint16_t offset) {
        auto& r = state_.registers;
        r.di = bus.readWord(segment, offset);
        r.es = bus.readWord(segment, static_cast<uint16_t>(offset + 2u));
    }
    void advanceOne(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        if (state_.biosWrapper && r.cs == state_.biosSegment) {
            switch (r.ip) {
            case 0xfea5: {
                bus.writeDword(0x40, 0x6c, bus.readDword(0x40, 0x6c) + uint32_t{1});
                const auto motor = bus.readByte(0x40, 0x40);
                if (motor) bus.writeByte(0x40, 0x40, static_cast<uint8_t>(motor - 1u));
                bus.writeByte(0x40, 0x3f, static_cast<uint8_t>(bus.readByte(0x40, 0x3f) & 0xf0u));
                r.ip = 0xfea9; return;
            }
            case 0xfea9: push(bus, r.ax); ++r.ip; return;
            case 0xfeaa: push(bus, r.dx); ++r.ip; return;
            case 0xfeab: push(bus, r.ds); ++r.ip; return;
            case 0xfeac: {
                push(bus, static_cast<uint16_t>(r.flags)); push(bus, r.cs); push(bus, 0xfeae);
                r.flags &= ~uint32_t{0x300};
                r.ip = bus.readWord(0, 0x70); r.cs = bus.readWord(0, 0x72);
                return;
            }
            case 0xfeae: r.flags &= ~uint32_t{0x200}; ++r.ip; return;
            case 0xfeaf: r.ds = pop(bus); ++r.ip; return;
            case 0xfeb0: r.dx = pop(bus); ++r.ip; return;
            case 0xfeb1: setAl(0x20); r.ip = 0xfeb3; return;
            case 0xfeb3: bus.outByte(0x20, static_cast<uint8_t>(r.ax)); r.ip = 0xfeb5; return;
            case 0xfeb5: r.ax = pop(bus); ++r.ip; return;
            case 0xfeb6: iret(bus); state_.returned = true; return;
            default: throw std::domain_error("Timer IRQ left BIOS callback instructions");
            }
        }
        if (r.cs == state_.crtSegment) {
            switch (r.ip) {
            case 0x02c9: r.bx = r.sp; r.ip = 0x02cb; return;
            case 0x02cb: r.bx = bus.readWord(r.ss, static_cast<uint16_t>(r.bx + 4u)); r.ip = 0x02cf; return;
            case 0x02cf: r.ax = 0x34dd; r.ip = 0x02d2; return;
            case 0x02d2: r.dx = 0x0012; r.ip = 0x02d5; return;
            case 0x02d5: arithmetic(r.dx, r.bx, 16, true); r.ip = 0x02d7; return;
            case 0x02d7: r.ip = (r.flags & Carry) ? 0x02d9 : 0x02f3; return;
            case 0x02d9: {
                const uint32_t dividend = (uint32_t{r.dx} << 16) | r.ax;
                if (r.bx == 0 || dividend / r.bx > 65535) throw std::domain_error("Original speaker divide fault");
                r.ax = static_cast<uint16_t>(dividend / r.bx); r.dx = static_cast<uint16_t>(dividend % r.bx);
                state_.definedFlags &= ~Arithmetic;
                r.ip = 0x02db; return;
            }
            case 0x02db: r.bx = r.ax; r.ip = 0x02dd; return;
            case 0x02dd: setAl(bus.inByte(0x61)); r.ip = 0x02df; return;
            case 0x02df: logic8(static_cast<uint8_t>(r.ax & 3u)); r.ip = 0x02e1; return;
            case 0x02e1: r.ip = (r.flags & Zero) ? 0x02e3 : 0x02eb; return;
            case 0x02e3: setAl(static_cast<uint8_t>(r.ax | 3u)); logic8(static_cast<uint8_t>(r.ax)); r.ip = 0x02e5; return;
            case 0x02e5: bus.outByte(0x61, static_cast<uint8_t>(r.ax)); r.ip = 0x02e7; return;
            case 0x02e7: setAl(0xb6); r.ip = 0x02e9; return;
            case 0x02e9: bus.outByte(0x43, static_cast<uint8_t>(r.ax)); r.ip = 0x02eb; return;
            case 0x02eb: setAl(static_cast<uint8_t>(r.bx)); r.ip = 0x02ed; return;
            case 0x02ed: bus.outByte(0x42, static_cast<uint8_t>(r.ax)); r.ip = 0x02ef; return;
            case 0x02ef: setAl(static_cast<uint8_t>(r.bx >> 8)); r.ip = 0x02f1; return;
            case 0x02f1: bus.outByte(0x42, static_cast<uint8_t>(r.ax)); r.ip = 0x02f3; return;
            case 0x02f3: farReturn(bus, 2); return;
            case 0x02f6: setAl(bus.inByte(0x61)); r.ip = 0x02f8; return;
            case 0x02f8: setAl(static_cast<uint8_t>(r.ax & 0xfcu)); logic8(static_cast<uint8_t>(r.ax)); r.ip = 0x02fa; return;
            case 0x02fa: bus.outByte(0x61, static_cast<uint8_t>(r.ax)); r.ip = 0x02fc; return;
            case 0x02fc: farReturn(bus, 0); return;
            default: throw std::domain_error("Timer IRQ left CRT speaker instructions");
            }
        }
        if (r.cs != state_.gameSegment) throw std::domain_error("Timer IRQ reached an unrecovered vector");
        switch (r.ip) {
        case 0x0fbe: push(bus, r.ax); ++r.ip; break;
        case 0x0fbf: push(bus, r.bx); ++r.ip; break;
        case 0x0fc0: push(bus, r.cx); ++r.ip; break;
        case 0x0fc1: push(bus, r.dx); ++r.ip; break;
        case 0x0fc2: push(bus, r.si); ++r.ip; break;
        case 0x0fc3: push(bus, r.di); ++r.ip; break;
        case 0x0fc4: push(bus, r.ds); ++r.ip; break;
        case 0x0fc5: push(bus, r.es); ++r.ip; break;
        case 0x0fc6: push(bus, r.bp); r.bp = r.sp; r.sp = static_cast<uint16_t>(r.sp - 4u); r.ip = 0x0fca; break;
        case 0x0fca: r.ax = state_.dataSegment; r.ip = 0x0fcd; break;
        case 0x0fcd: r.ds = r.ax; r.ip = 0x0fcf; break;
        case 0x0fcf: arithmetic(bus.readByte(r.ds, 0x79c4), 0, 8, true); r.ip = 0x0fd4; break;
        case 0x0fd4: r.ip = (r.flags & Zero) ? 0x0fd6 : 0x0fd9; break;
        case 0x0fd6: r.ip = 0x1087; break;
        case 0x0fd9: arithmetic(bus.readWord(r.ds, 0x78c0), 0xea60, 16, true); r.ip = 0x0fdf; break;
        case 0x0fdf: r.ip = (r.flags & (Carry | Zero)) ? 0x1007 : 0x0fe1; break;
        case 0x0fe1: r.ax = bus.readWord(r.ds, 0x78c0); r.ip = 0x0fe4; break;
        case 0x0fe4: r.ax = arithmetic(r.ax, 0xea42, 16, true); r.ip = 0x0fe7; break;
        case 0x0fe7: push(bus, r.ax); r.ip = 0x0fe8; break;
        case 0x0fe8: farCall(bus, 0x02c9, 0x0fed); break;
        case 0x0fed: bus.writeWord(r.ds, 0x78c0, arithmetic(bus.readWord(r.ds, 0x78c0), 4, 16, true)); r.ip = 0x0ff2; break;
        case 0x0ff2: arithmetic(bus.readWord(r.ds, 0x78c0), 0xea60, 16, true); r.ip = 0x0ff8; break;
        case 0x0ff8: r.ip = (r.flags & (Carry | Zero)) ? 0x0ffa : 0x1004; break;
        case 0x0ffa: bus.writeByte(r.ds, 0x79c4, 0); r.ip = 0x0fff; break;
        case 0x0fff: farCall(bus, 0x02f6, 0x1004); break;
        case 0x1004: r.ip = 0x1087; break;
        case 0x1007: bus.writeByte(r.ds, 0x79a0, static_cast<uint8_t>(arithmetic(bus.readByte(r.ds, 0x79a0), 1, 8, false, true))); r.ip = 0x100b; break;
        case 0x100b: setAl(bus.readByte(r.ds, 0x79a0)); r.ip = 0x100e; break;
        case 0x100e: arithmetic(static_cast<uint8_t>(r.ax), bus.readByte(r.ds, 0x79a2), 8, true); r.ip = 0x1012; break;
        case 0x1012: r.ip = (r.flags & Zero) ? 0x1014 : 0x1079; break;
        case 0x1014: bus.writeWord(r.ds, 0x78c0, arithmetic(bus.readWord(r.ds, 0x78c0), 1, 16, false, true)); r.ip = 0x1018; break;
        case 0x1018: r.ax = bus.readWord(r.ds, 0x78c0); r.ip = 0x101b; break;
        case 0x101b: shiftAx(); r.ip = 0x101d; break;
        case 0x101d: r.si = r.ax; r.ip = 0x101f; break;
        case 0x101f: shiftAx(); r.ip = 0x1021; break;
        case 0x1021: r.ax = arithmetic(r.ax, r.si, 16, false); r.ip = 0x1023; break;
        case 0x1023: les(bus, r.ds, 0x79c0); r.ip = 0x1027; break;
        case 0x1027: r.di = arithmetic(r.di, r.ax, 16, false); r.ip = 0x1029; break;
        case 0x1029: r.di = arithmetic(r.di, 0xfffa, 16, false); r.ip = 0x102d; break;
        case 0x102d: bus.writeWord(r.ss, static_cast<uint16_t>(r.bp - 4u), r.di); r.ip = 0x1030; break;
        case 0x1030: bus.writeWord(r.ss, static_cast<uint16_t>(r.bp - 2u), r.es); r.ip = 0x1033; break;
        case 0x1033: les(bus, r.ss, static_cast<uint16_t>(r.bp - 4u)); r.ip = 0x1036; break;
        case 0x1036: arithmetic(bus.readWord(r.es, r.di), 0x7530, 16, true); r.ip = 0x103b; break;
        case 0x103b: r.ip = (r.flags & Zero) ? 0x103d : 0x1053; break;
        case 0x103d: farCall(bus, 0x02f6, 0x1042); break;
        case 0x1042: bus.writeByte(r.ds, 0x79c4, 0); r.ip = 0x1047; break;
        case 0x1047: bus.writeByte(r.ds, 0x79a0, 0); r.ip = 0x104c; break;
        case 0x104c: bus.writeByte(r.ds, 0x79a2, 1); r.ip = 0x1051; break;
        case 0x1051: r.ip = 0x1077; break;
        case 0x1053: les(bus, r.ss, static_cast<uint16_t>(r.bp - 4u)); r.ip = 0x1056; break;
        case 0x1056: push(bus, bus.readWord(r.es, r.di)); r.ip = 0x1059; break;
        case 0x1059: farCall(bus, 0x02c9, 0x105e); break;
        case 0x105e: les(bus, r.ss, static_cast<uint16_t>(r.bp - 4u)); r.ip = 0x1061; break;
        case 0x1061: setAl(bus.readByte(r.es, static_cast<uint16_t>(r.di + 2u))); r.ip = 0x1065; break;
        case 0x1065: bus.writeByte(r.ds, 0x79a1, static_cast<uint8_t>(r.ax)); r.ip = 0x1068; break;
        case 0x1068: les(bus, r.ss, static_cast<uint16_t>(r.bp - 4u)); r.ip = 0x106b; break;
        case 0x106b: setAl(bus.readByte(r.es, static_cast<uint16_t>(r.di + 3u))); r.ip = 0x106f; break;
        case 0x106f: bus.writeByte(r.ds, 0x79a2, static_cast<uint8_t>(r.ax)); r.ip = 0x1072; break;
        case 0x1072: bus.writeByte(r.ds, 0x79a0, 0); r.ip = 0x1077; break;
        case 0x1077: r.ip = 0x1087; break;
        case 0x1079: setAl(bus.readByte(r.ds, 0x79a0)); r.ip = 0x107c; break;
        case 0x107c: arithmetic(static_cast<uint8_t>(r.ax), bus.readByte(r.ds, 0x79a1), 8, true); r.ip = 0x1080; break;
        case 0x1080: r.ip = (r.flags & Zero) ? 0x1082 : 0x1087; break;
        case 0x1082: farCall(bus, 0x02f6, 0x1087); break;
        case 0x1087: r.sp = r.bp; r.bp = pop(bus); ++r.ip; break;
        case 0x1088: r.es = pop(bus); ++r.ip; break;
        case 0x1089: r.ds = pop(bus); ++r.ip; break;
        case 0x108a: r.di = pop(bus); ++r.ip; break;
        case 0x108b: r.si = pop(bus); ++r.ip; break;
        case 0x108c: r.dx = pop(bus); ++r.ip; break;
        case 0x108d: r.cx = pop(bus); ++r.ip; break;
        case 0x108e: r.bx = pop(bus); ++r.ip; break;
        case 0x108f: r.ax = pop(bus); ++r.ip; break;
        case 0x1090: iret(bus); if (!state_.biosWrapper) state_.returned = true; break;
        default: throw std::domain_error("Timer IRQ reached unrecovered game instructions");
        }
    }

    TimerIrqSnapshot state_;
};

}
