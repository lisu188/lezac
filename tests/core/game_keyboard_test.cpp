#include "core/game_keyboard.hpp"

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
DosGetTimeRegisters entry() { return {0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x9abc,0x1000,0x1aa2,0xbeef,0x8000,0xfe00,0x7a00,0x202}; }
void unit() {
    struct Case { std::vector<uint16_t> keys; uint8_t pending; std::vector<uint8_t> writes; };
    const std::vector<Case> cases={{{},0,{}},{{0x1e61},0,{'a'}},{{0x4b00},0,{0,0x4b}},
        {{0x1e61,0x3062},0,{'a','b'}},{{0x8500,0x1e61},0,{'a'}},{{0},0,{3}},{{0xe00d},0,{13}},
        {{0x4be0},0,{0,0x4b}},{{},0x4b,{0x4b}},{{0x8500},0,{}}};
    unsigned boundaries=0,masked=0;
    for(const auto& test:cases) {
        const auto initialize=[&](Memory& memory) { memory.keys(test.keys,0x3c); memory.byte(0x1aa2,0x7f6d,test.pending); };
        Memory baseline; initialize(baseline);
        GameKeyboardOperation expected(entry(),0x1200,0x1000,0x200000); expected.advance(8192,baseline.bus());
        require(expected.returned() && expected.registers().cs==0x1000 && expected.registers().ip==0x7a13 &&
            expected.registers().sp==0xfe00 && baseline.writes==test.writes &&
            baseline.read(0x1aa2,0x2058)==(test.writes.empty()?0xa7:test.writes.back()) &&
            baseline.read(0x1aa2,0x7f6d)==0 && baseline.word(0x40,0x1a)==baseline.word(0x40,0x1c) &&
            expected.snapshot().reads==test.writes.size() && expected.snapshot().polls==test.writes.size()+1,
            "Game drain did not preserve last-byte ownership, prefix order, queue, stack or work");
        const auto work=expected.snapshot().dispatchedInstructions;
        for(uint64_t boundary=0;boundary<=work;++boundary) {
            Memory memory; initialize(memory); const auto bus=memory.bus();
            GameKeyboardOperation operation(entry(),0x1200,0x1000,0x200000);
            require(operation.advance(boundary,bus)==boundary,"Drain pre-IRQ work differs");
            const auto old=operation.snapshot(); require(operation.advance(0,bus)==0 && operation.snapshot()==old,"Zero drain budget changed state");
            if(!(operation.registers().flags&0x200u)) {
                const auto oldMemory=memory.bytes; bool rejected=false;
                try {operation.deliverTimerInterrupt(bus);} catch(const std::logic_error&) {rejected=true;}
                require(rejected && operation.snapshot()==old && memory.bytes==oldMemory,"Masked drain IRQ changed state");
                ++masked; continue;
            }
            operation.deliverTimerInterrupt(bus);
            while(!operation.finished()) {
                require(operation.advance(1,bus)==1,"Drain IRQ did not dispatch"); operation=GameKeyboardOperation(operation.snapshot());
            }
            require(operation.returned() && operation.registers()==expected.registers() && memory.writes==baseline.writes &&
                memory.word(0x40,0x1a)==baseline.word(0x40,0x1a) && memory.read(0x1aa2,0x7f6d)==0 && memory.word(0x40,0x6c)==101 &&
                operation.snapshot().dispatchedInstructions==work+36 && operation.snapshot().timerInstructions==36 &&
                operation.snapshot().timerDeliveries==1 && operation.snapshot().reads==expected.snapshot().reads &&
                operation.snapshot().polls==expected.snapshot().polls,"IRQ changed drain return, byte sequence or exact work");
            ++boundaries;
        }
    }
    Memory breaking; breaking.byte(0x1aa2,0x7f6d,1); breaking.byte(0x1aa2,0x7f6e,1); breaking.keys({0x1e61});
    GameKeyboardOperation flush(entry(),0x1200,0x1000,0x200000); flush.advance(8192,breaking.bus());
    require(flush.finished() && !flush.returned() && flush.snapshot().outcome==GameKeyboardOutcome::BreakOutput &&
        flush.registers().ip==0x15c && breaking.writes.empty(),"Break handoff incorrectly continued the game drain");
    std::cout<<"game_keyboard_unit=ok cases="<<cases.size()<<" timer_boundaries="<<boundaries<<" masked_boundaries="<<masked
        <<" extended_prefix_order=1 last_byte_preserved_when_empty=1 snapshot_restore=1\n";
}
struct Reader {
    std::ifstream stream;
    explicit Reader(const char* path):stream(path,std::ios::binary) {require(stream.good(),"Drain projection is missing");}
    uint32_t number(unsigned size) {
        uint32_t value=0; for(unsigned i=0;i<size;++i) {const int byte=stream.get();require(byte>=0,"Truncated drain projection");value|=uint32_t(byte)<<(8*i);} return value;
    }
    uint16_t word() {return static_cast<uint16_t>(number(2));}
    std::vector<uint8_t> take(unsigned size) {std::vector<uint8_t> data;for(unsigned i=0;i<size;++i)data.push_back(static_cast<uint8_t>(number(1)));return data;}
};
void original(const char* path) {
    Reader reader(path); require(reader.take(8)==std::vector<uint8_t>({'L','Z','G','K','E','Y','0','1'}),"Drain projection version differs");
    const auto count=reader.number(4);require(count==3,"Drain case domain differs");uint64_t comparisons=0,reads=0;
    struct State {DosGetTimeRegisters r;uint32_t mask,io;std::vector<uint8_t> stack,crt,bios,sound,last;};
    for(unsigned caseIndex=0;caseIndex<count;++caseIndex) {
        const auto game=reader.word(),base=reader.word(),ss=reader.word(),stackBase=reader.word(),entryIp=reader.word();
        const auto bankSegment=reader.word(),bankOffset=reader.word(),bankLength=reader.word();
        const auto stateCount=reader.number(4),ioCount=reader.number(4),irqCount=reader.number(4);
        require(stateCount>1 && stateCount<=8193 && bankLength==780 && irqCount<stateCount,"Drain observation scope differs");
        std::vector<uint32_t> deliveries;for(unsigned i=0;i<irqCount;++i)deliveries.push_back(reader.number(4));
        const auto bank=reader.take(bankLength);std::vector<State> states;
        for(unsigned i=0;i<stateCount;++i) {
            DosGetTimeRegisters r;
            r.ax=reader.word();r.bx=reader.word();r.cx=reader.word();r.dx=reader.word();r.si=reader.word();r.di=reader.word();r.bp=reader.word();
            r.cs=reader.word();r.ds=reader.word();r.es=reader.word();r.ss=reader.word();r.sp=reader.word();r.ip=reader.word();r.flags=reader.number(4);
            const auto mask=reader.number(4),io=reader.number(4);
            states.push_back({r,mask,io,reader.take(128),reader.take(2),reader.take(132),reader.take(10),reader.take(1)});
        }
        std::vector<std::tuple<bool,uint16_t,uint8_t>> events;
        for(unsigned i=0;i<ioCount;++i){const bool output=reader.number(1)!=0;const auto port=reader.word();events.emplace_back(output,port,static_cast<uint8_t>(reader.number(1)));}
        for(bool restore:{false,true}) {
            Memory memory(false);memory.script=events;const auto data=static_cast<uint16_t>(game+0xaa2);
            const auto seed=[&](uint16_t s,uint16_t o,const std::vector<uint8_t>& bytes){for(unsigned i=0;i<bytes.size();++i)memory.byte(s,static_cast<uint16_t>(o+i),bytes[i]);};
            seed(ss,stackBase,states[0].stack);seed(0x40,0,states[0].bios);seed(data,0x7f6d,states[0].crt);seed(data,0x2058,states[0].last);
            seed(bankSegment,bankOffset,bank);memory.word(0,0x58,base);memory.word(0,0x5a,0xf000);memory.word(0,0x70,0x0fbe);memory.word(0,0x72,game);
            unsigned sound=0;
            for(auto [offset,length]:{std::pair{0x78c0,2},std::pair{0x79a0,3},std::pair{0x79c0,5}})
                for(int i=0;i<length;++i)memory.byte(data,static_cast<uint16_t>(offset+i),states[0].sound[sound++]);
            memory.strict=true; require(entryIp==0x7a00 && states[0].r.ip==entryIp,"Drain entry metadata differs");
            GameKeyboardOperation operation(states[0].r,base,game,0x200000);
            for(unsigned step=0;step<stateCount;++step) {
                if(std::find(deliveries.begin(),deliveries.end(),step)!=deliveries.end())operation.deliverTimerInterrupt(memory.bus());
                auto actual=operation.registers(),expected=states[step].r;const auto context="drain case="+std::to_string(caseIndex)+" state="+std::to_string(step);
                require(((actual.flags^expected.flags)&states[step].mask)==0,context+" control flags differ");actual.flags=expected.flags=0;
                require(actual==expected,context+" CPU differs ip="+std::to_string(actual.ip));require(memory.io==states[step].io,context+" I/O count differs");
                for(unsigned i=0;i<128;++i)require(memory.read(ss,static_cast<uint16_t>(stackBase+i))==states[step].stack[i],context+" stack differs");
                for(unsigned i=0;i<132;++i)require(memory.read(0x40,static_cast<uint16_t>(i))==states[step].bios[i],context+" BIOS memory differs");
                for(unsigned i=0;i<2;++i)require(memory.read(data,static_cast<uint16_t>(0x7f6d+i))==states[step].crt[i],context+" CRT memory differs");
                require(memory.read(data,0x2058)==states[step].last[0],context+" last-key byte differs");sound=0;
                for(auto [offset,length]:{std::pair{0x78c0,2},std::pair{0x79a0,3},std::pair{0x79c0,5}})
                    for(int i=0;i<length;++i)require(memory.read(data,static_cast<uint16_t>(offset+i))==states[step].sound[sound++],context+" sound memory differs");
                ++comparisons;
                const auto old=operation.snapshot();require(operation.advance(0,memory.bus())==0 && operation.snapshot()==old,"Zero drain budget changed state");
                if(step+1<stateCount)require(operation.advance(1,memory.bus())==1,"Drain dispatch work differs");
                if(restore)operation=GameKeyboardOperation(operation.snapshot());
            }
            require(operation.returned() && operation.snapshot().dispatchedInstructions==stateCount-1 && memory.io==ioCount,"Drain terminal/work differs");
            reads+=operation.snapshot().reads;
        }
    }
    require(reader.stream.get()<0,"Drain projection tail differs");
    std::cout<<"game_keyboard_original=ok cases="<<count<<" comparisons="<<comparisons<<" reads="<<reads
        <<" restore_modes=2 later_state_injected=0 irq_eligibility_claim=0\n";
}
}
int main(int argc,char** argv) {
    try {
        unit();
        if(argc==3 && std::string(argv[1])=="--original")original(argv[2]);
        else require(argc==1,"Expected --original projection");
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
