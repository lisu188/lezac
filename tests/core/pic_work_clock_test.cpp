#include "core/pic_work_clock.hpp"

#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

using namespace lezac::core;
namespace {
void require(bool value, const std::string& message) {
    if (!value) throw std::runtime_error(message);
}
PicWorkClockSnapshot input() {
    PicWorkClockSnapshot state;
    state.cycles = 500;
    state.pitDelay = 1000.0f / (1193182.0f / 65536.0f);
    state.queue = {{state.pitDelay, PicClockEventKind::Pit0, 0}};
    return state;
}
void unit() {
    for (int64_t cycles = 0; cycles <= 64; ++cycles) for (bool read : {false, true}) {
        auto state = input(); state.cycles = cycles; state.ioDelayRemoved = 77;
        PicWorkClock clock(state);
        if (read) clock.chargePortRead(); else clock.chargePortWrite();
        const int64_t cost = read ? 5 : 4;
        const auto charged = cycles < 3 * cost ? 0 : cost;
        require(clock.snapshot().cycles == cycles - charged && clock.snapshot().ioDelayRemoved == 77 + charged,
                "port low-budget threshold differs");
    }
    auto state = input(); state.cycles = 1; state.cycleLeft = 100;
    PicWorkClock clock(state);
    require(clock.nextDispatch(false, 0x202).kind == PicClockBoundaryKind::Ready && clock.snapshot().cycles == 0,
            "last usable instruction budget differs");
    require(clock.nextDispatch(false, 0x202).kind == PicClockBoundaryKind::Ready &&
            clock.snapshot().cycles == 98 && clock.snapshot().cycleLeft == 0,
            "failed loop decrement or queue grant differs");
    state = input(); state.cycles = 0;
    clock = PicWorkClock(state);
    require(clock.nextDispatch(false, 0x202).kind == PicClockBoundaryKind::NeedMillisecond, "missing millisecond boundary");
    clock = PicWorkClock(clock.snapshot());
    clock.grantMillisecond();
    require(clock.nextDispatch(false, 0x202).kind == PicClockBoundaryKind::Ready &&
            clock.snapshot().ticks == 1 && clock.snapshot().cycles == 5999, "millisecond budget differs");
    state = input(); state.cycles = 0; state.cycleLeft = 100;
    state.queue = {{0.98f, PicClockEventKind::Pit0, 0}};
    clock = PicWorkClock(state);
    require(clock.nextDispatch(true, 0x202).timerDelivered && clock.snapshot().activeIrq == 0 &&
            clock.snapshot().inserviceLines == 1, "PIT pending IRQ was not delivered");
    clock.chargePortWrite(); clock.nonspecificMasterEoi();
    require(clock.snapshot().activeIrq == 0xff && clock.snapshot().inserviceLines == 0, "EOI did not retire timer");
    state.maskedLines = 1; clock = PicWorkClock(state);
    require(!clock.nextDispatch(true, 0x202).timerDelivered && clock.snapshot().activeLines == 1 &&
            clock.snapshot().pending == 0, "masked PIT activation differs");
    state.maskedLines = 0; state.queue = {{0.98f, PicClockEventKind::Foreign, 100}};
    clock = PicWorkClock(state);
    require(clock.nextDispatch(true, 0x202).kind == PicClockBoundaryKind::ForeignEvent && clock.snapshot().queue.size() == 1,
            "unknown device callback silently removed");
    state = input(); state.cycles = 0; state.cycleLeft = 100;
    state.pending = state.activeLines = 3;
    clock = PicWorkClock(state);
    require(clock.nextDispatch(true, 0x202).timerDelivered && clock.snapshot().pending == 2,
            "lower-priority pending keyboard displaced timer");
    state.pending = state.activeLines = 2; state.activeIrq = 0; state.inserviceLines = 1;
    clock = PicWorkClock(state);
    require(clock.nextDispatch(true, 0x202).kind == PicClockBoundaryKind::Ready && clock.snapshot().pending == 2,
            "lower-priority IRQ preempted in-service timer");
    state.activeIrq = 0xff; state.inserviceLines = 0;
    clock = PicWorkClock(state);
    require(clock.nextDispatch(true, 0x202).kind == PicClockBoundaryKind::OtherIrq, "eligible keyboard was ignored");
    const auto suspended = clock.snapshot();
    require(clock.nextDispatch(false, 0x202).kind == PicClockBoundaryKind::OtherIrq && clock.snapshot() == suspended,
            "unsupported IRQ boundary did not remain suspended");
    state = input(); clock = PicWorkClock(state);
    bool rejected = false;
    try { clock.nextDispatch(false, 0x302); } catch (const std::domain_error&) { rejected = true; }
    require(rejected && clock.snapshot() == state, "trap decoder changed the normal-core profile");
    for (unsigned invalid = 0; invalid < 8; ++invalid) {
        state = input();
        switch (invalid) {
        case 0: state.cycles = std::numeric_limits<int64_t>::min(); break;
        case 1: state.cycleLeft = std::numeric_limits<int64_t>::min(); break;
        case 2: state.cycleLeft = state.cycles = 6000; break;
        case 3: state.phase = static_cast<PicClockPhase>(4); break;
        case 4: state.queue[0].index = -1e20f; break;
        case 5: state.queue[0].index = -2; break;
        case 6: state.queue[0].index = 2048; break;
        case 7: state.pitDelay = 1; break;
        }
        rejected = false;
        try { PicWorkClock invalidClock(state); } catch (const std::invalid_argument&) { rejected = true; }
        require(rejected, "out-of-profile snapshot was accepted");
    }
    std::cout << "pic_work_clock_unit=ok io_threshold_cases=130 postdecrement=1 pit_pending=1 eoi=1 foreign_callbacks_explicit=1\n";
}
}
int main() {
    try { unit(); }
    catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
