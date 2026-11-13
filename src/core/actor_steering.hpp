#pragma once

#include "core/actor_finish.hpp"

namespace lezac::core {

enum class ActorSteeringEntry { Vector, CallSite, SquareRoot };
enum class ActorSteeringOutcome { Running, Returned, RuntimeError };
struct ActorSteeringSnapshot {
    ActorFinishSnapshot cpu;
    ActorSteeringEntry entry=ActorSteeringEntry::Vector;
    ActorSteeringOutcome outcome=ActorSteeringOutcome::Running;
    bool operator==(const ActorSteeringSnapshot&) const = default;
};

// Execute the original far-reference vector helper and RTL Newton iteration.
// All intermediate Real48 values remain in registers and the caller's stack.
class ActorSteeringOperation {
public:
    using CopyBudget=ActorFinishOperation::CopyBudget;
    ActorSteeringOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle,ActorSteeringEntry entry)
        : state_{ActorFinishSnapshot{r,game,idToggle},entry} {
        if (r.cs!=(entry==ActorSteeringEntry::SquareRoot ? library() : game) ||
            r.ip!=(entry==ActorSteeringEntry::SquareRoot ? 0xfc2 : entry==ActorSteeringEntry::CallSite ? 0x710d : 0x346b) ||
            r.ds!=static_cast<uint16_t>(game+0xaa2))
            throw std::invalid_argument("Actor steering entry differs");
        validate();
    }
    explicit ActorSteeringOperation(ActorSteeringSnapshot state) : state_(state) { validate(); }
    const ActorSteeringSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const { return ActorFinishOperation(state_.cpu).registers(); }
    bool finished() const noexcept { return state_.outcome!=ActorSteeringOutcome::Running; }
    bool interruptInProgress() const noexcept { return state_.cpu.timer.has_value(); }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished actor steering admitted IRQ");
        ActorFinishOperation irq(state_.cpu);irq.deliverTimerInterrupt(bus);state_.cpu=irq.snapshot();
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (state_.cpu.timer) {
                ActorFinishOperation irq(state_.cpu);
                if (irq.advance(1,bus,copies)!=1) throw std::domain_error("Actor steering IRQ did not dispatch");
                state_.cpu=irq.snapshot();
            } else {
                instruction(bus);++state_.cpu.dispatchedInstructions;
                const auto& r=state_.cpu.registers;
                if (r.cs==library() && r.ip==0xe2) state_.outcome=ActorSteeringOutcome::RuntimeError;
            }
            ++used;
        }
        return used;
    }
