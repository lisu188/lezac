#pragma once

#include "core/actor_steering.hpp"
#include "core/actor_terrain.hpp"

namespace lezac::core {

enum class ActorMotionEntry { Behavior, TileFracture, TileSample, Friction };
enum class ActorMotionOutcome { Running, MotionIntegration, Returned, RuntimeError, DivideError };
struct ActorMotionSnapshot {
    ActorFinishSnapshot cpu;
    ActorMotionEntry entry=ActorMotionEntry::Behavior;
    ActorMotionOutcome outcome=ActorMotionOutcome::Running;
    bool operator==(const ActorMotionSnapshot&) const = default;
};

// Original nonzero-behavior movement, nested terrain helpers and live-stack
// steering. Stop before common 73E5 integration or after a real helper return.
class ActorMotionOperation {
public:
    using CopyBudget=ActorFinishOperation::CopyBudget;
    ActorMotionOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle,ActorMotionEntry entry=ActorMotionEntry::Behavior)
        : state_{ActorFinishSnapshot{r,game,idToggle},entry} {
        const auto ip=entry==ActorMotionEntry::Behavior ? 0x7018 : entry==ActorMotionEntry::TileFracture ? 0x370e :
            entry==ActorMotionEntry::TileSample ? 0x5afd : 0x5b86;
        if (r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2) || r.ip!=ip)
            throw std::invalid_argument("Actor motion entry differs");
        validate();
    }
    explicit ActorMotionOperation(ActorMotionSnapshot state) : state_(state) { validate(); }
    const ActorMotionSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const { return ActorFinishOperation(state_.cpu).registers(); }
    bool finished() const noexcept { return state_.outcome!=ActorMotionOutcome::Running; }
    bool interruptInProgress() const noexcept { return state_.cpu.timer.has_value(); }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished actor motion admitted IRQ");
        ActorFinishOperation irq(state_.cpu);irq.deliverTimerInterrupt(bus);state_.cpu=irq.snapshot();
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (state_.cpu.timer) {
                ActorFinishOperation irq(state_.cpu);
                if (irq.advance(1,bus,copies)!=1) throw std::domain_error("Actor motion IRQ did not dispatch");
                state_.cpu=irq.snapshot();
            } else {
                const auto before=state_.cpu.registers;
                const bool returned=before.cs==state_.cpu.gameSegment &&
                    ((state_.entry==ActorMotionEntry::TileFracture && before.ip==0x3a53) ||
                     (state_.entry==ActorMotionEntry::TileSample && before.ip==0x5b83) ||
                     (state_.entry==ActorMotionEntry::Friction && before.ip==0x5bc9));
                instruction(bus,copies);++state_.cpu.dispatchedInstructions;
                const auto& r=state_.cpu.registers;
                if (returned) state_.outcome=ActorMotionOutcome::Returned;
                if (r.cs==state_.cpu.gameSegment && r.ip==0x73e5) state_.outcome=ActorMotionOutcome::MotionIntegration;
                if (r.cs==library() && r.ip==0xe2) state_.outcome=ActorMotionOutcome::RuntimeError;
            }
            ++used;
        }
        return used;
    }
