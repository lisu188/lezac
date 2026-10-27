#pragma once

#include "core/frame_actor_pass.hpp"
#include "core/frame_transient_queues.hpp"
#include "core/frame_tail.hpp"

namespace lezac::core {
enum class FrameIterationEntry { Full, PostRender, Actors };
enum class FrameIterationOutcome { Running, NextFrame, EndRunUi, BreakOutput, Restart,
    Completion, Escape, ViewChange, RuntimeError, DivideError, Terminated };
using FrameIterationCallee=std::variant<FramePrefixSnapshot,FrameActorPassSnapshot,
    FrameTransientQueuesSnapshot,FrameTailSnapshot>;
struct FrameIterationSnapshot {
    FrameIterationCallee callee;
    uint16_t gameSegment=0,callerSs=0,callerSp=0,callerBp=0;
    uint32_t idToggleMask=0;
    FrameIterationEntry entry=FrameIterationEntry::Full;
    FrameIterationOutcome outcome=FrameIterationOutcome::Running;
    std::array<std::array<uint64_t,3>,4> completed{};
    uint64_t dispatchedInstructions=0,timerInstructions=0,timerDeliveries=0;
    bool operator==(const FrameIterationSnapshot&) const = default;
};

// One original iteration; UI and restart endpoints remain explicit handoffs.
class FrameIterationOperation {
    template<class Child> static auto operation(const Child& child) {
        if constexpr (std::is_same_v<Child,FramePrefixSnapshot>) return FramePrefixOperation(child);
        else if constexpr (std::is_same_v<Child,FrameActorPassSnapshot>) return FrameActorPassOperation(child);
        else if constexpr (std::is_same_v<Child,FrameTransientQueuesSnapshot>) return FrameTransientQueuesOperation(child);
        else return FrameTailOperation(child);
    }
    static FrameIterationCallee body(DosGetTimeRegisters r,uint16_t game,uint32_t id) {
        if (r.ip==0x7a57) return FramePrefixOperation(r,game,id).snapshot();
        if (r.ip==0x7ebb) return FrameActorPassOperation(r,game,id).snapshot();
        throw std::invalid_argument("Frame iteration body entry differs");
    }
public:
    using CopyBudget=FramePrefixOperation::CopyBudget;
    FrameIterationOperation(DosGetTimeRegisters r,uint16_t dos,uint16_t keyboard,uint16_t psp,
                            uint16_t game,uint32_t id)
        :state_{FramePrefixOperation(r,dos,keyboard,psp,game,id).snapshot(),game,r.ss,r.sp,r.bp,id} {
        if (r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2) || r.ip!=0x7903)
            throw std::invalid_argument("Full frame iteration entry differs");
        validate();
    }
    FrameIterationOperation(DosGetTimeRegisters r,uint16_t game,uint32_t id)
        :state_{body(r,game,id),game,r.ss,r.sp,r.bp,id,
            r.ip==0x7a57 ? FrameIterationEntry::PostRender : FrameIterationEntry::Actors} {
        if (r.cs!=game || r.ds!=static_cast<uint16_t>(game+0xaa2))
            throw std::invalid_argument("Frame iteration body ownership differs");
        validate();
    }
    explicit FrameIterationOperation(FrameIterationSnapshot state):state_(std::move(state)) {validate();}
    const FrameIterationSnapshot& snapshot() const noexcept {return state_;}
    bool finished() const noexcept {return state_.outcome!=FrameIterationOutcome::Running;}
    DosGetTimeRegisters registers() const {
        return std::visit([](const auto& child) {return operation(child).registers();},state_.callee);
    }
    bool interruptInProgress() const {
        return std::visit([](const auto& child) {return operation(child).interruptInProgress();},state_.callee);
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished frame iteration admitted IRQ");
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
                auto active=operation(child);uint64_t consumed=0;
                if constexpr (std::is_same_v<Child,FrameTailSnapshot>) consumed=active.advance(1,bus);
                else consumed=active.advance(1,bus,copies);
                if (consumed!=1) throw std::domain_error("Frame iteration child stalled");
                child=active.snapshot();
            },state_.callee);
            ++used;++state_.dispatchedInstructions;if (timer) ++state_.timerInstructions;
            transition();if (finished()) validate();
        }
        return used;
    }
