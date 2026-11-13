#pragma once

#include "core/dos_time.hpp"
#include "core/timer_irq.hpp"

#include <bit>
#include <functional>
#include <stdexcept>

namespace lezac::core {

enum class ActorAnimationOutcome { Running, BehaviorDispatch, RuntimeError };
struct ActorAnimationSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment = 0;
    uint64_t dispatchedInstructions = 0, transferredBytes = 0;
    ActorAnimationOutcome outcome = ActorAnimationOutcome::Running;
    bool operator==(const ActorAnimationSnapshot&) const = default;
};

// Shared 6053..615A actor prologue, including stack check and mode-3 Move.
// BehaviorDispatch preserves the live stack at 615A; it is not a near return.
class ActorAnimationOperation {
public:
    using CopyBudget = std::function<uint16_t(uint16_t)>;
    ActorAnimationOperation(DosGetTimeRegisters registers, uint16_t game)
        : state_{registers,game} {
        if (registers.cs != game || registers.ds != static_cast<uint16_t>(game+0xaa2) || registers.ip != 0x6053)
            throw std::invalid_argument("Actor animation entry differs");
    }
    explicit ActorAnimationOperation(ActorAnimationSnapshot state) : state_(state) {}
    const ActorAnimationSnapshot& snapshot() const noexcept { return state_; }
    bool finished() const noexcept { return state_.outcome != ActorAnimationOutcome::Running; }
    bool atBehaviorDispatch() const noexcept { return state_.outcome == ActorAnimationOutcome::BehaviorDispatch; }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus, const CopyBudget& copies) {
        uint64_t used = 0;
        while (used < budget && !finished()) {
            instruction(bus,copies);
            ++used; ++state_.dispatchedInstructions;
            const auto& r = state_.registers;
            if (r.cs == state_.gameSegment && r.ip == 0x615a)
                state_.outcome = ActorAnimationOutcome::BehaviorDispatch;
            if (r.cs == library() && r.ip == 0xe2)
                state_.outcome = ActorAnimationOutcome::RuntimeError;
        }
        return used;
    }

