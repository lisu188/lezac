#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>

namespace lezac::core {

enum class PicClockEventKind : uint8_t {
    Pit0 = 1, Foreign = 2, VgaDrawPart = 3, VgaVertical = 4,
    VgaDisplayLatch = 5, VgaPanningLatch = 6, VgaVerticalInterrupt = 7
};
struct PicClockEvent {
    float index = 0;
    PicClockEventKind kind = PicClockEventKind::Foreign;
    uint64_t value = 0;
    bool operator==(const PicClockEvent&) const = default;
};
enum class PicClockPhase : uint8_t { Predecode, Queue, Millisecond, OtherIrq };
struct PicWorkClockSnapshot {
    int64_t cycles = 0, cycleLeft = 0, ioDelayRemoved = 0;
    uint64_t ticks = 0;
    int32_t cycleMax = 6000;
    uint16_t activeLines = 0, maskedLines = 0, inserviceLines = 0, pending = 0;
    uint8_t activeIrq = 0xff, irq0Vector = 8;
    bool special = false, autoEoi = false;
    float pitDelay = 0;
    double pitStart = 0;
    uint32_t pitCount = 65536;
    uint8_t pitMode = 3;
    bool pitUpdate = false;
    std::vector<PicClockEvent> queue;
    PicClockPhase phase = PicClockPhase::Predecode;
    uint64_t dispatched = 0, timerDeliveries = 0, millisecondGrants = 0;
    bool operator==(const PicWorkClockSnapshot&) const = default;
};
enum class PicClockBoundaryKind { Ready, NeedMillisecond, ForeignEvent, OtherIrq };
struct PicClockBoundary {
    PicClockBoundaryKind kind = PicClockBoundaryKind::Ready;
    bool timerDelivered = false;
};

// Functional model of the pinned normal-core/PIC work profile, not host elapsed time.
// Foreign device callbacks and millisecond ticker callbacks belong to the caller.
class PicWorkClock {
public:
    explicit PicWorkClock(PicWorkClockSnapshot state) : state_(std::move(state)) {
        if (state_.cycleMax != 6000 || state_.special || state_.autoEoi || state_.irq0Vector != 8 ||
            state_.pitCount != 65536 || state_.pitMode != 3 || state_.pitUpdate ||
            state_.pitDelay != 1000.0f / (1193182.0f / 65536.0f) || !std::isfinite(state_.pitStart) ||
            state_.queue.size() > 64 || state_.cycleLeft < -1 || state_.cycles < -1 ||
            state_.cycleLeft > state_.cycleMax || state_.cycles > state_.cycleMax ||
            state_.cycleLeft + state_.cycles > state_.cycleMax ||
            static_cast<unsigned>(state_.phase) > static_cast<unsigned>(PicClockPhase::OtherIrq) ||
            (state_.activeIrq > 15 && state_.activeIrq != 0xff))
            throw std::invalid_argument("PIC work clock differs from the recovered profile");
        for (unsigned i = 0; i < state_.queue.size(); ++i)
            if (!std::isfinite(state_.queue[i].index) || std::abs(state_.queue[i].index) > 1024 ||
                (state_.queue[i].kind == PicClockEventKind::Pit0 && state_.queue[i].index < -1) ||
                (i && state_.queue[i].index < state_.queue[i - 1].index))
                throw std::invalid_argument("PIC queue is not finite and ordered");
    }
    const PicWorkClockSnapshot& snapshot() const noexcept { return state_; }
    int64_t tickIndex() const noexcept { return state_.cycleMax - state_.cycleLeft - state_.cycles; }
    float fractionalTickIndex() const noexcept {
        return static_cast<float>(tickIndex()) / static_cast<float>(state_.cycleMax);
    }

    void chargePortRead() { chargeIo(1024); }
    void chargePortWrite() { chargeIo(1365); }
    void nonspecificMasterEoi() {
        if (state_.activeIrq >= 8) return;
        state_.inserviceLines &= static_cast<uint16_t>(~(uint16_t{1} << state_.activeIrq));
        state_.activeIrq = 0xff;
        for (uint8_t irq : priorityOrder) if (state_.inserviceLines & (uint16_t{1} << irq)) {
            state_.activeIrq = irq;
            break;
        }
    }

