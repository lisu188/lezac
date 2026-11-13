#pragma once

#include "core/actor_finish.hpp"

namespace lezac::core {

enum class TransientRemovalKind { Spark, Debris };
enum class TransientRemovalOutcome { Running, Returned, RuntimeError };
struct TransientRemovalSnapshot {
    ActorFinishSnapshot cpu;
    TransientRemovalKind kind=TransientRemovalKind::Spark;
    uint16_t callerSs=0,callerSp=0,callerBp=0;
    TransientRemovalOutcome outcome=TransientRemovalOutcome::Running;
    bool operator==(const TransientRemovalSnapshot&) const = default;
};

// Original 452A/458D near calls, including physical copies and RET 4.
class TransientRemovalOperation {
public:
    using CopyBudget=ActorFinishOperation::CopyBudget;
    TransientRemovalOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        :state_{ActorFinishSnapshot{r,game,idToggle},
            r.ip==0x452a ? TransientRemovalKind::Spark : TransientRemovalKind::Debris,
            r.ss,static_cast<uint16_t>(r.sp+6u),r.bp} {
        if (r.cs!=game || (r.ip!=0x452a && r.ip!=0x458d))
            throw std::invalid_argument("Transient removal entry differs");
        validate();
    }
    explicit TransientRemovalOperation(TransientRemovalSnapshot state):state_(std::move(state)) { validate(); }
    const TransientRemovalSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const { return ActorFinishOperation(state_.cpu).registers(); }
    bool finished() const noexcept { return state_.outcome!=TransientRemovalOutcome::Running; }
    bool interruptInProgress() const noexcept { return state_.cpu.timer.has_value(); }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished transient removal admitted IRQ");
        ActorFinishOperation irq(state_.cpu);irq.deliverTimerInterrupt(bus);state_.cpu=irq.snapshot();
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            if (state_.cpu.timer) {
                ActorFinishOperation irq(state_.cpu);
                if (irq.advance(1,bus,copies)!=1) throw std::domain_error("Transient removal IRQ did not dispatch");
                state_.cpu=irq.snapshot();
            } else {
                instruction(bus,copies);++state_.cpu.dispatchedInstructions;
                if (state_.cpu.registers.cs==library() && state_.cpu.registers.ip==0xe2)
                    state_.outcome=TransientRemovalOutcome::RuntimeError;
            }
            ++used;
        }
        return used;
    }
