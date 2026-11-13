#pragma once

#include "core/dos_time.hpp"
#include "core/timer_irq.hpp"

#include <bit>
#include <stdexcept>

namespace lezac::core {

enum class PlayerStartOutcome { Running, Returned, RuntimeError };
struct PlayerStartSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment = 0;
    uint64_t dispatchedInstructions = 0;
    PlayerStartOutcome outcome = PlayerStartOutcome::Running;
    bool operator==(const PlayerStartSnapshot&) const = default;
};

// Complete original 056B..0625 and its CRT stack check. The caller owns memory
// and clock scheduling; this operation does not copy portal or actor storage.
class PlayerStartOperation {
public:
    PlayerStartOperation(DosGetTimeRegisters registers, uint16_t game)
        : state_{registers, game} {
        if (registers.cs != game || registers.ds != static_cast<uint16_t>(game + 0xaa2) || registers.ip != 0x56b)
            throw std::invalid_argument("Player start entry differs");
    }
    explicit PlayerStartOperation(PlayerStartSnapshot state) : state_(state) {}
    const PlayerStartSnapshot& snapshot() const noexcept { return state_; }
    bool finished() const noexcept { return state_.outcome != PlayerStartOutcome::Running; }
    bool returned() const noexcept { return state_.outcome == PlayerStartOutcome::Returned; }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus) {
        uint64_t used = 0;
        while (used < budget && !finished()) {
            instruction(bus);
            ++used; ++state_.dispatchedInstructions;
            if (state_.registers.cs == library() && state_.registers.ip == 0xe2)
                state_.outcome = PlayerStartOutcome::RuntimeError;
        }
        return used;
    }
