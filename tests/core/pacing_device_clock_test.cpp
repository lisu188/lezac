#include "core/pacing_device_clock.hpp"

#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

using namespace lezac::core;
namespace {
void require(bool value, const std::string& message) {
    if (!value) throw std::runtime_error(message);
}
PacingDeviceClockSnapshot input(PicClockEventKind event = PicClockEventKind::VgaVertical) {
    PacingDeviceClockSnapshot state;
    state.clock.cycleLeft = 100;
    state.clock.pitDelay = 1000.0f / (1193182.0f / 65536.0f);
    state.clock.queue = {{0.98f,event,0},{state.clock.pitDelay,PicClockEventKind::Pit0,0}};
    state.devices = {5,3,0,0,4,50,200,200,0,0x0,0x8e,1,0,0,0,0,0,0,0,0,0,1,0,0,0};
    state.tickers = {11,10};
    const std::array<double,6> delays{2.5,14,12,13,12.5,0.05};
    for (unsigned i=0;i<delays.size();++i) state.delayBits[i]=std::bit_cast<uint64_t>(delays[i]);
    return state;
}
void unit() {
    PacingDeviceClock vertical(input());
    require(vertical.nextDispatch(true,0x202).kind==PicClockBoundaryKind::Ready,"vertical did not return to CPU");
    auto after=vertical.snapshot();
    require(after.deviceCallbacks==1 && after.devices[3]==4 && after.devices[6]==0 && after.devices[12]==1,
        "vertical draw startup differs");
    require(after.clock.queue.size()==6 && after.clock.queue[0].kind==PicClockEventKind::VgaDrawPart &&
        after.clock.queue[0].value==50,"vertical event scheduling differs");
    PacingDeviceClock restored(after);
    require(restored.snapshot()==after,"device snapshot restore differs");
    auto state=input(PicClockEventKind::VgaDrawPart);
    state.clock.queue[0].value=50;state.devices[3]=1;state.devices[6]=150;state.devices[12]=1;
    PacingDeviceClock lastPart(state);
    lastPart.nextDispatch(true,0x202);after=lastPart.snapshot();
    require(after.devices[3]==0 && after.devices[6]==200 && after.devices[12]==0 && after.clock.queue.size()==1,
        "last draw part did not end update");
    state=input(PicClockEventKind::VgaVerticalInterrupt);state.devices[10]=0x10;
    PacingDeviceClock retrace(state);retrace.nextDispatch(true,0x202);after=retrace.snapshot();
    require(after.devices[9]==1 && after.clock.activeLines==0,"VGA retrace flag or EGA-only IRQ differs");
    for(auto kind:{PicClockEventKind::VgaDisplayLatch,PicClockEventKind::VgaPanningLatch}) {
        state=input(kind);PacingDeviceClock latch(state);latch.nextDispatch(true,0x202);
        require(latch.snapshot().devices==state.devices,"display/panning latch changed clock-relevant state");
    }
    state=input();state.clock.cycles=0;state.clock.cycleLeft=0;state.clock.queue={{50,PicClockEventKind::Pit0,0}};
    PacingDeviceClock tick(state);
    require(tick.nextDispatch(false,0x202).kind==PicClockBoundaryKind::NeedMillisecond,"ticker was not due");
    tick.grantMillisecond();
    require(tick.snapshot().tickerCallbacks==2 && tick.workClock().snapshot().ticks==1,"idle/silent ticker accounting differs");
    for(unsigned invalid=0;invalid<12;++invalid) {
        state=input();
        switch(invalid) {
        case 0:state.devices[0]=4;break;
        case 1:state.devices[1]=9;break;
        case 2:state.devices[2]=1;break;
        case 3:state.devices[17]=1;break;
        case 4:state.devices[22]=1;break;
        case 5:state.devices[23]=1;break;
        case 6:state.devices[14]=1;break;
        case 7:state.devices[15]=1;break;
        case 8:state.devices[16]=1;break;
        case 9:state.tickers={11,2};break;
        case 10:state.clock.queue[0].kind=PicClockEventKind::Foreign;break;
        case 11:state.delayBits[0]=std::bit_cast<uint64_t>(std::numeric_limits<double>::quiet_NaN());break;
        }
        bool rejected=false;
        try {PacingDeviceClock invalidClock(state);} catch(const std::invalid_argument&) {rejected=true;}
        require(rejected,"unrecovered device profile was accepted");
    }
    std::cout<<"pacing_device_clock_unit=ok callback_kinds=5 profile_rejections=12 snapshot_restore=1 idle_silent_tickers=2\n";
}
}
int main() {
    try {unit();}
    catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
