#include "core/frame_active.hpp"
#include "core/frame_prefix.hpp"
#include "core/frame_iteration.hpp"
#include "core/pacing_device_clock.hpp"
#include "core/vga_dac_writer.hpp"

#include <algorithm>
#include <bit>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <system_error>
#include <vector>

using namespace lezac::core;
namespace {
#ifdef LEZAC_TEST_FRAME_ITERATION
constexpr unsigned LiveStateLimit=2000001;
#else
constexpr unsigned LiveStateLimit=500001;
#endif
#if defined(LEZAC_TEST_FRAME_ITERATION)
using LiveOperation=FrameIterationOperation;
constexpr const char* LiveMagic="LZFILV01";
constexpr const char* LiveResult="frame_iteration_live";
bool renderInProgress(const LiveOperation& operation) {
    const auto* prefix=std::get_if<FramePrefixSnapshot>(&operation.snapshot().callee);
    if (!prefix) return false;
    const auto* active=std::get_if<FrameActiveSnapshot>(&prefix->callee);
    return active && active->render.has_value();
}
bool terminal(const LiveOperation& operation) {
    return operation.finished() && operation.snapshot().outcome==FrameIterationOutcome::NextFrame;
}
#elif defined(LEZAC_TEST_FRAME_PREFIX)
using LiveOperation=FramePrefixOperation;
constexpr const char* LiveMagic="LZPFLV01";
constexpr const char* LiveResult="frame_prefix_live";
bool renderInProgress(const LiveOperation& operation) {
    const auto* active=std::get_if<FrameActiveSnapshot>(&operation.snapshot().callee);
    return active && active->render.has_value();
}
bool terminal(const LiveOperation& operation) {
    return operation.finished() && operation.snapshot().outcome==FramePrefixOutcome::ActorUpdate;
}
#else
using LiveOperation=FrameActiveOperation;
constexpr const char* LiveMagic="LZACTV01";
constexpr const char* LiveResult="frame_active_live";
bool renderInProgress(const LiveOperation& operation) {return operation.snapshot().render.has_value();}
bool terminal(const LiveOperation& operation) {return operation.returned();}
#endif
void require(bool value,const std::string& message) {if(!value) throw std::runtime_error(message);}
bool outputEntryExists(const std::string& path) {
    std::error_code error;
    const auto status=std::filesystem::symlink_status(path,error);
    require(!error || error==std::errc::no_such_file_or_directory,"Cannot inspect active output: "+path);
    return std::filesystem::exists(status);
}
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
    const auto count=reader.number(4);require(count>=1 && count<=4,"Foreground clock domain differs");ClockCases result;
    for(unsigned c=0;c<count;++c) {
        const auto size=reader.number(4);require(size>1 && size<=LiveStateLimit,"Foreground clock scope differs");
        std::array<uint32_t,256> native{};for(auto& value:native)value=reader.number(4);
        std::optional<RenderPaletteClockSnapshot> palette;
        std::vector<PacingDeviceClockSnapshot> states;
        states.reserve(size);
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
    std::vector<uint8_t> bytes;
    PicWorkClock* clock=nullptr;
    uint64_t writes=0,outputs=0;
    PacingDeviceClock* devices=nullptr;
    VgaDacWriter dac{};
    uint64_t dacWrites=0;
    static uint32_t at(uint16_t s,uint16_t o) {return (uint32_t{s}*16+o)&0xfffffu;}
    uint16_t word(uint16_t s,uint16_t o) const {
        const auto a=at(s,o);return static_cast<uint16_t>(bytes[a]|(uint16_t{bytes[(a+1u)&0xfffffu]}<<8));
    }
    void store(uint16_t s,uint16_t o,uint16_t value) {
        const auto a=at(s,o);bytes[a]=static_cast<uint8_t>(value);
        bytes[(a+1u)&0xfffffu]=static_cast<uint8_t>(value>>8);++writes;
    }
    TimerIrqBus bus() {
        return {
            [&](uint16_t s,uint16_t o){return bytes[at(s,o)];},
            [&](uint16_t s,uint16_t o){return word(s,o);},
            [&](uint16_t s,uint16_t o){return uint32_t{word(s,o)}|(uint32_t{word(s,static_cast<uint16_t>(o+2u))}<<16);},
            [&](uint16_t s,uint16_t o,uint8_t value){bytes[at(s,o)]=value;++writes;},
            [&](uint16_t s,uint16_t o,uint16_t value){store(s,o,value);},
            [&](uint16_t s,uint16_t o,uint32_t value){store(s,o,static_cast<uint16_t>(value));store(s,static_cast<uint16_t>(o+2u),static_cast<uint16_t>(value>>16));},
            [](uint16_t)->uint8_t{throw std::runtime_error("Active natural profile has no external port reads");},
            [&](uint16_t port,uint8_t value){
#ifdef LEZAC_TEST_FRAME_ITERATION
                if(port==0x3c8 || port==0x3c9) {
                    clock->chargePortWrite();
                    dac.write(port,value,[&](uint8_t index,uint8_t red,uint8_t green,uint8_t blue) {
                        devices->setPaletteColor(index,red,green,blue);
                    });
                    ++dacWrites;return;
                }
#endif
                require(port==0x20 && value==0x20,"Active natural profile has non-EOI output");
                clock->chargePortWrite();clock->nonspecificMasterEoi();++outputs;
            }
        };
    }
};
struct CpuState {DosGetTimeRegisters r;uint32_t mask;std::vector<uint8_t> opcode;};
void replay(const char* cpu,const char* device,const char* dump) {
    const auto observedClocks=clocks(device);Reader reader(cpu);
    require(reader.take(8)==std::vector<uint8_t>(LiveMagic,LiveMagic+8),"Active natural projection version differs");
    const auto count=reader.number(4);require(count==observedClocks.size(),"Active CPU/clock cases differ");
    uint64_t comparisons=0,irqs=0,renderIrqs=0;
    for(unsigned c=0;c<count;++c) {
        const auto game=reader.word(),dos=reader.word(),keyboard=reader.word(),psp=reader.word();
        const auto idToggle=reader.number(4),size=reader.number(4);
        require(size==observedClocks[c].size() && size>1 && size<=LiveStateLimit,"Active natural state count differs");
        const auto initial=reader.take(1048576),expectedMemory=reader.take(1048576);
        std::vector<CpuState> states;states.reserve(size);
        for(unsigned i=0;i<size;++i) {
            const auto r=registers(reader);const auto mask=reader.number(4);
            states.push_back({r,mask,reader.take(8)});
        }
        for(bool restore:{false,true}) {
            Memory memory{initial};PacingDeviceClock clock(observedClocks[c][0]);memory.clock=&clock.workClock();memory.devices=&clock;
            LiveOperation operation(states[0].r,dos,keyboard,psp,game,idToggle);const auto bus=memory.bus();
            uint64_t delivered=0,renderDelivered=0,dispatched=0,completedFrames=0;
            const auto before=operation.snapshot();
            require(operation.advance(0,bus,[](uint16_t)->uint16_t{throw std::runtime_error("Zero active budget requested REP");})==0 &&
                operation.snapshot()==before && !memory.writes,"Zero active budget changed state");
            for(unsigned step=0;step<size;++step) {
                const auto context="Active case="+std::to_string(c)+" state="+std::to_string(step);
                compare(clock.snapshot(),observedClocks[c][step],context);
                auto actual=operation.registers(),expected=states[step].r;
                require(((actual.flags^expected.flags)&states[step].mask)==0,context+" flags differ");
                actual.flags=expected.flags=0;require(actual==expected,context+" CPU differs ip="+std::to_string(actual.ip));
                for(unsigned byte=0;byte<8;++byte) require(memory.bytes[Memory::at(actual.cs,static_cast<uint16_t>(actual.ip+byte))]==
                    states[step].opcode[byte],context+" unchanged original instruction differs");
                ++comparisons;
                if(step+1==size) break;
                const auto r=operation.registers();const bool timer=operation.interruptInProgress();
                const bool callback=r.cs==0xf000 && (timer?r.ip==0xfea5:r.ip==dos+1u || r.ip==keyboard+1u);
                const bool iret=timer?((r.cs==0xf000 && r.ip==0xfeb6)||(r.cs==game && r.ip==0x1090)):
                    r.cs==0xf000 && (r.ip==dos+14u || r.ip==keyboard+5u);
                require(operation.advance(1,bus,[&](uint16_t n){return clock.workClock().chargeStringTransfers(n);})==1,
                    context+" active operation did not dispatch");
                ++dispatched;
#ifdef LEZAC_TEST_FRAME_ITERATION
                if (operation.finished()) {
                    require(terminal(operation),context+" full iteration left the next-frame path");
                    ++completedFrames;
                    if (step+2<size) {
                        require(completedFrames<4,context+" too many full frames");
                        // Continue solely from computed registers, retaining memory and device state.
                        operation=LiveOperation(operation.registers(),dos,keyboard,psp,game,idToggle);
                    }
                }
#endif
                const auto flags=operation.registers().flags;
                const bool sti=r.cs==0xf000 && (r.ip==dos || r.ip==keyboard);
                auto boundary=clock.nextDispatch(callback||((iret||sti)&&(flags&0x200u)&&clock.workClock().snapshot().pending),flags);
                while(boundary.kind==PicClockBoundaryKind::NeedMillisecond) {
                    clock.grantMillisecond();boundary=clock.nextDispatch(false,flags);
                }
                require(boundary.kind==PicClockBoundaryKind::Ready,context+" unsupported computed clock boundary");
                if(boundary.timerDelivered) {
                    renderDelivered+=renderInProgress(operation);
                    operation.deliverTimerInterrupt(bus);++delivered;
                }
                if(restore) {
                    operation=LiveOperation(operation.snapshot());clock=PacingDeviceClock(clock.snapshot());memory.clock=&clock.workClock();
                    memory.dac=VgaDacWriter(memory.dac.snapshot());
                }
            }
            require(terminal(operation) && dispatched==size-1,"Active natural terminal differs");
#ifdef LEZAC_TEST_FRAME_ITERATION
            require(completedFrames==4,"Continuous full-frame count differs");
#else
            require(operation.snapshot().timerDeliveries==delivered,"Active IRQ delivery accounting differs");
            (void)completedFrames;
#endif
            require(memory.outputs==delivered,"Active IRQ/EOI accounting differs");
            if(memory.bytes!=expectedMemory) {
                const auto mismatch=std::mismatch(memory.bytes.begin(),memory.bytes.end(),expectedMemory.begin());
                throw std::runtime_error("Active complete final memory differs case="+std::to_string(c)+" address="+
                    std::to_string(mismatch.first-memory.bytes.begin())+" actual="+std::to_string(*mismatch.first)+
                    " expected="+std::to_string(*mismatch.second));
            }
            if(dump && !restore) {
#ifdef LEZAC_TEST_FRAME_ITERATION
                const auto path=std::string(dump)+".rgb";
                require(!outputEntryExists(path),"Full-frame visual output already exists");
                const auto palette=clock.snapshot().palette;
                require(palette.has_value(),"Full-frame palette is absent");
                std::ofstream output(path,std::ios::binary);
                for(unsigned pixel=0;pixel<64000;++pixel) {
                    const auto rgb=palette->rgb[memory.bytes[0xa0000+pixel]];
                    for(unsigned shift:{16u,8u,0u}) output.put(static_cast<char>(rgb>>shift));
                }
                require(output.good(),"Full-frame RGB output failed");
#else
                const auto path=std::string(dump)+"-"+std::to_string(c)+".ram";
                const auto palettePath=std::string(dump)+"-"+std::to_string(c)+".pal";
                require(!outputEntryExists(path) && !outputEntryExists(palettePath),"Active output already exists");
                std::ofstream output(path,std::ios::binary);
                output.write(reinterpret_cast<const char*>(memory.bytes.data()),static_cast<std::streamsize>(memory.bytes.size()));
                require(output.good(),"Active RAM dump failed");
                const auto palette=clock.snapshot().palette;
                require(palette.has_value(),"Active palette is absent");
                std::ofstream paletteOutput(palettePath,std::ios::binary);
                for(const auto rgb:palette->rgb) for(unsigned shift:{16u,8u,0u})
                    paletteOutput.put(static_cast<char>(rgb>>shift));
                require(paletteOutput.good(),"Active palette dump failed");
#endif
            }
            irqs+=delivered;renderIrqs+=renderDelivered;
        }
    }
    require(reader.stream.get()<0,"Active CPU projection tail differs");
    require(irqs && renderIrqs,"Active capture missed natural render-time IRQs");
    std::cout<<LiveResult<<"=ok cases="<<count<<" comparisons="<<comparisons<<" predicted_irqs="<<irqs<<
        " render_irqs="<<renderIrqs<<" complete_memory_bytes="<<uint64_t{count}*2*1048576<<
        " later_state_injected=0 actual_app_integration=0 whole_game_parity=0\n";
}
}
int main(int argc,char** argv) {
    try {
#ifdef LEZAC_TEST_FRAME_ITERATION
        require(argc==3 || argc==4,"Expected stream-only full-frame projections and optional RGB prefix");
#else
        require(argc==3 || argc==4,"Expected active CPU/clock projections and optional RAM prefix");
#endif
        replay(argv[1],argv[2],argc==4?argv[3]:nullptr);return 0;}
    catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
