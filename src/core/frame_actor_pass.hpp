#pragma once

#include "core/actor_update.hpp"
#include "core/player_post.hpp"

namespace lezac::core {

enum class FrameActorPassOutcome { Running, TransientQueues, Restart, RuntimeError, DivideError };
enum class FrameActorPassKind { None, Nonplayer, Player };
using FrameActorPassCallee=std::variant<FrameActorEntrySnapshot,ActorUpdateSnapshot,PlayerPostSnapshot>;
struct FrameActorPassSnapshot {
    FrameActorPassCallee callee;
    uint16_t gameSegment=0,callerSs=0,callerSp=0,callerBp=0;
    uint32_t idToggleMask=0;
    FrameActorPassOutcome outcome=FrameActorPassOutcome::Running;
    FrameActorPassKind actorKind=FrameActorPassKind::None;
    uint64_t dispatchedInstructions=0,timerInstructions=0,timerDeliveries=0;
    uint64_t actorCalls=0,actorReturns=0,nonplayerCalls=0,playerCalls=0,postCalls=0,postReturns=0;
    bool operator==(const FrameActorPassSnapshot&) const = default;
};

// Original 7EBB boss/nonplayer/player passes, stopping before 804E queues.
// Every actual call, return and post-player continuation borrows the same SS/bus.
class FrameActorPassOperation {
    template<class Child> static auto operation(const Child& child) {
        if constexpr (std::is_same_v<Child,FrameActorEntrySnapshot>) return FrameActorEntryOperation(child);
        else if constexpr (std::is_same_v<Child,ActorUpdateSnapshot>) return ActorUpdateOperation(child);
        else return PlayerPostOperation(child);
    }
public:
    using CopyBudget=ActorUpdateOperation::CopyBudget;
    FrameActorPassOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        : state_{FrameActorEntryOperation(r,game,idToggle).snapshot(),game,r.ss,r.sp,r.bp,idToggle} {
        if (r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2) || r.ip!=0x7ebb)
            throw std::invalid_argument("Frame actor pass entry differs");
        validate();
    }
    explicit FrameActorPassOperation(FrameActorPassSnapshot state) : state_(std::move(state)) { validate(); }
    const FrameActorPassSnapshot& snapshot() const noexcept { return state_; }
    bool finished() const noexcept { return state_.outcome!=FrameActorPassOutcome::Running; }
    DosGetTimeRegisters registers() const {
        return std::visit([](const auto& child) { return operation(child).registers(); },state_.callee);
    }
    bool interruptInProgress() const {
        return std::visit([](const auto& child) { return operation(child).interruptInProgress(); },state_.callee);
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished frame actor pass admitted IRQ");
        std::visit([&](auto& child) {
            auto active=operation(child);active.deliverTimerInterrupt(bus);child=active.snapshot();
        },state_.callee);
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            const bool timer=interruptInProgress();
            std::visit([&](auto& child) {
                auto active=operation(child);
                if (active.advance(1,bus,copies)!=1) throw std::domain_error("Frame actor pass child stalled");
                child=active.snapshot();
            },state_.callee);
            ++used;++state_.dispatchedInstructions;
            if (timer) ++state_.timerInstructions;
            transition();
        }
        return used;
    }
