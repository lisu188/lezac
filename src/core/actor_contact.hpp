#pragma once

#include "core/actor_precontact.hpp"

namespace lezac::core {

enum class ActorContactOutcome { Running, TileBehavior, MotionIntegration, RuntimeError };
struct ActorContactSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment=0;
    uint32_t idToggleMask=0;
    std::optional<ActorPrecontactSnapshot> interrupt=std::nullopt;
    uint64_t dispatchedInstructions=0,timerInstructions=0,timerDeliveries=0;
    ActorContactOutcome outcome=ActorContactOutcome::Running;
    bool operator==(const ActorContactSnapshot&) const = default;
};

// 654E..65A2: tile cache or complete boss-head scanner and its real callees.
// 73E5 is the live-frame motion-integration handoff, not a completed actor.
class ActorContactOperation {
public:
    ActorContactOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        : state_{r,game,idToggle} {
        if (r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2) || r.ip!=0x654e)
            throw std::invalid_argument("Actor contact entry differs");
        validate();
    }
    explicit ActorContactOperation(ActorContactSnapshot state) : state_(state) { validate(); }
    const ActorContactSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const {
        return state_.interrupt ? ActorPrecontactOperation(*state_.interrupt).registers() : state_.registers;
    }
    bool finished() const noexcept { return state_.outcome!=ActorContactOutcome::Running && !state_.interrupt; }
    bool interruptInProgress() const noexcept { return state_.interrupt.has_value(); }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished() || state_.interrupt || !(state_.registers.flags&0x200u))
            throw std::logic_error("Actor contact IRQ is not eligible");
        ActorPrecontactOperation irq(ActorPrecontactSnapshot{state_.registers,state_.gameSegment,state_.idToggleMask});
        irq.deliverTimerInterrupt(bus);state_.interrupt=irq.snapshot();++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (state_.interrupt) {
                // Borrow only the established IRQ machinery, never its game code.
                ActorPrecontactOperation irq(*state_.interrupt);
                if (irq.advance(1,bus)!=1) throw std::domain_error("Actor contact IRQ did not dispatch");
                ++state_.timerInstructions;
                if (irq.interruptInProgress()) state_.interrupt=irq.snapshot();
                else { state_.registers=irq.registers();state_.interrupt.reset(); }
            } else {
                instruction(bus);
                const auto& r=state_.registers;
                if (r.cs==state_.gameSegment && r.ip==0x65a2) state_.outcome=ActorContactOutcome::TileBehavior;
                if (r.cs==state_.gameSegment && r.ip==0x73e5) state_.outcome=ActorContactOutcome::MotionIntegration;
                if (r.cs==library() && r.ip==0xe2) state_.outcome=ActorContactOutcome::RuntimeError;
            }
            ++used;++state_.dispatchedInstructions;
        }
        return used;
    }

