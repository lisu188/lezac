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
    static constexpr bool bossGameAddress(uint16_t ip) {
        switch (ip) {
        case 0x432a:case 0x432b:case 0x432d:case 0x4330:case 0x4335:case 0x4338:
        case 0x433b:case 0x433d:case 0x4340:case 0x4343:case 0x4346:case 0x4348:
        case 0x434b:case 0x434e:case 0x4350:case 0x4353:case 0x4356:case 0x4359:
        case 0x435d:case 0x4360:case 0x4363:case 0x4366:case 0x4369:case 0x436b:
        case 0x436d:case 0x4370:case 0x4374:case 0x4377:case 0x437a:case 0x437d:
        case 0x4382:case 0x4384:case 0x4387:case 0x438a:case 0x438e:case 0x438f:
        case 0x4391:case 0x4393:case 0x4396:case 0x439a:case 0x439c:case 0x439e:
        case 0x43a1:case 0x43a5:case 0x43a8:case 0x43ab:case 0x43ad:case 0x43af:
        case 0x43b1:case 0x43b3:case 0x43b5:case 0x43b7:case 0x43ba:case 0x43be:
        case 0x43c0:case 0x43c2:case 0x43c7:case 0x43ca:case 0x43ce:case 0x43d1:
        case 0x43d5:case 0x43d6:case 0x43d8:case 0x43da:case 0x43dd:case 0x43e1:
        case 0x43e3:case 0x43e5:case 0x43e8:case 0x43ec:case 0x43ef:case 0x43f3:
        case 0x43f5:case 0x43f7:case 0x43f9:case 0x43fb:case 0x43fd:case 0x43ff:
        case 0x4402:case 0x4406:case 0x4408:case 0x440a:case 0x440f:case 0x4411:
        case 0x4413:case 0x4416:case 0x441a:case 0x441b:case 0x441c:case 0x441e:
        case 0x4420:case 0x4423:case 0x4427:case 0x442a:case 0x442d:case 0x4431:
        case 0x4433:case 0x4435:case 0x4438:case 0x443c:case 0x443e:case 0x4440:
        case 0x4443:case 0x4446:case 0x444a:case 0x444d:case 0x4451:case 0x4453:
        case 0x4456:case 0x4459:case 0x445b:case 0x445d:case 0x445f:case 0x4461:
        case 0x4463:case 0x4467:case 0x446b:case 0x446f:case 0x4470:case 0x4471:
        case 0x4472:case 0x4475:case 0x4479:case 0x447b:case 0x447d:case 0x4482:
        case 0x4483:case 0x4484:case 0x4485:case 0x448a:case 0x448f:case 0x4490:
        case 0x4491:case 0x4494:case 0x4498:case 0x4499:case 0x449b:case 0x449d:
        case 0x44a0:case 0x44a3:case 0x44a5:case 0x44a7:case 0x44a9:case 0x44aa:
        case 0x44ab:case 0x44ad:case 0x44af:case 0x44b2:case 0x44b6:case 0x44b9:
        case 0x44bd:case 0x44bf:case 0x44c1:case 0x44c3:case 0x44c5:case 0x44c7:
        case 0x44c9:case 0x44cd:case 0x44d1:case 0x44d5:case 0x44d6:case 0x44d7:
        case 0x44d8:case 0x44db:case 0x44df:case 0x44e1:case 0x44e3:case 0x44e8:
        case 0x44e9:case 0x44ea:case 0x44eb:case 0x44f0:case 0x44f5:case 0x44f6:
        case 0x44f7:case 0x44fa:case 0x44fe:case 0x44ff:case 0x4501:case 0x4503:
        case 0x4506:case 0x450a:case 0x450c:case 0x450e:case 0x4510:case 0x4511:
        case 0x4512:case 0x4514:case 0x4516:case 0x4519:case 0x451d:case 0x4520:
        case 0x4523:case 0x4525:case 0x4528:case 0x4529:
            return true;
        default:return false;
        }
    }
    // E2 is an error endpoint, rejected separately while still running.
    static constexpr bool bossLibraryAddress(uint16_t ip) {
        switch (ip) {
        case 0xe2:case 0x4df:case 0x4e2:case 0x4e4:case 0x4e6:case 0x4e8:
        case 0x4ea:case 0x4ee:case 0x4f0:case 0x4f1:case 0x4f4:case 0x92a:
        case 0x92c:case 0x92e:case 0x930:case 0x931:case 0x932:case 0x934:
        case 0x936:case 0x938:case 0x93a:case 0x93c:case 0x93e:case 0x93f:
        case 0x940:case 0x942:case 0x944:case 0xca5:case 0xca8:case 0xcaa:
        case 0xcac:case 0xcae:case 0xcb0:case 0xcb1:case 0xcb3:case 0xcb5:
        case 0xcb9:case 0xcbb:case 0xcbd:case 0xcbf:case 0xcc1:case 0xcc5:
        case 0xcc9:case 0xcca:case 0xccc:case 0xcce:case 0xcd0:case 0xcd2:
        case 0xcd4:case 0xcd6:case 0xcd8:case 0xcda:case 0xcdb:case 0xcdd:
        case 0xcdf:case 0xce1:case 0xce3:case 0xce5:case 0xce7:case 0xce9:
        case 0xceb:case 0xced:case 0xcf0:case 0xcf2:case 0xcf4:case 0xcf6:
        case 0xcf8:case 0xcfb:case 0xd79:case 0xd7a:case 0xd7b:case 0xd7c:
        case 0xd7e:case 0xd80:case 0xd82:case 0xd84:case 0xd86:case 0xd87:
        case 0xd8b:case 0xd8e:case 0xd91:case 0xd94:case 0xd96:case 0xd98:
        case 0xd99:case 0xd9c:case 0xd9e:case 0xd9f:case 0xda1:case 0xda3:
        case 0xda5:case 0xda6:case 0xda8:case 0xdaa:case 0xdac:case 0xdad:
        case 0xdaf:case 0xdb1:case 0xdb2:case 0xdb4:case 0xdb6:case 0xdba:
        case 0xdbe:case 0xdc2:case 0xdc4:case 0xdc6:case 0xdc8:case 0xdc9:
        case 0xdcb:case 0xdce:case 0xdd0:case 0xdd2:case 0xdd4:case 0xdd6:
        case 0xdd8:case 0xdda:case 0xddc:case 0xdde:case 0xde0:case 0xde2:
        case 0xde4:case 0xde6:case 0xde8:case 0xdea:case 0xdec:case 0xdee:
        case 0xdf0:case 0xdf2:case 0xdf3:case 0xdf5:case 0xdf7:case 0xdf9:
        case 0xdfa:case 0xdfd:case 0xdff:case 0xe01:case 0xe03:case 0xe05:
        case 0xe07:case 0xe09:case 0xe0a:case 0xe0b:case 0xe0c:case 0xe0d:
        case 0xe0f:case 0xe11:case 0xe14:case 0xe16:case 0xe18:case 0xe1a:
        case 0xe1c:case 0xe1d:case 0xe21:case 0xe4e:case 0xe50:case 0xe52:
        case 0xe54:case 0xe56:case 0xe58:case 0xe5a:case 0xe5c:case 0xe5e:
        case 0xe61:case 0xe64:case 0xe66:case 0xe69:case 0xe6b:case 0xe6d:
        case 0xe6f:case 0xe71:case 0xe73:case 0xe75:case 0xe77:case 0xe79:
        case 0xe7b:case 0xe7d:case 0xe7f:case 0xe81:case 0xe83:case 0xe85:
        case 0xe87:case 0xe89:case 0xe8c:case 0xe8d:case 0xe8e:case 0xe90:
        case 0xe92:case 0xe94:case 0xe97:case 0xe99:case 0xe9b:case 0xe9d:
        case 0xea0:case 0xea3:case 0xea5:case 0xea7:case 0xea9:case 0xeac:
        case 0xeaf:case 0xeb1:case 0xeb3:case 0xeb5:case 0xeb7:case 0xeb9:
        case 0xebc:case 0xebe:case 0xec0:case 0xec2:case 0xec4:case 0xec6:
        case 0xec8:case 0xeca:case 0xecd:case 0xed0:case 0xed2:case 0xed4:
        case 0xed6:case 0xed8:case 0xeda:case 0xedd:case 0xee0:case 0xee1:
        case 0xee2:case 0xee3:case 0xee4:case 0xee6:case 0xee8:case 0xefb:
        case 0xefe:case 0xf00:case 0xf01:case 0xf03:case 0xf05:case 0xf08:
        case 0xf0a:case 0xf0f:case 0xf12:case 0xf13:case 0xf15:case 0xf18:
        case 0xf1a:case 0xf23:case 0xf26:case 0xf29:case 0xf2c:case 0xf2f:
        case 0xf32:
            return true;
        default:return false;
        }
    }
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
            state_.playerCalls>2 ||
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
                    if (((cpu->registers.ip==0x7ee4 || cpu->registers.ip==0x7ee8) && !state_.nonplayerCalls) ||
                        (cpu->registers.ip>=0x7ebb && cpu->registers.ip<=0x7ec5 && state_.actorCalls) ||
                        ((cpu->registers.ip<=0x7f3a || cpu->registers.ip==0x77dc) && state_.playerCalls) ||
                        (((cpu->registers.ip>=0x7f3c && cpu->registers.ip<=0x7f59) ||
                            cpu->registers.ip==0x804b) && state_.playerCalls>1) ||
                        (child.outcome==FrameActorEntryOutcome::Running &&
                            !callerAddress(cpu->registers.ip)) ||
                        (child.outcome!=FrameActorEntryOutcome::Running &&
                         child.outcome!=FrameActorEntryOutcome::TransientQueues && child.outcome!=FrameActorEntryOutcome::Restart))
                        invalid();
                } else if (const auto* links=std::get_if<BossLinksSnapshot>(&child.callee)) {
                    const auto& r=links->registers;
                    // Boss work precedes all actor calls; the shared balances force every other call counter to zero.
                    if (state_.actorCalls || links->dispatchedInstructions>child.dispatchedInstructions ||
                        (child.outcome==FrameActorEntryOutcome::Running &&
                            r.cs==static_cast<uint16_t>(state_.gameSegment+0x920) && r.ip==0xe2) ||
                        (r.cs==state_.gameSegment ? !bossGameAddress(r.ip) :
                            (r.cs!=static_cast<uint16_t>(state_.gameSegment+0x920) || !bossLibraryAddress(r.ip))) ||
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
                        (state_.actorKind==FrameActorPassKind::Nonplayer && state_.playerCalls) ||
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
