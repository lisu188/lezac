#pragma once

#include "core/actor_finish.hpp"

namespace lezac::core {

enum class ActorExpiryOutcome { Running, MotionIntegration, Returned, RuntimeError };
struct ActorExpirySnapshot {
    ActorFinishSnapshot cpu;
    ActorExpiryOutcome outcome=ActorExpiryOutcome::Running;
    bool operator==(const ActorExpirySnapshot&) const = default;
};

// Behavior-5 countdown, real physical/visual compaction, and actor near return.
// Share the established CPU/IRQ context, but never execute the common motion tail.
class ActorExpiryOperation {
public:
    using CopyBudget=ActorFinishOperation::CopyBudget;
    ActorExpiryOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        : state_{ActorFinishSnapshot{r,game,idToggle}} {
        if (r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2) || r.ip!=0x65a8)
            throw std::invalid_argument("Actor expiry entry differs");
        validate();
    }
    explicit ActorExpiryOperation(ActorExpirySnapshot state) : state_(state) { validate(); }
    const ActorExpirySnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const { return ActorFinishOperation(state_.cpu).registers(); }
    bool finished() const noexcept { return state_.outcome!=ActorExpiryOutcome::Running; }
    bool interruptInProgress() const noexcept { return state_.cpu.timer.has_value(); }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished actor expiry admitted IRQ");
        ActorFinishOperation irq(state_.cpu);irq.deliverTimerInterrupt(bus);state_.cpu=irq.snapshot();
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (state_.cpu.timer) {
                ActorFinishOperation irq(state_.cpu);
                if (irq.advance(1,bus,copies)!=1) throw std::domain_error("Actor expiry IRQ did not dispatch");
                state_.cpu=irq.snapshot();
            } else {
                instruction(bus,copies);++state_.cpu.dispatchedInstructions;
                const auto& r=state_.cpu.registers;
                if (r.cs==state_.cpu.gameSegment && r.ip==0x73e5) state_.outcome=ActorExpiryOutcome::MotionIntegration;
                if (r.cs==library() && r.ip==0xe2) state_.outcome=ActorExpiryOutcome::RuntimeError;
            }
            ++used;
        }
        return used;
    }
