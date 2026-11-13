#pragma once

#include "core/crt_keyboard.hpp"

namespace lezac::core {

enum class GameKeyboardOutcome { Running, Drained, BreakOutput };
struct GameKeyboardSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment = 0, callbackBase = 0;
    uint32_t idToggleMask = 0;
    GameKeyboardOutcome outcome = GameKeyboardOutcome::Running;
    std::optional<CrtKeyboardSnapshot> crt = std::nullopt;
    std::optional<TimerIrqSnapshot> timer = std::nullopt;
    uint64_t dispatchedInstructions = 0, polls = 0, reads = 0;
    uint64_t timerInstructions = 0, timerDeliveries = 0;
    bool operator==(const GameKeyboardSnapshot&) const = default;
};

// Original game:7A00..7A13. The preceding HUD call and IRQ eligibility are caller-owned.
class GameKeyboardOperation {
public:
    GameKeyboardOperation(DosGetTimeRegisters r, uint16_t callbackBase, uint16_t game, uint32_t idToggle)
        : state_{r, game, callbackBase, idToggle} {
        if (r.cs != game || r.ds != static_cast<uint16_t>(game + 0xaa2) || r.ip != 0x7a00 ||
            callbackBase > 0xffec || (idToggle != 0 && idToggle != 0x200000))
            throw std::invalid_argument("Game keyboard entry differs from the recovered profile");
    }
    explicit GameKeyboardOperation(GameKeyboardSnapshot state) : state_(state) {}
    const GameKeyboardSnapshot& snapshot() const noexcept { return state_; }
    bool finished() const noexcept { return !state_.timer && state_.outcome != GameKeyboardOutcome::Running; }
    bool returned() const noexcept { return finished() && state_.outcome == GameKeyboardOutcome::Drained; }
    bool interruptInProgress() const noexcept { return state_.timer || (state_.crt && state_.crt->timer); }
    DosGetTimeRegisters registers() const {
        if (state_.timer) return fromTimer(state_.timer->registers);
        return state_.crt ? CrtKeyboardOperation(*state_.crt).registers() : state_.registers;
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (state_.crt) {
            CrtKeyboardOperation operation(*state_.crt);
            operation.deliverTimerInterrupt(bus);
            state_.crt = operation.snapshot();
        } else {
            if (state_.timer || !(state_.registers.flags & 0x200u))
                throw std::logic_error("Game keyboard timer is not eligible");
            auto& r = state_.registers;
            push(bus, static_cast<uint16_t>(r.flags)); push(bus, r.cs); push(bus, r.ip);
            r.flags &= ~uint32_t{0x300}; r.cs = 0xf000; r.ip = 0xfea5;
            state_.timer = TimerIrqOperation(toTimer(r), state_.gameSegment, state_.idToggleMask).snapshot();
        }
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus) {
        uint64_t consumed = 0;
        while (consumed < budget && !finished()) {
            if (state_.timer) {
                TimerIrqOperation timer(*state_.timer);
                if (timer.advance(1, bus) != 1) throw std::domain_error("Game keyboard timer did not dispatch");
                ++state_.timerInstructions;
                if (timer.returned()) {
                    state_.registers = fromTimer(timer.snapshot().registers);
                    state_.timer.reset();
                } else state_.timer = timer.snapshot();
            } else if (state_.crt) {
                CrtKeyboardOperation operation(*state_.crt);
                const bool timer = operation.interruptInProgress();
                if (operation.advance(1, bus) != 1) throw std::domain_error("Game keyboard CRT did not dispatch");
                if (timer) ++state_.timerInstructions;
                state_.crt = operation.snapshot();
                if (operation.finished()) {
                    state_.registers = operation.registers();
                    if (!operation.returned()) state_.outcome = GameKeyboardOutcome::BreakOutput;
                    state_.crt.reset();
                }
            } else instruction(bus);
            ++state_.dispatchedInstructions; ++consumed;
        }
        return consumed;
    }

private:
    void push(const TimerIrqBus& bus, uint16_t value) {
        auto& r = state_.registers;
        r.sp = static_cast<uint16_t>(r.sp - 2u); bus.writeWord(r.ss, r.sp, value);
    }
    void call(const TimerIrqBus& bus, uint16_t entry, uint16_t next) {
        auto& r = state_.registers;
        push(bus, r.cs); push(bus, next);
        r.cs = static_cast<uint16_t>(state_.gameSegment + 0x84a); r.ip = entry;
        state_.crt = CrtKeyboardOperation(r, state_.callbackBase, state_.gameSegment, state_.idToggleMask).snapshot();
    }
    void instruction(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        if (r.cs != state_.gameSegment) throw std::domain_error("Game keyboard left recovered code");
        switch (r.ip) {
        case 0x7a00: call(bus, 0x2fd, 0x7a05); ++state_.polls; break;
        case 0x7a05: {
            const auto value = static_cast<uint8_t>(r.ax);
            const uint32_t flags = (value == 0 ? 0x40u : 0u) | ((value & 0x80u) ? 0x80u : 0u) |
                (std::popcount(value) % 2 == 0 ? 4u : 0u);
            r.flags = (r.flags & ~uint32_t{0x8d5}) | flags; r.ip = 0x7a07; break;
        }
        case 0x7a07:
            r.ip = (r.flags & 0x40u) ? 0x7a13 : 0x7a09;
            if (r.ip == 0x7a13) state_.outcome = GameKeyboardOutcome::Drained;
            break;
        case 0x7a09: call(bus, 0x30f, 0x7a0e); ++state_.reads; break;
        case 0x7a0e: bus.writeByte(r.ds, 0x2058, static_cast<uint8_t>(r.ax)); r.ip = 0x7a11; break;
        case 0x7a11: r.ip = 0x7a00; break;
        default: throw std::domain_error("Game keyboard reached an unrecovered instruction");
        }
    }
    static TimerIrqRegisters toTimer(const DosGetTimeRegisters& r) {
        return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};
    }
    static DosGetTimeRegisters fromTimer(const TimerIrqRegisters& r) {
        return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};
    }
    GameKeyboardSnapshot state_;
};

}