private:
    ActorContactSnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.gameSegment+0x920); }
    void validate() const {
        if (state_.idToggleMask!=0 && state_.idToggleMask!=0x200000)
            throw std::invalid_argument("Actor contact ID-toggle profile differs");
        if (state_.registers.ds!=static_cast<uint16_t>(state_.gameSegment+0xaa2) ||
            (state_.registers.cs!=state_.gameSegment && state_.registers.cs!=library()) ||
            (state_.interrupt && (state_.outcome!=ActorContactOutcome::Running || !state_.interrupt->timer ||
                state_.interrupt->outcome!=ActorPrecontactOutcome::Running ||
                state_.interrupt->registers!=state_.registers ||
                state_.interrupt->gameSegment!=state_.gameSegment || state_.interrupt->idToggleMask!=state_.idToggleMask ||
                state_.interrupt->timer->gameSegment!=state_.gameSegment ||
                state_.interrupt->timer->dataSegment!=static_cast<uint16_t>(state_.gameSegment+0xaa2) ||
                state_.interrupt->timer->idToggleMask!=state_.idToggleMask ||
                !state_.interrupt->timer->biosWrapper || state_.interrupt->timer->returned)))
            throw std::invalid_argument("Actor contact register/IRQ ownership differs");
    }
    bool flag(uint32_t bit) const { return (state_.registers.flags&bit)!=0; }
    static uint32_t valueFlags(uint16_t value,bool byte=false) {
        return (value==0 ? 0x40u : 0u)|(value&(byte ? 128u : 32768u) ? 0x80u : 0u)|
            (std::popcount(static_cast<uint8_t>(value))%2==0 ? 4u : 0u);
    }
    uint16_t logic(uint16_t value) {
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|valueFlags(value);return value;
    }
    uint16_t arithmetic(uint16_t a,uint16_t b,bool subtract=false,bool byte=false,bool carry=false) {
        const uint32_t mask=byte ? 255u : 65535u,sign=byte ? 128u : 32768u,extra=carry && flag(1) ? 1u : 0u;
        const uint32_t wide=subtract ? uint32_t{a}-b-extra : uint32_t{a}+b+extra;
        const auto value=static_cast<uint16_t>(wide&mask);
        uint32_t f=valueFlags(value,byte)|((a^b^value)&16u);
        if (subtract ? uint32_t{a}<uint32_t{b}+extra : wide>mask) f|=1;
        if (subtract ? ((a^b)&(a^value)&sign) : (~(a^b)&(a^value)&sign)) f|=0x800;
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|f;return value;
    }
    uint16_t increment(uint16_t value,bool subtract=false,bool byte=false) {
        const auto carry=state_.registers.flags&1u;value=arithmetic(value,1,subtract,byte);
        state_.registers.flags=(state_.registers.flags&~uint32_t{1})|carry;return value;
    }
    uint16_t shift(uint16_t value,unsigned count,bool right=false) {
        for (unsigned i=0;i<count;++i) {
            const auto old=value;const auto carry=right ? value&1u : value>>15;
            value=static_cast<uint16_t>(right ? value>>1 : value<<1);
            state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|valueFlags(value)|16u|carry|
                (right ? (old&0x8000u ? 0x800u : 0u) : ((old^value)&0x8000u ? 0x800u : 0u));
        }
        return value;
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r=state_.registers;
        const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value); };
        const auto pop=[&] { const auto value=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return value; };
        const auto local=[&](int offset) { return bus.readWord(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto lb=[&](int offset) { return bus.readByte(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto store=[&](int offset,uint16_t value) { bus.writeWord(r.ss,static_cast<uint16_t>(r.bp+offset),value); };
        const auto sb=[&](int offset,uint8_t value) { bus.writeByte(r.ss,static_cast<uint16_t>(r.bp+offset),value); };
        const auto les=[&](int offset) { r.di=local(offset);r.es=local(offset+2); };
        const auto indirectLes=[&] { const auto at=static_cast<uint16_t>(r.di+4u);r.di=bus.readWord(r.ss,at);r.es=bus.readWord(r.ss,static_cast<uint16_t>(at+2u)); };
        const auto parent=[&](int offset) { return bus.readWord(r.ss,static_cast<uint16_t>(r.di+offset)); };
        const auto parentByte=[&](int offset) { return bus.readByte(r.ss,static_cast<uint16_t>(r.di+offset)); };
        const auto parentStore=[&](int offset,uint16_t value) { bus.writeWord(r.ss,static_cast<uint16_t>(r.di+offset),value); };
        const auto parentByteStore=[&](int offset,uint8_t value) { bus.writeByte(r.ss,static_cast<uint16_t>(r.di+offset),value); };
        const auto read=[&](unsigned offset) { return bus.readWord(r.es,static_cast<uint16_t>(r.di+offset)); };
        const auto byte=[&](unsigned offset) { return bus.readByte(r.es,static_cast<uint16_t>(r.di+offset)); };
        const auto wb=[&](unsigned offset,uint8_t value) { bus.writeByte(r.es,static_cast<uint16_t>(r.di+offset),value); };
        const auto data=[&](uint16_t offset) { return bus.readByte(r.ds,offset); };
        const auto dw=[&](uint16_t offset) { return bus.readWord(r.ds,offset); };
        const auto al=[&](uint8_t value) { r.ax=static_cast<uint16_t>((r.ax&0xff00u)|value); };
        const auto dl=[&](uint8_t value) { r.dx=static_cast<uint16_t>((r.dx&0xff00u)|value); };
        const auto zeroAh=[&] { r.ax&=255u;r.flags=(r.flags&~uint32_t{0x8d5})|0x44u; };
        const auto cbw=[&] { r.ax=static_cast<uint16_t>((r.ax&255u)|((r.ax&128u) ? 0xff00u : 0u)); };
        const auto cwd=[&] { r.dx=(r.ax&0x8000u) ? 0xffff : 0; };
        const auto branch=[&](bool condition,uint16_t yes,uint16_t no) { r.ip=condition ? yes : no; };
        const auto less=[&] { return flag(0x80)!=flag(0x800); };
        const auto nearCall=[&](uint16_t ip,uint16_t next) { push(next);r.ip=ip; };
        const auto farCall=[&](uint16_t ip,uint16_t next) { push(r.cs);push(next);r.cs=library();r.ip=ip; };
        const auto multiply=[&](uint16_t value) {
            const uint32_t product=uint32_t{r.ax}*value;r.ax=static_cast<uint16_t>(product);r.dx=static_cast<uint16_t>(product>>16);
            r.flags=(r.flags&~uint32_t{0x841})|(r.dx ? 0x801u : 0u)|(r.ax==0 ? 0x40u : 0u);
        };
        const auto signedMultiply=[&](uint16_t value,int16_t factor) {
            const int32_t product=int32_t{std::bit_cast<int16_t>(value)}*factor;
            r.di=static_cast<uint16_t>(product);
            r.flags=(r.flags&~uint32_t{0x801})|((product < -32768 || product > 32767) ? 0x801u : 0u);
        };
        const auto divide=[&](uint16_t divisor) {
            const uint32_t value=(uint32_t{r.dx}<<16)|r.ax;
            if (!divisor || value/divisor>65535) throw std::domain_error("Actor contact DIV overflow");
            r.ax=static_cast<uint16_t>(value/divisor);r.dx=static_cast<uint16_t>(value%divisor);
        };
        const auto signedDivide=[&](uint16_t divisor) {
            const int64_t value=std::bit_cast<int32_t>((uint32_t{r.dx}<<16)|r.ax);
            const auto factor=std::bit_cast<int16_t>(divisor);
            if (!factor || value/factor < -32768 || value/factor > 32767) throw std::domain_error("Actor contact IDIV overflow");
            r.ax=static_cast<uint16_t>(value/factor);r.dx=static_cast<uint16_t>(value%factor);
        };
        if (r.cs==library() || (r.cs==state_.gameSegment && r.ip>=0x5a75 && r.ip<0x5afd)) {
            ActorPrecontactOperation callee(ActorPrecontactSnapshot{r,state_.gameSegment,state_.idToggleMask});
            callee.advance(1,bus);r=callee.registers();return;
        }
        if (r.cs!=state_.gameSegment) throw std::domain_error("Actor contact left recovered code");
        switch (r.ip) {
        case 0x654e:arithmetic(lb(-49),6,true,true);r.ip=0x6552;break;
        case 0x6552:branch(!flag(0x40),0x655b,0x6554);break;
        case 0x6554:push(r.bp);r.ip=0x6555;break;
        case 0x6555:nearCall(0x5cb0,0x6558);break;
        case 0x6558:r.ip=0x73e5;break;
        case 0x655b:r.di=dw(0xc1e0);r.es=dw(0xc1e2);r.ip=0x655f;break;
        case 0x655f:r.ax=local(-44);r.ip=0x6562;break;
        case 0x6562:r.ax=arithmetic(r.ax,4);r.ip=0x6565;break;
        case 0x6565:case 0x6567:case 0x6569:r.ax=shift(r.ax,1,true);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x656b:r.cx=r.ax;r.ip=0x656d;break;
        case 0x656d:r.ax=local(-46);r.ip=0x6570;break;
        case 0x6570:case 0x6572:case 0x6574:r.ax=shift(r.ax,1,true);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x6576:r.ax=increment(r.ax,true);r.ip=0x6577;break;
        case 0x6577:r.cx=increment(r.cx,true);r.ip=0x6578;break;
        case 0x6578:r.bx=dw(0xc204);r.ip=0x657c;break;
        case 0x657c:multiply(r.bx);r.ip=0x657e;break;
        case 0x657e:r.ax=arithmetic(r.ax,r.cx);r.ip=0x6580;break;
        case 0x6580:r.di=arithmetic(r.di,r.ax);r.ip=0x6582;break;
        case 0x6582:store(-42,r.di);r.ip=0x6585;break;
        case 0x6585:r.bx=logic(0);r.ip=0x6587;break;
        case 0x6587:r.cx=4;r.ip=0x658a;break;
        case 0x658a:push(r.cx);r.ip=0x658b;break;
        case 0x658b:push(r.di);r.ip=0x658c;break;
        case 0x658c:r.cx=4;r.ip=0x658f;break;
        case 0x658f:al(byte(0));r.ip=0x6592;break;
        case 0x6592:bus.writeByte(r.ds,static_cast<uint16_t>(r.bx+0x2048u),static_cast<uint8_t>(r.ax));r.ip=0x6596;break;
        case 0x6596:r.bx=increment(r.bx);r.ip=0x6597;break;
        case 0x6597:r.di=increment(r.di);r.ip=0x6598;break;
        case 0x6598:r.cx=static_cast<uint16_t>(r.cx-1u);branch(r.cx!=0,0x658f,0x659a);break;
        case 0x659a:r.di=pop();r.ip=0x659b;break;
        case 0x659b:r.cx=pop();r.ip=0x659c;break;
        case 0x659c:r.di=arithmetic(r.di,dw(0xc204));r.ip=0x65a0;break;
        case 0x65a0:r.cx=static_cast<uint16_t>(r.cx-1u);branch(r.cx!=0,0x658a,0x65a2);break;

        case 0x5cb0:push(r.bp);r.ip=0x5cb1;break;
        case 0x5cb1:r.bp=r.sp;r.ip=0x5cb3;break;
        case 0x5cb3:r.ax=16;r.ip=0x5cb6;break;
        case 0x5cb6:farCall(0x4df,0x5cbb);break;
        case 0x5cbb:r.sp=arithmetic(r.sp,16,true);r.ip=0x5cbe;break;
        case 0x5cbe:r.di=local(4);r.ip=0x5cc1;break;
        case 0x5cc1:indirectLes();r.ip=0x5cc5;break;
        case 0x5cc5:store(-16,r.di);r.ip=0x5cc8;break;
        case 0x5cc8:store(-14,r.es);r.ip=0x5ccb;break;
        case 0x5ccb:les(-16);r.ip=0x5cce;break;
        case 0x5cce:r.ax=read(14);r.ip=0x5cd2;break;
        case 0x5cd2:r.ax=logic(r.ax&255u);r.ip=0x5cd5;break;
        case 0x5cd5:sb(-1,static_cast<uint8_t>(r.ax));r.ip=0x5cd8;break;
        case 0x5cd8:les(-16);r.ip=0x5cdb;break;
        case 0x5cdb:r.ax=read(14);r.ip=0x5cdf;break;
        case 0x5cdf:r.ax=shift(r.ax,8,true);r.ip=0x5ce2;break;
        case 0x5ce2:sb(-2,static_cast<uint8_t>(r.ax));r.ip=0x5ce5;break;
        case 0x5ce5:r.di=local(4);r.ip=0x5ce8;break;
        case 0x5ce8:r.ax=parent(-46);r.ip=0x5cec;break;
        case 0x5cec:r.ax=shift(r.ax,3,true);r.ip=0x5cef;break;
        case 0x5cef:multiply(dw(0xc204));r.ip=0x5cf3;break;
        case 0x5cf3:r.dx=r.ax;r.ip=0x5cf5;break;
        case 0x5cf5:r.di=local(4);r.ip=0x5cf8;break;
        case 0x5cf8:r.ax=parent(-44);r.ip=0x5cfc;break;
        case 0x5cfc:r.ax=shift(r.ax,3,true);r.ip=0x5cff;break;
        case 0x5cff:r.ax=arithmetic(r.ax,r.dx);r.ip=0x5d01;break;
        case 0x5d01:r.di=local(4);r.ip=0x5d04;break;
        case 0x5d04:parentStore(-42,r.ax);r.ip=0x5d08;break;
        case 0x5d08:r.di=local(4);r.ip=0x5d0b;break;
        case 0x5d0b:r.ax=parent(-42);r.ip=0x5d0f;break;
        case 0x5d0f:r.ax=arithmetic(r.ax,dw(0xc204),true);r.ip=0x5d13;break;
        case 0x5d13:store(-6,r.ax);r.ip=0x5d16;break;
        case 0x5d16:store(-10,1);r.ip=0x5d1b;break;
        case 0x5d1b:r.di=local(4);r.ip=0x5d1e;break;
        case 0x5d1e:parentByteStore(-34,0);r.ip=0x5d23;break;
        case 0x5d23:al(lb(-1));r.ip=0x5d26;break;
        case 0x5d26:zeroAh();r.ip=0x5d28;break;
        case 0x5d28:arithmetic(r.ax,local(-10),true);r.ip=0x5d2b;break;
        case 0x5d2b:branch(flag(1),0x5d5a,0x5d2d);break;
        case 0x5d2d:r.ax=local(-6);r.ip=0x5d30;break;
        case 0x5d30:r.di=dw(0xc1e0);r.es=dw(0xc1e2);r.ip=0x5d34;break;
        case 0x5d34:r.di=arithmetic(r.di,r.ax);r.ip=0x5d36;break;
        case 0x5d36:al(byte(0));r.ip=0x5d39;break;
        case 0x5d39:sb(-3,static_cast<uint8_t>(r.ax));r.ip=0x5d3c;break;
        case 0x5d3c:arithmetic(lb(-3),1,true,true);r.ip=0x5d40;break;
        case 0x5d40:branch(flag(1),0x5d52,0x5d42);break;
        case 0x5d42:arithmetic(lb(-3),76,true,true);r.ip=0x5d46;break;
        case 0x5d46:branch(!flag(1)&&!flag(0x40),0x5d52,0x5d48);break;
        case 0x5d48:r.di=local(4);r.ip=0x5d4b;break;
        case 0x5d4b:parentByteStore(-34,1);r.ip=0x5d50;break;
        case 0x5d50:r.ip=0x5d5a;break;
        case 0x5d52:store(-6,increment(local(-6)));r.ip=0x5d55;break;
        case 0x5d55:store(-10,increment(local(-10)));r.ip=0x5d58;break;
        case 0x5d58:r.ip=0x5d23;break;
        case 0x5d5a:al(lb(-2));r.ip=0x5d5d;break;
        case 0x5d5d:zeroAh();r.ip=0x5d5f;break;
        case 0x5d5f:multiply(dw(0xc204));r.ip=0x5d63;break;
        case 0x5d63:r.di=local(4);r.ip=0x5d66;break;
        case 0x5d66:r.ax=arithmetic(r.ax,parent(-42));r.ip=0x5d6a;break;
        case 0x5d6a:store(-6,r.ax);r.ip=0x5d6d;break;
        case 0x5d6d:store(-10,1);r.ip=0x5d72;break;
        case 0x5d72:r.di=local(4);r.ip=0x5d75;break;
        case 0x5d75:parentByteStore(-33,0);r.ip=0x5d7a;break;
        case 0x5d7a:al(lb(-1));r.ip=0x5d7d;break;
        case 0x5d7d:zeroAh();r.ip=0x5d7f;break;
        case 0x5d7f:arithmetic(r.ax,local(-10),true);r.ip=0x5d82;break;
        case 0x5d82:branch(flag(1),0x5db1,0x5d84);break;
        case 0x5d84:r.ax=local(-6);r.ip=0x5d87;break;
        case 0x5d87:r.di=dw(0xc1e0);r.es=dw(0xc1e2);r.ip=0x5d8b;break;
        case 0x5d8b:r.di=arithmetic(r.di,r.ax);r.ip=0x5d8d;break;
        case 0x5d8d:al(byte(0));r.ip=0x5d90;break;
        case 0x5d90:sb(-3,static_cast<uint8_t>(r.ax));r.ip=0x5d93;break;
        case 0x5d93:arithmetic(lb(-3),1,true,true);r.ip=0x5d97;break;
        case 0x5d97:branch(flag(1),0x5da9,0x5d99);break;
        case 0x5d99:arithmetic(lb(-3),82,true,true);r.ip=0x5d9d;break;
        case 0x5d9d:branch(!flag(1)&&!flag(0x40),0x5da9,0x5d9f);break;
        case 0x5d9f:r.di=local(4);r.ip=0x5da2;break;
        case 0x5da2:parentByteStore(-33,1);r.ip=0x5da7;break;
        case 0x5da7:r.ip=0x5db1;break;
        case 0x5da9:store(-6,increment(local(-6)));r.ip=0x5dac;break;
        case 0x5dac:store(-10,increment(local(-10)));r.ip=0x5daf;break;
        case 0x5daf:r.ip=0x5d7a;break;
        case 0x5db1:r.di=local(4);r.ip=0x5db4;break;
        case 0x5db4:r.ax=parent(-42);r.ip=0x5db8;break;
        case 0x5db8:r.ax=increment(r.ax,true);r.ip=0x5db9;break;
        case 0x5db9:store(-6,r.ax);r.ip=0x5dbc;break;
        case 0x5dbc:store(-10,1);r.ip=0x5dc1;break;
        case 0x5dc1:r.di=local(4);r.ip=0x5dc4;break;
        case 0x5dc4:parentByteStore(-35,0);r.ip=0x5dc9;break;
        case 0x5dc9:al(lb(-2));r.ip=0x5dcc;break;
        case 0x5dcc:zeroAh();r.ip=0x5dce;break;
        case 0x5dce:arithmetic(r.ax,local(-10),true);r.ip=0x5dd1;break;
        case 0x5dd1:branch(flag(1),0x5e03,0x5dd3);break;
        case 0x5dd3:r.ax=local(-6);r.ip=0x5dd6;break;
        case 0x5dd6:r.di=dw(0xc1e0);r.es=dw(0xc1e2);r.ip=0x5dda;break;
        case 0x5dda:r.di=arithmetic(r.di,r.ax);r.ip=0x5ddc;break;
        case 0x5ddc:al(byte(0));r.ip=0x5ddf;break;
        case 0x5ddf:sb(-3,static_cast<uint8_t>(r.ax));r.ip=0x5de2;break;
        case 0x5de2:arithmetic(lb(-3),1,true,true);r.ip=0x5de6;break;
        case 0x5de6:branch(flag(1),0x5df8,0x5de8);break;
        case 0x5de8:arithmetic(lb(-3),76,true,true);r.ip=0x5dec;break;
        case 0x5dec:branch(!flag(1)&&!flag(0x40),0x5df8,0x5dee);break;
        case 0x5dee:r.di=local(4);r.ip=0x5df1;break;
        case 0x5df1:parentByteStore(-35,1);r.ip=0x5df6;break;
        case 0x5df6:r.ip=0x5e03;break;
        case 0x5df8:r.ax=dw(0xc204);r.ip=0x5dfb;break;
        case 0x5dfb:store(-6,arithmetic(local(-6),r.ax));r.ip=0x5dfe;break;
        case 0x5dfe:store(-10,increment(local(-10)));r.ip=0x5e01;break;
        case 0x5e01:r.ip=0x5dc9;break;
        case 0x5e03:al(lb(-1));r.ip=0x5e06;break;
        case 0x5e06:zeroAh();r.ip=0x5e08;break;
        case 0x5e08:r.di=local(4);r.ip=0x5e0b;break;
        case 0x5e0b:r.ax=arithmetic(r.ax,parent(-42));r.ip=0x5e0f;break;
        case 0x5e0f:store(-6,r.ax);r.ip=0x5e12;break;
        case 0x5e12:store(-10,1);r.ip=0x5e17;break;
        case 0x5e17:r.di=local(4);r.ip=0x5e1a;break;
        case 0x5e1a:parentByteStore(-36,0);r.ip=0x5e1f;break;
        case 0x5e1f:al(lb(-2));r.ip=0x5e22;break;
        case 0x5e22:zeroAh();r.ip=0x5e24;break;
        case 0x5e24:arithmetic(r.ax,local(-10),true);r.ip=0x5e27;break;
        case 0x5e27:branch(flag(1),0x5e59,0x5e29);break;
        case 0x5e29:r.ax=local(-6);r.ip=0x5e2c;break;
        case 0x5e2c:r.di=dw(0xc1e0);r.es=dw(0xc1e2);r.ip=0x5e30;break;
        case 0x5e30:r.di=arithmetic(r.di,r.ax);r.ip=0x5e32;break;
        case 0x5e32:al(byte(0));r.ip=0x5e35;break;
        case 0x5e35:sb(-3,static_cast<uint8_t>(r.ax));r.ip=0x5e38;break;
        case 0x5e38:arithmetic(lb(-3),1,true,true);r.ip=0x5e3c;break;
        case 0x5e3c:branch(flag(1),0x5e4e,0x5e3e);break;
        case 0x5e3e:arithmetic(lb(-3),76,true,true);r.ip=0x5e42;break;
        case 0x5e42:branch(!flag(1)&&!flag(0x40),0x5e4e,0x5e44);break;
        case 0x5e44:r.di=local(4);r.ip=0x5e47;break;
        case 0x5e47:parentByteStore(-36,1);r.ip=0x5e4c;break;
        case 0x5e4c:r.ip=0x5e59;break;
        case 0x5e4e:r.ax=dw(0xc204);r.ip=0x5e51;break;
        case 0x5e51:store(-6,arithmetic(local(-6),r.ax));r.ip=0x5e54;break;
        case 0x5e54:store(-10,increment(local(-10)));r.ip=0x5e57;break;
        case 0x5e57:r.ip=0x5e1f;break;
        case 0x5e59:r.ax=dw(0x78c2);r.ip=0x5e5c;break;
        case 0x5e5c:r.dx=logic(0);r.ip=0x5e5e;break;
        case 0x5e5e:r.cx=29;r.ip=0x5e61;break;
        case 0x5e61:divide(r.cx);r.ip=0x5e63;break;
        case 0x5e63:std::swap(r.ax,r.dx);r.ip=0x5e64;break;
        case 0x5e64:logic(r.ax);r.ip=0x5e66;break;
        case 0x5e66:branch(flag(0x40),0x5e6b,0x5e68);break;
        case 0x5e68:r.ip=0x5ef4;break;
        case 0x5e6b:push(100);r.ip=0x5e6d;break;
        case 0x5e6d:farCall(0x13a8,0x5e72);break;
        case 0x5e72:arithmetic(r.ax,70,true);r.ip=0x5e75;break;
        case 0x5e75:branch(flag(1)||flag(0x40),0x5e8f,0x5e77);break;
        case 0x5e77:r.ax=dw(0x78c2);r.ip=0x5e7a;break;
        case 0x5e7a:r.ax=logic(r.ax&1u);r.ip=0x5e7d;break;
        case 0x5e7d:logic(r.ax);r.ip=0x5e7f;break;
        case 0x5e7f:branch(!flag(0x40),0x5e8f,0x5e81);break;
        case 0x5e81:bus.writeWord(r.ds,0x2074,105);r.ip=0x5e87;break;
        case 0x5e87:bus.writeByte(r.ds,0x799f,4);r.ip=0x5e8c;break;
        case 0x5e8c:nearCall(0x165a,0x5e8f);break;
        case 0x5e8f:r.di=local(4);r.ip=0x5e92;break;
        case 0x5e92:arithmetic(parent(-4),0,true);r.ip=0x5e97;break;
        case 0x5e97:branch(flag(0x40)||less(),0x5ead,0x5e99);break;
        case 0x5e99:push(800);r.ip=0x5e9c;break;
        case 0x5e9c:farCall(0x13a8,0x5ea1);break;
        case 0x5ea1:r.ax=arithmetic(r.ax,150);r.ip=0x5ea4;break;
        case 0x5ea4:r.di=local(4);r.ip=0x5ea7;break;
        case 0x5ea7:parentStore(-12,r.ax);r.ip=0x5eab;break;
        case 0x5eab:r.ip=0x5ecc;break;
        case 0x5ead:push(800);r.ip=0x5eb0;break;
        case 0x5eb0:farCall(0x13a8,0x5eb5);break;
        case 0x5eb5:r.dx=logic(0);r.ip=0x5eb7;break;
        case 0x5eb7:r.cx=r.ax;r.ip=0x5eb9;break;
        case 0x5eb9:r.bx=r.dx;r.ip=0x5ebb;break;
        case 0x5ebb:r.ax=0xff6a;r.ip=0x5ebe;break;
        case 0x5ebe:r.dx=0xffff;r.ip=0x5ec1;break;
        case 0x5ec1:r.ax=arithmetic(r.ax,r.cx,true);r.ip=0x5ec3;break;
        case 0x5ec3:r.dx=arithmetic(r.dx,r.bx,true,false,true);r.ip=0x5ec5;break;
        case 0x5ec5:r.di=local(4);r.ip=0x5ec8;break;
        case 0x5ec8:parentStore(-12,r.ax);r.ip=0x5ecc;break;
        case 0x5ecc:r.di=local(4);r.ip=0x5ecf;break;
        case 0x5ecf:arithmetic(parentByte(-33),0,true,true);r.ip=0x5ed4;break;
        case 0x5ed4:branch(flag(0x40),0x5ef4,0x5ed6);break;
        case 0x5ed6:push(1500);r.ip=0x5ed9;break;
        case 0x5ed9:farCall(0x13a8,0x5ede);break;
        case 0x5ede:r.dx=logic(0);r.ip=0x5ee0;break;
        case 0x5ee0:r.ax=arithmetic(0,r.ax,true);r.ip=0x5ee2;break;
        case 0x5ee2:r.dx=arithmetic(r.dx,0,false,false,true);r.ip=0x5ee5;break;
        case 0x5ee5:r.dx=arithmetic(0,r.dx,true);r.ip=0x5ee7;break;
        case 0x5ee7:r.ax=arithmetic(r.ax,300,true);r.ip=0x5eea;break;
        case 0x5eea:r.dx=arithmetic(r.dx,0,true,false,true);r.ip=0x5eed;break;
        case 0x5eed:r.di=local(4);r.ip=0x5ef0;break;
        case 0x5ef0:parentStore(-14,r.ax);r.ip=0x5ef4;break;
        case 0x5ef4:bus.writeByte(r.ds,0x661e,0);r.ip=0x5ef9;break;
        case 0x5ef9:r.di=local(4);r.ip=0x5efc;break;
        case 0x5efc:r.ax=parent(-42);r.ip=0x5f00;break;
        case 0x5f00:store(-6,r.ax);r.ip=0x5f03;break;
        case 0x5f03:store(-10,1);r.ip=0x5f08;break;
        case 0x5f08:al(lb(-2));r.ip=0x5f0b;break;
        case 0x5f0b:zeroAh();r.ip=0x5f0d;break;
        case 0x5f0d:arithmetic(r.ax,local(-10),true);r.ip=0x5f10;break;
        case 0x5f10:branch(flag(1),0x5f5f,0x5f12);break;
        case 0x5f12:r.ax=local(-6);r.ip=0x5f15;break;
        case 0x5f15:store(-8,r.ax);r.ip=0x5f18;break;
        case 0x5f18:store(-12,1);r.ip=0x5f1d;break;
        case 0x5f1d:al(lb(-1));r.ip=0x5f20;break;
        case 0x5f20:zeroAh();r.ip=0x5f22;break;
        case 0x5f22:arithmetic(r.ax,local(-12),true);r.ip=0x5f25;break;
        case 0x5f25:branch(flag(1),0x5f50,0x5f27);break;
        case 0x5f27:r.ax=local(-6);r.ip=0x5f2a;break;
        case 0x5f2a:r.di=dw(0xc1e0);r.es=dw(0xc1e2);r.ip=0x5f2e;break;
        case 0x5f2e:r.di=arithmetic(r.di,r.ax);r.ip=0x5f30;break;
        case 0x5f30:al(byte(0));r.ip=0x5f33;break;
        case 0x5f33:sb(-3,static_cast<uint8_t>(r.ax));r.ip=0x5f36;break;
        case 0x5f36:arithmetic(lb(-3),117,true,true);r.ip=0x5f3a;break;
        case 0x5f3a:branch(!flag(0x40),0x5f46,0x5f3c);break;
        case 0x5f3c:bus.writeByte(r.ds,0x661e,static_cast<uint8_t>(increment(data(0x661e),false,true)));r.ip=0x5f40;break;
        case 0x5f40:r.ax=local(-6);r.ip=0x5f43;break;
        case 0x5f43:bus.writeWord(r.ds,0x2072,r.ax);r.ip=0x5f46;break;
        case 0x5f46:store(-12,arithmetic(local(-12),2));r.ip=0x5f4a;break;
        case 0x5f4a:store(-6,arithmetic(local(-6),2));r.ip=0x5f4e;break;
        case 0x5f4e:r.ip=0x5f1d;break;
        case 0x5f50:r.ax=local(-8);r.ip=0x5f53;break;
        case 0x5f53:r.ax=arithmetic(r.ax,dw(0xc204));r.ip=0x5f57;break;
        case 0x5f57:store(-6,r.ax);r.ip=0x5f5a;break;
        case 0x5f5a:store(-10,increment(local(-10)));r.ip=0x5f5d;break;
        case 0x5f5d:r.ip=0x5f08;break;
        case 0x5f5f:arithmetic(data(0x661e),0,true,true);r.ip=0x5f64;break;
        case 0x5f64:branch(flag(0x40)||less(),0x5fb3,0x5f66);break;
        case 0x5f66:nearCall(0x3a56,0x5f69);break;
        case 0x5f69:r.di=dw(0x2074);r.ip=0x5f6d;break;
        case 0x5f6d:arithmetic(data(static_cast<uint16_t>(r.di+0x78d5u)),1,true,true);r.ip=0x5f72;break;
        case 0x5f72:branch(flag(1)||flag(0x40),0x5f7d,0x5f74);break;
        case 0x5f74:al(data(0x661e));r.ip=0x5f77;break;
        case 0x5f77:cbw();r.ip=0x5f78;break;
        case 0x5f78:r.ax=shift(r.ax,1);r.ip=0x5f7a;break;
        case 0x5f7a:bus.writeByte(r.ds,0x661e,static_cast<uint8_t>(r.ax));r.ip=0x5f7d;break;
        case 0x5f7d:les(-16);r.ip=0x5f80;break;
        case 0x5f80:al(byte(36));r.ip=0x5f84;break;
        case 0x5f84:sb(-3,static_cast<uint8_t>(r.ax));r.ip=0x5f87;break;
        case 0x5f87:al(lb(-3));r.ip=0x5f8a;break;
        case 0x5f8a:zeroAh();r.ip=0x5f8c;break;
        case 0x5f8c:r.dx=r.ax;r.ip=0x5f8e;break;
        case 0x5f8e:al(data(0x661e));r.ip=0x5f91;break;
        case 0x5f91:cbw();r.ip=0x5f92;break;
        case 0x5f92:arithmetic(r.ax,r.dx,true);r.ip=0x5f94;break;
        case 0x5f94:branch(flag(0x40)||less(),0x5fa1,0x5f96);break;
        case 0x5f96:r.di=local(4);r.ip=0x5f99;break;
        case 0x5f99:indirectLes();r.ip=0x5f9d;break;
        case 0x5f9d:wb(2,static_cast<uint8_t>(increment(byte(2),true,true)));r.ip=0x5fa1;break;
        case 0x5fa1:al(data(0x661e));r.ip=0x5fa4;break;
        case 0x5fa4:les(-16);r.ip=0x5fa7;break;
        case 0x5fa7:wb(36,static_cast<uint8_t>(arithmetic(byte(36),r.ax&255u,true,true)));r.ip=0x5fab;break;
        case 0x5fab:push(47);r.ip=0x5fad;break;
        case 0x5fad:push(local(4));r.ip=0x5fb0;break;
        case 0x5fb0:nearCall(0x5a75,0x5fb3);break;
        case 0x5fb3:les(-16);r.ip=0x5fb6;break;
        case 0x5fb6:arithmetic(byte(2),255,true,true);r.ip=0x5fbb;break;
        case 0x5fbb:branch(!flag(0x40),0x5fc1,0x5fbd);break;
        case 0x5fbd:push(r.bp);r.ip=0x5fbe;break;
        case 0x5fbe:nearCall(0x5bcc,0x5fc1);break;
        case 0x5fc1:r.di=local(4);r.ip=0x5fc4;break;
        case 0x5fc4:arithmetic(parentByte(-33),0,true,true);r.ip=0x5fc9;break;
        case 0x5fc9:branch(!flag(0x40),0x5fd3,0x5fcb);break;
        case 0x5fcb:r.di=local(4);r.ip=0x5fce;break;
        case 0x5fce:parentStore(-14,arithmetic(parent(-14),64));r.ip=0x5fd3;break;
        case 0x5fd3:r.di=local(4);r.ip=0x5fd6;break;
        case 0x5fd6:arithmetic(parentByte(-34),0,true,true);r.ip=0x5fdb;break;
        case 0x5fdb:branch(flag(0x40),0x5fe7,0x5fdd);break;
        case 0x5fdd:r.di=local(4);r.ip=0x5fe0;break;
        case 0x5fe0:arithmetic(parent(-14),0,true);r.ip=0x5fe5;break;
        case 0x5fe5:branch(less(),0x5ffb,0x5fe7);break;
        case 0x5fe7:r.di=local(4);r.ip=0x5fea;break;
        case 0x5fea:arithmetic(parentByte(-33),0,true,true);r.ip=0x5fef;break;
        case 0x5fef:branch(flag(0x40),0x6011,0x5ff1);break;
        case 0x5ff1:r.di=local(4);r.ip=0x5ff4;break;
        case 0x5ff4:arithmetic(parent(-14),0,true);r.ip=0x5ff9;break;
        case 0x5ff9:branch(flag(0x40)||less(),0x6011,0x5ffb);break;
        case 0x5ffb:r.di=local(4);r.ip=0x5ffe;break;
        case 0x5ffe:r.ax=parent(-14);r.ip=0x6002;break;
        case 0x6002:cwd();r.ip=0x6003;break;
        case 0x6003:r.cx=2;r.ip=0x6006;break;
        case 0x6006:signedDivide(r.cx);r.ip=0x6008;break;
        case 0x6008:r.ax=arithmetic(0,r.ax,true);r.ip=0x600a;break;
        case 0x600a:r.di=local(4);r.ip=0x600d;break;
        case 0x600d:parentStore(-14,r.ax);r.ip=0x6011;break;
        case 0x6011:r.di=local(4);r.ip=0x6014;break;
        case 0x6014:arithmetic(parentByte(-35),0,true,true);r.ip=0x6019;break;
        case 0x6019:branch(flag(0x40),0x6025,0x601b);break;
        case 0x601b:r.di=local(4);r.ip=0x601e;break;
        case 0x601e:arithmetic(parent(-12),0,true);r.ip=0x6023;break;
        case 0x6023:branch(less(),0x6039,0x6025);break;
        case 0x6025:r.di=local(4);r.ip=0x6028;break;
        case 0x6028:arithmetic(parentByte(-36),0,true,true);r.ip=0x602d;break;
        case 0x602d:branch(flag(0x40),0x604f,0x602f);break;
        case 0x602f:r.di=local(4);r.ip=0x6032;break;
        case 0x6032:arithmetic(parent(-12),0,true);r.ip=0x6037;break;
        case 0x6037:branch(flag(0x40)||less(),0x604f,0x6039);break;
        case 0x6039:r.di=local(4);r.ip=0x603c;break;
        case 0x603c:r.ax=parent(-12);r.ip=0x6040;break;
        case 0x6040:cwd();r.ip=0x6041;break;
        case 0x6041:r.cx=2;r.ip=0x6044;break;
        case 0x6044:signedDivide(r.cx);r.ip=0x6046;break;
        case 0x6046:r.ax=arithmetic(0,r.ax,true);r.ip=0x6048;break;
        case 0x6048:r.di=local(4);r.ip=0x604b;break;
        case 0x604b:parentStore(-12,r.ax);r.ip=0x604f;break;
        case 0x604f:r.sp=r.bp;r.bp=pop();r.ip=0x6050;break;
        case 0x6050:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+2u);break;

        // Reverse bomb attribution retains the previous result when unmatched.
        case 0x3a56:r.ax=dw(0x2076);r.ip=0x3a59;break;
        case 0x3a59:r.ax=increment(r.ax,true);r.ip=0x3a5a;break;
        case 0x3a5a:r.bx=11;r.ip=0x3a5d;break;
        case 0x3a5d:multiply(r.bx);r.ip=0x3a5f;break;
        case 0x3a5f:r.bx=r.ax;r.ip=0x3a61;break;
        case 0x3a61:r.ax=dw(static_cast<uint16_t>(r.bx+0x209eu));r.ip=0x3a65;break;
        case 0x3a65:arithmetic(r.ax,dw(0x2072),true);r.ip=0x3a69;break;
        case 0x3a69:branch(!flag(0x40),0x3a78,0x3a6b);break;
        case 0x3a6b:r.ax=r.bx;r.ip=0x3a6d;break;
        case 0x3a6d:r.bx=11;r.ip=0x3a70;break;
        case 0x3a70:divide(r.bx);r.ip=0x3a72;break;
        case 0x3a72:r.ax=increment(r.ax);r.ip=0x3a73;break;
        case 0x3a73:bus.writeWord(r.ds,0x2074,r.ax);r.ip=0x3a76;break;
        case 0x3a76:r.ip=0x3a7d;break;
        case 0x3a78:r.bx=arithmetic(r.bx,11,true);r.ip=0x3a7b;break;
        case 0x3a7b:branch(!flag(1),0x3a61,0x3a7d);break;
        case 0x3a7d:r.ip=pop();break;

        // Fatal conversion walks physical actors and then performs the trigger.
        case 0x5bcc:push(r.bp);r.ip=0x5bcd;break;
        case 0x5bcd:r.bp=r.sp;r.ip=0x5bcf;break;
        case 0x5bcf:r.ax=10;r.ip=0x5bd2;break;
        case 0x5bd2:farCall(0x4df,0x5bd7);break;
        case 0x5bd7:r.sp=arithmetic(r.sp,10,true);r.ip=0x5bda;break;
        case 0x5bda:r.di=local(4);r.ip=0x5bdd;break;
        case 0x5bdd:r.di=parent(4);r.ip=0x5be1;break;
        case 0x5be1:indirectLes();r.ip=0x5be5;break;
        case 0x5be5:r.ax=read(18);r.ip=0x5be9;break;
        case 0x5be9:store(-4,r.ax);r.ip=0x5bec;break;
        case 0x5bec:al(data(0x208d));r.ip=0x5bef;break;
        case 0x5bef:zeroAh();r.ip=0x5bf1;break;
        case 0x5bf1:store(-6,r.ax);r.ip=0x5bf4;break;
        case 0x5bf4:r.ax=1;r.ip=0x5bf7;break;
        case 0x5bf7:arithmetic(r.ax,local(-6),true);r.ip=0x5bfa;break;
        case 0x5bfa:branch(!flag(1)&&!flag(0x40),0x5c59,0x5bfc);break;
        case 0x5bfc:store(-2,r.ax);r.ip=0x5bff;break;
        case 0x5bff:r.ip=0x5c04;break;
        case 0x5c01:store(-2,increment(local(-2)));r.ip=0x5c04;break;
        case 0x5c04:signedMultiply(local(-2),38);r.ip=0x5c08;break;
        case 0x5c08:r.di=arithmetic(r.di,0x1bae);r.ip=0x5c0c;break;
        case 0x5c0c:store(-10,r.di);r.ip=0x5c0f;break;
        case 0x5c0f:store(-8,r.ds);r.ip=0x5c12;break;
        case 0x5c12:les(-10);r.ip=0x5c15;break;
        case 0x5c15:arithmetic(byte(0),31,true,true);r.ip=0x5c19;break;
        case 0x5c19:branch(!flag(0x40),0x5c51,0x5c1b);break;
        case 0x5c1b:les(-10);r.ip=0x5c1e;break;
        case 0x5c1e:al(byte(37));r.ip=0x5c22;break;
        case 0x5c22:zeroAh();r.ip=0x5c24;break;
        case 0x5c24:arithmetic(r.ax,local(-4),true);r.ip=0x5c27;break;
        case 0x5c27:branch(!flag(0x40),0x5c51,0x5c29);break;
        case 0x5c29:les(-10);r.ip=0x5c2c;break;
        case 0x5c2c:wb(0,14);r.ip=0x5c30;break;
        case 0x5c30:push(10);r.ip=0x5c32;break;
        case 0x5c32:farCall(0x13a8,0x5c37);break;
        case 0x5c37:r.ax=arithmetic(r.ax,40);r.ip=0x5c3a;break;
        case 0x5c3a:les(-10);r.ip=0x5c3d;break;
        case 0x5c3d:wb(2,static_cast<uint8_t>(r.ax));r.ip=0x5c41;break;
        case 0x5c41:les(-10);r.ip=0x5c44;break;
        case 0x5c44:wb(21,2);r.ip=0x5c49;break;
        case 0x5c49:les(-10);r.ip=0x5c4c;break;
        case 0x5c4c:wb(27,0);r.ip=0x5c51;break;
        case 0x5c51:r.ax=local(-2);r.ip=0x5c54;break;
        case 0x5c54:arithmetic(r.ax,local(-6),true);r.ip=0x5c57;break;
        case 0x5c57:branch(!flag(0x40),0x5c01,0x5c59);break;
        case 0x5c59:r.di=local(4);r.ip=0x5c5c;break;
        case 0x5c5c:r.di=parent(4);r.ip=0x5c60;break;
        case 0x5c60:indirectLes();r.ip=0x5c64;break;
        case 0x5c64:wb(21,2);r.ip=0x5c69;break;
        case 0x5c69:r.di=local(4);r.ip=0x5c6c;break;
        case 0x5c6c:r.di=parent(4);r.ip=0x5c70;break;
        case 0x5c70:indirectLes();r.ip=0x5c74;break;
        case 0x5c74:wb(0,14);r.ip=0x5c78;break;
        case 0x5c78:r.di=local(4);r.ip=0x5c7b;break;
        case 0x5c7b:r.di=parent(4);r.ip=0x5c7f;break;
        case 0x5c7f:indirectLes();r.ip=0x5c83;break;
        case 0x5c83:wb(2,60);r.ip=0x5c88;break;
        case 0x5c88:r.di=local(4);r.ip=0x5c8b;break;
        case 0x5c8b:r.di=parent(4);r.ip=0x5c8f;break;
        case 0x5c8f:indirectLes();r.ip=0x5c93;break;
        case 0x5c93:wb(27,0);r.ip=0x5c98;break;
        case 0x5c98:push(1000);r.ip=0x5c9b;break;
        case 0x5c9b:nearCall(0x5740,0x5c9e);break;
        case 0x5c9e:bus.writeWord(r.ds,0x2074,61);r.ip=0x5ca4;break;
        case 0x5ca4:bus.writeByte(r.ds,0x799f,12);r.ip=0x5ca9;break;
        case 0x5ca9:nearCall(0x165a,0x5cac);break;
        case 0x5cac:r.sp=r.bp;r.bp=pop();r.ip=0x5cad;break;
        case 0x5cad:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+2u);break;

        // Tile-trigger records use last-match selection and inclusive ranges.
        case 0x5740:push(r.bp);r.ip=0x5741;break;
        case 0x5741:r.bp=r.sp;r.ip=0x5743;break;
        case 0x5743:r.ax=14;r.ip=0x5746;break;
        case 0x5746:farCall(0x4df,0x574b);break;
        case 0x574b:r.sp=arithmetic(r.sp,14,true);r.ip=0x574e;break;
        case 0x574e:r.ax=local(4);r.ip=0x5751;break;
        case 0x5751:r.ax=logic(r.ax&0x7fffu);r.ip=0x5754;break;
        case 0x5754:store(4,r.ax);r.ip=0x5757;break;
        case 0x5757:r.ax=dw(0x2074);r.ip=0x575a;break;
        case 0x575a:store(-4,r.ax);r.ip=0x575d;break;
        case 0x575d:bus.writeWord(r.ds,0x2074,39);r.ip=0x5763;break;
        case 0x5763:bus.writeByte(r.ds,0x799f,6);r.ip=0x5768;break;
        case 0x5768:nearCall(0x165a,0x576b);break;
        case 0x576b:r.ax=local(-4);r.ip=0x576e;break;
        case 0x576e:bus.writeWord(r.ds,0x2074,r.ax);r.ip=0x5771;break;
        case 0x5771:r.ax=logic(0);r.ip=0x5773;break;
        case 0x5773:store(-6,r.ax);r.ip=0x5776;break;
        case 0x5776:arithmetic(data(0x79a7),0,true,true);r.ip=0x577b;break;
        case 0x577b:branch(flag(1)||flag(0x40),0x57b0,0x577d);break;
        case 0x577d:al(data(0x79a7));r.ip=0x5780;break;
        case 0x5780:zeroAh();r.ip=0x5782;break;
        case 0x5782:store(-10,r.ax);r.ip=0x5785;break;
        case 0x5785:r.ax=1;r.ip=0x5788;break;
        case 0x5788:arithmetic(r.ax,local(-10),true);r.ip=0x578b;break;
        case 0x578b:branch(!flag(1)&&!flag(0x40),0x57b0,0x578d);break;
        case 0x578d:store(-2,r.ax);r.ip=0x5790;break;
        case 0x5790:r.ip=0x5795;break;
        case 0x5792:store(-2,increment(local(-2)));r.ip=0x5795;break;
        case 0x5795:signedMultiply(local(-2),14);r.ip=0x5799;break;
        case 0x5799:r.ax=dw(static_cast<uint16_t>(r.di+0x77c4u));r.ip=0x579d;break;
        case 0x579d:arithmetic(r.ax,local(4),true);r.ip=0x57a0;break;
        case 0x57a0:branch(!flag(0x40),0x57a8,0x57a2);break;
        case 0x57a2:r.ax=local(-2);r.ip=0x57a5;break;
        case 0x57a5:store(-6,r.ax);r.ip=0x57a8;break;
        case 0x57a8:r.ax=local(-2);r.ip=0x57ab;break;
        case 0x57ab:arithmetic(r.ax,local(-10),true);r.ip=0x57ae;break;
        case 0x57ae:branch(!flag(0x40),0x5792,0x57b0);break;
        case 0x57b0:arithmetic(local(-6),0,true);r.ip=0x57b4;break;
        case 0x57b4:branch(!flag(1)&&!flag(0x40),0x57b9,0x57b6);break;
        case 0x57b6:r.ip=0x586e;break;
        case 0x57b9:signedMultiply(local(-6),14);r.ip=0x57bd;break;
        case 0x57bd:r.di=arithmetic(r.di,0x77c0);r.ip=0x57c1;break;
        case 0x57c1:store(-12,r.di);r.ip=0x57c4;break;
        case 0x57c4:store(-10,r.ds);r.ip=0x57c7;break;
        case 0x57c7:r.ax=dw(0x78ba);r.ip=0x57ca;break;
        case 0x57ca:store(-14,r.ax);r.ip=0x57cd;break;
        case 0x57cd:r.ax=1;r.ip=0x57d0;break;
        case 0x57d0:arithmetic(r.ax,local(-14),true);r.ip=0x57d3;break;
        case 0x57d3:branch(flag(1)||flag(0x40),0x57d8,0x57d5);break;
        case 0x57d5:r.ip=0x586e;break;
        case 0x57d8:store(-2,r.ax);r.ip=0x57db;break;
        case 0x57db:r.ip=0x57e0;break;
        case 0x57dd:store(-2,increment(local(-2)));r.ip=0x57e0;break;
        case 0x57e0:r.ax=dw(0x206e);r.ip=0x57e3;break;
        case 0x57e3:push(r.ax);r.ip=0x57e4;break;
        case 0x57e4:r.ax=local(-2);r.ip=0x57e7;break;
        case 0x57e7:r.ax=shift(r.ax,1);r.ip=0x57e9;break;
        case 0x57e9:r.di=r.ax;r.ip=0x57eb;break;
        case 0x57eb:r.es=pop();r.ip=0x57ec;break;
        case 0x57ec:r.ax=read(0);r.ip=0x57ef;break;
        case 0x57ef:store(-8,r.ax);r.ip=0x57f2;break;
        case 0x57f2:r.ax=local(-8);r.ip=0x57f5;break;
        case 0x57f5:r.ax=logic(r.ax&0x7fffu);r.ip=0x57f8;break;
        case 0x57f8:store(-8,r.ax);r.ip=0x57fb;break;
        case 0x57fb:r.ax=local(-8);r.ip=0x57fe;break;
        case 0x57fe:les(-12);r.ip=0x5801;break;
        case 0x5801:arithmetic(r.ax,read(0),true);r.ip=0x5804;break;
        case 0x5804:branch(flag(1),0x5863,0x5806);break;
        case 0x5806:r.ax=local(-8);r.ip=0x5809;break;
        case 0x5809:les(-12);r.ip=0x580c;break;
        case 0x580c:arithmetic(r.ax,read(2),true);r.ip=0x5810;break;
        case 0x5810:branch(!flag(1)&&!flag(0x40),0x5863,0x5812);break;
        case 0x5812:store(-4,1);r.ip=0x5817;break;
        case 0x5817:r.ip=0x581c;break;
        case 0x5819:store(-4,increment(local(-4)));r.ip=0x581c;break;
        case 0x581c:r.ax=local(-4);r.ip=0x581f;break;
        case 0x581f:les(-12);r.ip=0x5822;break;
        case 0x5822:r.di=arithmetic(r.di,r.ax);r.ip=0x5824;break;
        case 0x5824:arithmetic(byte(5),0,true,true);r.ip=0x5829;break;
        case 0x5829:branch(flag(1)||flag(0x40),0x585d,0x582b);break;
        case 0x582b:r.ax=local(-4);r.ip=0x582e;break;
        case 0x582e:les(-12);r.ip=0x5831;break;
        case 0x5831:r.di=arithmetic(r.di,r.ax);r.ip=0x5833;break;
        case 0x5833:dl(byte(5));r.ip=0x5837;break;
        case 0x5837:r.ax=dw(0xc1fe);r.ip=0x583a;break;
        case 0x583a:push(r.ax);r.ip=0x583b;break;
        case 0x583b:r.di=local(-2);r.ip=0x583e;break;
        case 0x583e:r.es=pop();r.ip=0x583f;break;
        case 0x583f:al(byte(0));r.ip=0x5842;break;
        case 0x5842:arithmetic(r.ax&255u,r.dx&255u,true,true);r.ip=0x5844;break;
        case 0x5844:branch(!flag(0x40),0x585d,0x5846);break;
        case 0x5846:r.ax=local(-4);r.ip=0x5849;break;
        case 0x5849:les(-12);r.ip=0x584c;break;
        case 0x584c:r.di=arithmetic(r.di,r.ax);r.ip=0x584e;break;
        case 0x584e:dl(byte(9));r.ip=0x5852;break;
        case 0x5852:r.ax=dw(0xc1fe);r.ip=0x5855;break;
        case 0x5855:push(r.ax);r.ip=0x5856;break;
        case 0x5856:r.di=local(-2);r.ip=0x5859;break;
        case 0x5859:r.es=pop();r.ip=0x585a;break;
        case 0x585a:wb(0,static_cast<uint8_t>(r.dx));r.ip=0x585d;break;
        case 0x585d:arithmetic(local(-4),4,true);r.ip=0x5861;break;
        case 0x5861:branch(!flag(0x40),0x5819,0x5863);break;
        case 0x5863:r.ax=local(-2);r.ip=0x5866;break;
        case 0x5866:arithmetic(r.ax,local(-14),true);r.ip=0x5869;break;
        case 0x5869:branch(flag(0x40),0x586e,0x586b);break;
        case 0x586b:r.ip=0x57dd;break;
        case 0x586e:r.sp=r.bp;r.bp=pop();r.ip=0x586f;break;
        case 0x586f:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+2u);break;

        case 0x165a:al(data(0x79c4));r.ip=0x165d;break;
        case 0x165d:arithmetic(r.ax&255u,0,true,true);r.ip=0x165f;break;
        case 0x165f:branch(flag(0x40),0x166c,0x1661);break;
        case 0x1661:al(data(0x799e));r.ip=0x1664;break;
        case 0x1664:al(static_cast<uint8_t>(increment(r.ax&255u,true,true)));r.ip=0x1666;break;
        case 0x1666:arithmetic(r.ax&255u,data(0x799f),true,true);r.ip=0x166a;break;
        case 0x166a:branch(!less(),0x167d,0x166c);break;
        case 0x166c:al(data(0x799f));r.ip=0x166f;break;
        case 0x166f:bus.writeByte(r.ds,0x799e,static_cast<uint8_t>(r.ax));r.ip=0x1672;break;
        case 0x1672:r.ax=dw(0x2074);r.ip=0x1675;break;
        case 0x1675:bus.writeWord(r.ds,0x78c0,r.ax);r.ip=0x1678;break;
        case 0x1678:bus.writeByte(r.ds,0x79c4,1);r.ip=0x167d;break;
        case 0x167d:r.ip=pop();break;
        default:throw std::domain_error("Actor contact reached an unrecovered instruction");
        }
    }
};

