#pragma once

#include "core/frame_hud.hpp"
#include "core/frame_pacing_operation.hpp"

namespace lezac::core {

struct FrameForegroundSnapshot {
    FramePacingSnapshot pacing;
    std::optional<FrameHudSnapshot> hud=std::nullopt;
    uint16_t keyboardBase=0;
    uint64_t dispatchedInstructions=0;
    bool operator==(const FrameForegroundSnapshot&) const = default;
};

// Original 7903..7A13 on one memory bus. DOS and BIOS callback bases are distinct.
class FrameForegroundOperation {
public:
    FrameForegroundOperation(DosGetTimeRegisters r,uint16_t dosBase,uint16_t keyboardBase,
                             uint16_t psp,uint16_t game,uint32_t idToggle)
        :state_{FramePacingOperation(r,dosBase,psp,game,idToggle).snapshot(),std::nullopt,keyboardBase} {
        if(keyboardBase>0xffec) throw std::invalid_argument("Foreground keyboard callback differs");
    }
    explicit FrameForegroundOperation(FrameForegroundSnapshot state):state_(state) {}
    const FrameForegroundSnapshot& snapshot() const noexcept {return state_;}
    bool finished() const {
        return state_.hud?FrameHudOperation(*state_.hud).finished():FramePacingOperation(state_.pacing).finished();
    }
    bool returned() const {return state_.hud && FrameHudOperation(*state_.hud).returned();}
    bool interruptInProgress() const {
        return state_.hud?FrameHudOperation(*state_.hud).interruptInProgress():FramePacingOperation(state_.pacing).interruptInProgress();
    }
    DosGetTimeRegisters registers() const {
        return state_.hud?FrameHudOperation(*state_.hud).registers():FramePacingOperation(state_.pacing).registers();
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if(state_.hud) {
            FrameHudOperation operation(*state_.hud);operation.deliverTimerInterrupt(bus);state_.hud=operation.snapshot();
        } else {
            FramePacingOperation operation(state_.pacing);operation.deliverTimerInterrupt(bus);state_.pacing=operation.snapshot();
        }
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const FrameHudOperation::CopyBudget& copies) {
        uint64_t consumed=0;
        while(consumed<budget && !finished()) {
            if(state_.hud) {
                FrameHudOperation operation(*state_.hud);
                if(operation.advance(1,bus,copies)!=1) throw std::domain_error("Foreground HUD did not dispatch");
                state_.hud=operation.snapshot();
            } else {
                FramePacingOperation operation(state_.pacing);
                if(operation.advance(1,bus)!=1) throw std::domain_error("Foreground pacing did not dispatch");
                state_.pacing=operation.snapshot();
                if(operation.returned()) {
                    const auto r=operation.registers();
                    if(r.cs!=state_.pacing.gameSegment || r.ip!=0x79e8) throw std::domain_error("Foreground pacing handoff differs");
                    state_.hud=FrameHudOperation(r,state_.keyboardBase,state_.pacing.gameSegment,state_.pacing.idToggleMask).snapshot();
                }
            }
            ++consumed;++state_.dispatchedInstructions;
        }
        return consumed;
    }
private:
    FrameForegroundSnapshot state_;
};

}