private:
    ActorAnimationSnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.gameSegment+0x920); }
    bool flag(uint32_t bit) const { return (state_.registers.flags & bit) != 0; }
    static uint32_t resultFlags(uint16_t value, bool byte = false) {
        return (value == 0 ? 0x40u : 0u) | (value & (byte ? 0x80 : 0x8000) ? 0x80u : 0u) |
            (std::popcount(static_cast<uint8_t>(value)) % 2 == 0 ? 4u : 0u);
    }
    uint16_t arithmetic(uint16_t left, uint16_t right, bool subtract = false, bool byte = false) {
        const uint32_t mask = byte ? 255u : 65535u, sign = byte ? 128u : 32768u;
        const uint32_t wide = subtract ? uint32_t{left}-right : uint32_t{left}+right;
        const auto value = static_cast<uint16_t>(wide & mask);
        uint32_t flags = resultFlags(value,byte) | ((left ^ right ^ value) & 16u);
        if (subtract ? left < right : wide > mask) flags |= 1;
        if (subtract ? ((left ^ right) & (left ^ value) & sign) :
                       (~(left ^ right) & (left ^ value) & sign)) flags |= 0x800;
        state_.registers.flags = (state_.registers.flags & ~uint32_t{0x8d5}) | flags;
        return value;
    }
    void zeroAh() {
        state_.registers.ax &= 255u;
        state_.registers.flags = (state_.registers.flags & ~uint32_t{0x8d5}) | 0x44u;
    }
    uint16_t shift(uint16_t value, unsigned count) {
        auto& r = state_.registers;
        for (unsigned i = 0; i < count; ++i) {
            const auto carry = value >> 15;
            value = static_cast<uint16_t>(value << 1);
            r.flags = (r.flags & ~uint32_t{1}) | carry;
        }
        r.flags = (r.flags & ~uint32_t{0xc4}) | resultFlags(value);
        return value;
    }
    void instruction(const TimerIrqBus& bus, const CopyBudget& copies) {
        auto& r = state_.registers;
        const auto push = [&](uint16_t value) { r.sp = static_cast<uint16_t>(r.sp-2u); bus.writeWord(r.ss,r.sp,value); };
        const auto pop = [&] { const auto value = bus.readWord(r.ss,r.sp); r.sp = static_cast<uint16_t>(r.sp+2u); return value; };
        const auto local = [&](int offset) { return bus.readWord(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto storeLocal = [&](int offset, uint16_t value) { bus.writeWord(r.ss,static_cast<uint16_t>(r.bp+offset),value); };
        const auto les = [&](int offset) { r.di = local(offset); r.es = local(offset+2); };
        const auto al = [&](uint8_t value) { r.ax = static_cast<uint16_t>((r.ax & 0xff00u) | value); };
        const auto read = [&](unsigned offset) { return bus.readByte(r.es,static_cast<uint16_t>(r.di+offset)); };
        const auto write = [&](unsigned offset, uint8_t value) { bus.writeByte(r.es,static_cast<uint16_t>(r.di+offset),value); };
        const auto farCall = [&](uint16_t ip, uint16_t next) { push(r.cs); push(next); r.cs = library(); r.ip = ip; };
        const auto branch = [&](bool yes, uint16_t target, uint16_t next) { r.ip = yes ? target : next; };
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
            case 0x4f1:r.ax=0xca;r.ip=0x4f4;break;
            case 0x4f4:r.ip=0xe2;break;
            case 0x90e:r.bx=r.sp;r.ip=0x910;break;
            case 0x910:r.dx=r.ds;r.ip=0x912;break;
            case 0x912:r.si=bus.readWord(r.ss,static_cast<uint16_t>(r.bx+10u));r.ds=bus.readWord(r.ss,static_cast<uint16_t>(r.bx+12u));r.ip=0x916;break;
            case 0x916:r.di=bus.readWord(r.ss,static_cast<uint16_t>(r.bx+6u));r.es=bus.readWord(r.ss,static_cast<uint16_t>(r.bx+8u));r.ip=0x91a;break;
            case 0x91a:r.cx=bus.readWord(r.ss,static_cast<uint16_t>(r.bx+4u));r.ip=0x91e;break;
            case 0x91e:r.flags&=~uint32_t{0x400};r.ip=0x91f;break;
            case 0x91f: {
                const auto grant = r.cx ? copies(r.cx) : 0;
                if (grant > r.cx) throw std::domain_error("Actor animation copy grant exceeds CX");
                for (uint16_t i=0;i<grant;++i) {
                    const auto value=bus.readByte(r.ds,r.si);
                    bus.writeByte(r.es,r.di,value);
                    r.si=static_cast<uint16_t>(r.si+1u);r.di=static_cast<uint16_t>(r.di+1u);--r.cx;
                    ++state_.transferredBytes;
                }
                if (!r.cx) r.ip=0x921;
                break;
            }
            case 0x921:r.ds=r.dx;r.ip=0x923;break;
            case 0x923:r.ip=pop();r.cs=pop();r.sp=static_cast<uint16_t>(r.sp+10u);break;
            default:throw std::domain_error("Actor animation runtime left recovered code");
            }
            return;
        }
        if (r.cs != state_.gameSegment) throw std::domain_error("Actor animation left recovered code");
        switch (r.ip) {
        case 0x6053:push(r.bp);r.ip=0x6054;break;
        case 0x6054:r.bp=r.sp;r.ip=0x6056;break;
        case 0x6056:r.ax=0x3a;r.ip=0x6059;break;
        case 0x6059:farCall(0x4df,0x605e);break;
        case 0x605e:r.sp=arithmetic(r.sp,0x3a,true);r.ip=0x6061;break;
        case 0x6061:les(4);r.ip=0x6064;break;
        case 0x6064:al(read(1));r.ip=0x6068;break;
        case 0x6068:bus.writeByte(r.ss,static_cast<uint16_t>(r.bp-0x13u),static_cast<uint8_t>(r.ax));r.ip=0x606b;break;
        case 0x606b:les(4);r.ip=0x606e;break;
        case 0x606e:r.di=arithmetic(r.di,0x16);r.ip=0x6072;break;
        case 0x6072:storeLocal(-0x3a,r.di);r.ip=0x6075;break;
        case 0x6075:storeLocal(-0x38,r.es);r.ip=0x6078;break;
        case 0x6078:les(-0x3a);r.ip=0x607b;break;
        case 0x607b:arithmetic(read(5),0,true,true);r.ip=0x6080;break;
        case 0x6080:branch(!flag(1)&&!flag(0x40),0x6085,0x6082);break;
        case 0x6082:r.ip=0x615a;break;
        case 0x6085:les(-0x3a);r.ip=0x6088;break;
        case 0x6088: {
            const auto carry=r.flags&1u;
            write(3,static_cast<uint8_t>(arithmetic(read(3),1,false,true)));
            r.flags=(r.flags&~uint32_t{1})|carry;r.ip=0x608c;break;
        }
        case 0x608c:les(-0x3a);r.ip=0x608f;break;
        case 0x608f:al(read(3));r.ip=0x6093;break;
        case 0x6093:les(-0x3a);r.ip=0x6096;break;
        case 0x6096:arithmetic(static_cast<uint8_t>(r.ax),read(4),true,true);r.ip=0x609a;break;
        case 0x609a:branch(!flag(1)&&!flag(0x40),0x609f,0x609c);break;
        case 0x609c:r.ip=0x615a;break;
        case 0x609f:les(-0x3a);r.ip=0x60a2;break;
        case 0x60a2:write(3,0);r.ip=0x60a7;break;
        case 0x60a7:les(-0x3a);r.ip=0x60aa;break;
        case 0x60aa:al(read(6));r.ip=0x60ae;break;
        case 0x60ae:case 0x6131:r.ax=static_cast<uint16_t>(static_cast<int16_t>(std::bit_cast<int8_t>(static_cast<uint8_t>(r.ax))));r.ip=r.ip==0x60ae?0x60af:0x6132;break;
        case 0x60af:r.dx=r.ax;r.ip=0x60b1;break;
        case 0x60b1:les(-0x3a);r.ip=0x60b4;break;
        case 0x60b4:al(read(0));r.ip=0x60b7;break;
        case 0x60b7:zeroAh();r.ip=0x60b9;break;
        case 0x60b9:r.ax=arithmetic(r.ax,r.dx);r.ip=0x60bb;break;
        case 0x60bb:les(-0x3a);r.ip=0x60be;break;
        case 0x60be:write(0,static_cast<uint8_t>(r.ax));r.ip=0x60c1;break;
        case 0x60c1:les(-0x3a);r.ip=0x60c4;break;
        case 0x60c4:arithmetic(read(5),2,true,true);r.ip=0x60c9;break;
        case 0x60c9:branch(flag(0x40),0x610c,0x60cb);break;
        case 0x60cb:les(-0x3a);r.ip=0x60ce;break;
        case 0x60ce:al(read(0));r.ip=0x60d1;break;
        case 0x60d1:les(-0x3a);r.ip=0x60d4;break;
        case 0x60d4:arithmetic(static_cast<uint8_t>(r.ax),read(2),true,true);r.ip=0x60d8;break;
        case 0x60d8:branch(flag(1)||flag(0x40),0x610a,0x60da);break;
        case 0x60da:les(-0x3a);r.ip=0x60dd;break;
        case 0x60dd:al(read(1));r.ip=0x60e1;break;
        case 0x60e1:les(-0x3a);r.ip=0x60e4;break;
        case 0x60e4:write(0,static_cast<uint8_t>(r.ax));r.ip=0x60e7;break;
        case 0x60e7:les(-0x3a);r.ip=0x60ea;break;
        case 0x60ea:arithmetic(read(5),3,true,true);r.ip=0x60ef;break;
        case 0x60ef:branch(!flag(0x40),0x610a,0x60f1);break;
        case 0x60f1:les(4);r.ip=0x60f4;break;
        case 0x60f4:r.di=arithmetic(r.di,0x1d);r.ip=0x60f8;break;
        case 0x60f8:push(r.es);r.ip=0x60f9;break;
        case 0x60f9:push(r.di);r.ip=0x60fa;break;
        case 0x60fa:les(4);r.ip=0x60fd;break;
        case 0x60fd:r.di=arithmetic(r.di,0x16);r.ip=0x6101;break;
        case 0x6101:push(r.es);r.ip=0x6102;break;
        case 0x6102:push(r.di);r.ip=0x6103;break;
        case 0x6103:push(7);r.ip=0x6105;break;
        case 0x6105:farCall(0x90e,0x610a);break;
        case 0x610a:r.ip=0x613b;break;
        case 0x610c:les(-0x3a);r.ip=0x610f;break;
        case 0x610f:al(read(0));r.ip=0x6112;break;
        case 0x6112:les(-0x3a);r.ip=0x6115;break;
        case 0x6115:arithmetic(static_cast<uint8_t>(r.ax),read(2),true,true);r.ip=0x6119;break;
        case 0x6119:branch(!flag(1),0x612a,0x611b);break;
        case 0x611b:les(-0x3a);r.ip=0x611e;break;
        case 0x611e:al(read(0));r.ip=0x6121;break;
        case 0x6121:les(-0x3a);r.ip=0x6124;break;
        case 0x6124:arithmetic(static_cast<uint8_t>(r.ax),read(1),true,true);r.ip=0x6128;break;
        case 0x6128:branch(!flag(1)&&!flag(0x40),0x613b,0x612a);break;
        case 0x612a:les(-0x3a);r.ip=0x612d;break;
        case 0x612d:al(read(6));r.ip=0x6131;break;
        case 0x6132:r.ax=arithmetic(0,r.ax,true);r.ip=0x6134;break;
        case 0x6134:les(-0x3a);r.ip=0x6137;break;
        case 0x6137:write(6,static_cast<uint8_t>(r.ax));r.ip=0x613b;break;
        case 0x613b:les(-0x3a);r.ip=0x613e;break;
        case 0x613e:al(read(0));r.ip=0x6141;break;
        case 0x6141:zeroAh();r.ip=0x6143;break;
        case 0x6143:r.di=r.ax;r.ip=0x6145;break;
        case 0x6145:r.di=shift(r.di,2);r.ip=0x6148;break;
        case 0x6148:r.dx=bus.readWord(r.ds,static_cast<uint16_t>(r.di+0xc324u));r.ip=0x614c;break;
        case 0x614c:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp-0x13u)));r.ip=0x614f;break;
        case 0x614f:zeroAh();r.ip=0x6151;break;
        case 0x6151:r.di=r.ax;r.ip=0x6153;break;
        case 0x6153:r.di=shift(r.di,3);r.ip=0x6156;break;
        case 0x6156:bus.writeWord(r.ds,static_cast<uint16_t>(r.di+0xc224u),r.dx);r.ip=0x615a;break;
        default:throw std::domain_error("Actor animation reached an unrecovered instruction");
        }
    }
};

} // namespace lezac::core