private:
    FrameActorPassSnapshot state_;
    static constexpr bool callerAddress(uint16_t ip) {
        switch (ip) {
        case 0x7ebb:case 0x7ec0:case 0x7ec2:case 0x7ec5:case 0x7ecb:case 0x7ece:
        case 0x7ed0:case 0x7ed4:case 0x7ed6:case 0x7edb:case 0x7edf:case 0x7ee0:
        case 0x7ee1:case 0x7ee4:case 0x7ee8:case 0x7eea:case 0x7eef:case 0x7ef1:
        case 0x7ef6:case 0x7ef8:case 0x7efc:case 0x7f01:case 0x7f03:case 0x7f09:
        case 0x7f0b:case 0x7f0f:case 0x7f13:case 0x7f18:case 0x7f1a:case 0x7f1e:
        case 0x7f23:case 0x7f28:case 0x7f2a:case 0x7f2d:case 0x7f2f:case 0x7f34:
        case 0x7f3a:case 0x7f3c:case 0x7f40:case 0x7f44:case 0x7f49:case 0x7f4b:
        case 0x7f4e:case 0x7f53:case 0x7f57:case 0x7f58:case 0x7f59:
        case 0x8044:case 0x8049:case 0x804b:return true;
        default:return false;
        }
    }
    void caller(DosGetTimeRegisters r) {
        state_.callee=FrameActorEntrySnapshot{FrameActorCallerSnapshot{r},state_.gameSegment,state_.idToggleMask};
        state_.actorKind=FrameActorPassKind::None;
    }
    void transition() {
        if (interruptInProgress()) return;
        const auto r=registers();
        if (const auto* entry=std::get_if<FrameActorEntrySnapshot>(&state_.callee)) {
            if (r.cs==state_.gameSegment && r.ip==0x6053) {
                if (entry->actorKind==FrameActorEntryKind::NonPlayer) {
                    state_.actorKind=FrameActorPassKind::Nonplayer;++state_.nonplayerCalls;
                } else if (entry->actorKind==FrameActorEntryKind::PlayerOne ||
                           entry->actorKind==FrameActorEntryKind::PlayerTwo) {
                    state_.actorKind=FrameActorPassKind::Player;++state_.playerCalls;
                } else throw std::domain_error("Frame actor pass actual CALL kind differs");
                ++state_.actorCalls;
                state_.callee=ActorUpdateOperation(r,state_.gameSegment,state_.idToggleMask).snapshot();
            } else if (entry->outcome!=FrameActorEntryOutcome::Running) {
                if (entry->outcome==FrameActorEntryOutcome::TransientQueues) state_.outcome=FrameActorPassOutcome::TransientQueues;
                else if (entry->outcome==FrameActorEntryOutcome::Restart) state_.outcome=FrameActorPassOutcome::Restart;
                else if (entry->outcome==FrameActorEntryOutcome::RuntimeError) state_.outcome=FrameActorPassOutcome::RuntimeError;
                else throw std::domain_error("Frame actor pass caller crossed its boundary");
            }
        } else if (const auto* actor=std::get_if<ActorUpdateSnapshot>(&state_.callee)) {
            if (actor->outcome==ActorUpdateOutcome::Returned) {
                if (r.cs!=state_.gameSegment || r.ip!=(state_.actorKind==FrameActorPassKind::Nonplayer ? 0x7ee4 : 0x7f5c))
                    throw std::domain_error("Frame actor pass actual return differs");
                ++state_.actorReturns;
                if (state_.actorKind==FrameActorPassKind::Nonplayer) caller(r);
                else {
                    ++state_.postCalls;
                    state_.callee=PlayerPostOperation(r,state_.gameSegment,state_.idToggleMask).snapshot();
                }
            } else if (actor->outcome==ActorUpdateOutcome::RuntimeError) state_.outcome=FrameActorPassOutcome::RuntimeError;
            else if (actor->outcome==ActorUpdateOutcome::DivideError) state_.outcome=FrameActorPassOutcome::DivideError;
        } else {
            const auto& post=std::get<PlayerPostSnapshot>(state_.callee);
            if (post.outcome==PlayerPostOutcome::Caller) { ++state_.postReturns;caller(r); }
            else if (post.outcome==PlayerPostOutcome::RuntimeError) state_.outcome=FrameActorPassOutcome::RuntimeError;
            else if (post.outcome!=PlayerPostOutcome::Running)
                throw std::domain_error("Frame actor pass retained a standalone post helper");
        }
        if (finished()) validate();
    }
    void validate() const {
        const auto invalid=[] { throw std::invalid_argument("Frame actor pass continuation ownership differs"); };
        if ((state_.idToggleMask!=0 && state_.idToggleMask!=0x200000) ||
            (state_.outcome!=FrameActorPassOutcome::Running && state_.outcome!=FrameActorPassOutcome::TransientQueues &&
             state_.outcome!=FrameActorPassOutcome::Restart && state_.outcome!=FrameActorPassOutcome::RuntimeError &&
             state_.outcome!=FrameActorPassOutcome::DivideError) ||
            (state_.actorKind!=FrameActorPassKind::None && state_.actorKind!=FrameActorPassKind::Nonplayer &&
             state_.actorKind!=FrameActorPassKind::Player) ||
            state_.timerInstructions>state_.dispatchedInstructions || state_.actorCalls>state_.dispatchedInstructions ||
            state_.actorReturns>state_.actorCalls ||
            state_.nonplayerCalls>state_.actorCalls || state_.playerCalls!=state_.actorCalls-state_.nonplayerCalls ||
            state_.postCalls>state_.playerCalls || state_.postReturns>state_.postCalls ||
            state_.postCalls>state_.actorReturns)
            invalid();
        FrameActorPassOutcome actual=FrameActorPassOutcome::Running;
        std::visit([&](const auto& child) {
            using Child=std::remove_cvref_t<decltype(child)>;
            if (child.gameSegment!=state_.gameSegment || child.idToggleMask!=state_.idToggleMask ||
                child.dispatchedInstructions>state_.dispatchedInstructions)
                invalid();
            const auto active=operation(child);
            if constexpr (std::is_same_v<Child,FrameActorEntrySnapshot>) {
                if (state_.actorKind!=FrameActorPassKind::None || state_.actorCalls!=state_.actorReturns ||
                    state_.playerCalls!=state_.postCalls ||
                    state_.postCalls!=state_.postReturns || child.actorKind!=FrameActorEntryKind::None ||
                    child.prefixTimerInstructions || child.prefixTimerDeliveries ||
                    child.tailTimerInstructions>state_.timerInstructions || child.tailTimerDeliveries>state_.timerDeliveries)
                    invalid();
                if (const auto* cpu=std::get_if<FrameActorCallerSnapshot>(&child.callee)) {
                    if ((child.outcome==FrameActorEntryOutcome::Running &&
                            !callerAddress(cpu->registers.ip)) ||
                        (child.outcome!=FrameActorEntryOutcome::Running &&
                         child.outcome!=FrameActorEntryOutcome::TransientQueues && child.outcome!=FrameActorEntryOutcome::Restart))
                        invalid();
                } else if (const auto* links=std::get_if<BossLinksSnapshot>(&child.callee)) {
                    const auto& r=links->registers;
                    if (links->dispatchedInstructions>child.dispatchedInstructions ||
                        (child.outcome==FrameActorEntryOutcome::Running &&
                            r.cs==static_cast<uint16_t>(state_.gameSegment+0x920) && r.ip==0xe2) ||
                        (r.cs==state_.gameSegment ? (r.ip<0x432a || r.ip>0x4529) :
                            (r.cs!=static_cast<uint16_t>(state_.gameSegment+0x920) || r.ip>=0x1820)) ||
                        (child.outcome==FrameActorEntryOutcome::Running ? links->outcome!=BossLinksOutcome::Running :
                            (child.outcome!=FrameActorEntryOutcome::RuntimeError || links->outcome!=BossLinksOutcome::RuntimeError)))
                        invalid();
                } else invalid();
                if (child.timer && (child.timer->returned || !child.timer->biosWrapper ||
                    child.timer->gameSegment!=state_.gameSegment || child.timer->dataSegment!=static_cast<uint16_t>(state_.gameSegment+0xaa2) ||
                    child.timer->idToggleMask!=state_.idToggleMask || !state_.timerDeliveries))
                    invalid();
                if (child.outcome==FrameActorEntryOutcome::TransientQueues) actual=FrameActorPassOutcome::TransientQueues;
                else if (child.outcome==FrameActorEntryOutcome::Restart) actual=FrameActorPassOutcome::Restart;
                else if (child.outcome==FrameActorEntryOutcome::RuntimeError) actual=FrameActorPassOutcome::RuntimeError;
                else if (child.outcome!=FrameActorEntryOutcome::Running) invalid();
            } else {
                if (child.callerSs!=state_.callerSs || child.callerSp!=state_.callerSp || child.callerBp!=state_.callerBp ||
                    child.timerInstructions>state_.timerInstructions || child.timerDeliveries>state_.timerDeliveries)
                    invalid();
                if constexpr (std::is_same_v<Child,ActorUpdateSnapshot>) {
                    if (state_.actorKind==FrameActorPassKind::None || state_.actorCalls!=state_.actorReturns+1 ||
                        state_.postCalls!=state_.postReturns ||
                        state_.playerCalls-state_.postCalls!=(state_.actorKind==FrameActorPassKind::Player ? 1u : 0u))
                        invalid();
                    if (child.outcome==ActorUpdateOutcome::RuntimeError) actual=FrameActorPassOutcome::RuntimeError;
                    else if (child.outcome==ActorUpdateOutcome::DivideError) actual=FrameActorPassOutcome::DivideError;
                    else if (child.outcome!=ActorUpdateOutcome::Running) invalid();
                } else {
                    if (state_.actorKind!=FrameActorPassKind::Player || child.entry!=PlayerPostEntry::Caller ||
                        state_.actorCalls!=state_.actorReturns || state_.postCalls!=state_.postReturns+1 ||
                        state_.playerCalls!=state_.postCalls)
                        invalid();
                    if (child.outcome==PlayerPostOutcome::RuntimeError) actual=FrameActorPassOutcome::RuntimeError;
                    else if (child.outcome!=PlayerPostOutcome::Running) invalid();
                }
            }
            if (state_.outcome==FrameActorPassOutcome::Running && active.finished()) invalid();
        },state_.callee);
        const auto r=registers();
        if (state_.outcome!=actual || r.ss!=state_.callerSs ||
            (finished() && interruptInProgress()) ||
            (state_.outcome==FrameActorPassOutcome::TransientQueues &&
                (r.cs!=state_.gameSegment || r.ip!=0x804e)) ||
            (state_.outcome==FrameActorPassOutcome::Restart && (r.cs!=state_.gameSegment || r.ip!=0x77dc)) ||
            (state_.outcome==FrameActorPassOutcome::RuntimeError &&
                (r.cs!=static_cast<uint16_t>(state_.gameSegment+0x920) || r.ip!=0xe2)) ||
            ((state_.outcome==FrameActorPassOutcome::TransientQueues || state_.outcome==FrameActorPassOutcome::Restart) &&
                (r.sp!=state_.callerSp || r.bp!=state_.callerBp)))
            invalid();
    }
};

} // namespace lezac::core
