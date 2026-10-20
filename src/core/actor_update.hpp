#pragma once

#include "core/actor_expiry.hpp"
#include "core/actor_tile_flags.hpp"
#include "core/player_motion.hpp"

#include <cstdint>
#include <optional>
#include <stdexcept>
#include <type_traits>
#include <utility>
#include <variant>

namespace lezac::core {

enum class ActorUpdateOutcome { Running, Returned, RuntimeError, DivideError };
using ActorUpdateCallee=std::variant<FrameActorContactSnapshot,ActorTileFlagsSnapshot,
    PlayerMotionSnapshot,ActorMotionSnapshot,ActorExpirySnapshot,ActorFinishSnapshot>;
struct ActorUpdateSnapshot {
    ActorUpdateCallee callee;
    uint16_t gameSegment=0,callerSs=0,callerSp=0,callerBp=0;
    uint32_t idToggleMask=0;
    ActorUpdateOutcome outcome=ActorUpdateOutcome::Running;
    uint64_t dispatchedInstructions=0,timerInstructions=0,timerDeliveries=0;
    bool operator==(const ActorUpdateSnapshot&) const = default;
};

// One complete original 6053 actor call on the caller's borrowed bus and SS.
// Stop after the real RET 4; do not execute the caller's next instruction.
class ActorUpdateOperation {
    template<class Child> static auto operation(const Child& child) {
        if constexpr (std::is_same_v<Child,FrameActorContactSnapshot>) return FrameActorContactOperation(child);
        else if constexpr (std::is_same_v<Child,ActorTileFlagsSnapshot>) return ActorTileFlagsOperation(child);
        else if constexpr (std::is_same_v<Child,PlayerMotionSnapshot>) return PlayerMotionOperation(child);
        else if constexpr (std::is_same_v<Child,ActorMotionSnapshot>) return ActorMotionOperation(child);
        else if constexpr (std::is_same_v<Child,ActorExpirySnapshot>) return ActorExpiryOperation(child);
        else return ActorFinishOperation(child);
    }
public:
    using CopyBudget=ActorFinishOperation::CopyBudget;
    ActorUpdateOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        : state_{FrameActorContactOperation(r,game,idToggle).snapshot(),game,r.ss,
            static_cast<uint16_t>(r.sp+6u),r.bp,idToggle} {
        if (r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2) || r.ip!=0x6053)
            throw std::invalid_argument("Actor update entry differs");
        validate();
    }
    explicit ActorUpdateOperation(ActorUpdateSnapshot state) : state_(std::move(state)) { validate(); }
    const ActorUpdateSnapshot& snapshot() const noexcept { return state_; }
    DosGetTimeRegisters registers() const {
        return std::visit([](const auto& child) { return operation(child).registers(); },state_.callee);
    }
    bool finished() const noexcept { return state_.outcome!=ActorUpdateOutcome::Running; }
    bool interruptInProgress() const {
        return std::visit([](const auto& child) { return operation(child).interruptInProgress(); },state_.callee);
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished actor update admitted IRQ");
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
                using Child=std::remove_cvref_t<decltype(child)>;
                auto active=operation(child);uint64_t count=0;
                if constexpr (std::is_same_v<Child,ActorTileFlagsSnapshot>) count=active.advance(1,bus);
                else count=active.advance(1,bus,copies);
                if (count!=1) throw std::domain_error("Actor update child did not dispatch");
                child=active.snapshot();
            },state_.callee);
            ++used;++state_.dispatchedInstructions;
            if (timer) ++state_.timerInstructions;
            transition();
        }
        return used;
    }
