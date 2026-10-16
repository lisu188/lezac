#pragma once

#include "core/frame_display.hpp"

#include <optional>

namespace lezac::core {

struct InterruptibleFrameDisplaySnapshot {
    FrameDisplaySnapshot display;
    std::optional<TimerIrqSnapshot> timer;
    uint32_t idToggleMask = 0;
    uint64_t dispatchedInstructions = 0, timerInstructions = 0, timerDeliveries = 0;
    bool operator==(const InterruptibleFrameDisplaySnapshot&) const = default;
};

// PIC eligibility belongs to the caller; original math and IRQ0 share one bus.
class InterruptibleFrameDisplayOperation {
public:
    InterruptibleFrameDisplayOperation(DosGetTimeRegisters registers, uint16_t game, uint32_t idToggleMask)
        : state_{FrameDisplayOperation(registers, game).snapshot(), std::nullopt, idToggleMask} {}
    explicit InterruptibleFrameDisplayOperation(InterruptibleFrameDisplaySnapshot state) : state_(state) {}
    const InterruptibleFrameDisplaySnapshot& snapshot() const noexcept { return state_; }
    bool interruptInProgress() const noexcept { return state_.timer.has_value(); }
    bool finished() const noexcept { return !state_.timer && state_.display.outcome != FrameDisplayOutcome::Running; }
    bool returned() const noexcept { return !state_.timer && state_.display.outcome == FrameDisplayOutcome::Returned; }
    DosGetTimeRegisters registers() const {
        return state_.timer ? fromTimer(state_.timer->registers) : state_.display.registers;
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (state_.timer || !(state_.display.registers.flags & 0x200u))
            throw std::logic_error("Frame display timer is not eligible");
        auto r = toTimer(state_.display.registers);
        const auto push = [&](uint16_t value) { r.sp = static_cast<uint16_t>(r.sp - 2u); bus.writeWord(r.ss, r.sp, value); };
        push(static_cast<uint16_t>(r.flags)); push(r.cs); push(r.ip);
        r.flags &= ~uint32_t{0x300}; r.cs = 0xf000; r.ip = 0xfea5;
        state_.timer = TimerIrqOperation(r, state_.display.gameSegment, state_.idToggleMask).snapshot();
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus) {
        uint64_t consumed = 0;
        while (consumed < budget && !finished()) {
            if (state_.timer) {
                TimerIrqOperation timer(*state_.timer);
                timer.advance(1, bus);
                ++state_.timerInstructions;
                if (timer.returned()) {
                    state_.display.registers = fromTimer(timer.snapshot().registers);
                    state_.timer.reset();
                } else state_.timer = timer.snapshot();
            } else {
                FrameDisplayOperation display(state_.display);
                display.advance(1, bus);
                state_.display = display.snapshot();
            }
            ++state_.dispatchedInstructions; ++consumed;
        }
        return consumed;
    }

private:
    static TimerIrqRegisters toTimer(const DosGetTimeRegisters& r) {
        return {r.ax, r.bx, r.cx, r.dx, r.si, r.di, r.bp, r.cs, r.ds, r.es, r.ss, r.sp, r.ip, r.flags};
    }
    static DosGetTimeRegisters fromTimer(const TimerIrqRegisters& r) {
        return {r.ax, r.bx, r.cx, r.dx, r.si, r.di, r.bp, r.cs, r.ds, r.es, r.ss, r.sp, r.ip, r.flags};
    }
    InterruptibleFrameDisplaySnapshot state_;
};

}
