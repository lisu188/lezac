#pragma once

#include "core/frame_foreground.hpp"
#include "core/frame_render.hpp"

namespace lezac::core {

struct FrameActiveSnapshot {
    FrameForegroundSnapshot foreground;
    std::optional<FrameRenderSnapshot> render=std::nullopt;
    std::optional<TimerIrqSnapshot> renderTimer=std::nullopt;
    uint64_t dispatchedInstructions=0,timerInstructions=0,timerDeliveries=0;
    bool operator==(const FrameActiveSnapshot&) const = default;
};

// Original 7903..7A57 on one bus. The external clock owns legal IRQ/REP grants.
class FrameActiveOperation {
public:
    using CopyBudget=FrameHudOperation::CopyBudget;
    FrameActiveOperation(DosGetTimeRegisters r,uint16_t dosBase,uint16_t keyboardBase,
                         uint16_t psp,uint16_t game,uint32_t idToggle)
        :state_{FrameForegroundOperation(r,dosBase,keyboardBase,psp,game,idToggle).snapshot()} {}
    explicit FrameActiveOperation(FrameActiveSnapshot state):state_(state) {
        if(state_.renderTimer && !state_.render)
            throw std::invalid_argument("Active-frame timer has no suspended renderer");
    }
    const FrameActiveSnapshot& snapshot() const noexcept {return state_;}
    bool finished() const {
        if(state_.renderTimer) return false;
        return state_.render?FrameRenderOperation(*state_.render).finished():
            FrameForegroundOperation(state_.foreground).finished();
    }
    bool returned() const {
        return !state_.renderTimer && state_.render && FrameRenderOperation(*state_.render).returned();
    }
    bool interruptInProgress() const {
        return state_.render?state_.renderTimer.has_value():
            FrameForegroundOperation(state_.foreground).interruptInProgress();
    }
    DosGetTimeRegisters registers() const {
        if(state_.renderTimer) return fromTimer(state_.renderTimer->registers);
        return state_.render?state_.render->registers:FrameForegroundOperation(state_.foreground).registers();
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if(finished() || interruptInProgress() || !(registers().flags&0x200u))
            throw std::logic_error("Active-frame timer is not eligible");
        if(!state_.render) {
            FrameForegroundOperation foreground(state_.foreground);
            foreground.deliverTimerInterrupt(bus);state_.foreground=foreground.snapshot();
        } else {
            auto r=state_.render->registers;
            const auto push=[&](uint16_t value) {r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value);};
            push(static_cast<uint16_t>(r.flags));push(r.cs);push(r.ip);
            r.flags&=~uint32_t{0x300};r.cs=0xf000;r.ip=0xfea5;
            state_.renderTimer=TimerIrqOperation(toTimer(r),state_.foreground.pacing.gameSegment,
                state_.foreground.pacing.idToggleMask).snapshot();
        }
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while(used<budget && !finished()) {
            if(state_.renderTimer) {
                TimerIrqOperation timer(*state_.renderTimer);
                if(timer.advance(1,bus)!=1) throw std::domain_error("Active-frame IRQ did not dispatch");
                ++state_.timerInstructions;
                if(timer.returned()) {
                    const auto r=fromTimer(timer.snapshot().registers);
                    state_.render->registers=r;
                    std::visit([&](auto& child) {
                        using Child=std::remove_cvref_t<decltype(child)>;
                        if constexpr(!std::is_same_v<Child,std::monostate>) child.registers=r;
                    },state_.render->callee);
                    state_.renderTimer.reset();
                } else state_.renderTimer=timer.snapshot();
            } else if(state_.render) {
                FrameRenderOperation render(*state_.render);
                if(render.advance(1,bus,copies)!=1) throw std::domain_error("Active-frame render did not dispatch");
                state_.render=render.snapshot();
            } else {
                FrameForegroundOperation foreground(state_.foreground);
                const bool timer=foreground.interruptInProgress();
                if(foreground.advance(1,bus,copies)!=1) throw std::domain_error("Active-frame foreground did not dispatch");
                if(timer) ++state_.timerInstructions;
                state_.foreground=foreground.snapshot();
                if(foreground.returned()) {
                    const auto r=foreground.registers();
                    if(r.cs!=state_.foreground.pacing.gameSegment || r.ip!=0x7a13)
                        throw std::domain_error("Active-frame render handoff differs");
                    state_.render=FrameRenderOperation(r,state_.foreground.pacing.gameSegment).snapshot();
                }
            }
            ++used;++state_.dispatchedInstructions;
        }
        return used;
    }
private:
    static TimerIrqRegisters toTimer(const DosGetTimeRegisters& r) {
        return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};
    }
    static DosGetTimeRegisters fromTimer(const TimerIrqRegisters& r) {
        return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};
    }
    FrameActiveSnapshot state_;
};

} // namespace lezac::core
