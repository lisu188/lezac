#pragma once

#include "core/frame_active.hpp"
#include "core/frame_spawner.hpp"
#include "core/frame_waiting.hpp"

namespace lezac::core {

enum class FramePrefixOutcome { Running, ActorUpdate, EndRunUi, RuntimeError, BreakOutput };
using FramePrefixCallee = std::variant<FrameActiveSnapshot, FrameSpawnerSnapshot, FrameWaitingSnapshot>;
struct FramePrefixSnapshot {
    FramePrefixCallee callee;
    uint16_t gameSegment = 0;
    uint32_t idToggleMask = 0;
    FramePrefixOutcome outcome = FramePrefixOutcome::Running;
    std::optional<TimerIrqSnapshot> spawnerTimer = std::nullopt;
    uint64_t dispatchedInstructions = 0, timerInstructions = 0, timerDeliveries = 0;
    bool operator==(const FramePrefixSnapshot&) const = default;
};

// One continuous 7903..7EBB prefix. ActorUpdate is an explicit handoff, not
// completion of the original iteration or an executed actor-update call.
class FramePrefixOperation {
public:
    using CopyBudget = FrameHudOperation::CopyBudget;
    FramePrefixOperation(DosGetTimeRegisters r, uint16_t dosBase, uint16_t keyboardBase,
                         uint16_t psp, uint16_t game, uint32_t idToggle)
        : state_{FrameActiveOperation(r, dosBase, keyboardBase, psp, game, idToggle).snapshot(), game, idToggle} {}
    FramePrefixOperation(DosGetTimeRegisters r, uint16_t game, uint32_t idToggle)
        : state_{FrameSpawnerOperation(r, game).snapshot(), game, idToggle} {
        validate();
    }
    explicit FramePrefixOperation(FramePrefixSnapshot state) : state_(state) { validate(); }
    const FramePrefixSnapshot& snapshot() const noexcept { return state_; }
    bool finished() const noexcept { return state_.outcome != FramePrefixOutcome::Running && !state_.spawnerTimer; }
    DosGetTimeRegisters registers() const {
        if (state_.spawnerTimer) return fromTimer(state_.spawnerTimer->registers);
        return std::visit([](const auto& child) -> DosGetTimeRegisters {
            using Child = std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child, FrameActiveSnapshot>) return FrameActiveOperation(child).registers();
            else if constexpr (std::is_same_v<Child, FrameWaitingSnapshot>) return FrameWaitingOperation(child).registers();
            else return child.registers;
        }, state_.callee);
    }
    bool interruptInProgress() const {
        if (state_.spawnerTimer) return true;
        return std::visit([](const auto& child) {
            using Child = std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child, FrameActiveSnapshot>) return FrameActiveOperation(child).interruptInProgress();
            else if constexpr (std::is_same_v<Child, FrameWaitingSnapshot>) return FrameWaitingOperation(child).interruptInProgress();
            else return false;
        }, state_.callee);
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (finished() || interruptInProgress() || !(registers().flags & 0x200u))
            throw std::logic_error("Frame prefix IRQ is not eligible");
        std::visit([&](auto& child) {
            using Child = std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child, FrameSpawnerSnapshot>) {
                auto r = child.registers;
                const auto push = [&](uint16_t value) { r.sp = static_cast<uint16_t>(r.sp - 2u); bus.writeWord(r.ss, r.sp, value); };
                push(static_cast<uint16_t>(r.flags)); push(r.cs); push(r.ip);
                r.flags &= ~uint32_t{0x300}; r.cs = 0xf000; r.ip = 0xfea5;
                state_.spawnerTimer = TimerIrqOperation(toTimer(r), state_.gameSegment, state_.idToggleMask).snapshot();
            } else {
                using Operation = std::conditional_t<std::is_same_v<Child, FrameActiveSnapshot>, FrameActiveOperation, FrameWaitingOperation>;
                Operation operation(child); operation.deliverTimerInterrupt(bus); child = operation.snapshot();
            }
        }, state_.callee);
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus, const CopyBudget& copies) {
        uint64_t used = 0;
        while (used < budget && !finished()) {
            if (state_.spawnerTimer) {
                TimerIrqOperation timer(*state_.spawnerTimer);
                if (timer.advance(1, bus) != 1) throw std::domain_error("Frame prefix IRQ did not dispatch");
                ++state_.timerInstructions;
                if (timer.returned()) {
                    std::get<FrameSpawnerSnapshot>(state_.callee).registers = fromTimer(timer.snapshot().registers);
                    state_.spawnerTimer.reset();
                } else state_.spawnerTimer = timer.snapshot();
            } else {
                const bool timer = interruptInProgress();
                int next = -1;
                DosGetTimeRegisters handoff;
                std::visit([&](auto& child) {
                    using Child = std::remove_cvref_t<decltype(child)>;
                    if constexpr (std::is_same_v<Child, FrameSpawnerSnapshot>) {
                        FrameSpawnerOperation operation(child);
                        if (operation.advance(1, bus) != 1) throw std::domain_error("Frame prefix spawner did not dispatch");
                        child = operation.snapshot();
                        if (operation.finished()) {
                            if (operation.returned()) { next = 1; handoff = child.registers; }
                            else state_.outcome = FramePrefixOutcome::RuntimeError;
                        }
                    } else {
                        using Operation = std::conditional_t<std::is_same_v<Child, FrameActiveSnapshot>, FrameActiveOperation, FrameWaitingOperation>;
                        Operation operation(child);
                        if (operation.advance(1, bus, copies) != 1) throw std::domain_error("Frame prefix callee did not dispatch");
                        child = operation.snapshot();
                        if (operation.finished()) {
                            if constexpr (std::is_same_v<Child, FrameActiveSnapshot>) {
                                if (operation.returned()) { next = 0; handoff = operation.registers(); }
                                else state_.outcome = child.foreground.hud && child.foreground.hud->outcome == FrameHudOutcome::BreakOutput
                                    ? FramePrefixOutcome::BreakOutput : FramePrefixOutcome::RuntimeError;
                            } else {
                                state_.outcome = child.outcome == FrameWaitingOutcome::Completed ? FramePrefixOutcome::ActorUpdate
                                    : child.outcome == FrameWaitingOutcome::EndRun ? FramePrefixOutcome::EndRunUi : FramePrefixOutcome::RuntimeError;
                            }
                        }
                    }
                }, state_.callee);
                if (timer) ++state_.timerInstructions;
                if (next == 0) state_.callee = FrameSpawnerOperation(handoff, state_.gameSegment).snapshot();
                if (next == 1) state_.callee = FrameWaitingOperation(handoff, state_.gameSegment, state_.idToggleMask).snapshot();
            }
            ++used; ++state_.dispatchedInstructions;
        }
        return used;
    }
