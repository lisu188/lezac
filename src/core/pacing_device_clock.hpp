#pragma once

#include "core/pic_work_clock.hpp"

#include <array>
#include <bit>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace lezac::core {

struct PacingDeviceClockSnapshot {
    PicWorkClockSnapshot clock;
    std::array<uint64_t, 25> devices{};
    std::array<uint64_t, 6> delayBits{};
    std::vector<uint8_t> tickers;
    uint64_t deviceCallbacks = 0, tickerCallbacks = 0;
    bool operator==(const PacingDeviceClockSnapshot&) const = default;
};

// Timing-relevant VGA PART callbacks and idle keyboard/silent-mixer tickers.
// Rendering pixels and other device/IRQ profiles are not implemented here.
class PacingDeviceClock {
public:
    explicit PacingDeviceClock(PacingDeviceClockSnapshot state)
        : clock_(state.clock), state_(std::move(state)) {
        const auto& d = state_.devices;
        if (d[0] != 5 || d[1] != 3 || d[2] != 0 || d[4] != 4 || d[5] != 50 || d[7] != 200 ||
            d[3] > d[4] || d[6] > d[7] || d[8] || d[9] > 1 || d[10] > 255 || d[11] != 1 || d[12] > 1 ||
            d[13] || d[14] || d[15] || d[16] || d[17] || d[18] || d[19] || d[20] || d[21] != 1 || d[22] || d[23] || d[24] ||
            state_.tickers != std::vector<uint8_t>{11,10})
            throw std::invalid_argument("Pacing device clock differs from the observed VGA/idle/silent profile");
        for (auto bits : state_.delayBits) {
            const double delay = std::bit_cast<double>(bits);
            if (!std::isfinite(delay) || delay <= 0 || delay > 1024)
                throw std::invalid_argument("VGA delay is outside the recovered bounds");
        }
        for (const auto& event : state_.clock.queue)
            if (static_cast<unsigned>(event.kind) < 1 || event.kind == PicClockEventKind::Foreign || static_cast<unsigned>(event.kind) > 7)
                throw std::invalid_argument("Pacing device callback identity is unknown");
    }
    PacingDeviceClockSnapshot snapshot() const {
        auto result = state_; result.clock = clock_.snapshot(); return result;
    }
    PicWorkClock& workClock() noexcept { return clock_; }
    const PicWorkClock& workClock() const noexcept { return clock_; }

    PicClockBoundary nextDispatch(bool coreReturned, uint32_t flags) {
        auto boundary = clock_.nextDispatch(coreReturned, flags);
        while (boundary.kind == PicClockBoundaryKind::ForeignEvent) {
            const auto event = clock_.consumeDeviceEvent();
            callback(event);
            ++state_.deviceCallbacks;
            boundary = clock_.nextDispatch(false, flags);
        }
        return boundary;
    }
    void grantMillisecond() {
        clock_.grantMillisecond();
        // Both observed tickers have no queue/IRQ effect in this validated idle/silent profile.
        state_.tickerCallbacks += state_.tickers.size();
    }

private:
    double delay(unsigned index) const { return std::bit_cast<double>(state_.delayBits[index]); }
    void schedule(const PicClockEvent& source, PicClockEventKind kind, float delta, uint64_t value = 0) {
        clock_.scheduleDeviceEvent({source.index + delta, kind, value});
    }
    void callback(const PicClockEvent& event) {
        auto& d = state_.devices;
        switch (event.kind) {
        case PicClockEventKind::VgaDrawPart:
            if (!d[3] || event.value > 200 || d[6] + event.value > d[7])
                throw std::domain_error("VGA draw part left the recovered line domain");
            d[6] += event.value;
            if (--d[3]) schedule(event, event.kind, static_cast<float>(delay(0)), d[3] != 1 ? d[5] : d[7] - d[6]);
            else d[12] = 0;
            break;
        case PicClockEventKind::VgaVertical:
            schedule(event, event.kind, static_cast<float>(delay(1)));
            schedule(event, PicClockEventKind::VgaDisplayLatch, static_cast<float>(delay(2)));
            schedule(event, PicClockEventKind::VgaPanningLatch, static_cast<float>(delay(3)));
            schedule(event, PicClockEventKind::VgaVerticalInterrupt, static_cast<float>(delay(4) + 0.005));
            if (d[12]) break;
            d[13] = 0; d[12] = 1;
            if (d[3]) {
                clock_.removeDeviceEvents(PicClockEventKind::VgaDrawPart);
                d[12] = 0;
            }
            d[6] = 0; d[3] = d[4];
            schedule(event, PicClockEventKind::VgaDrawPart, static_cast<float>(delay(0)), d[5]);
            break;
        case PicClockEventKind::VgaVerticalInterrupt:
            if (!d[9] && (d[10] & 0x30) == 0x10) d[9] = 1;
            break;
        case PicClockEventKind::VgaDisplayLatch:
        case PicClockEventKind::VgaPanningLatch:
            break;
        default: throw std::domain_error("Unrecovered pacing device callback");
        }
    }
    PicWorkClock clock_;
    PacingDeviceClockSnapshot state_;
};

}
