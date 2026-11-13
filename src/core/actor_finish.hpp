#pragma once

#include "core/actor_contact.hpp"
#include "core/actor_real48.hpp"

namespace lezac::core {

enum class ActorFinishOutcome { Running, Returned, RuntimeError };
struct ActorFinishSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment=0;
    uint32_t idToggleMask=0;
    std::optional<TimerIrqSnapshot> timer=std::nullopt;
    uint64_t dispatchedInstructions=0,timerInstructions=0,timerDeliveries=0,transferredBytes=0;
    ActorFinishOutcome outcome=ActorFinishOutcome::Running;
    bool operator==(const ActorFinishSnapshot&) const = default;
};

// Original common 73E5..7783 tail, with its damage/expiry helpers and near return.
// The caller instruction after RET remains unexecuted.
class ActorFinishOperation {
public:
    using CopyBudget=ActorAnimationOperation::CopyBudget;
    ActorFinishOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle) : state_{r,game,idToggle} {
        if (r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2) || r.ip!=0x73e5)
            throw std::invalid_argument("Actor finish entry differs");
        validate();
    }
    explicit ActorFinishOperation(ActorFinishSnapshot state) : state_(state) { validate(); }
    const ActorFinishSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const { return state_.timer ? fromTimer(state_.timer->registers) : state_.registers; }
    bool finished() const noexcept { return state_.outcome!=ActorFinishOutcome::Running && !state_.timer; }
    bool interruptInProgress() const noexcept { return state_.timer.has_value(); }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished() || state_.timer || !(state_.registers.flags&0x200u))
            throw std::logic_error("Actor finish IRQ is not eligible");
        auto r=state_.registers;
        const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value); };
        push(static_cast<uint16_t>(r.flags));push(r.cs);push(r.ip);
        r.flags&=~uint32_t{0x300};r.cs=0xf000;r.ip=0xfea5;
        state_.timer=TimerIrqOperation(toTimer(r),state_.gameSegment,state_.idToggleMask).snapshot();
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (state_.timer) {
                TimerIrqOperation irq(*state_.timer);
                if (irq.advance(1,bus)!=1) throw std::domain_error("Actor finish IRQ did not dispatch");
                ++state_.timerInstructions;
                if (irq.returned()) { state_.registers=fromTimer(irq.snapshot().registers);state_.timer.reset(); }
                else state_.timer=irq.snapshot();
            } else {
                instruction(bus,copies);
                if (state_.registers.cs==library() && state_.registers.ip==0xe2)
                    state_.outcome=ActorFinishOutcome::RuntimeError;
            }
            ++used;++state_.dispatchedInstructions;
        }
        return used;
    }