private:
    ActorSteeringSnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.cpu.gameSegment+0x920); }
    void validate() const {
        (void)ActorFinishOperation(state_.cpu);
        if (state_.cpu.outcome!=ActorFinishOutcome::Running || (finished() && state_.cpu.timer) ||
            (state_.entry!=ActorSteeringEntry::Vector && state_.entry!=ActorSteeringEntry::CallSite && state_.entry!=ActorSteeringEntry::SquareRoot) ||
            (state_.outcome!=ActorSteeringOutcome::Running && state_.outcome!=ActorSteeringOutcome::Returned && state_.outcome!=ActorSteeringOutcome::RuntimeError) ||
            (state_.outcome==ActorSteeringOutcome::RuntimeError && (state_.cpu.registers.cs!=library() || state_.cpu.registers.ip!=0xe2)))
            throw std::invalid_argument("Actor steering CPU/outcome ownership differs");
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
    static void low(uint16_t& word,uint16_t value) { word=static_cast<uint16_t>((word&0xff00u)|(value&255u)); }
    void instruction(const TimerIrqBus& bus) {
        auto& r=state_.cpu.registers;
        const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value); };
        const auto pop=[&] { const auto value=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return value; };
        const auto local=[&](int offset) { return bus.readWord(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto store=[&](int offset,uint16_t value) { bus.writeWord(r.ss,static_cast<uint16_t>(r.bp+offset),value); };
        const auto les=[&](int offset) { r.di=local(offset);r.es=local(offset+2); };
        const auto branch=[&](bool condition,uint16_t yes,uint16_t no) { r.ip=condition ? yes : no; };
        const auto call=[&](uint16_t target,uint16_t next) { push(next);r.ip=target; };
        const auto farCall=[&](uint16_t target,uint16_t next) { push(r.cs);push(next);r.cs=library();r.ip=target; };
        if (r.cs==library()) {
            switch (r.ip) {
            case 0xfc2:push(r.bp);r.ip=0xfc3;break;
            case 0xfc3:r.bp=r.sp;r.ip=0xfc5;break;
            case 0xfc5:r.sp=arithmetic(r.sp,8,true);r.ip=0xfc8;break;
            case 0xfc8:r.cx=r.ax;r.ip=0xfca;break;
            case 0xfca:r.si=r.bx;r.ip=0xfcc;break;
            case 0xfcc:r.di=r.dx;r.ip=0xfce;break;
            case 0xfce:logic(r.ax&255u,true);r.ip=0xfd0;break;
            case 0xfd0:branch(flag(0x40),0x100e,0xfd2);break;
            case 0xfd2:logic((r.dx>>8)&128u,true);r.ip=0xfd5;break;
            case 0xfd5:branch(!flag(0x40),0x1018,0xfd7);break;
            case 0xfd7:store(-8,r.ax);r.ip=0xfda;break;
            case 0xfda:store(-6,r.bx);r.ip=0xfdd;break;
            case 0xfdd:store(-4,r.dx);r.ip=0xfe0;break;
            case 0xfe0:low(r.cx,arithmetic(r.cx&255u,128,false,true));r.ip=0xfe3;break;
            case 0xfe3: {
                const auto value=static_cast<uint8_t>(r.cx);
                const auto result=static_cast<uint8_t>((value>>1)|(value&128u));
                r.flags=(r.flags&~uint32_t{0x8d5})|valueFlags(result,true)|16u|(value&1u);
                low(r.cx,result);r.ip=0xfe5;break;
            }
            case 0xfe5:low(r.cx,arithmetic(r.cx&255u,128,false,true));r.ip=0xfe8;break;
            case 0xfe8:low(r.ax,r.cx);r.ip=0xfea;break;
            case 0xfea:low(r.ax,arithmetic(r.ax&255u,20,true,true));r.ip=0xfec;break;
            case 0xfec:bus.writeByte(r.ss,static_cast<uint16_t>(r.bp-2u),static_cast<uint8_t>(r.ax));r.ip=0xfef;break;
            case 0xfef:r.ax=local(-8);r.ip=0xff2;break;
            case 0xff2:r.bx=local(-6);r.ip=0xff5;break;
            case 0xff5:r.dx=local(-4);r.ip=0xff8;break;
            case 0xff8:call(0xf53,0xffb);break;
            case 0xffb:call(0xf35,0xffe);break;
            case 0xffe: {
                const auto carry=r.flags&1u;low(r.ax,arithmetic(r.ax&255u,1,true,true));
                r.flags=(r.flags&~uint32_t{1})|carry;r.ip=0x1000;break;
            }
            case 0x1000:push(r.dx);r.ip=0x1001;break;
            case 0x1001:push(r.bx);r.ip=0x1002;break;
            case 0x1002:push(r.ax);r.ip=0x1003;break;
            case 0x1003:call(0xbe1,0x1006);break;
            case 0x1006:arithmetic(r.ax&255u,bus.readByte(r.ss,static_cast<uint16_t>(r.bp-2u)),true,true);r.ip=0x1009;break;
            case 0x1009:r.cx=pop();r.ip=0x100a;break;
            case 0x100a:r.si=pop();r.ip=0x100b;break;
            case 0x100b:r.di=pop();r.ip=0x100c;break;
            case 0x100c:branch(!flag(1),0xfef,0x100e);break;
            case 0x100e:r.ax=r.cx;r.ip=0x1010;break;
            case 0x1010:r.bx=r.si;r.ip=0x1012;break;
            case 0x1012:r.dx=r.di;r.ip=0x1014;break;
            case 0x1014:r.sp=r.bp;r.ip=0x1016;break;
            case 0x1016:r.bp=pop();r.ip=0x1017;break;
            case 0x1017:r.ip=pop();r.cs=pop();if (state_.entry==ActorSteeringEntry::SquareRoot) state_.outcome=ActorSteeringOutcome::Returned;break;
            case 0x1018:r.sp=r.bp;r.ip=0x101a;break;
            case 0x101a:r.bp=pop();r.ip=0x101b;break;
            case 0x101b:r.ax=0xcf;r.ip=0x101e;break;
            case 0x101e:r.ip=0xe2;break;
            default:advanceActorReal48Instruction(r,state_.cpu.gameSegment,bus);break;
            }
            return;
        }
        if (r.cs!=state_.cpu.gameSegment) throw std::domain_error("Actor steering left recovered code");
        switch (r.ip) {
        case 0x346b:push(r.bp);r.ip=0x346c;break;
        case 0x346c:r.bp=r.sp;r.ip=0x346e;break;
        case 0x346e:r.ax=18;r.ip=0x3471;break;
        case 0x3471:farCall(0x4df,0x3476);break;
        case 0x3476:r.sp=arithmetic(r.sp,18,true);r.ip=0x3479;break;
        case 0x3479:les(20);r.ip=0x347c;break;
        case 0x347c:r.ax=bus.readWord(r.es,r.di);r.ip=0x347f;break;
        case 0x347f:r.dx=(r.ax&0x8000u) ? uint16_t{65535} : uint16_t{0};r.ip=0x3480;break;
        case 0x3480:farCall(0xf0f,0x3485);break;
        case 0x3485:store(-12,r.ax);r.ip=0x3488;break;
        case 0x3488:store(-10,r.bx);r.ip=0x348b;break;
        case 0x348b:store(-8,r.dx);r.ip=0x348e;break;
        case 0x348e:les(16);r.ip=0x3491;break;
        case 0x3491:r.ax=bus.readWord(r.es,r.di);r.ip=0x3494;break;
        case 0x3494:r.dx=(r.ax&0x8000u) ? uint16_t{65535} : uint16_t{0};r.ip=0x3495;break;
        case 0x3495:farCall(0xf0f,0x349a);break;
        case 0x349a:store(-18,r.ax);r.ip=0x349d;break;
        case 0x349d:store(-16,r.bx);r.ip=0x34a0;break;
        case 0x34a0:store(-14,r.dx);r.ip=0x34a3;break;
        case 0x34a3:r.ax=local(-12);r.ip=0x34a6;break;
        case 0x34a6:r.bx=local(-10);r.ip=0x34a9;break;
        case 0x34a9:r.dx=local(-8);r.ip=0x34ac;break;
        case 0x34ac:r.cx=logic(0);r.ip=0x34ae;break;
        case 0x34ae:r.si=logic(0);r.ip=0x34b0;break;
        case 0x34b0:r.di=logic(0);r.ip=0x34b2;break;
        case 0x34b2:farCall(0xf0b,0x34b7);break;
        case 0x34b7:branch(!flag(0x40),0x34e0,0x34b9);break;
        case 0x34b9:r.ax=local(-18);r.ip=0x34bc;break;
        case 0x34bc:r.bx=local(-16);r.ip=0x34bf;break;
        case 0x34bf:r.dx=local(-14);r.ip=0x34c2;break;
        case 0x34c2:r.cx=logic(0);r.ip=0x34c4;break;
        case 0x34c4:r.si=logic(0);r.ip=0x34c6;break;
        case 0x34c6:r.di=logic(0);r.ip=0x34c8;break;
        case 0x34c8:farCall(0xf0b,0x34cd);break;
        case 0x34cd:branch(!flag(0x40),0x34e0,0x34cf);break;
        case 0x34cf:store(-6,0);r.ip=0x34d4;break;
        case 0x34d4:store(-4,0);r.ip=0x34d9;break;
        case 0x34d9:store(-2,0);r.ip=0x34de;break;
        case 0x34de:r.ip=0x353f;break;
        case 0x34e0:r.ax=local(-18);r.ip=0x34e3;break;
        case 0x34e3:r.bx=local(-16);r.ip=0x34e6;break;
        case 0x34e6:r.dx=local(-14);r.ip=0x34e9;break;
        case 0x34e9:r.cx=local(-18);r.ip=0x34ec;break;
        case 0x34ec:r.si=local(-16);r.ip=0x34ef;break;
        case 0x34ef:r.di=local(-14);r.ip=0x34f2;break;
        case 0x34f2:farCall(0xefb,0x34f7);break;
        case 0x34f7:push(r.dx);r.ip=0x34f8;break;
        case 0x34f8:push(r.bx);r.ip=0x34f9;break;
        case 0x34f9:push(r.ax);r.ip=0x34fa;break;
        case 0x34fa:r.ax=local(-12);r.ip=0x34fd;break;
        case 0x34fd:r.bx=local(-10);r.ip=0x3500;break;
        case 0x3500:r.dx=local(-8);r.ip=0x3503;break;
        case 0x3503:r.cx=local(-12);r.ip=0x3506;break;
        case 0x3506:r.si=local(-10);r.ip=0x3509;break;
        case 0x3509:r.di=local(-8);r.ip=0x350c;break;
        case 0x350c:farCall(0xefb,0x3511);break;
        case 0x3511:r.cx=pop();r.ip=0x3512;break;
        case 0x3512:r.si=pop();r.ip=0x3513;break;
        case 0x3513:r.di=pop();r.ip=0x3514;break;
        case 0x3514:farCall(0xee9,0x3519);break;
        case 0x3519:farCall(0xfc2,0x351e);break;
        case 0x351e:push(r.dx);r.ip=0x351f;break;
        case 0x351f:push(r.bx);r.ip=0x3520;break;
        case 0x3520:push(r.ax);r.ip=0x3521;break;
        case 0x3521:les(12);r.ip=0x3524;break;
        case 0x3524:r.ax=bus.readWord(r.es,r.di);r.ip=0x3527;break;
        case 0x3527:r.dx=logic(0);r.ip=0x3529;break;
        case 0x3529:farCall(0xf0f,0x352e);break;
        case 0x352e:r.cx=pop();r.ip=0x352f;break;
        case 0x352f:r.si=pop();r.ip=0x3530;break;
        case 0x3530:r.di=pop();r.ip=0x3531;break;
        case 0x3531:farCall(0xf01,0x3536);break;
        case 0x3536:store(-6,r.ax);r.ip=0x3539;break;
        case 0x3539:store(-4,r.bx);r.ip=0x353c;break;
        case 0x353c:store(-2,r.dx);r.ip=0x353f;break;
        case 0x353f:r.ax=local(-12);r.ip=0x3542;break;
        case 0x3542:r.bx=local(-10);r.ip=0x3545;break;
        case 0x3545:r.dx=local(-8);r.ip=0x3548;break;
        case 0x3548:r.cx=local(-6);r.ip=0x354b;break;
        case 0x354b:r.si=local(-4);r.ip=0x354e;break;
        case 0x354e:r.di=local(-2);r.ip=0x3551;break;
        case 0x3551:farCall(0xefb,0x3556);break;
        case 0x3556:farCall(0xf13,0x355b);break;
        case 0x355b:les(8);r.ip=0x355e;break;
        case 0x355e:bus.writeWord(r.es,r.di,r.ax);r.ip=0x3561;break;
        case 0x3561:r.ax=local(-18);r.ip=0x3564;break;
        case 0x3564:r.bx=local(-16);r.ip=0x3567;break;
        case 0x3567:r.dx=local(-14);r.ip=0x356a;break;
        case 0x356a:r.cx=local(-6);r.ip=0x356d;break;
        case 0x356d:r.si=local(-4);r.ip=0x3570;break;
        case 0x3570:r.di=local(-2);r.ip=0x3573;break;
        case 0x3573:farCall(0xefb,0x3578);break;
        case 0x3578:farCall(0xf13,0x357d);break;
        case 0x357d:les(4);r.ip=0x3580;break;
        case 0x3580:bus.writeWord(r.es,r.di,r.ax);r.ip=0x3583;break;
        case 0x3583:r.sp=r.bp;r.bp=pop();r.ip=0x3584;break;
        case 0x3584:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+20u);if (state_.entry==ActorSteeringEntry::Vector) state_.outcome=ActorSteeringOutcome::Returned;break;
        case 0x710d:r.di=static_cast<uint16_t>(r.bp-4u);r.ip=0x7110;break;
        case 0x7110:push(r.ss);r.ip=0x7111;break;
        case 0x7111:push(r.di);r.ip=0x7112;break;
        case 0x7112:r.di=static_cast<uint16_t>(r.bp-6u);r.ip=0x7115;break;
        case 0x7115:push(r.ss);r.ip=0x7116;break;
        case 0x7116:push(r.di);r.ip=0x7117;break;
        case 0x7117:r.di=0x2074;r.ip=0x711a;break;
        case 0x711a:push(r.ds);r.ip=0x711b;break;
        case 0x711b:push(r.di);r.ip=0x711c;break;
        case 0x711c:r.di=static_cast<uint16_t>(r.bp-12u);r.ip=0x711f;break;
        case 0x711f:push(r.ss);r.ip=0x7120;break;
        case 0x7120:push(r.di);r.ip=0x7121;break;
        case 0x7121:r.di=static_cast<uint16_t>(r.bp-14u);r.ip=0x7124;break;
        case 0x7124:push(r.ss);r.ip=0x7125;break;
        case 0x7125:push(r.di);r.ip=0x7126;break;
        case 0x7126:call(0x346b,0x7129);break;
        case 0x7129:r.ip=0x714f;state_.outcome=ActorSteeringOutcome::Returned;break;
        default:throw std::domain_error("Actor steering left recovered game instructions");
        }
    }
};

} // namespace lezac::core
