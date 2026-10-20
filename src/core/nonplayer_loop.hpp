#pragma once

#include "core/actor_expiry.hpp"
#include "core/actor_motion.hpp"
#include "core/actor_tile_flags.hpp"

#include <cstdint>
#include <optional>
#include <stdexcept>
#include <type_traits>
#include <utility>
#include <variant>

namespace lezac::core {

enum class NonplayerLoopOutcome { Running, PlayerPhase, PlayerMotion, RuntimeError, DivideError };
using NonplayerLoopCallee=std::variant<FrameActorEntrySnapshot,ActorPrecontactSnapshot,ActorContactSnapshot,
    ActorTileFlagsSnapshot,ActorMotionSnapshot,ActorExpirySnapshot,ActorFinishSnapshot>;
struct NonplayerLoopSnapshot {
    NonplayerLoopCallee callee;
    uint16_t gameSegment=0,callerSp=0,callerBp=0;
    uint32_t idToggleMask=0;
    NonplayerLoopOutcome outcome=NonplayerLoopOutcome::Running;
    uint64_t dispatchedInstructions=0,timerInstructions=0,timerDeliveries=0,actorCalls=0,actorReturns=0;
    bool operator==(const NonplayerLoopSnapshot&) const = default;
};

// Original 7EBB nonplayer caller through 7EEA, preserving one borrowed SS
// across every actual 6053 call and return. The player phase is not executed.
class NonplayerLoopOperation {
    template<class Child> static auto operation(const Child& child) {
        if constexpr (std::is_same_v<Child,FrameActorEntrySnapshot>) return FrameActorEntryOperation(child);
        else if constexpr (std::is_same_v<Child,ActorPrecontactSnapshot>) return ActorPrecontactOperation(child);
        else if constexpr (std::is_same_v<Child,ActorContactSnapshot>) return ActorContactOperation(child);
        else if constexpr (std::is_same_v<Child,ActorTileFlagsSnapshot>) return ActorTileFlagsOperation(child);
        else if constexpr (std::is_same_v<Child,ActorMotionSnapshot>) return ActorMotionOperation(child);
        else if constexpr (std::is_same_v<Child,ActorExpirySnapshot>) return ActorExpiryOperation(child);
        else return ActorFinishOperation(child);
    }
public:
    using CopyBudget=ActorFinishOperation::CopyBudget;
    NonplayerLoopOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        : state_{FrameActorEntryOperation(r,game,idToggle).snapshot(),game,r.sp,r.bp,idToggle} {
        if (r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2) || r.ip!=0x7ebb)
            throw std::invalid_argument("Nonplayer loop entry differs");
        validate();
    }
    explicit NonplayerLoopOperation(NonplayerLoopSnapshot state) : state_(std::move(state)) { validate(); }
    const NonplayerLoopSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const {
        return std::visit([](const auto& child) { return operation(child).registers(); },state_.callee);
    }
    bool finished() const noexcept { return state_.outcome!=NonplayerLoopOutcome::Running; }
    bool interruptInProgress() const {
        return std::visit([](const auto& child) { return operation(child).interruptInProgress(); },state_.callee);
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished nonplayer loop admitted IRQ");
        std::visit([&](auto& child) {
            auto active=operation(child);active.deliverTimerInterrupt(bus);child=active.snapshot();
        },state_.callee);
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            const bool timer=interruptInProgress();
            const auto before=registers();
            if (!timer && before.cs==state_.gameSegment && before.ip==0x6053) ++state_.actorCalls;
            std::visit([&](auto& child) {
                using Child=std::remove_cvref_t<decltype(child)>;
                auto active=operation(child);
                uint64_t count=0;
                if constexpr (std::is_same_v<Child,ActorPrecontactSnapshot> ||
                        std::is_same_v<Child,ActorContactSnapshot> || std::is_same_v<Child,ActorTileFlagsSnapshot>)
                    count=active.advance(1,bus);
                else count=active.advance(1,bus,copies);
                if (count!=1) throw std::domain_error("Nonplayer loop child did not dispatch");
                child=active.snapshot();
            },state_.callee);
            ++used;++state_.dispatchedInstructions;
            if (timer) ++state_.timerInstructions;
            transition();
        }
        return used;
    }

