#pragma once

#include "core/interruptible_frame_clock.hpp"
#include "core/interruptible_frame_display.hpp"

namespace lezac::core {

struct FramePacingCalculationSnapshot {
    InterruptibleFrameClockSnapshot elapsed;
    std::optional<InterruptibleFrameDisplaySnapshot> display;
    uint64_t dispatchedInstructions = 0;
    bool operator==(const FramePacingCalculationSnapshot&) const = default;
};

// Computed DOS IRET -> elapsed store -> software Real48 display store, on one bus.
class FramePacingCalculationOperation {
public:
    FramePacingCalculationOperation(DosGetTimeRegisters registers, uint16_t callbackBase, uint16_t psp,
                                   uint16_t game, uint32_t idToggle)
        : state_{InterruptibleFrameClockOperation(registers, callbackBase, psp, game, idToggle).snapshot(), std::nullopt} {}
    explicit FramePacingCalculationOperation(FramePacingCalculationSnapshot state) : state_(state) {}
    const FramePacingCalculationSnapshot& snapshot() const noexcept { return state_; }
    bool finished() const { return state_.display && InterruptibleFrameDisplayOperation(*state_.display).finished(); }
    bool returned() const { return state_.display && InterruptibleFrameDisplayOperation(*state_.display).returned(); }
    bool interruptInProgress() const {
        return state_.display ? state_.display->timer.has_value() : InterruptibleFrameClockOperation(state_.elapsed).interruptInProgress();
    }
    DosGetTimeRegisters registers() const {
        return state_.display ? InterruptibleFrameDisplayOperation(*state_.display).registers() :
            InterruptibleFrameClockOperation(state_.elapsed).registers();
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (state_.display) {
            InterruptibleFrameDisplayOperation operation(*state_.display);
            operation.deliverTimerInterrupt(bus);
            state_.display = operation.snapshot();
        } else {
            InterruptibleFrameClockOperation operation(state_.elapsed);
            operation.deliverTimerInterrupt(bus);
            state_.elapsed = operation.snapshot();
        }
    }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus) {
        uint64_t consumed = 0;
        while (consumed < budget && !finished()) {
            if (state_.display) {
                InterruptibleFrameDisplayOperation operation(*state_.display);
                if (operation.advance(1, bus) != 1)
                    throw std::domain_error("Display calculation did not dispatch an instruction");
                ++consumed;
                state_.display = operation.snapshot();
            } else {
                InterruptibleFrameClockOperation operation(state_.elapsed);
                if (operation.advance(1, bus) != 1)
                    throw std::domain_error("Elapsed calculation did not dispatch an instruction");
                ++consumed;
                state_.elapsed = operation.snapshot();
                if (operation.returned()) {
                    const auto r = operation.registers();
                    if (r.cs != state_.elapsed.dos.gameSegment || r.ip != 0x7966)
                        throw std::domain_error("Pacing calculation did not reach the display caller");
                    state_.display = InterruptibleFrameDisplayOperation(r, state_.elapsed.dos.gameSegment,
                        state_.elapsed.dos.dos.idToggleMask).snapshot();
                }
            }
            ++state_.dispatchedInstructions;
        }
        return consumed;
    }

private:
    FramePacingCalculationSnapshot state_;
};

}
