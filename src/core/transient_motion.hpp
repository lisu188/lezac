#pragma once

#include "core/actor_finish.hpp"

namespace lezac::core {

enum class TransientMotionOutcome { Running, Returned };
struct TransientMotionSnapshot {
    ActorFinishSnapshot cpu;
    uint16_t callerSs=0,callerSp=0,callerBp=0;
    TransientMotionOutcome outcome=TransientMotionOutcome::Running;
    bool operator==(const TransientMotionSnapshot&) const = default;
};

// Original 3EDA..3F26 shared spark/debris byte accumulators and near return.
class TransientMotionOperation {
public:
    TransientMotionOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        :state_{ActorFinishSnapshot{r,game,idToggle},r.ss,static_cast<uint16_t>(r.sp+2u),r.bp} {
        if (r.cs!=game || r.ip!=0x3eda) throw std::invalid_argument("Transient motion entry differs");
        validate();
    }
    explicit TransientMotionOperation(TransientMotionSnapshot state):state_(std::move(state)) { validate(); }
    const TransientMotionSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const { return ActorFinishOperation(state_.cpu).registers(); }
    bool finished() const noexcept { return state_.outcome==TransientMotionOutcome::Returned; }
    bool interruptInProgress() const noexcept { return state_.cpu.timer.has_value(); }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished transient motion admitted IRQ");
        ActorFinishOperation irq(state_.cpu);irq.deliverTimerInterrupt(bus);state_.cpu=irq.snapshot();
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (state_.cpu.timer) {
                ActorFinishOperation irq(state_.cpu);
                if (irq.advance(1,bus,[](uint16_t n) { return n; })!=1)
                    throw std::domain_error("Transient motion IRQ did not dispatch");
                state_.cpu=irq.snapshot();
            } else { instruction(bus);++state_.cpu.dispatchedInstructions; }
            ++used;
        }
        return used;
    }