private:
    FrameIterationSnapshot state_;
    [[noreturn]] static void invalid() {throw std::invalid_argument("Frame iteration continuation ownership differs");}
    size_t first() const {return state_.entry==FrameIterationEntry::Actors ? 1u : 0u;}
    template<class Child> static std::optional<FrameIterationOutcome> terminal(const Child& child) {
        const auto active=operation(child);
        if (!active.finished()) return FrameIterationOutcome::Running;
        if constexpr (std::is_same_v<Child,FramePrefixSnapshot>) {
            switch (child.outcome) {
            case FramePrefixOutcome::ActorUpdate:return std::nullopt;
            case FramePrefixOutcome::EndRunUi:return FrameIterationOutcome::EndRunUi;
            case FramePrefixOutcome::RuntimeError:return FrameIterationOutcome::RuntimeError;
            case FramePrefixOutcome::BreakOutput:return FrameIterationOutcome::BreakOutput;
            default:invalid();
            }
        } else if constexpr (std::is_same_v<Child,FrameActorPassSnapshot>) {
            switch (child.outcome) {
            case FrameActorPassOutcome::TransientQueues:return std::nullopt;
            case FrameActorPassOutcome::Restart:return FrameIterationOutcome::Restart;
            case FrameActorPassOutcome::RuntimeError:return FrameIterationOutcome::RuntimeError;
            case FrameActorPassOutcome::DivideError:return FrameIterationOutcome::DivideError;
            default:invalid();
            }
        } else if constexpr (std::is_same_v<Child,FrameTransientQueuesSnapshot>) {
            switch (child.outcome) {
            case FrameTransientQueuesOutcome::FrameTail:return std::nullopt;
            case FrameTransientQueuesOutcome::RuntimeError:return FrameIterationOutcome::RuntimeError;
            case FrameTransientQueuesOutcome::DivideError:return FrameIterationOutcome::DivideError;
            case FrameTransientQueuesOutcome::Terminated:return FrameIterationOutcome::Terminated;
            default:invalid();
            }
        } else {
            switch (child.outcome) {
            case FrameTailOutcome::NextFrame:return FrameIterationOutcome::NextFrame;
            case FrameTailOutcome::Completion:return FrameIterationOutcome::Completion;
            case FrameTailOutcome::Escape:return FrameIterationOutcome::Escape;
            case FrameTailOutcome::ViewChange:return FrameIterationOutcome::ViewChange;
            case FrameTailOutcome::RuntimeError:return FrameIterationOutcome::RuntimeError;
            case FrameTailOutcome::DivideError:return FrameIterationOutcome::DivideError;
            default:invalid();
            }
        }
    }
    void handoff(const DosGetTimeRegisters& r,uint16_t ip) const {
        if (r.cs!=state_.gameSegment || r.ds!=static_cast<uint16_t>(state_.gameSegment+0xaa2) ||
            r.ss!=state_.callerSs || r.sp!=state_.callerSp || r.bp!=state_.callerBp || r.ip!=ip)
            throw std::domain_error("Frame iteration actual handoff differs");
    }
    void transition() {
        const auto kind=state_.callee.index();
        const auto next=std::visit([&](const auto& child)->std::optional<FrameIterationCallee> {
            const auto result=terminal(child);
            if (result) {state_.outcome=*result;return std::nullopt;}
            const auto r=operation(child).registers();
            if constexpr (std::is_same_v<std::remove_cvref_t<decltype(child)>,FramePrefixSnapshot>) {
                handoff(r,0x7ebb);return FrameActorPassOperation(r,state_.gameSegment,state_.idToggleMask).snapshot();
            } else if constexpr (std::is_same_v<std::remove_cvref_t<decltype(child)>,FrameActorPassSnapshot>) {
                handoff(r,0x804e);return FrameTransientQueuesOperation(r,state_.gameSegment,state_.idToggleMask).snapshot();
            } else if constexpr (std::is_same_v<std::remove_cvref_t<decltype(child)>,FrameTransientQueuesSnapshot>) {
                handoff(r,0x806a);return FrameTailOperation(r,state_.gameSegment,state_.idToggleMask).snapshot();
            } else invalid();
        },state_.callee);
        if (next) {
            state_.completed[kind]=std::visit([](const auto& child) {
                return std::array<uint64_t,3>{child.dispatchedInstructions,child.timerInstructions,child.timerDeliveries};
            },state_.callee);
            state_.callee=*next;
        }
    }
    void validate() const {
        if ((state_.entry!=FrameIterationEntry::Full && state_.entry!=FrameIterationEntry::PostRender &&
             state_.entry!=FrameIterationEntry::Actors) ||
            (state_.idToggleMask!=0 && state_.idToggleMask!=0x200000) || state_.callee.index()<first()) invalid();
        const auto kind=state_.callee.index();
        auto totals=std::array<uint64_t,3>{state_.dispatchedInstructions,state_.timerInstructions,state_.timerDeliveries};
        for (size_t i=0;i<state_.completed.size();++i) {
            const auto& row=state_.completed[i];
            if (i<first() || i>=kind) {if (row!=std::array<uint64_t,3>{}) invalid();}
            else if (!row[0] || row[1]>row[0] || row[2]>row[1]) invalid();
            for (size_t n=0;n<3;++n) {if (row[n]>totals[n]) invalid();totals[n]-=row[n];}
        }
        std::visit([&](const auto& child) {
            using Child=std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child,FrameTransientQueuesSnapshot>) {
                if (child.caller.gameSegment!=state_.gameSegment || child.caller.idToggleMask!=state_.idToggleMask) invalid();
            } else if (child.gameSegment!=state_.gameSegment || child.idToggleMask!=state_.idToggleMask) invalid();
            if constexpr (!std::is_same_v<Child,FramePrefixSnapshot>)
                if (child.callerSs!=state_.callerSs || child.callerSp!=state_.callerSp || child.callerBp!=state_.callerBp) invalid();
            if (totals!=std::array<uint64_t,3>{child.dispatchedInstructions,child.timerInstructions,child.timerDeliveries}) invalid();
            const auto result=terminal(child);if (!result || *result!=state_.outcome) invalid();
        },state_.callee);
        if (state_.timerInstructions>state_.dispatchedInstructions || (finished() && interruptInProgress()) ||
            (!state_.timerDeliveries && (state_.timerInstructions || interruptInProgress())) ||
            (state_.timerDeliveries>state_.timerInstructions &&
                state_.timerDeliveries-state_.timerInstructions>(interruptInProgress() ? 1u : 0u))) invalid();
        const auto r=registers();
        if (kind>0 && r.ss!=state_.callerSs) invalid();
        if (!state_.dispatchedInstructions && (r.cs!=state_.gameSegment || r.ss!=state_.callerSs ||
            r.sp!=state_.callerSp || r.bp!=state_.callerBp || r.ip!=(state_.entry==FrameIterationEntry::Full ? 0x7903 :
                state_.entry==FrameIterationEntry::PostRender ? 0x7a57 : 0x7ebb))) invalid();
    }
};
} // namespace lezac::core
