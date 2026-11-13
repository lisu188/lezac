#include "core/frame_hud.hpp"
#include "core/pacing_device_clock.hpp"
#include <bit>

#include <algorithm>
#include <fstream>
#include <iostream>
#include <string>
#include <tuple>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool value, const std::string& message) { if (!value) throw std::runtime_error(message); }
struct Memory {
    std::vector<uint8_t> bytes = std::vector<uint8_t>(1048576), known = std::vector<uint8_t>(1048576);
    std::vector<std::tuple<bool,uint16_t,uint8_t>> script;
    std::vector<uint8_t> writes;
    std::size_t io = 0;
    bool strict = false;
    static uint32_t at(uint16_t s,uint16_t o) { return (uint32_t{s}*16+o)&0xfffff; }
    uint8_t read(uint16_t s,uint16_t o) const { require(!strict || known[at(s,o)],"Read outside original drain input"); return bytes[at(s,o)]; }
    uint16_t word(uint16_t s,uint16_t o) const { return static_cast<uint16_t>(read(s,o)|(uint16_t{read(s,static_cast<uint16_t>(o+1u))}<<8)); }
    void byte(uint16_t s,uint16_t o,uint8_t v) {
        require(!strict || known[at(s,o)],"Write outside original drain ownership"); bytes[at(s,o)]=v; known[at(s,o)]=1;
        if(s==0x1aa2 && o==0x2058) writes.push_back(v);
    }
    void word(uint16_t s,uint16_t o,uint16_t v) { byte(s,o,static_cast<uint8_t>(v)); byte(s,static_cast<uint16_t>(o+1u),static_cast<uint8_t>(v>>8)); }
    explicit Memory(bool defaults=true) {
        if(!defaults) return;
        word(0,0x58,0x1200); word(0,0x5a,0xf000); word(0,0x70,0x0fbe); word(0,0x72,0x1000);
        word(0x40,0x80,0x1e); word(0x40,0x82,0x3e); word(0x40,0x1a,0x1e); word(0x40,0x1c,0x1e);
        word(0x40,0x6c,100); byte(0x40,0x40,2); byte(0x40,0x3f,0xa5);
        byte(0x1aa2,0x2058,0xa7); writes.clear();
    }
    void keys(const std::vector<uint16_t>& values,uint16_t head=0x1e) {
        word(0x40,0x1a,head); auto tail=head;
        for(auto key:values) { word(0x40,tail,key); tail=static_cast<uint16_t>(tail+2u); if(tail>=0x3e) tail=0x1e; }
        word(0x40,0x1c,tail);
    }
    TimerIrqBus bus() {
        return {
            [&](uint16_t s,uint16_t o){return read(s,o);},
            [&](uint16_t s,uint16_t o){return word(s,o);},
            [&](uint16_t s,uint16_t o){return uint32_t{word(s,o)}|(uint32_t{word(s,static_cast<uint16_t>(o+2u))}<<16);},
            [&](uint16_t s,uint16_t o,uint8_t v){byte(s,o,v);},
            [&](uint16_t s,uint16_t o,uint16_t v){word(s,o,v);},
            [&](uint16_t s,uint16_t o,uint32_t v){word(s,o,static_cast<uint16_t>(v));word(s,static_cast<uint16_t>(o+2u),static_cast<uint16_t>(v>>16));},
            [&](uint16_t p){
                require(p==0x61,"Unexpected drain IRQ input"); if(!strict) return uint8_t{0};
                require(io<script.size() && !std::get<0>(script[io]) && std::get<1>(script[io])==p,"Original drain input order differs");
                return std::get<2>(script[io++]);
            },
            [&](uint16_t p,uint8_t v){
                require(p==0x20 || p==0x61,"Unexpected drain IRQ output");
                if(strict) require(io<script.size() && script[io++]==std::tuple{true,p,v},"Original drain output order differs");
            }
        };
    }
};
struct Reader {
    std::ifstream stream;
    explicit Reader(const char* path):stream(path,std::ios::binary) {require(stream.good(),"Drain projection is missing");}
    uint32_t number(unsigned size) {
        uint32_t value=0; for(unsigned i=0;i<size;++i) {const int byte=stream.get();require(byte>=0,"Truncated drain projection");value|=uint32_t(byte)<<(8*i);} return value;
    }
    uint16_t word() {return static_cast<uint16_t>(number(2));}
    std::vector<uint8_t> take(unsigned size) {std::vector<uint8_t> data;for(unsigned i=0;i<size;++i)data.push_back(static_cast<uint8_t>(number(1)));return data;}
    uint64_t wide() {const auto low=number(4);return uint64_t{low}|(uint64_t{number(4)}<<32);}
};
using ClockCases=std::vector<std::vector<PacingDeviceClockSnapshot>>;
class ReplayClock {
public:
    explicit ReplayClock(PacingDeviceClockSnapshot state):state_(state) {
        if(state.devices[16]) core_.emplace(state.clock);
        else full_.emplace(state);
    }
    PicWorkClock& workClock() {return full_?full_->workClock():*core_;}
    PacingDeviceClockSnapshot snapshot() const {if(full_)return full_->snapshot();auto result=state_;result.clock=core_->snapshot();return result;}
    PicClockBoundary nextDispatch(bool returned,uint32_t flags) {return full_?full_->nextDispatch(returned,flags):core_->nextDispatch(returned,flags);}
    void grantMillisecond() {require(full_.has_value(),"Passive dirty-palette window crossed an unmodeled ticker");full_->grantMillisecond();}
private:
    PacingDeviceClockSnapshot state_;
    std::optional<PacingDeviceClock> full_;
    std::optional<PicWorkClock> core_;
};
ClockCases clocks(const char* path) {
    Reader reader(path);require(reader.take(8)==std::vector<uint8_t>({'L','Z','P','D','C','L','0','1'}),"HUD clock version differs");
    const auto count=reader.number(4);require(count>0 && count<=4,"HUD clock cases differ");ClockCases result;
    for(unsigned c=0;c<count;++c) {
        const auto size=reader.number(4);require(size>1 && size<=8193,"HUD clock states differ");std::vector<PacingDeviceClockSnapshot> states;
        for(unsigned i=0;i<size;++i) {
            PacingDeviceClockSnapshot observed;auto& state=observed.clock;
            state.cycles=std::bit_cast<int64_t>(reader.wide());state.cycleLeft=std::bit_cast<int64_t>(reader.wide());
            state.ioDelayRemoved=std::bit_cast<int64_t>(reader.wide());state.ticks=reader.wide();reader.take(14);
            state.activeLines=reader.word();state.maskedLines=reader.word();state.inserviceLines=reader.word();state.pending=reader.word();
            state.activeIrq=static_cast<uint8_t>(reader.number(1));state.irq0Vector=static_cast<uint8_t>(reader.number(1));
            state.special=reader.number(1)!=0;state.autoEoi=reader.number(1)!=0;
            state.pitDelay=std::bit_cast<float>(reader.number(4));state.pitStart=std::bit_cast<double>(reader.wide());
            state.pitCount=reader.number(4);state.pitMode=static_cast<uint8_t>(reader.number(1));state.pitUpdate=reader.number(1)!=0;
            const auto events=reader.word();require(events<=64,"HUD event count differs");
            for(unsigned e=0;e<events;++e) {const auto index=std::bit_cast<float>(reader.number(4));const auto kind=static_cast<PicClockEventKind>(reader.number(1));state.queue.push_back({index,kind,reader.wide()});}
            for(auto& value:observed.devices)value=reader.wide();
            for(auto& value:observed.delayBits)value=reader.wide();
            const auto tickerCount=reader.number(1);require(tickerCount<=16,"HUD ticker count differs");
            for(unsigned t=0;t<tickerCount;++t)observed.tickers.push_back(static_cast<uint8_t>(reader.number(1)));
            states.push_back(std::move(observed));
        }
        result.push_back(std::move(states));
    }
    require(reader.stream.get()<0,"HUD clock tail differs");return result;
}
void compare(PacingDeviceClockSnapshot actual,PacingDeviceClockSnapshot expected,const std::string& context) {
    actual.clock.dispatched=expected.clock.dispatched=0;actual.clock.timerDeliveries=expected.clock.timerDeliveries=0;
    actual.clock.millisecondGrants=expected.clock.millisecondGrants=0;
    actual.deviceCallbacks=expected.deviceCallbacks=0;actual.tickerCallbacks=expected.tickerCallbacks=0;
    require(actual==expected,context+" computed clock/device state differs");
    require(std::bit_cast<uint32_t>(actual.clock.pitDelay)==std::bit_cast<uint32_t>(expected.clock.pitDelay) &&
        std::bit_cast<uint64_t>(actual.clock.pitStart)==std::bit_cast<uint64_t>(expected.clock.pitStart),context+" PIT bits differ");
    for(unsigned i=0;i<actual.clock.queue.size();++i)
        require(std::bit_cast<uint32_t>(actual.clock.queue[i].index)==std::bit_cast<uint32_t>(expected.clock.queue[i].index),context+" event index bits differ");
}
DosGetTimeRegisters registers(Reader& reader) {
    DosGetTimeRegisters r;
    r.ax=reader.word();r.bx=reader.word();r.cx=reader.word();r.dx=reader.word();r.si=reader.word();r.di=reader.word();r.bp=reader.word();
    r.cs=reader.word();r.ds=reader.word();r.es=reader.word();r.ss=reader.word();r.sp=reader.word();r.ip=reader.word();r.flags=reader.number(4);return r;
}
void seedHud(Memory& memory,const std::vector<uint8_t>& bytes) {
    unsigned position=0;
    for(auto [offset,length]:{std::pair{0x206e,30},std::pair{0x79b3,47},std::pair{0x1aae,7},std::pair{0x1afa,2}})
        for(int i=0;i<length;++i)memory.byte(0x1aa2,static_cast<uint16_t>(offset+i),bytes[position++]);
}
void checkHud(const Memory& memory,const std::vector<uint8_t>& bytes) {
    unsigned position=0;
    for(auto [offset,length]:{std::pair{0x206e,30},std::pair{0x79b3,47},std::pair{0x1aae,7},std::pair{0x1afa,2}})
        for(int i=0;i<length;++i)require(memory.read(0x1aa2,static_cast<uint16_t>(offset+i))==bytes[position++],"Original controlled HUD globals differ");
}
void oracle(const char* path) {
    Reader reader(path);require(reader.take(8)==std::vector<uint8_t>({'L','Z','H','U','D','O','R','1'}),"HUD oracle version differs");
    const auto count=reader.number(4);require(count==17,"HUD oracle domain differs");unsigned boundaries=0;
    for(unsigned index=0;index<count;++index) {
        const bool error=reader.number(1)!=0;const auto input=registers(reader);
        const auto stack=reader.take(128),hud=reader.take(86),font=reader.take(640),pixels=reader.take(272);
        const auto expected=registers(reader);const auto finalStack=reader.take(128),finalHud=reader.take(86),finalPixels=reader.take(272);
        const auto initial=[&]() {
            Memory memory(false);seedHud(memory,hud);
            for(unsigned i=0;i<128;++i)memory.byte(0x8000,static_cast<uint16_t>(0xfdb0+i),stack[i]);
            for(unsigned i=0;i<640;++i)memory.byte(0x1aa2,static_cast<uint16_t>(40000+i),font[i]);
            unsigned position=0;
            for(unsigned block=0;block<2;++block)for(unsigned row=0;row<8;++row)for(unsigned x=0;x<17;++x)
                memory.byte(0xa000,static_cast<uint16_t>((166+block*16+row)*320+159+x),pixels[position++]);
            memory.strict=true;return memory;
        };
        const auto checkPixels=[&](const Memory& memory) {
            unsigned position=0;
            for(unsigned block=0;block<2;++block)for(unsigned row=0;row<8;++row)for(unsigned x=0;x<17;++x)
                require(memory.read(0xa000,static_cast<uint16_t>((166+block*16+row)*320+159+x))==finalPixels[position++],"Original controlled indexed pixels differ");
        };
        uint64_t fullWork=0;
        for(bool partial:{false,true}) {
            Memory memory=initial();FrameHudOperation operation(input,0x1200,0x1000,0x200000);
            const FrameHudOperation::CopyBudget copies=[&](uint16_t requested){return partial?std::min<uint16_t>(requested,1):requested;};
            while(!operation.finished()) {
                require(operation.snapshot().dispatchedInstructions<20000,"Controlled HUD did not terminate");
                require(operation.advance(1,memory.bus(),copies)==1,"Controlled HUD did not dispatch");operation=FrameHudOperation(operation.snapshot());
            }
            require(operation.registers()==expected && operation.returned()!=error,"Original controlled CPU/full flags or error handoff differs case="+std::to_string(index));
            checkHud(memory,finalHud);checkPixels(memory);
            for(unsigned i=0;i<640;++i)require(memory.read(0x1aa2,static_cast<uint16_t>(40000+i))==font[i],"Original controlled font changed");
            for(unsigned i=0;i<128;++i)require(memory.read(0x8000,static_cast<uint16_t>(0xfdb0+i))==finalStack[i],"Original controlled stack differs");
            if(!partial)fullWork=operation.snapshot().dispatchedInstructions;
        }
        if(index==3)for(uint64_t boundary=0;boundary<=fullWork;++boundary) {
            Memory memory=initial();memory.strict=false;memory.word(0,0x70,0x0fbe);memory.word(0,0x72,0x1000);
            memory.word(0x40,0x6c,100);memory.byte(0x40,0x40,2);memory.byte(0x40,0x3f,0xa5);
            FrameHudOperation operation(input,0x1200,0x1000,0x200000);const auto copies=[](uint16_t n){return n;};
            require(operation.advance(boundary,memory.bus(),copies)==boundary,"HUD pre-IRQ work differs");operation.deliverTimerInterrupt(memory.bus());
            while(!operation.finished()) {operation.advance(1,memory.bus(),copies);operation=FrameHudOperation(operation.snapshot());}
            require(operation.registers()==expected && operation.snapshot().timerInstructions==36 && memory.word(0x40,0x6c)==101,
                "HUD IRQ changed caller context or work");checkHud(memory,finalHud);checkPixels(memory);++boundaries;
        }
    }
    require(reader.stream.get()<0,"HUD oracle tail differs");
    std::cout<<"frame_hud_oracle=ok cases=17 copy_modes=2 full_endpoint_flags=1 timer_boundaries="<<boundaries<<" original_calls_stubbed=0\n";
}
void unit() {
    struct BudgetCase {int64_t cycles;uint16_t requested,transferred;int64_t remaining;};
    const std::vector<BudgetCase> cases={{0,0,0,0},{0,1,1,0},{0,4,1,0},
        {1,0,0,2},{1,1,1,1},{2,3,3,0},{8,4,4,5},{8,30,9,0}};
    for(auto [cycles,requested,transferred,remaining]:cases) {
        PicWorkClockSnapshot state;state.cycles=cycles;state.pitDelay=1000.0f/(1193182.0f/65536.0f);
        PicWorkClock clock(state);require(clock.chargeStringTransfers(requested)==transferred && clock.snapshot().cycles==remaining,
            "Pinned normal-core REP charge differs");
        require(PicWorkClock(clock.snapshot()).snapshot()==clock.snapshot(),"REP charge snapshot differs");
    }
    FrameHudSnapshot shifted;shifted.gameSegment=0x1000;shifted.hudOnly=true;
    shifted.registers.cs=0x1000;shifted.registers.ip=0x315c;shifted.registers.ax=9;shifted.registers.flags=0x202;
    Memory memory;FrameHudOperation operation(shifted);operation.advance(1,memory.bus(),[](uint16_t n){return n;});
    require(operation.registers().ax==576 && (operation.registers().flags&0x10u),"Pinned SHLW AF materialization differs");
    std::cout<<"frame_hud_unit=ok string_budget_cases=8\n";
}
void original(const char* cpuPath,const char* clockPath) {
    const auto clockCases=clocks(clockPath);Reader reader(cpuPath);
    require(reader.take(8)==std::vector<uint8_t>({'L','Z','F','H','U','D','0','1'}),"HUD CPU version differs");
    const auto count=reader.number(4);require(count==clockCases.size(),"HUD CPU/clock cases differ");uint64_t comparisons=0,transfers=0,grants=0;
    struct State {DosGetTimeRegisters r;uint32_t mask,io;std::vector<uint8_t> stack,crt,bios,sound,last,hud,pixels;};
    for(unsigned caseIndex=0;caseIndex<count;++caseIndex) {
        const auto game=reader.word(),base=reader.word(),ss=reader.word(),stackBase=reader.word(),entryIp=reader.word();
        const auto bankSegment=reader.word(),bankOffset=reader.word(),bankLength=reader.word();
        const auto stateCount=reader.number(4),ioCount=reader.number(4),irqCount=reader.number(4);
        require(stateCount==clockCases[caseIndex].size() && bankLength==780,"HUD CPU scope differs");
        reader.take(4*irqCount);const auto bank=reader.take(bankLength),font=reader.take(640);std::vector<State> states;
        for(unsigned i=0;i<stateCount;++i) {
            DosGetTimeRegisters r;
            r.ax=reader.word();r.bx=reader.word();r.cx=reader.word();r.dx=reader.word();r.si=reader.word();r.di=reader.word();r.bp=reader.word();
            r.cs=reader.word();r.ds=reader.word();r.es=reader.word();r.ss=reader.word();r.sp=reader.word();r.ip=reader.word();r.flags=reader.number(4);
            const auto mask=reader.number(4),io=reader.number(4);
            states.push_back({r,mask,io,reader.take(128),reader.take(2),reader.take(132),reader.take(10),reader.take(1),reader.take(86),reader.take(272)});
        }
        std::vector<std::tuple<bool,uint16_t,uint8_t>> events;
        for(unsigned i=0;i<ioCount;++i){const bool output=reader.number(1)!=0;const auto port=reader.word();events.emplace_back(output,port,static_cast<uint8_t>(reader.number(1)));}
        for(bool restore:{false,true}) {
            Memory memory(false);memory.script=events;const auto data=static_cast<uint16_t>(game+0xaa2);
            const auto seed=[&](uint16_t s,uint16_t o,const std::vector<uint8_t>& bytes){for(unsigned i=0;i<bytes.size();++i)memory.byte(s,static_cast<uint16_t>(o+i),bytes[i]);};
            seed(ss,stackBase,states[0].stack);seed(0x40,0,states[0].bios);seed(data,0x7f6d,states[0].crt);seed(data,0x2058,states[0].last);seed(bankSegment,bankOffset,bank);
            memory.word(0,0x58,base);memory.word(0,0x5a,0xf000);memory.word(0,0x70,0x0fbe);memory.word(0,0x72,game);
            unsigned position=0;
            for(auto [offset,length]:{std::pair{0x78c0,2},std::pair{0x79a0,3},std::pair{0x79c0,5}})
                for(int i=0;i<length;++i)memory.byte(data,static_cast<uint16_t>(offset+i),states[0].sound[position++]);
            position=0;
            for(auto [offset,length]:{std::pair{0x206e,30},std::pair{0x79b3,47},std::pair{0x1aae,7},std::pair{0x1afa,2}})
                for(int i=0;i<length;++i)memory.byte(data,static_cast<uint16_t>(offset+i),states[0].hud[position++]);
            seed(data,memory.word(data,0x2070),font);position=0;
            for(unsigned block=0;block<2;++block)for(unsigned row=0;row<8;++row)for(unsigned x=0;x<17;++x)
                memory.byte(0xa000,static_cast<uint16_t>((166+block*16+row)*320+159+x),states[0].pixels[position++]);
            memory.strict=true;require(entryIp==0x79e8,"HUD entry differs");
            FrameHudOperation operation(states[0].r,base,game,0x200000);
            ReplayClock clock(clockCases[caseIndex][0]);
            const auto bus=memory.bus();
            for(unsigned step=0;step<stateCount;++step) {
                const auto context="HUD case="+std::to_string(caseIndex)+" state="+std::to_string(step);
                compare(clock.snapshot(),clockCases[caseIndex][step],context);
                auto actual=operation.registers(),expected=states[step].r;
                require(((actual.flags^expected.flags)&states[step].mask)==0,context+" control flags differ");actual.flags=expected.flags=0;
                require(actual==expected,context+" CPU differs ip="+std::to_string(actual.ip));require(memory.io==states[step].io,context+" I/O differs");
                for(unsigned i=0;i<128;++i)require(memory.read(ss,static_cast<uint16_t>(stackBase+i))==states[step].stack[i],context+" stack differs");
                for(unsigned i=0;i<132;++i)require(memory.read(0x40,static_cast<uint16_t>(i))==states[step].bios[i],context+" BIOS differs");
                for(unsigned i=0;i<2;++i)require(memory.read(data,static_cast<uint16_t>(0x7f6d+i))==states[step].crt[i],context+" CRT differs");
                require(memory.read(data,0x2058)==states[step].last[0],context+" key differs");position=0;
                for(auto [offset,length]:{std::pair{0x78c0,2},std::pair{0x79a0,3},std::pair{0x79c0,5}})
                    for(int i=0;i<length;++i)require(memory.read(data,static_cast<uint16_t>(offset+i))==states[step].sound[position++],context+" sound globals differ");
                for(unsigned i=0;i<640;++i)require(memory.read(data,static_cast<uint16_t>(memory.word(data,0x2070)+i))==font[i],context+" font changed");
                for(unsigned i=0;i<bankLength;++i)require(memory.read(bankSegment,static_cast<uint16_t>(bankOffset+i))==bank[i],context+" sound bank changed");
                const auto old=operation.snapshot();require(operation.advance(0,bus,[](uint16_t)->uint16_t{throw std::runtime_error("Zero budget charged REP");})==0 &&
                    operation.snapshot()==old,"Zero HUD budget changed state");position=0;
                for(auto [offset,length]:{std::pair{0x206e,30},std::pair{0x79b3,47},std::pair{0x1aae,7},std::pair{0x1afa,2}})
                    for(int i=0;i<length;++i)require(memory.read(data,static_cast<uint16_t>(offset+i))==states[step].hud[position++],context+" HUD scratch/cache/palette differs");
                position=0;
                for(unsigned block=0;block<2;++block)for(unsigned row=0;row<8;++row)for(unsigned x=0;x<17;++x)
                    require(memory.read(0xa000,static_cast<uint16_t>((166+block*16+row)*320+159+x))==states[step].pixels[position++],context+" indexed pixel differs");
                ++comparisons;
                if(step+1<stateCount) {
                    const auto before=operation.registers();const bool timer=operation.interruptInProgress();
                    const bool callback=before.cs==0xf000 && before.ip==(timer?0xfea5:base+1u);
                    const bool iret=timer?((before.cs==0xf000 && before.ip==0xfeb6)||(before.cs==game && before.ip==0x1090)):
                        (before.cs==0xf000 && before.ip==base+5u);
                    require(operation.advance(1,bus,[&](uint16_t requested){return clock.workClock().chargeStringTransfers(requested);})==1,"HUD dispatch differs");
                    const auto flags=operation.registers().flags;const bool sti=before.cs==0xf000 && before.ip==base;
                    auto boundary=clock.nextDispatch(callback||((iret||sti)&&(flags&0x200u)&&clock.workClock().snapshot().pending),flags);
                    while(boundary.kind==PicClockBoundaryKind::NeedMillisecond){clock.grantMillisecond();boundary=clock.nextDispatch(false,flags);}
                    require(boundary.kind==PicClockBoundaryKind::Ready,context+" unsupported clock boundary");
                    if(boundary.timerDelivered)operation.deliverTimerInterrupt(bus);
                }
                if(restore){operation=FrameHudOperation(operation.snapshot());clock=ReplayClock(clock.snapshot());}
            }
            require(operation.returned() && operation.snapshot().dispatchedInstructions==stateCount-1,"HUD terminal differs");
            transfers+=operation.snapshot().stringTransfers;grants+=clock.snapshot().clock.millisecondGrants;
        }
    }
    require(reader.stream.get()<0,"HUD CPU tail differs");
    std::cout<<"frame_hud_original=ok cases="<<count<<" comparisons="<<comparisons<<" string_transfers="<<transfers
        <<" millisecond_grants="<<grants<<" later_state_injected=0\n";
}
}
int main(int argc,char** argv) {
    try {
        unit();
        if(argc==4 && std::string(argv[1])=="--original")original(argv[2],argv[3]);
        else if(argc==3 && std::string(argv[1])=="--oracle")oracle(argv[2]);
        else require(argc==1,"Expected --original CPU clock or --oracle file");
    }
    catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
