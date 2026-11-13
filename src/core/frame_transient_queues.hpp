#pragma once

#include "core/transient_update.hpp"

namespace lezac::core {
enum class FrameTransientQueuesOutcome { Running, FrameTail, RuntimeError, DivideError, Terminated };
struct FrameTransientQueuesSnapshot {
    ActorFinishSnapshot caller;
    std::optional<TransientUpdateSnapshot> child=std::nullopt;
    uint16_t callerSs=0,callerSp=0,callerBp=0;
    FrameTransientQueuesOutcome outcome=FrameTransientQueuesOutcome::Running;
    std::array<uint64_t,2> calls{},returns{};
    std::array<uint64_t,4> completed{};
    uint64_t dispatchedInstructions=0,timerInstructions=0,timerDeliveries=0,transferredBytes=0;
    bool operator==(const FrameTransientQueuesSnapshot&) const = default;
};

// Original 804E queue selection, with actual 45FA/5102 calls, stopping at 806A.
class FrameTransientQueuesOperation {
public:
    using CopyBudget=TransientUpdateOperation::CopyBudget;
    FrameTransientQueuesOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        :state_{ActorFinishSnapshot{r,game,idToggle},std::nullopt,r.ss,r.sp,r.bp} {
        if (r.cs!=game || r.ip!=0x804e) throw std::invalid_argument("Frame transient queue entry differs");
        validate();
    }
    explicit FrameTransientQueuesOperation(FrameTransientQueuesSnapshot state):state_(std::move(state)) {validate();}
    const FrameTransientQueuesSnapshot& snapshot() const noexcept {return state_;}
    bool finished() const noexcept {return state_.outcome!=FrameTransientQueuesOutcome::Running;}
    DosGetTimeRegisters registers() const {
        return state_.child ? TransientUpdateOperation(*state_.child).registers() : ActorFinishOperation(state_.caller).registers();
    }
    bool interruptInProgress() const {
        return state_.child ? TransientUpdateOperation(*state_.child).interruptInProgress() : state_.caller.timer.has_value();
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished frame transient queues admitted IRQ");
        if (state_.child) {
            TransientUpdateOperation child(*state_.child);child.deliverTimerInterrupt(bus);state_.child=child.snapshot();
        } else {
            ActorFinishOperation caller(state_.caller);caller.deliverTimerInterrupt(bus);state_.caller=caller.snapshot();
        }
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            const bool timer=interruptInProgress();
            if (state_.child) {
                TransientUpdateOperation child(*state_.child);const auto before=child.snapshot().transferredBytes;
                if (child.advance(1,bus,copies)!=1) throw std::domain_error("Frame transient queue child stalled");
                state_.child=child.snapshot();state_.transferredBytes+=child.snapshot().transferredBytes-before;
            } else if (state_.caller.timer) {
                ActorFinishOperation caller(state_.caller);
                if (caller.advance(1,bus,copies)!=1) throw std::domain_error("Frame transient queue IRQ stalled");
                state_.caller=caller.snapshot();
            } else {
                instruction(bus);++state_.caller.dispatchedInstructions;
            }
            ++used;++state_.dispatchedInstructions;if (timer) ++state_.timerInstructions;
            transition();if (finished()) validate();
        }
        return used;
    }
private:
    FrameTransientQueuesSnapshot state_;
    uint16_t game() const {return state_.caller.gameSegment;}
    [[noreturn]] static void invalid() {throw std::invalid_argument("Frame transient queue continuation ownership differs");}
    static void conservation(uint64_t total,uint64_t own,uint64_t complete,uint64_t active) {
        if (own>total || complete>total-own || active!=total-own-complete) invalid();
    }
    void validate() const {
        const auto& caller=state_.caller;const auto& r=caller.registers;
        (void)ActorFinishOperation(caller);
        if (caller.outcome!=ActorFinishOutcome::Running || r.cs!=game() || r.ds!=static_cast<uint16_t>(game()+0xaa2) ||
            r.ss!=state_.callerSs || r.bp!=state_.callerBp || caller.transferredBytes ||
            caller.timerInstructions>caller.dispatchedInstructions ||
            state_.timerInstructions>state_.dispatchedInstructions ||
            (state_.outcome!=FrameTransientQueuesOutcome::Running && state_.outcome!=FrameTransientQueuesOutcome::FrameTail &&
             state_.outcome!=FrameTransientQueuesOutcome::RuntimeError && state_.outcome!=FrameTransientQueuesOutcome::DivideError &&
             state_.outcome!=FrameTransientQueuesOutcome::Terminated) ||
            (state_.child && caller.timer) || (finished() && interruptInProgress()) || registers().ss!=state_.callerSs)
            invalid();
        const auto foreground=caller.dispatchedInstructions-caller.timerInstructions;
        const auto& calls=state_.calls;const auto& returns=state_.returns;
        for (size_t i=0;i<2;++i)
            if (calls[i]>1 || returns[i]>calls[i]) invalid();
        if (calls[1] && calls[0]!=returns[0]) invalid();
        if (state_.completed[0]<returns[0]+returns[1] || state_.completed[1]>state_.completed[0] ||
            state_.completed[2]>state_.completed[1] ||
            (!returns[0] && !returns[1] && state_.completed!=std::array<uint64_t,4>{})) invalid();
        std::array<uint64_t,4> active{};
        if (state_.child) {
            const auto& child=*state_.child;const auto operation=TransientUpdateOperation(child);
            const size_t kind=child.entry==TransientUpdateEntry::SparksAndDebris ? 0u : 1u;
            if (child.foreground.gameSegment!=game() || child.foreground.idToggleMask!=caller.idToggleMask ||
                child.callerSs!=state_.callerSs || child.callerSp!=state_.callerSp || child.callerBp!=state_.callerBp ||
                r.sp!=static_cast<uint16_t>(state_.callerSp-2u) || r.ip!=(kind==0 ? 0x45fa : 0x5102) ||
                calls[kind]!=1 || returns[kind] || calls[1-kind]!=returns[1-kind] ||
                (kind==0 && (calls[1] || (foreground!=3 && foreground!=5) || (r.flags&1u))) ||
                (kind==1 && ((r.flags&0x41u) || (calls[0] ? (foreground!=6 && foreground!=8) : foreground!=7))) ||
                (operation.finished()!=finished())) invalid();
            const auto expected=child.outcome==TransientUpdateOutcome::RuntimeError ? FrameTransientQueuesOutcome::RuntimeError :
                child.outcome==TransientUpdateOutcome::DivideError ? FrameTransientQueuesOutcome::DivideError :
                child.outcome==TransientUpdateOutcome::Terminated ? FrameTransientQueuesOutcome::Terminated : FrameTransientQueuesOutcome::Running;
            if (state_.outcome!=expected || child.outcome==TransientUpdateOutcome::Returned) invalid();
            active={child.dispatchedInstructions,child.timerInstructions,child.timerDeliveries,child.transferredBytes};
        } else {
            if (r.sp!=state_.callerSp || calls!=returns ||
                (state_.outcome!=FrameTransientQueuesOutcome::Running && state_.outcome!=FrameTransientQueuesOutcome::FrameTail)) invalid();
            switch (r.ip) {
            case 0x804e:if (foreground || calls[0] || calls[1]) invalid();break;
            case 0x8053:if (foreground!=1 || calls[0] || calls[1] || (r.flags&1u)) invalid();break;
            case 0x8055:if (foreground!=2 || calls[0] || calls[1] || (r.flags&0x41u)!=0x40u) invalid();break;
            case 0x805b:if (foreground!=3 || calls[0] || calls[1]) invalid();break;
            case 0x805d:if ((foreground!=2 && foreground!=4) || calls[0] || calls[1] || (r.flags&1u)) invalid();break;
            case 0x8060:if (calls[1] || (calls[0] ? (foreground!=3 && foreground!=5) : foreground!=4)) invalid();break;
            case 0x8065:if (calls[1] || (r.flags&1u) || (calls[0] ? (foreground!=4 && foreground!=6) : foreground!=5)) invalid();break;
            case 0x8067:if (calls[1] || (r.flags&0x41u) || (calls[0] ? (foreground!=5 && foreground!=7) : foreground!=6)) invalid();break;
            case 0x806a:
                if (state_.outcome!=FrameTransientQueuesOutcome::FrameTail ||
                    (calls[1] ? (calls[0] ? (foreground!=6 && foreground!=8) : foreground!=7) :
                        ((r.flags&0x41u)!=0x40u || (calls[0] ? (foreground!=5 && foreground!=7) : foreground!=6)))) invalid();
                break;
            default:invalid();
            }
            if (state_.outcome==FrameTransientQueuesOutcome::FrameTail && r.ip!=0x806a) invalid();
        }
        conservation(state_.dispatchedInstructions,caller.dispatchedInstructions,state_.completed[0],active[0]);
        conservation(state_.timerInstructions,caller.timerInstructions,state_.completed[1],active[1]);
        conservation(state_.timerDeliveries,caller.timerDeliveries,state_.completed[2],active[2]);
        conservation(state_.transferredBytes,caller.transferredBytes,state_.completed[3],active[3]);
        if ((!state_.timerDeliveries && (state_.timerInstructions || interruptInProgress())) ||
            (state_.timerDeliveries>state_.timerInstructions &&
                state_.timerDeliveries-state_.timerInstructions>(interruptInProgress() ? 1u : 0u))) invalid();
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r=state_.caller.registers;const auto flag=[&](uint32_t bit) {return (r.flags&bit)!=0;};
        const auto compare=[&](uint16_t a,uint16_t b) {
            const auto value=static_cast<uint16_t>(a-b);
            r.flags=(r.flags&~uint32_t{0x8d5})|(a<b ? 1u : 0u)|((a^b^value)&16u)|
                (value==0 ? 0x40u : 0u)|(value&0x8000u ? 0x80u : 0u)|
                (std::popcount(static_cast<uint8_t>(value))%2==0 ? 4u : 0u)|
                (((a^b)&(a^value)&0x8000u) ? 0x800u : 0u);
        };
        const auto call=[&](uint16_t target,uint16_t next) {
            r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,next);r.ip=target;
        };
        switch (r.ip) {
        case 0x804e:compare(bus.readWord(r.ds,0x2076),0);r.ip=0x8053;break;
        case 0x8053:r.ip=!flag(1) && !flag(0x40) ? 0x805d : 0x8055;break;
        case 0x8055:compare(bus.readWord(r.ds,0x207e),200);r.ip=0x805b;break;
        case 0x805b:r.ip=flag(1) ? 0x8060 : 0x805d;break;
        case 0x805d:call(0x45fa,0x8060);break;
        case 0x8060:compare(bus.readWord(r.ds,0x2080),0);r.ip=0x8065;break;
        case 0x8065:r.ip=flag(1) || flag(0x40) ? 0x806a : 0x8067;break;
        case 0x8067:call(0x5102,0x806a);break;
        default:throw std::domain_error("Frame transient queue caller left original instructions");
        }
    }
    void transition() {
        if (state_.child) {
            TransientUpdateOperation child(*state_.child);if (!child.finished()) return;
            const auto& snapshot=child.snapshot();
            if (snapshot.outcome==TransientUpdateOutcome::Returned) {
                const size_t kind=snapshot.entry==TransientUpdateEntry::SparksAndDebris ? 0u : 1u;
                const auto r=child.registers();
                if (r.cs!=game() || r.ip!=(kind==0 ? 0x8060 : 0x806a) || r.sp!=state_.callerSp || r.bp!=state_.callerBp)
                    throw std::domain_error("Frame transient queue actual child return differs");
                ++state_.returns[kind];state_.caller.registers=r;
                state_.completed[0]+=snapshot.dispatchedInstructions;state_.completed[1]+=snapshot.timerInstructions;
                state_.completed[2]+=snapshot.timerDeliveries;state_.completed[3]+=snapshot.transferredBytes;
                state_.child.reset();
            } else {
                state_.outcome=snapshot.outcome==TransientUpdateOutcome::RuntimeError ? FrameTransientQueuesOutcome::RuntimeError :
                    snapshot.outcome==TransientUpdateOutcome::DivideError ? FrameTransientQueuesOutcome::DivideError : FrameTransientQueuesOutcome::Terminated;
                return;
            }
        }
        if (!state_.child && !state_.caller.timer) {
            const auto r=state_.caller.registers;
            if (r.ip==0x806a) state_.outcome=FrameTransientQueuesOutcome::FrameTail;
            else if (r.ip==0x45fa || r.ip==0x5102) {
                const auto mode=r.ip==0x45fa ? TransientUpdateEntry::SparksAndDebris : TransientUpdateEntry::Collapse;
                ++state_.calls[mode==TransientUpdateEntry::SparksAndDebris ? 0u : 1u];
                state_.child=TransientUpdateOperation(r,game(),state_.caller.idToggleMask,mode).snapshot();
            }
        }
    }
};
} // namespace lezac::core
