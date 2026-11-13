#include "core/crt_keyboard.hpp"

#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool value,const std::string& message) {if(!value) throw std::runtime_error(message);}
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576);
    std::vector<uint8_t> known=std::vector<uint8_t>(1048576);
    std::vector<std::tuple<bool,uint16_t,uint8_t>> script;
    std::size_t io=0;
    bool strict=false;
    static uint32_t at(uint16_t s,uint16_t o) {return (uint32_t{s}*16+o)&0xfffff;}
    uint8_t read(uint16_t s,uint16_t o) const {require(!strict || known[at(s,o)],"Read outside original keyboard input");return bytes[at(s,o)];}
    uint16_t word(uint16_t s,uint16_t o) const {return static_cast<uint16_t>(read(s,o)|(uint16_t{read(s,static_cast<uint16_t>(o+1u))}<<8));}
    void byte(uint16_t s,uint16_t o,uint8_t v) {
        require(!strict || known[at(s,o)],"Write outside original keyboard ownership");bytes[at(s,o)]=v;known[at(s,o)]=1;
    }
    void word(uint16_t s,uint16_t o,uint16_t v) {byte(s,o,static_cast<uint8_t>(v));byte(s,static_cast<uint16_t>(o+1u),static_cast<uint8_t>(v>>8));}
    explicit Memory(bool defaults=true) {
        if(!defaults) return;
        word(0,0x58,0x1200);word(0,0x5a,0xf000);
        word(0,0x70,0x0fbe);word(0,0x72,0x1000);
        word(0x40,0x80,0x1e);word(0x40,0x82,0x3e);
        word(0x40,0x1a,0x1e);word(0x40,0x1c,0x1e);
        word(0x8000,0xfe00,0x7a05);word(0x8000,0xfe02,0x1000);
        word(0x40,0x6c,100);byte(0x40,0x40,2);byte(0x40,0x3f,0xa5);
    }
    void keys(const std::vector<uint16_t>& keys,uint16_t head=0x1e) {
        word(0x40,0x1a,head);
        auto tail=head;
        for(auto key:keys) {word(0x40,tail,key);tail=static_cast<uint16_t>(tail+2u);if(tail>=0x3e) tail=0x1e;}
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
                require(p==0x61,"Unexpected keyboard IRQ input");
                if(!strict) return uint8_t{0};
                require(io<script.size() && !std::get<0>(script[io]) && std::get<1>(script[io])==p,"Original keyboard input order differs");
                return std::get<2>(script[io++]);
            },
            [&](uint16_t p,uint8_t v){
                require(p==0x20 || p==0x61,"Unexpected keyboard IRQ output");
                if(strict) require(io<script.size() && script[io++]==std::tuple{true,p,v},"Original keyboard output order differs");
            }
        };
    }
};
DosGetTimeRegisters entry(uint16_t ip) {
    return {0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x9abc,0x184a,0x1aa2,0xbeef,0x8000,0xfe00,ip,0x202};
}
void unit() {
    unsigned boundaries=0,masked=0;
    for(unsigned profile=0;profile<7;++profile) {
        const uint16_t ip=profile<3?0x2fd:0x30f;
        Memory baseline;
        if(profile==1 || profile==3) baseline.keys({0x1e61});
        if(profile==2 || profile==4) baseline.byte(0x1aa2,0x7f6d,0x4b);
        if(profile==5) baseline.keys({0x4b00});
        if(profile==6) baseline.keys({0});
        CrtKeyboardOperation expected(entry(ip),0x1200,0x1000,0x200000);
        expected.advance(1024,baseline.bus());require(expected.returned() && expected.registers().cs==0x1000 &&
            expected.registers().ip==0x7a05 && expected.registers().sp==0xfe04,"CRT keyboard unit did not return with its far context");
        const auto result=static_cast<uint8_t>(expected.registers().ax);
        require(result==std::array<uint8_t,7>{0,1,1,'a',0x4b,0,3}[profile],"CRT keyboard result differs");
        const auto work=expected.snapshot().dispatchedInstructions;
        for(uint64_t boundary=0;boundary<=work;++boundary) {
            Memory memory;
            if(profile==1 || profile==3) memory.keys({0x1e61});
            if(profile==2 || profile==4) memory.byte(0x1aa2,0x7f6d,0x4b);
            if(profile==5) memory.keys({0x4b00});
            if(profile==6) memory.keys({0});
            CrtKeyboardOperation operation(entry(ip),0x1200,0x1000,0x200000);
            const auto bus=memory.bus();require(operation.advance(boundary,bus)==boundary,"Keyboard pre-IRQ work differs");
            if(!(operation.registers().flags&0x200u)) {
                const auto old=operation.snapshot();const auto oldMemory=memory.bytes;bool rejected=false;
                try {operation.deliverTimerInterrupt(bus);} catch(const std::logic_error&) {rejected=true;}
                require(rejected && operation.snapshot()==old && memory.bytes==oldMemory,"Masked keyboard IRQ changed state");
                ++masked;continue;
            }
            operation.deliverTimerInterrupt(bus);
            while(!operation.finished()) {
                require(operation.advance(1,bus)==1,"Keyboard IRQ did not dispatch");
                operation=CrtKeyboardOperation(operation.snapshot());
            }
            require(operation.returned() && operation.registers()==expected.registers() &&
                memory.word(0x40,0x1a)==baseline.word(0x40,0x1a) && memory.word(0x40,0x1c)==baseline.word(0x40,0x1c) &&
                memory.read(0x1aa2,0x7f6d)==baseline.read(0x1aa2,0x7f6d) && memory.word(0x40,0x6c)==101 &&
                operation.snapshot().timerInstructions==36 && operation.snapshot().dispatchedInstructions==work+36,
                "Keyboard IRQ changed return context, queue, pending byte or work");
            ++boundaries;
        }
    }
    Memory enhanced;enhanced.keys({0x8500,0x1ef0,0xe00d},0x3a);
    CrtKeyboardOperation status(entry(0x2fd),0x1200,0x1000,0x200000);status.advance(1024,enhanced.bus());
    require(status.returned() && status.registers().ax==0x1c01 && enhanced.word(0x40,0x1a)==0x1e,
        "Enhanced discard, ring wrap or numpad translation differs");
    Memory waiting;CrtKeyboardOperation read(entry(0x30f),0x1200,0x1000,0x200000);
    require(read.advance(64,waiting.bus())==64 && !read.finished() && read.snapshot().biosCallbacks==5 && read.snapshot().lastBiosReadEmpty &&
        read.registers().cs==0xf000 && read.registers().ip==0x1206,
        "Empty ReadKey did not execute original BIOS idle loop");
    waiting.keys({0x3062});read.advance(1024,waiting.bus());
    require(read.returned() && static_cast<uint8_t>(read.registers().ax)=='b',"ReadKey did not resume after a declared queue input");
    Memory breaking;breaking.byte(0x1aa2,0x7f6d,1);breaking.byte(0x1aa2,0x7f6e,1);breaking.keys({0x1e61,0x3062});
    CrtKeyboardOperation flush(entry(0x30f),0x1200,0x1000,0x200000);flush.advance(1024,breaking.bus());
    require(flush.finished() && !flush.returned() && flush.snapshot().outcome==CrtKeyboardOutcome::BreakOutput &&
        flush.registers().ip==0x15c && breaking.word(0x40,0x1a)==breaking.word(0x40,0x1c) &&
        breaking.read(0x1aa2,0x7f6e)==0,"Ctrl-Break queue flush/handoff differs");
    for(unsigned pending=1;pending<256;++pending) {
        Memory statusMemory,readMemory;
        statusMemory.byte(0x1aa2,0x7f6d,static_cast<uint8_t>(pending));
        readMemory.byte(0x1aa2,0x7f6d,static_cast<uint8_t>(pending));
        CrtKeyboardOperation pendingStatus(entry(0x2fd),0x1200,0x1000,0x200000),pendingRead(entry(0x30f),0x1200,0x1000,0x200000);
        pendingStatus.advance(64,statusMemory.bus());pendingRead.advance(64,readMemory.bus());
        require(pendingStatus.returned() && static_cast<uint8_t>(pendingStatus.registers().ax)==1 &&
            pendingRead.returned() && static_cast<uint8_t>(pendingRead.registers().ax)==pending &&
            readMemory.read(0x1aa2,0x7f6d)==0 && pendingRead.snapshot().biosCallbacks==0,
            "Pending extended-byte domain differs");
    }
    auto maskedEntry=entry(0x2fd);maskedEntry.flags&=~uint32_t{0x200};Memory statusIf;
    CrtKeyboardOperation enablesIf(maskedEntry,0x1200,0x1000,0x200000);enablesIf.advance(64,statusIf.bus());
    require(enablesIf.returned() && (enablesIf.registers().flags&0x200u),"BIOS KeyPressed did not enable IF on return");
    maskedEntry.ip=0x30f;Memory readIf;readIf.keys({0x1e61});
    CrtKeyboardOperation preservesIf(maskedEntry,0x1200,0x1000,0x200000);preservesIf.advance(64,readIf.bus());
    require(preservesIf.returned() && !(preservesIf.registers().flags&0x200u),"BIOS ReadKey changed the caller's masked IF");
    std::cout<<"crt_keyboard_unit=ok timer_boundaries="<<boundaries<<" masked_boundaries="<<masked
        <<" bios_idle_resume=1 enhanced_discard=1 ring_wrap=1 break_output_handoff=1 pending_byte_inputs=255 snapshot_restore=1\n";
}
void classification(const char* path) {
    std::ifstream stream(path,std::ios::binary);require(stream.good(),"Classification corpus missing");
    for(unsigned value=0;value<65536;++value) {
        const auto enhanced=stream.get(),low=stream.get(),high=stream.get();require(enhanced>=0 && low>=0 && high>=0,"Classification truncated");
        auto key=static_cast<uint16_t>(value);const bool actual=CrtKeyboardOperation::enhancedKey(key);
        require(actual==(enhanced!=0) && key==static_cast<uint16_t>(low|(high<<8)),"Original BIOS classification differs");
    }
    require(stream.get()<0,"Classification tail differs");
    std::cout<<"bios_keyboard_classification=ok inputs=65536 original_source_function=1\n";
}
struct Reader {
    std::ifstream stream;
    explicit Reader(const char* path):stream(path,std::ios::binary) {require(stream.good(),"Keyboard projection missing");}
    uint32_t number(unsigned size) {
        uint32_t value=0;
        for(unsigned i=0;i<size;++i) {const auto byte=stream.get();require(byte>=0,"Keyboard projection truncated");value|=uint32_t{static_cast<uint8_t>(byte)}<<(8*i);}
        return value;
    }
    uint16_t word() {return static_cast<uint16_t>(number(2));}
    std::vector<uint8_t> take(unsigned size) {std::vector<uint8_t> data;for(unsigned i=0;i<size;++i) data.push_back(static_cast<uint8_t>(number(1)));return data;}
};
void pendingOracle(const char* path) {
    Reader reader(path);require(reader.take(8)==std::vector<uint8_t>({'L','Z','C','K','O','R','0','1'}),"Pending oracle version differs");
    require(reader.number(4)==510,"Pending oracle domain differs");
    for(unsigned index=0;index<510;++index) {
        const auto ip=reader.word();const auto pending=reader.number(1),flags=reader.number(4),work=reader.number(4);
        require(ip==(index<255?0x2fd:0x30f) && pending==index%255+1 && work==(index<255?4u:9u),"Pending oracle input sequence differs");
        DosGetTimeRegisters expected;
        expected.ax=reader.word();expected.bx=reader.word();expected.cx=reader.word();expected.dx=reader.word();
        expected.si=reader.word();expected.di=reader.word();expected.bp=reader.word();expected.cs=reader.word();
        expected.ds=reader.word();expected.es=reader.word();expected.ss=reader.word();expected.sp=reader.word();expected.ip=reader.word();expected.flags=reader.number(4);
        const auto stack=reader.take(128),crt=reader.take(2);
        Memory memory;
        for(unsigned i=0;i<128;++i) memory.byte(0x8000,static_cast<uint16_t>(0xfdb0+i),static_cast<uint8_t>(pending+i));
        memory.word(0x8000,0xfe00,0x7a05);memory.word(0x8000,0xfe02,0x1000);
        memory.byte(0x1aa2,0x7f6d,static_cast<uint8_t>(pending));
        auto input=entry(ip);input.flags=flags;
        CrtKeyboardOperation operation(input,0x1200,0x1000,0x200000);operation.advance(64,memory.bus());
        require(operation.returned() && operation.registers()==expected && operation.snapshot().dispatchedInstructions==work &&
            operation.snapshot().biosCallbacks==0,"Original pending-byte CPU or work differs");
        for(unsigned i=0;i<128;++i) require(memory.read(0x8000,static_cast<uint16_t>(0xfdb0+i))==stack[i],"Original pending-byte stack differs");
        require(memory.read(0x1aa2,0x7f6d)==crt[0] && memory.read(0x1aa2,0x7f6e)==crt[1],"Original pending-byte globals differ");
    }
    require(reader.stream.get()<0,"Pending oracle tail differs");
    std::cout<<"crt_keyboard_pending_oracle=ok cases=510 pending_inputs=255 original_calls_stubbed=0 full_endpoint_flags=1\n";
}
void original(const char* path) {
    Reader reader(path);require(reader.take(8)==std::vector<uint8_t>({'L','Z','C','K','E','Y','0','1'}),"Keyboard projection version differs");
    const auto count=reader.number(4);require(count>0 && count<=12,"Keyboard case domain differs");uint64_t comparisons=0;
    struct State {DosGetTimeRegisters r;uint32_t mask,io;std::vector<uint8_t> stack,crt,bios,sound;};
    for(unsigned caseIndex=0;caseIndex<count;++caseIndex) {
        const auto game=reader.word(),base=reader.word(),ss=reader.word(),stackBase=reader.word(),entryIp=reader.word();
        const auto bankSegment=reader.word(),bankOffset=reader.word(),bankLength=reader.word();
        const auto stateCount=reader.number(4),ioCount=reader.number(4),irqCount=reader.number(4);
        require(stateCount>1 && stateCount<=8193 && bankLength==780 && irqCount<stateCount,"Keyboard observation scope differs");
        std::vector<uint32_t> deliveries;for(unsigned i=0;i<irqCount;++i) deliveries.push_back(reader.number(4));
        const auto bank=reader.take(bankLength);std::vector<State> states;
        for(unsigned i=0;i<stateCount;++i) {
            DosGetTimeRegisters r;
            r.ax=reader.word();r.bx=reader.word();r.cx=reader.word();r.dx=reader.word();r.si=reader.word();r.di=reader.word();r.bp=reader.word();
            r.cs=reader.word();r.ds=reader.word();r.es=reader.word();r.ss=reader.word();r.sp=reader.word();r.ip=reader.word();r.flags=reader.number(4);
            const auto mask=reader.number(4),io=reader.number(4);
            states.push_back({r,mask,io,reader.take(128),reader.take(2),reader.take(132),reader.take(10)});
        }
        std::vector<std::tuple<bool,uint16_t,uint8_t>> events;
        for(unsigned i=0;i<ioCount;++i) {const bool output=reader.number(1)!=0;const auto port=reader.word();events.emplace_back(output,port,static_cast<uint8_t>(reader.number(1)));}
        for(bool restore:{false,true}) {
            Memory memory(false);memory.script=events;const auto data=static_cast<uint16_t>(game+0xaa2);
            const auto seed=[&](uint16_t s,uint16_t o,const std::vector<uint8_t>& bytes) {for(unsigned i=0;i<bytes.size();++i) memory.byte(s,static_cast<uint16_t>(o+i),bytes[i]);};
            seed(ss,stackBase,states[0].stack);seed(0x40,0,states[0].bios);seed(data,0x7f6d,states[0].crt);
            seed(bankSegment,bankOffset,bank);memory.word(0,0x58,base);memory.word(0,0x5a,0xf000);
            memory.word(0,0x70,0x0fbe);memory.word(0,0x72,game);
            unsigned sound=0;
            for(auto [offset,length]:{std::pair{0x78c0,2},std::pair{0x79a0,3},std::pair{0x79c0,5}})
                for(int i=0;i<length;++i) memory.byte(data,static_cast<uint16_t>(offset+i),states[0].sound[sound++]);
            memory.strict=true;
            require(states[0].r.ip==entryIp,"Keyboard entry metadata differs");
            CrtKeyboardOperation operation(states[0].r,base,game,0x200000);
            for(unsigned step=0;step<stateCount;++step) {
                if(std::find(deliveries.begin(),deliveries.end(),step)!=deliveries.end()) operation.deliverTimerInterrupt(memory.bus());
                auto actual=operation.registers(),expected=states[step].r;const auto context="keyboard case="+std::to_string(caseIndex)+" state="+std::to_string(step);
                require(((actual.flags^expected.flags)&states[step].mask)==0,context+" control flags differ");actual.flags=expected.flags=0;
                require(actual==expected,context+" CPU differs ip="+std::to_string(actual.ip));require(memory.io==states[step].io,context+" I/O count differs");
                for(unsigned i=0;i<128;++i) require(memory.read(ss,static_cast<uint16_t>(stackBase+i))==states[step].stack[i],context+" stack differs");
                for(unsigned i=0;i<132;++i) require(memory.read(0x40,static_cast<uint16_t>(i))==states[step].bios[i],context+" BIOS memory differs");
                for(unsigned i=0;i<2;++i) require(memory.read(data,static_cast<uint16_t>(0x7f6d+i))==states[step].crt[i],context+" CRT memory differs");
                sound=0;
                for(auto [offset,length]:{std::pair{0x78c0,2},std::pair{0x79a0,3},std::pair{0x79c0,5}})
                    for(int i=0;i<length;++i) require(memory.read(data,static_cast<uint16_t>(offset+i))==states[step].sound[sound++],context+" sound memory differs");
                ++comparisons;
                const auto old=operation.snapshot();require(operation.advance(0,memory.bus())==0 && operation.snapshot()==old,"Zero keyboard budget changed state");
                if(step+1<stateCount) require(operation.advance(1,memory.bus())==1,"Keyboard dispatch work differs");
                if(restore) operation=CrtKeyboardOperation(operation.snapshot());
            }
            require(operation.returned() && operation.snapshot().dispatchedInstructions==stateCount-1 && memory.io==ioCount,
                "Keyboard terminal/work differs");
        }
    }
    require(reader.stream.get()<0,"Keyboard projection tail differs");
    std::cout<<"crt_keyboard_original=ok cases="<<count<<" comparisons="<<comparisons<<" restore_modes=2 later_state_injected=0 irq_eligibility_claim=0\n";
}
}
int main(int argc,char** argv) {
    try {
        unit();
        if(argc==3 && std::string(argv[1])=="--classification") classification(argv[2]);
        else if(argc==3 && std::string(argv[1])=="--original") original(argv[2]);
        else if(argc==3 && std::string(argv[1])=="--pending-oracle") pendingOracle(argv[2]);
        else require(argc==1,"Expected --classification projection");
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