private:
    ActorFinishSnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.gameSegment+0x920); }
    uint16_t graphics() const { return static_cast<uint16_t>(state_.gameSegment+0x8ac); }
    static TimerIrqRegisters toTimer(const DosGetTimeRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    static DosGetTimeRegisters fromTimer(const TimerIrqRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    void validate() const {
        const auto& r=state_.registers;
        if ((state_.idToggleMask!=0 && state_.idToggleMask!=0x200000) ||
            (r.cs!=state_.gameSegment && r.cs!=library() && r.cs!=graphics()) ||
            (r.cs==state_.gameSegment && r.ds!=static_cast<uint16_t>(state_.gameSegment+0xaa2)) ||
            (state_.timer && (state_.outcome!=ActorFinishOutcome::Running || state_.timer->returned ||
                !state_.timer->biosWrapper || state_.timer->gameSegment!=state_.gameSegment ||
                state_.timer->dataSegment!=static_cast<uint16_t>(state_.gameSegment+0xaa2) ||
                state_.timer->idToggleMask!=state_.idToggleMask)))
            throw std::invalid_argument("Actor finish register/IRQ ownership differs");
    }
    bool flag(uint32_t bit) const { return (state_.registers.flags&bit)!=0; }
    static uint32_t valueFlags(uint16_t value,bool byte=false) {
        return (value==0 ? 0x40u : 0u)|(value&(byte ? 128u : 32768u) ? 0x80u : 0u)|
            (std::popcount(static_cast<uint8_t>(value))%2==0 ? 4u : 0u);
    }
    uint16_t logic(uint16_t value,bool byte=false) {
        value=static_cast<uint16_t>(value&(byte ? 255u : 65535u));
        state_.registers.flags=(state_.registers.flags&~uint32_t{0x8d5})|valueFlags(value,byte);return value;
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
    void instruction(const TimerIrqBus& bus,const CopyBudget& copies) {
        auto& r=state_.registers;
        const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value); };
        const auto pop=[&] { const auto value=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return value; };
        const auto local=[&](int offset) { return bus.readWord(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto lb=[&](int offset) { return bus.readByte(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto store=[&](int offset,uint16_t value) { bus.writeWord(r.ss,static_cast<uint16_t>(r.bp+offset),value); };
        const auto sb=[&](int offset,uint8_t value) { bus.writeByte(r.ss,static_cast<uint16_t>(r.bp+offset),value); };
        const auto les=[&](int offset) { r.di=local(offset);r.es=local(offset+2); };
        const auto read=[&](unsigned offset) { return bus.readWord(r.es,static_cast<uint16_t>(r.di+offset)); };
        const auto byte=[&](unsigned offset) { return bus.readByte(r.es,static_cast<uint16_t>(r.di+offset)); };
        const auto write=[&](unsigned offset,uint16_t value) { bus.writeWord(r.es,static_cast<uint16_t>(r.di+offset),value); };
        const auto wb=[&](unsigned offset,uint8_t value) { bus.writeByte(r.es,static_cast<uint16_t>(r.di+offset),value); };
        const auto data=[&](uint16_t offset) { return bus.readByte(r.ds,offset); };
        const auto dw=[&](uint16_t offset) { return bus.readWord(r.ds,offset); };
        const auto al=[&](uint8_t value) { r.ax=static_cast<uint16_t>((r.ax&0xff00u)|value); };
        const auto bl=[&](uint8_t value) { r.bx=static_cast<uint16_t>((r.bx&0xff00u)|value); };
        const auto bh=[&](uint8_t value) { r.bx=static_cast<uint16_t>((r.bx&255u)|(uint16_t{value}<<8)); };
        const auto dl=[&](uint8_t value) { r.dx=static_cast<uint16_t>((r.dx&0xff00u)|value); };
        const auto zeroAh=[&] { r.ax&=255u;logic(0,true); };
        const auto cbw=[&] { r.ax=static_cast<uint16_t>((r.ax&255u)|((r.ax&128u) ? 0xff00u : 0u)); };
        const auto cwd=[&] { r.dx=(r.ax&0x8000u) ? 0xffff : 0; };
        const auto less=[&] { return flag(0x80)!=flag(0x800); };
        const auto branch=[&](bool condition,uint16_t yes,uint16_t no) { r.ip=condition ? yes : no; };
        const auto nearCall=[&](uint16_t ip,uint16_t next) { push(next);r.ip=ip; };
        const auto farCall=[&](uint16_t ip,uint16_t next) { push(r.cs);push(next);r.cs=library();r.ip=ip; };
        const auto signedMultiply=[&](uint16_t value,int16_t factor) {
            const int32_t product=int32_t{std::bit_cast<int16_t>(value)}*factor;r.di=static_cast<uint16_t>(product);
            r.flags=(r.flags&~uint32_t{0x801})|((product < -32768 || product > 32767) ? 0x801u : 0u);
        };
        const auto multiply=[&](uint16_t value) {
            const uint32_t product=uint32_t{r.ax}*value;r.ax=static_cast<uint16_t>(product);r.dx=static_cast<uint16_t>(product>>16);
            r.flags=(r.flags&~uint32_t{0x841})|(r.dx ? 0x801u : 0u)|(r.ax==0 ? 0x40u : 0u);
        };
        if (r.cs==library()) {
            if (r.ip>=0x90e && r.ip<=0x923) {
                ActorAnimationOperation runtime(ActorAnimationSnapshot{r,state_.gameSegment});
                runtime.advance(1,bus,copies);r=runtime.snapshot().registers;
                state_.transferredBytes+=runtime.snapshot().transferredBytes;
            } else if ((r.ip>=0x13a8 && r.ip<0x13bc) || (r.ip>=0x13f7 && r.ip<=0x142c)) {
                FrameSpawnerOperation runtime(FrameSpawnerSnapshot{r,state_.gameSegment});
                runtime.advance(1,bus);r=runtime.snapshot().registers;
            } else {
                advanceActorReal48Instruction(r,state_.gameSegment,bus);
            }
            return;
        }
        if (r.cs==graphics() || (r.cs==state_.gameSegment &&
                ((r.ip>=0x2f9f && r.ip<0x30a3) || (r.ip>=0x6ab && r.ip<0x709)))) {
            FrameSpawnerOperation callee(FrameSpawnerSnapshot{r,state_.gameSegment});
            callee.advance(1,bus);r=callee.snapshot().registers;return;
        }
        if (r.cs==state_.gameSegment && ((r.ip>=0x5a75 && r.ip<0x5afd) || (r.ip>=0x165a && r.ip<0x167e))) {
            ActorContactOperation callee(ActorContactSnapshot{r,state_.gameSegment,state_.idToggleMask});
            callee.advance(1,bus);r=callee.registers();return;
        }
        if (r.cs!=state_.gameSegment) throw std::domain_error("Actor finish left recovered code");
        switch (r.ip) {
        case 0x73e5:r.ax=local(-14);r.ip=0x73e8;break;
        case 0x73e8:bh(static_cast<uint8_t>(logic(0,true)));r.ip=0x73ea;break;
        case 0x73ea:arithmetic(r.ax,0,true);r.ip=0x73ed;break;
        case 0x73ed:branch(!less(),0x73f1,0x73ef);break;
        case 0x73ef:bh(255);r.ip=0x73f1;break;
        case 0x73f1:bl(lb(-17));r.ip=0x73f4;break;
        case 0x73f4:bl(static_cast<uint8_t>(arithmetic(r.bx&255u,r.ax&255u,false,true)));r.ip=0x73f6;break;
        case 0x73f6:sb(-17,static_cast<uint8_t>(r.bx));r.ip=0x73f9;break;
        case 0x73f9:al(static_cast<uint8_t>(r.ax>>8));r.ip=0x73fb;break;
        case 0x73fb:r.ax=static_cast<uint16_t>((r.ax&255u)|(r.bx&0xff00u));r.ip=0x73fd;break;
        case 0x73fd:store(-46,arithmetic(local(-46),r.ax,false,false,true));r.ip=0x7400;break;
        case 0x7400:r.ax=local(-12);r.ip=0x7403;break;
        case 0x7403:bh(static_cast<uint8_t>(logic(0,true)));r.ip=0x7405;break;
        case 0x7405:arithmetic(r.ax,0,true);r.ip=0x7408;break;
        case 0x7408:branch(!less(),0x740c,0x740a);break;
        case 0x740a:bh(255);r.ip=0x740c;break;
        case 0x740c:bl(lb(-17));r.ip=0x740f;break;
        case 0x740f:bl(lb(-16));r.ip=0x7412;break;
        case 0x7412:bl(static_cast<uint8_t>(arithmetic(r.bx&255u,r.ax&255u,false,true)));r.ip=0x7414;break;
        case 0x7414:sb(-16,static_cast<uint8_t>(r.bx));r.ip=0x7417;break;
        case 0x7417:al(static_cast<uint8_t>(r.ax>>8));r.ip=0x7419;break;
        case 0x7419:r.ax=static_cast<uint16_t>((r.ax&255u)|(r.bx&0xff00u));r.ip=0x741b;break;
        case 0x741b:store(-44,arithmetic(local(-44),r.ax,false,false,true));r.ip=0x741e;break;
        case 0x741e:arithmetic(lb(-15),1,true,true);r.ip=0x7422;break;
        case 0x7422:branch(!flag(1),0x7427,0x7424);break;
        case 0x7424:r.ip=0x7517;break;
        case 0x7427:arithmetic(lb(-15),8,true,true);r.ip=0x742b;break;
        case 0x742b:branch(flag(1)||flag(0x40),0x7430,0x742d);break;
        case 0x742d:r.ip=0x7517;break;
        case 0x7430:arithmetic(lb(-15),31,true,true);r.ip=0x7434;break;
        case 0x7434:branch(!flag(0x40),0x7439,0x7436);break;
        case 0x7436:r.ip=0x7517;break;
        case 0x7439:r.ax=logic(0);r.ip=0x743b;break;
        case 0x743b:bus.writeWord(r.ds,0x2072,r.ax);r.ip=0x743e;break;
        case 0x743e:r.ax=local(-42);r.ip=0x7441;break;
        case 0x7441:r.ax=arithmetic(r.ax,dw(0xc204));r.ip=0x7445;break;
        case 0x7445:r.ax=increment(r.ax);r.ip=0x7446;break;
        case 0x7446:bus.writeWord(r.ds,0x2074,r.ax);r.ip=0x7449;break;
        case 0x7449:bus.writeByte(r.ds,0x208c,1);r.ip=0x744e;break;
        case 0x744e:nearCall(0x56b6,0x7451);break;
        case 0x7451:arithmetic(data(0x661e),0,true,true);r.ip=0x7456;break;
        case 0x7456:branch(!flag(0x40),0x745b,0x7458);break;
        case 0x7458:r.ip=0x7517;break;
        case 0x745b:arithmetic(local(-12),0,true);r.ip=0x745f;break;
        case 0x745f:branch(flag(0x40)||less(),0x7467,0x7461);break;
        case 0x7461:sb(-18,2);r.ip=0x7465;break;
        case 0x7465:r.ip=0x746b;break;
        case 0x7467:sb(-18,1);r.ip=0x746b;break;
        case 0x746b:al(lb(-18));r.ip=0x746e;break;
        case 0x746e:zeroAh();r.ip=0x7470;break;
        case 0x7470:r.dx=r.ax;r.ip=0x7472;break;
        case 0x7472:al(lb(-15));r.ip=0x7475;break;
        case 0x7475:zeroAh();r.ip=0x7477;break;
        case 0x7477:r.di=r.ax;r.ip=0x7479;break;
        case 0x7479:r.di=shift(r.di,1);r.ip=0x747b;break;
        case 0x747b:r.di=arithmetic(r.di,r.dx);r.ip=0x747d;break;
        case 0x747d:al(data(static_cast<uint16_t>(r.di+0x77u)));r.ip=0x7481;break;
        case 0x7481:push(r.ax);r.ip=0x7482;break;
        case 0x7482:push(r.bp);r.ip=0x7483;break;
        case 0x7483:nearCall(0x5a75,0x7486);break;
        case 0x7486:les(4);r.ip=0x7489;break;
        case 0x7489:r.di=arithmetic(r.di,22);r.ip=0x748d;break;
        case 0x748d:store(-58,r.di);r.ip=0x7490;break;
        case 0x7490:store(-56,r.es);r.ip=0x7493;break;
        case 0x7493:les(-58);r.ip=0x7496;break;
        case 0x7496:al(byte(4));r.ip=0x749a;break;
        case 0x749a:zeroAh();r.ip=0x749c;break;
        case 0x749c:r.ax=arithmetic(r.ax,4,true);r.ip=0x749f;break;
        case 0x749f:les(-58);r.ip=0x74a2;break;
        case 0x74a2:wb(3,static_cast<uint8_t>(r.ax));r.ip=0x74a6;break;
        case 0x74a6:al(data(0x661e));r.ip=0x74a9;break;
        case 0x74a9:cbw();r.ip=0x74aa;break;
        case 0x74aa:r.dx=r.ax;r.ip=0x74ac;break;
        case 0x74ac:les(4);r.ip=0x74af;break;
        case 0x74af:al(byte(36));r.ip=0x74b3;break;
        case 0x74b3:zeroAh();r.ip=0x74b5;break;
        case 0x74b5:r.ax=arithmetic(r.ax,r.dx);r.ip=0x74b7;break;
        case 0x74b7:logic(r.ax);r.ip=0x74b9;break;
        case 0x74b9:branch(!less(),0x74ff,0x74bb);break;
        case 0x74bb:les(4);r.ip=0x74be;break;
        case 0x74be:wb(27,0);r.ip=0x74c3;break;
        case 0x74c3:les(4);r.ip=0x74c6;break;
        case 0x74c6:store(-58,r.di);r.ip=0x74c9;break;
        case 0x74c9:store(-56,r.es);r.ip=0x74cc;break;
        case 0x74cc:les(-58);r.ip=0x74cf;break;
        case 0x74cf:wb(21,2);r.ip=0x74d4;break;
        case 0x74d4:les(-58);r.ip=0x74d7;break;
        case 0x74d7:wb(0,12);r.ip=0x74db;break;
        case 0x74db:les(-58);r.ip=0x74de;break;
        case 0x74de:wb(2,25);r.ip=0x74e3;break;
        case 0x74e3:les(-58);r.ip=0x74e6;break;
        case 0x74e6:arithmetic(byte(37),0,true,true);r.ip=0x74eb;break;
        case 0x74eb:branch(flag(1)||flag(0x40),0x74fd,0x74ed);break;
        case 0x74ed:les(-58);r.ip=0x74f0;break;
        case 0x74f0:al(byte(37));r.ip=0x74f4;break;
        case 0x74f4:zeroAh();r.ip=0x74f6;break;
        case 0x74f6:signedMultiply(r.ax,30);r.ip=0x74f9;break;
        case 0x74f9:bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x74b2u),static_cast<uint8_t>(increment(data(static_cast<uint16_t>(r.di+0x74b2u)),false,true)));r.ip=0x74fd;break;
        case 0x74fd:r.ip=0x7517;break;
        case 0x74ff:al(data(0x661e));r.ip=0x7502;break;
        case 0x7502:cbw();r.ip=0x7503;break;
        case 0x7503:r.dx=r.ax;r.ip=0x7505;break;
        case 0x7505:les(4);r.ip=0x7508;break;
        case 0x7508:al(byte(36));r.ip=0x750c;break;
        case 0x750c:zeroAh();r.ip=0x750e;break;
        case 0x750e:r.ax=arithmetic(r.ax,r.dx);r.ip=0x7510;break;
        case 0x7510:les(4);r.ip=0x7513;break;
        case 0x7513:wb(36,static_cast<uint8_t>(r.ax));r.ip=0x7517;break;
        case 0x7517:les(4);r.ip=0x751a;break;
        case 0x751a:al(byte(20));r.ip=0x751e;break;
        case 0x751e:cbw();r.ip=0x751f;break;
        case 0x751f:cwd();r.ip=0x7520;break;
        case 0x7520:r.cx=r.ax;r.ip=0x7522;break;
        case 0x7522:r.bx=r.dx;r.ip=0x7524;break;
        case 0x7524:r.ax=local(-46);r.ip=0x7527;break;
        case 0x7527:r.dx=logic(0);r.ip=0x7529;break;
        case 0x7529:r.ax=arithmetic(r.ax,r.cx);r.ip=0x752b;break;
        case 0x752b:r.dx=arithmetic(r.dx,r.bx,false,false,true);r.ip=0x752d;break;
        case 0x752d:store(-46,r.ax);r.ip=0x7530;break;
        case 0x7530:al(lb(-19));r.ip=0x7533;break;
        case 0x7533:zeroAh();r.ip=0x7535;break;
        case 0x7535:r.di=r.ax;r.ip=0x7537;break;
        case 0x7537:r.di=shift(r.di,3);r.ip=0x753a;break;
        case 0x753a:r.di=arithmetic(r.di,0xc21e);r.ip=0x753e;break;
        case 0x753e:store(-58,r.di);r.ip=0x7541;break;
        case 0x7541:store(-56,r.ds);r.ip=0x7544;break;
        case 0x7544:r.ax=local(-44);r.ip=0x7547;break;
        case 0x7547:les(-58);r.ip=0x754a;break;
        case 0x754a:write(0,r.ax);r.ip=0x754d;break;
        case 0x754d:r.ax=local(-46);r.ip=0x7550;break;
        case 0x7550:les(-58);r.ip=0x7553;break;
        case 0x7553:write(2,r.ax);r.ip=0x7557;break;
        case 0x7557:les(4);r.ip=0x755a;break;
        case 0x755a:store(-58,r.di);r.ip=0x755d;break;
        case 0x755d:store(-56,r.es);r.ip=0x7560;break;
        case 0x7560:al(lb(-16));r.ip=0x7563;break;
        case 0x7563:zeroAh();r.ip=0x7565;break;
        case 0x7565:les(-58);r.ip=0x7568;break;
        case 0x7568:write(10,r.ax);r.ip=0x756c;break;
        case 0x756c:al(lb(-17));r.ip=0x756f;break;
        case 0x756f:zeroAh();r.ip=0x7571;break;
        case 0x7571:les(-58);r.ip=0x7574;break;
        case 0x7574:write(12,r.ax);r.ip=0x7578;break;
        case 0x7578:r.ax=local(-12);r.ip=0x757b;break;
        case 0x757b:les(-58);r.ip=0x757e;break;
        case 0x757e:write(6,r.ax);r.ip=0x7582;break;
        case 0x7582:r.ax=local(-14);r.ip=0x7585;break;
        case 0x7585:les(-58);r.ip=0x7588;break;
        case 0x7588:write(8,r.ax);r.ip=0x758c;break;
        case 0x758c:arithmetic(lb(-15),12,true,true);r.ip=0x7590;break;
        case 0x7590:branch(!flag(1),0x7595,0x7592);break;
        case 0x7592:r.ip=0x777f;break;
        case 0x7595:arithmetic(lb(-49),5,true,true);r.ip=0x7599;break;
        case 0x7599:branch(!flag(0x40),0x759e,0x759b);break;
        case 0x759b:r.ip=0x777f;break;
        case 0x759e:arithmetic(lb(-15),30,true,true);r.ip=0x75a2;break;
        case 0x75a2:branch(flag(1),0x75a7,0x75a4);break;
        case 0x75a4:r.ip=0x777f;break;
        case 0x75a7:r.ax=dw(0x78c2);r.ip=0x75aa;break;
        case 0x75aa:r.ax=logic(r.ax&1u);r.ip=0x75ad;break;
        case 0x75ad:les(4);r.ip=0x75b0;break;
        case 0x75b0:wb(2,static_cast<uint8_t>(arithmetic(byte(2),r.ax&255u,true,true)));r.ip=0x75b4;break;
        case 0x75b4:les(4);r.ip=0x75b7;break;
        case 0x75b7:arithmetic(byte(2),0,true,true);r.ip=0x75bc;break;
        case 0x75bc:branch(flag(0x40),0x75cb,0x75be);break;
        case 0x75be:les(4);r.ip=0x75c1;break;
        case 0x75c1:arithmetic(byte(2),255,true,true);r.ip=0x75c6;break;
        case 0x75c6:branch(flag(0x40),0x75cb,0x75c8);break;
        case 0x75c8:r.ip=0x777f;break;
        case 0x75cb:arithmetic(lb(-15),12,true,true);r.ip=0x75cf;break;
        case 0x75cf:branch(flag(1)||flag(0x40),0x75fe,0x75d1);break;
        case 0x75d1:arithmetic(lb(-15),19,true,true);r.ip=0x75d5;break;
        case 0x75d5:branch(!flag(1),0x75fe,0x75d7);break;
        case 0x75d7:r.ax=local(-46);r.ip=0x75da;break;
        case 0x75da:r.ax=shift(r.ax,3,true);r.ip=0x75dd;break;
        case 0x75dd:multiply(dw(0xc204));r.ip=0x75e1;break;
        case 0x75e1:r.dx=r.ax;r.ip=0x75e3;break;
        case 0x75e3:r.ax=local(-44);r.ip=0x75e6;break;
        case 0x75e6:r.ax=shift(r.ax,3,true);r.ip=0x75e9;break;
        case 0x75e9:r.ax=arithmetic(r.ax,r.dx);r.ip=0x75eb;break;
        case 0x75eb:push(r.ax);r.ip=0x75ec;break;
        case 0x75ec:al(lb(-15));r.ip=0x75ef;break;
        case 0x75ef:zeroAh();r.ip=0x75f1;break;
        case 0x75f1:r.ax=arithmetic(r.ax,12,true);r.ip=0x75f4;break;
        case 0x75f4:r.di=r.ax;r.ip=0x75f6;break;
        case 0x75f6:al(data(static_cast<uint16_t>(r.di+0x31u)));r.ip=0x75fa;break;
        case 0x75fa:push(r.ax);r.ip=0x75fb;break;
        case 0x75fb:nearCall(0x414a,0x75fe);break;
        case 0x75fe:arithmetic(lb(-15),12,true,true);r.ip=0x7602;break;
        case 0x7602:branch(flag(0x40),0x766d,0x7604);break;
        case 0x7604:les(4);r.ip=0x7607;break;
        case 0x7607:store(-58,r.di);r.ip=0x760a;break;
        case 0x760a:store(-56,r.es);r.ip=0x760d;break;
        case 0x760d:les(-58);r.ip=0x7610;break;
        case 0x7610:wb(21,5);r.ip=0x7615;break;
        case 0x7615:les(-58);r.ip=0x7618;break;
        case 0x7618:r.ax=logic(0);r.ip=0x761a;break;
        case 0x761a:write(6,r.ax);r.ip=0x761e;break;
        case 0x761e:les(-58);r.ip=0x7621;break;
        case 0x7621:r.ax=logic(0);r.ip=0x7623;break;
        case 0x7623:write(8,r.ax);r.ip=0x7627;break;
        case 0x7627:les(-58);r.ip=0x762a;break;
        case 0x762a:wb(0,0);r.ip=0x762e;break;
        case 0x762e:les(-58);r.ip=0x7631;break;
        case 0x7631:wb(2,18);r.ip=0x7636;break;
        case 0x7636:arithmetic(lb(-15),19,true,true);r.ip=0x763a;break;
        case 0x763a:branch(!flag(1),0x7644,0x763c);break;
        case 0x763c:al(data(0x6a));r.ip=0x763f;break;
        case 0x763f:sb(-18,static_cast<uint8_t>(r.ax));r.ip=0x7642;break;
        case 0x7642:r.ip=0x764a;break;
        case 0x7644:al(data(0x6c));r.ip=0x7647;break;
        case 0x7647:sb(-18,static_cast<uint8_t>(r.ax));r.ip=0x764a;break;
        case 0x764a:al(lb(-18));r.ip=0x764d;break;
        case 0x764d:push(r.ax);r.ip=0x764e;break;
        case 0x764e:push(r.bp);r.ip=0x764f;break;
        case 0x764f:nearCall(0x5a75,0x7652);break;
        case 0x7652:les(-58);r.ip=0x7655;break;
        case 0x7655:r.di=arithmetic(r.di,22);r.ip=0x7659;break;
        case 0x7659:push(r.es);r.ip=0x765a;break;
        case 0x765a:push(r.di);r.ip=0x765b;break;
        case 0x765b:al(lb(-18));r.ip=0x765e;break;
        case 0x765e:push(r.ax);r.ip=0x765f;break;
        case 0x765f:al(data(0x6d));r.ip=0x7662;break;
        case 0x7662:push(r.ax);r.ip=0x7663;break;
        case 0x7663:push(2);r.ip=0x7665;break;
        case 0x7665:push(1);r.ip=0x7667;break;
        case 0x7667:nearCall(0x6ab,0x766a);break;
        case 0x766a:r.ip=0x76f4;break;
        case 0x766d:push(100);r.ip=0x766f;break;
        case 0x766f:farCall(0x13a8,0x7674);break;
        case 0x7674:bus.writeByte(r.ds,0x79a3,static_cast<uint8_t>(r.ax));r.ip=0x7677;break;
        case 0x7677:push(20);r.ip=0x7679;break;
        case 0x7679:farCall(0x13a8,0x767e);break;
        case 0x767e:r.ax=arithmetic(r.ax,0xea74);r.ip=0x7681;break;
        case 0x7681:bus.writeWord(r.ds,0x2074,r.ax);r.ip=0x7684;break;
        case 0x7684:bus.writeByte(r.ds,0x799f,4);r.ip=0x7689;break;
        case 0x7689:nearCall(0x165a,0x768c);break;
        case 0x768c:al(data(0x79a3));r.ip=0x768f;break;
        case 0x768f:arithmetic(r.ax&255u,data(0x52),true,true);r.ip=0x7693;break;
        case 0x7693:branch(!flag(1),0x769a,0x7695);break;
        case 0x7695:r.ip=0x760d;break;
        case 0x7698:r.ip=0x76b4;break;
        case 0x769a:sb(-18,1);r.ip=0x769e;break;
        case 0x769e:al(lb(-18));r.ip=0x76a1;break;
        case 0x76a1:zeroAh();r.ip=0x76a3;break;
        case 0x76a3:r.di=r.ax;r.ip=0x76a5;break;
        case 0x76a5:al(data(static_cast<uint16_t>(r.di+0x52u)));r.ip=0x76a9;break;
        case 0x76a9:arithmetic(r.ax&255u,data(0x79a3),true,true);r.ip=0x76ad;break;
        case 0x76ad:branch(!flag(1),0x76b4,0x76af);break;
        case 0x76af:sb(-18,static_cast<uint8_t>(increment(lb(-18),false,true)));r.ip=0x76b2;break;
        case 0x76b2:r.ip=0x769e;break;
        case 0x76b4:sb(-18,static_cast<uint8_t>(increment(lb(-18),true,true)));r.ip=0x76b7;break;
        case 0x76b7:al(lb(-18));r.ip=0x76ba;break;
        case 0x76ba:zeroAh();r.ip=0x76bc;break;
        case 0x76bc:r.ax=arithmetic(r.ax,62);r.ip=0x76bf;break;
        case 0x76bf:push(r.ax);r.ip=0x76c0;break;
        case 0x76c0:push(r.bp);r.ip=0x76c1;break;
        case 0x76c1:nearCall(0x5a75,0x76c4);break;
        case 0x76c4:les(4);r.ip=0x76c7;break;
        case 0x76c7:store(-58,r.di);r.ip=0x76ca;break;
        case 0x76ca:store(-56,r.es);r.ip=0x76cd;break;
        case 0x76cd:al(lb(-18));r.ip=0x76d0;break;
        case 0x76d0:zeroAh();r.ip=0x76d2;break;
        case 0x76d2:r.ax=arithmetic(r.ax,19);r.ip=0x76d5;break;
        case 0x76d5:les(-58);r.ip=0x76d8;break;
        case 0x76d8:wb(0,static_cast<uint8_t>(r.ax));r.ip=0x76db;break;
        case 0x76db:les(-58);r.ip=0x76de;break;
        case 0x76de:wb(2,100);r.ip=0x76e3;break;
        case 0x76e3:les(-58);r.ip=0x76e6;break;
        case 0x76e6:wb(27,0);r.ip=0x76eb;break;
        case 0x76eb:les(-58);r.ip=0x76ee;break;
        case 0x76ee:write(8,arithmetic(read(8),200,true));r.ip=0x76f4;break;
        case 0x76f4:arithmetic(lb(-15),19,true,true);r.ip=0x76f8;break;
        case 0x76f8:branch(flag(1),0x76fd,0x76fa);break;
        case 0x76fa:r.ip=0x777f;break;
        case 0x76fd:al(lb(-15));r.ip=0x7700;break;
        case 0x7700:zeroAh();r.ip=0x7702;break;
        case 0x7702:r.ax=arithmetic(r.ax,12,true);r.ip=0x7705;break;
        case 0x7705:sb(-18,static_cast<uint8_t>(r.ax));r.ip=0x7708;break;
        case 0x7708:arithmetic(lb(-18),0,true,true);r.ip=0x770c;break;
        case 0x770c:branch(!flag(1)&&!flag(0x40),0x7712,0x770e);break;
        case 0x770e:sb(-18,1);r.ip=0x7712;break;
        case 0x7712:al(lb(-18));r.ip=0x7715;break;
        case 0x7715:zeroAh();r.ip=0x7717;break;
        case 0x7717:r.ax=increment(r.ax);r.ip=0x7718;break;
        case 0x7718:sb(-55,static_cast<uint8_t>(r.ax));r.ip=0x771b;break;
        case 0x771b:al(1);r.ip=0x771d;break;
        case 0x771d:arithmetic(r.ax&255u,lb(-55),true,true);r.ip=0x7720;break;
        case 0x7720:branch(!flag(1)&&!flag(0x40),0x777f,0x7722);break;
        case 0x7722:sb(-15,static_cast<uint8_t>(r.ax));r.ip=0x7725;break;
        case 0x7725:r.ip=0x772a;break;
        case 0x7727:sb(-15,static_cast<uint8_t>(increment(lb(-15),false,true)));r.ip=0x772a;break;
        case 0x772a:push(local(-44));r.ip=0x772d;break;
        case 0x772d:push(local(-46));r.ip=0x7730;break;
        case 0x7730:push(600);r.ip=0x7733;break;
        case 0x7733:farCall(0x13a8,0x7738);break;
        case 0x7738:r.ax=arithmetic(r.ax,300,true);r.ip=0x773b;break;
        case 0x773b:push(r.ax);r.ip=0x773c;break;
        case 0x773c:push(600);r.ip=0x773f;break;
        case 0x773f:farCall(0x13a8,0x7744);break;
        case 0x7744:r.ax=arithmetic(r.ax,300,true);r.ip=0x7747;break;
        case 0x7747:push(r.ax);r.ip=0x7748;break;
        case 0x7748:push(13);r.ip=0x774a;break;
        case 0x774a:push(11);r.ip=0x774c;break;
        case 0x774c:push(15);r.ip=0x774e;break;
        case 0x774e:push(5);r.ip=0x7750;break;
        case 0x7750:nearCall(0x2f9f,0x7753);break;
        case 0x7753:arithmetic(dw(0x2072),1,true);r.ip=0x7758;break;
        case 0x7758:branch(!flag(0x40),0x7777,0x775a);break;
        case 0x775a:al(data(0x208d));r.ip=0x775d;break;
        case 0x775d:zeroAh();r.ip=0x775f;break;
        case 0x775f:signedMultiply(r.ax,38);r.ip=0x7762;break;
        case 0x7762:r.di=arithmetic(r.di,0x1bc4);r.ip=0x7766;break;
        case 0x7766:push(r.ds);r.ip=0x7767;break;
        case 0x7767:push(r.di);r.ip=0x7768;break;
        case 0x7768:al(data(0x6a));r.ip=0x776b;break;
        case 0x776b:push(r.ax);r.ip=0x776c;break;
        case 0x776c:al(data(0x6d));r.ip=0x776f;break;
        case 0x776f:push(r.ax);r.ip=0x7770;break;
        case 0x7770:push(2);r.ip=0x7772;break;
        case 0x7772:push(2);r.ip=0x7774;break;
        case 0x7774:nearCall(0x6ab,0x7777);break;
        case 0x7777:al(lb(-15));r.ip=0x777a;break;
        case 0x777a:arithmetic(r.ax&255u,lb(-55),true,true);r.ip=0x777d;break;
        case 0x777d:branch(!flag(0x40),0x7727,0x777f);break;
        case 0x777f:r.sp=r.bp;r.bp=pop();r.ip=0x7780;break;
        case 0x7780:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+4u);state_.outcome=ActorFinishOutcome::Returned;break;

        case 0x56b6:bus.writeByte(r.ds,0x661e,0);r.ip=0x56bb;break;
        case 0x56bb:r.cx=4;r.ip=0x56be;break;
        case 0x56be:r.bx=dw(0x2072);r.ip=0x56c2;break;
        case 0x56c2:bus.writeWord(r.ds,0x2072,0);r.ip=0x56c8;break;
        case 0x56c8:r.es=dw(0xc1fe);r.ip=0x56cc;break;
        case 0x56cc:r.di=dw(0x2074);r.ip=0x56d0;break;
        case 0x56d0:al(byte(0));r.ip=0x56d3;break;
        case 0x56d3:arithmetic(r.ax&255u,117,true,true);r.ip=0x56d5;break;
        case 0x56d5:branch(!flag(0x40),0x56e3,0x56d7);break;
        case 0x56d7:bus.writeWord(r.ds,0x2072,r.di);r.ip=0x56db;break;
        case 0x56db:case 0x56df:bus.writeByte(r.ds,0x661e,static_cast<uint8_t>(increment(data(0x661e),true,true)));r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x56e3:arithmetic(r.cx,r.bx,true);r.ip=0x56e5;break;
        case 0x56e5:branch(flag(0x40)||less(),0x56f9,0x56e7);break;
        case 0x56e7:arithmetic(r.ax&255u,1,true,true);r.ip=0x56e9;break;
        case 0x56e9:branch(flag(1),0x56f9,0x56eb);break;
        case 0x56eb:arithmetic(r.ax&255u,76,true,true);r.ip=0x56ed;break;
        case 0x56ed:branch(!flag(1)&&!flag(0x40),0x56f9,0x56ef);break;
        case 0x56ef:al(data(0x661e));r.ip=0x56f2;break;
        case 0x56f2:al(static_cast<uint8_t>(arithmetic(r.ax&255u,data(0x208c),true,true)));r.ip=0x56f6;break;
        case 0x56f6:bus.writeByte(r.ds,0x661e,static_cast<uint8_t>(r.ax));r.ip=0x56f9;break;
        case 0x56f9:arithmetic(r.cx,4,true);r.ip=0x56fc;break;
        case 0x56fc:branch(!flag(0x40),0x5701,0x56fe);break;
        case 0x56fe:r.di=increment(r.di);r.ip=0x56ff;break;
        case 0x56ff:r.ip=0x5712;break;
        case 0x5701:arithmetic(r.cx,3,true);r.ip=0x5704;break;
        case 0x5704:branch(!flag(0x40),0x570c,0x5706);break;
        case 0x5706:r.di=arithmetic(r.di,dw(0xc204));r.ip=0x570a;break;
        case 0x570a:r.ip=0x5712;break;
        case 0x570c:arithmetic(r.cx,2,true);r.ip=0x570f;break;
        case 0x570f:branch(!flag(0x40),0x5712,0x5711);break;
        case 0x5711:r.di=increment(r.di,true);r.ip=0x5712;break;
        case 0x5712:r.cx=static_cast<uint16_t>(r.cx-1u);branch(r.cx!=0,0x56d0,0x5714);break;
        case 0x5714:r.ip=pop();break;

        case 0x495:push(r.bp);r.ip=0x496;break;
        case 0x496:r.bp=r.sp;r.ip=0x498;break;
        case 0x498:r.ax=12;r.ip=0x49b;break;
        case 0x49b:farCall(0x4df,0x4a0);break;
        case 0x4a0:r.sp=arithmetic(r.sp,12,true);r.ip=0x4a3;break;
        case 0x4a3:les(8);r.ip=0x4a6;break;
        case 0x4a6:push(r.es);r.ip=0x4a7;break;
        case 0x4a7:push(r.di);r.ip=0x4a8;break;
        case 0x4a8:r.di=static_cast<uint16_t>(r.bp-4u);r.ip=0x4ab;break;
        case 0x4ab:push(r.ss);r.ip=0x4ac;break;
        case 0x4ac:push(r.di);r.ip=0x4ad;break;
        case 0x4ad:push(3);r.ip=0x4af;break;
        case 0x4af:farCall(0x90e,0x4b4);break;
        case 0x4b4:les(4);r.ip=0x4b7;break;
        case 0x4b7:push(r.es);r.ip=0x4b8;break;
        case 0x4b8:push(r.di);r.ip=0x4b9;break;
        case 0x4b9:r.di=static_cast<uint16_t>(r.bp-8u);r.ip=0x4bc;break;
        case 0x4bc:push(r.ss);r.ip=0x4bd;break;
        case 0x4bd:push(r.di);r.ip=0x4be;break;
        case 0x4be:push(3);r.ip=0x4c0;break;
        case 0x4c0:farCall(0x90e,0x4c5);break;
        case 0x4c5:al(data(0x79cb));r.ip=0x4c8;break;
        case 0x4c8:zeroAh();r.ip=0x4ca;break;
        case 0x4ca:r.ax=increment(r.ax);r.ip=0x4cb;break;
        case 0x4cb:sb(-9,static_cast<uint8_t>(r.ax));r.ip=0x4ce;break;
        case 0x4ce:arithmetic(data(0x79cb),0,true,true);r.ip=0x4d3;break;
        case 0x4d3:branch(flag(1)||flag(0x40),0x508,0x4d5);break;
        case 0x4d5:al(data(0x79cb));r.ip=0x4d8;break;
        case 0x4d8:sb(-11,static_cast<uint8_t>(r.ax));r.ip=0x4db;break;
        case 0x4db:al(1);r.ip=0x4dd;break;
        case 0x4dd:arithmetic(r.ax&255u,lb(-11),true,true);r.ip=0x4e0;break;
        case 0x4e0:branch(!flag(1)&&!flag(0x40),0x508,0x4e2);break;
        case 0x4e2:sb(-10,static_cast<uint8_t>(r.ax));r.ip=0x4e5;break;
        case 0x4e5:r.ip=0x4ea;break;
        case 0x4e7:sb(-10,static_cast<uint8_t>(increment(lb(-10),false,true)));r.ip=0x4ea;break;
        case 0x4ea:al(lb(-10));r.ip=0x4ed;break;
        case 0x4ed:zeroAh();r.ip=0x4ef;break;
        case 0x4ef:r.di=r.ax;r.ip=0x4f1;break;
        case 0x4f1:al(data(static_cast<uint16_t>(r.di+0x79cdu)));r.ip=0x4f5;break;
        case 0x4f5:arithmetic(r.ax&255u,lb(12),true,true);r.ip=0x4f8;break;
        case 0x4f8:branch(!flag(0x40),0x500,0x4fa);break;
        case 0x4fa:al(lb(-10));r.ip=0x4fd;break;
        case 0x4fd:sb(-9,static_cast<uint8_t>(r.ax));r.ip=0x500;break;
        case 0x500:al(lb(-10));r.ip=0x503;break;
        case 0x503:arithmetic(r.ax&255u,lb(-11),true,true);r.ip=0x506;break;
        case 0x506:branch(!flag(0x40),0x4e7,0x508);break;
        case 0x508:arithmetic(lb(-9),3,true,true);r.ip=0x50c;break;
        case 0x50c:branch(!flag(1),0x567,0x50e);break;
        case 0x50e:al(lb(-9));r.ip=0x511;break;
        case 0x511:arithmetic(r.ax&255u,data(0x79cb),true,true);r.ip=0x515;break;
        case 0x515:branch(flag(1)||flag(0x40),0x51b,0x517);break;
        case 0x517:bus.writeByte(r.ds,0x79cb,static_cast<uint8_t>(increment(data(0x79cb),false,true)));r.ip=0x51b;break;
        case 0x51b:dl(lb(12));r.ip=0x51e;break;
        case 0x51e:al(lb(-9));r.ip=0x521;break;
        case 0x521:zeroAh();r.ip=0x523;break;
        case 0x523:r.di=r.ax;r.ip=0x525;break;
        case 0x525:bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x79cdu),static_cast<uint8_t>(r.dx));r.ip=0x529;break;
        case 0x529:r.di=static_cast<uint16_t>(r.bp-4u);r.ip=0x52c;break;
        case 0x52c:push(r.ss);r.ip=0x52d;break;
        case 0x52d:push(r.di);r.ip=0x52e;break;
        case 0x52e:al(lb(-9));r.ip=0x531;break;
        case 0x531:zeroAh();r.ip=0x533;break;
        case 0x533:r.di=r.ax;r.ip=0x535;break;
        case 0x535:r.si=r.di;r.ip=0x537;break;
        case 0x537:r.di=shift(r.di,1);r.ip=0x539;break;
        case 0x539:r.di=arithmetic(r.di,r.si);r.ip=0x53b;break;
        case 0x53b:r.di=arithmetic(r.di,0x79cf);r.ip=0x53f;break;
        case 0x53f:push(r.ds);r.ip=0x540;break;
        case 0x540:push(r.di);r.ip=0x541;break;
        case 0x541:push(3);r.ip=0x543;break;
        case 0x543:farCall(0x90e,0x548);break;
        case 0x548:r.di=static_cast<uint16_t>(r.bp-8u);r.ip=0x54b;break;
        case 0x54b:push(r.ss);r.ip=0x54c;break;
        case 0x54c:push(r.di);r.ip=0x54d;break;
        case 0x54d:al(lb(-9));r.ip=0x550;break;
        case 0x550:zeroAh();r.ip=0x552;break;
        case 0x552:r.di=r.ax;r.ip=0x554;break;
        case 0x554:r.si=r.di;r.ip=0x556;break;
        case 0x556:r.di=shift(r.di,1);r.ip=0x558;break;
        case 0x558:r.di=arithmetic(r.di,r.si);r.ip=0x55a;break;
        case 0x55a:r.di=arithmetic(r.di,0x79d9);r.ip=0x55e;break;
        case 0x55e:push(r.ds);r.ip=0x55f;break;
        case 0x55f:push(r.di);r.ip=0x560;break;
        case 0x560:push(3);r.ip=0x562;break;
        case 0x562:farCall(0x90e,0x567);break;
        case 0x567:r.sp=r.bp;r.bp=pop();r.ip=0x568;break;
        case 0x568:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+10u);break;
        case 0x3fa6:push(r.bp);r.ip=0x3fa7;break;
        case 0x3fa7:r.bp=r.sp;r.ip=0x3fa9;break;
        case 0x3fa9:r.ax=4;r.ip=0x3fac;break;
        case 0x3fac:farCall(0x4df,0x3fb1);break;
        case 0x3fb1:r.sp=arithmetic(r.sp,4,true);r.ip=0x3fb4;break;
        case 0x3fb4:r.ax=local(22);r.ip=0x3fb7;break;
        case 0x3fb7:r.bx=local(24);r.ip=0x3fba;break;
        case 0x3fba:r.dx=local(26);r.ip=0x3fbd;break;
        case 0x3fbd:r.cx=0x89;r.ip=0x3fc0;break;
        case 0x3fc0:r.si=logic(0);r.ip=0x3fc2;break;
        case 0x3fc2:r.di=0x3400;r.ip=0x3fc5;break;
        case 0x3fc5:farCall(0xf01,0x3fca);break;
        case 0x3fca:r.cx=0x5c83;r.ip=0x3fcd;break;
        case 0x3fcd:r.si=0xc28f;r.ip=0x3fd0;break;
        case 0x3fd0:r.di=0x48f5;r.ip=0x3fd3;break;
        case 0x3fd3:farCall(0xefb,0x3fd8);break;
        case 0x3fd8:store(22,r.ax);r.ip=0x3fdb;break;
        case 0x3fdb:store(24,r.bx);r.ip=0x3fde;break;
        case 0x3fde:store(26,r.dx);r.ip=0x3fe1;break;
        case 0x3fe1:r.ax=local(16);r.ip=0x3fe4;break;
        case 0x3fe4:r.bx=local(18);r.ip=0x3fe7;break;
        case 0x3fe7:r.dx=local(20);r.ip=0x3fea;break;
        case 0x3fea:r.cx=0x89;r.ip=0x3fed;break;
        case 0x3fed:r.si=logic(0);r.ip=0x3fef;break;
        case 0x3fef:r.di=0x3400;r.ip=0x3ff2;break;
        case 0x3ff2:farCall(0xf01,0x3ff7);break;
        case 0x3ff7:r.cx=0x5c83;r.ip=0x3ffa;break;
        case 0x3ffa:r.si=0xc28f;r.ip=0x3ffd;break;
        case 0x3ffd:r.di=0x48f5;r.ip=0x4000;break;
        case 0x4000:farCall(0xefb,0x4005);break;
        case 0x4005:store(16,r.ax);r.ip=0x4008;break;
        case 0x4008:store(18,r.bx);r.ip=0x400b;break;
        case 0x400b:store(20,r.dx);r.ip=0x400e;break;
        case 0x400e:r.ax=local(10);r.ip=0x4011;break;
        case 0x4011:r.bx=local(12);r.ip=0x4014;break;
        case 0x4014:r.dx=local(14);r.ip=0x4017;break;
        case 0x4017:r.cx=0x89;r.ip=0x401a;break;
        case 0x401a:r.si=logic(0);r.ip=0x401c;break;
        case 0x401c:r.di=0x3400;r.ip=0x401f;break;
        case 0x401f:farCall(0xf01,0x4024);break;
        case 0x4024:r.cx=0x5c83;r.ip=0x4027;break;
        case 0x4027:r.si=0xc28f;r.ip=0x402a;break;
        case 0x402a:r.di=0x48f5;r.ip=0x402d;break;
        case 0x402d:farCall(0xefb,0x4032);break;
        case 0x4032:store(10,r.ax);r.ip=0x4035;break;
        case 0x4035:store(12,r.bx);r.ip=0x4038;break;
        case 0x4038:store(14,r.dx);r.ip=0x403b;break;
        case 0x403b:arithmetic(dw(0x2076),198,true);r.ip=0x4041;break;
        case 0x4041:branch(flag(1),0x4046,0x4043);break;
        case 0x4043:r.ip=0x410a;break;
        case 0x4046:bus.writeWord(r.ds,0x2076,increment(dw(0x2076)));r.ip=0x404a;break;
        case 0x404a:al(lb(8));r.ip=0x404d;break;
        case 0x404d:r.di=dw(0x2076);r.ip=0x4051;break;
        case 0x4051:bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x78d5u),static_cast<uint8_t>(r.ax));r.ip=0x4055;break;
        case 0x4055:signedMultiply(dw(0x2076),11);r.ip=0x405a;break;
        case 0x405a:r.di=arithmetic(r.di,0x2093);r.ip=0x405e;break;
        case 0x405e:store(-4,r.di);r.ip=0x4061;break;
        case 0x4061:store(-2,r.ds);r.ip=0x4064;break;
        case 0x4064:r.ax=local(28);r.ip=0x4067;break;
        case 0x4067:les(-4);r.ip=0x406a;break;
        case 0x406a:write(0,r.ax);r.ip=0x406d;break;
        case 0x406d:al(lb(6));r.ip=0x4070;break;
        case 0x4070:zeroAh();r.ip=0x4072;break;
        case 0x4072:r.dx=logic(0);r.ip=0x4074;break;
        case 0x4074:farCall(0xf0f,0x4079);break;
        case 0x4079:push(r.dx);r.ip=0x407a;break;
        case 0x407a:push(r.bx);r.ip=0x407b;break;
        case 0x407b:push(r.ax);r.ip=0x407c;break;
        case 0x407c:r.ax=local(22);r.ip=0x407f;break;
        case 0x407f:r.bx=local(24);r.ip=0x4082;break;
        case 0x4082:r.dx=local(26);r.ip=0x4085;break;
        case 0x4085:farCall(0x1021,0x408a);break;
        case 0x408a:r.cx=pop();r.ip=0x408b;break;
        case 0x408b:r.si=pop();r.ip=0x408c;break;
        case 0x408c:r.di=pop();r.ip=0x408d;break;
        case 0x408d:farCall(0xefb,0x4092);break;
        case 0x4092:farCall(0xf13,0x4097);break;
        case 0x4097:les(-4);r.ip=0x409a;break;
        case 0x409a:wb(4,static_cast<uint8_t>(r.ax));r.ip=0x409e;break;
        case 0x409e:al(lb(6));r.ip=0x40a1;break;
        case 0x40a1:zeroAh();r.ip=0x40a3;break;
        case 0x40a3:r.dx=logic(0);r.ip=0x40a5;break;
        case 0x40a5:farCall(0xf0f,0x40aa);break;
        case 0x40aa:push(r.dx);r.ip=0x40ab;break;
        case 0x40ab:push(r.bx);r.ip=0x40ac;break;
        case 0x40ac:push(r.ax);r.ip=0x40ad;break;
        case 0x40ad:r.ax=local(22);r.ip=0x40b0;break;
        case 0x40b0:r.bx=local(24);r.ip=0x40b3;break;
        case 0x40b3:r.dx=local(26);r.ip=0x40b6;break;
        case 0x40b6:farCall(0x1034,0x40bb);break;
        case 0x40bb:r.cx=pop();r.ip=0x40bc;break;
        case 0x40bc:r.si=pop();r.ip=0x40bd;break;
        case 0x40bd:r.di=pop();r.ip=0x40be;break;
        case 0x40be:farCall(0xefb,0x40c3);break;
        case 0x40c3:farCall(0xf13,0x40c8);break;
        case 0x40c8:r.ax=arithmetic(0,r.ax,true);r.ip=0x40ca;break;
        case 0x40ca:r.dx=arithmetic(r.dx,0,false,false,true);r.ip=0x40cd;break;
        case 0x40cd:r.dx=arithmetic(0,r.dx,true);r.ip=0x40cf;break;
        case 0x40cf:les(-4);r.ip=0x40d2;break;
        case 0x40d2:wb(5,static_cast<uint8_t>(r.ax));r.ip=0x40d6;break;
        case 0x40d6:les(-4);r.ip=0x40d9;break;
        case 0x40d9:wb(6,0);r.ip=0x40de;break;
        case 0x40de:les(-4);r.ip=0x40e1;break;
        case 0x40e1:wb(7,0);r.ip=0x40e6;break;
        case 0x40e6:les(-4);r.ip=0x40e9;break;
        case 0x40e9:wb(9,117);r.ip=0x40ee;break;
        case 0x40ee:r.di=local(4);r.ip=0x40f1;break;
        case 0x40f1:al(bus.readByte(r.ss,static_cast<uint16_t>(r.di-3u)));r.ip=0x40f5;break;
        case 0x40f5:les(-4);r.ip=0x40f8;break;
        case 0x40f8:wb(8,static_cast<uint8_t>(r.ax));r.ip=0x40fc;break;
        case 0x40fc:r.di=local(4);r.ip=0x40ff;break;
        case 0x40ff:al(bus.readByte(r.ss,static_cast<uint16_t>(r.di-4u)));r.ip=0x4103;break;
        case 0x4103:les(-4);r.ip=0x4106;break;
        case 0x4106:wb(10,static_cast<uint8_t>(r.ax));r.ip=0x410a;break;
        case 0x410a:r.ax=local(22);r.ip=0x410d;break;
        case 0x410d:r.bx=local(24);r.ip=0x4110;break;
        case 0x4110:r.dx=local(26);r.ip=0x4113;break;
        case 0x4113:r.cx=local(10);r.ip=0x4116;break;
        case 0x4116:r.si=local(12);r.ip=0x4119;break;
        case 0x4119:r.di=local(14);r.ip=0x411c;break;
        case 0x411c:farCall(0xee9,0x4121);break;
        case 0x4121:store(22,r.ax);r.ip=0x4124;break;
        case 0x4124:store(24,r.bx);r.ip=0x4127;break;
        case 0x4127:store(26,r.dx);r.ip=0x412a;break;
        case 0x412a:r.ax=local(22);r.ip=0x412d;break;
        case 0x412d:r.bx=local(24);r.ip=0x4130;break;
        case 0x4130:r.dx=local(26);r.ip=0x4133;break;
        case 0x4133:r.cx=local(16);r.ip=0x4136;break;
        case 0x4136:r.si=local(18);r.ip=0x4139;break;
        case 0x4139:r.di=local(20);r.ip=0x413c;break;
        case 0x413c:farCall(0xf0b,0x4141);break;
        case 0x4141:branch(!flag(1)&&!flag(0x40),0x4146,0x4143);break;
        case 0x4143:r.ip=0x403b;break;
        case 0x4146:r.sp=r.bp;r.bp=pop();r.ip=0x4147;break;
        case 0x4147:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+26u);break;
        case 0x414a:push(r.bp);r.ip=0x414b;break;
        case 0x414b:r.bp=r.sp;r.ip=0x414d;break;
        case 0x414d:r.ax=4;r.ip=0x4150;break;
        case 0x4150:farCall(0x4df,0x4155);break;
        case 0x4155:r.sp=arithmetic(r.sp,4,true);r.ip=0x4158;break;
        case 0x4158:r.ax=local(6);r.ip=0x415b;break;
        case 0x415b:store(-2,r.ax);r.ip=0x415e;break;
        case 0x415e:arithmetic(lb(4),1,true,true);r.ip=0x4162;break;
        case 0x4162:branch(flag(1)||flag(0x40),0x4170,0x4164);break;
        case 0x4164:bus.writeWord(r.ds,0x209a,2);r.ip=0x416a;break;
        case 0x416a:bus.writeWord(r.ds,0x209c,1);r.ip=0x4170;break;
        case 0x4170:al(lb(4));r.ip=0x4173;break;
        case 0x4173:arithmetic(r.ax&255u,1,true,true);r.ip=0x4175;break;
        case 0x4175:branch(!flag(0x40),0x41b7,0x4177);break;
        case 0x4177:sb(-3,8);r.ip=0x417b;break;
        case 0x417b:sb(-4,5);r.ip=0x417f;break;
        case 0x417f:push(local(-2));r.ip=0x4182;break;
        case 0x4182:r.ax=logic(0);r.ip=0x4184;break;
        case 0x4184:r.bx=logic(0);r.ip=0x4186;break;
        case 0x4186:r.dx=logic(0);r.ip=0x4188;break;
        case 0x4188:push(r.dx);r.ip=0x4189;break;
        case 0x4189:push(r.bx);r.ip=0x418a;break;
        case 0x418a:push(r.ax);r.ip=0x418b;break;
        case 0x418b:r.ax=0x89;r.ip=0x418e;break;
        case 0x418e:r.bx=logic(0);r.ip=0x4190;break;
        case 0x4190:r.dx=0x2a00;r.ip=0x4193;break;
        case 0x4193:push(r.dx);r.ip=0x4194;break;
        case 0x4194:push(r.bx);r.ip=0x4195;break;
        case 0x4195:push(r.ax);r.ip=0x4196;break;
        case 0x4196:r.ax=0x86;r.ip=0x4199;break;
        case 0x4199:r.bx=logic(0);r.ip=0x419b;break;
        case 0x419b:r.dx=0x3400;r.ip=0x419e;break;
        case 0x419e:push(r.dx);r.ip=0x419f;break;
        case 0x419f:push(r.bx);r.ip=0x41a0;break;
        case 0x41a0:push(r.ax);r.ip=0x41a1;break;
        case 0x41a1:push(1);r.ip=0x41a3;break;
        case 0x41a3:push(80);r.ip=0x41a5;break;
        case 0x41a5:push(r.bp);r.ip=0x41a6;break;
        case 0x41a6:nearCall(0x3fa6,0x41a9);break;
        case 0x41a9:bus.writeWord(r.ds,0x2074,0xea74);r.ip=0x41af;break;
        case 0x41af:bus.writeByte(r.ds,0x799f,4);r.ip=0x41b4;break;
        case 0x41b4:r.ip=0x4323;break;
        case 0x41b7:arithmetic(r.ax&255u,2,true,true);r.ip=0x41b9;break;
        case 0x41b9:branch(!flag(0x40),0x41fb,0x41bb);break;
        case 0x41bb:sb(-3,9);r.ip=0x41bf;break;
        case 0x41bf:sb(-4,5);r.ip=0x41c3;break;
        case 0x41c3:push(local(-2));r.ip=0x41c6;break;
        case 0x41c6:r.ax=logic(0);r.ip=0x41c8;break;
        case 0x41c8:r.bx=logic(0);r.ip=0x41ca;break;
        case 0x41ca:r.dx=logic(0);r.ip=0x41cc;break;
        case 0x41cc:push(r.dx);r.ip=0x41cd;break;
        case 0x41cd:push(r.bx);r.ip=0x41ce;break;
        case 0x41ce:push(r.ax);r.ip=0x41cf;break;
        case 0x41cf:r.ax=0x89;r.ip=0x41d2;break;
        case 0x41d2:r.bx=logic(0);r.ip=0x41d4;break;
        case 0x41d4:r.dx=0x3280;r.ip=0x41d7;break;
        case 0x41d7:push(r.dx);r.ip=0x41d8;break;
        case 0x41d8:push(r.bx);r.ip=0x41d9;break;
        case 0x41d9:push(r.ax);r.ip=0x41da;break;
        case 0x41da:r.ax=0x85;r.ip=0x41dd;break;
        case 0x41dd:r.bx=logic(0);r.ip=0x41df;break;
        case 0x41df:r.dx=0x7000;r.ip=0x41e2;break;
        case 0x41e2:push(r.dx);r.ip=0x41e3;break;
        case 0x41e3:push(r.bx);r.ip=0x41e4;break;
        case 0x41e4:push(r.ax);r.ip=0x41e5;break;
        case 0x41e5:push(1);r.ip=0x41e7;break;
        case 0x41e7:push(110);r.ip=0x41e9;break;
        case 0x41e9:push(r.bp);r.ip=0x41ea;break;
        case 0x41ea:nearCall(0x3fa6,0x41ed);break;
        case 0x41ed:bus.writeWord(r.ds,0x2074,0xea7e);r.ip=0x41f3;break;
        case 0x41f3:bus.writeByte(r.ds,0x799f,5);r.ip=0x41f8;break;
        case 0x41f8:r.ip=0x4323;break;
        case 0x41fb:arithmetic(r.ax&255u,3,true,true);r.ip=0x41fd;break;
        case 0x41fd:branch(!flag(0x40),0x423f,0x41ff);break;
        case 0x41ff:sb(-3,9);r.ip=0x4203;break;
        case 0x4203:sb(-4,3);r.ip=0x4207;break;
        case 0x4207:push(local(-2));r.ip=0x420a;break;
        case 0x420a:r.ax=logic(0);r.ip=0x420c;break;
        case 0x420c:r.bx=logic(0);r.ip=0x420e;break;
        case 0x420e:r.dx=logic(0);r.ip=0x4210;break;
        case 0x4210:push(r.dx);r.ip=0x4211;break;
        case 0x4211:push(r.bx);r.ip=0x4212;break;
        case 0x4212:push(r.ax);r.ip=0x4213;break;
        case 0x4213:r.ax=0x89;r.ip=0x4216;break;
        case 0x4216:r.bx=logic(0);r.ip=0x4218;break;
        case 0x4218:r.dx=0x3280;r.ip=0x421b;break;
        case 0x421b:push(r.dx);r.ip=0x421c;break;
        case 0x421c:push(r.bx);r.ip=0x421d;break;
        case 0x421d:push(r.ax);r.ip=0x421e;break;
        case 0x421e:r.ax=0x85;r.ip=0x4221;break;
        case 0x4221:r.bx=logic(0);r.ip=0x4223;break;
        case 0x4223:r.dx=0x3000;r.ip=0x4226;break;
        case 0x4226:push(r.dx);r.ip=0x4227;break;
        case 0x4227:push(r.bx);r.ip=0x4228;break;
        case 0x4228:push(r.ax);r.ip=0x4229;break;
        case 0x4229:push(9);r.ip=0x422b;break;
        case 0x422b:push(110);r.ip=0x422d;break;
        case 0x422d:push(r.bp);r.ip=0x422e;break;
        case 0x422e:nearCall(0x3fa6,0x4231);break;
        case 0x4231:bus.writeWord(r.ds,0x2074,0xea88);r.ip=0x4237;break;
        case 0x4237:bus.writeByte(r.ds,0x799f,6);r.ip=0x423c;break;
        case 0x423c:r.ip=0x4323;break;
        case 0x423f:arithmetic(r.ax&255u,4,true,true);r.ip=0x4241;break;
        case 0x4241:branch(flag(0x40),0x4246,0x4243);break;
        case 0x4243:r.ip=0x4323;break;
        case 0x4246:sb(-3,58);r.ip=0x424a;break;
        case 0x424a:sb(-4,10);r.ip=0x424e;break;
        case 0x424e:push(0);r.ip=0x4250;break;
        case 0x4250:r.di=0x1ab6;r.ip=0x4253;break;
        case 0x4253:push(r.ds);r.ip=0x4254;break;
        case 0x4254:push(r.di);r.ip=0x4255;break;
        case 0x4255:r.di=0x1aba;r.ip=0x4258;break;
        case 0x4258:push(r.ds);r.ip=0x4259;break;
        case 0x4259:push(r.di);r.ip=0x425a;break;
        case 0x425a:nearCall(0x495,0x425d);break;
        case 0x425d:push(local(-2));r.ip=0x4260;break;
        case 0x4260:r.ax=0x87;r.ip=0x4263;break;
        case 0x4263:r.bx=logic(0);r.ip=0x4265;break;
        case 0x4265:r.dx=0x3400;r.ip=0x4268;break;
        case 0x4268:push(r.dx);r.ip=0x4269;break;
        case 0x4269:push(r.bx);r.ip=0x426a;break;
        case 0x426a:push(r.ax);r.ip=0x426b;break;
        case 0x426b:r.ax=0x88;r.ip=0x426e;break;
        case 0x426e:r.bx=logic(0);r.ip=0x4270;break;
        case 0x4270:r.dx=0x3400;r.ip=0x4273;break;
        case 0x4273:push(r.dx);r.ip=0x4274;break;
        case 0x4274:push(r.bx);r.ip=0x4275;break;
        case 0x4275:push(r.ax);r.ip=0x4276;break;
        case 0x4276:r.ax=0x84;r.ip=0x4279;break;
        case 0x4279:r.bx=logic(0);r.ip=0x427b;break;
        case 0x427b:r.dx=0x7000;r.ip=0x427e;break;
        case 0x427e:push(r.dx);r.ip=0x427f;break;
        case 0x427f:push(r.bx);r.ip=0x4280;break;
        case 0x4280:push(r.ax);r.ip=0x4281;break;
        case 0x4281:push(0xffdd);r.ip=0x4283;break;
        case 0x4283:push(126);r.ip=0x4285;break;
        case 0x4285:push(r.bp);r.ip=0x4286;break;
        case 0x4286:nearCall(0x3fa6,0x4289);break;
        case 0x4289:r.ax=local(-2);r.ip=0x428c;break;
        case 0x428c:r.ax=increment(r.ax);r.ip=0x428d;break;
        case 0x428d:push(r.ax);r.ip=0x428e;break;
        case 0x428e:r.ax=logic(0);r.ip=0x4290;break;
        case 0x4290:r.bx=logic(0);r.ip=0x4292;break;
        case 0x4292:r.dx=logic(0);r.ip=0x4294;break;
        case 0x4294:push(r.dx);r.ip=0x4295;break;
        case 0x4295:push(r.bx);r.ip=0x4296;break;
        case 0x4296:push(r.ax);r.ip=0x4297;break;
        case 0x4297:r.ax=0x87;r.ip=0x429a;break;
        case 0x429a:r.bx=logic(0);r.ip=0x429c;break;
        case 0x429c:r.dx=0x3400;r.ip=0x429f;break;
        case 0x429f:push(r.dx);r.ip=0x42a0;break;
        case 0x42a0:push(r.bx);r.ip=0x42a1;break;
        case 0x42a1:push(r.ax);r.ip=0x42a2;break;
        case 0x42a2:r.ax=0x84;r.ip=0x42a5;break;
        case 0x42a5:r.bx=logic(0);r.ip=0x42a7;break;
        case 0x42a7:r.dx=0x7000;r.ip=0x42aa;break;
        case 0x42aa:push(r.dx);r.ip=0x42ab;break;
        case 0x42ab:push(r.bx);r.ip=0x42ac;break;
        case 0x42ac:push(r.ax);r.ip=0x42ad;break;
        case 0x42ad:push(0xffdd);r.ip=0x42af;break;
        case 0x42af:push(126);r.ip=0x42b1;break;
        case 0x42b1:push(r.bp);r.ip=0x42b2;break;
        case 0x42b2:nearCall(0x3fa6,0x42b5);break;
        case 0x42b5:r.ax=local(-2);r.ip=0x42b8;break;
        case 0x42b8:r.ax=arithmetic(r.ax,dw(0xc204));r.ip=0x42bc;break;
        case 0x42bc:push(r.ax);r.ip=0x42bd;break;
        case 0x42bd:r.ax=0x88;r.ip=0x42c0;break;
        case 0x42c0:r.bx=logic(0);r.ip=0x42c2;break;
        case 0x42c2:r.dx=0x3400;r.ip=0x42c5;break;
        case 0x42c5:push(r.dx);r.ip=0x42c6;break;
        case 0x42c6:push(r.bx);r.ip=0x42c7;break;
        case 0x42c7:push(r.ax);r.ip=0x42c8;break;
        case 0x42c8:r.ax=0x89;r.ip=0x42cb;break;
        case 0x42cb:r.bx=logic(0);r.ip=0x42cd;break;
        case 0x42cd:r.dx=0x700;r.ip=0x42d0;break;
        case 0x42d0:push(r.dx);r.ip=0x42d1;break;
        case 0x42d1:push(r.bx);r.ip=0x42d2;break;
        case 0x42d2:push(r.ax);r.ip=0x42d3;break;
        case 0x42d3:r.ax=0x84;r.ip=0x42d6;break;
        case 0x42d6:r.bx=logic(0);r.ip=0x42d8;break;
        case 0x42d8:r.dx=0x7000;r.ip=0x42db;break;
        case 0x42db:push(r.dx);r.ip=0x42dc;break;
        case 0x42dc:push(r.bx);r.ip=0x42dd;break;
        case 0x42dd:push(r.ax);r.ip=0x42de;break;
        case 0x42de:push(0xffdd);r.ip=0x42e0;break;
        case 0x42e0:push(126);r.ip=0x42e2;break;
        case 0x42e2:push(r.bp);r.ip=0x42e3;break;
        case 0x42e3:nearCall(0x3fa6,0x42e6);break;
        case 0x42e6:r.ax=local(-2);r.ip=0x42e9;break;
        case 0x42e9:r.ax=arithmetic(r.ax,dw(0xc204));r.ip=0x42ed;break;
        case 0x42ed:r.ax=increment(r.ax);r.ip=0x42ee;break;
        case 0x42ee:push(r.ax);r.ip=0x42ef;break;
        case 0x42ef:r.ax=0x89;r.ip=0x42f2;break;
        case 0x42f2:r.bx=logic(0);r.ip=0x42f4;break;
        case 0x42f4:r.dx=0xc00;r.ip=0x42f7;break;
        case 0x42f7:push(r.dx);r.ip=0x42f8;break;
        case 0x42f8:push(r.bx);r.ip=0x42f9;break;
        case 0x42f9:push(r.ax);r.ip=0x42fa;break;
        case 0x42fa:r.ax=0x89;r.ip=0x42fd;break;
        case 0x42fd:r.bx=logic(0);r.ip=0x42ff;break;
        case 0x42ff:r.dx=0x3400;r.ip=0x4302;break;
        case 0x4302:push(r.dx);r.ip=0x4303;break;
        case 0x4303:push(r.bx);r.ip=0x4304;break;
        case 0x4304:push(r.ax);r.ip=0x4305;break;
        case 0x4305:r.ax=0x84;r.ip=0x4308;break;
        case 0x4308:r.bx=logic(0);r.ip=0x430a;break;
        case 0x430a:r.dx=0x7000;r.ip=0x430d;break;
        case 0x430d:push(r.dx);r.ip=0x430e;break;
        case 0x430e:push(r.bx);r.ip=0x430f;break;
        case 0x430f:push(r.ax);r.ip=0x4310;break;
        case 0x4310:push(0xffdd);r.ip=0x4312;break;
        case 0x4312:push(126);r.ip=0x4314;break;
        case 0x4314:push(r.bp);r.ip=0x4315;break;
        case 0x4315:nearCall(0x3fa6,0x4318);break;
        case 0x4318:bus.writeByte(r.ds,0x799f,7);r.ip=0x431d;break;
        case 0x431d:bus.writeWord(r.ds,0x2074,0xeace);r.ip=0x4323;break;
        case 0x4323:nearCall(0x165a,0x4326);break;
        case 0x4326:r.sp=r.bp;r.bp=pop();r.ip=0x4327;break;
        case 0x4327:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+4u);break;
        default:throw std::domain_error("Actor finish reached an unrecovered instruction");
        }
    }
};

