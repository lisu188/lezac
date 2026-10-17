#pragma once

#include "core/crt_delay.hpp"
#include "core/frame_pacing_calculation.hpp"

#include <bit>
#include <optional>
#include <utility>

namespace lezac::core {

enum class FramePacingStage { Gate, Calculation, FeedbackDelay, Returned, RuntimeError };
struct FramePacingSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment = 0, callbackBase = 0, pspSegment = 0;
    uint32_t idToggleMask = 0;
    FramePacingStage stage = FramePacingStage::Gate;
    std::optional<FramePacingCalculationSnapshot> calculation = std::nullopt;
    std::optional<CrtDelaySnapshot> delay = std::nullopt;
    std::optional<TimerIrqSnapshot> timer = std::nullopt;
    uint64_t dispatchedInstructions = 0, gateInstructions = 0, feedbackInstructions = 0;
    uint64_t timerInstructions = 0, timerDeliveries = 0;
    bool operator==(const FramePacingSnapshot&) const = default;
};

// Original game:7903..79E8, including its DOS, Real48, feedback and CRT.Delay calls.
// The caller owns PIC eligibility and every external device callback.
class FramePacingOperation {
public:
    FramePacingOperation(DosGetTimeRegisters r, uint16_t callbackBase, uint16_t psp, uint16_t game, uint32_t idToggle)
        : state_{r, game, callbackBase, psp, idToggle} {
        if (r.cs != game || r.ip != 0x7903 || r.ds != static_cast<uint16_t>(game + 0xaa2) ||
            callbackBase > 0xfff0 || (idToggle != 0 && idToggle != 0x200000))
            throw std::invalid_argument("Frame pacing entry differs from the recovered profile");
    }
    explicit FramePacingOperation(FramePacingSnapshot state) : state_(state) {}
    const FramePacingSnapshot& snapshot() const noexcept { return state_; }
    bool finished() const noexcept {
        return !state_.timer && (state_.stage == FramePacingStage::Returned || state_.stage == FramePacingStage::RuntimeError);
    }
    bool returned() const noexcept { return finished() && state_.stage == FramePacingStage::Returned; }
    bool interruptInProgress() const {
        return state_.timer || (state_.stage == FramePacingStage::Calculation &&
            FramePacingCalculationOperation(*state_.calculation).interruptInProgress());
    }
    DosGetTimeRegisters registers() const {
        if (state_.timer) return fromTimer(state_.timer->registers);
        if (state_.stage == FramePacingStage::Calculation)
            return FramePacingCalculationOperation(*state_.calculation).registers();
        return state_.registers;
    }
    void deliverTimerInterrupt(const TimerIrqBus& bus) {
        if (state_.stage == FramePacingStage::Calculation) {
            FramePacingCalculationOperation operation(*state_.calculation);
            operation.deliverTimerInterrupt(bus);
            state_.calculation = operation.snapshot();
            return;
        }
        if (state_.timer || !(state_.registers.flags & 0x200u))
            throw std::logic_error("Frame pacing timer is not eligible");
        auto r = state_.registers;
        push(r, bus, static_cast<uint16_t>(r.flags)); push(r, bus, r.cs); push(r, bus, r.ip);
        r.flags &= ~uint32_t{0x300}; r.cs = 0xf000; r.ip = 0xfea5;
        state_.timer = TimerIrqOperation(toTimer(r), state_.gameSegment, state_.idToggleMask).snapshot();
        ++state_.timerDeliveries;
    }
    uint64_t advance(uint64_t budget, const TimerIrqBus& bus) {
        uint64_t consumed = 0;
        while (consumed < budget && !finished()) {
            if (state_.timer) {
                TimerIrqOperation operation(*state_.timer);
                if (operation.advance(1, bus) != 1) throw std::domain_error("Pacing timer did not dispatch");
                ++state_.timerInstructions;
                if (operation.returned()) {
                    state_.registers = fromTimer(operation.snapshot().registers);
                    if (state_.delay && !state_.delay->returned)
                        state_.delay->registers = toDelay(state_.registers);
                    state_.timer.reset();
                } else state_.timer = operation.snapshot();
            } else if (state_.stage == FramePacingStage::Calculation) {
                FramePacingCalculationOperation operation(*state_.calculation);
                if (operation.advance(1, bus) != 1) throw std::domain_error("Pacing calculation did not dispatch");
                state_.calculation = operation.snapshot();
                if (operation.finished()) {
                    state_.registers = operation.registers();
                    state_.stage = operation.returned() ? FramePacingStage::FeedbackDelay : FramePacingStage::RuntimeError;
                }
            } else if (state_.delay && !state_.delay->returned) {
                CrtDelayOperation operation(*state_.delay);
                if (operation.advance(1, {bus.readByte, bus.readWord, bus.writeWord}) != 1)
                    throw std::domain_error("Pacing CRT delay did not dispatch");
                state_.delay = operation.snapshot();
                // The generic CRT operation leaves logical AF unspecified; this host materializes it as zero.
                if (!(state_.delay->definedFlags & 0x10u)) state_.delay->registers.flags &= ~uint32_t{0x10};
                state_.registers = fromDelay(state_.delay->registers, state_.registers.si);
                if (operation.returned()) {
                    if (state_.registers.cs != state_.gameSegment || state_.registers.ip != 0x79e8)
                        throw std::domain_error("Pacing CRT delay returned outside the recovered fragment");
                    state_.stage = FramePacingStage::Returned;
                }
            } else if (state_.stage == FramePacingStage::Gate) {
                gate(bus);
                ++state_.gateInstructions;
            } else if (state_.stage == FramePacingStage::FeedbackDelay) {
                feedback(bus);
                ++state_.feedbackInstructions;
            } else throw std::domain_error("Frame pacing reached an unrecovered stage");
            ++state_.dispatchedInstructions; ++consumed;
        }
        return consumed;
    }

private:
    static constexpr uint32_t Arithmetic = 0x8d5;
    static void push(DosGetTimeRegisters& r, const TimerIrqBus& bus, uint16_t value) {
        r.sp = static_cast<uint16_t>(r.sp - 2u); bus.writeWord(r.ss, r.sp, value);
    }
    static uint32_t valueFlags(uint16_t value) {
        return (value == 0 ? 0x40u : 0u) | ((value & 0x8000) ? 0x80u : 0u) |
            (std::popcount(static_cast<uint8_t>(value)) % 2 == 0 ? 4u : 0u);
    }
    uint16_t logic(uint16_t value) {
        state_.registers.flags = (state_.registers.flags & ~Arithmetic) | valueFlags(value);
        return value;
    }
    uint16_t arithmetic(uint16_t left, uint16_t right, bool subtract) {
        const uint32_t wide = subtract ? uint32_t{left} - right : uint32_t{left} + right;
        const auto value = static_cast<uint16_t>(wide);
        uint32_t flags = valueFlags(value) | (((left ^ right ^ value) & 0x10) ? 0x10u : 0u);
        if (subtract ? left < right : wide > 65535) flags |= 1;
        if (subtract ? ((left ^ right) & (left ^ value) & 0x8000) : (~(left ^ right) & (left ^ value) & 0x8000)) flags |= 0x800;
        state_.registers.flags = (state_.registers.flags & ~Arithmetic) | flags;
        return value;
    }
    void gate(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        if (r.cs == 0xf000 && r.ip == state_.callbackBase) {
            r.flags |= 0x200; ++r.ip;
            state_.calculation = FramePacingCalculationOperation(r, state_.callbackBase, state_.pspSegment,
                state_.gameSegment, state_.idToggleMask).snapshot();
            state_.stage = FramePacingStage::Calculation;
            return;
        }
        if (r.cs != state_.gameSegment) throw std::domain_error("Pacing gate left recovered code");
        switch (r.ip) {
        case 0x7903: {
            const auto carry = r.flags & 1u;
            bus.writeWord(r.ds, 0x78c2, arithmetic(bus.readWord(r.ds, 0x78c2), 1, false));
            r.flags = (r.flags & ~uint32_t{1}) | carry; r.ip = 0x7907; break;
        }
        case 0x7907: r.ax = bus.readWord(r.ds, 0x78c2); r.ip = 0x790a; break;
        case 0x790a: r.dx = logic(0); r.ip = 0x790c; break;
        case 0x790c: r.cx = 30; r.ip = 0x790f; break;
        case 0x790f: {
            const uint32_t value = (uint32_t{r.dx} << 16) | r.ax;
            if (!r.cx || value / r.cx > 65535) throw std::domain_error("Pacing DIV left recovered operand domain");
            r.ax = static_cast<uint16_t>(value / r.cx); r.dx = static_cast<uint16_t>(value % r.cx);
            // Pinned DIVW leaves the preceding lazy arithmetic flags intact.
            r.ip = 0x7911; break;
        }
        case 0x7911: std::swap(r.ax, r.dx); r.ip = 0x7912; break;
        case 0x7912: logic(r.ax); r.ip = 0x7914; break;
        case 0x7914: r.ip = (r.flags & 0x40u) ? 0x7919 : 0x7916; break;
        case 0x7916: r.ip = 0x79df; state_.stage = FramePacingStage::FeedbackDelay; break;
        case 0x7919: r.ax = 0x2c00; r.ip = 0x791c; break;
        case 0x791c:
            if (bus.readWord(0, 0x84) != state_.callbackBase || bus.readWord(0, 0x86) != 0xf000)
                throw std::domain_error("Pacing INT21 vector differs from the pinned callback");
            push(r, bus, static_cast<uint16_t>(r.flags)); push(r, bus, r.cs); push(r, bus, 0x791e);
            r.flags &= ~uint32_t{0x300}; r.cs = 0xf000; r.ip = state_.callbackBase; break;
        default: throw std::domain_error("Pacing gate reached an unrecovered instruction");
        }
    }
    void feedback(const TimerIrqBus& bus) {
        auto& r = state_.registers;
        if (r.cs != state_.gameSegment) throw std::domain_error("Pacing feedback left recovered code");
        const auto sample = [&](uint16_t offset) { r.ax = static_cast<uint16_t>((r.ax & 0xff00) | bus.readByte(r.ds, offset)); };
        switch (r.ip) {
        case 0x799a: arithmetic(bus.readWord(r.ds, 0x2074), 125, true); r.ip = 0x799f; break;
        case 0x799f: r.ip = (r.flags & 0x41u) ? 0x79bf : 0x79a1; break;
        case 0x79a1: arithmetic(bus.readWord(r.ds, 0x78cc), 0, true); r.ip = 0x79a6; break;
        case 0x79a6: r.ip = (r.flags & 0x41u) ? 0x79bf : 0x79a8; break;
        case 0x79a8: r.ax = bus.readWord(r.ds, 0x78cc); r.ip = 0x79ab; break;
        case 0x79ab: arithmetic(r.ax, bus.readWord(r.ds, 0x78ca), true); r.ip = 0x79af; break;
        case 0x79af: r.ip = (r.flags & 0x41u) ? 0x79ba : 0x79b1; break;
        case 0x79b1: r.ax = bus.readWord(r.ds, 0x78ca); r.ip = 0x79b4; break;
        case 0x79b4: bus.writeWord(r.ds, 0x78cc, arithmetic(bus.readWord(r.ds, 0x78cc), r.ax, true)); r.ip = 0x79b8; break;
        case 0x79b8: r.ip = 0x79bf; break;
        case 0x79ba: r.ax = logic(0); r.ip = 0x79bc; break;
        case 0x79bc: bus.writeWord(r.ds, 0x78cc, r.ax); r.ip = 0x79bf; break;
        case 0x79bf: arithmetic(bus.readWord(r.ds, 0x2074), 120, true); r.ip = 0x79c4; break;
        case 0x79c4: r.ip = !(r.flags & 1u) ? 0x79cd : 0x79c6; break;
        case 0x79c6: r.ax = bus.readWord(r.ds, 0x78ca); r.ip = 0x79c9; break;
        case 0x79c9: bus.writeWord(r.ds, 0x78cc, arithmetic(bus.readWord(r.ds, 0x78cc), r.ax, false)); r.ip = 0x79cd; break;
        case 0x79cd: sample(0x79ab); r.ip = 0x79d0; break;
        case 0x79d0: bus.writeByte(r.ds, 0x79a8, static_cast<uint8_t>(r.ax)); r.ip = 0x79d3; break;
        case 0x79d3: sample(0x79ac); r.ip = 0x79d6; break;
        case 0x79d6: bus.writeByte(r.ds, 0x79a9, static_cast<uint8_t>(r.ax)); r.ip = 0x79d9; break;
        case 0x79d9: sample(0x79aa); r.ip = 0x79dc; break;
        case 0x79dc: bus.writeByte(r.ds, 0x79a4, static_cast<uint8_t>(r.ax)); r.ip = 0x79df; break;
        case 0x79df: push(r, bus, bus.readWord(r.ds, 0x78cc)); r.ip = 0x79e3; break;
        case 0x79e3:
            push(r, bus, r.cs); push(r, bus, 0x79e8);
            r.cs = static_cast<uint16_t>(state_.gameSegment + 0x84a); r.ip = 0x029c;
            state_.delay = CrtDelayOperation(toDelay(r)).snapshot(); break;
        default: throw std::domain_error("Pacing feedback reached an unrecovered instruction");
        }
    }
    static TimerIrqRegisters toTimer(const DosGetTimeRegisters& r) {
        return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};
    }
    static DosGetTimeRegisters fromTimer(const TimerIrqRegisters& r) {
        return {r.ax,r.bx,r.cx,r.dx,r.si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};
    }
    static CrtDelayRegisters toDelay(const DosGetTimeRegisters& r) {
        return {r.ax,r.bx,r.cx,r.dx,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};
    }
    static DosGetTimeRegisters fromDelay(const CrtDelayRegisters& r, uint16_t si) {
        return {r.ax,r.bx,r.cx,r.dx,si,r.di,r.bp,r.cs,r.ds,r.es,r.ss,r.sp,r.ip,r.flags};
    }
    FramePacingSnapshot state_;
};

}