private:
    NonplayerLoopSnapshot state_;
    void validate() const {
        if ((state_.idToggleMask!=0 && state_.idToggleMask!=0x200000) ||
                state_.actorReturns>state_.actorCalls ||
                (state_.outcome!=NonplayerLoopOutcome::Running && state_.outcome!=NonplayerLoopOutcome::PlayerPhase &&
                 state_.outcome!=NonplayerLoopOutcome::PlayerMotion && state_.outcome!=NonplayerLoopOutcome::RuntimeError &&
                 state_.outcome!=NonplayerLoopOutcome::DivideError))
            throw std::invalid_argument("Nonplayer loop counter/outcome profile differs");
        std::visit([&](const auto& child) {
            using Child=std::remove_cvref_t<decltype(child)>;
            const auto& cpu=[&]() -> const auto& {
                if constexpr (std::is_same_v<Child,ActorMotionSnapshot> || std::is_same_v<Child,ActorExpirySnapshot>)
                    return child.cpu;
                else return child;
            }();
            if (cpu.gameSegment!=state_.gameSegment || cpu.idToggleMask!=state_.idToggleMask)
                throw std::invalid_argument("Nonplayer loop child ownership differs");
            const auto active=operation(child);
            if (state_.outcome==NonplayerLoopOutcome::Running && active.finished())
                throw std::invalid_argument("Running nonplayer loop retained a finished child");
            if constexpr (std::is_same_v<Child,FrameActorEntrySnapshot>)
                if (std::holds_alternative<FramePrefixSnapshot>(child.callee))
                    throw std::invalid_argument("Nonplayer loop admitted a pre-caller frame prefix");
        },state_.callee);
        const auto r=registers();
        if ((finished() && interruptInProgress()) ||
                (state_.outcome==NonplayerLoopOutcome::PlayerPhase && (r.cs!=state_.gameSegment || r.ip!=0x7eea)) ||
                (state_.outcome==NonplayerLoopOutcome::PlayerMotion && (r.cs!=state_.gameSegment || r.ip!=0x6737)) ||
                (state_.outcome==NonplayerLoopOutcome::RuntimeError &&
                    (r.cs!=static_cast<uint16_t>(state_.gameSegment+0x920) || r.ip!=0xe2)) ||
                (state_.outcome==NonplayerLoopOutcome::DivideError &&
                    (!std::holds_alternative<ActorMotionSnapshot>(state_.callee) ||
                     std::get<ActorMotionSnapshot>(state_.callee).outcome!=ActorMotionOutcome::DivideError)))
            throw std::invalid_argument("Nonplayer loop handoff ownership differs");
    }
    NonplayerLoopCallee returned(DosGetTimeRegisters r) {
        if (r.cs!=state_.gameSegment || r.ip!=0x7ee4 || r.sp!=state_.callerSp || r.bp!=state_.callerBp)
            throw std::domain_error("Nonplayer actor did not restore its actual caller");
        ++state_.actorReturns;
        return FrameActorEntrySnapshot{FrameActorCallerSnapshot{r},state_.gameSegment,state_.idToggleMask};
    }
    void transition() {
        const auto r=registers();
        const auto game=state_.gameSegment;const auto id=state_.idToggleMask;
        const auto next=std::visit([&](const auto& child) -> std::optional<NonplayerLoopCallee> {
            using Child=std::remove_cvref_t<decltype(child)>;
            const auto active=operation(child);
            if constexpr (std::is_same_v<Child,FrameActorEntrySnapshot>) {
                if (!active.interruptInProgress() && r.cs==game && r.ip==0x7eea) {
                    state_.outcome=NonplayerLoopOutcome::PlayerPhase;
                } else if (active.finished()) {
                    if (child.outcome==FrameActorEntryOutcome::ActorBody)
                        return ActorPrecontactOperation(r,game,id).snapshot();
                    state_.outcome=NonplayerLoopOutcome::RuntimeError;
                }
            } else if (active.finished()) {
                if constexpr (std::is_same_v<Child,ActorPrecontactSnapshot>) {
                    if (child.outcome==ActorPrecontactOutcome::BehaviorDispatch)
                        return ActorContactOperation(r,game,id).snapshot();
                    state_.outcome=NonplayerLoopOutcome::RuntimeError;
                } else if constexpr (std::is_same_v<Child,ActorContactSnapshot>) {
                    if (child.outcome==ActorContactOutcome::TileBehavior)
                        return ActorTileFlagsOperation(r,game,id).snapshot();
                    if (child.outcome==ActorContactOutcome::MotionIntegration)
                        return ActorFinishOperation(r,game,id).snapshot();
                    state_.outcome=NonplayerLoopOutcome::RuntimeError;
                } else if constexpr (std::is_same_v<Child,ActorTileFlagsSnapshot>) {
                    if (child.outcome==ActorTileFlagsOutcome::Behavior)
                        return ActorMotionOperation(r,game,id).snapshot();
                    if (child.outcome==ActorTileFlagsOutcome::Expiry)
                        return ActorExpiryOperation(r,game,id).snapshot();
                    state_.outcome=NonplayerLoopOutcome::PlayerMotion;
                } else if constexpr (std::is_same_v<Child,ActorMotionSnapshot>) {
                    if (child.outcome==ActorMotionOutcome::MotionIntegration)
                        return ActorFinishOperation(r,game,id).snapshot();
                    state_.outcome=child.outcome==ActorMotionOutcome::DivideError ?
                        NonplayerLoopOutcome::DivideError : NonplayerLoopOutcome::RuntimeError;
                } else if constexpr (std::is_same_v<Child,ActorExpirySnapshot>) {
                    if (child.outcome==ActorExpiryOutcome::MotionIntegration)
                        return ActorFinishOperation(r,game,id).snapshot();
                    if (child.outcome==ActorExpiryOutcome::Returned) return returned(r);
                    state_.outcome=NonplayerLoopOutcome::RuntimeError;
                } else {
                    if (child.outcome==ActorFinishOutcome::Returned) return returned(r);
                    state_.outcome=NonplayerLoopOutcome::RuntimeError;
                }
            }
            return std::nullopt;
        },state_.callee);
        if (next) state_.callee=*next;
    }
};

} // namespace lezac::core
