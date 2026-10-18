#include "core/frame_active.hpp"

#include <array>
#include <iostream>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool value,const char* message) {if(!value) throw std::runtime_error(message);}
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576);
    unsigned writes=0,outputs=0;
    static uint32_t at(uint16_t s,uint16_t o) {return (uint32_t{s}*16+o)&0xfffff;}
    uint16_t word(uint16_t s,uint16_t o) const {return static_cast<uint16_t>(bytes[at(s,o)]|(uint16_t{bytes[at(s,static_cast<uint16_t>(o+1))]}<<8));}
    void store(uint16_t s,uint16_t o,uint16_t v) {bytes[at(s,o)]=static_cast<uint8_t>(v);bytes[at(s,static_cast<uint16_t>(o+1))]=static_cast<uint8_t>(v>>8);++writes;}
    TimerIrqBus bus() {
        return {
            [&](uint16_t s,uint16_t o){return bytes[at(s,o)];},
            [&](uint16_t s,uint16_t o){return word(s,o);},
            [&](uint16_t s,uint16_t o){return uint32_t{word(s,o)}|(uint32_t{word(s,static_cast<uint16_t>(o+2))}<<16);},
            [&](uint16_t s,uint16_t o,uint8_t v){bytes[at(s,o)]=v;++writes;},
            [&](uint16_t s,uint16_t o,uint16_t v){store(s,o,v);},
            [&](uint16_t s,uint16_t o,uint32_t v){store(s,o,static_cast<uint16_t>(v));store(s,static_cast<uint16_t>(o+2),static_cast<uint16_t>(v>>16));},
            [](uint16_t)->uint8_t{throw std::runtime_error("Idle timer read a port");},
            [&](uint16_t p,uint8_t v){require(p==0x20 && v==0x20,"Timer output differs");++outputs;}
        };
    }
};
DosGetTimeRegisters initial() {
    DosGetTimeRegisters r;r.cs=0x1000;r.ds=0x1aa2;r.es=0x3000;r.ss=0x8000;
    r.sp=0x3fe4;r.bp=0x3ff0;r.ip=0x7903;r.flags=0x200;r.ax=11;r.bx=12;r.cx=3;r.dx=14;r.si=16;r.di=18;return r;
}
template<class Exception,class Action>
void rejects(Action action,const char* message) {bool rejected=false;try{action();}catch(const Exception&){rejected=true;}require(rejected,message);}
void unit() {
    const auto copies=[](uint16_t n){return std::min<uint16_t>(n,1);};
    auto r=initial();auto base=FrameActiveOperation(r,0x140,0x160,0x900,0x1000,0x200000).snapshot();
    unsigned cases=0,steps=0;
    for(unsigned callee=0;callee<5;++callee) {
        Memory memory;memory.store(0,0x70,0x0fbe);memory.store(0,0x72,0x1000);
        auto state=base;r=initial();r.ip=0x7a13;state.render=FrameRenderOperation(r,0x1000).snapshot();
        if(callee==1) {r.ip=0x3587;state.render->callee=FrameCameraOperation(r,0x1000).snapshot();}
        if(callee==2) {r.cs=0x18ac;r.ip=0xf4;state.render->callee=FrameWorldRasterOperation(r,0x1000).snapshot();}
        if(callee>=3) {r.cs=0x18ac;r.ip=0x3c8;auto copy=FrameViewCopyOperation(r,0x1000).snapshot();
            if(callee==4) {r.ip=0x407;r.ds=0x4000;r.es=0xa000;copy.registers=r;copy.transferredWords=7;}
            state.render->callee=copy;
        }
        state.render->registers=r;FrameActiveOperation op(state);const auto bus=memory.bus();
        const auto writes=memory.writes;const auto before=op.snapshot();
        require(op.advance(0,bus,copies)==0 && op.snapshot()==before && memory.writes==writes,"Zero budget dispatched render");
        op.deliverTimerInterrupt(bus);
        require(op.interruptInProgress() && !op.finished() && op.snapshot().timerDeliveries==1,"IRQ suspension missing");
        require(op.snapshot().render==before.render,"IRQ changed suspended renderer");
        require(memory.word(r.ss,static_cast<uint16_t>(r.sp-6))==r.ip && memory.word(r.ss,static_cast<uint16_t>(r.sp-4))==r.cs &&
            memory.word(r.ss,static_cast<uint16_t>(r.sp-2))==r.flags,"IRQ stack frame differs");
        const auto suspended=op.snapshot();const auto irqWrites=memory.writes;
        require(op.advance(0,bus,copies)==0 && op.snapshot()==suspended && memory.writes==irqWrites,"Zero budget dispatched IRQ");
        rejects<std::logic_error>([&]{op.deliverTimerInterrupt(bus);},"Nested timer accepted");
        require(op.snapshot()==suspended && memory.writes==irqWrites,"Rejected timer changed state");
        unsigned used=0;
        while(op.interruptInProgress()) {
            require(op.advance(1,bus,copies)==1,"IRQ failed to dispatch");op=FrameActiveOperation(op.snapshot());
            require(++used<200,"IRQ did not return");
        }
        auto returned=r;returned.flags|=2;
        require(op.registers()==returned && op.snapshot().render->registers==returned,"IRQ returned wrong caller registers");
        std::visit([&](const auto& child){using Child=std::remove_cvref_t<decltype(child)>;
            if constexpr(!std::is_same_v<Child,std::monostate>) require(child.registers==returned,"IRQ did not update suspended callee registers");
        },op.snapshot().render->callee);
        require(op.snapshot().timerInstructions==used && op.snapshot().dispatchedInstructions==used && memory.outputs==1,"IRQ accounting differs");
        if(callee==4) {
            const auto copyBefore=std::get<FrameViewCopySnapshot>(op.snapshot().render->callee);
            require(op.advance(1,bus,copies)==1,"REP resume failed");
            const auto copyAfter=std::get<FrameViewCopySnapshot>(op.snapshot().render->callee);
            require(copyAfter.transferredWords==copyBefore.transferredWords+1 && copyAfter.registers.cx==2,"REP was restarted or skipped");
        }
        steps+=used;++cases;
    }
    Memory memory;const auto bus=memory.bus();auto masked=base;masked.foreground.pacing.registers.flags=2;
    FrameActiveOperation op(masked);const auto before=op.snapshot();
    rejects<std::logic_error>([&]{op.deliverTimerInterrupt(bus);},"Masked timer accepted");
    require(op.snapshot()==before && memory.writes==0,"Masked timer changed state");
    auto invalid=base;invalid.renderTimer=TimerIrqSnapshot{};
    rejects<std::invalid_argument>([&]{FrameActiveOperation bad(invalid);},"Timer without renderer accepted");
    auto failed=base;failed.foreground.pacing.stage=FramePacingStage::RuntimeError;
    FrameActiveOperation error(failed);require(error.finished() && !error.returned() && error.advance(9,bus,copies)==0,"Foreground error fell into renderer");
    rejects<std::logic_error>([&]{error.deliverTimerInterrupt(bus);},"Finished foreground accepted IRQ");
    for(auto outcome:{FrameHudOutcome::RuntimeError,FrameHudOutcome::BreakOutput}) {
        auto interrupted=base;r=initial();r.ip=0x79e8;
        interrupted.foreground.hud=FrameHudOperation(r,0x160,0x1000,0x200000).snapshot();
        interrupted.foreground.hud->outcome=outcome;
        FrameActiveOperation stopped(interrupted);
        require(stopped.finished() && !stopped.returned() && !stopped.snapshot().render &&
            stopped.advance(1,bus,copies)==0,"HUD failure/break fell into renderer");
    }
    auto done=base;r=initial();r.ip=0x7a13;done.render=FrameRenderOperation(r,0x1000).snapshot();
    FrameActiveOperation inactive(done);require(inactive.advance(99,bus,copies)==4 && inactive.returned(),"Inactive render did not finish");
    const auto final=inactive.snapshot();require(inactive.advance(99,bus,copies)==0 && inactive.snapshot()==final,"Finished active frame changed");
    rejects<std::logic_error>([&]{inactive.deliverTimerInterrupt(bus);},"Finished renderer accepted IRQ");
    std::cout<<"frame_active_unit=ok render_irq_cases="<<cases<<" timer_steps="<<steps<<" full_frame_claim=0\n";
}
}
int main() {try{unit();return 0;}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
