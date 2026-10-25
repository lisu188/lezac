#pragma once

#include "core/actor_terrain.hpp"
#include "core/player_post.hpp"
#include "core/transient_motion.hpp"
#include "core/transient_removal.hpp"
#include "core/transient_queue_instructions.hpp"

#include <array>
#include <type_traits>
#include <tuple>
#include <variant>
#include <vector>

namespace lezac::core {
enum class TransientUpdateOutcome { Running, Returned, RuntimeError, DivideError };
using TransientUpdateHelper=std::variant<TransientMotionSnapshot,TransientRemovalSnapshot,PlayerPostSnapshot>;
struct TransientUpdateFrame {
    uint16_t segment=0,entry=0,sp=0,bp=0,callSegment=0,callIp=0;
    bool operator==(const TransientUpdateFrame&) const = default;
};
struct TransientUpdateSnapshot {
    ActorFinishSnapshot foreground;
    std::optional<TransientUpdateHelper> helper=std::nullopt;
    uint16_t callerSs=0,callerSp=0,callerBp=0;
    TransientUpdateOutcome outcome=TransientUpdateOutcome::Running;
    uint64_t dispatchedInstructions=0,timerInstructions=0,timerDeliveries=0,transferredBytes=0;
    std::array<uint64_t,3> helperCalls{},helperReturns{};
    std::vector<TransientUpdateFrame> frames{};
    uint64_t completedInstructions=0,completedTimerInstructions=0,completedTimerDeliveries=0,completedBytes=0;
    bool operator==(const TransientUpdateSnapshot&) const = default;
};

// Complete original 45FA spark/debris updater on one borrowed memory bus.
class TransientUpdateOperation {
    template<class Child> static auto operation(const Child& child) {
        if constexpr (std::is_same_v<Child,TransientMotionSnapshot>) return TransientMotionOperation(child);
        else if constexpr (std::is_same_v<Child,TransientRemovalSnapshot>) return TransientRemovalOperation(child);
        else return PlayerPostOperation(child);
    }
public:
    using CopyBudget=ActorFinishOperation::CopyBudget;
    TransientUpdateOperation(DosGetTimeRegisters r,uint16_t game,uint32_t idToggle)
        :state_{ActorFinishSnapshot{r,game,idToggle},std::nullopt,r.ss,static_cast<uint16_t>(r.sp+2u),r.bp} {
        if (r.cs!=game || r.ip!=0x45fa) throw std::invalid_argument("Transient updater entry differs");
        state_.frames.push_back({0,0x45fa,r.sp,r.bp,0,0});validate();
    }
    explicit TransientUpdateOperation(TransientUpdateSnapshot state):state_(std::move(state)) {validate();}
    const TransientUpdateSnapshot& snapshot() const noexcept {return state_;}
    bool finished() const noexcept {return state_.outcome!=TransientUpdateOutcome::Running;}
    DosGetTimeRegisters registers() const {
        if (state_.helper) return std::visit([](const auto& child) {return operation(child).registers();},*state_.helper);
        return ActorFinishOperation(state_.foreground).registers();
    }
    bool interruptInProgress() const {
        if (state_.helper) return std::visit([](const auto& child) {return operation(child).interruptInProgress();},*state_.helper);
        return state_.foreground.timer.has_value();
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished()) throw std::logic_error("Finished transient updater admitted IRQ");
        if (state_.helper) std::visit([&](auto& child) {
            auto active=operation(child);active.deliverTimerInterrupt(bus);child=active.snapshot();
        },*state_.helper);
        else {
            ActorFinishOperation irq(state_.foreground);irq.deliverTimerInterrupt(bus);state_.foreground=irq.snapshot();
        }
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while (used<budget && !finished()) {
            const bool timer=interruptInProgress();
            if (state_.helper) {
                std::visit([&](auto& child) {
                    using Child=std::remove_cvref_t<decltype(child)>;
                    auto active=operation(child);const auto before=helperBytes(child);
                    uint64_t count=0;
                    if constexpr (std::is_same_v<Child,TransientMotionSnapshot>) count=active.advance(1,bus);
                    else count=active.advance(1,bus,copies);
                    if (count!=1) throw std::domain_error("Transient updater helper did not dispatch");
                    child=active.snapshot();state_.transferredBytes+=helperBytes(child)-before;
                },*state_.helper);
            } else foregroundInstruction(bus,copies);
            ++used;++state_.dispatchedInstructions;if (timer) ++state_.timerInstructions;
            transition();
            if (finished()) validate();
        }
        return used;
    }
private:
    TransientUpdateSnapshot state_;
    uint16_t game() const {return state_.foreground.gameSegment;}
    uint16_t library() const {return static_cast<uint16_t>(game()+0x920);}
    template<class Child> static uint64_t helperBytes(const Child& child) {
        if constexpr (std::is_same_v<Child,PlayerPostSnapshot>) return child.stringTransfers;
        else return child.cpu.transferredBytes;
    }
    static void invalid() {throw std::invalid_argument("Transient updater continuation ownership differs");}
    static const TransientQueueStackProfile* profile(const TransientUpdateFrame& frame,uint16_t ip) {
        const auto key=std::tuple{frame.segment,frame.entry,ip};
        const auto found=std::lower_bound(kTransientStackProfiles.begin(),kTransientStackProfiles.end(),key,
            [](const auto& p,const auto& value) {return std::tuple{p.segment,p.entry,p.ip}<value;});
        return found!=kTransientStackProfiles.end() && std::tuple{found->segment,found->entry,found->ip}==key ? &*found : nullptr;
    }
    static const TransientQueueCall* call(uint16_t segment,uint16_t ip) {
        const auto key=std::pair{segment,ip};
        const auto found=std::lower_bound(kTransientCalls.begin(),kTransientCalls.end(),key,
            [](const auto& c,const auto& value) {return std::pair{c.segment,c.ip}<value;});
        return found!=kTransientCalls.end() && std::pair{found->segment,found->ip}==key ? &*found : nullptr;
    }
    static uint16_t stack(const TransientUpdateFrame& frame,const TransientQueueStackProfile& p) {
        return static_cast<uint16_t>(frame.sp+p.sp);
    }
    static uint16_t base(const TransientUpdateFrame& frame,const TransientQueueStackProfile& p) {
        return p.bpKind==0 ? frame.bp : static_cast<uint16_t>(frame.sp+p.bp);
    }
    void validateFrames() const {
        if (state_.frames.empty() || state_.frames.size()>32) invalid();
        const auto& root=state_.frames.front();
        if (root.segment || root.entry!=0x45fa || root.sp!=static_cast<uint16_t>(state_.callerSp-2u) ||
            root.bp!=state_.callerBp || root.callSegment || root.callIp) invalid();
        for (size_t i=1;i<state_.frames.size();++i) {
            const auto& child=state_.frames[i];const auto& parent=state_.frames[i-1];
            const auto* c=call(child.callSegment,child.callIp);const auto* p=profile(parent,child.callIp);
            if (!c || !p || child.callSegment!=parent.segment || child.segment!=c->targetSegment || child.entry!=c->target ||
                child.sp!=static_cast<uint16_t>(stack(parent,*p)-c->width) || p->bpKind==2 || child.bp!=base(parent,*p)) invalid();
        }
        const auto& frame=state_.frames.back();const auto& r=state_.foreground.registers;
        if (finished()) {
            if (state_.outcome==TransientUpdateOutcome::Returned && (state_.frames.size()!=1 || r.ip!=0x8060)) invalid();
            if (state_.outcome!=TransientUpdateOutcome::DivideError) return;
        }
        if (state_.helper) {
            if (r.cs!=static_cast<uint16_t>(game()+frame.segment) || r.ip!=frame.entry || r.sp!=frame.sp || r.bp!=frame.bp) invalid();
        } else if (profile(frame,frame.entry)) {
            const auto* p=profile(frame,r.ip);
            if (!p || r.cs!=static_cast<uint16_t>(game()+frame.segment) || r.sp!=stack(frame,*p) ||
                (p->bpKind!=2 && r.bp!=base(frame,*p))) invalid();
        } else if (r.cs!=library() || r.ip<0xbe1 || r.ip>=0x13a8) invalid();
    }
    void foregroundTransition(const DosGetTimeRegisters& before) {
        auto& r=state_.foreground.registers;
        const auto& frame=state_.frames.back();
        if (profile(frame,frame.entry)) {
            if (const auto* c=call(static_cast<uint16_t>(before.cs-game()),before.ip)) {
                if (state_.frames.size()>=32 || r.cs!=static_cast<uint16_t>(game()+c->targetSegment) || r.ip!=c->target)
                    throw std::domain_error("Transient updater actual call differs");
                state_.frames.push_back({c->targetSegment,c->target,r.sp,r.bp,c->segment,c->ip});return;
            }
        }
        if (state_.frames.size()>1) {
            const auto* c=call(frame.callSegment,frame.callIp);
            if (c && r.cs==static_cast<uint16_t>(game()+c->segment) && r.ip==c->next) state_.frames.pop_back();
        }
    }
    void validate() const {
        const auto& fg=state_.foreground;const auto& r=fg.registers;
        (void)ActorFinishOperation(fg);
        validateFrames();
        uint64_t instructions=fg.dispatchedInstructions+state_.completedInstructions;
        uint64_t timers=fg.timerInstructions+state_.completedTimerInstructions;
        uint64_t deliveries=fg.timerDeliveries+state_.completedTimerDeliveries;
        uint64_t bytes=fg.transferredBytes+state_.completedBytes;
        if (state_.helper) std::visit([&](const auto& child) {
            const auto& cpu=[&]() -> const auto& {
                if constexpr (std::is_same_v<std::remove_cvref_t<decltype(child)>,PlayerPostSnapshot>) return child;
                else return child.cpu;
            }();
            instructions+=cpu.dispatchedInstructions;timers+=cpu.timerInstructions;
            deliveries+=cpu.timerDeliveries;bytes+=helperBytes(child);
        },*state_.helper);
        if (fg.outcome!=ActorFinishOutcome::Running || r.ss!=state_.callerSs ||
            state_.dispatchedInstructions!=instructions || state_.timerInstructions!=timers ||
            state_.timerDeliveries!=deliveries || state_.transferredBytes!=bytes ||
            (r.cs!=game() && r.cs!=library()) ||
            (r.cs==game() && r.ds!=static_cast<uint16_t>(game()+0xaa2)) ||
            fg.dispatchedInstructions>state_.dispatchedInstructions || fg.timerInstructions>state_.timerInstructions ||
            fg.timerDeliveries>state_.timerDeliveries || fg.transferredBytes>state_.transferredBytes ||
            state_.timerInstructions>state_.dispatchedInstructions ||
            (!state_.timerDeliveries && (state_.timerInstructions || interruptInProgress())) ||
            (state_.timerDeliveries>state_.timerInstructions &&
                state_.timerDeliveries-state_.timerInstructions>(interruptInProgress() ? 1u : 0u)) ||
            (state_.outcome!=TransientUpdateOutcome::Running && state_.outcome!=TransientUpdateOutcome::Returned &&
             state_.outcome!=TransientUpdateOutcome::RuntimeError && state_.outcome!=TransientUpdateOutcome::DivideError) ||
            (finished() && interruptInProgress()) || (state_.helper && fg.timer)) invalid();
        for (size_t i=0;i<state_.helperCalls.size();++i) {
            if (state_.helperCalls[i]>state_.dispatchedInstructions || state_.helperReturns[i]>state_.helperCalls[i] ||
                state_.helperCalls[i]-state_.helperReturns[i]!=(state_.helper && state_.helper->index()==i ? 1u : 0u)) invalid();
        }
        if (state_.helper) std::visit([&](const auto& child) {
            using Child=std::remove_cvref_t<decltype(child)>;
            const auto& cpu=[&]() -> const auto& {
                if constexpr (std::is_same_v<Child,PlayerPostSnapshot>) return child;
                else return child.cpu;
            }();
            const auto active=operation(child);
            if (cpu.gameSegment!=game() || cpu.idToggleMask!=fg.idToggleMask ||
                child.callerSs!=state_.callerSs || child.callerBp!=r.bp ||
                child.callerSp!=static_cast<uint16_t>(r.sp+(std::is_same_v<Child,PlayerPostSnapshot> ? 4u :
                    std::is_same_v<Child,TransientRemovalSnapshot> ? 6u : 2u)) ||
                cpu.dispatchedInstructions>state_.dispatchedInstructions ||
                cpu.timerInstructions>state_.timerInstructions || cpu.timerDeliveries>state_.timerDeliveries ||
                helperBytes(child)>state_.transferredBytes ||
                (active.finished()!=(state_.outcome==TransientUpdateOutcome::RuntimeError))) invalid();
            if constexpr (std::is_same_v<Child,TransientMotionSnapshot>) {
                if (r.cs!=game() || r.ip!=0x3eda) invalid();
            } else if constexpr (std::is_same_v<Child,TransientRemovalSnapshot>) {
                if (r.cs!=game() || r.ip!=(child.kind==TransientRemovalKind::Spark ? 0x452a : 0x458d)) invalid();
            } else if (r.cs!=library() || r.ip!=0x945 || child.entry!=PlayerPostEntry::ScoreDivide) invalid();
        },*state_.helper);
        else if (state_.outcome==TransientUpdateOutcome::Running &&
            !(r.cs==game() && transientQueueInstructionBoundary(r.ip)) &&
            !transientQueueBorrowedBoundary(r.cs,r.ip,game())) invalid();
        const auto live=registers();
        if (state_.outcome==TransientUpdateOutcome::Returned &&
            (state_.helper || live.cs!=game() || live.sp!=state_.callerSp || live.bp!=state_.callerBp)) invalid();
        if (state_.outcome==TransientUpdateOutcome::RuntimeError && (live.cs!=library() || live.ip!=0xe2)) invalid();
        if (state_.outcome==TransientUpdateOutcome::DivideError &&
            (state_.helper || live.cs!=game() || (live.ip!=0x4818 && live.ip!=0x484c))) invalid();
    }
    void foregroundInstruction(const TimerIrqBus& bus,const CopyBudget& copies) {
        auto& fg=state_.foreground;const auto before=fg.transferredBytes;
        if (fg.timer) {
            ActorFinishOperation irq(fg);irq.advance(1,bus,copies);fg=irq.snapshot();
        } else {
            const auto pc=fg.registers;
            try {
                if (advanceTransientQueueInstruction(fg.registers,game(),bus)) ++fg.dispatchedInstructions;
                else if (pc.cs==game() && pc.ip>=0x370e && pc.ip<0x3a7e) {
                    advanceActorTerrainInstruction(fg.registers,game(),bus);++fg.dispatchedInstructions;
                } else {
                    ActorFinishOperation child(fg);
                    if (child.advance(1,bus,copies)!=1) throw std::domain_error("Transient updater borrowed instruction stalled");
                    fg=child.snapshot();fg.outcome=ActorFinishOutcome::Running;
                }
                if (pc.cs==game() && pc.ip==0x4d3b) state_.outcome=TransientUpdateOutcome::Returned;
                foregroundTransition(pc);
            } catch (const TransientQueueDivideFault&) {
                ++fg.dispatchedInstructions;state_.outcome=TransientUpdateOutcome::DivideError;
            }
        }
        state_.transferredBytes+=fg.transferredBytes-before;
    }
    void transition() {
        if (state_.helper) {
            bool returned=false;
            std::visit([&](const auto& child) {
                using Child=std::remove_cvref_t<decltype(child)>;
                const auto active=operation(child);if (!active.finished()) return;
                if constexpr (std::is_same_v<Child,TransientMotionSnapshot>) returned=true;
                else if constexpr (std::is_same_v<Child,TransientRemovalSnapshot>) returned=child.outcome==TransientRemovalOutcome::Returned;
                else returned=child.outcome==PlayerPostOutcome::Returned;
                if (returned) {
                    state_.foreground.registers=active.registers();
                    const auto& cpu=[&]() -> const auto& {
                        if constexpr (std::is_same_v<Child,PlayerPostSnapshot>) return child;
                        else return child.cpu;
                    }();
                    state_.completedInstructions+=cpu.dispatchedInstructions;state_.completedTimerInstructions+=cpu.timerInstructions;
                    state_.completedTimerDeliveries+=cpu.timerDeliveries;state_.completedBytes+=helperBytes(child);
                }
                else state_.outcome=TransientUpdateOutcome::RuntimeError;
            },*state_.helper);
            if (returned) {
                ++state_.helperReturns[state_.helper->index()];state_.helper.reset();
                if (state_.frames.size()<2) throw std::domain_error("Transient updater helper lacks caller");
                const auto& frame=state_.frames.back();const auto* c=call(frame.callSegment,frame.callIp);
                const auto r=state_.foreground.registers;
                if (!c || r.cs!=static_cast<uint16_t>(game()+c->segment) || r.ip!=c->next)
                    throw std::domain_error("Transient updater helper return differs");
                state_.frames.pop_back();
            }
        }
        if (!state_.helper && !finished() && !state_.foreground.timer) {
            const auto r=state_.foreground.registers;const auto id=state_.foreground.idToggleMask;
            if (r.cs==library() && r.ip==0xe2) state_.outcome=TransientUpdateOutcome::RuntimeError;
            else if (r.cs==game() && r.ip==0x3eda) state_.helper=TransientMotionOperation(r,game(),id).snapshot();
            else if (r.cs==game() && (r.ip==0x452a || r.ip==0x458d)) state_.helper=TransientRemovalOperation(r,game(),id).snapshot();
            else if (r.cs==library() && r.ip==0x945) state_.helper=PlayerPostOperation(r,game(),id,PlayerPostEntry::ScoreDivide).snapshot();
            if (state_.helper) ++state_.helperCalls[state_.helper->index()];
        }
    }
};
} // namespace lezac::core