private:
    ActorExpirySnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.cpu.gameSegment+0x920); }
    uint16_t graphics() const { return static_cast<uint16_t>(state_.cpu.gameSegment+0x8ac); }
    void validate() const {
        (void)ActorFinishOperation(state_.cpu);
        const auto& r=state_.cpu.registers;
        if (state_.cpu.outcome!=ActorFinishOutcome::Running ||
            (finished() && state_.cpu.timer) ||
            (state_.outcome==ActorExpiryOutcome::MotionIntegration && (r.cs!=state_.cpu.gameSegment || r.ip!=0x73e5)) ||
            (state_.outcome==ActorExpiryOutcome::RuntimeError && (r.cs!=library() || r.ip!=0xe2)) ||
            (state_.outcome!=ActorExpiryOutcome::Running && state_.outcome!=ActorExpiryOutcome::MotionIntegration &&
                state_.outcome!=ActorExpiryOutcome::Returned && state_.outcome!=ActorExpiryOutcome::RuntimeError))
            throw std::invalid_argument("Actor expiry CPU/outcome ownership differs");
    }
    bool flag(uint32_t bit) const { return (state_.cpu.registers.flags&bit)!=0; }
    static uint32_t valueFlags(uint16_t value,bool byte=false) {
        return (value==0 ? 0x40u : 0u)|(value&(byte ? 128u : 32768u) ? 0x80u : 0u)|
            (std::popcount(static_cast<uint8_t>(value))%2==0 ? 4u : 0u);
    }
    uint16_t logic(uint16_t value,bool byte=false) {
        state_.cpu.registers.flags=(state_.cpu.registers.flags&~uint32_t{0x8d5})|valueFlags(value,byte);return value;
    }
    uint16_t arithmetic(uint16_t a,uint16_t b,bool subtract=false,bool byte=false) {
        const uint32_t mask=byte ? 255u : 65535u,sign=byte ? 128u : 32768u;
        const uint32_t wide=subtract ? uint32_t{a}-b : uint32_t{a}+b;
        const auto value=static_cast<uint16_t>(wide&mask);
        uint32_t f=valueFlags(value,byte)|((a^b^value)&16u);
        if (subtract ? a<b : wide>mask) f|=1;
        if (subtract ? ((a^b)&(a^value)&sign) : (~(a^b)&(a^value)&sign)) f|=0x800;
        state_.cpu.registers.flags=(state_.cpu.registers.flags&~uint32_t{0x8d5})|f;return value;
    }
    uint16_t increment(uint16_t value,bool subtract=false,bool byte=false) {
        const auto carry=state_.cpu.registers.flags&1u;value=arithmetic(value,1,subtract,byte);
        state_.cpu.registers.flags=(state_.cpu.registers.flags&~uint32_t{1})|carry;return value;
    }
    uint16_t shift(uint16_t value,unsigned count) {
        for (unsigned i=0;i<count;++i) {
            const auto old=value;const auto carry=value>>15;value=static_cast<uint16_t>(value<<1);
            state_.cpu.registers.flags=(state_.cpu.registers.flags&~uint32_t{0x8d5})|valueFlags(value)|16u|carry|
                ((old^value)&0x8000u ? 0x800u : 0u);
        }
        return value;
    }
    void instruction(const TimerIrqBus& bus,const CopyBudget& copies) {
        auto& r=state_.cpu.registers;
        const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value); };
        const auto pop=[&] { const auto value=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return value; };
        const auto local=[&](int offset) { return bus.readWord(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto lb=[&](int offset) { return bus.readByte(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto store=[&](int offset,uint16_t value) { bus.writeWord(r.ss,static_cast<uint16_t>(r.bp+offset),value); };
        const auto sb=[&](int offset,uint8_t value) { bus.writeByte(r.ss,static_cast<uint16_t>(r.bp+offset),value); };
        const auto les=[&](int offset) { r.di=local(offset);r.es=local(offset+2); };
        const auto data=[&](uint16_t offset) { return bus.readByte(r.ds,offset); };
        const auto dw=[&](uint16_t offset) { return bus.readWord(r.ds,offset); };
        const auto wb=[&](unsigned offset,uint8_t value) { bus.writeByte(r.es,static_cast<uint16_t>(r.di+offset),value); };
        const auto byte=[&](unsigned offset) { return bus.readByte(r.es,static_cast<uint16_t>(r.di+offset)); };
        const auto al=[&](uint8_t value) { r.ax=static_cast<uint16_t>((r.ax&0xff00u)|value); };
        const auto zeroAh=[&] { r.ax&=255u;logic(0,true); };
        const auto less=[&] { return flag(0x80)!=flag(0x800); };
        const auto branch=[&](bool condition,uint16_t yes,uint16_t no) { r.ip=condition ? yes : no; };
        const auto farCall=[&](uint16_t segment,uint16_t ip,uint16_t next) { push(r.cs);push(next);r.cs=segment;r.ip=ip; };
        const auto signedMultiply=[&](uint16_t value) {
            const int32_t product=int32_t{std::bit_cast<int16_t>(value)}*38;r.di=static_cast<uint16_t>(product);
            r.flags=(r.flags&~uint32_t{0x801})|((product < -32768 || product > 32767) ? 0x801u : 0u);
        };
        const auto multiply=[&] {
            const uint32_t product=uint32_t{r.ax}*r.bx;r.ax=static_cast<uint16_t>(product);r.dx=static_cast<uint16_t>(product>>16);
            r.flags=(r.flags&~uint32_t{0x841})|(r.dx ? 0x801u : 0u)|(r.ax==0 ? 0x40u : 0u);
        };
        if (r.cs==library()) {
            ActorAnimationOperation runtime(ActorAnimationSnapshot{r,state_.cpu.gameSegment});
            runtime.advance(1,bus,copies);r=runtime.snapshot().registers;
            state_.cpu.transferredBytes+=runtime.snapshot().transferredBytes;return;
        }
        if (r.cs==graphics()) {
            switch (r.ip) {
            case 0x594:push(r.bp);r.ip=0x595;break;
            case 0x595:r.bp=r.sp;r.ip=0x597;break;
            case 0x597:r.ax=logic(0);r.ip=0x599;break;
            case 0x599:farCall(library(),0x4df,0x59e);break;
            case 0x59e:arithmetic(data(0xc496),0,true,true);r.ip=0x5a3;break;
            case 0x5a3:branch(flag(1)||flag(0x40),0x5d8,0x5a5);break;
            case 0x5a5:al(data(0xc496));r.ip=0x5a8;break;
            case 0x5a8:zeroAh();r.ip=0x5aa;break;
            case 0x5aa:r.ax=increment(r.ax,true);r.ip=0x5ab;break;
            case 0x5ab:arithmetic(r.ax,local(6),true);r.ip=0x5ae;break;
            case 0x5ae:branch(flag(0x40)||less(),0x5d4,0x5b0);break;
            case 0x5b0:push(r.ds);r.ip=0x5b1;break;
            case 0x5b1:r.es=pop();r.ip=0x5b2;break;
            case 0x5b2:al(data(0xc496));r.ip=0x5b5;break;
            case 0x5b5:zeroAh();r.ip=0x5b7;break;
            case 0x5b7:r.ax=arithmetic(r.ax,local(6),true);r.ip=0x5ba;break;
            case 0x5ba:r.ax=increment(r.ax,true);r.ip=0x5bb;break;
            case 0x5bb:r.bx=8;r.ip=0x5be;break;
            case 0x5be:multiply();r.ip=0x5c0;break;
            case 0x5c0:r.cx=r.ax;r.ip=0x5c2;break;
            case 0x5c2:r.di=dw(0xc1fc);r.ip=0x5c6;break;
            case 0x5c6:r.ax=local(6);r.ip=0x5c9;break;
            case 0x5c9:multiply();r.ip=0x5cb;break;
            case 0x5cb:r.di=arithmetic(r.di,r.ax);r.ip=0x5cd;break;
            case 0x5cd:r.si=r.di;r.ip=0x5cf;break;
            case 0x5cf:r.si=arithmetic(r.si,8);r.ip=0x5d2;break;
            case 0x5d2: {
                const uint16_t amount=r.cx ? copies(r.cx) : uint16_t{0};
                if (amount>r.cx) throw std::domain_error("Actor visual copy grant exceeds CX");
                for (unsigned i=0;i<amount;++i) {
                    bus.writeByte(r.es,r.di,bus.readByte(r.ds,r.si));
                    const auto step=flag(0x400) ? uint16_t{65535} : uint16_t{1};
                    r.si=static_cast<uint16_t>(r.si+step);r.di=static_cast<uint16_t>(r.di+step);
                }
                r.cx=static_cast<uint16_t>(r.cx-amount);state_.cpu.transferredBytes+=amount;
                if (!r.cx) r.ip=0x5d4;
                break;
            }
            case 0x5d4:bus.writeByte(r.ds,0xc496,static_cast<uint8_t>(increment(data(0xc496),true,true)));r.ip=0x5d8;break;
            case 0x5d8:r.bp=pop();r.ip=0x5d9;break;
            case 0x5d9:r.ip=pop();r.cs=pop();r.sp=static_cast<uint16_t>(r.sp+2u);break;
            default:throw std::domain_error("Actor expiry left recovered visual compaction");
            }
            return;
        }
        if (r.cs!=state_.cpu.gameSegment) throw std::domain_error("Actor expiry left recovered code");
        if (r.ip==0x777f || r.ip==0x7780) {
            ActorFinishOperation tail(ActorFinishSnapshot{r,state_.cpu.gameSegment,state_.cpu.idToggleMask});
            tail.advance(1,bus,copies);r=tail.registers();
            if (tail.snapshot().outcome==ActorFinishOutcome::Returned) state_.outcome=ActorExpiryOutcome::Returned;
            return;
        }
        switch (r.ip) {
        case 0x65a8:r.ax=dw(0x78c2);r.ip=0x65ab;break;
        case 0x65ab:r.ax=logic(r.ax&1u);r.ip=0x65ae;break;
        case 0x65ae:les(4);r.ip=0x65b1;break;
        case 0x65b1:wb(2,static_cast<uint8_t>(arithmetic(byte(2),r.ax&255u,true,true)));r.ip=0x65b5;break;
        case 0x65b5:les(4);r.ip=0x65b8;break;
        case 0x65b8:arithmetic(byte(2),0,true,true);r.ip=0x65bd;break;
        case 0x65bd:branch(!flag(0x40),0x65d7,0x65bf);break;
        case 0x65bf:push(dw(0x2082));r.ip=0x65c3;break;
        case 0x65c3:push(0x65c6);r.ip=0x3358;break;
        case 0x65c6:bus.writeWord(r.ds,0x2082,increment(dw(0x2082),true));r.ip=0x65ca;break;
        case 0x65ca:arithmetic(lb(-15),10,true,true);r.ip=0x65ce;break;
        case 0x65ce:branch(!flag(0x40),0x65d4,0x65d0);break;
        case 0x65d0:bus.writeByte(r.ds,0x208e,static_cast<uint8_t>(increment(data(0x208e),true,true)));r.ip=0x65d4;break;
        case 0x65d4:r.ip=0x777f;break;
        case 0x65d7:r.ip=0x73e5;break;
        case 0x3358:push(r.bp);r.ip=0x3359;break;
        case 0x3359:r.bp=r.sp;r.ip=0x335b;break;
        case 0x335b:r.ax=10;r.ip=0x335e;break;
        case 0x335e:farCall(library(),0x4df,0x3363);break;
        case 0x3363:r.sp=arithmetic(r.sp,10,true);r.ip=0x3366;break;
        case 0x3366:al(data(0x208d));r.ip=0x3369;break;
        case 0x3369:zeroAh();r.ip=0x336b;break;
        case 0x336b:arithmetic(r.ax,local(4),true);r.ip=0x336e;break;
        case 0x336e:branch(!less(),0x3373,0x3370);break;
        case 0x3370:r.ip=0x3467;break;
        case 0x3373:signedMultiply(local(4));r.ip=0x3377;break;
        case 0x3377:al(data(static_cast<uint16_t>(r.di+0x1bafu)));r.ip=0x337b;break;
        case 0x337b:sb(-3,static_cast<uint8_t>(r.ax));r.ip=0x337e;break;
        case 0x337e:al(lb(-3));r.ip=0x3381;break;
        case 0x3381:zeroAh();r.ip=0x3383;break;
        case 0x3383:push(r.ax);r.ip=0x3384;break;
        case 0x3384:farCall(graphics(),0x594,0x3389);break;
        case 0x3389:al(data(0x208d));r.ip=0x338c;break;
        case 0x338c:zeroAh();r.ip=0x338e;break;
        case 0x338e:r.ax=increment(r.ax,true);r.ip=0x338f;break;
        case 0x338f:store(-6,r.ax);r.ip=0x3392;break;
        case 0x3392:r.ax=local(4);r.ip=0x3395;break;
        case 0x3395:arithmetic(r.ax,local(-6),true);r.ip=0x3398;break;
        case 0x3398:branch(!flag(0x40)&&!less(),0x33c8,0x339a);break;
        case 0x339a:store(-2,r.ax);r.ip=0x339d;break;
        case 0x339d:r.ip=0x33a2;break;
        case 0x339f:store(-2,increment(local(-2)));r.ip=0x33a2;break;
        case 0x33a2:r.ax=local(-2);r.ip=0x33a5;break;
        case 0x33a5:r.ax=increment(r.ax);r.ip=0x33a6;break;
        case 0x33a6:signedMultiply(r.ax);r.ip=0x33a9;break;
        case 0x33a9:r.di=arithmetic(r.di,0x1bae);r.ip=0x33ad;break;
        case 0x33ad:push(r.ds);r.ip=0x33ae;break;
        case 0x33ae:push(r.di);r.ip=0x33af;break;
        case 0x33af:signedMultiply(local(-2));r.ip=0x33b3;break;
        case 0x33b3:r.di=arithmetic(r.di,0x1bae);r.ip=0x33b7;break;
        case 0x33b7:push(r.ds);r.ip=0x33b8;break;
        case 0x33b8:push(r.di);r.ip=0x33b9;break;
        case 0x33b9:push(38);r.ip=0x33bb;break;
        case 0x33bb:farCall(library(),0x90e,0x33c0);break;
        case 0x33c0:r.ax=local(-2);r.ip=0x33c3;break;
        case 0x33c3:arithmetic(r.ax,local(-6),true);r.ip=0x33c6;break;
        case 0x33c6:branch(!flag(0x40),0x339f,0x33c8);break;
        case 0x33c8:bus.writeByte(r.ds,0x208d,static_cast<uint8_t>(increment(data(0x208d),true,true)));r.ip=0x33cc;break;
        case 0x33cc:al(data(0x208d));r.ip=0x33cf;break;
        case 0x33cf:zeroAh();r.ip=0x33d1;break;
        case 0x33d1:store(-6,r.ax);r.ip=0x33d4;break;
        case 0x33d4:r.ax=logic(0);r.ip=0x33d6;break;
        case 0x33d6:arithmetic(r.ax,local(-6),true);r.ip=0x33d9;break;
        case 0x33d9:branch(!flag(0x40)&&!less(),0x340c,0x33db);break;
        case 0x33db:store(-2,r.ax);r.ip=0x33de;break;
        case 0x33de:r.ip=0x33e3;break;
        case 0x33e0:store(-2,increment(local(-2)));r.ip=0x33e3;break;
        case 0x33e3:signedMultiply(local(-2));r.ip=0x33e7;break;
        case 0x33e7:r.di=arithmetic(r.di,0x1bae);r.ip=0x33eb;break;
        case 0x33eb:store(-10,r.di);r.ip=0x33ee;break;
        case 0x33ee:store(-8,r.ds);r.ip=0x33f1;break;
        case 0x33f1:les(-10);r.ip=0x33f4;break;
        case 0x33f4:al(byte(1));r.ip=0x33f8;break;
        case 0x33f8:arithmetic(r.ax&255u,lb(-3),true,true);r.ip=0x33fb;break;
        case 0x33fb:branch(flag(1)||flag(0x40),0x3404,0x33fd);break;
        case 0x33fd:les(-10);r.ip=0x3400;break;
        case 0x3400:wb(1,static_cast<uint8_t>(increment(byte(1),true,true)));r.ip=0x3404;break;
        case 0x3404:r.ax=local(-2);r.ip=0x3407;break;
        case 0x3407:arithmetic(r.ax,local(-6),true);r.ip=0x340a;break;
        case 0x340a:branch(!flag(0x40),0x33e0,0x340c);break;
        case 0x340c:arithmetic(data(0x79f9),0,true,true);r.ip=0x3411;break;
        case 0x3411:branch(flag(1)||flag(0x40),0x3467,0x3413);break;
        case 0x3413:al(data(0x79f9));r.ip=0x3416;break;
        case 0x3416:zeroAh();r.ip=0x3418;break;
        case 0x3418:store(-6,r.ax);r.ip=0x341b;break;
        case 0x341b:r.ax=1;r.ip=0x341e;break;
        case 0x341e:arithmetic(r.ax,local(-6),true);r.ip=0x3421;break;
        case 0x3421:branch(!flag(0x40)&&!less(),0x3467,0x3423);break;
        case 0x3423:store(-2,r.ax);r.ip=0x3426;break;
        case 0x3426:r.ip=0x342b;break;
        case 0x3428:store(-2,increment(local(-2)));r.ip=0x342b;break;
        case 0x342b:r.di=local(-2);r.ip=0x342e;break;
        case 0x342e:r.di=shift(r.di,4);r.ip=0x3431;break;
        case 0x3431:r.di=arithmetic(r.di,0x79ea);r.ip=0x3435;break;
        case 0x3435:store(-10,r.di);r.ip=0x3438;break;
        case 0x3438:store(-8,r.ds);r.ip=0x343b;break;
        case 0x343b:les(-10);r.ip=0x343e;break;
        case 0x343e:al(byte(0));r.ip=0x3441;break;
        case 0x3441:arithmetic(r.ax&255u,lb(-3),true,true);r.ip=0x3444;break;
        case 0x3444:branch(flag(1)||flag(0x40),0x344c,0x3446);break;
        case 0x3446:les(-10);r.ip=0x3449;break;
        case 0x3449:wb(0,static_cast<uint8_t>(increment(byte(0),true,true)));r.ip=0x344c;break;
        case 0x344c:les(-10);r.ip=0x344f;break;
        case 0x344f:al(byte(1));r.ip=0x3453;break;
        case 0x3453:arithmetic(r.ax&255u,lb(-3),true,true);r.ip=0x3456;break;
        case 0x3456:branch(flag(1)||flag(0x40),0x345f,0x3458);break;
        case 0x3458:les(-10);r.ip=0x345b;break;
        case 0x345b:wb(1,static_cast<uint8_t>(increment(byte(1),true,true)));r.ip=0x345f;break;
        case 0x345f:r.ax=local(-2);r.ip=0x3462;break;
        case 0x3462:arithmetic(r.ax,local(-6),true);r.ip=0x3465;break;
        case 0x3465:branch(!flag(0x40),0x3428,0x3467);break;
        case 0x3467:r.sp=r.bp;r.bp=pop();r.ip=0x3468;break;
        case 0x3468:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+2u);break;
        default:throw std::domain_error("Actor expiry reached an unrecovered instruction");
        }
    }
};

} // namespace lezac::core