private:
    TransientRemovalSnapshot state_;
    uint16_t library() const { return static_cast<uint16_t>(state_.cpu.gameSegment+0x920); }
    bool spark() const { return state_.kind==TransientRemovalKind::Spark; }
    static bool libraryBoundary(uint16_t ip) {
        switch (ip) {
        case 0x4df:case 0x4e2:case 0x4e4:case 0x4e6:case 0x4e8:
        case 0x4ea:case 0x4ee:case 0x4f0:case 0x4f1:case 0x4f4:return true;
        default:return false;
        }
    }
    bool gameBoundary(uint16_t ip) const {
        if (!spark()) {
            if (ip>=0x458d && ip<=0x45ce) ip=static_cast<uint16_t>(ip-0x63u);
            else switch (ip) {
            case 0x45d0:case 0x45d3:case 0x45d4:case 0x45d6:case 0x45d8:
            case 0x45db:case 0x45df:case 0x45e1:case 0x45e3:case 0x45e5:
            case 0x45e7:case 0x45e9:case 0x45eb:case 0x45ee:case 0x45f2:
            case 0x45f6:case 0x45f7:return true;
            default:return false;
            }
        }
        switch (ip) {
        case 0x452a:case 0x452b:case 0x452d:case 0x452f:case 0x4534:case 0x4537:
        case 0x4539:case 0x453b:case 0x453d:case 0x4540:case 0x4541:case 0x4543:
        case 0x4545:case 0x4547:case 0x4549:case 0x454b:case 0x454c:case 0x454d:
        case 0x4550:case 0x4553:case 0x4556:case 0x4558:case 0x4559:case 0x455d:
        case 0x4560:case 0x4561:case 0x4563:case 0x4565:case 0x4567:case 0x456a:
        case 0x456b:return true;
        case 0x456d:case 0x4571:case 0x4574:case 0x4576:case 0x4579:case 0x457a:
        case 0x457e:case 0x4582:case 0x4583:case 0x4585:case 0x4589:case 0x458a:return spark();
        default:return false;
        }
    }
    void validate() const {
        (void)ActorFinishOperation(state_.cpu);
        const auto& cpu=state_.cpu;const auto& r=cpu.registers;
        if ((state_.kind!=TransientRemovalKind::Spark && state_.kind!=TransientRemovalKind::Debris) ||
            (state_.outcome!=TransientRemovalOutcome::Running && state_.outcome!=TransientRemovalOutcome::Returned &&
                state_.outcome!=TransientRemovalOutcome::RuntimeError) || cpu.outcome!=ActorFinishOutcome::Running ||
            r.ss!=state_.callerSs || r.ds!=static_cast<uint16_t>(cpu.gameSegment+0xaa2) ||
            cpu.timerInstructions>cpu.dispatchedInstructions ||
            (!cpu.timerDeliveries && (cpu.timerInstructions || cpu.timer)) ||
            (cpu.timerDeliveries>cpu.timerInstructions && cpu.timerDeliveries-cpu.timerInstructions>(cpu.timer ? 1u : 0u)) ||
            (cpu.timer && (finished() || cpu.timer->registers.ss!=state_.callerSs ||
                cpu.timer->dispatchedInstructions>cpu.timerInstructions)))
            throw std::invalid_argument("Transient removal CPU/counter ownership differs");
        const auto below=[&](uint16_t n) { return static_cast<uint16_t>(state_.callerSp-n); };
        uint16_t sp=below(8),bp=below(8);
        if (state_.outcome==TransientRemovalOutcome::Returned) {
            if (r.cs!=cpu.gameSegment || r.sp!=state_.callerSp || r.bp!=state_.callerBp)
                throw std::invalid_argument("Transient removal return ownership differs");
            return;
        }
        if (r.cs==library()) {
            sp=below(12);
            if (state_.outcome==TransientRemovalOutcome::RuntimeError ? r.ip!=0xe2 : !libraryBoundary(r.ip))
                throw std::invalid_argument("Transient removal runtime boundary differs");
        } else {
            if (state_.outcome!=TransientRemovalOutcome::Running || r.cs!=cpu.gameSegment || !gameBoundary(r.ip))
                throw std::invalid_argument("Transient removal instruction boundary differs");
            if (r.ip==0x452a || r.ip==0x458d || r.ip==0x458a || r.ip==0x45f7) {
                sp=below(6);bp=state_.callerBp;
            }
            if (r.ip==0x452b || r.ip==0x458e) bp=state_.callerBp;
            if (r.ip==0x454c || (r.ip>=0x4559 && r.ip<=0x456a) ||
                r.ip==0x45af || (r.ip>=0x45bc && r.ip<=0x45cd)) sp=below(10);
        }
        if (r.sp!=sp || r.bp!=bp)
            throw std::invalid_argument("Transient removal caller frame differs");
    }
    bool flag(uint32_t bit) const { return (state_.cpu.registers.flags&bit)!=0; }
    static uint32_t valueFlags(uint16_t value) {
        return (value==0 ? 0x40u : 0u)|(value&0x8000u ? 0x80u : 0u)|
            (std::popcount(static_cast<uint8_t>(value))%2==0 ? 4u : 0u);
    }
    uint16_t arithmetic(uint16_t a,uint16_t b,bool subtract=false) {
        const uint32_t wide=subtract ? uint32_t{a}-b : uint32_t{a}+b;
        const auto value=static_cast<uint16_t>(wide);uint32_t f=valueFlags(value)|((a^b^value)&16u);
        if (subtract ? a<b : wide>65535) f|=1;
        if (subtract ? ((a^b)&(a^value)&0x8000u) : (~(a^b)&(a^value)&0x8000u)) f|=0x800;
        state_.cpu.registers.flags=(state_.cpu.registers.flags&~uint32_t{0x8d5})|f;return value;
    }
    uint16_t increment(uint16_t value,bool subtract=false) {
        const auto carry=state_.cpu.registers.flags&1u;value=arithmetic(value,1,subtract);
        state_.cpu.registers.flags=(state_.cpu.registers.flags&~uint32_t{1})|carry;return value;
    }
    void instruction(const TimerIrqBus& bus,const CopyBudget& copies) {
        auto& cpu=state_.cpu;auto& r=cpu.registers;
        const auto push=[&](uint16_t value) { r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value); };
        const auto pop=[&] { const auto value=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return value; };
        const auto local=[&](int offset) { return bus.readWord(r.ss,static_cast<uint16_t>(r.bp+offset)); };
        const auto dw=[&](uint16_t offset) { return bus.readWord(r.ds,offset); };
        const auto next=[&](uint16_t bytes) { r.ip=static_cast<uint16_t>(r.ip+bytes); };
        const auto less=[&] { return flag(0x80)!=flag(0x800); };
        const auto branch=[&](bool condition,uint16_t yes,uint16_t no) { r.ip=condition ? yes : no; };
        const auto multiply=[&] {
            const uint32_t product=uint32_t{r.ax}*r.bx;r.ax=static_cast<uint16_t>(product);r.dx=static_cast<uint16_t>(product>>16);
            r.flags=(r.flags&~uint32_t{0x841})|(r.dx ? 0x801u : 0u)|(r.ax==0 ? 0x40u : 0u);
        };
        const auto zero=[&](uint16_t& value) { value=0;r.flags=(r.flags&~uint32_t{0x8d5})|0x44u; };
        if (r.cs==library()) {
            BossLinksOperation runtime(BossLinksSnapshot{r,cpu.gameSegment});
            runtime.advance(1,bus);r=runtime.snapshot().registers;return;
        }
        switch (r.ip) {
        case 0x452a:case 0x458d:push(r.bp);next(1);break;
        case 0x452b:case 0x458e:r.bp=r.sp;next(2);break;
        case 0x452d:case 0x4590:zero(r.ax);next(2);break;
        case 0x452f:case 0x4592: { const auto ip=static_cast<uint16_t>(r.ip+5u);push(r.cs);push(ip);r.cs=library();r.ip=0x4df;break; }
        case 0x4534:case 0x4597:r.ax=dw(spark() ? 0x2076 : 0x207e);next(3);break;
        case 0x4537:case 0x459a:case 0x45df:zero(r.dx);next(2);break;
        case 0x4539:case 0x459c:case 0x45d4:r.cx=r.ax;next(2);break;
        case 0x453b:case 0x459e:case 0x45d6:r.bx=r.dx;next(2);break;
        case 0x453d:case 0x45a0:case 0x455d:case 0x45c0:case 0x45d0:r.ax=local(6);next(3);break;
        case 0x4540:case 0x45a3:case 0x45d3:r.dx=r.ax&0x8000u ? 65535 : 0;next(1);break;
        case 0x4541:case 0x45a4:case 0x45e1:arithmetic(r.dx,r.bx,true);next(2);break;
        case 0x4543:case 0x45a6:branch(less(),spark() ? 0x454b : 0x45ae,spark() ? 0x4545 : 0x45a8);break;
        case 0x4545:case 0x45a8:branch(!flag(0x40) && !less(),spark() ? 0x4585 : 0x45d0,spark() ? 0x4547 : 0x45aa);break;
        case 0x4547:case 0x45aa:case 0x45e7:arithmetic(r.ax,r.cx,true);next(2);break;
        case 0x4549:case 0x45ac:branch(!flag(1),spark() ? 0x4585 : 0x45d0,spark() ? 0x454b : 0x45ae);break;
        case 0x454b:case 0x45ae:push(r.ds);next(1);break;
        case 0x454c:case 0x45af:r.es=pop();next(1);break;
        case 0x454d:case 0x45b0:r.ax=dw(spark() ? 0x2076 : 0x207e);next(3);break;
        case 0x4550:case 0x45b3:r.ax=arithmetic(r.ax,local(6),true);next(3);break;
        case 0x4553:case 0x45b6:r.bx=11;next(3);break;
        case 0x4556:case 0x45b9:case 0x4561:case 0x45c4:multiply();next(2);break;
        case 0x4558:case 0x45bb:push(r.ax);next(1);break;
        case 0x4559:case 0x45bc:r.di=dw(0x207c);next(4);break;
        case 0x4560:case 0x45c3:r.ax=increment(r.ax,true);next(1);break;
        case 0x4563:case 0x45c6:r.di=arithmetic(r.di,r.ax);next(2);break;
        case 0x4565:case 0x45c8:r.si=r.di;next(2);break;
        case 0x4567:case 0x45ca:r.si=arithmetic(r.si,11);next(3);break;
        case 0x456a:case 0x45cd:r.cx=pop();next(1);break;
        case 0x456b:case 0x45ce: {
            const auto grant=r.cx ? copies(r.cx) : 0;
            if (grant>r.cx) throw std::domain_error("Transient removal copy grant exceeds CX");
            for (uint16_t i=0;i<grant;++i) {
                bus.writeByte(r.es,r.di,bus.readByte(r.ds,r.si));
                const uint16_t delta=flag(0x400) ? uint16_t{65535} : uint16_t{1};
                r.si=static_cast<uint16_t>(r.si+delta);r.di=static_cast<uint16_t>(r.di+delta);--r.cx;++cpu.transferredBytes;
            }
            if (!r.cx) next(2);
            break;
        }
        case 0x456d:r.bx=dw(0x2076);next(4);break;
        case 0x4571:r.bx=arithmetic(r.bx,local(6),true);next(3);break;
        case 0x4574:r.cx=r.bx;next(2);break;
        case 0x4576:r.bx=local(6);next(3);break;
        case 0x4579:r.bx=increment(r.bx,true);next(1);break;
        case 0x457a:r.ax=static_cast<uint16_t>((r.ax&0xff00u)|bus.readByte(r.ds,static_cast<uint16_t>(r.bx+0x78d7u)));next(4);break;
        case 0x457e:bus.writeByte(r.ds,static_cast<uint16_t>(r.bx+0x78d6u),static_cast<uint8_t>(r.ax));next(4);break;
        case 0x4582:r.bx=increment(r.bx);next(1);break;
        case 0x4583:r.cx=static_cast<uint16_t>(r.cx-1u);branch(r.cx!=0,0x457a,0x4585);break;
        case 0x4585:bus.writeWord(r.ds,0x2076,increment(dw(0x2076),true));next(4);break;
        case 0x45d8:case 0x45eb:r.di=local(4);next(3);break;
        case 0x45db:r.ax=bus.readWord(r.ss,static_cast<uint16_t>(r.di-2u));next(4);break;
        case 0x45e3:branch(!flag(0x40) && !less(),0x45eb,0x45e5);break;
        case 0x45e5:branch(less(),0x45f2,0x45e7);break;
        case 0x45e9:branch(flag(1),0x45f2,0x45eb);break;
        case 0x45ee:bus.writeWord(r.ss,static_cast<uint16_t>(r.di-2u),increment(bus.readWord(r.ss,static_cast<uint16_t>(r.di-2u)),true));next(4);break;
        case 0x45f2:bus.writeWord(r.ds,0x207e,increment(dw(0x207e),true));next(4);break;
        case 0x4589:case 0x45f6:r.sp=r.bp;r.bp=pop();next(1);break;
        case 0x458a:case 0x45f7:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+4u);state_.outcome=TransientRemovalOutcome::Returned;break;
        default:throw std::domain_error("Transient removal left recovered code");
        }
    }
};

} // namespace lezac::core