private:
    void validate() const {
        if (state_.idToggleMask != 0 && state_.idToggleMask != 0x200000)
            throw std::invalid_argument("Frame prefix ID-toggle profile differs");
        const bool matching = std::visit([&](const auto& child) {
            using Child = std::remove_cvref_t<decltype(child)>;
            if constexpr (std::is_same_v<Child, FrameActiveSnapshot>)
                return child.foreground.pacing.gameSegment == state_.gameSegment && child.foreground.pacing.idToggleMask == state_.idToggleMask;
            else if constexpr (std::is_same_v<Child, FrameWaitingSnapshot>)
                return child.gameSegment == state_.gameSegment && child.idToggleMask == state_.idToggleMask;
            else return child.gameSegment == state_.gameSegment;
        }, state_.callee);
        if (!matching || (state_.spawnerTimer && (!std::holds_alternative<FrameSpawnerSnapshot>(state_.callee) ||
                state_.outcome != FramePrefixOutcome::Running)))
            throw std::invalid_argument("Frame prefix callee/IRQ ownership differs");
    }
    static TimerIrqRegisters toTimer(const DosGetTimeRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    static DosGetTimeRegisters fromTimer(const TimerIrqRegisters& r) { return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags}; }
    FramePrefixSnapshot state_;
};

} // namespace lezac::core