enum class FrameActorContactOutcome { Running, TileBehavior, MotionIntegration, TransientQueues, Restart, EndRunUi, RuntimeError, BreakOutput };
using FrameActorContactCallee=std::variant<FrameActorPrecontactSnapshot,ActorContactSnapshot>;
struct FrameActorContactSnapshot {
    FrameActorContactCallee callee;
    uint16_t gameSegment=0;
    uint32_t idToggleMask=0;
    uint64_t dispatchedInstructions=0,prefixTimerInstructions=0,prefixTimerDeliveries=0;
    FrameActorContactOutcome outcome=FrameActorContactOutcome::Running;
    bool operator==(const FrameActorContactSnapshot&) const = default;
};

class FrameActorContactOperation {
public:
    using CopyBudget=FrameActorPrecontactOperation::CopyBudget;
    FrameActorContactOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        : state_{r.ip==0x654e ? FrameActorContactCallee{ActorContactOperation(r,game,idToggle).snapshot()} :
            FrameActorContactCallee{FrameActorPrecontactOperation(r,game,idToggle).snapshot()},game,idToggle} { validate(); }
    FrameActorContactOperation(DosGetTimeRegisters r,uint16_t dos,uint16_t keyboard,uint16_t psp,uint16_t game,uint32_t idToggle)
        : state_{FrameActorPrecontactOperation(r,dos,keyboard,psp,game,idToggle).snapshot(),game,idToggle} { validate(); }
    explicit FrameActorContactOperation(FrameActorContactSnapshot state) : state_(state) { validate(); }
    const FrameActorContactSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const {
        return std::visit([](const auto& child) -> DosGetTimeRegisters {
            using Child=std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child,FrameActorPrecontactSnapshot>) return FrameActorPrecontactOperation(child).registers();
            else return ActorContactOperation(child).registers();
        },state_.callee);
    }
    bool finished() const noexcept { return state_.outcome!=FrameActorContactOutcome::Running; }
    bool interruptInProgress() const {
        return std::visit([](const auto& child) {
            using Child=std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child,FrameActorPrecontactSnapshot>) return FrameActorPrecontactOperation(child).interruptInProgress();
            else return ActorContactOperation(child).interruptInProgress();
        },state_.callee);
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished frame actor contact admitted IRQ");
        std::visit([&](auto& child) {
            using Child=std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child,FrameActorPrecontactSnapshot>) {
                FrameActorPrecontactOperation operation(child);operation.deliverTimerInterrupt(bus);child=operation.snapshot();savePrefixTimers(child);
            } else {
                ActorContactOperation operation(child);operation.deliverTimerInterrupt(bus);child=operation.snapshot();
            }
        },state_.callee);
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            std::optional<DosGetTimeRegisters> next;
            std::visit([&](auto& child) {
                using Child=std::remove_cvref_t<decltype(child)>;
                if constexpr (std::is_same_v<Child,FrameActorPrecontactSnapshot>) {
                    FrameActorPrecontactOperation operation(child);
                    if (operation.advance(1,bus,copies)!=1) throw std::domain_error("Actor precontact did not dispatch");
                    child=operation.snapshot();savePrefixTimers(child);
                    if (operation.finished()) {
                        switch (child.outcome) {
                        case FrameActorPrecontactOutcome::BehaviorDispatch:next=operation.registers();break;
                        case FrameActorPrecontactOutcome::TransientQueues:state_.outcome=FrameActorContactOutcome::TransientQueues;break;
                        case FrameActorPrecontactOutcome::Restart:state_.outcome=FrameActorContactOutcome::Restart;break;
                        case FrameActorPrecontactOutcome::EndRunUi:state_.outcome=FrameActorContactOutcome::EndRunUi;break;
                        case FrameActorPrecontactOutcome::RuntimeError:state_.outcome=FrameActorContactOutcome::RuntimeError;break;
                        case FrameActorPrecontactOutcome::BreakOutput:state_.outcome=FrameActorContactOutcome::BreakOutput;break;
                        default:throw std::logic_error("Finished actor precontact has no outcome");
                        }
                    }
                } else {
                    ActorContactOperation operation(child);
                    if (operation.advance(1,bus)!=1) throw std::domain_error("Actor contact did not dispatch");
                    child=operation.snapshot();
                    if (operation.finished()) state_.outcome=child.outcome==ActorContactOutcome::TileBehavior ?
                        FrameActorContactOutcome::TileBehavior : child.outcome==ActorContactOutcome::MotionIntegration ?
                        FrameActorContactOutcome::MotionIntegration : FrameActorContactOutcome::RuntimeError;
                }
            },state_.callee);
            if (next) state_.callee=ActorContactOperation(*next,state_.gameSegment,state_.idToggleMask).snapshot();
            ++used;++state_.dispatchedInstructions;
        }
        return used;
    }
private:
    FrameActorContactSnapshot state_;
    void validate() const {
        if ((state_.idToggleMask!=0 && state_.idToggleMask!=0x200000) ||
            !std::visit([&](const auto& child) { return child.gameSegment==state_.gameSegment && child.idToggleMask==state_.idToggleMask; },state_.callee))
            throw std::invalid_argument("Frame actor contact ID-toggle/callee ownership differs");
    }
    void savePrefixTimers(const FrameActorPrecontactSnapshot& prefix) {
        state_.prefixTimerInstructions=prefix.entryTimerInstructions;state_.prefixTimerDeliveries=prefix.entryTimerDeliveries;
        if (const auto* entry=std::get_if<FrameActorEntrySnapshot>(&prefix.callee)) {
            state_.prefixTimerInstructions=entry->prefixTimerInstructions+entry->tailTimerInstructions;
            state_.prefixTimerDeliveries=entry->prefixTimerDeliveries+entry->tailTimerDeliveries;
        } else if (const auto* body=std::get_if<ActorPrecontactSnapshot>(&prefix.callee)) {
            state_.prefixTimerInstructions+=body->timerInstructions;state_.prefixTimerDeliveries+=body->timerDeliveries;
        }
    }
};

} // namespace lezac::core
