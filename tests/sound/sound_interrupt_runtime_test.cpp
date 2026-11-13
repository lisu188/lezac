#include "resources/sound.hpp"
#include "sound/sound_engine.hpp"
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>

using namespace lezac::sound;
namespace {
void require(bool value,const char* message){if(!value)throw std::runtime_error(message);}
void compare(const lezac::resources::SoundBank& bank,uint16_t cursor,SoundInterruptState state,bool active=true){
    SoundEngine reference(bank),runtime(bank);
    const SoundLatch initial{active,5,cursor,1,false};
    reference.restoreLatchForFixture(initial);runtime.restoreLatchForFixture(initial);
    reference.restoreInterruptForFixture(state);runtime.restoreInterruptForFixture(state);
    const auto expected=reference.advanceSoundInterrupt(),actual=runtime.advanceSoundInterruptWorkOrdered();
    require(actual.frequency==expected.frequency && actual.programTone==expected.programTone && actual.silence==expected.silence,
            "runtime action differs from recovered transition");
    const auto a=runtime.latch(),b=reference.latch();
    require(a.active==b.active && a.currentSelector==b.currentSelector && a.latchedOffset==b.latchedOffset &&
            a.recordIndex==b.recordIndex && a.directSweep==b.directSweep,"runtime canonical latch differs");
    const auto x=runtime.interruptState(),y=reference.interruptState();
    require(x.accumulator==y.accumulator && x.gateTick==y.gateTick && x.periodTicks==y.periodTicks,"runtime byte counters differ");
    const auto work=runtime.interruptWorkState();
    require(work.callbacks==1 && work.dispatchedInstructions>=24 && work.dispatchedInstructions<128,"runtime work not accounted");
    if(!active)require(work.dispatchedInstructions==24 && work.portReads==0 && work.portWrites==0,"idle work differs");
}
}
int main(int argc,char** argv){try{
    require(argc==2,"expected sound bank path");const auto bank=lezac::resources::loadRawSon(argv[1]);
    std::size_t cases=0;
    for(unsigned cursor=0;cursor<130;++cursor)
        for(uint8_t acc:{uint8_t{0},uint8_t{1},uint8_t{254},uint8_t{255}})
            for(uint8_t gate:{uint8_t{0},uint8_t{1},uint8_t{2},uint8_t{255}})
                for(uint8_t period:{uint8_t{0},uint8_t{1},uint8_t{2},uint8_t{255}}){
                    compare(bank,static_cast<uint16_t>(cursor),{acc,gate,period});++cases;
                }
    for(unsigned cursor=0xea61;cursor<65536;++cursor){compare(bank,static_cast<uint16_t>(cursor),{255,0,0});++cases;}
    for(unsigned cursor:{0u,129u,65535u}){compare(bank,static_cast<uint16_t>(cursor),{255,17,0},false);++cases;}
    for(unsigned cursor:{130u,10923u,60000u}){
        SoundEngine reference(bank),runtime(bank);
        reference.restoreLatchForFixture({true,5,static_cast<uint16_t>(cursor),1,false});
        runtime.restoreLatchForFixture(reference.latch());
        bool oldRejected=false,newRejected=false;
        try{reference.advanceSoundInterrupt();}catch(const std::runtime_error&){oldRejected=true;}
        try{runtime.advanceSoundInterruptWorkOrdered();}catch(const std::runtime_error&){newRejected=true;}
        require(oldRejected && newRejected && reference.latch().latchedOffset==runtime.latch().latchedOffset &&
                reference.interruptState().accumulator==runtime.interruptState().accumulator,
                "unsupported bank failure boundary differs");
    }
    SoundEngine idle(bank);
    idle.skipClockedSamples(kAudioSampleRate);
    require(idle.interruptWorkState().callbacks==idle.clockState().interrupts &&
            idle.interruptWorkState().dispatchedInstructions==idle.clockState().interrupts*24,"analytical idle work differs");
    SoundEngine live(bank);
    live.restoreLatchForFixture({true,5,0xea61,1,true});
    live.skipClockedSamples(kAudioSampleRate);
    require(!live.latch().active && live.interruptWorkState().callbacks==live.clockState().interrupts &&
            live.interruptWorkState().dispatchedInstructions>live.clockState().interrupts*24,"live clock did not use runtime IRQ");
    std::cout<<"sound_interrupt_runtime=ok cases="<<cases<<" canonical_owner=1 live_route=1 idle_work=24 host_schedule_unchanged=1\n";
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