private:
    ActorUpdateSnapshot state_;
    void validate() const {
        if ((state_.idToggleMask!=0 && state_.idToggleMask!=0x200000) ||
            state_.timerInstructions>state_.dispatchedInstructions ||
            (state_.outcome!=ActorUpdateOutcome::Running && state_.outcome!=ActorUpdateOutcome::Returned &&
             state_.outcome!=ActorUpdateOutcome::RuntimeError && state_.outcome!=ActorUpdateOutcome::DivideError))
            throw std::invalid_argument("Actor update counter/outcome profile differs");
        std::visit([&](const auto& child) {
            using Child=std::remove_cvref_t<decltype(child)>;
            const auto& cpu=[&]() -> const auto& {
                if constexpr (std::is_same_v<Child,PlayerMotionSnapshot> ||
                    std::is_same_v<Child,ActorMotionSnapshot> || std::is_same_v<Child,ActorExpirySnapshot>)
                    return child.cpu;
                else return child;
            }();
            if (cpu.gameSegment!=state_.gameSegment || cpu.idToggleMask!=state_.idToggleMask)
                throw std::invalid_argument("Actor update child ownership differs");
            const auto active=operation(child);
            if (state_.outcome==ActorUpdateOutcome::Running && active.finished())
                throw std::invalid_argument("Running actor update retained a finished child");
            if (finished() && !active.finished())
                throw std::invalid_argument("Finished actor update retained a running child");
            if constexpr (std::is_same_v<Child,FrameActorContactSnapshot>) {
                if (const auto* pre=std::get_if<FrameActorPrecontactSnapshot>(&child.callee))
                    if (const auto* entry=std::get_if<FrameActorEntrySnapshot>(&pre->callee))
                        if (!std::holds_alternative<ActorAnimationSnapshot>(entry->callee))
                            throw std::invalid_argument("Actor update admitted a pre-actor caller");
            }
            if (state_.outcome==ActorUpdateOutcome::Returned) {
                if constexpr (std::is_same_v<Child,ActorFinishSnapshot>)
                    if (child.outcome==ActorFinishOutcome::Returned) return;
                if constexpr (std::is_same_v<Child,ActorExpirySnapshot>)
                    if (child.outcome==ActorExpiryOutcome::Returned) return;
                throw std::invalid_argument("Actor update return lacks an actual RET");
            }
            if (state_.outcome==ActorUpdateOutcome::RuntimeError) {
                bool matching=false;
                if constexpr (std::is_same_v<Child,FrameActorContactSnapshot>)
                    matching=child.outcome==FrameActorContactOutcome::RuntimeError;
                else if constexpr (std::is_same_v<Child,PlayerMotionSnapshot>)
                    matching=child.outcome==PlayerMotionOutcome::RuntimeError;
                else if constexpr (std::is_same_v<Child,ActorMotionSnapshot>)
                    matching=child.outcome==ActorMotionOutcome::RuntimeError;
                else if constexpr (std::is_same_v<Child,ActorExpirySnapshot>)
                    matching=child.outcome==ActorExpiryOutcome::RuntimeError;
                else if constexpr (std::is_same_v<Child,ActorFinishSnapshot>)
                    matching=child.outcome==ActorFinishOutcome::RuntimeError;
                if (!matching) throw std::invalid_argument("Actor update runtime outcome lacks a runtime error");
            }
            if (state_.outcome==ActorUpdateOutcome::DivideError) {
                if constexpr (std::is_same_v<Child,PlayerMotionSnapshot>)
                    if (child.outcome==PlayerMotionOutcome::DivideError) return;
                if constexpr (std::is_same_v<Child,ActorMotionSnapshot>)
                    if (child.outcome==ActorMotionOutcome::DivideError) return;
                throw std::invalid_argument("Actor update divide outcome lacks a fault");
            }
        },state_.callee);
        const auto r=registers();
        if ((finished() && interruptInProgress()) ||
            (state_.outcome==ActorUpdateOutcome::Returned && (r.cs!=state_.gameSegment ||
                r.ss!=state_.callerSs || r.sp!=state_.callerSp || r.bp!=state_.callerBp)) ||
            (state_.outcome==ActorUpdateOutcome::RuntimeError &&
                (r.cs!=static_cast<uint16_t>(state_.gameSegment+0x920) || r.ip!=0xe2)))
            throw std::invalid_argument("Actor update endpoint ownership differs");
    }
    void transition() {
        const auto r=registers();const auto game=state_.gameSegment;const auto id=state_.idToggleMask;
        const auto next=std::visit([&](const auto& child) -> std::optional<ActorUpdateCallee> {
            using Child=std::remove_cvref_t<decltype(child)>;
            if (!operation(child).finished()) return std::nullopt;
            if constexpr (std::is_same_v<Child,FrameActorContactSnapshot>) {
                if (child.outcome==FrameActorContactOutcome::TileBehavior)
                    return ActorTileFlagsOperation(r,game,id).snapshot();
                if (child.outcome==FrameActorContactOutcome::MotionIntegration)
                    return ActorFinishOperation(r,game,id).snapshot();
                if (child.outcome!=FrameActorContactOutcome::RuntimeError)
                    throw std::domain_error("Actor update left its actor call");
                state_.outcome=ActorUpdateOutcome::RuntimeError;
            } else if constexpr (std::is_same_v<Child,ActorTileFlagsSnapshot>) {
                if (child.outcome==ActorTileFlagsOutcome::Behavior) return ActorMotionOperation(r,game,id).snapshot();
                if (child.outcome==ActorTileFlagsOutcome::Expiry) return ActorExpiryOperation(r,game,id).snapshot();
                return PlayerMotionOperation(r,game,id).snapshot();
            } else if constexpr (std::is_same_v<Child,PlayerMotionSnapshot>) {
                if (child.outcome==PlayerMotionOutcome::Terrain) return ActorMotionSnapshot{child.cpu};
                state_.outcome=child.outcome==PlayerMotionOutcome::DivideError ?
                    ActorUpdateOutcome::DivideError : ActorUpdateOutcome::RuntimeError;
            } else if constexpr (std::is_same_v<Child,ActorMotionSnapshot>) {
                if (child.outcome==ActorMotionOutcome::MotionIntegration) return child.cpu;
                state_.outcome=child.outcome==ActorMotionOutcome::DivideError ?
                    ActorUpdateOutcome::DivideError : ActorUpdateOutcome::RuntimeError;
            } else if constexpr (std::is_same_v<Child,ActorExpirySnapshot>) {
                if (child.outcome==ActorExpiryOutcome::MotionIntegration) return child.cpu;
                state_.outcome=child.outcome==ActorExpiryOutcome::Returned ?
                    ActorUpdateOutcome::Returned : ActorUpdateOutcome::RuntimeError;
            } else {
                state_.outcome=child.outcome==ActorFinishOutcome::Returned ?
                    ActorUpdateOutcome::Returned : ActorUpdateOutcome::RuntimeError;
            }
            return std::nullopt;
        },state_.callee);
        if (next) state_.callee=*next;
        if (finished()) validate();
    }
};

} // namespace lezac::core
