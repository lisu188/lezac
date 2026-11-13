#pragma once

#include "core/dos_time.hpp"
#include "core/timer_irq.hpp"

#include <optional>

namespace lezac::core {

struct InterruptibleDosTimeSnapshot {
    DosGetTimeSnapshot dos;
    std::optional<TimerIrqSnapshot> timer;
    uint16_t gameSegment = 0;
    uint64_t dispatchedInstructions = 0, timerInstructions = 0, timerDeliveries = 0;
    bool operator==(const InterruptibleDosTimeSnapshot&) const = default;
};

// DOS and IRQ0 use one caller-owned memory bus, including BIOS 0040:006C.
// Entry flags are materialized CPU state. The caller owns PIC timing and IRQ eligibility.
class InterruptibleDosTimeOperation {
public:
    InterruptibleDosTimeOperation(DosGetTimeRegisters registers, uint16_t callbackBase,
                                 uint16_t pspSegment, uint16_t gameSegment, uint32_t idToggleMask)
        : state_{DosGetTimeOperation(registers, callbackBase, pspSegment, idToggleMask).snapshot(),
                 std::nullopt, gameSegment} {}
    explicit InterruptibleDosTimeOperation(InterruptibleDosTimeSnapshot snapshot) : state_(snapshot) {}

    const InterruptibleDosTimeSnapshot& snapshot() const noexcept { return state_; }
    bool interruptInProgress() const noexcept { return state_.timer.has_value(); }
    bool returned() const noexcept { return !state_.timer && state_.dos.returned; }
    DosGetTimeRegisters registers() const {
        return state_.timer ? fromTimer(state_.timer->registers) : state_.dos.registers;
    }

    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (returned() || state_.timer || !(state_.dos.registers.flags & 0x200u))
            throw std::logic_error("DOS timer interrupt is not eligible at this boundary");
        auto registers = toTimer(state_.dos.registers);
        const auto push = [&](uint16_t word) {
            const auto next = static_cast<uint16_t>(registers.sp - 2u);
            bus.writeWord(registers.ss, next, word);
            registers.sp = next;
        };
        push(static_cast<uint16_t>(registers.flags));
        push(registers.cs);
        push(registers.ip);
        registers.flags &= ~uint32_t{0x300};
        registers.ip = 0xfea5;
        registers.cs = 0xf000;
        state_.timer = TimerIrqOperation(registers, state_.gameSegment, state_.dos.idToggleMask).snapshot();
        ++state_.timerDeliveries;
    }

    uint64_t advance(uint64_t budget, const TimerIrqBus& bus) {
        const DosGetTimeBus dosBus{
            [&] { return bus.readDword(0x40, 0x6c); }, bus.readWord, bus.writeWord, bus.writeDword};
        uint64_t consumed = 0;
        while (consumed < budget && !returned()) {
            if (state_.timer) {
                TimerIrqOperation operation(*state_.timer);
                operation.advance(1, bus);
                ++state_.timerInstructions;
                if (operation.returned()) {
                    state_.dos.registers = fromTimer(operation.snapshot().registers);
                    state_.timer.reset();
                } else {
                    state_.timer = operation.snapshot();
                }
            } else {
                DosGetTimeOperation operation(state_.dos);
                operation.advance(1, dosBus);
                state_.dos = operation.snapshot();
            }
            ++state_.dispatchedInstructions;
            ++consumed;
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
    InterruptibleDosTimeSnapshot state_;
};

}
