#include "core/frame_foreground.hpp"
#include "core/pacing_device_clock.hpp"

#include <algorithm>
#include <bit>
#include <fstream>
#include <iostream>
#include <string>
#include <tuple>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool value,const std::string& message) {if(!value) throw std::runtime_error(message);}
struct Reader {
    std::ifstream stream;
    explicit Reader(const char* path):stream(path,std::ios::binary) {require(stream.good(),"Foreground projection missing");}
    uint32_t number(unsigned size) {
        uint32_t value=0;
        for(unsigned i=0;i<size;++i) {const int b=stream.get();require(b>=0,"Truncated foreground projection");value|=uint32_t(b)<<(8*i);}
        return value;
    }
    uint16_t word() {return static_cast<uint16_t>(number(2));}
    uint64_t wide() {const auto low=number(4);return uint64_t{low}|(uint64_t{number(4)}<<32);}
    std::vector<uint8_t> take(unsigned size) {std::vector<uint8_t> result;for(unsigned i=0;i<size;++i)result.push_back(static_cast<uint8_t>(number(1)));return result;}
};
DosGetTimeRegisters registers(Reader& reader) {
    DosGetTimeRegisters r;
    r.ax=reader.word();r.bx=reader.word();r.cx=reader.word();r.dx=reader.word();r.si=reader.word();r.di=reader.word();r.bp=reader.word();
    r.cs=reader.word();r.ds=reader.word();r.es=reader.word();r.ss=reader.word();r.sp=reader.word();r.ip=reader.word();r.flags=reader.number(4);return r;
}
using ClockCases=std::vector<std::vector<PacingDeviceClockSnapshot>>;
ClockCases clocks(const char* path) {
    Reader reader(path);require(reader.take(8)==std::vector<uint8_t>({'L','Z','F','G','C','L','0','1'}),"Foreground clock version differs");
    const auto count=reader.number(4);require(count>=1 && count<=2,"Foreground clock domain differs");ClockCases result;
    for(unsigned c=0;c<count;++c) {
        const auto size=reader.number(4);require(size>1 && size<=150001,"Foreground clock scope differs");
        std::array<uint32_t,256> native{};for(auto& value:native)value=reader.number(4);
        std::optional<RenderPaletteClockSnapshot> palette;
        std::vector<PacingDeviceClockSnapshot> states;
        for(unsigned i=0;i<size;++i) {
            PacingDeviceClockSnapshot observed;auto& state=observed.clock;
            state.cycles=std::bit_cast<int64_t>(reader.wide());state.cycleLeft=std::bit_cast<int64_t>(reader.wide());
            state.ioDelayRemoved=std::bit_cast<int64_t>(reader.wide());state.ticks=reader.wide();reader.take(14);
            state.activeLines=reader.word();state.maskedLines=reader.word();state.inserviceLines=reader.word();state.pending=reader.word();
            state.activeIrq=static_cast<uint8_t>(reader.number(1));state.irq0Vector=static_cast<uint8_t>(reader.number(1));
            state.special=reader.number(1)!=0;state.autoEoi=reader.number(1)!=0;
            state.pitDelay=std::bit_cast<float>(reader.number(4));state.pitStart=std::bit_cast<double>(reader.wide());
            state.pitCount=reader.number(4);state.pitMode=static_cast<uint8_t>(reader.number(1));state.pitUpdate=reader.number(1)!=0;
            const auto events=reader.word();require(events<=64,"Foreground event count differs");
            for(unsigned e=0;e<events;++e) {const auto index=std::bit_cast<float>(reader.number(4));const auto kind=static_cast<PicClockEventKind>(reader.number(1));state.queue.push_back({index,kind,reader.wide()});}
            for(auto& value:observed.devices)value=reader.wide();
            for(auto& value:observed.delayBits)value=reader.wide();
            const auto tickerCount=reader.number(1);require(tickerCount<=16,"Foreground ticker count differs");
            for(unsigned t=0;t<tickerCount;++t)observed.tickers.push_back(static_cast<uint8_t>(reader.number(1)));
            if(reader.number(1)) {
                palette.emplace();palette->first=reader.number(4);palette->last=reader.number(4);
                palette->inMode=reader.number(4);palette->outMode=reader.number(4);
                for(auto& value:palette->rgb)value=reader.number(4);
                for(auto& value:palette->lut)value=reader.number(4);
                for(auto& value:palette->modified)value=static_cast<uint8_t>(reader.number(1));
            }
            require(palette.has_value(),"Foreground palette entry missing");
            for(auto& value:palette->format)value=reader.number(4);
            observed.palette=palette;
            if(i==0) {
                const PacingDeviceClock validated(observed);
                for(unsigned color=0;color<256;++color) {
                    const auto rgb=palette->rgb[color];const auto& f=palette->format;
                    require(native[color]==((((rgb>>16)&255u)<<f[6])|(((rgb>>8)&255u)<<f[7])|((rgb&255u)<<f[8])|f[5]),
                        "Original native palette mapping differs");
                }
            }
            states.push_back(std::move(observed));
        }
        result.push_back(std::move(states));
    }
    require(reader.stream.get()<0,"Foreground clock tail differs");return result;
}
void compare(PacingDeviceClockSnapshot actual,PacingDeviceClockSnapshot expected,const std::string& context) {
    actual.clock.dispatched=expected.clock.dispatched=0;actual.clock.timerDeliveries=expected.clock.timerDeliveries=0;
    actual.clock.millisecondGrants=expected.clock.millisecondGrants=0;
    actual.deviceCallbacks=expected.deviceCallbacks=0;actual.tickerCallbacks=expected.tickerCallbacks=0;
    require(actual==expected,context+" computed clock/device/palette state differs");
    require(std::bit_cast<uint32_t>(actual.clock.pitDelay)==std::bit_cast<uint32_t>(expected.clock.pitDelay) &&
        std::bit_cast<uint64_t>(actual.clock.pitStart)==std::bit_cast<uint64_t>(expected.clock.pitStart),context+" PIT bits differ");
    for(unsigned i=0;i<actual.clock.queue.size();++i)
        require(std::bit_cast<uint32_t>(actual.clock.queue[i].index)==std::bit_cast<uint32_t>(expected.clock.queue[i].index),context+" event bits differ");
}
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576),known=std::vector<uint8_t>(1048576);
    std::vector<std::tuple<bool,uint16_t,uint8_t>> script;
    std::size_t io=0;
    bool strict=false;
    PicWorkClock* clock=nullptr;
    static uint32_t at(uint16_t s,uint16_t o) {return (uint32_t{s}*16+o)&0xfffff;}
    uint8_t read(uint16_t s,uint16_t o) const {require(!strict || known[at(s,o)],"Foreground read outside captured ownership at="+std::to_string(o));return bytes[at(s,o)];}
    uint16_t word(uint16_t s,uint16_t o) const {return static_cast<uint16_t>(read(s,o)|(uint16_t{read(s,static_cast<uint16_t>(o+1u))}<<8));}
    void byte(uint16_t s,uint16_t o,uint8_t v) {require(!strict || known[at(s,o)],"Foreground write outside captured ownership");bytes[at(s,o)]=v;known[at(s,o)]=1;}
    void word(uint16_t s,uint16_t o,uint16_t v) {byte(s,o,static_cast<uint8_t>(v));byte(s,static_cast<uint16_t>(o+1u),static_cast<uint8_t>(v>>8));}
    void seed(uint16_t s,uint16_t o,const std::vector<uint8_t>& values) {for(unsigned i=0;i<values.size();++i)byte(s,static_cast<uint16_t>(o+i),values[i]);}
    TimerIrqBus bus() {
        return {
            [&](uint16_t s,uint16_t o){return read(s,o);},[&](uint16_t s,uint16_t o){return word(s,o);},
            [&](uint16_t s,uint16_t o){return uint32_t{word(s,o)}|(uint32_t{word(s,static_cast<uint16_t>(o+2u))}<<16);},
            [&](uint16_t s,uint16_t o,uint8_t v){byte(s,o,v);},[&](uint16_t s,uint16_t o,uint16_t v){word(s,o,v);},
            [&](uint16_t s,uint16_t o,uint32_t v){word(s,o,static_cast<uint16_t>(v));word(s,static_cast<uint16_t>(o+2u),static_cast<uint16_t>(v>>16));},
            [&](uint16_t p){require(io<script.size() && !std::get<0>(script[io]) && std::get<1>(script[io])==p,"Foreground input order differs");clock->chargePortRead();return std::get<2>(script[io++]);},
            [&](uint16_t p,uint8_t v){require(io<script.size() && script[io++]==std::tuple{true,p,v},"Foreground output order differs");clock->chargePortWrite();if(p==0x20 && v==0x20)clock->nonspecificMasterEoi();}
        };
    }
};
void foregroundBytes(Memory& memory,uint16_t data,const std::vector<uint8_t>& frame,const std::vector<uint8_t>& display,const std::vector<uint8_t>& pacing,bool seed) {
    unsigned position=0;
    const auto access=[&](uint16_t s,uint16_t o,uint8_t value){if(seed)memory.byte(s,o,value);else require(memory.read(s,o)==value,"Foreground timing globals differ");};
    for(auto [offset,length]:{std::pair{0x2074,2},std::pair{0x79a4,9}})
        for(int i=0;i<length;++i)access(data,static_cast<uint16_t>(offset+i),frame[position++]);
    position=0;
    for(auto [offset,length]:{std::pair{0x78c6,4},std::pair{0x79b5,1}})
        for(int i=0;i<length;++i)access(data,static_cast<uint16_t>(offset+i),display[position++]);
    position=0;
    for(auto [offset,length]:{std::pair{0x78c2,2},std::pair{0x78ca,4},std::pair{0x7f68,2}})
        for(int i=0;i<length;++i)access(data,static_cast<uint16_t>(offset+i),pacing[position++]);
    access(0x40,0,pacing[8]);
}
PacingDeviceClockSnapshot paletteInput() {
    PacingDeviceClockSnapshot s;s.clock.cycleLeft=100;s.clock.pitDelay=1000.0f/(1193182.0f/65536.0f);
    s.clock.queue={{0.98f,PicClockEventKind::VgaVertical,0},{s.clock.pitDelay,PicClockEventKind::Pit0,0}};
    s.devices={5,3,0,0,4,50,200,200,0,0,0x8e,1,0,0,0,0,0,0,0,0,0,1,0,0,0};s.tickers={11,10};
    const std::array<double,6> delays{2.5,14,12,13,12.5,0.05};
    for(unsigned i=0;i<6;++i)s.delayBits[i]=std::bit_cast<uint64_t>(delays[i]);
    return s;
}
void paletteOracle(const char* path) {
    Reader reader(path);require(reader.take(8)==std::vector<uint8_t>({'L','Z','P','A','L','0','0','1'}),"Palette oracle version differs");
    const auto count=reader.number(4);require(count==96,"Palette oracle domain differs");unsigned checks=0;
    const auto read=[&](const std::array<uint32_t,18>& format){
        RenderPaletteClockSnapshot p;p.format=format;p.first=reader.number(4);p.last=reader.number(4);const auto dirty=reader.number(4);
        for(auto& value:p.rgb)value=reader.number(4);
        for(auto& value:p.lut)value=reader.number(4);
        for(auto& value:p.modified)value=static_cast<uint8_t>(reader.number(1));
        return std::pair{p,dirty};
    };
    for(unsigned c=0;c<count;++c) {
        std::array<uint32_t,18> format{};for(auto& value:format)value=reader.number(4);
        const auto [input,dirty]=read(format);const auto [expected,expectedDirty]=read(format);
        for(bool clear:{false,true}) {
            auto state=paletteInput();state.palette=input;state.devices[16]=dirty;state.devices[15]=clear;
            PacingDeviceClock clock(state);require(clock.nextDispatch(true,0x202).kind==PicClockBoundaryKind::Ready,"Palette clock boundary differs");
            const auto after=clock.snapshot();require(after.palette==expected && after.devices[16]==expectedDirty && after.devices[15]==0 &&
                after.devices[13]==0,"Unchanged original palette function differs case="+std::to_string(c));
            require(PacingDeviceClock(after).snapshot()==after,"Palette restore differs");++checks;
            state.devices[12]=1;PacingDeviceClock active(state);active.nextDispatch(true,0x202);
            require(active.snapshot().palette==input && active.snapshot().devices[16]==dirty,"Updating renderer incorrectly checked palette");++checks;
        }
    }
    require(reader.stream.get()<0,"Palette oracle tail differs");
    auto state=paletteInput();state.palette.emplace();state.palette->format={32,4,0xff0000,0xff00,0xff,0,16,8,0,0,0,1,1,0,0,0,0,0};
    unsigned rejected=0;
    for(unsigned control=0;control<23;++control) {
        auto bad=state;auto& p=*bad.palette;
        if(control<18) {
            const unsigned f=control;
            if(f==0 || f==1 || f==11 || f==12)p.format[f]=0;
            else if(f==9)p.format[f]=0x4000;
            else ++p.format[f];
        } else if(control==18)p.first=257;
        else if(control==19)p.last=256;
        else if(control==20)p.inMode=1;
        else if(control==21)p.rgb[5]=0x1000000;
        else p.modified[5]=2;
        bool failed=false;try {const PacingDeviceClock invalid(bad);}catch(const std::invalid_argument&){failed=true;}
        require(failed,"Unsupported palette profile accepted control="+std::to_string(control));++rejected;
    }
    std::cout<<"render_palette_original=ok cases="<<count<<" callback_checks="<<checks<<" profile_rejections="<<rejected<<" native_sdl_mapping=1 whole_host_claim=0\n";
}
void original(const char* cpuPath,const char* clockPath,bool live=false,const char* dumpPath=nullptr) {
    const auto clockCases=clocks(clockPath);Reader reader(cpuPath);
    require(reader.take(8)==std::vector<uint8_t>({'L','Z','F','F','G','D','0','1'}),"Foreground CPU version differs");
    const auto count=reader.number(4);require(count==clockCases.size(),"Foreground CPU/clock cases differ");
    uint64_t comparisons=0,transfers=0,grants=0,callbacks=0,irqs=0,expectedIrqs=0;
    std::vector<uint8_t> visual={'L','Z','H','U','D','P','I','X'};
    const auto number=[&](uint32_t value){for(unsigned i=0;i<4;++i)visual.push_back(static_cast<uint8_t>(value>>(8*i)));};
    number(count);
    struct State {DosGetTimeRegisters r;uint32_t mask,io;std::vector<uint8_t> stack,crt,bios,sound,last,hud,pixels,psp,frame,display,pacing;};
    for(unsigned c=0;c<count;++c) {
        const auto game=reader.word(),keyboard=reader.word(),ss=reader.word(),stackBase=reader.word(),entryIp=reader.word();
        const auto bankSegment=reader.word(),bankOffset=reader.word(),bankLength=reader.word(),dos=reader.word(),psp=reader.word();
        const auto size=reader.number(4),ioCount=reader.number(4),irqCount=reader.number(4);
        expectedIrqs+=2u*irqCount;
        require(size==clockCases[c].size() && bankLength==780 && entryIp==0x7903,"Foreground CPU scope differs");
        reader.take(4*irqCount);const auto bank=reader.take(bankLength),font=reader.take(640);std::vector<State> states;
        for(unsigned i=0;i<size;++i) {
            const auto r=registers(reader);const auto mask=reader.number(4),io=reader.number(4);
            states.push_back({r,mask,io,reader.take(128),reader.take(2),reader.take(132),reader.take(10),reader.take(1),reader.take(86),reader.take(272),reader.take(32),reader.take(11),reader.take(5),reader.take(9)});
        }
        std::vector<std::tuple<bool,uint16_t,uint8_t>> events;
        for(unsigned i=0;i<ioCount;++i){const bool output=reader.number(1)!=0;const auto port=reader.word();events.emplace_back(output,port,static_cast<uint8_t>(reader.number(1)));}
        if(live)require(ioCount==irqCount && std::all_of(events.begin(),events.end(),[](const auto& event){
            return event==std::tuple{true,uint16_t{0x20},uint8_t{0x20}};
        }),"Live corpus left the idle-sound EOI-only profile; external port-read inputs are unsupported");
        for(bool restore:{false,true}) {
            Memory memory;memory.script=events;const auto data=static_cast<uint16_t>(game+0xaa2);
            memory.seed(ss,stackBase,states[0].stack);memory.seed(0x40,0,states[0].bios);memory.seed(data,0x7f6d,states[0].crt);
            memory.seed(data,0x2058,states[0].last);memory.seed(bankSegment,bankOffset,bank);memory.seed(psp,0x2e,states[0].psp);
            memory.word(0,0x58,keyboard);memory.word(0,0x5a,0xf000);memory.word(0,0x70,0x0fbe);memory.word(0,0x72,game);
            memory.word(0,0x84,dos);memory.word(0,0x86,0xf000);
            unsigned position=0;
            for(auto [offset,length]:{std::pair{0x78c0,2},std::pair{0x79a0,3},std::pair{0x79c0,5}})
                for(int i=0;i<length;++i)memory.byte(data,static_cast<uint16_t>(offset+i),states[0].sound[position++]);
            position=0;
            for(auto [offset,length]:{std::pair{0x206e,30},std::pair{0x79b3,47},std::pair{0x1aae,7},std::pair{0x1afa,2}})
                for(int i=0;i<length;++i)memory.byte(data,static_cast<uint16_t>(offset+i),states[0].hud[position++]);
            foregroundBytes(memory,data,states[0].frame,states[0].display,states[0].pacing,true);
            memory.seed(data,memory.word(data,0x2070),font);position=0;
            for(unsigned block=0;block<2;++block)for(unsigned row=0;row<8;++row)for(unsigned x=0;x<17;++x)
                memory.byte(0xa000,static_cast<uint16_t>((166+block*16+row)*320+159+x),states[0].pixels[position++]);
            memory.strict=true;FrameForegroundOperation operation(states[0].r,dos,keyboard,psp,game,0x200000);
            PacingDeviceClock clock(clockCases[c][0]);memory.clock=&clock.workClock();const auto bus=memory.bus();
            for(unsigned step=0;step<size;++step) {
                const auto context="Foreground case="+std::to_string(c)+" state="+std::to_string(step);
                compare(clock.snapshot(),clockCases[c][step],context);
                auto actual=operation.registers(),expected=states[step].r;
                require(((actual.flags^expected.flags)&states[step].mask)==0,context+" control flags differ");actual.flags=expected.flags=0;
                require(actual==expected,context+" CPU differs ip="+std::to_string(actual.ip));require(memory.io==states[step].io,context+" I/O differs");
                const auto check=[&](uint16_t s,uint16_t o,const std::vector<uint8_t>& values){for(unsigned i=0;i<values.size();++i)require(memory.read(s,static_cast<uint16_t>(o+i))==values[i],context+" captured memory differs at="+std::to_string(o+i));};
                check(ss,stackBase,states[step].stack);check(0x40,0,states[step].bios);check(data,0x7f6d,states[step].crt);
                check(data,0x2058,states[step].last);check(psp,0x2e,states[step].psp);check(bankSegment,bankOffset,bank);check(data,memory.word(data,0x2070),font);
                foregroundBytes(memory,data,states[step].frame,states[step].display,states[step].pacing,false);position=0;
                for(auto [offset,length]:{std::pair{0x78c0,2},std::pair{0x79a0,3},std::pair{0x79c0,5}})
                    for(int i=0;i<length;++i)require(memory.read(data,static_cast<uint16_t>(offset+i))==states[step].sound[position++],context+" sound differs");
                position=0;
                for(auto [offset,length]:{std::pair{0x206e,30},std::pair{0x79b3,47},std::pair{0x1aae,7},std::pair{0x1afa,2}})
                    for(int i=0;i<length;++i)require(memory.read(data,static_cast<uint16_t>(offset+i))==states[step].hud[position++],context+" HUD differs");
                position=0;
                for(unsigned block=0;block<2;++block)for(unsigned row=0;row<8;++row)for(unsigned x=0;x<17;++x)
                    require(memory.read(0xa000,static_cast<uint16_t>((166+block*16+row)*320+159+x))==states[step].pixels[position++],context+" pixel differs");
                const auto old=operation.snapshot();require(operation.advance(0,bus,[](uint16_t)->uint16_t{throw std::runtime_error("Zero budget charged REP");})==0 && operation.snapshot()==old,"Zero foreground budget changed state");
                ++comparisons;
                if(step+1<size) {
                    const auto before=operation.registers();const bool timer=operation.interruptInProgress();
                    const bool callback=before.cs==0xf000 && (timer?before.ip==0xfea5:before.ip==dos+1u || before.ip==keyboard+1u);
                    const bool iret=timer?((before.cs==0xf000 && before.ip==0xfeb6)||(before.cs==game && before.ip==0x1090)):
                        before.cs==0xf000 && (before.ip==dos+14u || before.ip==keyboard+5u);
                    require(operation.advance(1,bus,[&](uint16_t n){return clock.workClock().chargeStringTransfers(n);})==1,context+" dispatch differs");
                    const auto flags=operation.registers().flags;const bool sti=before.cs==0xf000 && (before.ip==dos || before.ip==keyboard);
                    auto boundary=clock.nextDispatch(callback||((iret||sti)&&(flags&0x200u)&&clock.workClock().snapshot().pending),flags);
                    while(boundary.kind==PicClockBoundaryKind::NeedMillisecond){clock.grantMillisecond();boundary=clock.nextDispatch(false,flags);}
                    require(boundary.kind==PicClockBoundaryKind::Ready,context+" unsupported clock boundary");
                    if(boundary.timerDelivered){operation.deliverTimerInterrupt(bus);++irqs;}
                }
                if(restore){operation=FrameForegroundOperation(operation.snapshot());clock=PacingDeviceClock(clock.snapshot());memory.clock=&clock.workClock();}
            }
            require(operation.returned() && operation.snapshot().dispatchedInstructions==size-1 && memory.io==ioCount,"Foreground terminal differs");
            require(operation.snapshot().hud.has_value(),"Foreground HUD handoff missing");
            transfers+=operation.snapshot().hud->stringTransfers;grants+=clock.snapshot().clock.millisecondGrants;callbacks+=clock.snapshot().deviceCallbacks;
            require(operation.snapshot().pacing.dispatchedInstructions+operation.snapshot().hud->dispatchedInstructions==size-1,"Foreground work was lost at handoff");
            if(dumpPath && !restore) {
                number(c);number(states[0].pacing[0]|(uint32_t{states[0].pacing[1]}<<8));
                const auto palette=clock.snapshot().palette;require(palette.has_value(),"HUD dump has no computed palette");
                for(auto rgb:palette->rgb)for(unsigned shift:{16u,8u,0u})visual.push_back(static_cast<uint8_t>(rgb>>shift));
                for(unsigned block=0;block<2;++block)for(unsigned row=0;row<8;++row)for(unsigned x=0;x<17;++x)
                    visual.push_back(memory.read(0xa000,static_cast<uint16_t>((166+block*16+row)*320+159+x)));
                visual.insert(visual.end(),states.back().pixels.begin(),states.back().pixels.end());
            }
        }
    }
    require(reader.stream.get()<0,"Foreground CPU tail differs");
    require(callbacks>0 && grants>0,"Foreground corpus did not exercise live device timing");
    require(irqs==expectedIrqs,"Computed and observed timer delivery counts differ");
    if(live)require(transfers>0 && irqs>0,"Live foreground corpus missed changed glyphs or natural timer delivery");
    if(dumpPath) {
        require(!std::ifstream(dumpPath,std::ios::binary).good(),"HUD dump already exists");
        std::ofstream dump(dumpPath,std::ios::binary);dump.write(reinterpret_cast<const char*>(visual.data()),static_cast<std::streamsize>(visual.size()));
        require(dump.good(),"HUD dump write failed");
    }
    std::cout<<(live?"frame_foreground_live=ok cases=":"frame_foreground_original=ok cases=")<<count<<" comparisons="<<comparisons<<" transfers="<<transfers
        <<" millisecond_grants="<<grants<<" device_callbacks="<<callbacks<<" predicted_irqs="<<irqs<<" later_state_injected=0 whole_game_parity=0";
    if(live)std::cout<<" external_port_read_inputs=0";
    std::cout<<'\n';
}
}
int main(int argc,char** argv) {
    try {require(argc==3 || ((argc==4 || argc==5) && std::string(argv[1])=="--live"),"Expected original foreground CPU and clock projections");
        if(argc>=4)original(argv[2],argv[3],true,argc==5?argv[4]:nullptr);
        else if(std::string(argv[1])=="--palette-oracle")paletteOracle(argv[2]);else original(argv[1],argv[2]);}
    catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