    // The input state is already at the observed predecode boundary. Callback and
    // PIC-check exits re-enter the queue without the failed while-loop decrement.
    PicClockBoundary nextDispatch(bool coreReturned, uint32_t flags) {
        if (flags & 0x100u) throw std::domain_error("Trap decoder is outside the normal-core clock profile");
        if (state_.phase == PicClockPhase::OtherIrq) return {PicClockBoundaryKind::OtherIrq};
        if (state_.phase == PicClockPhase::Predecode) {
            ++state_.dispatched;
            if (!coreReturned && state_.cycles-- > 0) return {};
            state_.cycleLeft += state_.cycles;
            state_.cycles = 0;
            state_.phase = PicClockPhase::Queue;
        }
        if (state_.phase == PicClockPhase::Millisecond)
            return {PicClockBoundaryKind::NeedMillisecond};
        if (state_.cycleLeft <= 0) {
            state_.phase = PicClockPhase::Millisecond;
            return {PicClockBoundaryKind::NeedMillisecond};
        }
        const int64_t now = tickIndex();
        while (!state_.queue.empty() && eventCycles(state_.queue.front()) <= static_cast<float>(now)) {
            const auto event = state_.queue.front();
            if (event.kind != PicClockEventKind::Pit0) return {PicClockBoundaryKind::ForeignEvent};
            state_.queue.erase(state_.queue.begin());
            state_.activeLines |= 1;
            if (!(state_.maskedLines & 1)) state_.pending |= 1;
            state_.pitStart += state_.pitDelay;
            const PicClockEvent next{event.index + state_.pitDelay, PicClockEventKind::Pit0, 0};
            const auto at = std::upper_bound(state_.queue.begin(), state_.queue.end(), next.index,
                [](float index, const PicClockEvent& candidate) { return index < candidate.index; });
            state_.queue.insert(at, next);
        }
        int64_t budget = state_.cycleLeft;
        if (!state_.queue.empty()) {
            const float difference = eventCycles(state_.queue.front()) - static_cast<float>(now);
            if (!std::isfinite(difference) || difference < 0 || difference > 6000000)
                throw std::domain_error("PIC event budget is outside recovered bounds");
            int64_t cycles = static_cast<int64_t>(difference);
            if (cycles == 0) cycles = 1;
            budget = std::min(budget, cycles);
        }
        state_.cycles = budget;
        state_.cycleLeft -= budget;
        if ((flags & 0x200u) && state_.pending) {
            for (uint8_t irq : priorityOrder) {
                if (irq == state_.activeIrq) break;
                const auto bit = static_cast<uint16_t>(uint16_t{1} << irq);
                if (!(state_.activeLines & bit) || (state_.maskedLines & bit) ||
                    (irq >= 8 && (state_.maskedLines & 4))) continue;
                if (irq != 0) {
                    state_.phase = PicClockPhase::OtherIrq;
                    return {PicClockBoundaryKind::OtherIrq};
                }
                state_.activeLines &= static_cast<uint16_t>(~uint16_t{1});
                state_.pending &= static_cast<uint16_t>(~uint16_t{1});
                state_.inserviceLines |= 1;
                state_.activeIrq = 0;
                ++state_.timerDeliveries;
                --state_.cycles;
                state_.phase = PicClockPhase::Predecode;
                return {PicClockBoundaryKind::Ready, true};
            }
        }
        --state_.cycles;
        state_.phase = PicClockPhase::Predecode;
        return {};
    }

    void grantMillisecond() {
        if (state_.phase != PicClockPhase::Millisecond)
            throw std::logic_error("PIC millisecond grant is not due");
        state_.cycleLeft = state_.cycleMax;
        state_.cycles = 0;
        ++state_.ticks;
        for (auto& event : state_.queue) event.index -= 1.0;
        ++state_.millisecondGrants;
        state_.phase = PicClockPhase::Queue;
    }

    PicClockEvent consumeDeviceEvent() {
        if (state_.phase != PicClockPhase::Queue || state_.queue.empty() ||
            state_.queue.front().kind == PicClockEventKind::Pit0 ||
            eventCycles(state_.queue.front()) > static_cast<float>(tickIndex()))
            throw std::logic_error("PIC device callback is not due");
        const auto event = state_.queue.front();
        state_.queue.erase(state_.queue.begin());
        return event;
    }
    void scheduleDeviceEvent(PicClockEvent event) {
        if (state_.phase != PicClockPhase::Queue || !std::isfinite(event.index) ||
            std::abs(event.index) > 1024 || static_cast<unsigned>(event.kind) < 3 ||
            static_cast<unsigned>(event.kind) > 7 || state_.queue.size() >= 64)
            throw std::logic_error("PIC device scheduling is outside the recovered profile");
        const auto at = std::upper_bound(state_.queue.begin(), state_.queue.end(), event.index,
            [](float index, const PicClockEvent& candidate) { return index < candidate.index; });
        state_.queue.insert(at, event);
    }
    void removeDeviceEvents(PicClockEventKind kind) {
        if (state_.phase != PicClockPhase::Queue || static_cast<unsigned>(kind) < 3 || static_cast<unsigned>(kind) > 7)
            throw std::logic_error("PIC device removal is outside the recovered profile");
        std::erase_if(state_.queue, [kind](const PicClockEvent& event) { return event.kind == kind; });
    }

private:
    inline static constexpr uint8_t priorityOrder[] = {0, 1, 2, 8, 9, 10, 11, 12, 13, 14, 15, 3, 4, 5, 6, 7};
    float eventCycles(const PicClockEvent& event) const {
        return event.index * static_cast<float>(state_.cycleMax);
    }
    void chargeIo(int32_t divisor) {
        if (state_.phase != PicClockPhase::Predecode)
            throw std::logic_error("PIC I/O charge is outside a decoded instruction");
        int64_t charge = state_.cycleMax / divisor;
        if (state_.cycles < 3 * charge) charge = 0;
        state_.cycles -= charge;
        state_.ioDelayRemoved += charge;
    }
    PicWorkClockSnapshot state_;
};

}