private:
    ActorMotionSnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.cpu.gameSegment+0x920); }
    void validate() const {
        (void)ActorFinishOperation(state_.cpu);
        const auto& r=state_.cpu.registers;
        if (state_.cpu.outcome!=ActorFinishOutcome::Running || (finished() && state_.cpu.timer) ||
            (r.cs!=state_.cpu.gameSegment && r.cs!=library()) ||
            (state_.entry!=ActorMotionEntry::Behavior && state_.entry!=ActorMotionEntry::TileFracture &&
                state_.entry!=ActorMotionEntry::TileSample && state_.entry!=ActorMotionEntry::Friction) ||
            (state_.outcome!=ActorMotionOutcome::Running && state_.outcome!=ActorMotionOutcome::MotionIntegration &&
                state_.outcome!=ActorMotionOutcome::Returned && state_.outcome!=ActorMotionOutcome::RuntimeError &&
                state_.outcome!=ActorMotionOutcome::DivideError) ||
            (state_.outcome==ActorMotionOutcome::MotionIntegration && (r.cs!=state_.cpu.gameSegment || r.ip!=0x73e5)) ||
            (state_.outcome==ActorMotionOutcome::RuntimeError && (r.cs!=library() || r.ip!=0xe2)) ||
            (state_.outcome==ActorMotionOutcome::Returned &&
                (state_.entry==ActorMotionEntry::Behavior || r.cs!=state_.cpu.gameSegment)) ||
            (state_.outcome==ActorMotionOutcome::DivideError && (r.cs!=state_.cpu.gameSegment ||
                (r.ip!=0x70dc && r.ip!=0x70b4 && r.ip!=0x71e7 && r.ip!=0x73d2))))
            throw std::invalid_argument("Actor motion CPU/outcome ownership differs");
    }
    bool flag(uint32_t bit) const { return (state_.cpu.registers.flags&bit)!=0; }
    static uint32_t valueFlags(uint16_t value,bool byte=false) {
        return (value==0 ? 0x40u : 0u)|(value&(byte ? 128u : 32768u) ? 0x80u : 0u)|
            (std::popcount(static_cast<uint8_t>(value))%2==0 ? 4u : 0u);
    }
    uint16_t logic(uint16_t value,bool byte=false) {
        value=static_cast<uint16_t>(value&(byte ? 255u : 65535u));
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
    uint16_t increment(uint16_t value,bool subtract=false) {
        const auto carry=state_.cpu.registers.flags&1u;value=arithmetic(value,1,subtract);
        state_.cpu.registers.flags=(state_.cpu.registers.flags&~uint32_t{1})|carry;return value;
    }
    uint16_t shift(uint16_t value) {
        const auto result=static_cast<uint16_t>(value<<1);
        state_.cpu.registers.flags=(state_.cpu.registers.flags&~uint32_t{0x8d5})|valueFlags(result)|16u|
            (value&0x8000u ? 1u : 0u)|((value^result)&0x8000u ? 0x800u : 0u);return result;
    }
    void instruction(const TimerIrqBus& bus,const CopyBudget& copies) {
        auto& r=state_.cpu.registers;
        if (r.cs==library() && ((r.ip>=0x13a8 && r.ip<0x13bc) || (r.ip>=0x13f7 && r.ip<=0x142c))) {
            FrameSpawnerOperation child(FrameSpawnerSnapshot{r,state_.cpu.gameSegment});
            child.advance(1,bus);r=child.snapshot().registers;return;
        }
        if (r.cs==library() || (r.cs==state_.cpu.gameSegment &&
                ((r.ip>=0x346b && r.ip<=0x3584) || (r.ip>=0x710d && r.ip<=0x7129)))) {
            ActorSteeringOperation child(ActorSteeringSnapshot{ActorFinishSnapshot{r,state_.cpu.gameSegment,state_.cpu.idToggleMask}});
            child.advance(1,bus,copies);r=child.registers();return;
        }
        if (r.cs!=state_.cpu.gameSegment) throw std::domain_error("Actor motion left recovered code");
        if ((r.ip>=0x370e && r.ip<=0x3a53) || (r.ip>=0x5afd && r.ip<=0x5bc9)) {
            advanceActorTerrainInstruction(r,state_.cpu.gameSegment,bus);return;
        }
        if (r.ip>=0x165a && r.ip<=0x167d) {
            ActorContactOperation child(ActorContactSnapshot{r,state_.cpu.gameSegment,state_.cpu.idToggleMask});
            child.advance(1,bus);r=child.registers();return;
        }
        const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value); };
        const auto pop=[&] { const auto value=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return value; };
        const auto local=[&](int offset) { return bus.readWord(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto lb=[&](int offset) { return bus.readByte(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto store=[&](int offset,uint16_t value) { bus.writeWord(r.ss,static_cast<uint16_t>(r.bp+offset),value); };
        const auto sb=[&](int offset,uint8_t value) { bus.writeByte(r.ss,static_cast<uint16_t>(r.bp+offset),value); };
        const auto data=[&](uint16_t offset) { return bus.readByte(r.ds,offset); };
        const auto dw=[&](uint16_t offset) { return bus.readWord(r.ds,offset); };
        const auto wd=[&](uint16_t offset,uint16_t value) { bus.writeWord(r.ds,offset,value); };
        const auto bd=[&](uint16_t offset,uint8_t value) { bus.writeByte(r.ds,offset,value); };
        const auto les=[&](int offset) { r.di=local(offset);r.es=local(offset+2); };
        const auto word=[&](unsigned offset) { return bus.readWord(r.es,static_cast<uint16_t>(r.di+offset)); };
        const auto byte=[&](unsigned offset) { return bus.readByte(r.es,static_cast<uint16_t>(r.di+offset)); };
        const auto wb=[&](unsigned offset,uint8_t value) { bus.writeByte(r.es,static_cast<uint16_t>(r.di+offset),value); };
        const auto al=[&](uint16_t value) { r.ax=static_cast<uint16_t>((r.ax&0xff00u)|(value&255u)); };
        const auto cwd=[&] { r.dx=(r.ax&0x8000u) ? uint16_t{65535} : uint16_t{0}; };
        const auto less=[&] { return flag(0x80)!=flag(0x800); };
        const auto branch=[&](bool yes,uint16_t target,uint16_t next) { r.ip=yes ? target : next; };
        const auto call=[&](uint16_t target,uint16_t next) { push(next);r.ip=target; };
        const auto farCall=[&](uint16_t target,uint16_t next) { push(r.cs);push(next);r.cs=library();r.ip=target; };
        const auto divide=[&](uint16_t divisor,bool isSigned=false) {
            if (isSigned) {
                const int64_t numerator=std::bit_cast<int32_t>((uint32_t{r.dx}<<16)|r.ax);
                const auto denominator=std::bit_cast<int16_t>(divisor);
                if (!denominator || numerator/denominator < -32768 || numerator/denominator > 32767) {
                    state_.outcome=ActorMotionOutcome::DivideError;return false;
                }
                r.ax=static_cast<uint16_t>(numerator/denominator);r.dx=static_cast<uint16_t>(numerator%denominator);
            } else {
                const uint32_t numerator=(uint32_t{r.dx}<<16)|r.ax;
                if (!divisor || numerator/divisor>65535) { state_.outcome=ActorMotionOutcome::DivideError;return false; }
                r.ax=static_cast<uint16_t>(numerator/divisor);r.dx=static_cast<uint16_t>(numerator%divisor);
            }
            return true;
        };
        switch (r.ip) {
        case 0x7018:arithmetic(r.ax&255u,2,true,true);r.ip=0x701a;break;
        case 0x701a:branch(!flag(0x40),0x705b,0x701c);break;
        case 0x701c:arithmetic(lb(-33),0,true,true);r.ip=0x7020;break;
        case 0x7020:branch(flag(0x40),0x7028,0x7022);break;
        case 0x7022:arithmetic(local(-14),0,true);r.ip=0x7026;break;
        case 0x7026:branch(!less(),0x703a,0x7028);break;
        case 0x7028:store(-14,arithmetic(local(-14),64));r.ip=0x702c;break;
        case 0x702c:arithmetic(local(-14),2047,true);r.ip=0x7031;break;
        case 0x7031:branch(flag(0x40)||less(),0x7038,0x7033);break;
        case 0x7033:store(-14,2047);r.ip=0x7038;break;
        case 0x7038:r.ip=0x704e;break;
        case 0x703a:arithmetic(local(-14),0,true);r.ip=0x703e;break;
        case 0x703e:branch(flag(0x40)||less(),0x704e,0x7040);break;
        case 0x7040:r.ax=logic(0);r.ip=0x7042;break;
        case 0x7042:store(-14,r.ax);r.ip=0x7045;break;
        case 0x7045:r.ax=local(-46);r.ip=0x7048;break;
        case 0x7048:r.ax=logic(r.ax&0xfff8u);r.ip=0x704b;break;
        case 0x704b:store(-46,r.ax);r.ip=0x704e;break;
        case 0x704e:arithmetic(lb(-33),0,true,true);r.ip=0x7052;break;
        case 0x7052:branch(flag(0x40),0x7058,0x7054);break;
        case 0x7054:push(r.bp);r.ip=0x7055;break;
        case 0x7055:call(0x5b86,0x7058);break;
        case 0x7058:r.ip=0x732c;break;
        case 0x705b:arithmetic(r.ax&255u,4,true,true);r.ip=0x705d;break;
        case 0x705d:branch(flag(0x40),0x7062,0x705f);break;
        case 0x705f:r.ip=0x7152;break;
        case 0x7062:arithmetic(data(0x2055),1,true,true);r.ip=0x7067;break;
        case 0x7067:branch(flag(1),0x7076,0x7069);break;
        case 0x7069:arithmetic(data(0x2055),76,true,true);r.ip=0x706e;break;
        case 0x706e:branch(!flag(1)&&!flag(0x40),0x7076,0x7070);break;
        case 0x7070:sb(-30,1);r.ip=0x7074;break;
        case 0x7074:r.ip=0x708e;break;
        case 0x7076:arithmetic(data(0x2056),1,true,true);r.ip=0x707b;break;
        case 0x707b:branch(flag(1),0x708a,0x707d);break;
        case 0x707d:arithmetic(data(0x2056),76,true,true);r.ip=0x7082;break;
        case 0x7082:branch(!flag(1)&&!flag(0x40),0x708a,0x7084);break;
        case 0x7084:sb(-30,1);r.ip=0x7088;break;
        case 0x7088:r.ip=0x708e;break;
        case 0x708a:sb(-30,0);r.ip=0x708e;break;
        case 0x708e:arithmetic(lb(-30),0,true,true);r.ip=0x7092;break;
        case 0x7092:branch(flag(0x40),0x709f,0x7094);break;
        case 0x7094:arithmetic(lb(-34),0,true,true);r.ip=0x7098;break;
        case 0x7098:branch(flag(0x40),0x709f,0x709a);break;
        case 0x709a:r.ax=logic(0);r.ip=0x709c;break;
        case 0x709c:store(-14,r.ax);r.ip=0x709f;break;
        case 0x709f:arithmetic(lb(-30),0,true,true);r.ip=0x70a3;break;
        case 0x70a3:branch(flag(0x40),0x70b9,0x70a5);break;
        case 0x70a5:arithmetic(local(-14),0,true);r.ip=0x70a9;break;
        case 0x70a9:branch(flag(0x40)||less(),0x70b9,0x70ab);break;
        case 0x70ab:r.ax=local(-14);r.ip=0x70ae;break;
        case 0x70ae:r.ax=arithmetic(0,r.ax,true);r.ip=0x70b0;break;
        case 0x70b0:cwd();r.ip=0x70b1;break;
        case 0x70b1:r.cx=2;r.ip=0x70b4;break;
        case 0x70b4:if (divide(r.cx,true)) r.ip=0x70b6;break;
        case 0x70b6:store(-14,r.ax);r.ip=0x70b9;break;
        case 0x70b9:les(4);r.ip=0x70bc;break;
        case 0x70bc:r.ax=word(14);r.ip=0x70c0;break;
        case 0x70c0:wd(0xc1e8,r.ax);r.ip=0x70c3;break;
        case 0x70c3:les(4);r.ip=0x70c6;break;
        case 0x70c6:r.ax=word(16);r.ip=0x70ca;break;
        case 0x70ca:wd(0x2074,r.ax);r.ip=0x70cd;break;
        case 0x70cd:les(4);r.ip=0x70d0;break;
        case 0x70d0:r.ax=word(18);r.ip=0x70d4;break;
        case 0x70d4:wd(0x2072,r.ax);r.ip=0x70d7;break;
        case 0x70d7:r.ax=dw(0x78c2);r.ip=0x70da;break;
        case 0x70da:r.dx=logic(0);r.ip=0x70dc;break;
        case 0x70dc:if (divide(dw(0xc1e8))) r.ip=0x70e0;break;
        case 0x70e0:std::swap(r.ax,r.dx);r.ip=0x70e1;break;
        case 0x70e1:logic(r.ax);r.ip=0x70e3;break;
        case 0x70e3:branch(!flag(0x40),0x714f,0x70e5);break;
        case 0x70e5:r.ax=dw(0x2072);r.ip=0x70e8;break;
        case 0x70e8:r.dx=logic(0);r.ip=0x70ea;break;
        case 0x70ea:push(r.dx);r.ip=0x70eb;break;
        case 0x70eb:push(r.ax);r.ip=0x70ec;break;
        case 0x70ec:r.ax=local(-6);r.ip=0x70ef;break;
        case 0x70ef:cwd();r.ip=0x70f0;break;
        case 0x70f0:r.ax=logic(r.ax^r.dx);r.ip=0x70f2;break;
        case 0x70f2:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x70f4;break;
        case 0x70f4:r.cx=r.ax;r.ip=0x70f6;break;
        case 0x70f6:r.ax=local(-4);r.ip=0x70f9;break;
        case 0x70f9:cwd();r.ip=0x70fa;break;
        case 0x70fa:r.ax=logic(r.ax^r.dx);r.ip=0x70fc;break;
        case 0x70fc:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x70fe;break;
        case 0x70fe:r.ax=arithmetic(r.ax,r.cx);r.ip=0x7100;break;
        case 0x7100:cwd();r.ip=0x7101;break;
        case 0x7101:r.cx=pop();r.ip=0x7102;break;
        case 0x7102:r.bx=pop();r.ip=0x7103;break;
        case 0x7103:arithmetic(r.dx,r.bx,true);r.ip=0x7105;break;
        case 0x7105:branch(less(),0x710d,0x7107);break;
        case 0x7107:branch(!flag(0x40)&&!less(),0x712b,0x7109);break;
        case 0x7109:arithmetic(r.ax,r.cx,true);r.ip=0x710b;break;
        case 0x710b:branch(!flag(1),0x712b,0x710d);break;
        case 0x712b:r.ax=dw(0x2074);r.ip=0x712e;break;
        case 0x712e:r.ax=shift(r.ax);r.ip=0x7130;break;
        case 0x7130:push(r.ax);r.ip=0x7131;break;
        case 0x7131:farCall(0x13a8,0x7136);break;
        case 0x7136:r.ax=arithmetic(r.ax,dw(0x2074),true);r.ip=0x713a;break;
        case 0x713a:store(-12,r.ax);r.ip=0x713d;break;
        case 0x713d:r.ax=dw(0x2074);r.ip=0x7140;break;
        case 0x7140:r.ax=shift(r.ax);r.ip=0x7142;break;
        case 0x7142:push(r.ax);r.ip=0x7143;break;
        case 0x7143:farCall(0x13a8,0x7148);break;
        case 0x7148:r.ax=arithmetic(r.ax,dw(0x2074),true);r.ip=0x714c;break;
        case 0x714c:store(-14,r.ax);r.ip=0x714f;break;
        case 0x714f:r.ip=0x732c;break;
        case 0x7152:arithmetic(r.ax&255u,3,true,true);r.ip=0x7154;break;
        case 0x7154:branch(flag(0x40),0x7159,0x7156);break;
        case 0x7156:r.ip=0x732c;break;
        case 0x7159:arithmetic(lb(-35),0,true,true);r.ip=0x715d;break;
        case 0x715d:branch(!flag(0x40),0x7169,0x715f);break;
        case 0x715f:arithmetic(lb(-36),0,true,true);r.ip=0x7163;break;
        case 0x7163:branch(!flag(0x40),0x7169,0x7165);break;
        case 0x7165:al(0);r.ip=0x7167;break;
        case 0x7167:r.ip=0x716b;break;
        case 0x7169:al(1);r.ip=0x716b;break;
        case 0x716b:sb(-32,static_cast<uint8_t>(r.ax));r.ip=0x716e;break;
        case 0x716e:arithmetic(lb(-33),0,true,true);r.ip=0x7172;break;
        case 0x7172:branch(flag(0x40),0x717a,0x7174);break;
        case 0x7174:arithmetic(local(-14),0,true);r.ip=0x7178;break;
        case 0x7178:branch(!less(),0x718c,0x717a);break;
        case 0x717a:store(-14,arithmetic(local(-14),64));r.ip=0x717e;break;
        case 0x717e:arithmetic(local(-14),2047,true);r.ip=0x7183;break;
        case 0x7183:branch(flag(0x40)||less(),0x718a,0x7185);break;
        case 0x7185:store(-14,2047);r.ip=0x718a;break;
        case 0x718a:r.ip=0x71a4;break;
        case 0x718c:arithmetic(local(-14),0,true);r.ip=0x7190;break;
        case 0x7190:branch(flag(0x40)||less(),0x71a4,0x7192);break;
        case 0x7192:r.ax=logic(0);r.ip=0x7194;break;
        case 0x7194:store(-14,r.ax);r.ip=0x7197;break;
        case 0x7197:r.ax=local(-46);r.ip=0x719a;break;
        case 0x719a:r.ax=logic(r.ax&0xfff8u);r.ip=0x719d;break;
        case 0x719d:store(-46,r.ax);r.ip=0x71a0;break;
        case 0x71a0:sb(-32,1);r.ip=0x71a4;break;
        case 0x71a4:arithmetic(lb(-33),0,true,true);r.ip=0x71a8;break;
        case 0x71a8:branch(!flag(0x40),0x71ad,0x71aa);break;
        case 0x71aa:r.ip=0x727d;break;
        case 0x71ad:arithmetic(local(-12),0,true);r.ip=0x71b1;break;
        case 0x71b1:branch(flag(0x40),0x71f9,0x71b3);break;
        case 0x71b3:les(4);r.ip=0x71b6;break;
        case 0x71b6:r.ax=word(14);r.ip=0x71ba;break;
        case 0x71ba:r.dx=logic(0);r.ip=0x71bc;break;
        case 0x71bc:r.cx=r.ax;r.ip=0x71be;break;
        case 0x71be:r.bx=r.dx;r.ip=0x71c0;break;
        case 0x71c0:r.ax=local(-12);r.ip=0x71c3;break;
        case 0x71c3:cwd();r.ip=0x71c4;break;
        case 0x71c4:r.ax=logic(r.ax^r.dx);r.ip=0x71c6;break;
        case 0x71c6:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x71c8;break;
        case 0x71c8:cwd();r.ip=0x71c9;break;
        case 0x71c9:arithmetic(r.dx,r.bx,true);r.ip=0x71cb;break;
        case 0x71cb:branch(!flag(0x40),0x71d1,0x71cd);break;
        case 0x71cd:arithmetic(r.ax,r.cx,true);r.ip=0x71cf;break;
        case 0x71cf:branch(flag(0x40),0x71f7,0x71d1);break;
        case 0x71d1:les(4);r.ip=0x71d4;break;
        case 0x71d4:r.ax=word(14);r.ip=0x71d8;break;
        case 0x71d8:r.dx=logic(0);r.ip=0x71da;break;
        case 0x71da:r.cx=r.ax;r.ip=0x71dc;break;
        case 0x71dc:r.bx=r.dx;r.ip=0x71de;break;
        case 0x71de:r.ax=local(-12);r.ip=0x71e1;break;
        case 0x71e1:cwd();r.ip=0x71e2;break;
        case 0x71e2:r.ax=logic(r.ax^r.dx);r.ip=0x71e4;break;
        case 0x71e4:r.ax=arithmetic(r.ax,r.dx,true);r.ip=0x71e6;break;
        case 0x71e6:cwd();r.ip=0x71e7;break;
        case 0x71e7:if (divide(local(-12),true)) r.ip=0x71ea;break;
        case 0x71ea:cwd();r.ip=0x71eb;break;
        case 0x71eb:farCall(0x92a,0x71f0);break;
        case 0x71f0:store(-12,r.ax);r.ip=0x71f3;break;
        case 0x71f3:sb(-32,1);r.ip=0x71f7;break;
        case 0x71f7:r.ip=0x7203;break;
        case 0x71f9:les(4);r.ip=0x71fc;break;
        case 0x71fc:r.ax=word(14);r.ip=0x7200;break;
        case 0x7200:store(-12,r.ax);r.ip=0x7203;break;
        case 0x7203:arithmetic(data(0x2054),1,true,true);r.ip=0x7208;break;
        case 0x7208:branch(flag(1),0x7215,0x720a);break;
        case 0x720a:arithmetic(data(0x2054),82,true,true);r.ip=0x720f;break;
        case 0x720f:branch(!flag(1)&&!flag(0x40),0x7215,0x7211);break;
        case 0x7211:al(0);r.ip=0x7213;break;
        case 0x7213:r.ip=0x7217;break;
        case 0x7215:al(1);r.ip=0x7217;break;
        case 0x7217:sb(-30,static_cast<uint8_t>(r.ax));r.ip=0x721a;break;
        case 0x721a:arithmetic(data(0x2057),1,true,true);r.ip=0x721f;break;
        case 0x721f:branch(flag(1),0x722c,0x7221);break;
        case 0x7221:arithmetic(data(0x2057),82,true,true);r.ip=0x7226;break;
        case 0x7226:branch(!flag(1)&&!flag(0x40),0x722c,0x7228);break;
        case 0x7228:al(0);r.ip=0x722a;break;
        case 0x722a:r.ip=0x722e;break;
        case 0x722c:al(1);r.ip=0x722e;break;
        case 0x722e:sb(-31,static_cast<uint8_t>(r.ax));r.ip=0x7231;break;
        case 0x7231:arithmetic(lb(-30),0,true,true);r.ip=0x7235;break;
        case 0x7235:branch(!flag(0x40),0x723d,0x7237);break;
        case 0x7237:arithmetic(lb(-31),0,true,true);r.ip=0x723b;break;
        case 0x723b:branch(flag(0x40),0x7241,0x723d);break;
        case 0x723d:sb(-32,1);r.ip=0x7241;break;
        case 0x7241:arithmetic(lb(-30),0,true,true);r.ip=0x7245;break;
        case 0x7245:branch(flag(0x40),0x724d,0x7247);break;
        case 0x7247:arithmetic(lb(-31),0,true,true);r.ip=0x724b;break;
        case 0x724b:branch(!flag(0x40),0x727d,0x724d);break;
        case 0x724d:arithmetic(local(-12),0,true);r.ip=0x7251;break;
        case 0x7251:branch(!less(),0x7269,0x7253);break;
        case 0x7253:r.ax=local(-48);r.ip=0x7256;break;
        case 0x7256:store(-44,r.ax);r.ip=0x7259;break;
        case 0x7259:arithmetic(lb(-30),0,true,true);r.ip=0x725d;break;
        case 0x725d:branch(flag(0x40),0x7267,0x725f);break;
        case 0x725f:r.ax=local(-12);r.ip=0x7262;break;
        case 0x7262:r.ax=arithmetic(0,r.ax,true);r.ip=0x7264;break;
        case 0x7264:store(-12,r.ax);r.ip=0x7267;break;
        case 0x7267:r.ip=0x727d;break;
        case 0x7269:r.ax=local(-48);r.ip=0x726c;break;
        case 0x726c:store(-44,r.ax);r.ip=0x726f;break;
        case 0x726f:arithmetic(lb(-31),0,true,true);r.ip=0x7273;break;
        case 0x7273:branch(flag(0x40),0x727d,0x7275);break;
        case 0x7275:r.ax=local(-12);r.ip=0x7278;break;
        case 0x7278:r.ax=arithmetic(0,r.ax,true);r.ip=0x727a;break;
        case 0x727a:store(-12,r.ax);r.ip=0x727d;break;
        case 0x727d:arithmetic(lb(-32),0,true,true);r.ip=0x7281;break;
        case 0x7281:branch(!flag(0x40),0x7286,0x7283);break;
        case 0x7283:r.ip=0x732c;break;
        case 0x7286:arithmetic(local(-12),0,true);r.ip=0x728a;break;
        case 0x728a:branch(!less(),0x72da,0x728c);break;
        case 0x728c:les(4);r.ip=0x728f;break;
        case 0x728f:al(byte(3));r.ip=0x7293;break;
        case 0x7293:sb(-18,static_cast<uint8_t>(r.ax));r.ip=0x7296;break;
        case 0x7296:les(4);r.ip=0x7299;break;
        case 0x7299:r.di=arithmetic(r.di,22);r.ip=0x729d;break;
        case 0x729d:store(-58,r.di);r.ip=0x72a0;break;
        case 0x72a0:store(-56,r.es);r.ip=0x72a3;break;
        case 0x72a3:al(lb(-18));r.ip=0x72a6;break;
        case 0x72a6:r.ax&=255u;logic(0,true);r.ip=0x72a8;break;
        case 0x72a8:r.di=r.ax;r.ip=0x72aa;break;
        case 0x72aa:r.di=shift(r.di);r.ip=0x72ac;break;
        case 0x72ac:al(data(static_cast<uint16_t>(r.di+0x58u)));r.ip=0x72b0;break;
        case 0x72b0:les(-58);r.ip=0x72b3;break;
        case 0x72b3:wb(1,static_cast<uint8_t>(r.ax));r.ip=0x72b7;break;
        case 0x72b7:al(lb(-18));r.ip=0x72ba;break;
        case 0x72ba:r.ax&=255u;logic(0,true);r.ip=0x72bc;break;
        case 0x72bc:r.di=r.ax;r.ip=0x72be;break;
        case 0x72be:r.di=shift(r.di);r.ip=0x72c0;break;
        case 0x72c0:al(data(static_cast<uint16_t>(r.di+0x59u)));r.ip=0x72c4;break;
        case 0x72c4:les(-58);r.ip=0x72c7;break;
        case 0x72c7:wb(2,static_cast<uint8_t>(r.ax));r.ip=0x72cb;break;
        case 0x72cb:les(-58);r.ip=0x72ce;break;
        case 0x72ce:al(byte(1));r.ip=0x72d2;break;
        case 0x72d2:les(-58);r.ip=0x72d5;break;
        case 0x72d5:wb(0,static_cast<uint8_t>(r.ax));r.ip=0x72d8;break;
        case 0x72d8:r.ip=0x732c;break;
        case 0x72da:arithmetic(local(-12),0,true);r.ip=0x72de;break;
        case 0x72de:branch(flag(0x40)||less(),0x732c,0x72e0);break;
        case 0x72e0:les(4);r.ip=0x72e3;break;
        case 0x72e3:al(byte(4));r.ip=0x72e7;break;
        case 0x72e7:sb(-18,static_cast<uint8_t>(r.ax));r.ip=0x72ea;break;
        case 0x72ea:les(4);r.ip=0x72ed;break;
        case 0x72ed:r.di=arithmetic(r.di,22);r.ip=0x72f1;break;
        case 0x72f1:store(-58,r.di);r.ip=0x72f4;break;
        case 0x72f4:store(-56,r.es);r.ip=0x72f7;break;
        case 0x72f7:al(lb(-18));r.ip=0x72fa;break;
        case 0x72fa:r.ax&=255u;logic(0,true);r.ip=0x72fc;break;
        case 0x72fc:r.di=r.ax;r.ip=0x72fe;break;
        case 0x72fe:r.di=shift(r.di);r.ip=0x7300;break;
        case 0x7300:al(data(static_cast<uint16_t>(r.di+0x58u)));r.ip=0x7304;break;
        case 0x7304:les(-58);r.ip=0x7307;break;
        case 0x7307:wb(1,static_cast<uint8_t>(r.ax));r.ip=0x730b;break;
        case 0x730b:al(lb(-18));r.ip=0x730e;break;
        case 0x730e:r.ax&=255u;logic(0,true);r.ip=0x7310;break;
        case 0x7310:r.di=r.ax;r.ip=0x7312;break;
        case 0x7312:r.di=shift(r.di);r.ip=0x7314;break;
        case 0x7314:al(data(static_cast<uint16_t>(r.di+0x59u)));r.ip=0x7318;break;
        case 0x7318:les(-58);r.ip=0x731b;break;
        case 0x731b:wb(2,static_cast<uint8_t>(r.ax));r.ip=0x731f;break;
        case 0x731f:les(-58);r.ip=0x7322;break;
        case 0x7322:al(byte(1));r.ip=0x7326;break;
        case 0x7326:les(-58);r.ip=0x7329;break;
        case 0x7329:wb(0,static_cast<uint8_t>(r.ax));r.ip=0x732c;break;
        case 0x732c:arithmetic(lb(-15),4,true,true);r.ip=0x7330;break;
        case 0x7330:branch(!flag(0x40),0x738f,0x7332);break;
        case 0x7332:r.ax=local(-42);r.ip=0x7335;break;
        case 0x7335:r.ax=arithmetic(r.ax,dw(0xc204));r.ip=0x7339;break;
        case 0x7339:wd(0xc1e8,r.ax);r.ip=0x733c;break;
        case 0x733c:r.ax=logic(0);r.ip=0x733e;break;
        case 0x733e:wd(0x2074,r.ax);r.ip=0x7341;break;
        case 0x7341:push(r.bp);r.ip=0x7342;break;
        case 0x7342:call(0x5afd,0x7345);break;
        case 0x7345:r.ax=dw(0x2072);r.ip=0x7348;break;
        case 0x7348:wd(0x2074,arithmetic(dw(0x2074),r.ax));r.ip=0x734c;break;
        case 0x734c:arithmetic(data(0x661e),1,true,true);r.ip=0x7351;break;
        case 0x7351:branch(!flag(0x40),0x7367,0x7353);break;
        case 0x7353:r.ax=dw(0xc1e8);r.ip=0x7356;break;
        case 0x7356:r.ax=arithmetic(r.ax,dw(0xc204),true);r.ip=0x735a;break;
        case 0x735a:push(r.ax);r.ip=0x735b;break;
        case 0x735b:push(0);r.ip=0x735d;break;
        case 0x735d:push(0);r.ip=0x735f;break;
        case 0x735f:r.di=static_cast<uint16_t>(r.bp-18u);r.ip=0x7362;break;
        case 0x7362:push(r.ss);r.ip=0x7363;break;
        case 0x7363:push(r.di);r.ip=0x7364;break;
        case 0x7364:call(0x370e,0x7367);break;
        case 0x7367:r.ax=dw(0xc204);r.ip=0x736a;break;
        case 0x736a:r.ax=increment(r.ax);r.ip=0x736b;break;
        case 0x736b:wd(0xc1e8,arithmetic(dw(0xc1e8),r.ax));r.ip=0x736f;break;
        case 0x736f:push(r.bp);r.ip=0x7370;break;
        case 0x7370:call(0x5afd,0x7373);break;
        case 0x7373:r.ax=dw(0x2072);r.ip=0x7376;break;
        case 0x7376:wd(0x2074,arithmetic(dw(0x2074),r.ax));r.ip=0x737a;break;
        case 0x737a:arithmetic(dw(0x2074),0,true);r.ip=0x737f;break;
        case 0x737f:branch(flag(1)||flag(0x40),0x738f,0x7381);break;
        case 0x7381:bd(0x799f,1);r.ip=0x7386;break;
        case 0x7386:wd(0x2074,33);r.ip=0x738c;break;
        case 0x738c:call(0x165a,0x738f);break;
        case 0x738f:arithmetic(lb(-34),0,true,true);r.ip=0x7393;break;
        case 0x7393:branch(flag(0x40),0x73a0,0x7395);break;
        case 0x7395:arithmetic(local(-14),0,true);r.ip=0x7399;break;
        case 0x7399:branch(!less(),0x73a0,0x739b);break;
        case 0x739b:store(-14,1);r.ip=0x73a0;break;
        case 0x73a0:arithmetic(lb(-35),0,true,true);r.ip=0x73a4;break;
        case 0x73a4:branch(flag(0x40),0x73b1,0x73a6);break;
        case 0x73a6:arithmetic(lb(-36),0,true,true);r.ip=0x73aa;break;
        case 0x73aa:branch(flag(0x40),0x73b1,0x73ac);break;
        case 0x73ac:r.ax=logic(0);r.ip=0x73ae;break;
        case 0x73ae:store(-12,r.ax);r.ip=0x73b1;break;
        case 0x73b1:arithmetic(lb(-35),0,true,true);r.ip=0x73b5;break;
        case 0x73b5:branch(flag(0x40),0x73bd,0x73b7);break;
        case 0x73b7:arithmetic(local(-12),0,true);r.ip=0x73bb;break;
        case 0x73bb:branch(less(),0x73c9,0x73bd);break;
        case 0x73bd:arithmetic(lb(-36),0,true,true);r.ip=0x73c1;break;
        case 0x73c1:branch(flag(0x40),0x73e5,0x73c3);break;
        case 0x73c3:arithmetic(local(-12),0,true);r.ip=0x73c7;break;
        case 0x73c7:branch(flag(0x40)||less(),0x73e5,0x73c9);break;
        case 0x73c9:r.ax=local(-12);r.ip=0x73cc;break;
        case 0x73cc:r.ax=arithmetic(0,r.ax,true);r.ip=0x73ce;break;
        case 0x73ce:cwd();r.ip=0x73cf;break;
        case 0x73cf:r.cx=2;r.ip=0x73d2;break;
        case 0x73d2:if (divide(r.cx,true)) r.ip=0x73d4;break;
        case 0x73d4:store(-12,r.ax);r.ip=0x73d7;break;
        case 0x73d7:arithmetic(local(-12),0,true);r.ip=0x73db;break;
        case 0x73db:branch(!less(),0x73e2,0x73dd);break;
        case 0x73dd:store(-44,increment(local(-44),true));r.ip=0x73e0;break;
        case 0x73e0:r.ip=0x73e5;break;
        case 0x73e2:store(-44,increment(local(-44)));r.ip=0x73e5;break;
        default:throw std::domain_error("Actor motion left recovered game instructions");
        }
    }
};

} // namespace lezac::core