private:
    TransientMotionSnapshot state_;
    static bool boundary(uint16_t ip) {
        switch (ip) {
        case 0x3eda:case 0x3edd:case 0x3ee1:case 0x3ee4:case 0x3ee6:case 0x3ee8:
        case 0x3eeb:case 0x3eed:case 0x3eef:case 0x3ef2:case 0x3ef6:case 0x3ef8:
        case 0x3efc:case 0x3f00:case 0x3f03:case 0x3f07:case 0x3f0b:case 0x3f0d:
        case 0x3f0f:case 0x3f11:case 0x3f13:case 0x3f15:case 0x3f18:case 0x3f1c:
        case 0x3f1e:case 0x3f22:case 0x3f26:return true;
        default:return false;
        }
    }
    void validate() const {
        (void)ActorFinishOperation(state_.cpu);
        const auto& cpu=state_.cpu;const auto& r=cpu.registers;
        if ((state_.outcome!=TransientMotionOutcome::Running && state_.outcome!=TransientMotionOutcome::Returned) ||
            cpu.outcome!=ActorFinishOutcome::Running || cpu.transferredBytes ||
            r.cs!=cpu.gameSegment || r.ds!=static_cast<uint16_t>(cpu.gameSegment+0xaa2) ||
            r.ss!=state_.callerSs || r.bp!=state_.callerBp ||
            r.sp!=(finished() ? state_.callerSp : static_cast<uint16_t>(state_.callerSp-2u)) ||
            (!finished() && !boundary(r.ip)) || cpu.timerInstructions>cpu.dispatchedInstructions ||
            (!cpu.timerDeliveries && (cpu.timerInstructions || cpu.timer)) ||
            (cpu.timerDeliveries>cpu.timerInstructions && cpu.timerDeliveries-cpu.timerInstructions>(cpu.timer ? 1u : 0u)) ||
            (cpu.timer && (finished() || cpu.timer->registers.ss!=state_.callerSs ||
                cpu.timer->dispatchedInstructions>cpu.timerInstructions)))
            throw std::invalid_argument("Transient motion CPU/caller ownership differs");
    }
    bool flag(uint32_t bit) const { return (state_.cpu.registers.flags&bit)!=0; }
    uint16_t arithmetic(uint16_t a,uint16_t b,bool subtract=false,bool byte=false) {
        const uint32_t mask=byte ? 255u : 65535u,sign=byte ? 128u : 32768u;
        const uint32_t wide=subtract ? uint32_t{a}-b : uint32_t{a}+b;
        const auto value=static_cast<uint16_t>(wide&mask);
        uint32_t f=(value==0 ? 0x40u : 0u)|(value&sign ? 0x80u : 0u)|
            (std::popcount(static_cast<uint8_t>(value))%2==0 ? 4u : 0u)|((a^b^value)&16u);
        if (subtract ? a<b : wide>mask) f|=1;
        if (subtract ? ((a^b)&(a^value)&sign) : (~(a^b)&(a^value)&sign)) f|=0x800;
        state_.cpu.registers.flags=(state_.cpu.registers.flags&~uint32_t{0x8d5})|f;return value;
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r=state_.cpu.registers;
        const auto data=[&](uint16_t at) { return bus.readByte(r.ds,at); };
        const auto al=[&](uint8_t value) { r.ax=static_cast<uint16_t>((r.ax&0xff00u)|value); };
        const auto ah=[&](uint8_t value) { r.ax=static_cast<uint16_t>((r.ax&255u)|(uint16_t{value}<<8)); };
        const auto less=[&] { return flag(0x80)!=flag(0x800); };
        switch (r.ip) {
        case 0x3eda:al(data(0x78d2));r.ip=0x3edd;break;
        case 0x3edd:ah(data(0x78d3));r.ip=0x3ee1;break;
        case 0x3ee1:r.bx=1;r.ip=0x3ee4;break;
        case 0x3ee4:arithmetic(r.ax&255u,0,true,true);r.ip=0x3ee6;break;
        case 0x3ee6:r.ip=!less() ? 0x3eeb : 0x3ee8;break;
        case 0x3ee8:r.bx=65535;r.ip=0x3eeb;break;
        case 0x3eeb:case 0x3f11:ah(static_cast<uint8_t>(arithmetic(r.ax>>8,r.ax&255u,false,true)));r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x3eed:r.ip=!flag(0x800) ? 0x3efc : 0x3eef;break;
        case 0x3eef:case 0x3f15:ah(static_cast<uint8_t>(arithmetic(r.ax>>8,128,true,true)));r.ip=static_cast<uint16_t>(r.ip+3u);break;
        case 0x3ef2:case 0x3f18:r.cx=bus.readWord(r.ds,0x2090);r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x3ef6:case 0x3f1c:r.cx=arithmetic(r.cx,r.bx);r.ip=static_cast<uint16_t>(r.ip+2u);break;
        case 0x3ef8:case 0x3f1e:bus.writeWord(r.ds,0x2090,r.cx);r.ip=static_cast<uint16_t>(r.ip+4u);break;
        case 0x3efc:bus.writeByte(r.ds,0x78d3,static_cast<uint8_t>(r.ax>>8));r.ip=0x3f00;break;
        case 0x3f00:al(data(0x78d4));r.ip=0x3f03;break;
        case 0x3f03:ah(data(0x78d5));r.ip=0x3f07;break;
        case 0x3f07:r.bx=bus.readWord(r.ds,0xc204);r.ip=0x3f0b;break;
        case 0x3f0b:arithmetic(r.ax&255u,0,true,true);r.ip=0x3f0d;break;
        case 0x3f0d:r.ip=!less() ? 0x3f11 : 0x3f0f;break;
        case 0x3f0f:r.bx=arithmetic(0,r.bx,true);r.ip=0x3f11;break;
        case 0x3f13:r.ip=!flag(0x800) ? 0x3f22 : 0x3f15;break;
        case 0x3f22:bus.writeByte(r.ds,0x78d5,static_cast<uint8_t>(r.ax>>8));r.ip=0x3f26;break;
        case 0x3f26:r.ip=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);state_.outcome=TransientMotionOutcome::Returned;break;
        default:throw std::domain_error("Transient motion left recovered code");
        }
    }
};

} // namespace lezac::core