private:
    PlayerStartSnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.gameSegment + 0x920); }
    bool flag(uint32_t bit) const { return (state_.registers.flags & bit) != 0; }
    static uint32_t resultFlags(uint16_t value, unsigned bits) {
        return (value == 0 ? 0x40u : 0u) | (value & (1u << (bits - 1)) ? 0x80u : 0u) |
            (std::popcount(static_cast<uint8_t>(value)) % 2 == 0 ? 4u : 0u);
    }
    uint16_t arithmetic(uint16_t left, uint16_t right, bool subtract = false, unsigned bits = 16) {
        const uint32_t mask = bits == 8 ? 255u : 65535u, sign = 1u << (bits - 1);
        const uint32_t wide = subtract ? uint32_t{left} - right : uint32_t{left} + right;
        const auto value = static_cast<uint16_t>(wide & mask);
        uint32_t flags = resultFlags(value, bits) | ((left ^ right ^ value) & 16u);
        if (subtract ? left < right : wide > mask) flags |= 1;
        if (subtract ? ((left ^ right) & (left ^ value) & sign) : (~(left ^ right) & (left ^ value) & sign)) flags |= 0x800;
        state_.registers.flags = (state_.registers.flags & ~uint32_t{0x8d5}) | flags;
        return value;
    }
    uint16_t logic(uint16_t value) {
        state_.registers.flags = (state_.registers.flags & ~uint32_t{0x8d5}) | resultFlags(value, 8);
        return value;
    }
    uint16_t shift(uint16_t value, unsigned count) {
        for (unsigned i = 0; i < count; ++i) {
            const auto carry = value >> 15;
            value = static_cast<uint16_t>(value << 1);
            state_.registers.flags = (state_.registers.flags & ~uint32_t{1}) | carry;
        }
        state_.registers.flags = (state_.registers.flags & ~uint32_t{0xc4}) | resultFlags(value, 16);
        return value;
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        const auto push = [&](uint16_t value) { r.sp = static_cast<uint16_t>(r.sp - 2u); bus.writeWord(r.ss, r.sp, value); };
        const auto pop = [&] { const auto value = bus.readWord(r.ss, r.sp); r.sp = static_cast<uint16_t>(r.sp + 2u); return value; };
        const auto at = [&](int delta) { return static_cast<uint16_t>(r.bp + delta); };
        const auto local = [&](int delta) { return bus.readWord(r.ss, at(delta)); };
        const auto store = [&](int delta, uint16_t value) { bus.writeWord(r.ss, at(delta), value); };
        const auto branch = [&](bool yes, uint16_t target, uint16_t next) { r.ip = yes ? target : next; };
        const auto les = [&](int delta) { r.di = local(delta); r.es = local(delta + 2); };
        const auto al = [&](uint16_t value) { r.ax = static_cast<uint16_t>((r.ax & 0xff00u) | (value & 255u)); };
        const auto zeroAh = [&] { logic(0); r.ax &= 255u; };
        if (r.cs == library()) {
            switch (r.ip) {
            case 0x4df:r.ax=arithmetic(r.ax,0x200);r.ip=0x4e2;break;
            case 0x4e2:branch(flag(1),0x4f1,0x4e4);break;
            case 0x4e4:r.ax=arithmetic(r.ax,r.sp,true);r.ip=0x4e6;break;
            case 0x4e6:branch(!flag(1),0x4f1,0x4e8);break;
            case 0x4e8:r.ax=arithmetic(0,r.ax,true);r.ip=0x4ea;break;
            case 0x4ea:arithmetic(r.ax,bus.readWord(r.ds,0x1afa),true);r.ip=0x4ee;break;
            case 0x4ee:branch(flag(1),0x4f1,0x4f0);break;
            case 0x4f0:r.ip=pop();r.cs=pop();break;
            case 0x4f1:r.ax=202;r.ip=0x4f4;break;
            case 0x4f4:r.ip=0xe2;break;
            default:throw std::domain_error("Player start CRT left recovered code");
            }
            return;
        }
        if (r.cs != state_.gameSegment) throw std::domain_error("Player start left recovered code");
        switch (r.ip) {
        case 0x56b:push(r.bp);r.ip=0x56c;break;
        case 0x56c:r.bp=r.sp;r.ip=0x56e;break;
        case 0x56e:r.ax=12;r.ip=0x571;break;
        case 0x571:push(r.cs);push(0x576);r.cs=library();r.ip=0x4df;break;
        case 0x576:r.sp=arithmetic(r.sp,12,true);r.ip=0x579;break;
        case 0x579:store(-2,1);r.ip=0x57e;break;
        case 0x57e:bus.writeByte(r.ss,at(-3),0);r.ip=0x582;break;
        case 0x582:les(6);r.ip=0x585;break;
        case 0x585:bus.writeByte(r.es,static_cast<uint16_t>(r.di+2u),0);r.ip=0x58a;break;
        case 0x58a:al(bus.readByte(r.ds,0x79a5));r.ip=0x58d;break;
        case 0x58d:zeroAh();r.ip=0x58f;break;
        case 0x58f:arithmetic(r.ax,local(-2),true);r.ip=0x592;break;
        case 0x592:branch(flag(0x80)!=flag(0x800),0x5f2,0x594);break;
        case 0x594:arithmetic(bus.readByte(r.ss,at(-3)),0,true,8);r.ip=0x598;break;
        case 0x598:branch(!flag(0x40),0x5f2,0x59a);break;
        case 0x59a: {
            const int32_t value = int32_t{std::bit_cast<int16_t>(local(-2))} * 7;
            r.di=static_cast<uint16_t>(value);
            r.flags=(r.flags&~uint32_t{0x801})|(value < -32768 || value > 32767 ? 0x801u : 0u);
            r.ip=0x59e;break;
        }
        case 0x59e:r.di=arithmetic(r.di,0x7717);r.ip=0x5a2;break;
        case 0x5a2:store(-8,r.di);r.ip=0x5a5;break;
        case 0x5a5:store(-6,r.ds);r.ip=0x5a8;break;
        case 0x5a8:les(-8);r.ip=0x5ab;break;
        case 0x5ab:al(bus.readByte(r.es,static_cast<uint16_t>(r.di+6u)));r.ip=0x5af;break;
        case 0x5af:al(logic(static_cast<uint8_t>(r.ax)&bus.readByte(r.ss,at(4))));r.ip=0x5b2;break;
        case 0x5b2:logic(static_cast<uint8_t>(r.ax));r.ip=0x5b4;break;
        case 0x5b4:branch(flag(1)||flag(0x40),0x5ed,0x5b6);break;
        case 0x5b6:les(6);r.ip=0x5b9;break;
        case 0x5b9:al(bus.readByte(r.es,static_cast<uint16_t>(r.di+1u)));r.ip=0x5bd;break;
        case 0x5bd:zeroAh();r.ip=0x5bf;break;
        case 0x5bf:r.di=r.ax;r.ip=0x5c1;break;
        case 0x5c1:r.di=shift(r.di,3);r.ip=0x5c4;break;
        case 0x5c4:r.di=arithmetic(r.di,0xc21e);r.ip=0x5c8;break;
        case 0x5c8:store(-12,r.di);r.ip=0x5cb;break;
        case 0x5cb:store(-10,r.ds);r.ip=0x5ce;break;
        case 0x5ce:les(-8);r.ip=0x5d1;break;
        case 0x5d1:r.ax=bus.readWord(r.es,static_cast<uint16_t>(r.di+2u));r.ip=0x5d5;break;
        case 0x5d5:les(-12);r.ip=0x5d8;break;
        case 0x5d8:bus.writeWord(r.es,r.di,r.ax);r.ip=0x5db;break;
        case 0x5db:les(-8);r.ip=0x5de;break;
        case 0x5de:r.ax=bus.readWord(r.es,static_cast<uint16_t>(r.di+4u));r.ip=0x5e2;break;
        case 0x5e2:les(-12);r.ip=0x5e5;break;
        case 0x5e5:bus.writeWord(r.es,static_cast<uint16_t>(r.di+2u),r.ax);r.ip=0x5e9;break;
        case 0x5e9:bus.writeByte(r.ss,at(-3),1);r.ip=0x5ed;break;
        case 0x5ed: {
            const auto carry=r.flags&1u;store(-2,arithmetic(local(-2),1));r.flags=(r.flags&~uint32_t{1})|carry;r.ip=0x5f0;break;
        }
        case 0x5f0:r.ip=0x58a;break;
        case 0x5f2:arithmetic(bus.readByte(r.ss,at(-3)),0,true,8);r.ip=0x5f6;break;
        case 0x5f6:branch(!flag(0x40),0x621,0x5f8);break;
        case 0x5f8:les(6);r.ip=0x5fb;break;
        case 0x5fb:al(bus.readByte(r.es,static_cast<uint16_t>(r.di+1u)));r.ip=0x5ff;break;
        case 0x5ff:zeroAh();r.ip=0x601;break;
        case 0x601:r.di=r.ax;r.ip=0x603;break;
        case 0x603:r.di=shift(r.di,3);r.ip=0x606;break;
        case 0x606:r.di=arithmetic(r.di,0xc21e);r.ip=0x60a;break;
        case 0x60a:store(-8,r.di);r.ip=0x60d;break;
        case 0x60d:store(-6,r.ds);r.ip=0x610;break;
        case 0x610:les(-8);r.ip=0x613;break;
        case 0x613:bus.writeWord(r.es,r.di,17);r.ip=0x618;break;
        case 0x618:les(-8);r.ip=0x61b;break;
        case 0x61b:bus.writeWord(r.es,static_cast<uint16_t>(r.di+2u),17);r.ip=0x621;break;
        case 0x621:r.sp=r.bp;r.bp=pop();r.ip=0x622;break;
        case 0x622:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+6u);state_.outcome=PlayerStartOutcome::Returned;break;
        default:throw std::domain_error("Player start reached an unrecovered instruction");
        }
    }
};

}