enum class FrameActorFinishOutcome { Running, TileBehavior, ActorReturned, TransientQueues, Restart, EndRunUi, RuntimeError, BreakOutput };
using FrameActorFinishCallee=std::variant<FrameActorContactSnapshot,ActorFinishSnapshot>;
struct FrameActorFinishSnapshot {
    FrameActorFinishCallee callee;
    uint16_t gameSegment=0;
    uint32_t idToggleMask=0;
    uint64_t dispatchedInstructions=0,prefixTimerInstructions=0,prefixTimerDeliveries=0;
    FrameActorFinishOutcome outcome=FrameActorFinishOutcome::Running;
    bool operator==(const FrameActorFinishSnapshot&) const = default;
};

class FrameActorFinishOperation {
public:
    using CopyBudget=ActorFinishOperation::CopyBudget;
    FrameActorFinishOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        : state_{r.ip==0x73e5 ? FrameActorFinishCallee{ActorFinishOperation(r,game,idToggle).snapshot()} :
            FrameActorFinishCallee{FrameActorContactOperation(r,game,idToggle).snapshot()},game,idToggle} { validate(); }
    FrameActorFinishOperation(DosGetTimeRegisters r,uint16_t dos,uint16_t keyboard,uint16_t psp,uint16_t game,uint32_t idToggle)
        : state_{FrameActorContactOperation(r,dos,keyboard,psp,game,idToggle).snapshot(),game,idToggle} { validate(); }
    explicit FrameActorFinishOperation(FrameActorFinishSnapshot state) : state_(state) { validate(); }
    const FrameActorFinishSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const {
        return std::visit([](const auto& child) -> DosGetTimeRegisters {
            using Child=std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child,FrameActorContactSnapshot>) return FrameActorContactOperation(child).registers();
            else return ActorFinishOperation(child).registers();
        },state_.callee);
    }
    bool finished() const noexcept { return state_.outcome!=FrameActorFinishOutcome::Running; }
    bool interruptInProgress() const {
        return std::visit([](const auto& child) {
            using Child=std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child,FrameActorContactSnapshot>) return FrameActorContactOperation(child).interruptInProgress();
            else return ActorFinishOperation(child).interruptInProgress();
        },state_.callee);
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished frame actor tail admitted IRQ");
        std::visit([&](auto& child) {
            using Child=std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child,FrameActorContactSnapshot>) {
                FrameActorContactOperation operation(child);operation.deliverTimerInterrupt(bus);child=operation.snapshot();savePrefixTimers(child);
            } else {
                ActorFinishOperation operation(child);operation.deliverTimerInterrupt(bus);child=operation.snapshot();
            }
        },state_.callee);
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            std::optional<DosGetTimeRegisters> next;
            std::visit([&](auto& child) {
                using Child=std::remove_cvref_t<decltype(child)>;
                if constexpr (std::is_same_v<Child,FrameActorContactSnapshot>) {
                    FrameActorContactOperation operation(child);
                    if (operation.advance(1,bus,copies)!=1) throw std::domain_error("Actor contact did not dispatch");
                    child=operation.snapshot();savePrefixTimers(child);
                    if (operation.finished()) {
                        switch (child.outcome) {
                        case FrameActorContactOutcome::MotionIntegration:next=operation.registers();break;
                        case FrameActorContactOutcome::TileBehavior:state_.outcome=FrameActorFinishOutcome::TileBehavior;break;
                        case FrameActorContactOutcome::TransientQueues:state_.outcome=FrameActorFinishOutcome::TransientQueues;break;
                        case FrameActorContactOutcome::Restart:state_.outcome=FrameActorFinishOutcome::Restart;break;
                        case FrameActorContactOutcome::EndRunUi:state_.outcome=FrameActorFinishOutcome::EndRunUi;break;
                        case FrameActorContactOutcome::RuntimeError:state_.outcome=FrameActorFinishOutcome::RuntimeError;break;
                        case FrameActorContactOutcome::BreakOutput:state_.outcome=FrameActorFinishOutcome::BreakOutput;break;
                        default:throw std::logic_error("Finished actor contact has no outcome");
                        }
                    }
                } else {
                    ActorFinishOperation operation(child);
                    if (operation.advance(1,bus,copies)!=1) throw std::domain_error("Actor finish did not dispatch");
                    child=operation.snapshot();
                    if (operation.finished()) state_.outcome=child.outcome==ActorFinishOutcome::Returned ?
                        FrameActorFinishOutcome::ActorReturned : FrameActorFinishOutcome::RuntimeError;
                }
            },state_.callee);
            if (next) state_.callee=ActorFinishOperation(*next,state_.gameSegment,state_.idToggleMask).snapshot();
            ++used;++state_.dispatchedInstructions;
        }
        return used;
    }
private:
    FrameActorFinishSnapshot state_;
    void validate() const {
        if ((state_.idToggleMask!=0 && state_.idToggleMask!=0x200000) ||
            !std::visit([&](const auto& child) { return child.gameSegment==state_.gameSegment && child.idToggleMask==state_.idToggleMask; },state_.callee))
            throw std::invalid_argument("Frame actor finish ID-toggle/callee ownership differs");
    }
    void savePrefixTimers(const FrameActorContactSnapshot& prefix) {
        state_.prefixTimerInstructions=prefix.prefixTimerInstructions;state_.prefixTimerDeliveries=prefix.prefixTimerDeliveries;
        if (const auto* contact=std::get_if<ActorContactSnapshot>(&prefix.callee)) {
            state_.prefixTimerInstructions+=contact->timerInstructions;state_.prefixTimerDeliveries+=contact->timerDeliveries;
        }
    }
};

} // namespace lezac::core
