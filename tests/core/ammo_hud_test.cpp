#include "core/frame_hud.hpp"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool value,const char* message){if(!value)throw std::runtime_error(message);}
std::vector<uint8_t> readFile(const char* path) {
    std::ifstream in(path,std::ios::binary);require(in.good(),"Cannot read ammunition HUD input");
    return {std::istreambuf_iterator<char>(in),std::istreambuf_iterator<char>()};
}
struct Write {
    uint32_t address;
    uint8_t size;
    uint16_t value;
    bool operator==(const Write&) const=default;
};
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576);
    std::vector<Write> writes;
    static uint32_t address(uint16_t s,uint16_t o){return (uint32_t{s}*16+o)&0xfffffu;}
    uint16_t word(uint16_t s,uint16_t o) const {
        const auto at=address(s,o);return static_cast<uint16_t>(bytes[at]|(uint16_t{bytes[(at+1u)&0xfffffu]}<<8));
    }
    void word(uint16_t s,uint16_t o,uint16_t v) {
        const auto at=address(s,o);bytes[at]=static_cast<uint8_t>(v);bytes[(at+1u)&0xfffffu]=static_cast<uint8_t>(v>>8);
        writes.push_back({at,2,v});
    }
    TimerIrqBus bus() {
        return {
            [this](uint16_t s,uint16_t o){return bytes[address(s,o)];},
            [this](uint16_t s,uint16_t o){return word(s,o);},
            [this](uint16_t s,uint16_t o){return uint32_t{word(s,o)}|(uint32_t{word(s,static_cast<uint16_t>(o+2u))}<<16);},
            [this](uint16_t s,uint16_t o,uint8_t v){const auto at=address(s,o);bytes[at]=v;writes.push_back({at,1,v});},
            [this](uint16_t s,uint16_t o,uint16_t v){word(s,o,v);},
            [this](uint16_t s,uint16_t o,uint32_t v){word(s,o,static_cast<uint16_t>(v));word(s,static_cast<uint16_t>(o+2u),static_cast<uint16_t>(v>>16));},
            [](uint16_t p)->uint8_t{require(p==0x61,"Unexpected drawing IRQ input");return 0;},
            [](uint16_t p,uint8_t){require(p==0x20 || p==0x61,"Unexpected drawing IRQ output");}
        };
    }
};
struct Reader {
    std::vector<uint8_t> bytes;
    size_t at=0;
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated ammunition HUD corpus");
        uint32_t value=0;for(unsigned i=0;i<n;++i)value|=uint32_t{bytes[at++]}<<(i*8);return value;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;
        for(auto* v:{&r.ax,&r.bx,&r.cx,&r.dx,&r.si,&r.di,&r.bp,&r.cs,&r.ds,&r.es,&r.ss,&r.sp,&r.ip})
            *v=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
    std::vector<DosGetTimeRegisters> trace(uint32_t count) {
        std::vector<DosGetTimeRegisters> result(count);
        for(auto member:{&DosGetTimeRegisters::ax,&DosGetTimeRegisters::bx,&DosGetTimeRegisters::cx,
                &DosGetTimeRegisters::dx,&DosGetTimeRegisters::si,&DosGetTimeRegisters::di,&DosGetTimeRegisters::bp,
                &DosGetTimeRegisters::cs,&DosGetTimeRegisters::ds,&DosGetTimeRegisters::es,&DosGetTimeRegisters::ss,
                &DosGetTimeRegisters::sp,&DosGetTimeRegisters::ip})
            for(auto& r:result)r.*member=static_cast<uint16_t>(number(2));
        for(auto& r:result)r.flags=number(4);
        return result;
    }
};
Memory loadImage(const char* path) {
    const auto exe=readFile(path);
    const auto word=[&](size_t at){require(at+2<=exe.size(),"Truncated MZ image");return uint32_t{exe[at]}|(uint32_t{exe[at+1]}<<8);};
    require(word(0)==0x5a4d && word(6)==468 && word(8)*16==0x770,"Original MZ layout differs");
    Memory memory;
    require(exe.size()>0x770 && exe.size()-0x770<=memory.bytes.size()-0x10000,"Original image exceeds memory");
    std::copy(exe.begin()+0x770,exe.end(),memory.bytes.begin()+0x10000);
    for(uint32_t i=0;i<468;++i) {
        const auto e=word(24)+i*4,at=0x10000+word(e+2)*16+word(e);
        require(at+2<=memory.bytes.size(),"Original relocation exceeds memory");
        const auto v=static_cast<uint16_t>((memory.bytes[at]|(uint16_t{memory.bytes[at+1]}<<8))+0x1000);
        memory.bytes[at]=static_cast<uint8_t>(v);memory.bytes[at+1]=static_cast<uint8_t>(v>>8);
    }
    return memory;
}
void compare(DosGetTimeRegisters actual,DosGetTimeRegisters expected,uint32_t index,size_t cursor) {
    const bool control=((actual.flags^expected.flags)&~uint32_t{0x8d5})==0;
    actual.flags=expected.flags;
    if(!control || actual!=expected) {
        std::cerr<<"case="<<index<<" observation="<<cursor<<" actual="<<std::hex<<actual.cs<<':'<<actual.ip
            <<" expected="<<expected.cs<<':'<<expected.ip<<std::dec<<'\n';
        throw std::runtime_error("Ammunition HUD register/control-flag trace differs");
    }
}
struct Totals {uint64_t comparisons=0,dispatches=0,transfers=0,replays=0;unsigned irqCases=0;};
template<class Operation>
void irqCheck(Operation original,Memory memory,const std::vector<uint8_t>& expected,DosGetTimeRegisters endpoint) {
    memory.word(0,0x70,0x0fbe);memory.word(0,0x72,0x1000);memory.word(0x40,0x6c,100);memory.word(0x40,0x6e,0);
    memory.bytes[Memory::address(0x40,0x40)]=2;memory.bytes[Memory::address(0x40,0x3f)]=0xa5;
    const auto bus=memory.bus();auto operation=original;const auto copies=[](uint16_t n){return n;};
    unsigned before=0;
    while(!operation.finished() && !(operation.registers().cs==0x1000 && operation.registers().ds==0x4000 && operation.registers().ip==0x1344)) {
        require(before++<20000,"Drawing-bank IRQ boundary was not reached");operation.advance(1,bus,copies);
    }
    require(!operation.finished(),"Drawing-bank IRQ boundary missing");
    operation.deliverTimerInterrupt(bus);require(operation.interruptInProgress(),"Drawing IRQ was not delegated");
    while(!operation.finished()) {
        require(before++<40000,"Drawing-bank IRQ replay did not finish");operation.advance(17,bus,copies);
        operation=Operation(operation.snapshot());
    }
    require(operation.returned() && operation.registers()==endpoint,"Drawing IRQ changed caller endpoint");
    require(operation.snapshot().timerInstructions==36 && operation.snapshot().timerDeliveries==1 && memory.word(0x40,0x6c)==101,
            "Drawing IRQ computed timer context differs");
    require(std::equal(memory.bytes.begin()+0xa0000,memory.bytes.begin()+0xb0001,expected.begin()+0xa0000),
            "Drawing IRQ changed original VGA endpoint");
}
template<class Operation>
void check(Operation original,const Memory& initial,const std::vector<uint8_t>& expected,
           const std::vector<Write>& writes,const std::vector<DosGetTimeRegisters>& trace,
           DosGetTimeRegisters endpoint,uint32_t index,bool error,Totals& totals) {
    for(uint16_t limit:{uint16_t{1},uint16_t{2},uint16_t{65535}})for(uint64_t budget:{1u,2u,17u,4096u}) {
        auto memory=initial;const auto bus=memory.bus();auto operation=original;
        const auto copies=[=](uint16_t n){return std::min(n,limit);};const auto zero=operation.snapshot();
        require(operation.advance(0,bus,copies)==0 && operation.snapshot()==zero && memory.writes.empty(),"Zero HUD grant changed state");
        size_t cursor=0;compare(operation.registers(),trace[0],index,cursor);++totals.comparisons;
        while(!operation.finished()) {
            const auto used=operation.advance(budget,bus,copies);require(used>0 && used<=budget,"HUD instruction grant differs");
            for(uint64_t step=0;step<used;++step) {
                require(cursor+1<trace.size(),"HUD exceeded original endpoint");const auto before=trace[cursor];
                if(before.cs==0x1000 && (before.ip==0x116a || before.ip==0x7ec) && before.cx) {
                    cursor+=std::min(before.cx,limit);require(cursor<trace.size(),"Truncated REP observations");
                    if(trace[cursor].ip==before.ip && trace[cursor].cx==0)++cursor;
                } else ++cursor;
            }
            require(cursor<trace.size(),"HUD observations exhausted");compare(operation.registers(),trace[cursor],index,cursor);
            ++totals.comparisons;operation=Operation(operation.snapshot());
        }
        const auto final=operation.snapshot();
        require(cursor+1==trace.size(),"HUD endpoint observation differs");
        require(operation.registers()==endpoint,"HUD endpoint registers/all flags differ");
        if constexpr(std::is_same_v<Operation,FrameHudOperation>)
            require(final.outcome==(error?FrameHudOutcome::RuntimeError:FrameHudOutcome::Returned),"HUD outcome differs");
        else require(final.outcome==(error?FrameDrawingOutcome::RuntimeError:FrameDrawingOutcome::Returned),"Drawing outcome differs");
        require(memory.writes==writes,"HUD ordered original writes differ");
        require(memory.bytes==expected,"HUD full 1 MiB post-state differs");
        require(operation.advance(100,bus,copies)==0 && operation.snapshot()==final,"Finished HUD changed state");
        totals.dispatches+=final.dispatchedInstructions;totals.transfers+=final.stringTransfers;++totals.replays;
    }
    if(index==1 || index==2170) {irqCheck(original,initial,expected,endpoint);++totals.irqCases;}
}
void replay(const char* path,const char* exe) {
    Reader reader{readFile(path)};
    for(char c:std::string("LZAMMO02"))require(reader.number(1)==static_cast<uint8_t>(c),"Ammunition corpus magic differs");
    const auto count=reader.number(4);require(count==2226,"Ammunition corpus domain differs");
    const auto image=loadImage(exe);Totals totals;unsigned errors=0;
    for(uint32_t index=0;index<count;++index) {
        require(reader.number(4)==index,"Ammunition case index differs");const auto error=reader.number(4);
        require(error<=1,"Ammunition outcome field differs");errors+=error;
        const auto entry=reader.registers(),endpoint=reader.registers();auto initial=image;
        const auto seeds=reader.number(4);require(seeds<300,"Ammunition seed count exceeds reserve");
        for(uint32_t i=0;i<seeds;++i) {
            const auto at=reader.number(4),length=reader.number(4);
            require(length<=65536 && uint64_t{at}+length<=initial.bytes.size() && reader.at+length<=reader.bytes.size(),"Ammunition seed exceeds memory");
            std::copy_n(reader.bytes.begin()+static_cast<std::ptrdiff_t>(reader.at),length,initial.bytes.begin()+at);reader.at+=length;
        }
        const auto states=reader.number(4);require(states>1 && states<2000000,"Ammunition trace reserve differs");
        const auto trace=reader.trace(states);const auto writeCount=reader.number(4);require(writeCount<200000,"Ammunition write reserve differs");
        auto expected=initial.bytes;std::vector<Write> writes;
        for(uint32_t i=0;i<writeCount;++i) {
            const auto at=reader.number(4),size=reader.number(1),value=reader.number(2);
            require((size==1 || size==2) && uint64_t{at}+size<=expected.size(),"Ammunition write exceeds memory");
            writes.push_back({at,static_cast<uint8_t>(size),static_cast<uint16_t>(value)});
            expected[at]=static_cast<uint8_t>(value);if(size==2)expected[at+1]=static_cast<uint8_t>(value>>8);
        }
        if(entry.ip==0x326e)check(FrameHudOperation(entry,0x1200,0x1000,0x200000),initial,expected,writes,trace,endpoint,index,error!=0,totals);
        else check(FrameDrawingOperation(entry,0x1000,0x200000),initial,expected,writes,trace,endpoint,index,error!=0,totals);
    }
    require(reader.at==reader.bytes.size() && errors==7 && totals.irqCases==2,"Ammunition corpus tail differs");
    std::cout<<"ammo_hud_original=ok cases="<<count<<" replays="<<totals.replays<<" comparisons="<<totals.comparisons
        <<" dispatches="<<totals.dispatches<<" transfers="<<totals.transfers<<" runtime_errors="<<errors
        <<" computed_irq_cases="<<totals.irqCases<<" full_frame_claim=0 work_clock_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r;r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3fe4;r.bp=0x3ffe;r.ip=0x326e;
    unsigned rejected=0;
    for(unsigned field=0;field<3;++field) {
        auto bad=r;if(field==0)bad.cs=0;else if(field==1)bad.ds=0;else bad.ip=0;
        try{FrameHudOperation op(bad,0x1200,0x1000,0);}catch(const std::invalid_argument&){++rejected;}
        bad.ip=0x7c5;if(field==2)bad.ip=0;
        try{FrameDrawingOperation op(bad,0x1000,0);}catch(const std::invalid_argument&){++rejected;}
    }
    require(rejected==6,"Ammunition/drawing accepted invalid entry");
    std::cout<<"ammo_hud_unit=ok entry_rejections=6\n";
}
}
int main(int argc,char** argv) {
    try{if(argc==1)unit();else if(argc==3)replay(argv[1],argv[2]);else throw std::runtime_error("Expected ammunition corpus and original EXE");return 0;}
    catch(const std::exception& error){std::cerr<<"ammo_hud=failed "<<error.what()<<'\n';return 1;}
}
