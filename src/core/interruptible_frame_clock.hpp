#pragma once

#include "core/frame_elapsed.hpp"
#include "core/interruptible_dos_time.hpp"

#include <optional>
#include <stdexcept>

namespace lezac::core {

struct InterruptibleFrameClockSnapshot {
    InterruptibleDosTimeSnapshot dos;
    std::optional<FrameElapsedSnapshot> frame;
    std::optional<TimerIrqSnapshot> foregroundTimer;
    uint64_t dispatchedInstructions = 0, timerDeliveries = 0;
    bool operator==(const InterruptibleFrameClockSnapshot&) const = default;
};

// PIC owns eligibility. A timer may arrive after DOS IRET, before the caller's first instruction.
class InterruptibleFrameClockOperation {
public:
    InterruptibleFrameClockOperation(DosGetTimeRegisters registers, uint16_t callbackBase,
                                    uint16_t psp, uint16_t game, uint32_t idToggle)
        : state_{InterruptibleDosTimeOperation(registers, callbackBase, psp, game, idToggle).snapshot(),
                 std::nullopt, std::nullopt} {}
    explicit InterruptibleFrameClockOperation(InterruptibleFrameClockSnapshot state) : state_(state) {}
    const InterruptibleFrameClockSnapshot& snapshot() const noexcept { return state_; }
    bool interruptInProgress() const noexcept { return state_.foregroundTimer.has_value() || state_.dos.timer.has_value(); }
    bool returned() const noexcept {
        return state_.frame ? state_.frame->returned && !state_.foregroundTimer : state_.dos.dos.returned && !state_.dos.timer;
    }
    DosGetTimeRegisters registers() const {
        if (state_.foregroundTimer) return fromTimer(state_.foregroundTimer->registers);
        if (state_.frame) return state_.frame->registers;
        return InterruptibleDosTimeOperation(state_.dos).registers();
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (!state_.frame) {
            InterruptibleDosTimeOperation dos(state_.dos);
            dos.deliverTimerInterrupt(bus);
            state_.dos = dos.snapshot();
        } else {
            if (state_.foregroundTimer || !(state_.frame->registers.flags & 0x200u))
                throw std::logic_error("Foreground timer is not eligible");
            auto r = toTimer(state_.frame->registers);
            const auto push = [&](uint16_t value) {
                r.sp = static_cast<uint16_t>(r.sp - 2u);
                bus.writeWord(r.ss, r.sp, value);
            };
            push(static_cast<uint16_t>(r.flags)); push(r.cs); push(r.ip);
            r.flags &= ~uint32_t{0x300}; r.cs = 0xf000; r.ip = 0xfea5;
            state_.foregroundTimer = TimerIrqOperation(r, state_.dos.gameSegment, state_.dos.dos.idToggleMask).snapshot();
        }
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus) {
        uint64_t consumed = 0;
        while (consumed < budget && !returned()) {
            if (state_.foregroundTimer) {
                TimerIrqOperation timer(*state_.foregroundTimer);
                timer.advance(1, bus);
                if (timer.returned()) {
                    state_.frame->registers = fromTimer(timer.snapshot().registers);
                    state_.foregroundTimer.reset();
                } else state_.foregroundTimer = timer.snapshot();
            } else if (state_.frame) {
                FrameElapsedOperation frame(*state_.frame);
                frame.advance(1, bus);
                state_.frame = frame.snapshot();
            } else {
                InterruptibleDosTimeOperation dos(state_.dos);
                dos.advance(1, bus);
                state_.dos = dos.snapshot();
                const auto r = dos.registers();
                if (dos.returned() && r.cs == state_.dos.gameSegment && r.ip == 0x791e)
                    state_.frame = FrameElapsedOperation(r, state_.dos.gameSegment).snapshot();
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
    InterruptibleFrameClockSnapshot state_;
};

}
